"""
Tests for Violations Endpoints: Request Validation, Status Codes, and Schemas.
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from app.config import settings

client = TestClient(app)


class TestViolationsEndpoints:
    """Verifies typed validation, status codes, and error formatting for violations."""

    def test_list_violations_default(self):
        """GET /violations with defaults returns 200 OK."""
        response = client.get(f"{settings.API_PREFIX}/violations")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    def test_list_violations_invalid_confidence_filter(self):
        """GET /violations with invalid min_confidence > 1.0 returns 422 Unprocessable Entity."""
        response = client.get(f"{settings.API_PREFIX}/violations?min_confidence=1.8")
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "VALIDATION_ERROR"
        assert any("min_confidence" in d["field"] for d in data["details"])

    def test_approve_draft_success_returns_200(self):
        """POST /violations/{case_id}/approve-draft returns 200 with typed response."""
        payload = {
            "reviewerName": "Officer R. Sharma",
            "notes": "Clear helmet non-compliance confirmed on high-res optical feed.",
            "draftAmountInr": 1000.0,
        }
        response = client.post(
            f"{settings.API_PREFIX}/violations/TG-2026-8941/approve-draft",
            json=payload,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["caseId"] == "TG-2026-8941"
        assert data["data"]["status"] == "DRAFT_CREATED"
        assert data["data"]["reviewedBy"] == "Officer R. Sharma"

    def test_approve_draft_missing_reviewer_name_returns_422(self):
        """POST without reviewerName returns 422 with validation error details."""
        payload = {
            "notes": "Missing reviewer name",
        }
        response = client.post(
            f"{settings.API_PREFIX}/violations/TG-2026-8941/approve-draft",
            json=payload,
        )
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "VALIDATION_ERROR"
        assert any("reviewerName" in d["field"] for d in data["details"])

    def test_approve_draft_negative_amount_returns_422(self):
        """POST with negative draft amount returns 422."""
        payload = {
            "reviewerName": "Officer Sharma",
            "draftAmountInr": -250.0,
        }
        response = client.post(
            f"{settings.API_PREFIX}/violations/TG-2026-8941/approve-draft",
            json=payload,
        )
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert any("draftAmountInr" in d["field"] for d in data["details"])

    def test_reject_case_success_returns_200(self):
        """POST /violations/{case_id}/reject returns 200."""
        payload = {
            "reviewerName": "Officer Sharma",
            "reason": "Glare reflection on shadow contour; compliant turban verified.",
            "notes": "Verified against high-contrast filter.",
        }
        response = client.post(
            f"{settings.API_PREFIX}/violations/TG-2026-8941/reject",
            json=payload,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "REJECTED"
        assert data["data"]["rejectionReason"] == payload["reason"]

    def test_reject_case_blank_reason_returns_400(self):
        """POST with whitespace-only reason returns 400 Bad Request."""
        payload = {
            "reviewerName": "Officer Sharma",
            "reason": "   ",
        }
        response = client.post(
            f"{settings.API_PREFIX}/violations/TG-2026-8941/reject",
            json=payload,
        )
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "BUSINESS_VALIDATION_ERROR"

    def test_invalid_case_id_path_pattern_returns_422(self):
        """Path case_id with invalid characters returns 422."""
        payload = {
            "reviewerName": "Officer Sharma",
            "reason": "Valid reason text",
        }
        response = client.post(
            f"{settings.API_PREFIX}/violations/invalid*!@case/reject",
            json=payload,
        )
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert any("case_id" in d["field"] for d in data["details"])
