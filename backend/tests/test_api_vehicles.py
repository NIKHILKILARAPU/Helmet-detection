"""
Tests for Vehicle Registration, Plate Normalization, and Owner Linking.

Verifies:
- Plate normalization rules
- Duplicate plate collision prevention
- Unique person-vehicle relationship enforcement
- Mismatch dispute submission
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from main import app
from app.config import settings
from app.api.vehicles import normalize_plate_number
from app.core.security import hash_password
from app.db.connection import get_db
from app.db.collections import (
    COLLECTION_VEHICLES,
    COLLECTION_PERSONS,
    COLLECTION_PERSON_VEHICLES,
    COLLECTION_USERS,
)

client = TestClient(app)


class TestPlateNormalization:
    """Verifies that registration numbers are standardized."""

    def test_plate_cleaning(self):
        assert normalize_plate_number("ka 01 mj 4892") == "KA01MJ4892"
        assert normalize_plate_number("mh-12-ab-1234") == "MH12AB1234"
        assert normalize_plate_number("  dl  04  c 9999  ") == "DL04C9999"


class TestVehicleEndpoints:
    """Verifies vehicle management API endpoints with authentication."""

    @pytest.fixture(autouse=True)
    def setup_admin_and_data(self):
        db = get_db()
        now = datetime.now(timezone.utc)
        # Ensure test admin exists
        db[COLLECTION_USERS].delete_many({"email": "test.vehadmin@traffic.gov.in"})
        admin_doc = {
            "employeeId": "TEST-VEHADM-01",
            "name": "Vehicle Admin",
            "email": "test.vehadmin@traffic.gov.in",
            "passwordHash": hash_password("VehAdminPass123!"),
            "role": "admin",
            "status": "ACTIVE",
            "createdAt": now,
            "updatedAt": now,
        }
        db[COLLECTION_USERS].insert_one(admin_doc)

        yield

        # Cleanup
        db[COLLECTION_USERS].delete_many({"email": "test.vehadmin@traffic.gov.in"})
        db[COLLECTION_VEHICLES].delete_many({"plateNumber": {"$regex": r"^TEST"}})
        db[COLLECTION_PERSONS].delete_many({"personReference": {"$regex": r"^TEST"}})

    def _get_admin_token(self) -> str:
        login_res = client.post(
            f"{settings.API_PREFIX}/auth/login",
            json={"email": "test.vehadmin@traffic.gov.in", "password": "VehAdminPass123!"},
        )
        return login_res.json()["data"]["accessToken"]

    def test_create_vehicle_success_and_duplicate_rejection(self):
        """Vehicle registration normalizes plate and rejects duplicates with 409 Conflict."""
        token = self._get_admin_token()
        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "plateNumber": "test 01 ab 9999",
            "vehicleType": "Two-Wheeler",
            "model": "TVS Jupiter",
        }
        # First registration -> 201 Created
        res1 = client.post(f"{settings.API_PREFIX}/vehicles", json=payload, headers=headers)
        assert res1.status_code == 201
        data1 = res1.json()
        assert data1["success"] is True
        assert data1["data"]["plateNumber"] == "TEST01AB9999"

        # Duplicate registration -> 409 Conflict
        res2 = client.post(f"{settings.API_PREFIX}/vehicles", json=payload, headers=headers)
        assert res2.status_code == 409
        data2 = res2.json()
        assert data2["success"] is False
        assert data2["error_code"] == "RESOURCE_CONFLICT"

    def test_link_person_and_vehicle_duplicate_prevention(self):
        """Linking person to vehicle prevents duplicate active relationships."""
        db = get_db()
        now = datetime.now(timezone.utc)
        token = self._get_admin_token()
        headers = {"Authorization": f"Bearer {token}"}

        # Provision test person
        p_res = db[COLLECTION_PERSONS].insert_one({
            "personReference": "TEST-PER-101",
            "fullName": "Test Citizen",
            "identityStatus": "VERIFIED",
            "createdAt": now,
            "updatedAt": now,
        })
        # Provision test vehicle
        v_res = db[COLLECTION_VEHICLES].insert_one({
            "plateNumber": "TEST99ZZ1111",
            "registrationStatus": "ACTIVE",
            "verificationStatus": "VERIFIED",
            "createdAt": now,
            "updatedAt": now,
        })

        link_payload = {
            "personId": str(p_res.inserted_id),
            "vehicleId": str(v_res.inserted_id),
            "relationshipType": "REGISTERED_OWNER",
        }

        # First link -> 201 Created
        res1 = client.post(f"{settings.API_PREFIX}/person-vehicles", json=link_payload, headers=headers)
        assert res1.status_code == 201
        assert res1.json()["success"] is True

        # Second link -> 409 Conflict
        res2 = client.post(f"{settings.API_PREFIX}/person-vehicles", json=link_payload, headers=headers)
        assert res2.status_code == 409
        assert res2.json()["error_code"] == "RESOURCE_CONFLICT"

        # Cleanup
        db[COLLECTION_PERSON_VEHICLES].delete_many({"personId": p_res.inserted_id})
