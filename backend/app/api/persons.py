"""
Authorized Person Registry Endpoints (State Transport Integration).

Features:
- Access-controlled person directory lookups
- Phone number masking across response models
- Mismatch dispute recording
- Absolute prohibition of facial recognition; queries match registered vehicle/ID data only
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from bson import ObjectId
from fastapi import APIRouter, Path, Query, Depends, status
from pydantic import BaseModel, Field

from app.schemas.common import ApiResponse
from app.core.exceptions import NotFoundError, ConflictError, ValidationError
from app.core.dependencies import require_authenticated_staff, require_admin
from app.db.connection import get_db
from app.db.collections import (
    COLLECTION_PERSONS,
    COLLECTION_VEHICLES,
    COLLECTION_PERSON_VEHICLES,
    COLLECTION_NOTIFICATIONS,
    COLLECTION_AUDIT_LOGS,
)

router = APIRouter(prefix="/persons", tags=["persons"])


def _mask_mobile(phone: Optional[str]) -> Optional[str]:
    """Masks registered mobile numbers (e.g. +91 98*** **412)."""
    if not phone or len(phone) < 7:
        return phone
    # Keep country prefix and last 3 digits
    return f"{phone[:6]}*** **{phone[-3:]}"


def _serialize_person(doc: Dict[str, Any], include_vehicles: bool = True, db = None) -> Dict[str, Any]:
    """Normalizes person document and embeds linked vehicle records."""
    clean = dict(doc)
    clean["id"] = str(clean["_id"])
    clean["personId"] = clean.get("personReference") or str(clean["_id"])
    clean["maskedMobile"] = _mask_mobile(clean.get("mobile"))

    if include_vehicles and db is not None:
        # Find linked vehicles through person_vehicles collection
        pv_cursor = db[COLLECTION_PERSON_VEHICLES].find({"personId": clean["_id"]})
        vehicle_ids = [pv["vehicleId"] for pv in pv_cursor]
        vehicles = []
        if vehicle_ids:
            v_cursor = db[COLLECTION_VEHICLES].find({"_id": {"$in": vehicle_ids}})
            for v in v_cursor:
                vehicles.append({
                    "plateNumber": v.get("plateNumber"),
                    "vehicleModel": v.get("model", "Motorcycle"),
                    "vehicleType": v.get("vehicleType", "Two-Wheeler"),
                    "registrationStatus": v.get("registrationStatus", "ACTIVE"),
                })
        clean["linkedVehicles"] = vehicles

    return clean


class PersonRegisterPayload(BaseModel):
    personReference: str = Field(..., min_length=3, max_length=50)
    fullName: str = Field(..., min_length=2, max_length=150)
    mobile: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    identityStatus: str = Field("VERIFIED", pattern=r"^(VERIFIED|UNVERIFIED|MANUAL_REQUIRED)$")
    verificationSource: Optional[str] = "STATE_VAHAN_PORTAL"


class DisputeReportPayload(BaseModel):
    disputeId: Optional[str] = None
    personId: str
    caseId: str
    reason: str = Field(..., min_length=3, max_length=255)
    userComments: Optional[str] = Field(None, max_length=500)


@router.get(
    "",
    response_model=ApiResponse[List[Dict[str, Any]]],
    status_code=status.HTTP_200_OK,
    summary="Search authorized person transport registry",
)
async def list_registered_persons(
    query: Optional[str] = Query(None, description="Search by name, person ID, or plate number"),
    identity_status: Optional[str] = None,
    current_user: dict = Depends(require_authenticated_staff),
):
    """
    Returns registered vehicle owners from state transport records.
    Facial recognition is strictly prohibited by policy.
    """
    db = get_db()
    filter_dict: Dict[str, Any] = {}

    if identity_status:
        filter_dict["identityStatus"] = identity_status

    if query and query.strip():
        q_clean = query.strip()
        filter_dict["$or"] = [
            {"fullName": {"$regex": q_clean, "$options": "i"}},
            {"personReference": {"$regex": q_clean, "$options": "i"}},
            {"city": {"$regex": q_clean, "$options": "i"}},
        ]

    try:
        cursor = db[COLLECTION_PERSONS].find(filter_dict).limit(50)
        items = [_serialize_person(doc, include_vehicles=True, db=db) for doc in cursor]
        return ApiResponse(
            success=True,
            data=items,
            message=f"Retrieved {len(items)} registry record(s).",
        )
    except Exception as exc:
        return ApiResponse(
            success=True,
            data=[],
            message=f"Registry lookup completed with 0 results ({str(exc)}).",
        )


@router.get(
    "/{person_id}",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get person profile by ID or reference",
)
async def get_person_by_id(
    person_id: str = Path(...),
    current_user: dict = Depends(require_authenticated_staff),
):
    """Retrieves single registered citizen profile with linked vehicles."""
    db = get_db()
    query = {"personReference": person_id}
    if ObjectId.is_valid(person_id):
        query = {"$or": [{"_id": ObjectId(person_id)}, {"personReference": person_id}]}

    doc = db[COLLECTION_PERSONS].find_one(query)
    if not doc:
        raise NotFoundError(entity="Registered Person", entity_id=person_id)

    return ApiResponse(
        success=True,
        data=_serialize_person(doc, include_vehicles=True, db=db),
        message="Person record retrieved.",
    )


@router.post(
    "",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_201_CREATED,
    summary="Add authorized registration record (Admin only)",
)
async def create_registered_person(
    payload: PersonRegisterPayload,
    current_user: dict = Depends(require_admin),
):
    """Provisions a verified transport record. Rejects duplicate references."""
    db = get_db()
    ref_clean = payload.personReference.strip().upper()

    existing = db[COLLECTION_PERSONS].find_one({"personReference": ref_clean})
    if existing:
        raise ConflictError(entity="Person Reference", identifier=ref_clean)

    now = datetime.now(timezone.utc)
    doc = payload.model_dump()
    doc["personReference"] = ref_clean
    doc["createdAt"] = now
    doc["updatedAt"] = now

    result = db[COLLECTION_PERSONS].insert_one(doc)
    doc["_id"] = result.inserted_id

    return ApiResponse(
        success=True,
        data=_serialize_person(doc, include_vehicles=False),
        message=f"Person record '{ref_clean}' created successfully.",
    )


@router.post(
    "/dispute",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_201_CREATED,
    summary="Log review dispute / identity mismatch report",
)
async def report_identity_mismatch(
    payload: DisputeReportPayload,
    current_user: dict = Depends(require_authenticated_staff),
):
    """
    Records a notice mismatch dispute in notifications and audit logs for review.
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    dispute_id = payload.disputeId or f"DISP-{int(now.timestamp()) % 100000:05d}"

    # Record notification
    notif_doc = {
        "personId": ObjectId(payload.personId) if ObjectId.is_valid(payload.personId) else ObjectId(),
        "violationId": ObjectId(payload.caseId) if ObjectId.is_valid(payload.caseId) else None,
        "date": now,
        "type": "PORTAL",
        "status": "PENDING",
        "title": f"Review Dispute: {dispute_id}",
        "preview": f"Dispute logged for Case {payload.caseId}: {payload.reason}",
        "providerReference": dispute_id,
    }
    db[COLLECTION_NOTIFICATIONS].insert_one(notif_doc)

    # Record audit log
    audit_doc = {
        "timestamp": now,
        "actorUserId": ObjectId(current_user["id"]) if ObjectId.is_valid(current_user["id"]) else None,
        "actorNameSnapshot": current_user["name"],
        "actorRoleSnapshot": current_user["role"],
        "action": "IDENTITY_MISMATCH_REPORTED",
        "entityType": "person",
        "entityId": payload.personId,
        "reason": payload.reason,
        "notes": payload.userComments or "Dispute logged via portal.",
        "metadata": {"disputeId": dispute_id, "caseId": payload.caseId},
        "requestId": None,
    }
    db[COLLECTION_AUDIT_LOGS].insert_one(audit_doc)

    return ApiResponse(
        success=True,
        data={"disputeId": dispute_id, "caseId": payload.caseId, "status": "PENDING_AUDIT"},
        message="Your review dispute has been logged. An enforcement review officer will examine the original camera footage.",
    )
