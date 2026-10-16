# TrafficGuard AI — Python FastAPI Backend

Official backend service for TrafficGuard AI, providing REST APIs for candidate violation triage, e-challan draft sanctioning, camera stream configuration, and YOLOv8 inference boundaries.

---

## 🚀 Setup & Execution

### 1. Create and Activate Virtual Environment
```bash
# From the backend/ directory
python -m venv venv

# Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# Linux / macOS:
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 4. Run Development Server
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
API Documentation (Swagger UI) is available at: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 📁 Architecture
* `main.py`: FastAPI application entrypoint with CORS and health check.
* `app/config.py`: Central Pydantic settings loading `.env`.
* `app/api/`: Modular routers (`violations.py`, `stats.py`, `camera.py`).
* `app/models/`: YOLOv8 inference engine loading weights from the root `models/` directory outside `frontend/`.
