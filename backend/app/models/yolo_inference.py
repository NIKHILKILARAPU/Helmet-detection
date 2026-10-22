"""
YOLOv8/YOLOv11 Traffic & Helmet Inference Service.

Provides:
- One-time model loading and path validation
- Strict inspection of supported model classes (preventing standard COCO false-claims)
- Explicit CPU inference handling
- Structured bounding boxes, normalized/percentage coordinates, and categories
- Separation of vehicle/person detection from helmet/no-helmet classification
- Actionable MODEL_NOT_AVAILABLE error when weights are missing
"""

import os
import logging
from typing import Dict, Any, List, Optional, Union, Tuple
import numpy as np

from app.config import settings, resolve_model_path, MODELS_DIR, DEFAULT_YOLO_MODEL_PATH
from app.core.exceptions import ModelNotAvailableError

logger = logging.getLogger("trafficguard.yolo")

# Validated class keywords
HELMET_VIOLATION_KEYWORDS = {
    "no_helmet",
    "no-helmet",
    "without_helmet",
    "without-helmet",
    "no_helmet_rider",
    "no_helmet_pillion",
    "bare_head",
    "head",
}

HELMET_COMPLIANT_KEYWORDS = {
    "helmet",
    "with_helmet",
    "with-helmet",
    "helmet_on",
    "helmet_rider",
    "helmet_pillion",
}

PERSON_KEYWORDS = {
    "person",
    "rider",
    "driver",
    "pillion",
}

VEHICLE_KEYWORDS = {
    "motorcycle",
    "motorbike",
    "motor_bike",
    "scooter",
    "bike",
    "bicycle",
    "car",
    "bus",
    "truck",
    "auto",
    "auto_rickshaw",
}

EXPECTED_TRAFFIC_CLASSES = [
    "helmet",
    "no_helmet",
    "motorcycle",
    "rider",
    "person",
]


