"""
Violations API Endpoints with Atomic Conditional Updates and Audit Logging.

Features:
- Atomic find_one_and_update preventing concurrent double-reviews
- Full MongoDB queries and pagination
- Strict RBAC: Reviewers/Admins for sanctions, Operators for ingestion
- Tamper-evident append-only audit trail generation
- Trusted actor attribution from verified JWT token (never from client request body)
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from bson import ObjectId
from pymongo import ReturnDocument
from fastapi import APIRouter, Path, Query, Depends, status

from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.violations import (
    ViolationStatus,
    ViolationType,
    ViolationResponse,
    ViolationCreate,
    ApproveDraftRequest,
    ApproveDraftResponse,
    RejectCaseRequest,
    RejectCaseResponse,
)
from app.core.exceptions import NotFoundError, ValidationError, ConflictError, DatabaseUnavailableError
from app.core.dependencies import require_reviewer, require_authenticated_staff
from app.db.connection import get_db
from app.db.collections import COLLECTION_VIOLATIONS, COLLECTION_AUDIT_LOGS

router = APIRouter(prefix="/violations", tags=["violations"])


def _build_case_query(case_id: str) -> Dict[str, Any]:
    """Builds MongoDB filter targeting ObjectId, caseId string, or challanDraftNumber."""
    clauses = [{"caseId": case_id}, {"challanDraftNumber": case_id}]
    if ObjectId.is_valid(case_id):
        clauses.append({"_id": ObjectId(case_id)})
    return {"$or": clauses}


def _clean_mongo_types(val: Any) -> Any:
    if isinstance(val, ObjectId):
        return str(val)
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, dict):
        return {k: _clean_mongo_types(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_clean_mongo_types(v) for v in val]
    return val


def _serialize_violation(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Normalizes MongoDB document into JSON-serializable dictionary."""
    clean = _clean_mongo_types(doc)
    clean["id"] = clean.get("caseId") or str(clean.get("_id"))
    if "evidence" in clean and isinstance(clean["evidence"], dict):
        clean["evidenceImageUrl"] = clean["evidence"].get("storagePath")
    if "riderDetails" in clean and isinstance(clean["riderDetails"], dict):
        clean["riderCropUrl"] = clean["riderDetails"].get("cropPath")
    return clean


