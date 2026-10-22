"""
Vehicle Classification and Rider-Vehicle Spatial Association Service.

Responsibilities:
1. Distinguishes motorized two-wheelers (motorcycles, scooters, mopeds) from non-motorized cycles (bicycles).
2. Performs spatial association between detected riders and candidate vehicles using bounding-box overlap,
   centroid alignment, and vertical spatial relations.
3. Classifies vehicle type as:
   - MOTORCYCLE (motorized two-wheeler)
   - BICYCLE (non-motorized cycle)
   - OTHER (car, bus, truck, etc.)
   - UNCERTAIN (cannot be reliably confirmed; triggers manual review requirement)
4. Determines challan candidate eligibility:
   - Bicycle riders: strictly EXCLUDED from helmet violation challans.
   - Motorcycle riders without helmet: ELIGIBLE for candidate case creation.
   - Uncertain vehicle type: NOT an automatic challan candidate (NEEDS_MANUAL_REVIEW).
   - Strict rule: Motorcycle status is NEVER inferred solely from helmet confidence, person confidence, or plate detection.
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
import numpy as np


class VehicleType(str, Enum):
    MOTORCYCLE = "MOTORCYCLE"
    BICYCLE = "BICYCLE"
    OTHER = "OTHER"
    UNCERTAIN = "UNCERTAIN"


MOTORCYCLE_KEYWORDS = {
    "motorcycle",
    "motorbike",
    "motor_bike",
    "scooter",
    "moped",
    "two_wheeler",
    "two-wheeler",
}

BICYCLE_KEYWORDS = {
    "bicycle",
    "cycle",
    "cyclist",
    "pushbike",
    "pedal_cycle",
    "non_motorized_cycle",
    "push_bike",
}

OTHER_VEHICLE_KEYWORDS = {
    "car",
    "bus",
    "truck",
    "van",
    "auto",
    "auto_rickshaw",
    "rickshaw",
}


def classify_vehicle_label(label: str) -> VehicleType:
    """Classifies raw detection label into normalized VehicleType."""
    clean = str(label or "").lower().strip().replace("-", "_").replace(" ", "_")
    
    # Check motorized two-wheelers first
    for kw in MOTORCYCLE_KEYWORDS:
        if kw in clean:
            return VehicleType.MOTORCYCLE
            
    # Check bicycles / non-motorized cycles (excluding any motorized references)
    if "motor" not in clean:
        for kw in BICYCLE_KEYWORDS:
            if kw in clean:
                return VehicleType.BICYCLE
                
    # Check other vehicle categories
    for kw in OTHER_VEHICLE_KEYWORDS:
        if kw in clean:
            return VehicleType.OTHER
            
    return VehicleType.UNCERTAIN


def compute_box_iou(box1: List[float], box2: List[float]) -> float:
    """Computes Intersection over Union of two bounding boxes in [x1, y1, x2, y2] format."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter_area = inter_w * inter_h

    area1 = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
    area2 = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])

    union_area = area1 + area2 - inter_area
    if union_area <= 0.0:
        return 0.0
    return inter_area / union_area


def compute_rider_vehicle_association(
    rider_box: List[float],
    veh_box: List[float],
    min_association_threshold: float = 0.20,
) -> Tuple[bool, float]:
    """
    Evaluates spatial relationship between a rider and a vehicle.
    Returns (is_associated: bool, association_score: float).

    Spatial principles:
    1. A rider sits directly on top of or overlaps the upper region of the vehicle.
    2. Horizontal alignment: rider horizontal centroid should align within or near vehicle bounds.
    3. Vertical compatibility: rider bottom ry2 should be near or penetrating vehicle top vy1.
    4. Bounding box intersection and IoU.
    """
    rx1, ry1, rx2, ry2 = [float(v) for v in rider_box[:4]]
    vx1, vy1, vx2, vy2 = [float(v) for v in veh_box[:4]]

    rw = max(0.001, rx2 - rx1)
    rh = max(0.001, ry2 - ry1)
    vw = max(0.001, vx2 - vx1)
    vh = max(0.001, vy2 - vy1)

    # 1. Horizontal overlap and centroid containment
    inter_x = max(0.0, min(rx2, vx2) - max(rx1, vx1))
    h_overlap = inter_x / rw

    rcx = (rx1 + rx2) / 2.0
    vcx = (vx1 + vx2) / 2.0
    dx_norm = abs(rcx - vcx) / max(vw, rw)

    # Rider horizontal centroid must be reasonably positioned relative to vehicle bounds
    centroid_in_bounds = (vx1 - 0.25 * rw) <= rcx <= (vx2 + 0.25 * rw)
    if not centroid_in_bounds or h_overlap < 0.20:
        return False, 0.0

    # 2. Vertical relationship:
    # Rider bottom should be at least near vehicle top (ry2 >= vy1 - 0.35 * vh)
    # and rider top should not be below vehicle bottom (ry1 <= vy2)
    vertical_compatible = (ry2 >= (vy1 - 0.35 * vh)) and (ry1 <= vy2)
    if not vertical_compatible:
        return False, 0.0

    inter_y = max(0.0, min(ry2, vy2) - max(ry1, vy1))
    v_overlap = inter_y / rh

    # 3. Direct IoU
    iou = compute_box_iou([rx1, ry1, rx2, ry2], [vx1, vy1, vx2, vy2])

    # Centroid alignment score (1.0 = perfect vertical column alignment)
    centroid_score = max(0.0, 1.0 - min(1.0, dx_norm))

    # Composite association score (weighted)
    score = (0.35 * h_overlap) + (0.35 * centroid_score) + (0.20 * v_overlap) + (0.10 * iou)
    is_associated = score >= min_association_threshold
    return is_associated, round(score, 4)


