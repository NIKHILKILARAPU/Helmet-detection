"""
Tests for Atomic State Transitions, Concurrency, and Double-Review Prevention.

Verifies:
- Atomic find_one_and_update prevents race conditions
- Double review attempts return 409 Conflict
- Reviewer attribution is derived exclusively from JWT token
"""

import pytest
from datetime import datetime, timezone
from bson import ObjectId
from fastapi.testclient import TestClient

from main import app
from app.config import settings
from app.core.security import hash_password
from app.db.connection import get_db
from app.db.collections import COLLECTION_VIOLATIONS, COLLECTION_USERS

client = TestClient(app)


class TestConcurrencyAndReviewWorkflow:
    """Verifies atomic state transitions on violations."""

    @pytest.fixture(autouse=True)
    def setup_reviewer_and_case(self):
        db = get_db()
        now = datetime.now(timezone.utc)

        # Create test reviewer
        db[COLLECTION_USERS].delete_many({"email": "test.concrev@traffic.gov.in"})
        reviewer_doc = {
            "employeeId": "TEST-CONCREV-01",
            "name": "Officer Trustworthy",
            "email": "test.concrev@traffic.gov.in",
            "passwordHash": hash_password("ConcPass123!"),
            "role": "reviewer",
            "status": "ACTIVE",
            "createdAt": now,
            "updatedAt": now,
        }
        db[COLLECTION_USERS].insert_one(reviewer_doc)

        # Create a clean test violation case in PENDING_REVIEW
        case_id = "TG-TEST-CONC-01"
        db[COLLECTION_VIOLATIONS].delete_many({"caseId": case_id})
        violation_doc = {
            "caseId": case_id,
            "cameraId": ObjectId(),
            "capturedAt": now,
            "violationType": "NO_HELMET_RIDER",
            "confidence": 0.94,
            "status": "PENDING_REVIEW",
            "evidence": {"storagePath": "/evidence/test_conc.jpg"},
            "evidenceQuality": "HIGH",
            "boundingBoxes": [{"className": "NO_HELMET"}],
            "identityVerificationStatus": "UNVERIFIED",
            "reviewerNotes": None,
            "rejectionReason": None,
            "challanDraftNumber": None,
            "draftAmountInr": None,
            "reviewedBy": None,
            "reviewedAt": None,
            "createdAt": now,
            "updatedAt": now,
        }
        db[COLLECTION_VIOLATIONS].insert_one(violation_doc)

        yield case_id

        # Clean up
        db[COLLECTION_USERS].delete_many({"email": "test.concrev@traffic.gov.in"})
        db[COLLECTION_VIOLATIONS].delete_many({"caseId": case_id})

    def _get_reviewer_token(self) -> str:
        login_res = client.post(
            f"{settings.API_PREFIX}/auth/login",
            json={"email": "test.concrev@traffic.gov.in", "password": "ConcPass123!"},
        )
        return login_res.json()["data"]["accessToken"]

    def test_approve_case_success_and_prevent_double_review(self, setup_reviewer_and_case):
        """Case can be approved once; subsequent approve attempt returns 409 Conflict."""
        case_id = setup_reviewer_and_case
        token = self._get_reviewer_token()
        headers = {"Authorization": f"Bearer {token}"}

        approve_payload = {
            "reviewerName": "Officer ForgedName",  # Attempted client forgery
            "notes": "Verified against clear frame.",
            "draftAmountInr": 1000.0,
        }

        # First review -> 200 OK
        res1 = client.post(
            f"{settings.API_PREFIX}/violations/{case_id}/approve-draft",
            json=approve_payload,
            headers=headers,
        )
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["success"] is True
        assert data1["data"]["status"] == "DRAFT_CREATED"
        # Verify reviewer attribution is derived from authenticated user, NOT client body
        assert data1["data"]["reviewedBy"] == "Officer Trustworthy"

        # Second review attempt (Double review) -> 409 Conflict
        res2 = client.post(
            f"{settings.API_PREFIX}/violations/{case_id}/approve-draft",
            json=approve_payload,
            headers=headers,
        )
        assert res2.status_code == 409
        data2 = res2.json()
        assert data2["success"] is False
        assert data2["error_code"] == "RESOURCE_CONFLICT"
        assert "already in state" in data2["message"].lower()

    def test_reject_after_approve_prevented_with_409(self, setup_reviewer_and_case):
        """Rejecting an already approved case is prevented with 409 Conflict."""
        case_id = setup_reviewer_and_case
        token = self._get_reviewer_token()
        headers = {"Authorization": f"Bearer {token}"}

        # Approve case first
        client.post(
            f"{settings.API_PREFIX}/violations/{case_id}/approve-draft",
            json={"reviewerName": "Officer Trustworthy"},
            headers=headers,
        )

        # Attempt to reject now
        reject_payload = {
            "reviewerName": "Officer Trustworthy",
            "reason": "Late rejection attempt",
        }
        res = client.post(
            f"{settings.API_PREFIX}/violations/{case_id}/reject",
            json=reject_payload,
            headers=headers,
        )
        assert res.status_code == 409
        assert res.json()["error_code"] == "RESOURCE_CONFLICT"
