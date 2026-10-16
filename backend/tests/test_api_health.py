"""
Tests for API Health Check and Real Database Telemetry.

Verifies:
- Live DB health check integration
- Accurate reporting of ONLINE vs DEGRADED status
- Dedicated readiness probe returning HTTP 200 (online) and HTTP 503 (offline)
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app
from app.config import settings

client = TestClient(app)


class TestHealthEndpoint:
    """Tests /api/v1/health endpoint with mocked DB status."""

    def test_health_check_when_db_is_online(self):
        """When MongoDB ping succeeds, health endpoint should report ONLINE."""
        mock_health = {
            "status": "ONLINE",
            "database": settings.MONGO_DB_NAME,
            "latency_ms": 1.45,
            "is_ready": True,
        }
        with patch("app.db.connection.mongo_manager.check_health", return_value=mock_health):
            response = client.get(f"{settings.API_PREFIX}/health")
            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "ONLINE"
            assert data["database"]["status"] == "ONLINE"
            assert data["database"]["is_ready"] is True
            assert data["database"]["database"] == settings.MONGO_DB_NAME
            assert data["database"]["latency_ms"] == 1.45
            assert "microservices operational" in data["message"]

    def test_health_check_when_db_is_offline(self):
        """When MongoDB is unreachable, health endpoint should report DEGRADED and database OFFLINE."""
        mock_health = {
            "status": "OFFLINE",
            "database": settings.MONGO_DB_NAME,
            "error": "Connection refused on localhost:27017",
            "is_ready": False,
        }
        with patch("app.db.connection.mongo_manager.check_health", return_value=mock_health):
            response = client.get(f"{settings.API_PREFIX}/health")
            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "DEGRADED"
            assert data["database"]["status"] == "OFFLINE"
            assert data["database"]["is_ready"] is False
            assert "Connection refused" in data["database"]["error"]
            assert "degraded" in data["message"].lower()

    def test_db_readiness_probe_online(self):
        """Dedicated probe /health/db returns 200 when DB is online."""
        mock_health = {
            "status": "ONLINE",
            "database": settings.MONGO_DB_NAME,
            "latency_ms": 0.8,
            "is_ready": True,
        }
        with patch("app.db.connection.mongo_manager.check_health", return_value=mock_health):
            response = client.get(f"{settings.API_PREFIX}/health/db")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["status"] == "ONLINE"
            assert data["data"]["is_ready"] is True

    def test_db_readiness_probe_offline_returns_503(self):
        """Dedicated probe /health/db returns 503 when DB is offline."""
        mock_health = {
            "status": "OFFLINE",
            "database": settings.MONGO_DB_NAME,
            "error": "ServerSelectionTimeoutError",
            "is_ready": False,
        }
        with patch("app.db.connection.mongo_manager.check_health", return_value=mock_health):
            response = client.get(f"{settings.API_PREFIX}/health/db")
            assert response.status_code == 503
            data = response.json()
            assert data["success"] is False
            assert data["error_code"] == "DATABASE_UNAVAILABLE"
            assert "offline" in data["message"].lower()
