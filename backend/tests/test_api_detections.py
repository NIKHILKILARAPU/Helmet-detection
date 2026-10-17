"""
Unit & Integration Tests for YOLO Inference Service & Detections API Endpoint.

Verifies:
- Unauthorized request rejection (HTTP 401)
- Missing model weights error handling (HTTP 503, error_code MODEL_NOT_AVAILABLE)
- Input validation: file type rejection, empty file, malformed image bytes (HTTP 400)
- Model class taxonomy validation:
  - Generic COCO model (without helmet classes) reports helmetClassificationAvailable=False
  - Custom traffic model (with helmet/no_helmet classes) enables helmet classification
- Bounding box coordinate calculations (pixel, normalized, and percentage for UI overlay)
- Separation of vehicles, persons, and violation candidate objects
- Proper MongoDB schema persistence (model_runs and violations with status PENDING_REVIEW)
- Zero reliance on downloading external heavy weights for unit tests
"""

import io
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from bson import ObjectId
import numpy as np
import cv2
from fastapi.testclient import TestClient

from main import app
from app.config import settings
from app.core.security import hash_password, create_access_token
from app.db.connection import get_db
from app.db.collections import COLLECTION_USERS, COLLECTION_MODEL_RUNS, COLLECTION_VIOLATIONS, COLLECTION_CAMERAS
from app.models.yolo_inference import yolo_engine

client = TestClient(app)


def _create_test_image_bytes(width: int = 320, height: int = 240, color: tuple = (100, 150, 200)) -> bytes:
    """Generates valid JPEG image bytes in memory."""
    img = np.full((height, width, 3), color, dtype=np.uint8)
    success, encoded = cv2.imencode(".jpg", img)
    assert success
    return encoded.tobytes()


class MockBox:
    """Simulates an Ultralytics YOLO detected box."""

    def __init__(self, cls_id: int, conf: float, xyxy: list):
        self.cls = [MagicMock(item=lambda: cls_id)]
        self.conf = [MagicMock(item=lambda: conf)]
        self.xyxy = [MagicMock(tolist=lambda: xyxy)]


class MockResult:
    """Simulates an Ultralytics YOLO Results object."""

    def __init__(self, boxes: list):
        self.boxes = boxes


class MockYoloModel:
    """Simulates a YOLO model instance with configurable classes and output boxes."""

    def __init__(self, names: dict, mock_boxes: list = None):
        self.names = names
        self._mock_boxes = mock_boxes or []

    def predict(self, source, conf=0.5, device="cpu", verbose=False):
        return [MockResult(self._mock_boxes)]


@pytest.fixture(scope="module", autouse=True)
def setup_operator_user():
    """Seeds a test operator user and camera for detections testing."""
    db = get_db()
    now = datetime.now(timezone.utc)
    db[COLLECTION_USERS].delete_many({"email": "test.detections_op@traffic.gov.in"})
    db[COLLECTION_CAMERAS].delete_many({"name": "TEST_DETECTIONS_CAM"})

    op_doc = {
        "employeeId": "TEST-DET-OP-01",
        "name": "Operator Detection Tester",
        "email": "test.detections_op@traffic.gov.in",
        "passwordHash": hash_password("ValidDetectionPass123!"),
        "role": "operator",
        "status": "ACTIVE",
        "createdAt": now,
        "updatedAt": now,
    }
    db[COLLECTION_USERS].insert_one(op_doc)

    cam_doc = {
        "_id": ObjectId("65f000000000000000000099"),
        "name": "TEST_DETECTIONS_CAM",
        "junction": "Test Surveillance Point 1",
        "streamType": "WEBCAM",
        "source": "cam-0",
        "resolution": "1080p",
        "fps": 30.0,
        "status": "ONLINE",
        "lastHeartbeatAt": now,
        "createdBy": ObjectId("65f000000000000000000001"),
        "createdAt": now,
        "updatedAt": now,
    }
    db[COLLECTION_CAMERAS].insert_one(cam_doc)

    yield

    # Teardown
    db[COLLECTION_USERS].delete_many({"email": "test.detections_op@traffic.gov.in"})
    db[COLLECTION_CAMERAS].delete_many({"name": "TEST_DETECTIONS_CAM"})
    db[COLLECTION_MODEL_RUNS].delete_many({"modelName": "YOLOv8n-Traffic"})
    db[COLLECTION_VIOLATIONS].delete_many({"caseId": {"$regex": r"^TG-2026-"}})


@pytest.fixture
def auth_headers():
    """Returns valid Bearer authorization header for test operator."""
    db = get_db()
    user = db[COLLECTION_USERS].find_one({"email": "test.detections_op@traffic.gov.in"})
    token = create_access_token(
        data={
            "sub": str(user["_id"]),
            "employeeId": user["employeeId"],
            "name": user["name"],
            "role": user["role"],
        }
    )
    return {"Authorization": f"Bearer {token}"}


