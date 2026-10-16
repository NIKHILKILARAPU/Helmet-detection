"""
Unit tests for MongoDB JSON Schema Validators.

Tests:
- Schema presence for all 11 collections
- Required fields definitions
- Enum validity and rejection of invalid enum values
- Numeric constraints (confidence in [0, 1], non-negative penalties, positive retention days)
- Direct JSON schema validation behavior using jsonschema
"""

import copy
import pytest
import jsonschema
from bson import ObjectId
from app.db.collections import (
    ALL_COLLECTIONS,
    COLLECTION_USERS,
    COLLECTION_CAMERAS,
    COLLECTION_VIOLATIONS,
    COLLECTION_AUDIT_LOGS,
    COLLECTION_PERSONS,
    COLLECTION_VEHICLES,
    COLLECTION_PERSON_VEHICLES,
    COLLECTION_SYSTEM_SETTINGS,
    COLLECTION_NOTIFICATIONS,
    COLLECTION_OFFICER_SHIFTS,
    COLLECTION_MODEL_RUNS,
)
from app.db.schemas import (
    COLLECTION_SCHEMAS,
    USERS_SCHEMA,
    VIOLATIONS_SCHEMA,
    SYSTEM_SETTINGS_SCHEMA,
    CAMERAS_SCHEMA,
    AUDIT_LOGS_SCHEMA,
)


def _convert_bson_schema_to_json_schema(bson_schema: dict) -> dict:
    """
    Helper converting MongoDB $jsonSchema bsonType directives to standard JSON Schema types
    so that unit tests can validate documents in memory without a live MongoDB server.
    """
    json_schema = copy.deepcopy(bson_schema.get("$jsonSchema", bson_schema))

    def _replace_bson_types(node):
        if isinstance(node, dict):
            if "bsonType" in node:
                b_type = node.pop("bsonType")
                if isinstance(b_type, list):
                    mapped = []
                    for t in b_type:
                        if t in ("objectId", "date", "string"):
                            mapped.append("string")
                        elif t in ("int", "long", "double"):
                            mapped.append("number")
                        elif t == "bool":
                            mapped.append("boolean")
                        elif t == "null":
                            mapped.append("null")
                        else:
                            mapped.append(t)
                    node["type"] = mapped
                else:
                    if b_type in ("objectId", "date", "string"):
                        node["type"] = "string"
                    elif b_type in ("int", "long", "double"):
                        node["type"] = "number"
                    elif b_type == "bool":
                        node["type"] = "boolean"
                    else:
                        node["type"] = b_type
            for k, v in node.items():
                _replace_bson_types(v)
        elif isinstance(node, list):
            for item in node:
                _replace_bson_types(item)

    _replace_bson_types(json_schema)
    return json_schema


class TestSchemaDefinitions:
    """Tests schema structure and compliance for all 11 collections."""

    def test_all_11_collections_have_schemas(self):
        """Verify that every required collection has an associated JSON Schema."""
        assert len(ALL_COLLECTIONS) == 11
        for col_name in ALL_COLLECTIONS:
            assert col_name in COLLECTION_SCHEMAS, f"Missing schema for collection '{col_name}'"
            schema = COLLECTION_SCHEMAS[col_name]
            assert "$jsonSchema" in schema
            assert schema["$jsonSchema"]["bsonType"] == "object"
            assert "required" in schema["$jsonSchema"]
            assert len(schema["$jsonSchema"]["required"]) > 0

    def test_users_schema_required_fields_and_enums(self):
        """Verify users schema required fields, unique patterns, and role enums."""
        props = USERS_SCHEMA["$jsonSchema"]["properties"]
        required = USERS_SCHEMA["$jsonSchema"]["required"]

        for expected_field in [
            "employeeId",
            "name",
            "email",
            "passwordHash",
            "role",
            "status",
            "createdAt",
            "updatedAt",
        ]:
            assert expected_field in required

        assert props["role"]["enum"] == ["admin", "reviewer", "operator", "supervisor"]
        assert props["status"]["enum"] == ["ACTIVE", "INACTIVE"]

    def test_violations_schema_enums_and_ranges(self):
        """Verify violationType, status, confidence bounds, and draft penalty constraints."""
        props = VIOLATIONS_SCHEMA["$jsonSchema"]["properties"]
        required = VIOLATIONS_SCHEMA["$jsonSchema"]["required"]

        assert "cameraId" in required
        assert "violationType" in required
        assert "confidence" in required
        assert "status" in required
        assert "evidence" in required

        # Violation type enum
        assert set(props["violationType"]["enum"]) == {
            "NO_HELMET_RIDER",
            "NO_HELMET_PILLION",
            "TRIPLE_RIDING",
            "HELMET_STRAP_UNFASTENED",
        }

        # Status enum
        assert set(props["status"]["enum"]) == {
            "PENDING_REVIEW",
            "DRAFT_CREATED",
            "REJECTED",
            "REVIEWED",
        }

        # Confidence boundary [0.0, 1.0]
        assert props["confidence"]["minimum"] == 0.0
        assert props["confidence"]["maximum"] == 1.0

        # Draft penalty must be non-negative
        assert props["draftAmountInr"]["minimum"] == 0

    def test_system_settings_numeric_constraints(self):
        """Verify confidence threshold and retention days bounds."""
        props = SYSTEM_SETTINGS_SCHEMA["$jsonSchema"]["properties"]
        assert props["minConfidenceThreshold"]["minimum"] == 0.0
        assert props["minConfidenceThreshold"]["maximum"] == 1.0
        assert props["dataRetentionDays"]["minimum"] == 1
        assert props["defaultDraftPenaltyInr"]["minimum"] == 0

    def test_cameras_stream_types(self):
        """Verify streamType enum."""
        props = CAMERAS_SCHEMA["$jsonSchema"]["properties"]
        assert set(props["streamType"]["enum"]) == {"WEBCAM", "IP_CAMERA", "CCTV_STREAM"}
        assert set(props["status"]["enum"]) == {"ONLINE", "STANDBY", "DEGRADED", "OFFLINE"}

    def test_audit_logs_entity_types(self):
        """Verify audit log entityType enum covers all expected domains."""
        props = AUDIT_LOGS_SCHEMA["$jsonSchema"]["properties"]
        assert set(props["entityType"]["enum"]) == {
            "violation",
            "camera",
            "user",
            "settings",
            "person",
            "vehicle",
        }


