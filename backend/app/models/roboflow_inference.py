"""
Roboflow Hosted Helmet Detection Inference Service.

Integrates Roboflow hosted model:
- Model ID: helmet-and-no-helmet-rider-detection/6
- Classes: "With Helmet", "Without Helmet", "licence"
- Strict candidate violation routing for "Without Helmet" (PENDING_REVIEW)
- Safe handling of timeouts, auth errors, and missing keys without exposing secrets
"""

import base64
import logging
from typing import Dict, Any, List, Optional, Union, Tuple
import numpy as np
import httpx

from app.config import settings
from app.core.exceptions import ModelNotAvailableError, RemoteInferenceError
from app.schemas.common import ErrorDetail

logger = logging.getLogger("trafficguard.roboflow")

# Exact class names defined by Roboflow model helmet-and-no-helmet-rider-detection/6
ROBOFLOW_CLASS_WITH_HELMET = "With Helmet"
ROBOFLOW_CLASS_WITHOUT_HELMET = "Without Helmet"
ROBOFLOW_CLASS_LICENCE = "licence"

EXPECTED_ROBOFLOW_CLASSES = [
    ROBOFLOW_CLASS_WITH_HELMET,
    ROBOFLOW_CLASS_WITHOUT_HELMET,
    ROBOFLOW_CLASS_LICENCE,
]


_UNSET = object()


