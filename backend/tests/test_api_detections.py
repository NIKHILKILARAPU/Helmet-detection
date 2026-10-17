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
from app.db.collections import COLLECTION_USERS, COLLECTION_MODEL_RUNS, COLLECTION_VIOLATIONS, COLLECTION_CAMERAS, COLLECTION_AUDIT_LOGS
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

    yield

    # Teardown
    db[COLLECTION_USERS].delete_many({"email": "test.detections_op@traffic.gov.in"})
    db[COLLECTION_CAMERAS].delete_many({"name": "TEST_DETECTIONS_CAM"})
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
        assert box["xyxy"] == [250.0, 160.0, 350.0, 240.0]
        # Normalized: [ymin/H, xmin/W, ymax/H, xmax/W] = [160/400, 250/600, 240/400, 350/600]
        assert box["normalized"] == [0.4, 0.4167, 0.6, 0.5833]
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