class TestSchemaValidationLogic:
    """Tests document validation and rejection behavior using jsonschema."""

    @pytest.fixture
    def violations_validator(self):
        schema = _convert_bson_schema_to_json_schema(VIOLATIONS_SCHEMA)
        return jsonschema.Draft7Validator(schema)

    @pytest.fixture
    def users_validator(self):
        schema = _convert_bson_schema_to_json_schema(USERS_SCHEMA)
        return jsonschema.Draft7Validator(schema)

    def test_valid_violation_document_passes(self, violations_validator):
        valid_doc = {
            "cameraId": "507f1f77bcf86cd799439011",
            "capturedAt": "2026-10-16T10:00:00Z",
            "violationType": "NO_HELMET_RIDER",
            "confidence": 0.88,
            "status": "PENDING_REVIEW",
            "evidence": {
                "storagePath": "/evidence/2026/10/16/frame_1042.jpg",
                "fileHash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            },
            "evidenceQuality": "HIGH",
            "boundingBoxes": [
                {
                    "className": "NO_HELMET",
                    "confidence": 0.88,
                    "coordinates": {"ymin": 0.1, "xmin": 0.2, "ymax": 0.4, "xmax": 0.5},
                }
            ],
            "identityVerificationStatus": "UNVERIFIED",
            "createdAt": "2026-10-16T10:00:00Z",
            "updatedAt": "2026-10-16T10:00:00Z",
        }
        violations_validator.validate(valid_doc)  # Should not raise

    def test_invalid_violation_enum_fails(self, violations_validator):
        doc = {
            "cameraId": "507f1f77bcf86cd799439011",
            "capturedAt": "2026-10-16T10:00:00Z",
            "violationType": "OVERSPEEDING_HIGHWAY",  # INVALID ENUM
            "confidence": 0.88,
            "status": "PENDING_REVIEW",
            "evidence": {"storagePath": "/path.jpg"},
            "evidenceQuality": "HIGH",
            "boundingBoxes": [{"className": "TEST"}],
            "identityVerificationStatus": "UNVERIFIED",
            "createdAt": "2026-10-16T10:00:00Z",
            "updatedAt": "2026-10-16T10:00:00Z",
        }
        with pytest.raises(jsonschema.ValidationError) as exc:
            violations_validator.validate(doc)
        assert "OVERSPEEDING_HIGHWAY" in str(exc.value)

    def test_invalid_confidence_above_one_fails(self, violations_validator):
        doc = {
            "cameraId": "507f1f77bcf86cd799439011",
            "capturedAt": "2026-10-16T10:00:00Z",
            "violationType": "NO_HELMET_RIDER",
            "confidence": 1.45,  # INVALID: > 1.0
            "status": "PENDING_REVIEW",
            "evidence": {"storagePath": "/path.jpg"},
            "evidenceQuality": "HIGH",
            "boundingBoxes": [{"className": "TEST"}],
            "identityVerificationStatus": "UNVERIFIED",
            "createdAt": "2026-10-16T10:00:00Z",
            "updatedAt": "2026-10-16T10:00:00Z",
        }
        with pytest.raises(jsonschema.ValidationError) as exc:
            violations_validator.validate(doc)
        assert "1.45" in str(exc.value)

    def test_invalid_user_role_fails(self, users_validator):
        doc = {
            "employeeId": "TG-EMP-999",
            "name": "Jane Doe",
            "email": "jane.doe@traffic.gov.in",
            "passwordHash": "$2b$12$hashedpassword",
            "role": "citizen_superadmin",  # INVALID ROLE
            "status": "ACTIVE",
            "createdAt": "2026-10-16T10:00:00Z",
            "updatedAt": "2026-10-16T10:00:00Z",
        }
        with pytest.raises(jsonschema.ValidationError) as exc:
            users_validator.validate(doc)
        assert "citizen_superadmin" in str(exc.value)

    def test_missing_required_user_field_fails(self, users_validator):
        doc = {
            "employeeId": "TG-EMP-999",
            # "name" is missing
            "email": "jane.doe@traffic.gov.in",
            "passwordHash": "$2b$12$hashedpassword",
            "role": "admin",
            "status": "ACTIVE",
            "createdAt": "2026-10-16T10:00:00Z",
            "updatedAt": "2026-10-16T10:00:00Z",
        }
        with pytest.raises(jsonschema.ValidationError) as exc:
            users_validator.validate(doc)
        assert "'name' is a required property" in str(exc.value)
