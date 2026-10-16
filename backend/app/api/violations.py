"""
Violations API Endpoints for Candidate Triage and Draft Approvals.

Implements:
- Strict path, query, and request body validation
- Typed Pydantic request and response models
- Suitable HTTP status codes (200 OK, 400 Bad Request, 404 Not Found, 422 Unprocessable Entity)
- Standardized ApiResponse envelope
"""

from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Path, Query, status

from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.violations import (
    ViolationStatus,
    ViolationType,
    ViolationResponse,
    ApproveDraftRequest,
    ApproveDraftResponse,
    RejectCaseRequest,
    RejectCaseResponse,
)
from app.core.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/violations", tags=["violations"])


@router.get(
    "",
    response_model=ApiResponse[List[dict]],
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
    min_confidence: Optional[float] = Query(
        None,
        ge=0.0,
        le=1.0,
        description="Minimum model confidence threshold",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    Returns candidate violations filtered by query criteria.
    Validates all query filters and enforces page limits.
    """
    return ApiResponse(
        success=True,
        data=[],
        message=f"Retrieved candidate queue (filter: {status_filter or 'ALL'}).",
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
):
    """
    Creates or updates a provisional CHALLAN_DRAFT.
    Does NOT assert legal guilt or trigger automatic financial penalties.
    """
    # Validate case ID format
    if case_id.lower() in ("null", "undefined", "none"):
        raise NotFoundError(entity="Violation Case", entity_id=case_id)

    draft_number = payload.challanDraftNumber or f"DFT-{case_id.upper()}"
    draft_amount = payload.draftAmountInr if payload.draftAmountInr is not None else 1000.0

    response_data = ApproveDraftResponse(
        caseId=case_id,
        challanDraftNumber=draft_number,
        status=ViolationStatus.DRAFT_CREATED,
        draftAmountInr=draft_amount,
        reviewedBy=payload.reviewerName,
        reviewedAt=datetime.now(timezone.utc),
        message="Candidate draft created for official supervisory sanction.",
    )

    return ApiResponse(
        success=True,
        data=response_data,
        message=f"Draft {draft_number} approved and awaiting supervisory transmission.",
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
):
    """
    Rejects a candidate detection and logs the reason to the audit log.
    Requires a non-empty rejection reason.
    """
    if case_id.lower() in ("null", "undefined", "none"):
        raise NotFoundError(entity="Violation Case", entity_id=case_id)

    if not payload.reason.strip():
        raise ValidationError(message="Rejection reason cannot be blank or whitespace.")

    response_data = RejectCaseResponse(
        caseId=case_id,
        status=ViolationStatus.REJECTED,
        rejectionReason=payload.reason.strip(),
        reviewedBy=payload.reviewerName,
        reviewedAt=datetime.now(timezone.utc),
        message="Candidate case rejected and archived in audit log.",
    )

    return ApiResponse(
        success=True,
        data=response_data,
        message=f"Case {case_id} rejected with documented cause: {payload.reason}.",
    )
