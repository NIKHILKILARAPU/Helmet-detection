"""
Operational Endpoints: Officer Shifts and Model Run Telemetry.

Implements:
- Officer shift tracking (ON_DUTY, BREAK, ON_LEAVE)
- AI model execution telemetry persistence
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from bson import ObjectId
from fastapi import APIRouter, Query, Depends, status
from pydantic import BaseModel, Field

from app.schemas.common import ApiResponse
from app.core.exceptions import ValidationError
from app.core.dependencies import require_authenticated_staff, require_supervisor_or_admin
from app.db.connection import get_db
from app.db.collections import COLLECTION_OFFICER_SHIFTS, COLLECTION_MODEL_RUNS

router = APIRouter(prefix="/operations", tags=["operations"])


class ShiftLogPayload(BaseModel):
    status: str = Field(..., pattern=r"^(ON_DUTY|ON_LEAVE|BREAK)$")
    notes: Optional[str] = Field(None, max_length=255)


class ModelRunPayload(BaseModel):
    cameraId: str
    modelName: str = Field(default="YOLOv8n-Traffic")
    modelVersion: str = Field(default="8.1.0")
    processingTimeMs: float = Field(..., ge=0.0)
    resultSummary: Dict[str, Any]
    status: str = Field(default="SUCCESS", pattern=r"^(SUCCESS|FAILED)$")
    errorMessage: Optional[str] = None


@router.post(
    "/shifts",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_201_CREATED,
    summary="Record or update officer shift status",
)
async def log_officer_shift(
    payload: ShiftLogPayload,
    current_user: dict = Depends(require_authenticated_staff),
):
    """Logs duty status change for currently authenticated officer."""
    db = get_db()
    now = datetime.now(timezone.utc)

    officer_id = ObjectId(current_user["id"]) if ObjectId.is_valid(current_user["id"]) else current_user["id"]

    shift_doc = {
        "officerId": officer_id,
        "officerName": current_user["name"],
        "officerRole": current_user["role"],
        "shiftStart": now,
        "shiftEnd": None,
        "status": payload.status,
        "notes": payload.notes,
        "createdAt": now,
        "updatedAt": now,
    }
    result = db[COLLECTION_OFFICER_SHIFTS].insert_one(shift_doc)
    shift_doc["id"] = str(result.inserted_id)
    shift_doc["_id"] = str(result.inserted_id)
    shift_doc["officerId"] = str(shift_doc["officerId"])

    return ApiResponse(
        success=True,
        data=shift_doc,
        message=f"Officer {current_user['name']} shift status updated to {payload.status}.",
    )


@router.get(
    "/shifts",
    response_model=ApiResponse[List[Dict[str, Any]]],
    status_code=status.HTTP_200_OK,
    summary="List officer shifts (Supervisors and Admins)",
)
async def list_officer_shifts(
    status_filter: Optional[str] = None,
    current_user: dict = Depends(require_supervisor_or_admin),
):
    """Returns shift logs for operational supervisory overview."""
    db = get_db()
    query = {}
    if status_filter:
        query["status"] = status_filter

    cursor = db[COLLECTION_OFFICER_SHIFTS].find(query).sort("shiftStart", -1).limit(100)
    items = []
    for doc in cursor:
        item = dict(doc)
        item["id"] = str(item["_id"])
        item["_id"] = str(item["_id"])
        item["officerId"] = str(item["officerId"])
        items.append(item)

    return ApiResponse(
        success=True,
        data=items,
        message=f"Retrieved {len(items)} officer shift log(s).",
    )


@router.post(
    "/model-runs",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_201_CREATED,
    summary="Store computer vision pipeline telemetry",
)
async def log_model_run(
    payload: ModelRunPayload,
    current_user: dict = Depends(require_authenticated_staff),
):
    """Stores model execution telemetry without claiming live inference occurred when model absent."""
    db = get_db()
    now = datetime.now(timezone.utc)

    doc = payload.model_dump()
    if ObjectId.is_valid(payload.cameraId):
        doc["cameraId"] = ObjectId(payload.cameraId)
    doc["processedAt"] = now

    result = db[COLLECTION_MODEL_RUNS].insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc["_id"] = str(result.inserted_id)
    doc["cameraId"] = str(doc["cameraId"])

    return ApiResponse(
        success=True,
        data=doc,
        message="Model run telemetry recorded.",
    )
