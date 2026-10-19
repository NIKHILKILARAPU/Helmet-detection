"""
Detection Analysis API Schemas and Response DTOs.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.violations import ViolationType, EvidenceModel


class DetectionBoxPercentage(BaseModel):
    x: float = Field(..., description="Left offset in percentage (0 - 100)")
    y: float = Field(..., description="Top offset in percentage (0 - 100)")
    width: float = Field(..., description="Width in percentage (0 - 100)")
    height: float = Field(..., description="Height in percentage (0 - 100)")


class DetectionBoxResponse(BaseModel):
    id: str = Field(..., description="Unique box identifier within detection frame")
    label: str = Field(..., description="Predicted class name (e.g. NO_HELMET, HELMET, MOTORCYCLE, PERSON)")
    classId: int = Field(..., description="Model class integer ID")
    category: str = Field(..., description="Classification category: HELMET_VIOLATION, HELMET_COMPLIANT, PERSON, VEHICLE, LICENSE_PLATE, OTHER")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Prediction confidence score")
    xyxy: List[float] = Field(..., description="Bounding box pixel coordinates [x1, y1, x2, y2]")
    normalized: List[float] = Field(..., description="Consistent normalized coordinates [x1, y1, x2, y2] (range 0.0 - 1.0)")
    percentage: DetectionBoxPercentage = Field(..., description="Percentage coordinates for UI rendering")
    color: str = Field(..., description="Visualization color code hex")


class RiderDetectionModel(BaseModel):
    """
    Structured distinct rider/head detection with stable ID and safe evidence crop.
    
    CRITICAL PRIVACY NOTICE:
    Rider crops are exclusively used for helmet compliance visual verification by human review officers.
    Never used for biometric/facial recognition or automated identity inference.
    """
    detectionId: str = Field(..., description="Stable rider detection identifier (e.g. rider-1)")
    caseId: Optional[str] = Field(default=None, description="Linked individual candidate case ID if ingested")
    label: str = Field(..., description="Raw model class label (e.g. 'Without Helmet', 'With Helmet')")
    classification: str = Field(..., description="Normalized classification: 'WITHOUT_HELMET', 'WITH_HELMET', or 'UNKNOWN'")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model prediction confidence")
    bbox: List[float] = Field(..., description="Bounding box pixel coordinates [x1, y1, x2, y2]")
    normalized: List[float] = Field(..., description="Consistent normalized coordinates [x1, y1, x2, y2] (range 0.0 - 1.0)")
    cropPath: Optional[str] = Field(None, description="Storage URI to cropped rider evidence image")
    isViolation: bool = Field(..., description="True if rider is without helmet and eligible for challan")
    vehicleType: Optional[str] = Field(default="UNKNOWN", description="Associated vehicle type: 'MOTORCYCLE', 'BICYCLE', 'UNCERTAIN', etc.")
    vehicleConfidence: Optional[float] = Field(default=None, description="Vehicle classification confidence")
    vehicleBbox: Optional[List[float]] = Field(default=None, description="Bounding box of associated vehicle")
    associationScore: Optional[float] = Field(default=None, description="Rider to vehicle spatial association score")
    eligibleForChallan: bool = Field(default=False, description="True if rider is on a motorized two-wheeler and Without Helmet")
    exclusionReason: Optional[str] = Field(default=None, description="Reason if excluded from challan creation (e.g. 'BICYCLE_EXCLUDED', 'UNCERTAIN_VEHICLE_TYPE')")
    helmetClass: Optional[str] = Field(default=None, description="Detected helmet classification label")
    helmetConfidence: Optional[float] = Field(default=None, description="Helmet classification confidence")
    reviewStatus: Optional[str] = Field(default=None, description="Diagnostic triage review status (e.g. PENDING_REVIEW, EXCLUDED_BICYCLE)")


class PlateMatchResult(BaseModel):
    """
    Number plate optical character recognition and vehicle/owner registry matching result.
    
    OWNER VS RIDER DISTINCTION:
    The matched person is strictly the REGISTERED OWNER of the vehicle, NOT the rider.
    Unmatched plates remain visible with UNVERIFIED status for manual reviewer investigation.
    """
    plateDetected: bool = Field(..., description="True if license plate region was identified")
    rawText: Optional[str] = Field(None, description="Raw OCR plate text output")
    normalizedPlate: Optional[str] = Field(None, description="Cleaned uppercase alphanumeric plate number")
    bbox: Optional[List[float]] = Field(None, description="Bounding box pixel coordinates [x1, y1, x2, y2]")
    cropPath: Optional[str] = Field(None, description="Storage URI to cropped license plate evidence")
    matchStatus: str = Field(
        ...,
        description="Registry verification status: 'VERIFIED', 'UNVERIFIED', or 'MANUAL_REQUIRED'",
    )
    matchSource: Optional[str] = Field(None, description="Source of match verification (e.g. STATE_VEHICLE_REGISTRY)")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="OCR and registry matching confidence")
    matchedVehicleId: Optional[str] = Field(None, description="Matched vehicle ObjectId in vehicles collection")
    matchedPersonId: Optional[str] = Field(None, description="Registered vehicle owner ObjectId in persons collection")
    ownerNameSnapshot: Optional[str] = Field(None, description="Registered owner full name (strictly registered owner, not rider)")
    vehicleDetails: Optional[Dict[str, Any]] = Field(None, description="Vehicle make, model, and registration status")


class IngestedCaseSummary(BaseModel):
    """Structured individual candidate violation case created for a distinct unhelmeted rider."""
    caseId: str = Field(..., description="Unique violation case identifier (e.g. TG-2026-08123)")
    detectionId: str = Field(..., description="Associated rider detection ID (e.g. rider-1)")
    violationType: ViolationType = Field(..., description="Violation classification")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Rider-specific violation confidence")
    cropPath: Optional[str] = Field(None, description="Storage URI to cropped rider evidence image")
    status: str = Field(default="PENDING_REVIEW", description="Candidate case status")
    bbox: List[float] = Field(..., description="Bounding box pixel coordinates [x1, y1, x2, y2]")
    normalized: List[float] = Field(..., description="Normalized coordinates [x1, y1, x2, y2]")
    isDeduplicated: bool = Field(default=False, description="True if this specific rider case was deduplicated")
    vehicleType: Optional[str] = Field(default="MOTORCYCLE", description="Associated vehicle classification")
    vehicleConfidence: Optional[float] = Field(default=None, description="Vehicle classification confidence")
    vehicleBbox: Optional[List[float]] = Field(default=None, description="Bounding box of associated vehicle")
    associationScore: Optional[float] = Field(default=None, description="Rider to vehicle spatial association score")
    eligibleForChallan: bool = Field(default=True, description="Challan eligibility flag")
    exclusionReason: Optional[str] = Field(default=None, description="Exclusion cause if ineligible")
    reviewStatus: Optional[str] = Field(default="PENDING_REVIEW", description="Diagnostic review triage status")


class DetectionAnalysisResponse(BaseModel):
    detected: bool = Field(..., description="True if one or more objects detected")
    totalDetections: int = Field(..., description="Total bounding boxes found")
    boxes: List[DetectionBoxResponse] = Field(default_factory=list, description="All detected bounding boxes")
    vehicles: List[DetectionBoxResponse] = Field(default_factory=list, description="Detected vehicle objects (excludes license plates)")
    persons: List[DetectionBoxResponse] = Field(default_factory=list, description="Detected person/rider objects")
    riders: List[RiderDetectionModel] = Field(
        default_factory=list,
        description="Structured distinct rider detections with stable IDs and evidence crops",
    )
    plateMatch: Optional[PlateMatchResult] = Field(
        None,
        description="License plate detection, OCR extraction, and registry lookup result",
    )
    helmetClassificationAvailable: bool = Field(
        ...,
        description="True if model contains validated helmet classes. False if running generic COCO weights."
    )
    helmetClassificationMessage: str = Field(..., description="Detailed status regarding helmet classification capability")
    isCandidateViolation: bool = Field(
        ...,
        description="True only if loaded model supports helmet classification AND a violation was detected"
    )
    violationType: Optional[ViolationType] = Field(None, description="Classified violation type if detected")
    violationConfidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence of the violation")
    caseId: Optional[str] = Field(None, description="Primary candidate case ID (for backward compatibility)")
    cases: List[IngestedCaseSummary] = Field(
        default_factory=list,
        description="List of independent candidate violation cases created for distinct unhelmeted riders",
    )
    status: str = Field(
        default="PENDING_REVIEW",
        description="Candidate violation triage status. Never automatically issues fines."
    )
    evidence: Optional[EvidenceModel] = Field(None, description="Storage reference and metadata for captured frame")
    modelRunId: Optional[str] = Field(None, description="Reference ID to model_runs audit collection")
    processingTimeMs: float = Field(..., ge=0.0, description="Total execution and parsing duration in milliseconds")
    timingBreakdown: Optional[Dict[str, float]] = Field(
        None,
        description="Granular stage latency breakdown in ms: modelInferenceMs, evidenceSavingMs, ocrMs, dbLookupMs, totalProcessingMs",
    )
    imageDimensions: Dict[str, int] = Field(..., description="Optical frame width and height")
    modelInfo: Dict[str, Any] = Field(..., description="Telemetry regarding model architecture and loaded classes")
    isDeduplicated: bool = Field(default=False, description="True if violation was suppressed due to camera cooldown window")
    cooldownSecondsRemaining: Optional[int] = Field(default=None, description="Seconds remaining in cooldown window if deduplicated")