class YoloInferenceEngine:
    """
    Production-grade YOLO inference engine for TrafficGuard AI.
    Loads model weights once, caches model class taxonomy, and executes CPU inference safely.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: Optional[float] = None,
    ) -> None:
        self.model_path = model_path or settings.YOLO_MODEL_PATH
        self.resolved_model_path = resolve_model_path(self.model_path)
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else settings.INFERENCE_CONFIDENCE_THRESHOLD
        )
        self.model = None
        self._load_error: Optional[str] = None
        self.supported_classes: Dict[int, str] = {}
        self.helmet_classification_supported: bool = False
        self._load_model()

    def _load_model(self) -> None:
        """Attempts to load weights once if present on disk."""
        target_path = self.resolved_model_path
        if not target_path or not os.path.isfile(target_path):
            self.model = None
            self._load_error = (
                f"Model weights file not found at '{target_path}'. "
                f"Please ensure trained traffic/helmet detection weights (*.pt) are placed in the models directory."
            )
            self.supported_classes = {}
            self.helmet_classification_supported = False
            logger.warning(self._load_error)
            return

        if os.path.getsize(target_path) == 0:
            self.model = None
            self._load_error = (
                f"Model weights file at '{target_path}' is empty (0 bytes). "
                f"Please ensure valid trained traffic/helmet detection weights (*.pt) are placed in the models directory."
            )
            self.supported_classes = {}
            self.helmet_classification_supported = False
            logger.error(self._load_error)
            return

        try:
            from ultralytics import YOLO

            logger.info(f"Loading YOLO weights from: {target_path}")
            loaded = YOLO(target_path)
            self.model = loaded
            self._load_error = None
            self._inspect_model_classes()
            logger.info(
                f"Successfully loaded YOLO model with {len(self.supported_classes)} classes. "
                f"Helmet classification supported: {self.helmet_classification_supported}"
            )
        except Exception as exc:
            self.model = None
            self._load_error = f"Failed to initialize YOLO model from '{target_path}': {str(exc)}"
            self.supported_classes = {}
            self.helmet_classification_supported = False
            logger.error(self._load_error)

    def reload(self, model_path: Optional[str] = None) -> bool:
        """Reloads model weights from disk (supports dynamically changing or reloading weights)."""
        if model_path is not None:
            self.model_path = model_path
            self.resolved_model_path = resolve_model_path(model_path)
        else:
            self.resolved_model_path = resolve_model_path(self.model_path)
        self._load_model()
        return self.is_model_loaded()

    def _inspect_model_classes(self) -> None:
        """Analyzes class taxonomy of the loaded model."""
        if self.model is None:
            self.supported_classes = {}
            self.helmet_classification_supported = False
            return

        raw_names = getattr(self.model, "names", {})
        if isinstance(raw_names, dict):
            self.supported_classes = {int(k): str(v) for k, v in raw_names.items()}
        elif isinstance(raw_names, (list, tuple)):
            self.supported_classes = {i: str(name) for i, name in enumerate(raw_names)}
        else:
            self.supported_classes = {}

        # Validate helmet violation capability
        normalized_names = [name.lower().strip().replace(" ", "_") for name in self.supported_classes.values()]
        has_helmet_class = any(
            any(hw in name for hw in ["helmet", "head"]) for name in normalized_names
        )
        self.helmet_classification_supported = has_helmet_class

    def is_model_loaded(self) -> bool:
        """Returns True if model weights are successfully loaded in memory."""
        return self.model is not None

    def get_model_info(self) -> Dict[str, Any]:
        """Returns structured metadata about model state, path, and supported classes."""
        target_path = self.resolved_model_path
        file_exists = bool(target_path and os.path.isfile(target_path))
        file_size = os.path.getsize(target_path) if file_exists else None
        class_names = [self.supported_classes[k] for k in sorted(self.supported_classes.keys())]
        return {
            "provider": "local",
            "isLoaded": self.is_model_loaded(),
            "modelPath": self.model_path,
            "resolvedPath": target_path,
            "fileExists": file_exists,
            "fileSizeBytes": file_size,
            "classesCount": len(self.supported_classes),
            "classes": self.supported_classes,
            "classNames": class_names,
            "helmetClassificationSupported": self.helmet_classification_supported,
            "confidenceThreshold": self.confidence_threshold,
            "loadError": self._load_error,
            "errorMessage": self._load_error,
            "expectedClasses": EXPECTED_TRAFFIC_CLASSES,
            "legitimateSource": (
                "TrafficGuard fine-tuned traffic safety weights (*.pt) containing classes: "
                f"{', '.join(EXPECTED_TRAFFIC_CLASSES)}"
            ),
            "destinationPath": target_path,
        }

    def set_model(self, model_instance: Any, supported_classes: Optional[Dict[int, str]] = None) -> None:
        """Injects or mocks model instance (used for testing without downloading real weights)."""
        self.model = model_instance
        self._load_error = None
        if supported_classes is not None:
            self.supported_classes = supported_classes
        else:
            raw_names = getattr(model_instance, "names", {})
            if isinstance(raw_names, dict):
                self.supported_classes = {int(k): str(v) for k, v in raw_names.items()}
            elif isinstance(raw_names, (list, tuple)):
                self.supported_classes = {i: str(name) for i, name in enumerate(raw_names)}
            else:
                self.supported_classes = {}

        normalized_names = [name.lower().strip().replace(" ", "_") for name in self.supported_classes.values()]
        self.helmet_classification_supported = any(
            any(hw in name for hw in ["helmet", "head"]) for name in normalized_names
        )

    def _classify_label(self, label: str) -> Tuple[str, str]:
        """
        Maps a class label string into (category, hex_color).
        Categories: HELMET_VIOLATION, HELMET_COMPLIANT, PERSON, VEHICLE, OTHER
        """
        lbl = label.lower().strip().replace(" ", "_")

        for kw in HELMET_VIOLATION_KEYWORDS:
            if kw in lbl:
                return "HELMET_VIOLATION", "#DC2626"  # Red

        for kw in HELMET_COMPLIANT_KEYWORDS:
            if kw in lbl:
                return "HELMET_COMPLIANT", "#15803D"  # Green

        for kw in PERSON_KEYWORDS:
            if kw in lbl:
                return "PERSON", "#2563EB"  # Blue

        for kw in VEHICLE_KEYWORDS:
            if kw in lbl:
                return "VEHICLE", "#D97706"  # Amber

        return "OTHER", "#64748B"  # Slate

    def detect(
        self,
        image_input: Union[np.ndarray, bytes],
        confidence_threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Executes CPU YOLO inference on the input image.

        Raises:
            ModelNotAvailableError: If model weights are missing or uninitialized.
            ValueError: If input image is malformed.

        Returns:
            Structured detection dictionary with:
            - detected (bool)
            - totalDetections (int)
            - boxes (List of structured boxes with pixels, normalized, percentage coords)
            - vehicles (List of vehicle boxes)
            - persons (List of person boxes)
            - helmetClassificationAvailable (bool)
            - helmetClassificationMessage (str)
            - isCandidateViolation (bool)
            - violationType (Optional[str])
            - violationConfidence (Optional[float])
        """
        if not self.is_model_loaded():
            raise ModelNotAvailableError(
                message=(
                    f"AI model weights not found at '{self.resolved_model_path}'. "
                    f"Real detection cannot run without trained weights. "
                    f"Please place 'yolov8n-traffic.pt' in the models directory."
                ),
                expected_path=self.resolved_model_path,
                expected_classes=EXPECTED_TRAFFIC_CLASSES,
            )

        conf = (
            confidence_threshold
            if confidence_threshold is not None
            else self.confidence_threshold
        )

        # Prepare image array
        if isinstance(image_input, bytes):
            import cv2
            nparr = np.frombuffer(image_input, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Could not decode image bytes into valid OpenCV matrix.")
        else:
            img = image_input

        if not isinstance(img, np.ndarray) or img.size == 0:
            raise ValueError("Invalid image matrix provided for inference.")

        height, width = img.shape[:2]
        if height <= 0 or width <= 0:
            raise ValueError(f"Invalid image dimensions: {width}x{height}")

        # Run CPU prediction explicitly
        try:
            results = self.model.predict(
                source=img,
                conf=conf,
                device="cpu",
                verbose=False,
            )
        except Exception as exc:
            logger.exception(f"Inference execution failed: {exc}")
            raise RuntimeError(f"YOLO inference runtime error: {str(exc)}") from exc

        boxes: List[Dict[str, Any]] = []
        vehicles: List[Dict[str, Any]] = []
        persons: List[Dict[str, Any]] = []
        violation_boxes: List[Dict[str, Any]] = []
        compliant_boxes: List[Dict[str, Any]] = []

        box_counter = 1
        for result in results:
            if not hasattr(result, "boxes") or result.boxes is None:
                continue

            for box in result.boxes:
                cls_id = int(box.cls[0].item()) if hasattr(box.cls[0], "item") else int(box.cls[0])
                confidence = float(box.conf[0].item()) if hasattr(box.conf[0], "item") else float(box.conf[0])

                label = self.supported_classes.get(cls_id, f"class_{cls_id}")
                category, color = self._classify_label(label)

                xyxy = box.xyxy[0].tolist() if hasattr(box.xyxy[0], "tolist") else list(box.xyxy[0])
                x1, y1, x2, y2 = xyxy

                # Bound clamp
                x1 = max(0.0, min(float(width), float(x1)))
                y1 = max(0.0, min(float(height), float(y1)))
                x2 = max(0.0, min(float(width), float(x2)))
                y2 = max(0.0, min(float(height), float(y2)))

                # Normalized coordinates [x1, y1, x2, y2] (0.0 to 1.0)
                xmin_n = round(x1 / width, 4)
                ymin_n = round(y1 / height, 4)
                xmax_n = round(x2 / width, 4)
                ymax_n = round(y2 / height, 4)

                # Percentage coordinates for UI overlay
                pct_x = round((x1 / width) * 100, 2)
                pct_y = round((y1 / height) * 100, 2)
                pct_w = round(max(0.0, (x2 - x1) / width) * 100, 2)
                pct_h = round(max(0.0, (y2 - y1) / height) * 100, 2)

                box_obj = {
                    "id": f"det-bb-{box_counter}",
                    "label": label.upper().replace(" ", "_"),
                    "classId": cls_id,
                    "category": category,
                    "confidence": round(confidence, 4),
                    "xyxy": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                    "normalized": [xmin_n, ymin_n, xmax_n, ymax_n],
                    "coordinates": {
                        "x1": xmin_n,
                        "y1": ymin_n,
                        "x2": xmax_n,
                        "y2": ymax_n,
                        "xmin": xmin_n,
                        "ymin": ymin_n,
                        "xmax": xmax_n,
                        "ymax": ymax_n,
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

                if category == "VEHICLE":
                    vehicles.append(box_obj)
                elif category == "PERSON":
                    persons.append(box_obj)
                elif category == "HELMET_VIOLATION":
                    violation_boxes.append(box_obj)
                elif category == "HELMET_COMPLIANT":
                    compliant_boxes.append(box_obj)

        # Separate vehicle/person detection from helmet violation analysis
        is_candidate_violation = False
        violation_type: Optional[str] = None
        violation_confidence: Optional[float] = None
        helmet_message: str

        if not self.helmet_classification_supported:
            helmet_message = (
                "Loaded model contains standard object classes (e.g., COCO) but does not include "
                "validated helmet or no-helmet classes. Helmet violation classification is unavailable."
            )
        else:
            if violation_boxes:
                is_candidate_violation = True
                violation_confidence = max(b["confidence"] for b in violation_boxes)
                # Check for pillion or triple riding if multiple persons detected
                if len(persons) >= 3:
                    violation_type = "TRIPLE_RIDING"
                elif len(persons) >= 2 and any("pillion" in b["label"].lower() for b in violation_boxes):
                    violation_type = "NO_HELMET_PILLION"
                else:
                    violation_type = "NO_HELMET_RIDER"

                helmet_message = (
                    f"Candidate violation detected: {violation_type} "
                    f"({len(violation_boxes)} unhelmeted rider/head region(s) detected)."
                )
            elif compliant_boxes:
                helmet_message = (
                    f"Compliant: {len(compliant_boxes)} helmet(s) identified on riders."
                )
            elif persons:
                helmet_message = "Rider/Person detected but helmet status inconclusive."
            else:
                helmet_message = "No riders or helmet objects detected in frame."

        return {
            "detected": len(boxes) > 0,
            "totalDetections": len(boxes),
            "boxes": boxes,
            "vehicles": vehicles,
            "persons": persons,
            "helmetClassificationAvailable": self.helmet_classification_supported,
            "helmetClassificationMessage": helmet_message,
            "isCandidateViolation": is_candidate_violation,
            "violationType": violation_type,
            "violationConfidence": violation_confidence,
            "imageDimensions": {"width": width, "height": height},
        }


# Singleton engine instance
yolo_engine = YoloInferenceEngine()
