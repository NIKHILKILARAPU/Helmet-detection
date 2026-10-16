"""
Unit tests for MongoDB Connection Management and Lifecycle.

Tests:
- Initial disconnected state
- Rejection and error handling on unreachable host/port
- Accurate health check reporting (never reports false-positive READY)
- Graceful connection close and cleanup
"""

import pytest
from unittest.mock import MagicMock, patch
from app.db.connection import MongoDBManager, DatabaseConnectionError


class TestMongoDBManager:
    """Tests MongoDB connection lifecycle and error states."""

    def test_initial_disconnected_state(self):
        """Manager should report disconnected initially and offline if connection fails."""
        manager = MongoDBManager()
        assert manager.is_connected is False

        # When connection fails, check_health must report OFFLINE
        with patch.object(manager, "connect", side_effect=DatabaseConnectionError("Unreachable")):
            health = manager.check_health()
            assert health["status"] == "OFFLINE"
            assert health["is_ready"] is False
            assert "Unreachable" in health["error"]

    def test_unreachable_host_raises_database_connection_error(self):
        """Connecting to an invalid/unreachable host must raise DatabaseConnectionError."""
        manager = MongoDBManager()
        # Use an invalid port and a 100ms server selection timeout
        with pytest.raises(DatabaseConnectionError) as exc_info:
            manager.connect(
                uri="mongodb://127.0.0.1:59999",
                db_name="test_nonexistent",
                connect_timeout_ms=100,
                server_selection_timeout_ms=100,
            )
        assert "Failed to connect to MongoDB" in str(exc_info.value)
        assert manager.is_connected is False

    def test_mocked_ping_success_reports_online(self):
        """When client ping command succeeds, manager must report ONLINE."""
        manager = MongoDBManager()
        mock_client = MagicMock()
        mock_client.admin.command.return_value = {"ok": 1.0}
        mock_db = MagicMock()
        mock_client.__getitem__.return_value = mock_db

        with patch("app.db.connection.MongoClient", return_value=mock_client):
            db = manager.connect(uri="mongodb://localhost:27017", db_name="test_db")
            assert db is mock_db
            assert manager.is_connected is True

            health = manager.check_health()
            assert health["status"] == "ONLINE"
            assert health["is_ready"] is True
            assert "latency_ms" in health

    def test_mocked_ping_failure_reports_offline(self):
        """If ping throws after initialization, health check must report OFFLINE."""
        manager = MongoDBManager()
        mock_client = MagicMock()
        mock_client.admin.command.side_effect = Exception("Network connection lost")
        manager._client = mock_client
        manager._db_name = "test_db"

        assert manager.is_connected is False
        health = manager.check_health()
        assert health["status"] == "OFFLINE"
        assert health["is_ready"] is False
        assert "Network connection lost" in health["error"]

    def test_close_resets_connection_state(self):
        """Calling close() must close the client and set internal references to None."""
        manager = MongoDBManager()
        mock_client = MagicMock()
        manager._client = mock_client
        manager._db = MagicMock()

        manager.close()
        mock_client.close.assert_called_once()
        assert manager._client is None
        assert manager._db is None
        assert manager.is_connected is False
