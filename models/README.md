# AI Model Weights Directory

This directory stores trained computer vision weights (e.g., YOLOv8 / YOLOv11) used by the FastAPI backend inference service (`backend/app/models/yolo_inference.py`).

## Expected Model Weights File
- Expected default path: `models/yolov8n-traffic.pt`

## Required Class Taxonomy for Helmet Violation Detection
The YOLO model must be specifically trained or fine-tuned on traffic safety classes. Standard COCO weights (80 classes such as `person`, `car`, `motorcycle`, `bicycle`) **cannot** classify helmet compliance or violations.

To enable helmet violation detection, the model weights must contain validated classes matching:
1. **Helmet Compliant**: `helmet`, `with_helmet`, `helmet_on`, `helmet_rider`
2. **Helmet Violation**: `no_helmet`, `without_helmet`, `no_helmet_rider`, `no_helmet_pillion`
3. **Vehicle**: `motorcycle`, `scooter`, `bike`
4. **Person/Rider**: `rider`, `person`

### Behavior with Standard COCO Weights
If a standard COCO model (such as generic `yolov8n.pt`) is loaded:
- Vehicle and person detection will function and bounding boxes will be returned.
- Helmet classification will be reported as **unavailable** (`helmetClassificationAvailable: false`).
- No false helmet violations or sanctions will be claimed or issued.

## Backend Configuration
The backend locates weights via environment variables in `backend/.env` (or defaults to `models/yolov8n-traffic.pt`):
```env
YOLO_MODEL_PATH="../models/yolov8n-traffic.pt"
INFERENCE_CONFIDENCE_THRESHOLD=0.65
```

> **Note**: Model weights (`*.pt`, `*.onnx`, `*.engine`) are excluded from Git via `.gitignore` to prevent repository bloat.
