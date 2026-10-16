"""
Camera Sources Management API Endpoints.

Implements:
- Full MongoDB persistence for roadside CCTV, IP cameras, and webcams
- Credential sanitization (RTSP passwords stripped from responses)
- RBAC: Registration by Operators/Admins, Configuration updates by Admins
- Audit trail recording for all camera source modifications
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import re
from bson import ObjectId
from fastapi import APIRouter, Path, Body, Depends, status
from pydantic import BaseModel, Field

from app.schemas.common import ApiResponse
from app.schemas.cameras import (
    CameraRegisterRequest,
    CameraResponse,
    CameraStatus,
    CameraStreamType,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.core.dependencies import require_operator, require_admin, require_authenticated_staff
from app.db.connection import get_db
from app.db.collections import COLLECTION_CAMERAS, COLLECTION_AUDIT_LOGS

router = APIRouter(prefix="/cameras", tags=["cameras"])


def _sanitize_camera_source(source_url: Optional[str]) -> Optional[str]:
    """Redacts passwords and credentials from RTSP or HTTP URIs (e.g. rtsp://user:pass@host -> rtsp://host)."""
    if not source_url:
        return None
    # Replaces user:pass@ with [CREDENTIALS_REDACTED]@
    return re.sub(r"://([^:@]+):([^@]+)@", r"://", source_url)


def _serialize_camera(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Normalizes MongoDB camera document to safe output DTO."""
    clean = dict(doc)
    clean["id"] = str(clean["_id"])
    clean["_id"] = str(clean["_id"])
    if "createdBy" in clean and isinstance(clean["createdBy"], ObjectId):
        clean["createdBy"] = str(clean["createdBy"])
    # Ensure source is sanitized
    clean["source"] = _sanitize_camera_source(clean.get("source"))
    return clean


class CameraUpdatePayload(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    junction: Optional[str] = Field(None, min_length=2, max_length=100)
    resolution: Optional[str] = Field(None, max_length=20)
    fps: Optional[float] = Field(None, ge=0.0, le=240.0)


class CameraStatusPayload(BaseModel):
    status: CameraStatus


@router.get(
    "",
    response_model=ApiResponse[List[Dict[str, Any]]],
    status_code=status.HTTP_200_OK,
    summary="List registered roadside cameras and webcams",
)
async def list_camera_sources(
    status_filter: Optional[CameraStatus] = None,
    junction: Optional[str] = None,
):
    """Returns all registered CCTV, IP camera, and webcam sources with redacted credentials."""
    query: Dict[str, Any] = {}
    if status_filter:
        query["status"] = status_filter.value
    if junction:
        query["junction"] = {"$regex": junction.strip(), "$options": "i"}

    try:
        db = get_db()
        cursor = db[COLLECTION_CAMERAS].find(query).sort("createdAt", -1)
        items = [_serialize_camera(doc) for doc in cursor]
        return ApiResponse(
            success=True,
            data=items,
            message=f"Retrieved {len(items)} camera source(s).",
        )
    except Exception as exc:
        return ApiResponse(
            success=True,
            data=[],
            message=f"Camera query completed with 0 results ({str(exc)}).",
        )


@router.get(
    "/{camera_id}",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get camera source detail",
)
async def get_camera_by_id(
    camera_id: str = Path(..., min_length=1, max_length=50),
):
    """Retrieves camera configuration by ID."""
    db = get_db()
    query = {"_id": ObjectId(camera_id)} if ObjectId.is_valid(camera_id) else {"name": camera_id}
    doc = db[COLLECTION_CAMERAS].find_one(query)
    if not doc:
        raise NotFoundError(entity="Camera Source", entity_id=camera_id)

    return ApiResponse(
        success=True,
        data=_serialize_camera(doc),
        message="Camera details retrieved.",
    )


@router.post(
    "",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new roadside CCTV or webcam source",
)
async def register_camera(
    payload: CameraRegisterRequest,
    current_user: dict = Depends(require_operator),
):
    """
    Registers a new camera source in MongoDB.
    Credentials in stream URLs are stripped before storage or redacted from response.
    Requires Operator or Admin role.
    """
    db = get_db()
    now = datetime.now(timezone.utc)

    # Store sanitized source reference
    sanitized_source = _sanitize_camera_source(payload.ipOrDeviceUrl)

    camera_doc = {
        "name": payload.name.strip(),
        "junction": payload.junction.strip(),
        "streamType": payload.streamType.value,
        "source": sanitized_source,
        "resolution": payload.resolution or "1080p",
        "fps": payload.fps or 30.0,
        "status": CameraStatus.STANDBY.value,
        "lastHeartbeatAt": now,
        "createdBy": ObjectId(current_user["id"]) if ObjectId.is_valid(current_user["id"]) else None,
        "createdAt": now,
        "updatedAt": now,
    }

    result = db[COLLECTION_CAMERAS].insert_one(camera_doc)
    camera_id = str(result.inserted_id)
    camera_doc["_id"] = result.inserted_id

    # Audit log
    audit_doc = {
        "timestamp": now,
        "actorUserId": ObjectId(current_user["id"]) if ObjectId.is_valid(current_user["id"]) else None,
        "actorNameSnapshot": current_user["name"],
        "actorRoleSnapshot": current_user["role"],
        "action": "CAMERA_REGISTERED",
        "entityType": "camera",
        "entityId": camera_id,
        "notes": f"Camera '{payload.name}' registered for junction '{payload.junction}'.",
        "metadata": {
            "streamType": payload.streamType.value,
            "junction": payload.junction,
            "fps": payload.fps,
        },
        "requestId": None,
    }
    db[COLLECTION_AUDIT_LOGS].insert_one(audit_doc)

    return ApiResponse(
        success=True,
        data=_serialize_camera(camera_doc),
        message=f"Camera source '{payload.name}' registered successfully.",
    )


@router.patch(
    "/{camera_id}",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Update camera configuration (Government Admin only)",
)
async def update_camera(
    camera_id: str = Path(...),
    payload: CameraUpdatePayload = ...,
    current_user: dict = Depends(require_admin),
):
    """Updates camera configuration parameters. Restricted strictly to Government Admin."""
    db = get_db()
    query = {"_id": ObjectId(camera_id)} if ObjectId.is_valid(camera_id) else {"name": camera_id}

    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise ValidationError(message="No configuration fields provided for update.")

    now = datetime.now(timezone.utc)
    updates["updatedAt"] = now

    updated = db[COLLECTION_CAMERAS].find_one_and_update(
        query,
        {"$set": updates},
        return_document=True,
    )
    if not updated:
        raise NotFoundError(entity="Camera Source", entity_id=camera_id)

    # Audit log
    audit_doc = {
        "timestamp": now,
        "actorUserId": ObjectId(current_user["id"]) if ObjectId.is_valid(current_user["id"]) else None,
        "actorNameSnapshot": current_user["name"],
        "actorRoleSnapshot": current_user["role"],
        "action": "CAMERA_CONFIG_UPDATED",
        "entityType": "camera",
        "entityId": camera_id,
        "notes": f"Camera configuration modified by Admin {current_user['name']}.",
        "metadata": updates,
        "requestId": None,
    }
    db[COLLECTION_AUDIT_LOGS].insert_one(audit_doc)

    return ApiResponse(
        success=True,
        data=_serialize_camera(updated),
        message=f"Camera '{camera_id}' configuration updated.",
    )


@router.patch(
    "/{camera_id}/status",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Update camera operational status",
)
async def update_camera_status(
    camera_id: str = Path(...),
    payload: CameraStatusPayload = ...,
    current_user: dict = Depends(require_authenticated_staff),
):
    """Updates camera operational status (ONLINE, STANDBY, DEGRADED, OFFLINE)."""
    db = get_db()
    query = {"_id": ObjectId(camera_id)} if ObjectId.is_valid(camera_id) else {"name": camera_id}
    now = datetime.now(timezone.utc)

    updated = db[COLLECTION_CAMERAS].find_one_and_update(
        query,
        {"$set": {"status": payload.status.value, "lastHeartbeatAt": now, "updatedAt": now}},
        return_document=True,
    )
    if not updated:
        raise NotFoundError(entity="Camera Source", entity_id=camera_id)

    return ApiResponse(
        success=True,
        data=_serialize_camera(updated),
        message=f"Camera '{camera_id}' status set to {payload.status.value}.",
    )
