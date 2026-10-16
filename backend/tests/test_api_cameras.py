
"""
Tests for Camera Endpoints: Registration, Status Codes, and Sanitization.
"""

from fastapi.testclient import TestClient
from main import app
from app.config import settings

client = TestClient(app)


class TestCameraEndpoints:
    """Verifies typed validation and 201 Created status for camera registration."""

    def test_list_cameras_returns_200(self):
        """GET /cameras returns 200 OK."""
        response = client.get(f"{settings.API_PREFIX}/cameras")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    def test_register_camera_success_returns_201(self):
        """POST /cameras returns 201 Created and sanitized source."""
        payload = {
            "name": "North Junction Pole Cam 02",
            "junction": "Sector 4B Intersection",
            "streamType": "IP_CAMERA",
            "ipOrDeviceUrl": "rtsp://admin:secretPass@192.168.1.120:554/stream1",
            "resolution": "4K",
            "fps": 60.0,
        }
        response = client.post(f"{settings.API_PREFIX}/cameras", json=payload)
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
        payload = {
            "name": "Drone Cam",
            "junction": "Main Road",
            "streamType": "SATELLITE_UPLINK",  # Invalid enum
            "ipOrDeviceUrl": "http://10.0.0.1",
        }
        response = client.post(f"{settings.API_PREFIX}/cameras", json=payload)
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "VALIDATION_ERROR"
        assert any("streamType" in d["field"] for d in data["details"])
