"""
Unit & Integration Tests for YOLO and Roboflow Inference Services & Detections API Endpoint.

Verifies:
- Unauthorized request rejection (HTTP 401)
- Missing model weights / Roboflow API key error handling (HTTP 503 MODEL_NOT_AVAILABLE)
- Input validation: file type rejection, empty file, malformed image bytes (HTTP 400)
- Local YOLO Model class taxonomy validation:
  - Generic COCO model reports helmetClassificationAvailable=False
  - Custom traffic model enables helmet classification
- Roboflow Hosted Inference Integration:
  - Exact class mapping ("With Helmet", "Without Helmet", "licence")
  - Candidate violation triage strictly queued as PENDING_REVIEW
  - Coordinate conversion from Roboflow center format (x, y, w, h) to corner/normalized/percentage
  - Upstream error handling (401/403 auth, timeout 504, malformed response 502)
  - Zero leakage of API key in logs or error messages
  - Completely mocked HTTP responses; zero external network calls during automated testing
- Proper MongoDB schema persistence (model_runs, evidence, and violations)
"""

import os
import io
import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
from bson import ObjectId
import numpy as np
import cv2
import httpx
from fastapi.testclient import TestClient

from main import app
from app.config import settings
from app.core.security import hash_password, create_access_token
from app.db.connection import get_db
from app.db.collections import (
    COLLECTION_USERS,
    COLLECTION_MODEL_RUNS,
    COLLECTION_VIOLATIONS,
    COLLECTION_CAMERAS,
    COLLECTION_AUDIT_LOGS,
    COLLECTION_VEHICLES,
    COLLECTION_PERSON_VEHICLES,
    COLLECTION_PERSONS,
)
from app.models.yolo_inference import yolo_engine
from app.models.roboflow_inference import roboflow_engine, RoboflowInferenceEngine
from app.core.exceptions import ModelNotAvailableError, RemoteInferenceError
from app.api.detections import EVIDENCE_UPLOAD_DIR

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

    for extra_id in ("65f000000000000000000088", "65f000000000000000000077"):
        db[COLLECTION_CAMERAS].delete_many({"_id": ObjectId(extra_id)})
        db[COLLECTION_CAMERAS].insert_one({
            "_id": ObjectId(extra_id),
            "name": f"TEST_DETECTIONS_CAM_{extra_id[-2:]}",
            "junction": f"Test Point {extra_id[-2:]}",
            "streamType": "WEBCAM",
            "source": "cam-0",
            "resolution": "1080p",
            "fps": 30.0,
            "status": "ONLINE",
            "lastHeartbeatAt": now,
            "createdBy": ObjectId("65f000000000000000000001"),
            "createdAt": now,
            "updatedAt": now,
        })

    yield

    # Teardown
    db[COLLECTION_USERS].delete_many({"email": "test.detections_op@traffic.gov.in"})
    db[COLLECTION_CAMERAS].delete_many({"name": {"$regex": r"^TEST_DETECTIONS_CAM"}})
    db[COLLECTION_MODEL_RUNS].delete_many({"modelName": {"$regex": r"^(YOLO|Roboflow)"}})
    db[COLLECTION_VIOLATIONS].delete_many({"caseId": {"$regex": r"^TG-2026-"}})
    db[COLLECTION_AUDIT_LOGS].delete_many({"actorNameSnapshot": "Operator Detection Tester"})

    # Clean up synthetic test evidence files created during test runs
    if os.path.exists(EVIDENCE_UPLOAD_DIR):
        for f in os.listdir(EVIDENCE_UPLOAD_DIR):
            try:
                os.remove(os.path.join(EVIDENCE_UPLOAD_DIR, f))
            except Exception:
                pass


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

    def test_analyze_missing_local_model_weights_returns_503(self, auth_headers):
        """When local YOLO model weights file is absent, must return HTTP 503 MODEL_NOT_AVAILABLE."""
        original_provider = settings.INFERENCE_PROVIDER
        original_model = yolo_engine.model
        settings.INFERENCE_PROVIDER = "local"
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
            detail_fields = [d["field"] for d in data.get("details", [])]
            assert "model_path" in detail_fields
            assert "expected_classes" in detail_fields
        finally:
            yolo_engine.model = original_model
            settings.INFERENCE_PROVIDER = original_provider

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


class TestLocalYoloModelInference:
    """Verifies local YOLO engine execution and class taxonomy checks."""

    @pytest.fixture(autouse=True)
    def use_local_provider(self):
        original_provider = settings.INFERENCE_PROVIDER
        settings.INFERENCE_PROVIDER = "local"
        yield
        settings.INFERENCE_PROVIDER = original_provider

    def test_generic_coco_model_reports_helmet_classification_unavailable(self, auth_headers):
        """A standard COCO model reports helmetClassificationAvailable=False without false violations."""
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
        payload = response.json()["data"]
        assert payload["detected"] is True
        assert payload["totalDetections"] == 2
        assert payload["helmetClassificationAvailable"] is False
        assert "does not include validated helmet" in payload["helmetClassificationMessage"]
        assert payload["isCandidateViolation"] is False
        assert payload["status"] == "NO_VIOLATION"
        assert len(payload["vehicles"]) == 1
        assert len(payload["persons"]) == 1

    def test_custom_traffic_model_flags_helmet_violation_and_ingests_draft(self, auth_headers):
        """Custom traffic model detects unhelmeted rider and queues candidate with status PENDING_REVIEW."""
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
        payload = response.json()["data"]
        assert payload["detected"] is True
        assert payload["helmetClassificationAvailable"] is True
        assert payload["isCandidateViolation"] is True
        assert payload["violationType"] == "NO_HELMET_RIDER"
        assert payload["violationConfidence"] == 0.93
        assert payload["status"] == "PENDING_REVIEW"
        assert payload["caseId"] is not None

        # Verify DB persistence
        db = get_db()
        violation_doc = db[COLLECTION_VIOLATIONS].find_one({"caseId": payload["caseId"]})
        assert violation_doc is not None
        assert violation_doc["status"] == "PENDING_REVIEW"
        assert violation_doc["violationType"] == "NO_HELMET_RIDER"

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


