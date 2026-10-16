"""
YOLOv8 Helmet Detection Inference Boundary
Loads weights from models/ directory (outside frontend/) and performs candidate region analysis.
"""

import os
from typing import Dict, Any, List

class YoloInferenceEngine:
    def __init__(self, model_path: str = None, confidence_threshold: float = 0.65):
        self.model_path = model_path or os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../models/yolov8n-traffic.pt"))
        self.confidence_threshold = confidence_threshold
        self.model = None
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            try:
                from ultralytics import YOLO
                self.model = YOLO(self.model_path)
            except Exception:
                self.model = None
        else:
            self.model = None

    def is_model_loaded(self) -> bool:
        return self.model is not None

    def detect_candidate(self, image_bytes_or_array) -> Dict[str, Any]:
        """
        Runs candidate detection on frame. Returns bounding boxes and predicted violation class.
        """
        if not self.is_model_loaded():
            return {
                "detected": False,
                "confidence": 0.0,
                "boxes": [],
                "status": "DEMO_STANDIN",
                "message": "Model weights not present at model_path. Running in simulation boundary mode."
            }

        # Real inference with YOLO model when weights are present
        try:
            results = self.model(image_bytes_or_array, conf=self.confidence_threshold)
            boxes = []
            for r in results:
                for box in r.boxes:
                    cls_id = int(box.cls[0])
                    label = self.model.names[cls_id] if hasattr(self.model, 'names') else str(cls_id)
                    boxes.append({
                        "label": label,
                        "confidence": float(box.conf[0]),
                        "xyxy": box.xyxy[0].tolist()
                    })
            return {
                "detected": len(boxes) > 0,
                "boxes": boxes,
                "status": "LIVE_INFERENCE"
            }
        except Exception as e:
            return {
                "detected": False,
                "error": str(e),
                "status": "INFERENCE_ERROR"
            }

yolo_engine = YoloInferenceEngine()