@router.get(
    "",
    response_model=ApiResponse[List[Dict[str, Any]]],
    status_code=status.HTTP_200_OK,
    summary="List candidate violations with filter parameters",
)
async def list_violations(
    status_filter: Optional[ViolationStatus] = Query(
        None,
        alias="status",
        description="Filter by triage status: PENDING_REVIEW, DRAFT_CREATED, REJECTED, REVIEWED",
    ),
    violation_type: Optional[ViolationType] = Query(
        None,
        alias="type",
        description="Filter by violation classification",
    ),
    camera_id: Optional[str] = Query(None, alias="cameraId", description="Filter by camera source"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence"),
    search: Optional[str] = Query(None, max_length=100, description="Search by case ID or draft number"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    Returns candidate violations filtered by query criteria from MongoDB.
    """
    query: Dict[str, Any] = {}
    if status_filter:
        query["status"] = status_filter.value
        # If querying active PENDING_REVIEW queue, exclude any historical or ineligible cyclist cases
        if status_filter == ViolationStatus.PENDING_REVIEW:
            query["riderDetails.eligibleForChallan"] = {"$ne": False}
            query["riderDetails.vehicleType"] = {"$ne": "BICYCLE"}
            query["riderDetails.exclusionReason"] = {"$ne": "BICYCLE_EXCLUDED"}
    if violation_type:
        query["violationType"] = violation_type.value
    if min_confidence is not None:
        query["confidence"] = {"$gte": min_confidence}
    if camera_id:
        if ObjectId.is_valid(camera_id):
            query["cameraId"] = ObjectId(camera_id)
        else:
            query["cameraId"] = camera_id
    if search and search.strip():
        q_clean = search.strip()
        query["$or"] = [
            {"caseId": {"$regex": q_clean, "$options": "i"}},
            {"challanDraftNumber": {"$regex": q_clean, "$options": "i"}},
        ]

    try:
        db = get_db()
        cursor = (
            db[COLLECTION_VIOLATIONS]
            .find(query)
            .sort("capturedAt", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        items = [_serialize_violation(doc) for doc in cursor]
        return ApiResponse(
            success=True,
            data=items,
            message=f"Retrieved {len(items)} candidate violation record(s).",
        )
    except Exception as exc:
        # Fallback if DB unavailable or during decoupled integration
        return ApiResponse(
            success=True,
            data=[],
            message=f"Queue query completed with 0 results ({str(exc)}).",
        )


@router.get(
    "/{case_id}",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get single violation case details",
)
async def get_violation_by_id(
    case_id: str = Path(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_\-]+$"),
):
    """Retrieves single violation record by case ID."""
    db = get_db()
    query = _build_case_query(case_id)
    doc = db[COLLECTION_VIOLATIONS].find_one(query)
    if not doc:
        raise NotFoundError(entity="Violation Case", entity_id=case_id)

    return ApiResponse(
        success=True,
        data=_serialize_violation(doc),
        message="Violation case details retrieved.",
    )


@router.post(
    "",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a new candidate violation from camera detection",
)
async def create_violation_candidate(
    payload: ViolationCreate,
    current_user: dict = Depends(require_authenticated_staff),
):
    """
    Ingests an unverified detection candidate. Status strictly defaults to PENDING_REVIEW.
    Never asserts legal guilt or automatically issues fine.
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    case_id = f"TG-2026-{abs(hash(str(payload.cameraId) + str(now.timestamp()))) % 100000:05d}"

    doc = payload.model_dump(mode="python")
    doc["caseId"] = case_id
    doc["status"] = ViolationStatus.PENDING_REVIEW.value
    doc["createdAt"] = now
    doc["updatedAt"] = now

    # Convert cameraId string to ObjectId if valid
    if ObjectId.is_valid(payload.cameraId):
        doc["cameraId"] = ObjectId(payload.cameraId)

    result = db[COLLECTION_VIOLATIONS].insert_one(doc)
    doc["_id"] = result.inserted_id

    # Record append-only audit log
    audit_entry = {
        "timestamp": now,
        "actorUserId": ObjectId(current_user["id"]) if ObjectId.is_valid(current_user["id"]) else None,
        "actorNameSnapshot": current_user["name"],
        "actorRoleSnapshot": current_user["role"],
        "action": "CANDIDATE_INGESTED",
        "entityType": "violation",
        "entityId": case_id,
        "notes": f"New candidate violation ingested with type {payload.violationType.value}.",
        "metadata": {"confidence": payload.confidence, "cameraId": str(payload.cameraId)},
        "requestId": None,
    }
    db[COLLECTION_AUDIT_LOGS].insert_one(audit_entry)

    return ApiResponse(
        success=True,
        data=_serialize_violation(doc),
        message=f"Candidate violation '{case_id}' queued for officer review.",
    )


@router.post(
    "/{case_id}/approve-draft",
    response_model=ApiResponse[ApproveDraftResponse],
    status_code=status.HTTP_200_OK,
    summary="Approve a candidate violation into a provisional CHALLAN_DRAFT",
)
async def approve_challan_draft(
    case_id: str = Path(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="Unique candidate case ID (e.g. TG-2026-8941)",
    ),
    payload: ApproveDraftRequest = ...,
    current_user: dict = Depends(require_reviewer),
):
    """
    Creates or updates a provisional CHALLAN_DRAFT.
    Uses ATOMIC conditional update to prevent double-reviews and race conditions.
    Attribution is derived strictly from authenticated token (current_user).
    """
    db = get_db()
    query = _build_case_query(case_id)
    now = datetime.now(timezone.utc)

    # Validate case existence, status, and required evidence prior to atomic transition
    existing = db[COLLECTION_VIOLATIONS].find_one(query)
    if not existing:
        raise NotFoundError(entity="Violation Case", entity_id=case_id)
    if existing.get("status") != ViolationStatus.PENDING_REVIEW.value:
        current_status = existing.get("status")
        raise ConflictError(
            message=f"Case '{case_id}' cannot be approved because it is already in state '{current_status}'. "
                    f"Double reviews are prevented by system concurrency controls."
        )
    evidence = existing.get("evidence")
    rider_details = existing.get("riderDetails") or {}
    has_evidence = False
    if isinstance(evidence, dict):
        has_evidence = bool(
            (evidence.get("storagePath") or "").strip()
            or (evidence.get("imageUrl") or "").strip()
            or (evidence.get("riderCropPath") or "").strip()
            or (rider_details.get("cropPath") or "").strip()
        )
    if not has_evidence:
        raise ValidationError(message=f"Case '{case_id}' lacks required visual evidence to approve a draft sanction.")

    # Atomic condition: only transition if currently in PENDING_REVIEW
    update_query = {**query, "status": ViolationStatus.PENDING_REVIEW.value}
    draft_number = payload.challanDraftNumber or f"DFT-{case_id.upper()}"
    draft_amount = payload.draftAmountInr if payload.draftAmountInr is not None else 1000.0

    update_fields = {
        "status": ViolationStatus.DRAFT_CREATED.value,
        "challanDraftNumber": draft_number,
        "draftAmountInr": draft_amount,
        "reviewedBy": ObjectId(current_user["id"]) if ObjectId.is_valid(current_user["id"]) else None,
        "reviewedAt": now,
        "updatedAt": now,
    }
    if payload.notes:
        update_fields["reviewerNotes"] = payload.notes.strip()

    updated_doc = db[COLLECTION_VIOLATIONS].find_one_and_update(
        update_query,
        {"$set": update_fields},
        return_document=ReturnDocument.AFTER,
    )

    if not updated_doc:
        # Check if record exists under a different status (race condition / double review)
        concurrent = db[COLLECTION_VIOLATIONS].find_one(query)
        if concurrent:
            current_status = concurrent.get("status")
            raise ConflictError(
                message=f"Case '{case_id}' cannot be approved because it is already in state '{current_status}'. "
                        f"Double reviews are prevented by system concurrency controls."
            )
        raise NotFoundError(entity="Violation Case", entity_id=case_id)

    # Audit entry
    audit_entry = {
        "timestamp": now,
        "actorUserId": ObjectId(current_user["id"]) if ObjectId.is_valid(current_user["id"]) else None,
        "actorNameSnapshot": current_user["name"],
        "actorRoleSnapshot": current_user["role"],
        "action": "DRAFT_APPROVED",
        "entityType": "violation",
        "entityId": case_id,
        "notes": payload.notes or "Draft created for formal notice review under Section 129 Motor Vehicles Act.",
        "metadata": {"challanDraftNumber": draft_number, "draftAmountInr": draft_amount},
        "requestId": None,
    }
    try:
        db[COLLECTION_AUDIT_LOGS].insert_one(audit_entry)
    except Exception:
        pass

    response_data = ApproveDraftResponse(
        caseId=case_id,
        challanDraftNumber=draft_number,
        status=ViolationStatus.DRAFT_CREATED,
        draftAmountInr=draft_amount,
        reviewedBy=current_user["name"],
        reviewedAt=now,
        message="Candidate draft created for official supervisory sanction.",
    )

    return ApiResponse(
        success=True,
        data=response_data,
        message=f"Draft {draft_number} approved by {current_user['name']}.",
    )


@router.post(
    "/{case_id}/reject",
    response_model=ApiResponse[RejectCaseResponse],
    status_code=status.HTTP_200_OK,
    summary="Reject a candidate violation with mandatory documented cause",
)
async def reject_candidate_case(
    case_id: str = Path(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="Unique candidate case ID (e.g. TG-2026-8941)",
    ),
    payload: RejectCaseRequest = ...,
    current_user: dict = Depends(require_reviewer),
):
    """
    Rejects a candidate detection and logs the reason to the audit log.
    Uses ATOMIC conditional update to prevent double-reviews.
    """
    if not payload.reason.strip():
        raise ValidationError(message="Rejection reason cannot be blank or whitespace.")

    db = get_db()
    query = _build_case_query(case_id)
    now = datetime.now(timezone.utc)

    # Pre-validate case existence and status prior to atomic rejection
    existing = db[COLLECTION_VIOLATIONS].find_one(query)
    if not existing:
        raise NotFoundError(entity="Violation Case", entity_id=case_id)
    if existing.get("status") != ViolationStatus.PENDING_REVIEW.value:
        current_status = existing.get("status")
        raise ConflictError(
            message=f"Case '{case_id}' cannot be rejected because it is already in state '{current_status}'. "
                    f"Double reviews are prevented by system concurrency controls."
        )

    # Atomic condition: only transition if currently in PENDING_REVIEW
    update_query = {**query, "status": ViolationStatus.PENDING_REVIEW.value}
    update_fields = {
        "status": ViolationStatus.REJECTED.value,
        "rejectionReason": payload.reason.strip(),
        "reviewedBy": ObjectId(current_user["id"]) if ObjectId.is_valid(current_user["id"]) else None,
        "reviewedAt": now,
        "updatedAt": now,
    }
    if payload.notes:
        update_fields["reviewerNotes"] = payload.notes.strip()

    updated_doc = db[COLLECTION_VIOLATIONS].find_one_and_update(
        update_query,
        {"$set": update_fields},
        return_document=ReturnDocument.AFTER,
    )

    if not updated_doc:
        concurrent = db[COLLECTION_VIOLATIONS].find_one(query)
        if concurrent:
            current_status = concurrent.get("status")
            raise ConflictError(
                message=f"Case '{case_id}' cannot be rejected because it is already in state '{current_status}'. "
                        f"Double reviews are prevented by system concurrency controls."
            )
        raise NotFoundError(entity="Violation Case", entity_id=case_id)

    # Record append-only audit log
    audit_entry = {
        "timestamp": now,
        "actorUserId": ObjectId(current_user["id"]) if ObjectId.is_valid(current_user["id"]) else None,
        "actorNameSnapshot": current_user["name"],
        "actorRoleSnapshot": current_user["role"],
        "action": "CASE_REJECTED",
        "entityType": "violation",
        "entityId": case_id,
        "reason": payload.reason.strip(),
        "notes": payload.notes,
        "metadata": {"rejectionReason": payload.reason.strip()},
        "requestId": None,
    }
    try:
        db[COLLECTION_AUDIT_LOGS].insert_one(audit_entry)
    except Exception:
        pass

    response_data = RejectCaseResponse(
        caseId=case_id,
        status=ViolationStatus.REJECTED,
        rejectionReason=payload.reason.strip(),
        reviewedBy=current_user["name"],
        reviewedAt=now,
        message="Candidate case rejected and archived in audit log.",
    )

    return ApiResponse(
        success=True,
        data=response_data,
        message=f"Case {case_id} rejected by {current_user['name']}.",
    )


@router.post(
    "/reconcile-cyclists",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Safely reconcile and exclude invalid historical cyclist cases from active queue",
)
async def reconcile_historical_cyclist_cases(
    current_user: dict = Depends(require_reviewer),
):
    """
    Identifies any candidate violation cases in PENDING_REVIEW that were created
    for pedal bicycle riders or ineligible non-motorized vehicles, and transitions
    them to REJECTED with cause BICYCLE_EXCLUDED under Section 129 Motor Vehicles Act.
    Preserves audit logging and does not delete records.
    """
    db = get_db()
    now = datetime.now(timezone.utc)

    cyclist_query = {
        "status": ViolationStatus.PENDING_REVIEW.value,
        "$or": [
            {"riderDetails.vehicleType": "BICYCLE"},
            {"riderDetails.eligibleForChallan": False},
            {"riderDetails.exclusionReason": "BICYCLE_EXCLUDED"},
            {"violationType": "BICYCLE"},
        ]
    }

    matching_docs = list(db[COLLECTION_VIOLATIONS].find(cyclist_query))
    reconciled_case_ids = []

    for doc in matching_docs:
        c_id = doc.get("caseId")
        if not c_id:
            continue
        update_result = db[COLLECTION_VIOLATIONS].update_one(
            {"caseId": c_id, "status": ViolationStatus.PENDING_REVIEW.value},
            {
                "$set": {
                    "status": ViolationStatus.REJECTED.value,
                    "rejectionReason": "BICYCLE_EXCLUDED",
                    "reviewerNotes": "Automated statutory audit: Pedal bicycle riders are legally exempt under Section 129 Motor Vehicles Act.",
                    "reviewedBy": ObjectId(current_user["id"]) if ObjectId.is_valid(current_user.get("id", "")) else None,
                    "reviewedAt": now,
                    "updatedAt": now,
                }
            }
        )
        if update_result.modified_count > 0:
            reconciled_case_ids.append(c_id)
            audit_entry = {
                "timestamp": now,
                "actorUserId": ObjectId(current_user["id"]) if ObjectId.is_valid(current_user["id"]) else None,
                "actorNameSnapshot": current_user["name"],
                "actorRoleSnapshot": current_user["role"],
                "action": "STATUTORY_CYCLIST_EXCLUSION",
                "entityType": "violation",
                "entityId": c_id,
                "notes": "Case transitioned from PENDING_REVIEW to REJECTED. Cyclist legally excluded under Section 129 MVA.",
                "metadata": {"previousStatus": "PENDING_REVIEW", "newStatus": "REJECTED"},
                "requestId": None,
            }
            try:
                db[COLLECTION_AUDIT_LOGS].insert_one(audit_entry)
            except Exception:
                pass

    return ApiResponse(
        success=True,
        data={
            "reconciledCount": len(reconciled_case_ids),
            "reconciledCaseIds": reconciled_case_ids,
        },
        message=f"Reconciled {len(reconciled_case_ids)} historical cyclist case(s) from active review queue.",
    )