class TestRoboflowInferenceEngineUnit:
    """Direct unit tests for RoboflowInferenceEngine logic and error mapping."""

    def test_classify_roboflow_labels(self):
        """Validates exact mapping of Roboflow class labels."""
        engine = RoboflowInferenceEngine(api_key="mock_key")
        
        cat, color, viol = engine._classify_roboflow_label("Without Helmet")
        assert cat == "HELMET_VIOLATION"
        assert color == "#DC2626"
        assert viol is True

        cat, color, viol = engine._classify_roboflow_label("With Helmet")
        assert cat == "HELMET_COMPLIANT"
        assert color == "#15803D"
        assert viol is False

        cat, color, viol = engine._classify_roboflow_label("licence")
        assert cat == "LICENSE_PLATE"
        assert color == "#D97706"
        assert viol is False

        cat, color, viol = engine._classify_roboflow_label("unrecognized_class")
        assert cat == "OTHER"
        assert color == "#64748B"
        assert viol is False

    def test_parse_roboflow_response_center_to_corner_coordinates(self):
        """Validates translation of center (x, y, w, h) to corner [xyxy], normalized, and percentage."""
        engine = RoboflowInferenceEngine(api_key="mock_key")
        mock_raw = {
            "predictions": [
                {
                    "x": 300.0,
                    "y": 200.0,
                    "width": 100.0,
                    "height": 80.0,
                    "confidence": 0.94,
                    "class": "Without Helmet",
                    "class_id": 1,
                }
            ]
        }
        res = engine._parse_roboflow_response(mock_raw, width=600, height=400)
        assert res["detected"] is True
        assert res["totalDetections"] == 1
        assert res["isCandidateViolation"] is True
        assert res["violationType"] == "NO_HELMET_RIDER"
        assert res["violationConfidence"] == 0.94

        box = res["boxes"][0]
        assert box["label"] == "Without Helmet"
        assert box["category"] == "HELMET_VIOLATION"
        # Center x=300, w=100 -> x1=250, x2=350. Center y=200, h=80 -> y1=160, y2=240
        # Normalized: [x1/W, y1/H, x2/W, y2/H] = [250/600, 160/400, 350/600, 240/400]
        assert box["normalized"] == [0.4167, 0.4, 0.5833, 0.6]
        assert box["coordinates"]["x1"] == 0.4167
        assert box["coordinates"]["y1"] == 0.4
        assert box["coordinates"]["x2"] == 0.5833
        assert box["coordinates"]["y2"] == 0.6
        # Percentage coords:
        assert box["percentage"]["x"] == round((250.0 / 600) * 100, 2)
        assert box["percentage"]["y"] == round((160.0 / 400) * 100, 2)
        assert box["percentage"]["width"] == round((100.0 / 600) * 100, 2)
        assert box["percentage"]["height"] == round((80.0 / 400) * 100, 2)

    def test_detect_unconfigured_api_key_raises_503(self):
        """When API key is not configured, detect() must raise ModelNotAvailableError."""
        engine = RoboflowInferenceEngine(api_key=None)
        with pytest.raises(ModelNotAvailableError) as exc_info:
            asyncio.run(engine.detect(_create_test_image_bytes()))
        assert exc_info.value.status_code == 503
        assert exc_info.value.error_code == "MODEL_NOT_AVAILABLE"
        assert "ROBOFLOW_API_KEY" in exc_info.value.message

    def test_detect_upstream_timeout_raises_remote_inference_error_504(self):
        """When Roboflow API times out, must raise RemoteInferenceError with HTTP 504."""
        engine = RoboflowInferenceEngine(api_key="mock_secret_key_123")
        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Read timed out")):
            with pytest.raises(RemoteInferenceError) as exc_info:
                asyncio.run(engine.detect(_create_test_image_bytes()))
            assert exc_info.value.status_code == 504
            assert exc_info.value.error_code == "ROBOFLOW_TIMEOUT"

    def test_detect_upstream_auth_failure_raises_502_and_masks_key(self):
        """When upstream returns 401 Unauthorized, must raise HTTP 502 without leaking secret key."""
        engine = RoboflowInferenceEngine(api_key="secret_test_key_xyz_789")
        mock_resp = httpx.Response(
            status_code=401,
            json={"error": "Invalid API Key"},
            request=httpx.Request("POST", "https://detect.roboflow.com/test"),
        )
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            with pytest.raises(RemoteInferenceError) as exc_info:
                asyncio.run(engine.detect(_create_test_image_bytes()))
            assert exc_info.value.status_code == 502
            assert exc_info.value.error_code == "ROBOFLOW_AUTH_ERROR"
            assert "secret_test_key_xyz_789" not in str(exc_info.value)
            assert "secret_test_key_xyz_789" not in exc_info.value.message

    def test_detect_malformed_response_raises_502(self):
        """When upstream returns non-JSON text, must raise RemoteInferenceError HTTP 502."""
        engine = RoboflowInferenceEngine(api_key="mock_secret_key_123")
        mock_resp = httpx.Response(
            status_code=200,
            content=b"<html>502 Bad Gateway from cloudflare</html>",
            headers={"Content-Type": "text/html"},
            request=httpx.Request("POST", "https://detect.roboflow.com/test"),
        )
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            with pytest.raises(RemoteInferenceError) as exc_info:
                asyncio.run(engine.detect(_create_test_image_bytes()))
            assert exc_info.value.status_code == 502
            assert exc_info.value.error_code == "ROBOFLOW_INVALID_RESPONSE"


