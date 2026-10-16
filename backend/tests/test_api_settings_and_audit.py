"""
Tests for System Settings, Operations Telemetry, and Audit Log Queries.

Verifies:
- Settings retrieval and Admin-only updates with audit trail
- Shift status logging
- Paginated audit log queries
- Append-only immutability (no edit or delete endpoints exist)
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from main import app
from app.config import settings
from app.core.security import hash_password
from app.db.connection import get_db
from app.db.collections import COLLECTION_USERS, COLLECTION_AUDIT_LOGS

client = TestClient(app)


class TestSettingsAndAudit:
    """Verifies settings and audit trails."""

    @pytest.fixture(autouse=True)
    def setup_admin_and_supervisor(self):
        db = get_db()
        now = datetime.now(timezone.utc)
        db[COLLECTION_USERS].delete_many({"email": {"$regex": r"^test\.audit"}})

        admin_doc = {
            "employeeId": "TEST-AUDADM-01",
            "name": "Audit Admin",
            "email": "test.auditadmin@traffic.gov.in",
            "passwordHash": hash_password("AuditAdminPass123!"),
            "role": "admin",
            "status": "ACTIVE",
            "createdAt": now,
            "updatedAt": now,
        }
        sup_doc = {
            "employeeId": "TEST-AUDSUP-01",
            "name": "Audit Supervisor",
            "email": "test.auditsup@traffic.gov.in",
            "passwordHash": hash_password("AuditSupPass123!"),
            "role": "supervisor",
            "status": "ACTIVE",
            "createdAt": now,
            "updatedAt": now,
        }
        db[COLLECTION_USERS].insert_many([admin_doc, sup_doc])

        yield

        # Cleanup
        db[COLLECTION_USERS].delete_many({"email": {"$regex": r"^test\.audit"}})

    def _get_token(self, email: str, pwd: str) -> str:
        login_res = client.post(
            f"{settings.API_PREFIX}/auth/login",
            json={"email": email, "password": pwd},
        )
        return login_res.json()["data"]["accessToken"]

    def test_settings_retrieval(self):
        """GET /settings returns current policy thresholds."""
        token = self._get_token("test.auditadmin@traffic.gov.in", "AuditAdminPass123!")
        headers = {"Authorization": f"Bearer {token}"}
        res = client.get(f"{settings.API_PREFIX}/settings", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "minConfidenceThreshold" in data["data"]
        assert "dataRetentionDays" in data["data"]

    def test_settings_update_creates_audit_entry(self):
        """PATCH /settings updates parameters and logs to audit_logs."""
        token = self._get_token("test.auditadmin@traffic.gov.in", "AuditAdminPass123!")
        headers = {"Authorization": f"Bearer {token}"}

        patch_payload = {
            "minConfidenceThreshold": 0.65,
            "defaultDraftPenaltyInr": 1500.0,
        }
        res = client.patch(f"{settings.API_PREFIX}/settings", json=patch_payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["data"]["minConfidenceThreshold"] == 0.65
        assert data["data"]["defaultDraftPenaltyInr"] == 1500.0

        # Verify audit log was recorded in MongoDB
        db = get_db()
        audit = db[COLLECTION_AUDIT_LOGS].find_one({"action": "POLICY_THRESHOLDS_MODIFIED"})
        assert audit is not None
        assert audit["entityType"] == "settings"

    def test_log_officer_shift_status(self):
        """POST /operations/shifts records shift status for authenticated user."""
        token = self._get_token("test.auditadmin@traffic.gov.in", "AuditAdminPass123!")
        headers = {"Authorization": f"Bearer {token}"}

        shift_payload = {"status": "ON_DUTY", "notes": "Morning junction enforcement shift."}
        res = client.post(f"{settings.API_PREFIX}/operations/shifts", json=shift_payload, headers=headers)
        assert res.status_code == 201
        data = res.json()
        assert data["success"] is True
        assert data["data"]["status"] == "ON_DUTY"
        assert data["data"]["officerName"] == "Audit Admin"

    def test_audit_logs_query_and_immutability(self):
        """GET /audit-logs returns paginated records; no DELETE or PUT endpoints exist."""
        token = self._get_token("test.auditsup@traffic.gov.in", "AuditSupPass123!")
        headers = {"Authorization": f"Bearer {token}"}

        # Query audit logs -> 200 OK
        res = client.get(f"{settings.API_PREFIX}/audit-logs?page=1&page_size=10", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "total" in data
        assert isinstance(data["data"], list)

        # Attempt DELETE /audit-logs -> 405 Method Not Allowed
        del_res = client.delete(f"{settings.API_PREFIX}/audit-logs", headers=headers)
        assert del_res.status_code == 405

        # Attempt PUT /audit-logs -> 405 Method Not Allowed
        put_res = client.put(f"{settings.API_PREFIX}/audit-logs", json={}, headers=headers)
        assert put_res.status_code == 405