class VehicleClassifier:
    """
    Unified vehicle-type classification and rider association service.
    """

    def __init__(self, detector: Any = None):
        self._custom_detector = detector
        if self._custom_detector is None:
            self._init_default_detector()

    def _init_default_detector(self) -> None:
        """Attempts to load a secondary YOLO vehicle detector if weights exist."""
        try:
            import os
            from ultralytics import YOLO
            from app.config import BACKEND_DIR, PROJECT_ROOT, MODELS_DIR, resolve_model_path
            candidate_paths = [
                os.path.join(BACKEND_DIR, "yolov8n.pt"),
                os.path.join(MODELS_DIR, "yolov8n.pt"),
                os.path.join(PROJECT_ROOT, "yolov8n.pt"),
                os.path.join(MODELS_DIR, "yolov8n-traffic.pt"),
                resolve_model_path("yolov8n.pt"),
                resolve_model_path("yolov8n-traffic.pt"),
                "yolov8n.pt",
            ]
            for p in candidate_paths:
                if p and os.path.isfile(p):
                    self._custom_detector = YOLO(p)
                    break
        except Exception:
            self._custom_detector = None

    def set_detector(self, detector: Any) -> None:
        """Injects custom/mock vehicle detector for tests or specialized inference."""
        self._custom_detector = detector

    def extract_vehicle_boxes(
        self,
        boxes: List[Dict[str, Any]],
        image: Optional[np.ndarray] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extracts all vehicle bounding boxes from existing frame detections,
        or calls registered secondary detector if available.
        """
        vehicle_boxes: List[Dict[str, Any]] = []

        # 1. Check existing detection boxes
        for b in boxes:
            cat = str(b.get("category", "")).upper()
            lbl = str(b.get("label", "")).lower()
            v_type = classify_vehicle_label(lbl)
            if cat == "VEHICLE" or v_type in (VehicleType.MOTORCYCLE, VehicleType.BICYCLE, VehicleType.OTHER):
                vehicle_boxes.append({
                    **b,
                    "vehicleType": v_type.value,
                })

        # 2. If no vehicle boxes present and custom detector registered, query detector
        if not vehicle_boxes and self._custom_detector is not None and image is not None:
            try:
                res = self._custom_detector.predict(image, verbose=False)
                if hasattr(res, "boxes") or (isinstance(res, list) and len(res) > 0 and hasattr(res[0], "boxes")):
                    box_list = res[0].boxes if isinstance(res, list) else res.boxes
                    for bx in box_list:
                        cls_id = int(bx.cls[0].item()) if hasattr(bx.cls[0], "item") else int(bx.cls[0])
                        conf = float(bx.conf[0].item()) if hasattr(bx.conf[0], "item") else float(bx.conf[0])
                        label = getattr(self._custom_detector, "names", {}).get(cls_id, f"class_{cls_id}")
                        v_type = classify_vehicle_label(label)
                        # Only include genuine vehicles (motorcycle, bicycle, other); ignore persons, traffic lights, etc.
                        if v_type in (VehicleType.MOTORCYCLE, VehicleType.BICYCLE, VehicleType.OTHER):
                            coords = bx.xyxy[0].tolist() if hasattr(bx.xyxy[0], "tolist") else list(bx.xyxy[0])
                            vx1, vy1, vx2, vy2 = float(coords[0]), float(coords[1]), float(coords[2]), float(coords[3])
                            img_h, img_w = image.shape[:2] if image is not None else (1, 1)
                            norm_x1 = round(max(0.0, min(1.0, vx1 / img_w)), 4)
                            norm_y1 = round(max(0.0, min(1.0, vy1 / img_h)), 4)
                            norm_x2 = round(max(0.0, min(1.0, vx2 / img_w)), 4)
                            norm_y2 = round(max(0.0, min(1.0, vy2 / img_h)), 4)
                            pct_x = round(norm_x1 * 100, 2)
                            pct_y = round(norm_y1 * 100, 2)
                            pct_w = round(max(0.0, norm_x2 - norm_x1) * 100, 2)
                            pct_h = round(max(0.0, norm_y2 - norm_y1) * 100, 2)
                            vehicle_boxes.append({
                                "id": f"veh-sec-{len(vehicle_boxes) + 1}",
                                "label": label,
                                "classId": cls_id,
                                "category": "VEHICLE",
                                "vehicleType": v_type.value,
                                "confidence": round(conf, 4),
                                "xyxy": [round(c, 1) for c in coords],
                                "normalized": [norm_x1, norm_y1, norm_x2, norm_y2],
                                "coordinates": {
                                    "x1": norm_x1,
                                    "y1": norm_y1,
                                    "x2": norm_x2,
                                    "y2": norm_y2,
                                    "xmin": norm_x1,
                                    "ymin": norm_y1,
                                    "xmax": norm_x2,
                                    "ymax": norm_y2,
                                },
                                "percentage": {
                                    "x": pct_x,
                                    "y": pct_y,
                                    "width": pct_w,
                                    "height": pct_h,
                                },
                                "color": "#2563EB",
                            })
            except Exception:
                pass

        return vehicle_boxes

    def associate_rider(
        self,
        rider_box: List[float],
        vehicle_boxes: List[Dict[str, Any]],
    ) -> Tuple[VehicleType, float, Optional[List[float]], float]:
        """
        Finds the best matching vehicle for a rider box.
        Returns: (VehicleType, vehicle_confidence, vehicle_bbox, association_score).
        Handles ambiguous vehicle overlap safely by falling back to UNCERTAIN.
        """
        if not vehicle_boxes:
            return VehicleType.UNCERTAIN, 0.0, None, 0.0

        associations: List[Tuple[float, VehicleType, float, List[float], Dict[str, Any]]] = []

        for vb in vehicle_boxes:
            v_coords = vb.get("xyxy")
            if not v_coords or len(v_coords) < 4:
                continue

            is_assoc, score = compute_rider_vehicle_association(rider_box, v_coords)
            if is_assoc:
                v_type = classify_vehicle_label(vb.get("label", ""))
                v_conf = float(vb.get("confidence", 0.9))
                associations.append((score, v_type, v_conf, v_coords, vb))

        if not associations:
            return VehicleType.UNCERTAIN, 0.0, None, 0.0

        # Sort candidate vehicles by association score descending
        associations.sort(key=lambda x: x[0], reverse=True)
        top_score, top_type, top_conf, top_coords, _ = associations[0]

        # Ambiguity check: If runner-up vehicle is a conflicting category with competitive score
        if len(associations) > 1:
            second_score, second_type, second_conf, _, _ = associations[1]
            if top_type != second_type and top_type in (VehicleType.MOTORCYCLE, VehicleType.BICYCLE) and second_type in (VehicleType.MOTORCYCLE, VehicleType.BICYCLE):
                # When bicycle and motorcycle are in a close spatial race, fail safely to UNCERTAIN
                if abs(top_score - second_score) < 0.15 or (second_score / top_score > 0.80):
                    return VehicleType.UNCERTAIN, max(top_conf, second_conf), top_coords, top_score

        return top_type, top_conf, top_coords, top_score

    def evaluate_challan_eligibility(
        self,
        classification: str,
        vehicle_type: VehicleType,
        rider_confidence: float = 0.0,
    ) -> Tuple[bool, Optional[str]]:
        """
        Applies enforcement policy to determine whether a rider should be queued
        for a helmet-violation challan draft:
        - BICYCLE: Never eligible for helmet challans (BICYCLE_EXCLUDED)
        - MOTORCYCLE + WITHOUT_HELMET: Eligible for PENDING_REVIEW case
        - MOTORCYCLE + WITH_HELMET: Compliant, no challan
        - UNCERTAIN / OTHER: Ineligible for automatic challan (UNCERTAIN_VEHICLE_TYPE)
        """
        if vehicle_type == VehicleType.BICYCLE:
            return False, "BICYCLE_EXCLUDED"

        if vehicle_type == VehicleType.MOTORCYCLE:
            if classification == "WITHOUT_HELMET":
                return True, None
            elif classification == "WITH_HELMET":
                return False, "HELMET_COMPLIANT"
            else:
                return False, "UNCONFIRMED_HELMET_STATUS"

        # Uncertain or non-motorcycle (car, pedestrian, etc.)
        return False, "UNCERTAIN_VEHICLE_TYPE"


# Singleton instance
vehicle_classifier = VehicleClassifier()
