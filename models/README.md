# AI Model Weights Directory

This directory stores trained computer vision weights (e.g., YOLOv8 / YOLOv11) used by the FastAPI backend inference service (`backend/app/models/yolo_inference.py`).

## Recommended Model Setup
Place your trained PyTorch weights or exported ONNX models here:
- `yolov8n-traffic.pt` (Default lightweight model for helmet & rider detection)
- `best.pt` (Custom trained checkpoint)

## Backend Reference
The backend locates weights via environment variables in `backend/.env`:
```env
MODEL_WEIGHTS_PATH="../models/yolov8n-traffic.pt"
MODEL_CONFIDENCE_THRESHOLD=0.55
```

> **Note**: Model weights (`*.pt`, `*.onnx`, `*.engine`) are excluded from Git via `.gitignore` to prevent repository bloat.
