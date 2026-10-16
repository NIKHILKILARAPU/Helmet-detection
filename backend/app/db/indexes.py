"""
Index definitions for all 11 MongoDB collections in TrafficGuard AI.

Follows government enforcement system performance requirements:
- Compound indexes matching queries with descending timestamps
- Unique constraints on primary entity identifiers
- Partial unique index on challanDraftNumber ensuring only non-null draft numbers are unique
- No TTL indexes: retention is strictly handled by legal policy audits
"""

from typing import Dict, List
from pymongo import IndexModel, ASCENDING, DESCENDING
from app.db.collections import (
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

# 1. users indexes
USERS_INDEXES: List[IndexModel] = [
    IndexModel(
        [("email", ASCENDING)],
        unique=True,
        name="idx_users_email_unique",
    ),
    IndexModel(
        [("employeeId", ASCENDING)],
        unique=True,
        name="idx_users_employee_id_unique",
    ),
    IndexModel(
        [("role", ASCENDING), ("status", ASCENDING)],
        name="idx_users_role_status",
    ),
]

# 2. cameras indexes
CAMERAS_INDEXES: List[IndexModel] = [
    IndexModel(
        [("status", ASCENDING)],
        name="idx_cameras_status",
    ),
    IndexModel(
        [("junction", ASCENDING)],
        name="idx_cameras_junction",
    ),
]

# 3. violations indexes
VIOLATIONS_INDEXES: List[IndexModel] = [
    IndexModel(
        [("status", ASCENDING), ("capturedAt", DESCENDING)],
        name="idx_violations_status_captured_at",
    ),
    IndexModel(
        [("cameraId", ASCENDING), ("capturedAt", DESCENDING)],
        name="idx_violations_camera_captured_at",
    ),
    IndexModel(
        [("violationType", ASCENDING), ("capturedAt", DESCENDING)],
        name="idx_violations_type_captured_at",
    ),
    IndexModel(
        [("personId", ASCENDING), ("capturedAt", DESCENDING)],
        name="idx_violations_person_captured_at",
    ),
    # Partial unique index: applies strictly when challanDraftNumber is a non-empty string
    IndexModel(
        [("challanDraftNumber", ASCENDING)],
        unique=True,
        partialFilterExpression={"challanDraftNumber": {"$type": "string", "$gt": ""}},
        name="idx_violations_challan_draft_number_partial_unique",
    ),
]

# 4. audit_logs indexes
AUDIT_LOGS_INDEXES: List[IndexModel] = [
    IndexModel(
        [("entityType", ASCENDING), ("entityId", ASCENDING), ("timestamp", DESCENDING)],
        name="idx_audit_logs_entity_timestamp",
    ),
    IndexModel(
        [("actorUserId", ASCENDING), ("timestamp", DESCENDING)],
        name="idx_audit_logs_actor_timestamp",
    ),
]

# 5. persons indexes
PERSONS_INDEXES: List[IndexModel] = [
    IndexModel(
        [("personReference", ASCENDING)],
        unique=True,
        name="idx_persons_reference_unique",
    ),
    IndexModel(
        [("identityStatus", ASCENDING)],
        name="idx_persons_identity_status",
    ),
]

# 6. vehicles indexes
VEHICLES_INDEXES: List[IndexModel] = [
    IndexModel(
        [("plateNumber", ASCENDING)],
        unique=True,
        name="idx_vehicles_plate_number_unique",
    ),
]

# 7. person_vehicles indexes
PERSON_VEHICLES_INDEXES: List[IndexModel] = [
    IndexModel(
        [("personId", ASCENDING)],
        name="idx_person_vehicles_person_id",
    ),
    IndexModel(
        [("vehicleId", ASCENDING)],
        name="idx_person_vehicles_vehicle_id",
    ),
    # Unique compound index to prevent duplicate relationships of the same type
    IndexModel(
        [("personId", ASCENDING), ("vehicleId", ASCENDING), ("relationshipType", ASCENDING)],
        unique=True,
        name="idx_person_vehicles_compound_unique",
    ),
]

# 8. system_settings indexes
SYSTEM_SETTINGS_INDEXES: List[IndexModel] = [
    IndexModel(
        [("key", ASCENDING)],
        unique=True,
        name="idx_system_settings_key_unique",
    ),
]

# 9. notifications indexes
NOTIFICATIONS_INDEXES: List[IndexModel] = [
    IndexModel(
        [("personId", ASCENDING), ("date", DESCENDING)],
        name="idx_notifications_person_date",
    ),
    IndexModel(
        [("status", ASCENDING)],
        name="idx_notifications_status",
    ),
]

# 10. officer_shifts indexes
OFFICER_SHIFTS_INDEXES: List[IndexModel] = [
    IndexModel(
        [("officerId", ASCENDING), ("shiftStart", DESCENDING)],
        name="idx_officer_shifts_officer_start",
    ),
]

# 11. model_runs indexes
MODEL_RUNS_INDEXES: List[IndexModel] = [
    IndexModel(
        [("cameraId", ASCENDING), ("processedAt", DESCENDING)],
        name="idx_model_runs_camera_processed_at",
    ),
    IndexModel(
        [("status", ASCENDING)],
        name="idx_model_runs_status",
    ),
]

# Index map for all collections
COLLECTION_INDEXES: Dict[str, List[IndexModel]] = {
    COLLECTION_USERS: USERS_INDEXES,
    COLLECTION_CAMERAS: CAMERAS_INDEXES,
    COLLECTION_VIOLATIONS: VIOLATIONS_INDEXES,
    COLLECTION_AUDIT_LOGS: AUDIT_LOGS_INDEXES,
    COLLECTION_PERSONS: PERSONS_INDEXES,
    COLLECTION_VEHICLES: VEHICLES_INDEXES,
    COLLECTION_PERSON_VEHICLES: PERSON_VEHICLES_INDEXES,
    COLLECTION_SYSTEM_SETTINGS: SYSTEM_SETTINGS_INDEXES,
    COLLECTION_NOTIFICATIONS: NOTIFICATIONS_INDEXES,
    COLLECTION_OFFICER_SHIFTS: OFFICER_SHIFTS_INDEXES,
    COLLECTION_MODEL_RUNS: MODEL_RUNS_INDEXES,
}
