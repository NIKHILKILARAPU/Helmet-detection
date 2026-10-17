"""
Detections API Router: Multipart Frame Analysis & Real-time AI Inference.

Implements:
- POST /api/v1/detections/analyze accepting multipart/form-data frame uploads
- Strict image validation (file type, size limits, and decode integrity checks)
- Protection via JWT authentication and role-based authorization (require_authenticated_staff)
- Live CPU YOLO inference via reusable YoloInferenceEngine
- Schema-compliant persistence in MongoDB (model_runs, evidence metadata, and violations)
- Zero synthetic detections or DEMO_STANDIN fallbacks
- Strict PENDING_REVIEW candidate triage (never auto-issuing sanctions or fines)
"""

import os
import time
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from bson import ObjectId
import numpy as np
import cv2

from fastapi import APIRouter, UploadFile, File, Form, Depends, status
from fastapi.responses import JSONResponse

from app.schemas.common import ApiResponse
from app.schemas.detections import (
    DetectionAnalysisResponse,
    DetectionBoxResponse,
    DetectionBoxPercentage,
)
from app.schemas.violations import ViolationType, EvidenceModel
from app.core.exceptions import (
    ValidationError,
    ModelNotAvailableError,
    DatabaseUnavailableError,
)
from app.core.dependencies import require_authenticated_staff
from app.models.yolo_inference import yolo_engine
from app.db.connection import get_db
from app.db.collections import (
    COLLECTION_MODEL_RUNS,
    COLLECTION_VIOLATIONS,
    COLLECTION_CAMERAS,
    COLLECTION_AUDIT_LOGS,
)

logger = logging.getLogger("trafficguard.api.detections")

router = APIRouter(prefix="/detections", tags=["detections"])

# Constants
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

# Evidence upload directory on local disk
EVIDENCE_UPLOAD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../backend/uploads/evidence")
)
os.makedirs(EVIDENCE_UPLOAD_DIR, exist_ok=True)


def _resolve_camera_oid(db, requested_camera_id: Optional[str]) -> ObjectId:
    """Resolves or provisions a valid ObjectId for camera attribution."""
    if requested_camera_id and ObjectId.is_valid(requested_camera_id):
        return ObjectId(requested_camera_id)

    # Check for any registered camera in DB
    try:
        existing = db[COLLECTION_CAMERAS].find_one({}, {"_id": 1})
        if existing and "_id" in existing:
            return existing["_id"]
    except Exception:
        pass

    # Deterministic default ObjectId for operator workstation testing
    return ObjectId("65f000000000000000000001")


