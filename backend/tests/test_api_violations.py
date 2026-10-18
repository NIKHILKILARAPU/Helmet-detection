"""
Tests for Violations Endpoints: Request Validation, Status Codes, Schemas, and RBAC.
"""

import pytest
from datetime import datetime, timezone
from bson import ObjectId
from fastapi.testclient import TestClient
from main import app
from app.config import settings
from app.core.security import hash_password, create_access_token
from app.db.connection import get_db
from app.db.collections import COLLECTION_USERS, COLLECTION_VIOLATIONS

client = TestClient(app)


class TestViolationsEndpoints:
    """Verifies typed validation, status codes, and error formatting for violations."""

    @pytest.fixture(autouse=True)
    def setup_reviewer_officer(self):
        db = get_db()
        now = datetime.now(timezone.utc)
        db[COLLECTION_USERS].delete_many({"email": "test.viorev@traffic.gov.in"})

        rev_doc = {
            "employeeId": "TEST-VIOREV-01",
            "name": "Officer R. Sharma",
            "email": "test.viorev@traffic.gov.in",
            "passwordHash": hash_password("VioRevPass123!"),
            "role": "reviewer",
            "status": "ACTIVE",
            "createdAt": now,
            "updatedAt": now,
        }
        db[COLLECTION_USERS].insert_one(rev_doc)

        # Seed candidate case TG-2026-8941
        db[COLLECTION_VIOLATIONS].delete_many({"caseId": "TG-2026-8941"})
        db[COLLECTION_VIOLATIONS].insert_one({
            "caseId": "TG-2026-8941",
            "cameraId": ObjectId(),
            "capturedAt": now,
            "violationType": "NO_HELMET_RIDER",
            "confidence": 0.92,
            "status": "PENDING_REVIEW",
            "evidence": {"storagePath": "/evidence/test.jpg"},
            "evidenceQuality": "HIGH",
            "boundingBoxes": [{"className": "NO_HELMET"}],
            "identityVerificationStatus": "UNVERIFIED",
            "createdAt": now,
            "updatedAt": now,
        })

        yield

        # Cleanup
        db[COLLECTION_USERS].delete_many({"email": "test.viorev@traffic.gov.in"})
        db[COLLECTION_VIOLATIONS].delete_many({"caseId": "TG-2026-8941"})
        db["audit_logs"].delete_many({"actorNameSnapshot": "Officer R. Sharma"})

    def _get_reviewer_token(self) -> str:
        login_res = client.post(
            f"{settings.API_PREFIX}/auth/login",
            json={"email": "test.viorev@traffic.gov.in", "password": "VioRevPass123!"},
        )
        return login_res.json()["data"]["accessToken"]

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

    def test_approve_draft_unauthenticated_returns_401(self):
        """POST without Bearer token returns 401 Unauthorized."""
        payload = {"reviewerName": "Officer Sharma"}
        response = client.post(
            f"{settings.API_PREFIX}/violations/TG-2026-8941/approve-draft",
            json=payload,
        )
        assert response.status_code == 401
        assert response.json()["error_code"] == "UNAUTHORIZED"

    def test_approve_draft_success_returns_200(self):
        """POST /violations/{case_id}/approve-draft returns 200 with typed response."""
        token = self._get_reviewer_token()
        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "reviewerName": "Officer R. Sharma",
            "notes": "Clear helmet non-compliance confirmed on high-res optical feed.",
            "draftAmountInr": 1000.0,
        }
        response = client.post(
            f"{settings.API_PREFIX}/violations/TG-2026-8941/approve-draft",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["caseId"] == "TG-2026-8941"
        assert data["data"]["status"] == "DRAFT_CREATED"
        assert data["data"]["reviewedBy"] == "Officer R. Sharma"

    def test_approve_draft_missing_reviewer_name_returns_422(self):
        """POST without reviewerName returns 422 with validation error details."""
        token = self._get_reviewer_token()
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"notes": "Missing reviewer name"}

        response = client.post(
            f"{settings.API_PREFIX}/violations/TG-2026-8941/approve-draft",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "VALIDATION_ERROR"
        assert any("reviewerName" in d["field"] for d in data["details"])

    def test_approve_draft_negative_amount_returns_422(self):
        """POST with negative draft amount returns 422."""
        token = self._get_reviewer_token()
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "reviewerName": "Officer Sharma",
            "draftAmountInr": -250.0,
        }
        response = client.post(
            f"{settings.API_PREFIX}/violations/TG-2026-8941/approve-draft",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert any("draftAmountInr" in d["field"] for d in data["details"])

    def test_reject_case_success_returns_200(self):
        """POST /violations/{case_id}/reject returns 200."""
        token = self._get_reviewer_token()
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "reviewerName": "Officer Sharma",
            "reason": "Glare reflection on shadow contour; compliant turban verified.",
            "notes": "Verified against high-contrast filter.",
        }
        response = client.post(
            f"{settings.API_PREFIX}/violations/TG-2026-8941/reject",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "REJECTED"
        assert data["data"]["rejectionReason"] == payload["reason"]

    def test_reject_case_blank_reason_returns_400(self):
        """POST with whitespace-only reason returns 400 Bad Request."""
        token = self._get_reviewer_token()
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "reviewerName": "Officer Sharma",
            "reason": "   ",
        }
        response = client.post(
            f"{settings.API_PREFIX}/violations/TG-2026-8941/reject",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "BUSINESS_VALIDATION_ERROR"

    def test_invalid_case_id_path_pattern_returns_422(self):
        """Path case_id with invalid characters returns 422."""
        token = self._get_reviewer_token()
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "reviewerName": "Officer Sharma",
            "reason": "Valid reason text",
        }
        response = client.post(
            f"{settings.API_PREFIX}/violations/invalid*!@case/reject",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert any("case_id" in d["field"] for d in data["details"])

    def test_multi_rider_independent_approval_and_rejection_workflow(self):
        """
        Comprehensive test for Multi-Rider Single Image Isolation:
        - 4 distinct cases created from 1 image frame sharing modelRunId
        - Approving Case 1 updates only Case 1 to DRAFT_CREATED
        - Cases 2, 3, 4 remain strictly PENDING_REVIEW
        - Rejecting Case 2 updates only Case 2 to REJECTED with documented cause
        - Cases 3, 4 remain strictly in PENDING_REVIEW
        - Double-approval and double-rejection blocked by 409 Conflict
        """
        db = get_db()
        now = datetime.now(timezone.utc)
        token = self._get_reviewer_token()
        headers = {"Authorization": f"Bearer {token}"}
        shared_run_id = "RUN-MULTI-FRAME-QUAD-99"
        cam_id = ObjectId()

        case_ids = [f"TG-QUAD-RIDER-{i}" for i in range(1, 5)]
        for cid in case_ids:
            db[COLLECTION_VIOLATIONS].delete_many({"caseId": cid})

        # Insert 4 distinct cases from the same frame
        for i, cid in enumerate(case_ids, start=1):
            db[COLLECTION_VIOLATIONS].insert_one({
                "caseId": cid,
                "modelRunId": shared_run_id,
                "cameraId": cam_id,
                "capturedAt": now,
                "violationType": "NO_HELMET_RIDER",
                "confidence": 0.85 + (i * 0.02),
                "status": "PENDING_REVIEW",
                "evidence": {
                    "storagePath": "/evidence/multi_quad_frame.jpg",
                    "thumbnailPath": "/evidence/multi_quad_frame.jpg",
                },
                "riderDetails": {
                    "riderIndex": i,
                    "cropPath": f"/uploads/evidence/crop_rider_{cid}.jpg",
                    "coordinates": [50 * i, 50, 50 * i + 40, 100],
                },
                "evidenceQuality": "HIGH",
                "boundingBoxes": [{"className": "NO_HELMET"}],
                "identityVerificationStatus": "UNVERIFIED",
                "createdAt": now,
                "updatedAt": now,
            })

        try:
            # 1. Reviewer approves Case 1
            appr_res = client.post(
                f"{settings.API_PREFIX}/violations/{case_ids[0]}/approve-draft",
                json={"reviewerName": "Officer R. Sharma", "notes": "Approved Rider 1"},
                headers=headers,
            )
            assert appr_res.status_code == 200
            appr_data = appr_res.json()
            assert appr_data["success"] is True
            assert appr_data["data"]["caseId"] == case_ids[0]
            assert appr_data["data"]["status"] == "DRAFT_CREATED"
            assert appr_data["data"]["challanDraftNumber"] is not None
            assert appr_data["data"]["challanDraftNumber"].startswith("DFT-")

            # Verify Database State: Only Case 1 transitioned; Cases 2, 3, 4 strictly PENDING_REVIEW
            c1 = db[COLLECTION_VIOLATIONS].find_one({"caseId": case_ids[0]})
            c2 = db[COLLECTION_VIOLATIONS].find_one({"caseId": case_ids[1]})
            c3 = db[COLLECTION_VIOLATIONS].find_one({"caseId": case_ids[2]})
            c4 = db[COLLECTION_VIOLATIONS].find_one({"caseId": case_ids[3]})

            assert c1["status"] == "DRAFT_CREATED"
            assert c1["challanDraftNumber"] is not None

            assert c2["status"] == "PENDING_REVIEW"
            assert c2.get("challanDraftNumber") is None

            assert c3["status"] == "PENDING_REVIEW"
            assert c3.get("challanDraftNumber") is None

            assert c4["status"] == "PENDING_REVIEW"
            assert c4.get("challanDraftNumber") is None

            # 2. Reviewer rejects Case 2 with documented cause
            rej_res = client.post(
                f"{settings.API_PREFIX}/violations/{case_ids[1]}/reject",
                json={
                    "reviewerName": "Officer R. Sharma",
                    "reason": "FALSE_DETECTION_SHADOW",
                    "notes": "Helmet reflection shadow artifact verified on high-res crop.",
                },
                headers=headers,
            )
            assert rej_res.status_code == 200
            rej_data = rej_res.json()
            assert rej_data["success"] is True
            assert rej_data["data"]["caseId"] == case_ids[1]
            assert rej_data["data"]["status"] == "REJECTED"

            # Verify Database State: Case 2 is REJECTED, Case 1 is DRAFT_CREATED, Cases 3 and 4 remain PENDING_REVIEW
            c1 = db[COLLECTION_VIOLATIONS].find_one({"caseId": case_ids[0]})
            c2 = db[COLLECTION_VIOLATIONS].find_one({"caseId": case_ids[1]})
            c3 = db[COLLECTION_VIOLATIONS].find_one({"caseId": case_ids[2]})
            c4 = db[COLLECTION_VIOLATIONS].find_one({"caseId": case_ids[3]})

            assert c1["status"] == "DRAFT_CREATED"
            assert c2["status"] == "REJECTED"
            assert c2["rejectionReason"] == "FALSE_DETECTION_SHADOW"
            assert c3["status"] == "PENDING_REVIEW"
            assert c4["status"] == "PENDING_REVIEW"

            # 3. Concurrency / Double-review prevention (409 Conflict)
            appr_again = client.post(
                f"{settings.API_PREFIX}/violations/{case_ids[0]}/approve-draft",
                json={"reviewerName": "Officer R. Sharma"},
                headers=headers,
            )
            assert appr_again.status_code == 409
            assert appr_again.json()["error_code"] == "RESOURCE_CONFLICT"

            rej_again = client.post(
                f"{settings.API_PREFIX}/violations/{case_ids[1]}/reject",
                json={"reviewerName": "Officer R. Sharma", "reason": "Already rejected"},
                headers=headers,
            )
            assert rej_again.status_code == 409
            assert rej_again.json()["error_code"] == "RESOURCE_CONFLICT"

        finally:
            for cid in case_ids:
                db[COLLECTION_VIOLATIONS].delete_many({"caseId": cid})

    def test_approve_draft_not_found_returns_404(self):
        """Approving a non-existent case returns 404 RESOURCE_NOT_FOUND."""
        token = self._get_reviewer_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"{settings.API_PREFIX}/violations/TG-NONEXISTENT-9999/approve-draft",
            json={"reviewerName": "Officer Sharma"},
            headers=headers,
        )
        assert response.status_code == 404
        assert response.json()["error_code"] == "RESOURCE_NOT_FOUND"

    def test_reject_not_found_returns_404(self):
        """Rejecting a non-existent case returns 404 RESOURCE_NOT_FOUND."""
        token = self._get_reviewer_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"{settings.API_PREFIX}/violations/TG-NONEXISTENT-9999/reject",
            json={"reviewerName": "Officer Sharma", "reason": "Case does not exist"},
            headers=headers,
        )
        assert response.status_code == 404
        assert response.json()["error_code"] == "RESOURCE_NOT_FOUND"

    def test_approve_draft_missing_evidence_returns_400(self):
        """Approving a case that lacks required photographic evidence returns 400 BUSINESS_VALIDATION_ERROR."""
        db = get_db()
        now = datetime.now(timezone.utc)
        token = self._get_reviewer_token()
        headers = {"Authorization": f"Bearer {token}"}
        case_id = "TG-NO-EVIDENCE-01"

        db[COLLECTION_VIOLATIONS].delete_many({"caseId": case_id})
        db[COLLECTION_VIOLATIONS].insert_one({
            "caseId": case_id,
            "cameraId": ObjectId(),
            "capturedAt": now,
            "violationType": "NO_HELMET_RIDER",
            "confidence": 0.90,
            "status": "PENDING_REVIEW",
            "evidence": {"storagePath": "   "},  # Whitespace only
            "evidenceQuality": "HIGH",
            "boundingBoxes": [{"className": "NO_HELMET"}],
            "identityVerificationStatus": "UNVERIFIED",
            "createdAt": now,
            "updatedAt": now,
        })

        try:
            response = client.post(
                f"{settings.API_PREFIX}/violations/{case_id}/approve-draft",
                json={"reviewerName": "Officer Sharma"},
                headers=headers,
            )
            assert response.status_code == 400
            assert response.json()["error_code"] == "BUSINESS_VALIDATION_ERROR"
        finally:
            db[COLLECTION_VIOLATIONS].delete_many({"caseId": case_id})

    def test_reviewer_actions_rbac_forbidden_for_operator(self):
        """Operator role receives 403 Forbidden when attempting to approve or reject cases."""
        db = get_db()
        now = datetime.now(timezone.utc)
        op_email = "test.temp_op@traffic.gov.in"
        db[COLLECTION_USERS].delete_many({"email": op_email})

        user_res = db[COLLECTION_USERS].insert_one({
            "employeeId": "TEST-TEMP-OP-01",
            "name": "Camera Operator",
            "email": op_email,
            "passwordHash": hash_password("OpPass123!"),
            "role": "operator",
            "status": "ACTIVE",
            "createdAt": now,
            "updatedAt": now,
        })
        op_id = str(user_res.inserted_id)

        try:
            op_token = create_access_token(
                data={"sub": op_id, "name": "Camera Operator", "employeeId": "TEST-TEMP-OP-01", "role": "operator"}
            )
            op_headers = {"Authorization": f"Bearer {op_token}"}

            # Attempt approve
            res_appr = client.post(
                f"{settings.API_PREFIX}/violations/TG-2026-8941/approve-draft",
                json={"reviewerName": "Camera Operator"},
                headers=op_headers,
            )
            assert res_appr.status_code == 403
            assert res_appr.json()["error_code"] == "FORBIDDEN"

            # Attempt reject
            res_rej = client.post(
                f"{settings.API_PREFIX}/violations/TG-2026-8941/reject",
                json={"reviewerName": "Camera Operator", "reason": "Unauthorized attempt"},
                headers=op_headers,
            )
            assert res_rej.status_code == 403
            assert res_rej.json()["error_code"] == "FORBIDDEN"

        finally:
            db[COLLECTION_USERS].delete_many({"email": op_email})

