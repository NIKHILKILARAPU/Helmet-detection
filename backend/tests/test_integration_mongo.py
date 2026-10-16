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

TEST_DB_NAME = "test_trafficguard_integration_db"


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


@pytest.mark.skipif(
    not _is_mongodb_available(),
    reason="[INTEGRATION TEST SKIPPED] Live MongoDB instance is not reachable at "
           f"'{settings.MONGO_URI}'. Start MongoDB locally or provide valid MONGO_URI to run."
)
class TestLiveMongoIntegration:
    """Live integration tests requiring an actual running MongoDB server."""

    @pytest.fixture(scope="class", autouse=True)
    def setup_and_teardown_test_db(self):
        """Initializes a clean test database and tears it down after tests finish."""
        client = MongoClient(settings.MONGO_URI, tz_aware=True)
        test_db = client[TEST_DB_NAME]
        client.drop_database(TEST_DB_NAME)

        # Run full initialization
        report = initialize_database(db=test_db)
        assert report["success"] is True

        yield test_db

        # Clean up test database
        client.drop_database(TEST_DB_NAME)
        client.close()

    def test_live_schema_rejects_invalid_enum(self, setup_and_teardown_test_db):
        """Live MongoDB JSON Schema validator must reject invalid violationType enum."""
        test_db = setup_and_teardown_test_db
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
            test_db[COLLECTION_VIOLATIONS].insert_one(invalid_doc)
        assert "Document failed validation" in str(exc_info.value)

    def test_live_unique_index_enforces_unique_email(self, setup_and_teardown_test_db):
        """Live MongoDB unique index must reject duplicate employee email."""
        test_db = setup_and_teardown_test_db
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
        test_db[COLLECTION_USERS].insert_one(user1)

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
            test_db[COLLECTION_USERS].insert_one(user2)