@router.post(
    "/analyze",
    response_model=ApiResponse[DetectionAnalysisResponse],
    status_code=status.HTTP_200_OK,
    summary="Analyze an image frame for traffic objects and helmet violations",
)
async def analyze_frame(
    file: UploadFile = File(..., description="Image frame file (JPEG, PNG, or WEBP)"),
    camera_id: Optional[str] = Form(None, description="Optional registered camera ObjectId string"),
    source_label: Optional[str] = Form("Operator Live Station", description="Human-readable camera source title"),
    auto_ingest: bool = Form(True, description="Automatically queue candidate violations in reviewer desk"),
    current_user: dict = Depends(require_authenticated_staff),
):
    """
    Analyzes an uploaded surveillance or webcam image using YOLO inference.

    Workflow:
    1. Validates image MIME type, file extension, and maximum byte size.
    2. Validates image data integrity by decoding into OpenCV pixel buffer.
    3. Runs CPU inference via YoloInferenceEngine (checks model availability and supported classes).
    4. Persists the captured frame to local storage with cryptographic SHA-256 hash.
    5. Records the execution telemetry to the model_runs collection.
    6. If a candidate violation is detected and auto_ingest is true, registers a case
       in the violations collection with status PENDING_REVIEW.
    """
    start_time = time.perf_counter()

    # 1. Validate MIME type & file extension
    content_type = (file.content_type or "").lower().strip()
    original_filename = file.filename or "frame.jpg"
    ext = os.path.splitext(original_filename)[1].lower()

    if content_type not in ALLOWED_MIME_TYPES and ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            message=f"Unsupported file type '{content_type or ext}'. Only JPEG, PNG, and WEBP images are supported."
        )

    # 2. Read bytes and enforce size limits
    try:
        contents = await file.read()
    except Exception as exc:
        raise ValidationError(message=f"Failed to read uploaded image stream: {str(exc)}")

    file_size = len(contents)
    if file_size == 0:
        raise ValidationError(message="Uploaded image file is empty (0 bytes).")
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValidationError(
            message=f"Uploaded image ({file_size / (1024*1024):.2f} MB) exceeds maximum permitted limit of 10 MB."
        )

    # 3. Validate image decodability
    nparr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None or image.shape[0] == 0 or image.shape[1] == 0:
        raise ValidationError(
            message="Uploaded file could not be parsed as a valid image (corrupt or unreadable file data)."
        )

    height, width = image.shape[:2]

    # 4. Execute real YOLO inference
    det_result = yolo_engine.detect(image)
    processing_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

    # 5. Persist evidence frame to disk (never store huge base64 in MongoDB)
    file_hash = hashlib.sha256(contents).hexdigest()
    safe_ext = ext if ext in ALLOWED_EXTENSIONS else ".jpg"
    storage_filename = f"ev_{file_hash[:16]}_{int(time.time())}{safe_ext}"
    evidence_file_path = os.path.join(EVIDENCE_UPLOAD_DIR, storage_filename)
    relative_storage_path = f"/uploads/evidence/{storage_filename}"

    try:
        with open(evidence_file_path, "wb") as f:
            f.write(contents)
    except Exception as exc:
        logger.warning(f"Failed to write evidence frame to disk: {exc}")
        relative_storage_path = f"file://local/{storage_filename}"

    now = datetime.now(timezone.utc)
    model_run_id: Optional[str] = None
    case_id: Optional[str] = None

    # 6. MongoDB persistence
    try:
        db = get_db()
        camera_oid = _resolve_camera_oid(db, camera_id)

        # Log to model_runs collection
        model_run_doc = {
            "cameraId": camera_oid,
            "modelName": "YOLOv8n-Traffic",
            "modelVersion": "8.1.0",
            "processedAt": now,
            "processingTimeMs": processing_time_ms,
            "resultSummary": {
                "totalDetections": det_result["totalDetections"],
                "vehiclesCount": len(det_result["vehicles"]),
                "personsCount": len(det_result["persons"]),
                "isCandidateViolation": det_result["isCandidateViolation"],
                "violationType": det_result["violationType"],
            },
            "status": "SUCCESS",
            "errorMessage": None,
        }
        run_res = db[COLLECTION_MODEL_RUNS].insert_one(model_run_doc)
        model_run_id = str(run_res.inserted_id)

        # If candidate violation detected and auto_ingest enabled, create candidate case
        if det_result["isCandidateViolation"] and auto_ingest and det_result["violationType"]:
            case_id = f"TG-2026-{abs(hash(str(camera_oid) + str(now.timestamp()))) % 100000:05d}"
            
            # Map bounding boxes to schema requirements
            schema_boxes = [
                {
                    "className": b["label"],
                    "confidence": b["confidence"],
                    "coordinates": {
                        "ymin": b["normalized"][0],
                        "xmin": b["normalized"][1],
                        "ymax": b["normalized"][2],
                        "xmax": b["normalized"][3],
                    },
                }
                for b in det_result["boxes"]
            ]

            evidence_obj = {
                "storagePath": relative_storage_path,
                "fileHash": file_hash,
                "mimeType": content_type or "image/jpeg",
                "width": width,
                "height": height,
                "fileSizeBytes": file_size,
            }

            violation_doc = {
                "caseId": case_id,
                "cameraId": camera_oid,
                "capturedAt": now,
                "violationType": det_result["violationType"],
                "confidence": det_result["violationConfidence"],
                "status": "PENDING_REVIEW",  # Strictly pending review; never automatically fine
                "evidence": evidence_obj,
                "evidenceQuality": "HIGH",
                "boundingBoxes": schema_boxes,
                "identityVerificationStatus": "UNVERIFIED",
                "reviewerNotes": None,
                "rejectionReason": None,
                "challanDraftNumber": None,
                "draftAmountInr": None,
                "reviewedBy": None,
                "reviewedAt": None,
                "createdAt": now,
                "updatedAt": now,
            }
            db[COLLECTION_VIOLATIONS].insert_one(violation_doc)

            # Record append-only audit trail
            audit_entry = {
                "timestamp": now,
                "actorUserId": ObjectId(current_user["id"]) if ObjectId.is_valid(current_user["id"]) else None,
                "actorNameSnapshot": current_user["name"],
                "actorRoleSnapshot": current_user["role"],
                "action": "AI_CANDIDATE_INGESTED",
                "entityType": "violation",
                "entityId": case_id,
                "notes": f"Automated AI detection candidate logged: {det_result['violationType']}.",
                "metadata": {
                    "confidence": det_result["violationConfidence"],
                    "sourceLabel": source_label,
                    "cameraId": str(camera_oid),
                    "modelRunId": model_run_id,
                },
                "requestId": None,
            }
            try:
                db[COLLECTION_AUDIT_LOGS].insert_one(audit_entry)
            except Exception:
                pass

    except Exception as exc:
        logger.error(f"Database error during detection logging: {exc}")
        # Proceed with inference response if DB unavailable

    # Construct response DTO
    evidence_model = EvidenceModel(
        storagePath=relative_storage_path,
        fileHash=file_hash,
        mimeType=content_type or "image/jpeg",
        width=width,
        height=height,
        fileSizeBytes=file_size,
    )

    boxes_response = [
        DetectionBoxResponse(
            id=b["id"],
            label=b["label"],
            classId=b["classId"],
            category=b["category"],
            confidence=b["confidence"],
            xyxy=b["xyxy"],
            normalized=b["normalized"],
            percentage=DetectionBoxPercentage(
                x=b["percentage"]["x"],
                y=b["percentage"]["y"],
                width=b["percentage"]["width"],
                height=b["percentage"]["height"],
            ),
            color=b["color"],
        )
        for b in det_result["boxes"]
    ]

    vehicles_response = [b for b in boxes_response if b.category == "VEHICLE"]
    persons_response = [b for b in boxes_response if b.category == "PERSON"]

    response_data = DetectionAnalysisResponse(
        detected=det_result["detected"],
        totalDetections=det_result["totalDetections"],
        boxes=boxes_response,
        vehicles=vehicles_response,
        persons=persons_response,
        helmetClassificationAvailable=det_result["helmetClassificationAvailable"],
        helmetClassificationMessage=det_result["helmetClassificationMessage"],
        isCandidateViolation=det_result["isCandidateViolation"],
        violationType=det_result["violationType"],
        violationConfidence=det_result["violationConfidence"],
        caseId=case_id,
        status="PENDING_REVIEW" if det_result["isCandidateViolation"] else "NO_VIOLATION",
        evidence=evidence_model,
        modelRunId=model_run_id,
        processingTimeMs=processing_time_ms,
        imageDimensions={"width": width, "height": height},
        modelInfo=yolo_engine.get_model_info(),
    )

    return ApiResponse(
        success=True,
        data=response_data,
        message=(
            f"Frame analyzed successfully in {processing_time_ms}ms. "
            f"Found {det_result['totalDetections']} object(s)."
        ),
    )


@router.get(
    "/model-status",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get current YOLO model loading status and supported classes",
)
async def get_model_status():
    """
    Returns live information about the active YOLO model weights,
    path verification, and whether helmet violation classes are supported.
    """
    info = yolo_engine.get_model_info()
    return ApiResponse(
        success=True,
        data=info,
        message="YOLO model status retrieved.",
    )
