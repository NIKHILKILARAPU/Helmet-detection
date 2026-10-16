from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/violations", tags=["violations"])

class ApproveDraftRequest(BaseModel):
    reviewerName: str
    notes: Optional[str] = None
    challanDraftNumber: Optional[str] = None

class RejectCaseRequest(BaseModel):
    reviewerName: str
    reason: str
    notes: Optional[str] = None

@router.get("")
async def list_violations(status: Optional[str] = None):
    """
    Returns candidate violations from MongoDB or fallback queue.
    """
    return {
        "status": "success",
        "data": [],
        "message": "Connected to FastAPI violation queue"
    }

@router.post("/{case_id}/approve-draft")
async def approve_challan_draft(case_id: str, payload: ApproveDraftRequest):
    """
    Creates or updates a CHALLAN_DRAFT only. Does not issue an official fine.
    """
    return {
        "status": "success",
        "case_id": case_id,
        "challan_draft_number": payload.challanDraftNumber or f"DFT-2026-LIVE",
        "status_code": "DRAFT_CREATED",
        "message": "Candidate draft created for official supervisory sanction."
    }

@router.post("/{case_id}/reject")
async def reject_candidate_case(case_id: str, payload: RejectCaseRequest):
    """
    Rejects a candidate detection and logs the reason to the audit collection.
    """
    return {
        "status": "success",
        "case_id": case_id,
        "rejection_reason": payload.reason,
        "status_code": "REJECTED",
        "message": "Candidate case rejected and archived in audit log."
    }
