"""
Unit & Integration Tests for Authentication, Token Lifecycle, and Role RBAC.

Verifies:
- Password hashing with bcrypt
- Short-lived JWT generation, verification, and expiration
- Login endpoint status codes (200, 401, 403)
- Role protection: least-privilege matrix (Supervisors cannot modify settings)
- Bootstrap admin utility validation
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo import MongoClient

from main import app
from app.config import settings
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.core.exceptions import UnauthorizedError
from app.core.bootstrap_admin import bootstrap_admin
from app.db.collections import COLLECTION_USERS, COLLECTION_AUDIT_LOGS
from app.db.connection import get_db

client = TestClient(app)


class TestSecurityUtilities:
    """Verifies cryptographic primitives."""

    def test_hash_and_verify_password(self):
        pwd = "SuperSecretGovPassword2026!"
        hashed = hash_password(pwd)
        assert hashed != pwd
        assert verify_password(pwd, hashed) is True
        assert verify_password("WrongPassword!", hashed) is False

    def test_token_creation_and_decoding(self):
        data = {"sub": "user-1234", "role": "admin", "name": "Aditya"}
        token = create_access_token(data=data, expires_delta=timedelta(minutes=15))
        decoded = decode_access_token(token)
        assert decoded["sub"] == "user-1234"
        assert decoded["role"] == "admin"
        assert "exp" in decoded

    def test_expired_token_raises_unauthorized(self):
        data = {"sub": "user-1234"}
        token = create_access_token(data=data, expires_delta=timedelta(seconds=-1))
        with pytest.raises(UnauthorizedError) as exc:
            decode_access_token(token)
        assert "expired" in str(exc.value).lower()


@pytest.fixture(scope="module", autouse=True)
def setup_test_users():
    """Seeds uniquely named test officers in MongoDB."""
    db = get_db()
    # Clean existing test users if any
    db[COLLECTION_USERS].delete_many({"email": {"$regex": r"^test\."}})

    hashed_admin = hash_password("AdminPass123!")
    hashed_reviewer = hash_password("ReviewerPass123!")
    hashed_supervisor = hash_password("SupervisorPass123!")
    hashed_inactive = hash_password("InactivePass123!")

    now = datetime.now(timezone.utc)
    test_docs = [
        {
            "employeeId": "TEST-ADM-01",
            "name": "Test Admin",
            "email": "test.admin@traffic.gov.in",
            "passwordHash": hashed_admin,
            "role": "admin",
            "status": "ACTIVE",
            "createdAt": now,
            "updatedAt": now,
        },
        {
            "employeeId": "TEST-REV-01",
            "name": "Test Reviewer",
            "email": "test.reviewer@traffic.gov.in",
            "passwordHash": hashed_reviewer,
            "role": "reviewer",
            "status": "ACTIVE",
            "createdAt": now,
            "updatedAt": now,
        },
        {
            "employeeId": "TEST-SUP-01",
            "name": "Test Supervisor",
            "email": "test.supervisor@traffic.gov.in",
            "passwordHash": hashed_supervisor,
            "role": "supervisor",
            "status": "ACTIVE",
            "createdAt": now,
            "updatedAt": now,
        },
        {
            "employeeId": "TEST-INA-01",
            "name": "Test Inactive",
            "email": "test.inactive@traffic.gov.in",
            "passwordHash": hashed_inactive,
            "role": "reviewer",
            "status": "INACTIVE",
            "createdAt": now,
            "updatedAt": now,
        },
    ]
    db[COLLECTION_USERS].insert_many(test_docs)

    yield

    # Clean up test users
    db[COLLECTION_USERS].delete_many({"email": {"$regex": r"^test\."}})


class TestAuthEndpoints:
    """Tests /auth/login and /auth/me."""

    def test_login_successful(self):
        """POST /auth/login with valid credentials returns 200 and access token."""
        payload = {"email": "test.admin@traffic.gov.in", "password": "AdminPass123!"}
        response = client.post(f"{settings.API_PREFIX}/auth/login", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "accessToken" in data["data"]
        assert data["data"]["user"]["role"] == "admin"
        assert data["data"]["user"]["email"] == "test.admin@traffic.gov.in"

    def test_login_invalid_password_returns_401(self):
        """POST /auth/login with wrong password returns 401 Unauthorized."""
        payload = {"email": "test.admin@traffic.gov.in", "password": "BadPassword!"}
        response = client.post(f"{settings.API_PREFIX}/auth/login", json=payload)
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "UNAUTHORIZED"

    def test_login_inactive_user_returns_403(self):
        """POST /auth/login with inactive account returns 403 Forbidden."""
        payload = {"email": "test.inactive@traffic.gov.in", "password": "InactivePass123!"}
        response = client.post(f"{settings.API_PREFIX}/auth/login", json=payload)
        assert response.status_code == 403
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "FORBIDDEN"

    def test_get_current_user_profile_success(self):
        """GET /auth/me with valid Bearer token returns 200."""
        # Authenticate first
        login_res = client.post(
            f"{settings.API_PREFIX}/auth/login",
            json={"email": "test.reviewer@traffic.gov.in", "password": "ReviewerPass123!"},
        )
        token = login_res.json()["data"]["accessToken"]

        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(f"{settings.API_PREFIX}/auth/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["email"] == "test.reviewer@traffic.gov.in"
        assert data["data"]["role"] == "reviewer"

    def test_get_current_user_unauthenticated_returns_401(self):
        """GET /auth/me without header returns 401 Unauthorized."""
        response = client.get(f"{settings.API_PREFIX}/auth/me")
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "UNAUTHORIZED"


class TestRolePermissionMatrix:
    """Verifies that least-privilege RBAC is strictly enforced."""

    def _get_token(self, email: str, pwd: str) -> str:
        login_res = client.post(
            f"{settings.API_PREFIX}/auth/login",
            json={"email": email, "password": pwd},
        )
        return login_res.json()["data"]["accessToken"]

    def test_supervisor_cannot_modify_settings_returns_403(self):
        """Supervisors must not have admin permission to change settings."""
        token = self._get_token("test.supervisor@traffic.gov.in", "SupervisorPass123!")
        headers = {"Authorization": f"Bearer {token}"}

        patch_payload = {"minConfidenceThreshold": 0.75}
        response = client.patch(f"{settings.API_PREFIX}/settings", json=patch_payload, headers=headers)
        assert response.status_code == 403
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "FORBIDDEN"

    def test_reviewer_cannot_modify_settings_returns_403(self):
        """Reviewers cannot modify system settings."""
        token = self._get_token("test.reviewer@traffic.gov.in", "ReviewerPass123!")
        headers = {"Authorization": f"Bearer {token}"}

        patch_payload = {"dataRetentionDays": 60}
        response = client.patch(f"{settings.API_PREFIX}/settings", json=patch_payload, headers=headers)
        assert response.status_code == 403
        data = response.json()
        assert data["success"] is False

    def test_admin_can_modify_settings_returns_200(self):
        """Admin can modify system settings."""
        token = self._get_token("test.admin@traffic.gov.in", "AdminPass123!")
        headers = {"Authorization": f"Bearer {token}"}

        patch_payload = {"minConfidenceThreshold": 0.60}
        response = client.patch(f"{settings.API_PREFIX}/settings", json=patch_payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["minConfidenceThreshold"] == 0.60


class TestBootstrapAdmin:
    """Verifies the initial admin bootstrap CLI tool."""

    def test_bootstrap_admin_creates_account(self):
        db = get_db()
        db[COLLECTION_USERS].delete_many({"email": "test.bootstrap@traffic.gov.in"})

        result = bootstrap_admin(
            email="test.bootstrap@traffic.gov.in",
            name="Bootstrap Admin",
            employee_id="TEST-BST-01",
            password="SecureBootstrapPass2026!",
            db=db,
        )
        assert result["email"] == "test.bootstrap@traffic.gov.in"
        assert result["role"] == "admin"

        # Verify password verification succeeds
        user = db[COLLECTION_USERS].find_one({"email": "test.bootstrap@traffic.gov.in"})
        assert user is not None
        assert verify_password("SecureBootstrapPass2026!", user["passwordHash"]) is True

        # Clean up
        db[COLLECTION_USERS].delete_many({"email": "test.bootstrap@traffic.gov.in"})
        db[COLLECTION_AUDIT_LOGS].delete_many({"entityId": result["id"]})

    def test_bootstrap_admin_rejects_short_password(self):
        with pytest.raises(ValueError) as exc:
            bootstrap_admin(
                email="test.short@traffic.gov.in",
                name="Short",
                employee_id="TEST-SHT-01",
                password="short",
            )
        assert "at least 8 characters" in str(exc.value)