class RoboflowInferenceEngine:
    """
    Roboflow Hosted Detection Engine for TrafficGuard AI.
    Executes inference against https://detect.roboflow.com/helmet-and-no-helmet-rider-detection/6
    """

    def __init__(
        self,
        api_key: Any = _UNSET,
        model_id: Optional[str] = None,
        base_url: Optional[str] = None,
        confidence_threshold: Optional[float] = None,
    ) -> None:
        self.api_key = settings.ROBOFLOW_API_KEY if api_key is _UNSET else api_key
        self.model_id = model_id or settings.ROBOFLOW_MODEL_ID
        self.base_url = (base_url or settings.ROBOFLOW_BASE_URL).rstrip("/")
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else settings.INFERENCE_CONFIDENCE_THRESHOLD
        )
        self.supported_classes: Dict[int, str] = {
            0: ROBOFLOW_CLASS_WITH_HELMET,
            1: ROBOFLOW_CLASS_WITHOUT_HELMET,
            2: ROBOFLOW_CLASS_LICENCE,
        }
        self.helmet_classification_supported: bool = True

    def is_configured(self) -> bool:
        """Returns True if a non-empty API key is configured."""
        return bool(self.api_key and self.api_key.strip() and self.api_key != "your_roboflow_api_key_here")

    def get_model_info(self) -> Dict[str, Any]:
        """Returns structured metadata about model state, provider, and supported classes."""
        configured = self.is_configured()
        return {
            "provider": "roboflow",
            "isLoaded": configured,
            "modelId": self.model_id,
            "classesCount": len(self.supported_classes),
            "classes": self.supported_classes,
            "helmetClassificationSupported": True,
            "confidenceThreshold": self.confidence_threshold,
            "loadError": None if configured else "ROBOFLOW_API_KEY is missing or invalid in backend/.env",
            "expectedClasses": EXPECTED_ROBOFLOW_CLASSES,
        }

    def _classify_roboflow_label(self, raw_class_name: str) -> Tuple[str, str, bool]:
        """
        Maps Roboflow class name to (category, hex_color, is_violation).
        Exact mappings:
        - "Without Helmet" -> (HELMET_VIOLATION, #DC2626, True)
        - "With Helmet"    -> (HELMET_COMPLIANT, #15803D, False)
        - "licence"        -> (LICENSE_PLATE, #D97706, False)
        """
        norm = raw_class_name.strip()
        if norm.lower() == ROBOFLOW_CLASS_WITHOUT_HELMET.lower():
            return "HELMET_VIOLATION", "#DC2626", True
        elif norm.lower() == ROBOFLOW_CLASS_WITH_HELMET.lower():
            return "HELMET_COMPLIANT", "#15803D", False
        elif norm.lower() in [ROBOFLOW_CLASS_LICENCE.lower(), "license", "plate"]:
            return "LICENSE_PLATE", "#D97706", False
        else:
            return "OTHER", "#64748B", False

    def _prepare_image_payload(
        self, image_input: Union[np.ndarray, bytes]
    ) -> Tuple[str, int, int]:
        """Encodes image bytes to base64 string and extracts (width, height)."""
        import cv2

        if isinstance(image_input, bytes):
            image_bytes = image_input
            nparr = np.frombuffer(image_input, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None or img.size == 0:
                raise ValueError("Could not decode image bytes into valid pixel matrix.")
            height, width = img.shape[:2]
        elif isinstance(image_input, np.ndarray):
            if image_input.size == 0:
                raise ValueError("Invalid image matrix provided for inference.")
            height, width = image_input.shape[:2]
            success, encoded_buf = cv2.imencode(".jpg", image_input)
            if not success:
                raise ValueError("Failed to encode image array to JPEG format.")
            image_bytes = encoded_buf.tobytes()
        else:
            raise ValueError(f"Unsupported image input type: {type(image_input)}")

        if height <= 0 or width <= 0:
            raise ValueError(f"Invalid image dimensions: {width}x{height}")

        base64_str = base64.b64encode(image_bytes).decode("ascii")
        return base64_str, width, height

    def _parse_roboflow_response(
        self,
        data: Dict[str, Any],
        width: int,
        height: int,
    ) -> Dict[str, Any]:
        """
        Parses Roboflow prediction dictionary into the project's detection schema.
        Converts center coordinates (x, y, width, height) into corner [xyxy],
        normalized [ymin, xmin, ymax, xmax], and percentage coords.
        """
        predictions = data.get("predictions")
        if not isinstance(predictions, list):
            raise RemoteInferenceError(
                message="Roboflow inference API response missing 'predictions' list.",
                status_code=502,
                error_code="ROBOFLOW_INVALID_RESPONSE",
            )

        boxes: List[Dict[str, Any]] = []
        vehicles: List[Dict[str, Any]] = []
        persons: List[Dict[str, Any]] = []
        violation_boxes: List[Dict[str, Any]] = []
        compliant_boxes: List[Dict[str, Any]] = []

        box_counter = 1
        for pred in predictions:
            if not isinstance(pred, dict):
                continue

            raw_label = str(pred.get("class", "Unknown"))
            confidence = float(pred.get("confidence", 0.0))
            class_id = int(pred.get("class_id", -1)) if pred.get("class_id") is not None else box_counter

            category, color, is_violation = self._classify_roboflow_label(raw_label)

            # Roboflow center coordinates
            cx = float(pred.get("x", 0.0))
            cy = float(pred.get("y", 0.0))
            bw = float(pred.get("width", 0.0))
            bh = float(pred.get("height", 0.0))

            x1 = max(0.0, min(float(width), cx - (bw / 2.0)))
            y1 = max(0.0, min(float(height), cy - (bh / 2.0)))
            x2 = max(0.0, min(float(width), cx + (bw / 2.0)))
            y2 = max(0.0, min(float(height), cy + (bh / 2.0)))

            ymin_n = round(y1 / height, 4)
            xmin_n = round(x1 / width, 4)
            ymax_n = round(y2 / height, 4)
            xmax_n = round(x2 / width, 4)

            pct_x = round((x1 / width) * 100, 2)
            pct_y = round((y1 / height) * 100, 2)
            pct_w = round(max(0.0, (x2 - x1) / width) * 100, 2)
            pct_h = round(max(0.0, (y2 - y1) / height) * 100, 2)

            # Keep formatted uppercase label for UI consistency
            display_label = raw_label.upper().replace(" ", "_")

            box_obj = {
                "id": f"det-rf-{box_counter}",
                "label": display_label,
                "classId": class_id,
                "category": category,
                "confidence": round(confidence, 4),
                "xyxy": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                "normalized": [ymin_n, xmin_n, ymax_n, xmax_n],
                "coordinates": {
                    "ymin": ymin_n,
                    "xmin": xmin_n,
                    "ymax": ymax_n,
                    "xmax": xmax_n,
                },
                "percentage": {
                    "x": pct_x,
                    "y": pct_y,
                    "width": pct_w,
                    "height": pct_h,
                },
                "color": color,
            }
            box_counter += 1
            boxes.append(box_obj)

            if category == "HELMET_VIOLATION":
                violation_boxes.append(box_obj)
            elif category == "HELMET_COMPLIANT":
                compliant_boxes.append(box_obj)
            elif category == "LICENSE_PLATE":
                vehicles.append(box_obj)
            elif category == "VEHICLE":
                vehicles.append(box_obj)
            elif category == "PERSON":
                persons.append(box_obj)

        is_candidate_violation = False
        violation_type: Optional[str] = None
        violation_confidence: Optional[float] = None

        if violation_boxes:
            is_candidate_violation = True
            violation_confidence = max(b["confidence"] for b in violation_boxes)
            violation_type = "NO_HELMET_RIDER"
            helmet_message = (
                f"Candidate violation detected via Roboflow: {violation_type} "
                f"({len(violation_boxes)} unhelmeted rider/head region(s) detected)."
            )
        elif compliant_boxes:
            helmet_message = (
                f"Compliant: {len(compliant_boxes)} helmet(s) identified on rider(s) via Roboflow."
            )
        elif boxes:
            helmet_message = f"Detected {len(boxes)} traffic object(s) via Roboflow."
        else:
            helmet_message = "No riders or helmet objects detected in frame."

        return {
            "detected": len(boxes) > 0,
            "totalDetections": len(boxes),
            "boxes": boxes,
            "vehicles": vehicles,
            "persons": persons,
            "helmetClassificationAvailable": True,
            "helmetClassificationMessage": helmet_message,
            "isCandidateViolation": is_candidate_violation,
            "violationType": violation_type,
            "violationConfidence": violation_confidence,
            "imageDimensions": {"width": width, "height": height},
        }

    async def detect(
        self,
        image_input: Union[np.ndarray, bytes],
        confidence_threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Executes asynchronous remote inference against Roboflow API.

        Raises:
            ModelNotAvailableError: If ROBOFLOW_API_KEY is missing/unconfigured.
            RemoteInferenceError: On remote upstream errors, timeouts, or auth failures.
            ValueError: If input image is malformed.
        """
        if not self.is_configured():
            raise ModelNotAvailableError(
                message=(
                    "Roboflow API key is not configured. "
                    "Please set ROBOFLOW_API_KEY in backend/.env to enable hosted helmet detection."
                ),
                expected_classes=EXPECTED_ROBOFLOW_CLASSES,
            )

        conf = (
            confidence_threshold
            if confidence_threshold is not None
            else self.confidence_threshold
        )

        base64_payload, width, height = self._prepare_image_payload(image_input)

        url = f"{self.base_url}/{self.model_id}"
        # Roboflow expects confidence percentage (0-100) or float depending on endpoint
        params = {
            "api_key": self.api_key,
            "confidence": int(conf * 100),
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    url,
                    params=params,
                    content=base64_payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
        except httpx.TimeoutException:
            logger.error("Roboflow inference request timed out after 15 seconds.")
            raise RemoteInferenceError(
                message="Roboflow hosted inference API timed out after 15 seconds.",
                status_code=504,
                error_code="ROBOFLOW_TIMEOUT",
            )
        except httpx.RequestError as exc:
            logger.error(f"Roboflow network connectivity error: {exc}")
            raise RemoteInferenceError(
                message="Failed to connect to Roboflow hosted inference service. Please check network connection.",
                status_code=502,
                error_code="ROBOFLOW_NETWORK_ERROR",
            )

        # Handle HTTP error statuses safely without leaking the API key
        if response.status_code in (401, 403):
            logger.error(f"Roboflow authentication failed (HTTP {response.status_code}).")
            raise RemoteInferenceError(
                message="Roboflow authentication failed. Please verify your ROBOFLOW_API_KEY in backend/.env.",
                status_code=502,
                error_code="ROBOFLOW_AUTH_ERROR",
            )
        elif response.status_code == 404:
            logger.error(f"Roboflow model not found: {self.model_id}")
            raise RemoteInferenceError(
                message=f"Roboflow model '{self.model_id}' was not found.",
                status_code=502,
                error_code="ROBOFLOW_MODEL_NOT_FOUND",
            )
        elif response.status_code == 429:
            logger.warning("Roboflow rate limit reached.")
            raise RemoteInferenceError(
                message="Roboflow inference rate limit exceeded. Please retry shortly.",
                status_code=429,
                error_code="ROBOFLOW_RATE_LIMIT",
            )
        elif response.status_code >= 400:
            logger.error(f"Roboflow upstream error: HTTP {response.status_code}")
            raise RemoteInferenceError(
                message=f"Roboflow inference API returned error (HTTP {response.status_code}).",
                status_code=502,
                error_code="ROBOFLOW_UPSTREAM_ERROR",
            )

        try:
            json_data = response.json()
        except Exception as exc:
            logger.error(f"Failed to parse Roboflow response as JSON: {exc}")
            raise RemoteInferenceError(
                message="Invalid or non-JSON response received from Roboflow inference API.",
                status_code=502,
                error_code="ROBOFLOW_INVALID_RESPONSE",
            )

        return self._parse_roboflow_response(json_data, width, height)


# Singleton Roboflow inference instance
roboflow_engine = RoboflowInferenceEngine()
