"""
Unit tests for Database Initialization Logic and Idempotency.

Tests:
- Collection creation with validator when missing
- Validator modification (collMod) when collection exists
- Idempotent index creation
- Default settings seeding and preservation
- Complete repeatable initialization execution
"""

import pytest
from unittest.mock import MagicMock
from pymongo.errors import OperationFailure
from app.db.init_db import (
    apply_collection_validator,
    apply_collection_indexes,
    seed_default_settings,
    initialize_database,
)
from app.db.collections import (
    ALL_COLLECTIONS,
    COLLECTION_SYSTEM_SETTINGS,
    COLLECTION_USERS,
)
from app.db.default_settings import DEFAULT_SETTINGS_KEY


class TestInitDbFunctions:
    """Tests modular database initialization steps using mocked PyMongo database."""

    def test_apply_validator_creates_missing_collection(self):
        """If collection is missing, create_collection should be invoked."""
        mock_db = MagicMock()
        mock_db.list_collection_names.return_value = []

        schema = {"$jsonSchema": {"bsonType": "object"}}
        status = apply_collection_validator(mock_db, "users", schema)

        assert status == "created"
        mock_db.create_collection.assert_called_once_with(
            "users",
            validator=schema,
            validationLevel="strict",
            validationAction="error",
        )

    def test_apply_validator_updates_existing_collection(self):
        """If collection exists, collMod command should be invoked."""
        mock_db = MagicMock()
        mock_db.list_collection_names.return_value = ["users"]

        schema = {"$jsonSchema": {"bsonType": "object"}}
        status = apply_collection_validator(mock_db, "users", schema)

        assert status == "updated"
        mock_db.command.assert_called_once_with(
            "collMod",
            "users",
            validator=schema,
            validationLevel="strict",
            validationAction="error",
        )

    def test_apply_indexes_calls_create_indexes(self):
        """create_indexes should be called on the collection."""
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_db.__getitem__.return_value = mock_col
        mock_col.create_indexes.return_value = ["idx_email_1"]

        mock_model = MagicMock()
        result = apply_collection_indexes(mock_db, "users", [mock_model])

        assert result == ["idx_email_1"]
        mock_col.create_indexes.assert_called_once_with([mock_model])

    def test_apply_indexes_handles_operation_failure(self):
        """Gracefully isolates index creation if batch index creation encounters a conflict."""
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_db.__getitem__.return_value = mock_col

        mock_col.create_indexes.side_effect = [
            OperationFailure("Index options conflict"),
            ["idx_fallback_1"],
        ]

        mock_model = MagicMock()
        mock_model.document = {"name": "idx_fallback_1"}
        result = apply_collection_indexes(mock_db, "users", [mock_model])

        assert "idx_fallback_1" in result

    def test_seed_default_settings_when_missing(self):
        """When default settings do not exist, insert_one is called."""
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_db.__getitem__.return_value = mock_col
        mock_col.find_one.return_value = None  # None found
        mock_insert_res = MagicMock()
        mock_insert_res.inserted_id = "mock_obj_id"
        mock_col.insert_one.return_value = mock_insert_res

        status = seed_default_settings(mock_db)

        assert status == "seeded"
        mock_col.insert_one.assert_called_once()
        inserted_doc = mock_col.insert_one.call_args[0][0]
        assert inserted_doc["key"] == DEFAULT_SETTINGS_KEY
        assert inserted_doc["minConfidenceThreshold"] == 0.55
        assert inserted_doc["dataRetentionDays"] == 90

    def test_seed_default_settings_preserves_existing(self):
        """When default settings exist, do not overwrite or duplicate."""
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_db.__getitem__.return_value = mock_col
        mock_col.find_one.return_value = {"_id": "existing", "key": DEFAULT_SETTINGS_KEY}

        status = seed_default_settings(mock_db)

        assert status == "already_present"
        mock_col.insert_one.assert_not_called()

    def test_initialize_database_full_run_mocked(self):
        """Test full initialize_database workflow across all 11 collections."""
        mock_db = MagicMock()
        mock_db.name = "helmet_challan_db"
        mock_db.list_collection_names.return_value = []
        mock_col = MagicMock()
        mock_db.__getitem__.return_value = mock_col
        mock_col.create_indexes.return_value = ["mock_idx"]
        mock_col.find_one.return_value = None

        report = initialize_database(db=mock_db)

        assert report["success"] is True
        assert report["database_name"] == "helmet_challan_db"
        assert len(report["collections"]) == len(ALL_COLLECTIONS)
        assert report["settings_status"] == "seeded"
