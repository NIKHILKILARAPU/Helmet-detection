"""
Violation Domain Schemas, Request Payloads, and Response DTOs.
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator


class ViolationType(str, Enum):
    NO_HELMET_RIDER = "NO_HELMET_RIDER"
    NO_HELMET_PILLION = "NO_HELMET_PILLION"
    TRIPLE_RIDING = "TRIPLE_RIDING"
    HELMET_STRAP_UNFASTENED = "HELMET_STRAP_UNFASTENED"


class ViolationStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    DRAFT_CREATED = "DRAFT_CREATED"
    REJECTED = "REJECTED"
    REVIEWED = "REVIEWED"


class EvidenceQuality(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class IdentityVerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    MANUAL_REQUIRED = "MANUAL_REQUIRED"


class BoundingBoxModel(BaseModel):
    """Detection bounding box overlay."""
    className: str = Field(..., description="Class: NO_HELMET, HELMET, RIDER, LICENSE_PLATE")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    coordinates: Union[Dict[str, float], List[float]] = Field(
        ..., description="Normalized coordinates [ymin, xmin, ymax, xmax] or {ymin, xmin, ymax, xmax}"
    )


class EvidenceModel(BaseModel):
    """Storage metadata reference for captured frame (never a raw binary blob)."""
    storagePath: str = Field(..., min_length=3, description="File storage path or object store URI")
    fileHash: Optional[str] = Field(None, description="SHA-256 integrity hash")
    mimeType: Optional[str] = Field("image/jpeg", description="MIME content type")
    width: Optional[int] = Field(None, ge=1)
    height: Optional[int] = Field(None, ge=1)
    fileSizeBytes: Optional[int] = Field(None, ge=0)


class ViolationBase(BaseModel):
    cameraId: str = Field(..., description="ID reference to source camera")
    capturedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    violationType: ViolationType
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score between 0.0 and 1.0")
    status: ViolationStatus = Field(default=ViolationStatus.PENDING_REVIEW)
    evidence: EvidenceModel
    evidenceQuality: EvidenceQuality = Field(default=EvidenceQuality.HIGH)
    boundingBoxes: List[BoundingBoxModel] = Field(default_factory=list)
    identityVerificationStatus: IdentityVerificationStatus = Field(default=IdentityVerificationStatus.UNVERIFIED)
    personId: Optional[str] = None
    vehicleId: Optional[str] = None
    reviewerNotes: Optional[str] = None
    rejectionReason: Optional[str] = None
    challanDraftNumber: Optional[str] = None
    draftAmountInr: Optional[float] = Field(None, ge=0.0)
    reviewedBy: Optional[str] = None
    reviewedAt: Optional[datetime] = None


class ViolationCreate(ViolationBase):
    """Payload when creating/ingesting a new candidate violation from camera detection."""
    pass


class ViolationResponse(ViolationBase):
    """Output DTO for candidate violations."""
    id: str = Field(..., description="Unique case record identifier")
    createdAt: datetime
    updatedAt: datetime


class ApproveDraftRequest(BaseModel):
    """Payload for approving candidate into a CHALLAN_DRAFT."""
    reviewerName: str = Field(..., min_length=2, max_length=100, description="Name of reviewing officer")
    notes: Optional[str] = Field(None, max_length=500, description="Officer verification notes")
    challanDraftNumber: Optional[str] = Field(
        None,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="Optional custom draft identifier",
    )
    draftAmountInr: Optional[float] = Field(None, ge=0.0, description="Draft penalty amount in INR")


class ApproveDraftResponse(BaseModel):
    """Response returned upon successful creation of a draft challan."""
    caseId: str
    challanDraftNumber: str
    status: ViolationStatus = ViolationStatus.DRAFT_CREATED
    draftAmountInr: Optional[float] = None
    reviewedBy: str
    reviewedAt: datetime
    message: str = "Candidate draft created for official supervisory sanction."


class RejectCaseRequest(BaseModel):
    """Payload for rejecting a false-positive candidate detection."""
    reviewerName: str = Field(..., min_length=2, max_length=100, description="Name of reviewing officer")
    reason: str = Field(..., min_length=3, max_length=255, description="Documented rejection reason")
    notes: Optional[str] = Field(None, max_length=500, description="Optional audit notes")


class RejectCaseResponse(BaseModel):
    """Response returned upon successful candidate rejection."""
    caseId: str
    status: ViolationStatus = ViolationStatus.REJECTED
    rejectionReason: str
    reviewedBy: str
    reviewedAt: datetime
    message: str = "Candidate case rejected and archived in audit log."


class ViolationFilterParams(BaseModel):
    """Validated query parameters for listing candidate violations."""
    status: Optional[ViolationStatus] = None
    violationType: Optional[ViolationType] = None
    cameraId: Optional[str] = None
    minConfidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    page: int = Field(1, ge=1, description="Page number")
    pageSize: int = Field(20, ge=1, le=100, description="Items per page")
