"""
Integration Tests for MongoDB Live Instance.

REQUIREMENT:
These integration tests require an active MongoDB server running at MONGO_URI
(default: mongodb://localhost:27017).

If MongoDB is not reachable within 500ms, this test module skips gracefully
with an informative skip reason, allowing offline/mocked test suites to pass.
"""

import pytest
from datetime import datetime, timezone
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, WriteError, DuplicateKeyError
from bson import ObjectId

from app.config import settings
from app.db.init_db import initialize_database
from app.db.collections import COLLECTION_USERS, COLLECTION_VIOLATIONS

TEST_DB_NAME = "test_trafficguard_isolated_integration_db"


def _is_mongodb_available() -> bool:
    """Attempts a quick 500ms ping to check if live MongoDB is reachable."""
    try:
        client = MongoClient(
            settings.MONGO_URI,
            serverSelectionTimeoutMS=500,
            connectTimeoutMS=500,
        )
        client.admin.command("ping")
        client.close()
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError, Exception):
        return False


@pytest.fixture(scope="module")
def live_test_db():
    """Initializes a clean isolated test database and drops it after module tests finish."""
    if not _is_mongodb_available():
        pytest.skip(
            f"Live MongoDB instance is not reachable at '{settings.MONGO_URI}'. "
            "Start MongoDB locally to run live integration tests."
        )

    client = MongoClient(settings.MONGO_URI, tz_aware=True)
    test_db = client[TEST_DB_NAME]
    client.drop_database(TEST_DB_NAME)

    # Run full initialization
    report = initialize_database(db=test_db)
    assert report["success"] is True

    yield test_db

    # Clean up only the isolated test database
    client.drop_database(TEST_DB_NAME)
    client.close()


class TestLiveMongoIntegration:
    """Live integration tests requiring an actual running MongoDB server."""

    def test_live_schema_rejects_invalid_enum(self, live_test_db):
        """Live MongoDB JSON Schema validator must reject invalid violationType enum."""
        invalid_doc = {
            "cameraId": ObjectId(),
            "capturedAt": datetime.now(timezone.utc),
            "violationType": "SPEEDING_100KMPH",  # INVALID
            "confidence": 0.85,
            "status": "PENDING_REVIEW",
            "evidence": {"storagePath": "/test/frame.jpg"},
            "evidenceQuality": "HIGH",
            "boundingBoxes": [{"className": "RIDER"}],
            "identityVerificationStatus": "UNVERIFIED",
            "createdAt": datetime.now(timezone.utc),
            "updatedAt": datetime.now(timezone.utc),
        }
        with pytest.raises(WriteError) as exc_info:
            live_test_db[COLLECTION_VIOLATIONS].insert_one(invalid_doc)
        assert "Document failed validation" in str(exc_info.value)

    def test_live_unique_index_enforces_unique_email(self, live_test_db):
        """Live MongoDB unique index must reject duplicate employee email."""
        user1 = {
            "employeeId": "TG-EMP-1001",
            "name": "Officer One",
            "email": "unique.officer@traffic.gov.in",
            "passwordHash": "hash123",
            "role": "reviewer",
            "status": "ACTIVE",
            "createdAt": datetime.now(timezone.utc),
            "updatedAt": datetime.now(timezone.utc),
        }
        live_test_db[COLLECTION_USERS].insert_one(user1)

        user2 = {
            "employeeId": "TG-EMP-1002",
            "name": "Officer Two",
            "email": "unique.officer@traffic.gov.in",  # DUPLICATE EMAIL
            "passwordHash": "hash456",
            "role": "reviewer",
            "status": "ACTIVE",
            "createdAt": datetime.now(timezone.utc),
            "updatedAt": datetime.now(timezone.utc),
        }
        with pytest.raises(DuplicateKeyError):
            live_test_db[COLLECTION_USERS].insert_one(user2)
