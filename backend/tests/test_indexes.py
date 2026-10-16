"""
Unit tests for Index Definitions across all 11 collections.

Verifies:
- Complete index coverage for all collections
- Unique constraints on primary entities
- Partial unique index on violations.challanDraftNumber
- Descending order on timestamped queries
- Explicit absence of TTL indexes (no silent deletion of evidence)
"""

import pytest
from pymongo import ASCENDING, DESCENDING
from app.db.collections import ALL_COLLECTIONS
from app.db.indexes import (
    COLLECTION_INDEXES,
    USERS_INDEXES,
    CAMERAS_INDEXES,
    VIOLATIONS_INDEXES,
    AUDIT_LOGS_INDEXES,
    PERSONS_INDEXES,
    VEHICLES_INDEXES,
    PERSON_VEHICLES_INDEXES,
    SYSTEM_SETTINGS_INDEXES,
    NOTIFICATIONS_INDEXES,
    OFFICER_SHIFTS_INDEXES,
    MODEL_RUNS_INDEXES,
)


class TestIndexDefinitions:
    """Verifies index configurations, uniqueness, and partial filters."""

    def test_all_11_collections_have_index_models(self):
        """Verify that every collection has an index list registered."""
        for col_name in ALL_COLLECTIONS:
            assert col_name in COLLECTION_INDEXES
            assert len(COLLECTION_INDEXES[col_name]) > 0

    def test_unique_indexes_configured(self):
        """Verify unique indexes on critical identifiers."""
        # Users email and employeeId
        user_keys = [dict(m.document["key"]) for m in USERS_INDEXES if m.document.get("unique")]
        assert {"email": ASCENDING} in user_keys
        assert {"employeeId": ASCENDING} in user_keys

        # Persons personReference
        person_keys = [dict(m.document["key"]) for m in PERSONS_INDEXES if m.document.get("unique")]
        assert {"personReference": ASCENDING} in person_keys

        # Vehicles plateNumber
        vehicle_keys = [dict(m.document["key"]) for m in VEHICLES_INDEXES if m.document.get("unique")]
        assert {"plateNumber": ASCENDING} in vehicle_keys

        # System settings key
        settings_keys = [dict(m.document["key"]) for m in SYSTEM_SETTINGS_INDEXES if m.document.get("unique")]
        assert {"key": ASCENDING} in settings_keys

        # Person vehicles relationship compound uniqueness
        pv_keys = [dict(m.document["key"]) for m in PERSON_VEHICLES_INDEXES if m.document.get("unique")]
        assert {"personId": ASCENDING, "vehicleId": ASCENDING, "relationshipType": ASCENDING} in pv_keys

    def test_violations_partial_unique_index(self):
        """Verify partialFilterExpression on challanDraftNumber."""
        draft_indexes = [
            m for m in VIOLATIONS_INDEXES
            if "challanDraftNumber" in dict(m.document["key"])
        ]
        assert len(draft_indexes) == 1
        draft_idx = draft_indexes[0]
        doc = draft_idx.document

        assert doc.get("unique") is True
        filter_expr = doc.get("partialFilterExpression")
        assert filter_expr is not None
        assert "challanDraftNumber" in filter_expr
        assert filter_expr["challanDraftNumber"].get("$type") == "string"

    def test_compound_descending_timestamp_indexes(self):
        """Verify query optimization with descending timestamp keys."""
        # Violations status + capturedAt
        violation_keys = [list(m.document["key"].items()) for m in VIOLATIONS_INDEXES]
        assert [("status", ASCENDING), ("capturedAt", DESCENDING)] in violation_keys
        assert [("cameraId", ASCENDING), ("capturedAt", DESCENDING)] in violation_keys

        # Audit logs entity + timestamp
        audit_keys = [list(m.document["key"].items()) for m in AUDIT_LOGS_INDEXES]
        assert [("entityType", ASCENDING), ("entityId", ASCENDING), ("timestamp", DESCENDING)] in audit_keys
        assert [("actorUserId", ASCENDING), ("timestamp", DESCENDING)] in audit_keys

    def test_no_ttl_indexes_exist(self):
        """
        Verify that NO index has expireAfterSeconds.
        Traffic enforcement data and evidence must never be silently purged.
        """
        for col_name, models in COLLECTION_INDEXES.items():
            for m in models:
                assert "expireAfterSeconds" not in m.document, (
                    f"Forbidden TTL index found on collection '{col_name}' index '{m.document.get('name')}'"
                )