class TestDetectionsApiAuthorizationAndValidation:
    """Verifies security boundaries and HTTP validation for /detections/analyze."""

    def test_analyze_unauthorized_request_returns_401(self):
        """Calling /detections/analyze without JWT Bearer token must return HTTP 401."""
        img_bytes = _create_test_image_bytes()
        files = {"file": ("frame.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        response = client.post(f"{settings.API_PREFIX}/detections/analyze", files=files)
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "UNAUTHORIZED"

    def test_analyze_missing_model_weights_returns_503_model_not_available(self, auth_headers):
        """When YOLO model weights file is absent, must return HTTP 503 MODEL_NOT_AVAILABLE."""
        # Ensure model is unloaded
        original_model = yolo_engine.model
        yolo_engine.model = None

        try:
            img_bytes = _create_test_image_bytes()
            files = {"file": ("frame.jpg", io.BytesIO(img_bytes), "image/jpeg")}
            response = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files,
                headers=auth_headers,
            )
            assert response.status_code == 503
            data = response.json()
            assert data["success"] is False
            assert data["error_code"] == "MODEL_NOT_AVAILABLE"
            assert "yolov8n-traffic.pt" in data["message"]
            # Verify details document expected path and classes
            detail_fields = [d["field"] for d in data.get("details", [])]
            assert "model_path" in detail_fields
            assert "expected_classes" in detail_fields
        finally:
            yolo_engine.model = original_model

    def test_analyze_unsupported_file_mime_returns_400(self, auth_headers):
        """Uploading text/pdf files must return HTTP 400 validation error."""
        files = {"file": ("log.txt", io.BytesIO(b"Plain text log"), "text/plain")}
        response = client.post(
            f"{settings.API_PREFIX}/detections/analyze",
            files=files,
            headers=auth_headers,
        )
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "BUSINESS_VALIDATION_ERROR"
        assert "unsupported file type" in data["message"].lower()

    def test_analyze_empty_file_returns_400(self, auth_headers):
        """Uploading 0-byte file must return HTTP 400 validation error."""
        files = {"file": ("empty.jpg", io.BytesIO(b""), "image/jpeg")}
        response = client.post(
            f"{settings.API_PREFIX}/detections/analyze",
            files=files,
            headers=auth_headers,
        )
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "BUSINESS_VALIDATION_ERROR"
        assert "empty" in data["message"].lower()

    def test_analyze_corrupt_image_bytes_returns_400(self, auth_headers):
        """Uploading corrupt non-image bytes named .jpg must return HTTP 400."""
        files = {"file": ("corrupt.jpg", io.BytesIO(b"not-a-valid-jpeg-image-bytes-header"), "image/jpeg")}
        response = client.post(
            f"{settings.API_PREFIX}/detections/analyze",
            files=files,
            headers=auth_headers,
        )
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "BUSINESS_VALIDATION_ERROR"
        assert "corrupt or unreadable" in data["message"].lower()


class TestModelClassTaxonomyAndInference:
    """Verifies class taxonomy checks and structured output parsing."""

    def test_generic_coco_model_reports_helmet_classification_unavailable(self, auth_headers):
        """
        A standard COCO model has motorcycle and person, but NO helmet classes.
        Must report helmetClassificationAvailable=False and never flag false violations.
        """
        coco_names = {0: "person", 1: "bicycle", 2: "car", 3: "motorcycle"}
        mock_boxes = [
            MockBox(cls_id=3, conf=0.92, xyxy=[50.0, 100.0, 200.0, 220.0]),
            MockBox(cls_id=0, conf=0.88, xyxy=[80.0, 40.0, 160.0, 180.0]),
        ]
        mock_model = MockYoloModel(names=coco_names, mock_boxes=mock_boxes)
        yolo_engine.set_model(mock_model)

        img_bytes = _create_test_image_bytes(width=640, height=480)
        files = {"file": ("frame.jpg", io.BytesIO(img_bytes), "image/jpeg")}

        response = client.post(
            f"{settings.API_PREFIX}/detections/analyze",
            files=files,
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        payload = data["data"]
        assert payload["detected"] is True
        assert payload["totalDetections"] == 2
        assert payload["helmetClassificationAvailable"] is False
        assert "does not include validated helmet" in payload["helmetClassificationMessage"]
        assert payload["isCandidateViolation"] is False
        assert payload["violationType"] is None
        assert payload["status"] == "NO_VIOLATION"

        # Check vehicle and person separation
        assert len(payload["vehicles"]) == 1
        assert payload["vehicles"][0]["label"] == "MOTORCYCLE"
        assert payload["vehicles"][0]["category"] == "VEHICLE"
        assert len(payload["persons"]) == 1
        assert payload["persons"][0]["label"] == "PERSON"
        assert payload["persons"][0]["category"] == "PERSON"

    def test_custom_traffic_model_flags_helmet_violation_and_ingests_draft(self, auth_headers):
        """
        When model has validated helmet classes and detects a rider without helmet,
        it flags NO_HELMET_RIDER and queues candidate with status PENDING_REVIEW.
        """
        traffic_names = {0: "person", 1: "motorcycle", 2: "helmet", 3: "no_helmet"}
        mock_boxes = [
            MockBox(cls_id=1, conf=0.91, xyxy=[100.0, 200.0, 300.0, 400.0]),
            MockBox(cls_id=0, conf=0.95, xyxy=[120.0, 50.0, 280.0, 350.0]),
            MockBox(cls_id=3, conf=0.93, xyxy=[170.0, 60.0, 230.0, 130.0]),
        ]
        mock_model = MockYoloModel(names=traffic_names, mock_boxes=mock_boxes)
        yolo_engine.set_model(mock_model)

        img_bytes = _create_test_image_bytes(width=640, height=480)
        files = {"file": ("traffic_frame.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        form_data = {
            "camera_id": "65f000000000000000000099",
            "source_label": "Test Intersection Camera",
            "auto_ingest": "true",
        }

        response = client.post(
            f"{settings.API_PREFIX}/detections/analyze",
            files=files,
            data=form_data,
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        payload = data["data"]
        assert payload["detected"] is True
        assert payload["helmetClassificationAvailable"] is True
        assert payload["isCandidateViolation"] is True
        assert payload["violationType"] == "NO_HELMET_RIDER"
        assert payload["violationConfidence"] == 0.93
        assert payload["status"] == "PENDING_REVIEW"
        assert payload["caseId"] is not None
        assert payload["modelRunId"] is not None

        # Verify percentage coordinates format for UI overlay
        boxes = payload["boxes"]
        assert len(boxes) == 3
        no_helmet_box = next(b for b in boxes if b["label"] == "NO_HELMET")
        assert no_helmet_box["category"] == "HELMET_VIOLATION"
        assert no_helmet_box["color"] == "#DC2626"
        pct = no_helmet_box["percentage"]
        assert 0 <= pct["x"] <= 100
        assert 0 <= pct["y"] <= 100
        assert 0 <= pct["width"] <= 100
        assert 0 <= pct["height"] <= 100

        # Verify MongoDB persistence in violations and model_runs collections
        db = get_db()
        violation_doc = db[COLLECTION_VIOLATIONS].find_one({"caseId": payload["caseId"]})
        assert violation_doc is not None
        assert violation_doc["status"] == "PENDING_REVIEW"
        assert violation_doc["violationType"] == "NO_HELMET_RIDER"
        assert violation_doc["confidence"] == 0.93
        assert violation_doc["evidence"]["storagePath"].startswith("/uploads/evidence/")
        assert violation_doc["evidence"]["fileHash"] is not None
        assert violation_doc["evidence"]["width"] == 640
        assert violation_doc["evidence"]["height"] == 480

        # Verify model_runs collection entry
        run_doc = db[COLLECTION_MODEL_RUNS].find_one({"_id": ObjectId(payload["modelRunId"])})
        assert run_doc is not None
        assert run_doc["status"] == "SUCCESS"
        assert run_doc["resultSummary"]["totalDetections"] == 3
        assert run_doc["resultSummary"]["isCandidateViolation"] is True

    def test_custom_traffic_model_compliant_helmet(self, auth_headers):
        """When rider is wearing a helmet, candidate violation must NOT be triggered."""
        traffic_names = {0: "person", 1: "motorcycle", 2: "helmet", 3: "no_helmet"}
        mock_boxes = [
            MockBox(cls_id=1, conf=0.90, xyxy=[100.0, 200.0, 300.0, 400.0]),
            MockBox(cls_id=2, conf=0.96, xyxy=[160.0, 50.0, 240.0, 140.0]),
        ]
        mock_model = MockYoloModel(names=traffic_names, mock_boxes=mock_boxes)
        yolo_engine.set_model(mock_model)

        img_bytes = _create_test_image_bytes(width=640, height=480)
        files = {"file": ("compliant.jpg", io.BytesIO(img_bytes), "image/jpeg")}

        response = client.post(
            f"{settings.API_PREFIX}/detections/analyze",
            files=files,
            headers=auth_headers,
        )
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["helmetClassificationAvailable"] is True
        assert payload["isCandidateViolation"] is False
        assert payload["status"] == "NO_VIOLATION"
        assert "Compliant" in payload["helmetClassificationMessage"]

    def test_get_model_status_endpoint(self):
        """GET /detections/model-status returns 200 with model info."""
        response = client.get(f"{settings.API_PREFIX}/detections/model-status")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "classesCount" in data["data"]
        assert "helmetClassificationSupported" in data["data"]
        assert "expectedClasses" in data["data"]
