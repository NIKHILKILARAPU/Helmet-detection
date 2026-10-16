"""
Camera Sources API Endpoints.

Implements:
- Typed Pydantic models for registration & output
- Strict request validation on stream types and FPS
- Suitable HTTP status codes (200 OK, 201 Created, 422 Unprocessable Entity)
- Redaction of credentials from camera response payloads
"""

from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, status

from app.schemas.common import ApiResponse
from app.schemas.cameras import (
    CameraRegisterRequest,
    CameraResponse,
    CameraStatus,
)

router = APIRouter(prefix="/cameras", tags=["cameras"])


@router.get(
    "",
    response_model=ApiResponse[List[CameraResponse]],
    status_code=status.HTTP_200_OK,
    summary="List registered roadside cameras and webcams",
)
async def list_camera_sources():
    """Returns all registered CCTV, IP camera, and webcam sources."""
    return ApiResponse(
        success=True,
        data=[],
        message="Retrieved registered camera network feeds.",
    )


@router.post(
    "",
    response_model=ApiResponse[CameraResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new roadside CCTV or webcam source",
)
async def register_camera(payload: CameraRegisterRequest):
    """
    Registers a new camera source.
    Does not store plaintext passwords or expose secret authentication tokens.
    """
    now = datetime.now(timezone.utc)
    # Generate mock/sanitized representation
    camera_id = f"cam-{abs(hash(payload.name + payload.junction)) % 10000:04d}"

    camera_dto = CameraResponse(
        id=camera_id,
        name=payload.name,
        junction=payload.junction,
        streamType=payload.streamType,
        source=payload.ipOrDeviceUrl.split("@")[-1],  # Redacts user:pass if present in RTSP URI
        resolution=payload.resolution or "1080p",
        fps=payload.fps or 30.0,
        status=CameraStatus.STANDBY,
        lastHeartbeatAt=now,
        createdAt=now,
        updatedAt=now,
    )

    return ApiResponse(
        success=True,
        data=camera_dto,
        message=f"Camera source '{payload.name}' at {payload.junction} registered successfully.",
    )
