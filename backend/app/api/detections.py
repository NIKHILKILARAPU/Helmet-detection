"""
Detections API Router: Multipart Frame Analysis & Real-time AI Inference.

Implements:
- POST /api/v1/detections/analyze accepting multipart/form-data frame uploads
- Strict image validation (file type, size limits, and decode integrity checks)
- Protection via JWT authentication and role-based authorization (require_authenticated_staff)
- Live CPU YOLO or Roboflow hosted inference engine
- Sanitization of placeholder values ("string", "null", "undefined") for optional fields
- Database validation of supplied camera_id against registered cameras
- Consistent normalized bounding-box coordinates [x1, y1, x2, y2]
- Distinct rider extraction preserving all candidates with stable IDs, classifications, and crops
- Separate number plate detection and OCR extraction matching against registered vehicles and registered owners
- Strict owner vs rider separation: registered owners are never assumed to be the rider; facial recognition is forbidden
- Candidate violation triage strictly queued as PENDING_REVIEW (never auto-issuing sanctions or fines)
- Detailed stage latency timing breakdown: modelInferenceMs, evidenceSavingMs, ocrMs, dbLookupMs, totalProcessingMs
"""

import os
import time
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from bson import ObjectId
import numpy as np
import cv2

from fastapi import APIRouter, UploadFile, File, Form, Depends, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.schemas.common import ApiResponse
from app.schemas.detections import (
    DetectionAnalysisResponse,
    DetectionBoxResponse,
    DetectionBoxPercentage,
    RiderDetectionModel,
    PlateMatchResult,
)
from app.schemas.violations import ViolationType, EvidenceModel
from app.core.exceptions import (
    ValidationError,
    NotFoundError,
    ModelNotAvailableError,
    RemoteInferenceError,
    DatabaseUnavailableError,
)
from app.core.dependencies import require_authenticated_staff
from app.models.yolo_inference import yolo_engine
from app.models.roboflow_inference import roboflow_engine
from app.services.plate_reader import (
    extract_plate_text_from_crop,
    match_plate_against_registry,
    is_placeholder_string,
)
from app.db.connection import get_db
from app.db.collections import (
    COLLECTION_MODEL_RUNS,
    COLLECTION_VIOLATIONS,
    COLLECTION_CAMERAS,
    COLLECTION_AUDIT_LOGS,
    COLLECTION_VEHICLES,
    COLLECTION_PERSON_VEHICLES,
    COLLECTION_PERSONS,
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


def sanitize_placeholder(val: Optional[str]) -> Optional[str]:
    """
    Sanitizes string inputs to prevent placeholder strings (e.g. 'string', 'null',
    'undefined', 'none', '') from being interpreted as real IDs or data.
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("string", "null", "undefined", "none", "nan"):
        return None
    return s


def _resolve_camera_oid(db, requested_camera_id: Optional[str]) -> ObjectId:
    """
    Resolves camera ID for attribution.

    Validation rules:
    - If camera_id is supplied and non-placeholder:
      - Validates 24-character hexadecimal ObjectId syntax (HTTP 400 on failure).
      - Checks database registration in cameras collection (HTTP 404 on failure).
    - If camera_id is not supplied or is a placeholder ('string', 'null', 'undefined'):
      - Preserves optional field contract: falls back to any registered camera or test station.
    """
    clean_id = sanitize_placeholder(requested_camera_id)
    if clean_id is not None:
        if not ObjectId.is_valid(clean_id):
            raise ValidationError(
                message=f"Supplied camera_id '{clean_id}' is not a valid 24-character hexadecimal ObjectId."
            )
        cam_oid = ObjectId(clean_id)
        existing = db[COLLECTION_CAMERAS].find_one({"_id": cam_oid}, {"_id": 1})
        if not existing:
            raise NotFoundError(
                message=f"Camera with ID '{clean_id}' does not exist in the registered camera database.",
                entity="Camera",
                entity_id=clean_id,
            )
        return cam_oid

    # Optional camera fallback: find any active camera in DB
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
    cooldown_seconds: int = Form(15, description="Cooldown window in seconds for deduplicating repeated violations on this camera"),
    plate_hint: Optional[str] = Form(None, description="Optional manual or upstream OCR plate text hint"),
    current_user: dict = Depends(require_authenticated_staff),
):
    """
    Analyzes an uploaded surveillance or webcam image using the configured AI engine.

    Workflow:
    1. Validates image MIME type, file extension, and maximum byte size.
    2. Validates image data integrity by decoding into OpenCV pixel buffer.
    3. Sanitizes optional request parameters (camera_id, plate_hint, source_label).
    4. Runs AI inference (checks model availability and supported classes; no mock fallbacks).
    5. Persists the captured frame to local storage with cryptographic SHA-256 hash.
    6. Extracts distinct riders, generates stable detection IDs, classifications, and evidence crops.
    7. Extracts number plate if present, runs OCR, and matches against registered vehicles/owners.
    8. If a candidate violation is detected and auto_ingest is true, registers a case
       in the violations collection with status PENDING_REVIEW (never auto-issuing sanctions).
    9. Records execution telemetry and stage timing breakdown to the model_runs collection.
    """
    total_start_time = time.perf_counter()

    # 1. Sanitize optional text parameters to eliminate Swagger/client placeholder pollution
    clean_camera_id = sanitize_placeholder(camera_id)
    clean_plate_hint = sanitize_placeholder(plate_hint)
    clean_source_label = sanitize_placeholder(source_label) or "Operator Live Station"

    # 2. Validate MIME type & file extension
    content_type = (file.content_type or "").lower().strip()
    original_filename = file.filename or "frame.jpg"
    ext = os.path.splitext(original_filename)[1].lower()

    if content_type not in ALLOWED_MIME_TYPES and ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            message=f"Unsupported file type '{content_type or ext}'. Only JPEG, PNG, and WEBP images are supported."
        )

    # 3. Read bytes and enforce size limits
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

    # 4. Validate image decodability
    nparr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None or image.shape[0] == 0 or image.shape[1] == 0:
        raise ValidationError(
            message="Uploaded file could not be parsed as a valid image (corrupt or unreadable file data)."
        )

    height, width = image.shape[:2]

    # 5. Early request validation: resolve and validate camera attribution before AI inference
    db = get_db()
    camera_oid = _resolve_camera_oid(db, clean_camera_id)

    # 6. Execute AI inference via configured engine (Roboflow or local YOLO) with stage timing
    t_inf_start = time.perf_counter()
    provider = (settings.INFERENCE_PROVIDER or "roboflow").lower()
    if provider == "roboflow":
        det_result = await roboflow_engine.detect(image)
        model_name = f"Roboflow:{settings.ROBOFLOW_MODEL_ID.split('/')[0]}"
        model_version = settings.ROBOFLOW_MODEL_ID.split('/')[-1] if '/' in settings.ROBOFLOW_MODEL_ID else "6"
        active_model_info = roboflow_engine.get_model_info()
    else:
        det_result = yolo_engine.detect(image)
        model_name = "YOLOv8n-Traffic"
        model_version = "8.1.0"
        active_model_info = yolo_engine.get_model_info()
    model_inference_ms = round((time.perf_counter() - t_inf_start) * 1000, 2)

    # 6. Persist full evidence frame to disk
    t_ev_start = time.perf_counter()
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

    # 7. Extract distinct riders, stable IDs, classifications, and safe crops
    riders_response: List[RiderDetectionModel] = []
    rider_box_candidates = [
        b for b in det_result["boxes"]
        if b.get("category") in ("HELMET_VIOLATION", "HELMET_COMPLIANT", "PERSON")
        or str(b.get("label", "")).lower() in ("without helmet", "with helmet", "no_helmet", "helmet", "rider", "person")
    ]

    for idx, rb in enumerate(rider_box_candidates):
        stable_id = f"rider-{idx + 1}-{file_hash[:8]}"
        label_raw = str(rb.get("label", ""))
        category = rb.get("category", "")
        
        # Determine classification
        if category == "HELMET_VIOLATION" or label_raw.lower() in ("without helmet", "no_helmet", "no-helmet"):
            classification = "WITHOUT_HELMET"
            is_viol = True
        elif category == "HELMET_COMPLIANT" or label_raw.lower() in ("with helmet", "helmet", "with-helmet"):
            classification = "WITH_HELMET"
            is_viol = False
        else:
            classification = "UNKNOWN"
            is_viol = False

        # Safe pixel crop bounded within image dimensions (matches displayed coordinates)
        coords = rb.get("xyxy", [0, 0, 0, 0])
        rx1 = max(0, min(width - 1, int(round(coords[0]))))
        ry1 = max(0, min(height - 1, int(round(coords[1]))))
        rx2 = max(rx1 + 1, min(width, int(round(coords[2]))))
        ry2 = max(ry1 + 1, min(height, int(round(coords[3]))))

        rider_crop_path = None
        if (rx2 - rx1) > 2 and (ry2 - ry1) > 2:
            rider_crop_img = image[ry1:ry2, rx1:rx2]
            rider_crop_name = f"crop_rider_{file_hash[:8]}_{idx + 1}_{int(time.time())}.jpg"
            rider_crop_disk = os.path.join(EVIDENCE_UPLOAD_DIR, rider_crop_name)
            try:
                cv2.imwrite(rider_crop_disk, rider_crop_img)
                rider_crop_path = f"/uploads/evidence/{rider_crop_name}"
            except Exception as exc:
                logger.warning(f"Failed to save rider crop image: {exc}")

        # Consistent normalized format [x1, y1, x2, y2]
        x1_norm = round(rx1 / width, 4)
        y1_norm = round(ry1 / height, 4)
        x2_norm = round(rx2 / width, 4)
        y2_norm = round(ry2 / height, 4)

        riders_response.append(
            RiderDetectionModel(
                detectionId=stable_id,
                label=label_raw,
                classification=classification,
                confidence=rb.get("confidence", 0.0),
                bbox=[float(rx1), float(ry1), float(rx2), float(ry2)],
                normalized=[x1_norm, y1_norm, x2_norm, y2_norm],
                cropPath=rider_crop_path,
                isViolation=is_viol,
            )
        )

    # 8. Extract license plate & match against registry
    plate_boxes = [
        b for b in det_result["boxes"]
        if b.get("category") == "LICENSE_PLATE"
        or str(b.get("label", "")).lower() in ("licence", "license", "plate", "license_plate")
    ]

    plate_crop_path = None
    extracted_plate_text = None
    ocr_confidence = 0.0
    plate_box_coords = None

    if plate_boxes:
        pb = plate_boxes[0]
        p_coords = pb.get("xyxy", [0, 0, 0, 0])
        px1 = max(0, min(width - 1, int(round(p_coords[0]))))
        py1 = max(0, min(height - 1, int(round(p_coords[1]))))
        px2 = max(px1 + 1, min(width, int(round(p_coords[2]))))
        py2 = max(py1 + 1, min(height, int(round(p_coords[3]))))

        plate_crop = None
        if (px2 - px1) > 2 and (py2 - py1) > 2:
            plate_crop = image[py1:py2, px1:px2]
            plate_crop_name = f"crop_plate_{file_hash[:8]}_{int(time.time())}.jpg"
            plate_crop_disk = os.path.join(EVIDENCE_UPLOAD_DIR, plate_crop_name)
            try:
                cv2.imwrite(plate_crop_disk, plate_crop)
                plate_crop_path = f"/uploads/evidence/{plate_crop_name}"
            except Exception as exc:
                logger.warning(f"Failed to save plate crop: {exc}")

        t_ocr_start = time.perf_counter()
        extracted_plate_text, ocr_confidence = extract_plate_text_from_crop(
            plate_crop, ocr_override=clean_plate_hint
        )
        ocr_ms = round((time.perf_counter() - t_ocr_start) * 1000, 2)
        plate_box_coords = [float(px1), float(py1), float(px2), float(py2)]
    elif clean_plate_hint:
        t_ocr_start = time.perf_counter()
        extracted_plate_text, ocr_confidence = extract_plate_text_from_crop(
            None, ocr_override=clean_plate_hint
        )
        ocr_ms = round((time.perf_counter() - t_ocr_start) * 1000, 2)
        plate_box_coords = None
    else:
        ocr_ms = 0.0
        plate_box_coords = None

    evidence_saving_ms = round((time.perf_counter() - t_ev_start - (ocr_ms / 1000.0 if ocr_ms else 0.0)) * 1000, 2)

    now = datetime.now(timezone.utc)
    model_run_id: Optional[str] = None
    case_id: Optional[str] = None
    is_deduplicated = False
    cooldown_remaining: Optional[int] = None
    plate_match_res: Optional[PlateMatchResult] = None

    # 9. MongoDB persistence and violation deduplication
    t_db_start = time.perf_counter()
    try:
        # Match plate in database
        if extracted_plate_text:
            match_data = match_plate_against_registry(db, extracted_plate_text, ocr_confidence)
            plate_match_res = PlateMatchResult(
                plateDetected=True,
                rawText=match_data.get("rawText"),
                normalizedPlate=match_data.get("normalizedPlate"),
                bbox=plate_box_coords,
                cropPath=plate_crop_path,
                matchStatus=match_data.get("matchStatus", "MANUAL_REQUIRED"),
                matchSource=match_data.get("matchSource"),
                confidence=match_data.get("confidence"),
                matchedVehicleId=match_data.get("matchedVehicleId"),
                matchedPersonId=match_data.get("matchedPersonId"),
                ownerNameSnapshot=match_data.get("ownerNameSnapshot"),
                vehicleDetails=match_data.get("vehicleDetails"),
            )
        else:
            plate_match_res = PlateMatchResult(
                plateDetected=len(plate_boxes) > 0,
                rawText=None,
                normalizedPlate=None,
                bbox=plate_box_coords,
                cropPath=plate_crop_path,
                matchStatus="MANUAL_REQUIRED",
                matchSource=None,
                confidence=0.0,
                matchedVehicleId=None,
                matchedPersonId=None,
                ownerNameSnapshot=None,
                vehicleDetails=None,
            )

        # If candidate violation detected and auto_ingest enabled, check cooldown before creating draft
        if det_result["isCandidateViolation"] and auto_ingest and det_result["violationType"]:
            if cooldown_seconds > 0:
                cooldown_cutoff = now - timedelta(seconds=cooldown_seconds)
                recent_violation = db[COLLECTION_VIOLATIONS].find_one(
                    {
                        "cameraId": camera_oid,
                        "createdAt": {"$gte": cooldown_cutoff},
                        "status": "PENDING_REVIEW",
                    },
                    sort=[("createdAt", -1)],
                )
                if recent_violation:
                    is_deduplicated = True
                    case_id = recent_violation.get("caseId")
                    created_at = recent_violation.get("createdAt")
                    if created_at:
                        if created_at.tzinfo is None:
                            created_at = created_at.replace(tzinfo=timezone.utc)
                        elapsed = (now - created_at).total_seconds()
                        cooldown_remaining = max(0, int(cooldown_seconds - elapsed))

            if not is_deduplicated:
                case_id = f"TG-2026-{abs(hash(str(camera_oid) + str(now.timestamp()))) % 100000:05d}"
                
                # Map bounding boxes to schema requirements with consistent normalized coordinates [x1, y1, x2, y2]
                schema_boxes = [
                    {
                        "className": b["label"],
                        "confidence": b["confidence"],
                        "coordinates": {
                            "x1": b["normalized"][0],
                            "y1": b["normalized"][1],
                            "x2": b["normalized"][2],
                            "y2": b["normalized"][3],
                            "xmin": b["normalized"][0],
                            "ymin": b["normalized"][1],
                            "xmax": b["normalized"][2],
                            "ymax": b["normalized"][3],
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

                # Link matched vehicle and registered owner (strictly registered owner, never assumed rider)
                person_oid = None
                if plate_match_res and plate_match_res.matchedPersonId and ObjectId.is_valid(plate_match_res.matchedPersonId):
                    person_oid = ObjectId(plate_match_res.matchedPersonId)

                vehicle_oid = None
                if plate_match_res and plate_match_res.matchedVehicleId and ObjectId.is_valid(plate_match_res.matchedVehicleId):
                    vehicle_oid = ObjectId(plate_match_res.matchedVehicleId)

                verification_status = plate_match_res.matchStatus if plate_match_res else "UNVERIFIED"

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
                    "identityVerificationStatus": verification_status,
                    "personId": person_oid,
                    "vehicleId": vehicle_oid,
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
                        "sourceLabel": clean_source_label,
                        "cameraId": str(camera_oid),
                        "modelRunId": None,
                        "identityVerificationStatus": verification_status,
                        "matchedVehicleId": str(vehicle_oid) if vehicle_oid else None,
                        "matchedPersonId": str(person_oid) if person_oid else None,
                    },
                    "requestId": None,
                }
                try:
                    db[COLLECTION_AUDIT_LOGS].insert_one(audit_entry)
                except Exception:
                    pass

        # Compute preliminary total processing time before model_runs insert
        db_lookup_ms = round((time.perf_counter() - t_db_start) * 1000, 2)
        total_processing_ms = round((time.perf_counter() - total_start_time) * 1000, 2)

        timing_breakdown = {
            "modelInferenceMs": model_inference_ms,
            "evidenceSavingMs": evidence_saving_ms,
            "ocrMs": ocr_ms,
            "dbLookupMs": db_lookup_ms,
            "totalProcessingMs": total_processing_ms,
        }

        # Log to model_runs collection
        model_run_doc = {
            "cameraId": camera_oid,
            "modelName": model_name,
            "modelVersion": model_version,
            "processedAt": now,
            "processingTimeMs": total_processing_ms,
            "timingBreakdown": timing_breakdown,
            "resultSummary": {
                "totalDetections": det_result["totalDetections"],
                "vehiclesCount": len(det_result["vehicles"]),
                "personsCount": len(det_result["persons"]),
                "ridersCount": len(riders_response),
                "isCandidateViolation": det_result["isCandidateViolation"],
                "violationType": det_result["violationType"],
                "isDeduplicated": is_deduplicated,
                "cooldownRemaining": cooldown_remaining,
                "plateMatchStatus": plate_match_res.matchStatus if plate_match_res else "MANUAL_REQUIRED",
            },
            "status": "SUCCESS",
            "errorMessage": None,
        }
        run_res = db[COLLECTION_MODEL_RUNS].insert_one(model_run_doc)
        model_run_id = str(run_res.inserted_id)

    except (ValidationError, NotFoundError):
        raise
    except Exception as exc:
        logger.error(f"Database error during detection logging: {exc}")
        db_lookup_ms = round((time.perf_counter() - t_db_start) * 1000, 2)
        total_processing_ms = round((time.perf_counter() - total_start_time) * 1000, 2)
        timing_breakdown = {
            "modelInferenceMs": model_inference_ms,
            "evidenceSavingMs": evidence_saving_ms,
            "ocrMs": ocr_ms,
            "dbLookupMs": db_lookup_ms,
            "totalProcessingMs": total_processing_ms,
        }
        if not plate_match_res:
            plate_match_res = PlateMatchResult(
                plateDetected=len(plate_boxes) > 0,
                rawText=extracted_plate_text,
                normalizedPlate=None,
                bbox=plate_box_coords,
                cropPath=plate_crop_path,
                matchStatus="MANUAL_REQUIRED",
                matchSource=None,
                confidence=0.0,
                matchedVehicleId=None,
                matchedPersonId=None,
                ownerNameSnapshot=None,
                vehicleDetails=None,
            )

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

    # Explicit separation: vehicles list strictly contains VEHICLE objects, never LICENSE_PLATE
    vehicles_response = [b for b in boxes_response if b.category == "VEHICLE"]
    persons_response = [b for b in boxes_response if b.category == "PERSON"]

    total_processing_ms = round((time.perf_counter() - total_start_time) * 1000, 2)
    timing_breakdown["totalProcessingMs"] = total_processing_ms

    response_data = DetectionAnalysisResponse(
        detected=det_result["detected"],
        totalDetections=det_result["totalDetections"],
        boxes=boxes_response,
        vehicles=vehicles_response,
        persons=persons_response,
        riders=riders_response,
        plateMatch=plate_match_res,
        helmetClassificationAvailable=det_result["helmetClassificationAvailable"],
        helmetClassificationMessage=det_result["helmetClassificationMessage"],
        isCandidateViolation=det_result["isCandidateViolation"],
        violationType=det_result["violationType"],
        violationConfidence=det_result["violationConfidence"],
        caseId=case_id,
        status="PENDING_REVIEW" if det_result["isCandidateViolation"] else "NO_VIOLATION",
        evidence=evidence_model,
        modelRunId=model_run_id,
        processingTimeMs=total_processing_ms,
        timingBreakdown=timing_breakdown,
        imageDimensions={"width": width, "height": height},
        modelInfo=active_model_info,
        isDeduplicated=is_deduplicated,
        cooldownSecondsRemaining=cooldown_remaining,
    )

    return ApiResponse(
        success=True,
        data=response_data,
        message=(
            f"Frame analyzed successfully in {total_processing_ms}ms "
            f"(inference: {model_inference_ms}ms). "
            f"Found {det_result['totalDetections']} object(s), {len(riders_response)} rider(s)."
        ),
    )


@router.get(
    "/model-status",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get active AI model status and supported classes",
)
async def get_model_status():
    """
    Returns live information about the active AI model (Roboflow or local YOLO),
    configuration verification, and whether helmet violation classes are supported.
    """
    provider = (settings.INFERENCE_PROVIDER or "roboflow").lower()
    info = roboflow_engine.get_model_info() if provider == "roboflow" else yolo_engine.get_model_info()
    return ApiResponse(
        success=True,
        data=info,
        message=f"Active AI model status retrieved ({info.get('provider', 'local')}).",
    )