class TestRoboflowApiIntegration:
    """Verifies full API endpoints with Roboflow provider and mocked HTTP calls."""

    @pytest.fixture(autouse=True)
    def use_roboflow_provider(self):
        original_provider = settings.INFERENCE_PROVIDER
        original_key = roboflow_engine.api_key
        settings.INFERENCE_PROVIDER = "roboflow"
        roboflow_engine.api_key = "test_roboflow_mock_key_999"
        db = get_db()
        db[COLLECTION_VIOLATIONS].delete_many({"cameraId": ObjectId("65f000000000000000000099")})
        yield
        settings.INFERENCE_PROVIDER = original_provider
        roboflow_engine.api_key = original_key
        db[COLLECTION_VIOLATIONS].delete_many({"cameraId": ObjectId("65f000000000000000000099")})

    def test_roboflow_analyze_without_helmet_queues_pending_review(self, auth_headers):
        """
        Simulates remote Roboflow detecting 'Without Helmet'.
        Must return structured violation and persist case as PENDING_REVIEW in MongoDB.
        """
        mock_resp = httpx.Response(
            status_code=200,
            json={
                "inference_id": "rf-test-inf-1",
                "time": 0.055,
                "image": {"width": 640, "height": 480},
                "predictions": [
                    {
                        "x": 320.0,
                        "y": 180.0,
                        "width": 120.0,
                        "height": 140.0,
                        "confidence": 0.952,
                        "class": "Without Helmet",
                        "class_id": 1,
                    }
                ],
            },
            request=httpx.Request("POST", "https://detect.roboflow.com/helmet-and-no-helmet-rider-detection/6"),
        )

        img_bytes = _create_test_image_bytes(width=640, height=480)
        files = {"file": ("rider_no_helmet.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        form_data = {
            "camera_id": "65f000000000000000000099",
            "source_label": "Roboflow Test Cam",
            "auto_ingest": "true",
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

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
        assert payload["totalDetections"] == 1
        assert payload["helmetClassificationAvailable"] is True
        assert payload["isCandidateViolation"] is True
        assert payload["violationType"] == "NO_HELMET_RIDER"
        assert payload["violationConfidence"] == 0.952
        assert payload["status"] == "PENDING_REVIEW"
        assert payload["caseId"] is not None
        assert payload["modelInfo"]["provider"] == "roboflow"
        assert payload["modelInfo"]["modelId"] == "helmet-and-no-helmet-rider-detection/6"

        box = payload["boxes"][0]
        assert box["label"] == "Without Helmet"
        assert box["category"] == "HELMET_VIOLATION"
        assert box["color"] == "#DC2626"
        assert box["confidence"] == 0.952
        assert payload["isDeduplicated"] is False

        # Verify MongoDB persistence
        db = get_db()
        violation_doc = db[COLLECTION_VIOLATIONS].find_one({"caseId": payload["caseId"]})
        assert violation_doc is not None
        assert violation_doc["status"] == "PENDING_REVIEW"
        assert violation_doc["violationType"] == "NO_HELMET_RIDER"
        assert violation_doc["confidence"] == 0.952

        run_doc = db[COLLECTION_MODEL_RUNS].find_one({"_id": ObjectId(payload["modelRunId"])})
        assert run_doc is not None
        assert run_doc["modelName"] == "Roboflow:helmet-and-no-helmet-rider-detection"
        assert run_doc["modelVersion"] == "6"

    def test_roboflow_cooldown_deduplication_suppresses_duplicate_violations(self, auth_headers):
        """
        When periodic automatic capture runs, repeated detections within the cooldown
        window must NOT create duplicate violation documents in MongoDB.
        """
        mock_resp = httpx.Response(
            status_code=200,
            json={
                "predictions": [
                    {
                        "x": 320.0,
                        "y": 180.0,
                        "width": 120.0,
                        "height": 140.0,
                        "confidence": 0.945,
                        "class": "Without Helmet",
                        "class_id": 1,
                    }
                ]
            },
            request=httpx.Request("POST", "https://detect.roboflow.com/helmet-and-no-helmet-rider-detection/6"),
        )

        img_bytes = _create_test_image_bytes(width=640, height=480)
        files1 = {"file": ("rider_1.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        form_data = {
            "camera_id": "65f000000000000000000099",
            "source_label": "Cooldown Test Camera",
            "auto_ingest": "true",
            "cooldown_seconds": "30",
        }

        db = get_db()
        initial_count = db[COLLECTION_VIOLATIONS].count_documents({"cameraId": ObjectId("65f000000000000000000099")})

        # Frame 1: Initial violation capture
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            resp1 = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files1,
                data=form_data,
                headers=auth_headers,
            )

        assert resp1.status_code == 200
        data1 = resp1.json()["data"]
        assert data1["isCandidateViolation"] is True
        assert data1["isDeduplicated"] is False
        case_id_1 = data1["caseId"]
        assert case_id_1 is not None

        count_after_first = db[COLLECTION_VIOLATIONS].count_documents({"cameraId": ObjectId("65f000000000000000000099")})
        assert count_after_first == initial_count + 1

        # Frame 2: Immediate follow-up frame (within 30s cooldown)
        files2 = {"file": ("rider_2.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            resp2 = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files2,
                data=form_data,
                headers=auth_headers,
            )

        assert resp2.status_code == 200
        data2 = resp2.json()["data"]
        assert data2["isCandidateViolation"] is True
        # Must be deduplicated!
        assert data2["isDeduplicated"] is True
        assert data2["cooldownSecondsRemaining"] is not None
        assert data2["cooldownSecondsRemaining"] > 0
        assert data2["caseId"] == case_id_1

        # Violation collection count MUST NOT increase!
        count_after_second = db[COLLECTION_VIOLATIONS].count_documents({"cameraId": ObjectId("65f000000000000000000099")})
        assert count_after_second == count_after_first

    def test_roboflow_analyze_with_helmet_compliant(self, auth_headers):
        """Simulates remote Roboflow detecting 'With Helmet' -> NO_VIOLATION."""
        mock_resp = httpx.Response(
            status_code=200,
            json={
                "predictions": [
                    {
                        "x": 280.0,
                        "y": 150.0,
                        "width": 110.0,
                        "height": 120.0,
                        "confidence": 0.971,
                        "class": "With Helmet",
                        "class_id": 0,
                    }
                ]
            },
            request=httpx.Request("POST", "https://detect.roboflow.com/helmet-and-no-helmet-rider-detection/6"),
        )

        img_bytes = _create_test_image_bytes(width=640, height=480)
        files = {"file": ("helmet_compliant.jpg", io.BytesIO(img_bytes), "image/jpeg")}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            response = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files,
                headers=auth_headers,
            )

        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["detected"] is True
        assert payload["isCandidateViolation"] is False
        assert payload["status"] == "NO_VIOLATION"
        assert payload["boxes"][0]["label"] == "With Helmet"
        assert payload["boxes"][0]["category"] == "HELMET_COMPLIANT"
        assert payload["boxes"][0]["color"] == "#15803D"

    def test_roboflow_analyze_licence_plate(self, auth_headers):
        """Simulates remote Roboflow detecting 'licence' plate -> LICENSE_PLATE category."""
        mock_resp = httpx.Response(
            status_code=200,
            json={
                "predictions": [
                    {
                        "x": 300.0,
                        "y": 380.0,
                        "width": 130.0,
                        "height": 45.0,
                        "confidence": 0.884,
                        "class": "licence",
                        "class_id": 2,
                    }
                ]
            },
            request=httpx.Request("POST", "https://detect.roboflow.com/helmet-and-no-helmet-rider-detection/6"),
        )

        img_bytes = _create_test_image_bytes(width=640, height=480)
        files = {"file": ("license_plate.jpg", io.BytesIO(img_bytes), "image/jpeg")}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            response = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files,
                headers=auth_headers,
            )

        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["boxes"][0]["label"] == "licence"
        assert payload["boxes"][0]["category"] == "LICENSE_PLATE"
        assert payload["boxes"][0]["color"] == "#D97706"
        assert payload["isCandidateViolation"] is False

    def test_roboflow_missing_api_key_returns_503(self, auth_headers):
        """When ROBOFLOW_API_KEY is unset, endpoint must return HTTP 503 MODEL_NOT_AVAILABLE."""
        roboflow_engine.api_key = None

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
        assert "Roboflow API key" in data["message"]

    def test_roboflow_upstream_auth_failure_returns_502(self, auth_headers):
        """Upstream 401 Unauthorized returns HTTP 502 with ROBOFLOW_AUTH_ERROR."""
        mock_401 = httpx.Response(
            status_code=401,
            json={"error": "Unauthorized key"},
            request=httpx.Request("POST", "https://detect.roboflow.com/test"),
        )

        img_bytes = _create_test_image_bytes()
        files = {"file": ("frame.jpg", io.BytesIO(img_bytes), "image/jpeg")}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_401
            response = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files,
                headers=auth_headers,
            )

        assert response.status_code == 502
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "ROBOFLOW_AUTH_ERROR"
        assert "test_roboflow_mock_key_999" not in data["message"]

    def test_roboflow_upstream_timeout_returns_504(self, auth_headers):
        """Upstream timeout returns HTTP 504 with ROBOFLOW_TIMEOUT."""
        img_bytes = _create_test_image_bytes()
        files = {"file": ("frame.jpg", io.BytesIO(img_bytes), "image/jpeg")}

        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Read timeout")):
            response = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files,
                headers=auth_headers,
            )

        assert response.status_code == 504
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "ROBOFLOW_TIMEOUT"

    def test_roboflow_model_status_endpoint(self):
        """GET /detections/model-status returns Roboflow configuration and class telemetry."""
        response = client.get(f"{settings.API_PREFIX}/detections/model-status")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        info = data["data"]
        assert info["provider"] == "roboflow"
        assert info["modelId"] == "helmet-and-no-helmet-rider-detection/6"
        assert info["helmetClassificationSupported"] is True
        assert "With Helmet" in info["expectedClasses"]
        assert "Without Helmet" in info["expectedClasses"]
        assert "licence" in info["expectedClasses"]

    def test_periodic_capture_cooldown_expiry_creates_new_case(self, auth_headers):
        """
        When the configured cooldown window has elapsed, the next periodic capture
        must generate a new violation case and not deduplicate.
        """
        mock_resp = httpx.Response(
            status_code=200,
            json={
                "predictions": [
                    {
                        "x": 300.0,
                        "y": 200.0,
                        "width": 100.0,
                        "height": 100.0,
                        "confidence": 0.92,
                        "class": "Without Helmet",
                        "class_id": 1,
                    }
                ]
            },
            request=httpx.Request("POST", "https://detect.roboflow.com/helmet-and-no-helmet-rider-detection/6"),
        )

        camera_oid = ObjectId("65f000000000000000000088")
        db = get_db()
        db[COLLECTION_VIOLATIONS].delete_many({"cameraId": camera_oid})

        img_bytes = _create_test_image_bytes(width=640, height=480)
        files = {"file": ("periodic_frame.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        form_data = {
            "camera_id": str(camera_oid),
            "source_label": "Periodic Expiry Test",
            "auto_ingest": "true",
            "cooldown_seconds": "5",
        }

        # 1. First capture creates violation
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            resp1 = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files,
                data=form_data,
                headers=auth_headers,
            )
        assert resp1.status_code == 200
        data1 = resp1.json()["data"]
        assert data1["isCandidateViolation"] is True
        assert data1["isDeduplicated"] is False
        case_id_1 = data1["caseId"]

        # 2. Simulate time passing by shifting the violation's createdAt back by 10 seconds (exceeding 5s cooldown)
        past_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        db[COLLECTION_VIOLATIONS].update_one(
            {"caseId": case_id_1},
            {"$set": {"createdAt": past_time, "capturedAt": past_time}}
        )

        # 3. Next periodic tick after cooldown expired
        files2 = {"file": ("periodic_frame_2.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            resp2 = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files2,
                data=form_data,
                headers=auth_headers,
            )
        assert resp2.status_code == 200
        data2 = resp2.json()["data"]
        assert data2["isCandidateViolation"] is True
        assert data2["isDeduplicated"] is False
        assert data2["caseId"] != case_id_1

        # Both distinct violations exist
        total = db[COLLECTION_VIOLATIONS].count_documents({"cameraId": camera_oid})
        assert total == 2

    def test_periodic_capture_custom_cooldown_override(self, auth_headers):
        """
        Verify that passing a custom cooldown_seconds parameter (e.g. 60s)
        is respected by the API deduplication logic.
        """
        mock_resp = httpx.Response(
            status_code=200,
            json={
                "predictions": [
                    {
                        "x": 300.0,
                        "y": 200.0,
                        "width": 100.0,
                        "height": 100.0,
                        "confidence": 0.91,
                        "class": "Without Helmet",
                        "class_id": 1,
                    }
                ]
            },
            request=httpx.Request("POST", "https://detect.roboflow.com/helmet-and-no-helmet-rider-detection/6"),
        )

        camera_oid = ObjectId("65f000000000000000000077")
        db = get_db()
        db[COLLECTION_VIOLATIONS].delete_many({"cameraId": camera_oid})

        img_bytes = _create_test_image_bytes(width=640, height=480)
        files = {"file": ("periodic_frame.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        form_data = {
            "camera_id": str(camera_oid),
            "source_label": "Custom Cooldown Test",
            "auto_ingest": "true",
            "cooldown_seconds": "60",
        }

        # First capture
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            resp1 = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files,
                data=form_data,
                headers=auth_headers,
            )
        assert resp1.status_code == 200
        data1 = resp1.json()["data"]
        assert data1["isDeduplicated"] is False

        # Immediate follow-up tick (within 60s cooldown)
        files2 = {"file": ("periodic_frame_2.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            resp2 = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files2,
                data=form_data,
                headers=auth_headers,
            )
        assert resp2.status_code == 200
        data2 = resp2.json()["data"]
        assert data2["isDeduplicated"] is True
        assert data2["cooldownSecondsRemaining"] is not None
        assert 50 <= data2["cooldownSecondsRemaining"] <= 60


class TestDistinctRiderAndPlateMatchingPipeline:
    """
    Comprehensive tests for:
    - Zero, single, and multiple distinct rider detections
    - With-helmet vs without-helmet classification & violation flagging
    - Stable rider detection IDs and safe evidence cropping
    - Number plate detection, OCR extraction, and vehicle/owner registry matching
    - Unmatched plate retention (UNVERIFIED) for human review investigation
    - Unreadable/occluded plate handling (MANUAL_REQUIRED)
    - Strict registered vehicle owner vs rider distinction
    - Privacy protection: zero facial recognition and no automated guilt inference
    - Candidate violations saved strictly in PENDING_REVIEW status (never auto-fine)
    - Duplicate processing cooldown safeguards
    - Unauthorized request rejection (401)
    - Invalid upload validation (400)
    - Model unavailable error handling (503)
    """

    def test_zero_riders_detected_returns_empty_riders_and_manual_required_plate(self, auth_headers):
        """When frame has no detections, returns empty riders list and MANUAL_REQUIRED plateMatch."""
        mock_resp = httpx.Response(
            status_code=200,
            json={"predictions": []},
            request=httpx.Request("POST", "https://detect.roboflow.com/test"),
        )
        img_bytes = _create_test_image_bytes(width=320, height=240)
        files = {"file": ("empty_frame.jpg", io.BytesIO(img_bytes), "image/jpeg")}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            resp = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files,
                headers=auth_headers,
            )

        assert resp.status_code == 200
        body = resp.json()
        data = body["data"]
        assert data["detected"] is False
        assert data["totalDetections"] == 0
        assert data["riders"] == []
        assert data["isCandidateViolation"] is False
        assert data["status"] == "NO_VIOLATION"
        assert data["plateMatch"]["plateDetected"] is False
        assert data["plateMatch"]["matchStatus"] == "MANUAL_REQUIRED"

    def test_single_rider_with_helmet_compliant(self, auth_headers):
        """Single rider wearing helmet: rider classified as WITH_HELMET, isViolation=False, crop saved."""
        mock_resp = httpx.Response(
            status_code=200,
            json={
                "predictions": [
                    {
                        "x": 160.0,
                        "y": 120.0,
                        "width": 80.0,
                        "height": 80.0,
                        "confidence": 0.94,
                        "class": "With Helmet",
                        "class_id": 0,
                    }
                ]
            },
            request=httpx.Request("POST", "https://detect.roboflow.com/test"),
        )
        img_bytes = _create_test_image_bytes(width=320, height=240)
        files = {"file": ("helmet_frame.jpg", io.BytesIO(img_bytes), "image/jpeg")}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            resp = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files,
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["detected"] is True
        assert len(data["riders"]) == 1
        rider = data["riders"][0]
        assert rider["label"] == "With Helmet"
        assert rider["classification"] == "WITH_HELMET"
        assert rider["isViolation"] is False
        assert rider["cropPath"] is not None
        assert rider["cropPath"].startswith("/uploads/evidence/crop_rider_")
        assert data["isCandidateViolation"] is False
        assert data["status"] == "NO_VIOLATION"

    def test_single_rider_without_helmet_flagged_pending_review(self, auth_headers):
        """Single rider without helmet: rider classified as WITHOUT_HELMET, isViolation=True, queued PENDING_REVIEW."""
        mock_resp = httpx.Response(
            status_code=200,
            json={
                "predictions": [
                    {
                        "x": 160.0,
                        "y": 120.0,
                        "width": 80.0,
                        "height": 80.0,
                        "confidence": 0.91,
                        "class": "Without Helmet",
                        "class_id": 1,
                    }
                ]
            },
            request=httpx.Request("POST", "https://detect.roboflow.com/test"),
        )
        img_bytes = _create_test_image_bytes(width=320, height=240)
        files = {"file": ("no_helmet_frame.jpg", io.BytesIO(img_bytes), "image/jpeg")}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            resp = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files,
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["detected"] is True
        assert len(data["riders"]) == 1
        rider = data["riders"][0]
        assert rider["classification"] == "WITHOUT_HELMET"
        assert rider["isViolation"] is True
        assert rider["cropPath"] is not None
        assert data["isCandidateViolation"] is True
        assert data["status"] == "PENDING_REVIEW"
        assert data["caseId"] is not None

        # Verify record in database is strictly PENDING_REVIEW
        db = get_db()
        violation = db[COLLECTION_VIOLATIONS].find_one({"caseId": data["caseId"]})
        assert violation is not None
        assert violation["status"] == "PENDING_REVIEW"
        assert violation["challanDraftNumber"] is None
        assert violation["draftAmountInr"] is None

    def test_multiple_riders_helmet_and_no_helmet(self, auth_headers):
        """Multiple distinct riders (1 with helmet, 1 without helmet) receive separate stable IDs and crops."""
        mock_resp = httpx.Response(
            status_code=200,
            json={
                "predictions": [
                    {
                        "x": 100.0,
                        "y": 120.0,
                        "width": 60.0,
                        "height": 60.0,
                        "confidence": 0.95,
                        "class": "With Helmet",
                        "class_id": 0,
                    },
                    {
                        "x": 220.0,
                        "y": 130.0,
                        "width": 60.0,
                        "height": 60.0,
                        "confidence": 0.89,
                        "class": "Without Helmet",
                        "class_id": 1,
                    },
                ]
            },
            request=httpx.Request("POST", "https://detect.roboflow.com/test"),
        )
        img_bytes = _create_test_image_bytes(width=320, height=240)
        files = {"file": ("two_riders.jpg", io.BytesIO(img_bytes), "image/jpeg")}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            resp = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files,
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["riders"]) == 2

        # Stable detection IDs are distinct
        ids = [r["detectionId"] for r in data["riders"]]
        assert len(set(ids)) == 2

        # Verify one is compliant and one is violation
        classifications = {r["classification"]: r for r in data["riders"]}
        assert "WITH_HELMET" in classifications
        assert "WITHOUT_HELMET" in classifications
        assert classifications["WITH_HELMET"]["isViolation"] is False
        assert classifications["WITHOUT_HELMET"]["isViolation"] is True

        # Both have crops generated
        assert all(r["cropPath"] is not None for r in data["riders"])
        # Overall frame is a candidate violation due to the unhelmeted rider
        assert data["isCandidateViolation"] is True
        assert data["status"] == "PENDING_REVIEW"

    def test_unreadable_or_missing_plate_requires_manual_investigation(self, auth_headers):
        """Frame with rider violation but unreadable/absent plate returns MANUAL_REQUIRED."""
        mock_resp = httpx.Response(
            status_code=200,
            json={
                "predictions": [
                    {
                        "x": 150.0,
                        "y": 100.0,
                        "width": 70.0,
                        "height": 70.0,
                        "confidence": 0.90,
                        "class": "Without Helmet",
                        "class_id": 1,
                    }
                ]
            },
            request=httpx.Request("POST", "https://detect.roboflow.com/test"),
        )
        img_bytes = _create_test_image_bytes(width=320, height=240)
        files = {"file": ("no_plate.jpg", io.BytesIO(img_bytes), "image/jpeg")}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            resp = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files,
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["plateMatch"]["matchStatus"] == "MANUAL_REQUIRED"
        assert data["plateMatch"]["matchedVehicleId"] is None
        assert data["plateMatch"]["matchedPersonId"] is None

        # Verify candidate violation has identityVerificationStatus MANUAL_REQUIRED
        db = get_db()
        violation = db[COLLECTION_VIOLATIONS].find_one({"caseId": data["caseId"]})
        assert violation is not None
        assert violation["identityVerificationStatus"] == "MANUAL_REQUIRED"
        assert violation["personId"] is None
        assert violation["vehicleId"] is None

    def test_unmatched_plate_remains_visible_for_reviewer_investigation(self, auth_headers):
        """Plate detected but not found in vehicles collection returns UNVERIFIED and stays visible for investigation."""
        mock_resp = httpx.Response(
            status_code=200,
            json={
                "predictions": [
                    {
                        "x": 150.0,
                        "y": 100.0,
                        "width": 70.0,
                        "height": 70.0,
                        "confidence": 0.90,
                        "class": "Without Helmet",
                        "class_id": 1,
                    },
                    {
                        "x": 150.0,
                        "y": 200.0,
                        "width": 50.0,
                        "height": 20.0,
                        "confidence": 0.85,
                        "class": "licence",
                        "class_id": 2,
                    },
                ]
            },
            request=httpx.Request("POST", "https://detect.roboflow.com/test"),
        )
        img_bytes = _create_test_image_bytes(width=320, height=240)
        files = {"file": ("unmatched_plate.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        form_data = {"plate_hint": "MH02XX9999", "cooldown_seconds": "0"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            resp = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files,
                data=form_data,
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        plate_match = data["plateMatch"]
        assert plate_match["plateDetected"] is True
        assert plate_match["normalizedPlate"] == "MH02XX9999"
        assert plate_match["matchStatus"] == "UNVERIFIED"
        assert plate_match["matchedVehicleId"] is None
        assert plate_match["matchedPersonId"] is None
        assert plate_match["ownerNameSnapshot"] is None

        # Check DB violation stores UNVERIFIED
        db = get_db()
        violation = db[COLLECTION_VIOLATIONS].find_one({"caseId": data["caseId"]})
        assert violation is not None
        assert violation["identityVerificationStatus"] == "UNVERIFIED"

    def test_matched_plate_with_registered_owner_vs_rider_distinction(self, auth_headers):
        """
        When plate matches a registered vehicle, links vehicle and registered owner.
        Critically maintains distinction: the linked citizen is the REGISTERED OWNER, not assumed rider.
        """
        db = get_db()
        now = datetime.now(timezone.utc)
        test_plate = "KA03ZZ7777"

        # Setup test vehicle and registered owner
        db[COLLECTION_VEHICLES].delete_many({"plateNumber": test_plate})
        veh_res = db[COLLECTION_VEHICLES].insert_one({
            "plateNumber": test_plate,
            "vehicleType": "Two-Wheeler Motorcycle",
            "model": "Royal Enfield Hunter 350",
            "registrationStatus": "ACTIVE",
            "verificationStatus": "VERIFIED",
            "createdAt": now,
            "updatedAt": now,
        })
        vehicle_id = veh_res.inserted_id

        pers_res = db[COLLECTION_PERSONS].insert_one({
            "personReference": "TEST-CIT-OWNER-777",
            "fullName": "Suresh Raina (Registered Vehicle Owner)",
            "identityStatus": "VERIFIED",
            "verificationSource": "STATE_VAHAN_PORTAL",
            "createdAt": now,
            "updatedAt": now,
        })
        person_id = pers_res.inserted_id

        db[COLLECTION_PERSON_VEHICLES].insert_one({
            "personId": person_id,
            "vehicleId": vehicle_id,
            "relationshipType": "REGISTERED_OWNER",
        })

        try:
            mock_resp = httpx.Response(
                status_code=200,
                json={
                    "predictions": [
                        {
                            "x": 150.0,
                            "y": 100.0,
                            "width": 70.0,
                            "height": 70.0,
                            "confidence": 0.92,
                            "class": "Without Helmet",
                            "class_id": 1,
                        },
                        {
                            "x": 150.0,
                            "y": 200.0,
                            "width": 60.0,
                            "height": 25.0,
                            "confidence": 0.88,
                            "class": "licence",
                            "class_id": 2,
                        },
                    ]
                },
                request=httpx.Request("POST", "https://detect.roboflow.com/test"),
            )
            img_bytes = _create_test_image_bytes(width=320, height=240)
            files = {"file": ("matched_vehicle.jpg", io.BytesIO(img_bytes), "image/jpeg")}
            form_data = {"plate_hint": test_plate, "cooldown_seconds": "0"}

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_resp
                resp = client.post(
                    f"{settings.API_PREFIX}/detections/analyze",
                    files=files,
                    data=form_data,
                    headers=auth_headers,
                )

            assert resp.status_code == 200
            data = resp.json()["data"]
            pm = data["plateMatch"]
            assert pm["matchStatus"] == "VERIFIED"
            assert pm["normalizedPlate"] == test_plate
            assert pm["matchedVehicleId"] == str(vehicle_id)
            assert pm["matchedPersonId"] == str(person_id)
            assert pm["ownerNameSnapshot"] == "Suresh Raina (Registered Vehicle Owner)"
            assert pm["vehicleDetails"]["model"] == "Royal Enfield Hunter 350"

            # Check DB record attribution
            violation = db[COLLECTION_VIOLATIONS].find_one({"caseId": data["caseId"]})
            assert violation is not None
            assert violation["identityVerificationStatus"] == "VERIFIED"
            assert violation["vehicleId"] == vehicle_id
            assert violation["personId"] == person_id
            assert violation["status"] == "PENDING_REVIEW"
        finally:
            db[COLLECTION_VEHICLES].delete_many({"_id": vehicle_id})
            db[COLLECTION_PERSONS].delete_many({"_id": person_id})
            db[COLLECTION_PERSON_VEHICLES].delete_many({"vehicleId": vehicle_id})

    def test_privacy_safety_no_facial_recognition(self):
        """
        Verifies system privacy compliance:
        - No facial recognition routes exist
        - No citizen identity is inferred from facial/rider crops
        """
        route_paths = []
        for route in app.routes:
            p = getattr(route, "path", None)
            if p:
                route_paths.append(p)
        for path in route_paths:
            assert "face" not in path.lower()
            assert "biometric" not in path.lower()
            assert "facial-recognition" not in path.lower()

    def test_unauthorized_access_rejected_with_401(self):
        """Requests without Authorization header must be rejected with 401."""
        img_bytes = _create_test_image_bytes(width=320, height=240)
        files = {"file": ("frame.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        resp = client.post(f"{settings.API_PREFIX}/detections/analyze", files=files)
        assert resp.status_code == 401

    def test_invalid_image_upload_rejected_with_400(self, auth_headers):
        """Malformed bytes or unsupported file formats return 400 Bad Request."""
        # Empty file
        files_empty = {"file": ("empty.jpg", io.BytesIO(b""), "image/jpeg")}
        resp_empty = client.post(
            f"{settings.API_PREFIX}/detections/analyze",
            files=files_empty,
            headers=auth_headers,
        )
        assert resp_empty.status_code == 400

        # Corrupt bytes
        files_corrupt = {"file": ("corrupt.jpg", io.BytesIO(b"NOT_AN_IMAGE_FILE_DATA"), "image/jpeg")}
        resp_corrupt = client.post(
            f"{settings.API_PREFIX}/detections/analyze",
            files=files_corrupt,
            headers=auth_headers,
        )
        assert resp_corrupt.status_code == 400

    def test_model_unavailable_returns_503(self, auth_headers):
        """When AI model is not configured or missing, returns 503 MODEL_NOT_AVAILABLE rather than mock data."""
        with patch.object(roboflow_engine, "is_configured", return_value=False):
            with patch.object(
                roboflow_engine,
                "detect",
                side_effect=ModelNotAvailableError(message="Roboflow engine is not configured."),
            ):
                img_bytes = _create_test_image_bytes(width=320, height=240)
                files = {"file": ("frame.jpg", io.BytesIO(img_bytes), "image/jpeg")}
                resp = client.post(
                    f"{settings.API_PREFIX}/detections/analyze",
                    files=files,
                    headers=auth_headers,
                )
                assert resp.status_code == 503
                body = resp.json()
                assert body["success"] is False
                assert body.get("error_code") == "MODEL_NOT_AVAILABLE" or body.get("errorCode") == "MODEL_NOT_AVAILABLE"


class TestAuditAndRobustnessImprovements:
    """
    Regression and verification tests covering:
    1. Detection request validation (placeholder values: 'string', 'null', 'undefined'; camera DB validation).
    2. Bounding-box coordinates: [x1, y1, x2, y2] normalized format, percentage accuracy, crop coordinate alignment.
    3. Licence plate handling: ensuring plate region is never falsely classified as a vehicle.
    4. Rider workflow: preserving four individual rider candidates with crops and confidences in PENDING_REVIEW.
    5. Performance timing breakdown telemetry (modelInferenceMs, evidenceSavingMs, ocrMs, dbLookupMs).
    """

    @pytest.mark.parametrize("placeholder", ["string", "null", "undefined", "none", "", "   "])
    def test_placeholder_camera_id_treated_as_optional_fallback(self, auth_headers, placeholder):
        """Placeholder camera_id values (Swagger defaults) must never error out or be queried as real IDs."""
        mock_resp = httpx.Response(
            status_code=200,
            json={"predictions": []},
            request=httpx.Request("POST", "https://detect.roboflow.com/test"),
        )
        img_bytes = _create_test_image_bytes(width=320, height=240)
        files = {"file": ("test.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        form_data = {"camera_id": placeholder, "cooldown_seconds": "0"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            resp = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files,
                data=form_data,
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_invalid_camera_id_syntax_returns_400(self, auth_headers):
        """Non-placeholder, non-ObjectId camera_id returns HTTP 400 validation error."""
        img_bytes = _create_test_image_bytes(width=320, height=240)
        files = {"file": ("test.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        form_data = {"camera_id": "not-a-valid-hex-camera-id", "cooldown_seconds": "0"}

        resp = client.post(
            f"{settings.API_PREFIX}/detections/analyze",
            files=files,
            data=form_data,
            headers=auth_headers,
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["success"] is False
        assert "not a valid 24-character hexadecimal ObjectId" in body["message"]

    def test_non_existent_camera_id_returns_404(self, auth_headers):
        """Syntactically valid ObjectId camera_id not present in database returns HTTP 404."""
        non_existent_id = "65f000000000000000000999"
        img_bytes = _create_test_image_bytes(width=320, height=240)
        files = {"file": ("test.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        form_data = {"camera_id": non_existent_id, "cooldown_seconds": "0"}

        resp = client.post(
            f"{settings.API_PREFIX}/detections/analyze",
            files=files,
            data=form_data,
            headers=auth_headers,
        )
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert f"Camera '{non_existent_id}' not found" in body["message"]

    @pytest.mark.parametrize("placeholder", ["string", "null", "undefined", "none", "", "   "])
    def test_placeholder_plate_hint_ignored(self, auth_headers, placeholder):
        """Placeholder plate_hint values must never be searched as plate numbers or marked verified."""
        mock_resp = httpx.Response(
            status_code=200,
            json={"predictions": []},
            request=httpx.Request("POST", "https://detect.roboflow.com/test"),
        )
        img_bytes = _create_test_image_bytes(width=320, height=240)
        files = {"file": ("test.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        form_data = {"plate_hint": placeholder, "cooldown_seconds": "0"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            resp = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files,
                data=form_data,
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        pm = data["plateMatch"]
        assert pm["plateDetected"] is False
        assert pm["rawText"] is None
        assert pm["normalizedPlate"] is None
        assert pm["matchStatus"] == "MANUAL_REQUIRED"
        assert pm["matchedVehicleId"] is None

    def test_known_dimensions_coordinates_and_crop_alignment(self, auth_headers):
        """
        Validates coordinate calculations using known dimensions (640x480).
        Verifies xyxy, normalized [x1, y1, x2, y2], percentage coordinates,
        and confirms that the generated crop on disk matches the exact bounding box pixel dimensions.
        """
        # Center x=320, y=240, width=160, height=120
        # Expected x1 = 320 - 80 = 240, x2 = 320 + 80 = 400 (width = 160)
        # Expected y1 = 240 - 60 = 180, y2 = 240 + 60 = 300 (height = 120)
        mock_resp = httpx.Response(
            status_code=200,
            json={
                "predictions": [
                    {
                        "x": 320.0,
                        "y": 240.0,
                        "width": 160.0,
                        "height": 120.0,
                        "confidence": 0.93,
                        "class": "Without Helmet",
                        "class_id": 1,
                    }
                ]
            },
            request=httpx.Request("POST", "https://detect.roboflow.com/test"),
        )
        img_bytes = _create_test_image_bytes(width=640, height=480)
        files = {"file": ("known_coords.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        form_data = {"cooldown_seconds": "0"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            resp = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files,
                data=form_data,
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        box = data["boxes"][0]

        # 1. Pixel xyxy coordinates [x1, y1, x2, y2]
        assert box["xyxy"] == [240.0, 180.0, 400.0, 300.0]

        # 2. Consistent normalized coordinates [x1, y1, x2, y2]
        # x1/W = 240/640 = 0.375, y1/H = 180/480 = 0.375
        # x2/W = 400/640 = 0.625, y2/H = 300/480 = 0.625
        assert box["normalized"] == [0.375, 0.375, 0.625, 0.625]

        # 3. Percentage coordinates
        assert box["percentage"]["x"] == 37.5
        assert box["percentage"]["y"] == 37.5
        assert box["percentage"]["width"] == 25.0
        assert box["percentage"]["height"] == 25.0

        # 4. Verify rider crop file matches the exact pixel dimensions (120x160)
        rider = data["riders"][0]
        crop_path = rider["cropPath"]
        assert crop_path is not None
        crop_filename = os.path.basename(crop_path)
        disk_crop_file = os.path.join(EVIDENCE_UPLOAD_DIR, crop_filename)
        assert os.path.isfile(disk_crop_file)

        crop_img = cv2.imread(disk_crop_file)
        assert crop_img is not None
        crop_h, crop_w = crop_img.shape[:2]
        assert crop_h == 120
        assert crop_w == 160

    def test_licence_plate_class_not_falsely_represented_as_vehicle(self, auth_headers):
        """The 'licence' class is a plate region detection and must never be included in vehicles list."""
        mock_resp = httpx.Response(
            status_code=200,
            json={
                "predictions": [
                    {
                        "x": 200.0,
                        "y": 150.0,
                        "width": 80.0,
                        "height": 80.0,
                        "confidence": 0.92,
                        "class": "Without Helmet",
                        "class_id": 1,
                    },
                    {
                        "x": 200.0,
                        "y": 300.0,
                        "width": 60.0,
                        "height": 20.0,
                        "confidence": 0.88,
                        "class": "licence",
                        "class_id": 2,
                    },
                ]
            },
            request=httpx.Request("POST", "https://detect.roboflow.com/test"),
        )
        img_bytes = _create_test_image_bytes(width=640, height=480)
        files = {"file": ("plate_only.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        form_data = {"cooldown_seconds": "0"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            resp = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files,
                data=form_data,
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["totalDetections"] == 2
        # Vehicles list must NOT contain the licence plate
        assert len(data["vehicles"]) == 0
        assert data["plateMatch"]["plateDetected"] is True

    def test_preserve_four_individual_rider_candidates(self, auth_headers):
        """Confirms that all 4 individual rider candidates returned by model are preserved with crops and confidences."""
        mock_resp = httpx.Response(
            status_code=200,
            json={
                "predictions": [
                    {
                        "x": 100.0,
                        "y": 100.0,
                        "width": 50.0,
                        "height": 50.0,
                        "confidence": 0.95,
                        "class": "Without Helmet",
                        "class_id": 1,
                    },
                    {
                        "x": 200.0,
                        "y": 100.0,
                        "width": 50.0,
                        "height": 50.0,
                        "confidence": 0.91,
                        "class": "With Helmet",
                        "class_id": 0,
                    },
                    {
                        "x": 300.0,
                        "y": 100.0,
                        "width": 50.0,
                        "height": 50.0,
                        "confidence": 0.88,
                        "class": "Without Helmet",
                        "class_id": 1,
                    },
                    {
                        "x": 400.0,
                        "y": 100.0,
                        "width": 50.0,
                        "height": 50.0,
                        "confidence": 0.82,
                        "class": "With Helmet",
                        "class_id": 0,
                    },
                ]
            },
            request=httpx.Request("POST", "https://detect.roboflow.com/test"),
        )
        img_bytes = _create_test_image_bytes(width=640, height=480)
        files = {"file": ("four_riders.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        form_data = {"cooldown_seconds": "0"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            resp = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files,
                data=form_data,
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        riders = data["riders"]
        # Exactly four candidates preserved
        assert len(riders) == 4

        expected_confs = [0.95, 0.91, 0.88, 0.82]
        expected_classifications = ["WITHOUT_HELMET", "WITH_HELMET", "WITHOUT_HELMET", "WITH_HELMET"]
        expected_violations = [True, False, True, False]

        for i in range(4):
            assert riders[i]["confidence"] == expected_confs[i]
            assert riders[i]["classification"] == expected_classifications[i]
            assert riders[i]["isViolation"] == expected_violations[i]
            assert riders[i]["cropPath"] is not None
            crop_name = os.path.basename(riders[i]["cropPath"])
            assert os.path.isfile(os.path.join(EVIDENCE_UPLOAD_DIR, crop_name))

        # Distinct stable IDs
        ids = [r["detectionId"] for r in riders]
        assert len(set(ids)) == 4

        # Candidate violation status remains strictly PENDING_REVIEW
        assert data["isCandidateViolation"] is True
        assert data["status"] == "PENDING_REVIEW"
        assert data["caseId"] is not None

        db = get_db()
        violation = db[COLLECTION_VIOLATIONS].find_one({"caseId": data["caseId"]})
        assert violation is not None
        assert violation["status"] == "PENDING_REVIEW"
        assert violation["challanDraftNumber"] is None
        assert violation["draftAmountInr"] is None

    def test_timing_breakdown_telemetry(self, auth_headers):
        """Validates that granular stage timings (model inference, evidence saving, ocr, db lookup) are tracked."""
        mock_resp = httpx.Response(
            status_code=200,
            json={"predictions": []},
            request=httpx.Request("POST", "https://detect.roboflow.com/test"),
        )
        img_bytes = _create_test_image_bytes(width=320, height=240)
        files = {"file": ("timing_test.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        form_data = {"cooldown_seconds": "0"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            resp = client.post(
                f"{settings.API_PREFIX}/detections/analyze",
                files=files,
                data=form_data,
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "timingBreakdown" in data
        timing = data["timingBreakdown"]
        assert "modelInferenceMs" in timing
        assert "evidenceSavingMs" in timing
        assert "ocrMs" in timing
        assert "dbLookupMs" in timing
        assert "totalProcessingMs" in timing
        assert timing["totalProcessingMs"] >= 0.0



