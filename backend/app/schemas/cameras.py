"""
Camera Domain Schemas, Request Payloads, and Response DTOs.
"""

from enum import Enum
from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class CameraStreamType(str, Enum):
    WEBCAM = "WEBCAM"
    IP_CAMERA = "IP_CAMERA"
    CCTV_STREAM = "CCTV_STREAM"


class CameraStatus(str, Enum):
    ONLINE = "ONLINE"
    STANDBY = "STANDBY"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"


class CameraRegisterRequest(BaseModel):
    """Payload to register a roadside camera or webcam source."""
    name: str = Field(..., min_length=2, max_length=100, description="Camera feed name")
    junction: str = Field(..., min_length=2, max_length=100, description="Intersection or road checkpoint")
    streamType: CameraStreamType = Field(..., description="Camera source type")
    ipOrDeviceUrl: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Stream URI, RTSP address, or hardware webcam device index (e.g. 0)",
    )
    resolution: Optional[str] = Field("1080p", max_length=20, description="Optical resolution")
    fps: Optional[float] = Field(30.0, ge=0.0, le=240.0, description="Frame rate per second")


class CameraResponse(BaseModel):
    """Output DTO for registered cameras."""
    id: str = Field(..., description="Unique camera ID")
    name: str
    junction: str
    streamType: CameraStreamType
    source: Optional[str] = Field(None, description="Sanitized source reference (credentials excluded)")
    resolution: Optional[str] = None
    fps: Optional[float] = None
    status: CameraStatus = CameraStatus.STANDBY
    lastHeartbeatAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime
