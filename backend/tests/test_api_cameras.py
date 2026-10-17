"""
Tests for Camera Endpoints: Registration, Status Codes, Sanitization, and RBAC.
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from main import app
from app.config import settings
from app.core.security import hash_password
from app.db.connection import get_db
from app.db.collections import COLLECTION_USERS, COLLECTION_CAMERAS

client = TestClient(app)


class TestCameraEndpoints:
    """Verifies typed validation, credential sanitization, and RBAC for cameras."""

    @pytest.fixture(autouse=True)
    def setup_operator(self):
        db = get_db()
        now = datetime.now(timezone.utc)
        db[COLLECTION_USERS].delete_many({"email": "test.camop@traffic.gov.in"})

        op_doc = {
            "employeeId": "TEST-CAMOP-01",
            "name": "Operator Testing",
            "email": "test.camop@traffic.gov.in",
            "passwordHash": hash_password("CamOpPass123!"),
            "role": "operator",
            "status": "ACTIVE",
            "createdAt": now,
            "updatedAt": now,
        }
        db[COLLECTION_USERS].insert_one(op_doc)

        yield

        # Cleanup
        db[COLLECTION_USERS].delete_many({"email": "test.camop@traffic.gov.in"})
        db[COLLECTION_CAMERAS].delete_many({"name": {"$regex": r"^TEST|^North Junction"}})
        db["audit_logs"].delete_many({"actorNameSnapshot": "Operator Testing"})

    def _get_operator_token(self) -> str:
        login_res = client.post(
            f"{settings.API_PREFIX}/auth/login",
            json={"email": "test.camop@traffic.gov.in", "password": "CamOpPass123!"},
        )
        return login_res.json()["data"]["accessToken"]

    def test_list_cameras_returns_200(self):
        """GET /cameras returns 200 OK."""
        response = client.get(f"{settings.API_PREFIX}/cameras")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    def test_register_camera_unauthenticated_returns_401(self):
        """POST /cameras without Bearer token returns 401."""
        payload = {
            "name": "Unauthorized Cam",
            "junction": "Sector 4B",
            "streamType": "IP_CAMERA",
            "ipOrDeviceUrl": "rtsp://10.0.0.1",
        }
        response = client.post(f"{settings.API_PREFIX}/cameras", json=payload)
        assert response.status_code == 401
        assert response.json()["error_code"] == "UNAUTHORIZED"

    def test_register_camera_success_returns_201(self):
        """POST /cameras returns 201 Created and sanitized source."""
        token = self._get_operator_token()
        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "name": "North Junction Pole Cam 02",
            "junction": "Sector 4B Intersection",
            "streamType": "IP_CAMERA",
            "ipOrDeviceUrl": "rtsp://admin:secretPass@192.168.1.120:554/stream1",
            "resolution": "4K",
            "fps": 60.0,
        }
        response = client.post(f"{settings.API_PREFIX}/cameras", json=payload, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == payload["name"]
        assert data["data"]["streamType"] == "IP_CAMERA"
        # Verify credentials redacted: secretPass is NOT exposed
        assert "secretPass" not in data["data"]["source"]
        assert "192.168.1.120:554/stream1" in data["data"]["source"]

    def test_register_camera_invalid_stream_type_returns_422(self):
        """POST /cameras with invalid streamType returns 422 Unprocessable Entity."""
        token = self._get_operator_token()
        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "name": "Drone Cam",
            "junction": "Main Road",
            "streamType": "SATELLITE_UPLINK",  # Invalid enum
            "ipOrDeviceUrl": "http://10.0.0.1",
        }
        response = client.post(f"{settings.API_PREFIX}/cameras", json=payload, headers=headers)
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "VALIDATION_ERROR"
        assert any("streamType" in d["field"] for d in data["details"])
