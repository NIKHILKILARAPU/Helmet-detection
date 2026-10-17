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
    category: str = Field(..., description="Classification category: HELMET_VIOLATION, HELMET_COMPLIANT, PERSON, VEHICLE, OTHER")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Prediction confidence score")
    xyxy: List[float] = Field(..., description="Bounding box pixel coordinates [xmin, ymin, xmax, ymax]")
    normalized: List[float] = Field(..., description="Normalized coordinates [ymin, xmin, ymax, xmax]")
    percentage: DetectionBoxPercentage = Field(..., description="Percentage coordinates for UI rendering")
    color: str = Field(..., description="Visualization color code hex")


class DetectionAnalysisResponse(BaseModel):
    detected: bool = Field(..., description="True if one or more objects detected")
    totalDetections: int = Field(..., description="Total bounding boxes found")
    boxes: List[DetectionBoxResponse] = Field(default_factory=list, description="All detected bounding boxes")
    vehicles: List[DetectionBoxResponse] = Field(default_factory=list, description="Detected vehicle objects")
    persons: List[DetectionBoxResponse] = Field(default_factory=list, description="Detected person/rider objects")
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
    caseId: Optional[str] = Field(None, description="Generated candidate case ID if ingested to reviewer queue")
    status: str = Field(
        default="PENDING_REVIEW",
        description="Candidate violation triage status. Never automatically issues fines."
    )
    evidence: Optional[EvidenceModel] = Field(None, description="Storage reference and metadata for captured frame")
    modelRunId: Optional[str] = Field(None, description="Reference ID to model_runs audit collection")
    processingTimeMs: float = Field(..., ge=0.0, description="CPU execution and parsing duration in milliseconds")
    imageDimensions: Dict[str, int] = Field(..., description="Optical frame width and height")
    modelInfo: Dict[str, Any] = Field(..., description="Telemetry regarding model architecture and loaded classes")
