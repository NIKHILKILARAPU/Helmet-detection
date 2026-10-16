"""
MongoDB JSON Schema Validators for all 11 collections.

Each collection schema strictly defines:
- bsonType constraints
- Required fields
- Allowed enum values
- Numeric boundaries (confidence [0, 1], non-negative amounts, etc.)
- Metadata and structured evidence objects
"""

from typing import Dict, Any
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

# 1. users collection validator
USERS_SCHEMA: Dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "employeeId",
            "name",
            "email",
            "passwordHash",
            "role",
            "status",
            "createdAt",
            "updatedAt",
        ],
        "properties": {
            "_id": {"bsonType": "objectId"},
            "employeeId": {
                "bsonType": "string",
                "description": "Unique employee identification code (e.g. TG-ADM-001)",
            },
            "name": {
                "bsonType": "string",
                "description": "Full name of the officer or staff member",
            },
            "email": {
                "bsonType": "string",
                "pattern": r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
                "description": "Unique official government email address",
            },
            "passwordHash": {
                "bsonType": "string",
                "description": "Bcrypt/Argon2 hashed password",
            },
            "role": {
                "enum": ["admin", "reviewer", "operator", "supervisor"],
                "description": "Authorized government role",
            },
            "department": {
                "bsonType": ["string", "null"],
                "description": "Assigned division or traffic zone",
            },
            "rank": {
                "bsonType": ["string", "null"],
                "description": "Official police rank designation",
            },
            "status": {
                "enum": ["ACTIVE", "INACTIVE"],
                "description": "Account activation status",
            },
            "lastLoginAt": {
                "bsonType": ["date", "null"],
                "description": "Timestamp of most recent authentication",
            },
            "createdAt": {"bsonType": "date"},
            "updatedAt": {"bsonType": "date"},
        },
    }
}

# 2. cameras collection validator
CAMERAS_SCHEMA: Dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "name",
            "junction",
            "streamType",
            "status",
            "createdBy",
            "createdAt",
            "updatedAt",
        ],
        "properties": {
            "_id": {"bsonType": "objectId"},
            "name": {
                "bsonType": "string",
                "description": "Descriptive camera name / identifier",
            },
            "junction": {
                "bsonType": "string",
                "description": "Physical junction or checkpoint name",
            },
            "streamType": {
                "enum": ["WEBCAM", "IP_CAMERA", "CCTV_STREAM"],
                "description": "Camera source feed type",
            },
            "source": {
                "bsonType": ["string", "null"],
                "description": "Safe source reference (device index or network URI identifier; no plaintext secrets)",
            },
            "resolution": {
                "bsonType": ["string", "null"],
                "description": "Optical capture resolution (e.g. 1080p, 4K)",
            },
            "fps": {
                "bsonType": ["int", "long", "double", "null"],
                "minimum": 0,
                "description": "Frame capture rate per second",
            },
            "status": {
                "enum": ["ONLINE", "STANDBY", "DEGRADED", "OFFLINE"],
                "description": "Operational connectivity status",
            },
            "lastHeartbeatAt": {
                "bsonType": ["date", "null"],
                "description": "Last ping timestamp received from camera hardware",
            },
            "createdBy": {
                "bsonType": "objectId",
                "description": "Reference to users collection for auditability",
            },
            "createdAt": {"bsonType": "date"},
            "updatedAt": {"bsonType": "date"},
        },
    }
}

# 3. violations collection validator
VIOLATIONS_SCHEMA: Dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "cameraId",
            "capturedAt",
            "violationType",
            "confidence",
            "status",
            "evidence",
            "evidenceQuality",
            "boundingBoxes",
            "identityVerificationStatus",
            "createdAt",
            "updatedAt",
        ],
        "properties": {
            "_id": {"bsonType": "objectId"},
            "cameraId": {
                "bsonType": "objectId",
                "description": "Reference to cameras collection",
            },
            "capturedAt": {
                "bsonType": "date",
                "description": "Timestamp when frame was captured",
            },
            "violationType": {
                "enum": [
                    "NO_HELMET_RIDER",
                    "NO_HELMET_PILLION",
                    "TRIPLE_RIDING",
                    "HELMET_STRAP_UNFASTENED",
                ],
                "description": "Classified violation category",
            },
            "confidence": {
                "bsonType": ["double", "int"],
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Model confidence score between 0.0 and 1.0",
            },
            "status": {
                "enum": ["PENDING_REVIEW", "DRAFT_CREATED", "REJECTED", "REVIEWED"],
                "description": "Triage status; defaults to PENDING_REVIEW",
            },
            "evidence": {
                "bsonType": "object",
                "required": ["storagePath"],
                "properties": {
                    "storagePath": {
                        "bsonType": "string",
                        "description": "File system or object store URI reference (never large binary blob)",
                    },
                    "fileHash": {
                        "bsonType": ["string", "null"],
                        "description": "SHA-256 integrity hash of captured frame",
                    },
                    "mimeType": {"bsonType": ["string", "null"]},
                    "width": {"bsonType": ["int", "long", "null"]},
                    "height": {"bsonType": ["int", "long", "null"]},
                    "fileSizeBytes": {"bsonType": ["int", "long", "null"]},
                },
                "description": "Structured storage reference and optical metadata",
            },
            "evidenceQuality": {
                "enum": ["HIGH", "MEDIUM", "LOW"],
                "description": "Optical sharpness and ambient lighting assessment",
            },
            "boundingBoxes": {
                "bsonType": "array",
                "items": {
                    "bsonType": "object",
                    "required": ["className"],
                    "properties": {
                        "className": {"bsonType": "string"},
                        "confidence": {
                            "bsonType": ["double", "int", "null"],
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                        "coordinates": {
                            "bsonType": ["object", "array"],
                            "description": "Normalized coordinates [ymin, xmin, ymax, xmax] or {x, y, w, h}",
                        },
                    },
                },
                "description": "List of AI detection bounding boxes",
            },
            "personId": {
                "bsonType": ["objectId", "null"],
                "description": "Reference to persons collection if verified via registration lookup",
            },
            "vehicleId": {
                "bsonType": ["objectId", "null"],
                "description": "Reference to vehicles collection",
            },
            "identityVerificationStatus": {
                "enum": ["VERIFIED", "UNVERIFIED", "MANUAL_REQUIRED"],
                "description": "Status of authorized registry matching (never facial recognition)",
            },
            "reviewerNotes": {
                "bsonType": ["string", "null"],
                "description": "Human review officer observations",
            },
            "rejectionReason": {
                "bsonType": ["string", "null"],
                "description": "Mandatory documented cause when rejected",
            },
            "challanDraftNumber": {
                "bsonType": ["string", "null"],
                "description": "Provisional draft number (e.g. TG-DRAFT-2026-8941)",
            },
            "draftAmountInr": {
                "bsonType": ["double", "int", "long", "null"],
                "minimum": 0,
                "description": "Non-negative draft penalty estimate in INR",
            },
            "reviewedBy": {
                "bsonType": ["objectId", "null"],
                "description": "Reference to users collection for the review officer",
            },
            "reviewedAt": {
                "bsonType": ["date", "null"],
                "description": "Timestamp of officer review action",
            },
            "createdAt": {"bsonType": "date"},
            "updatedAt": {"bsonType": "date"},
        },
    }
}

# 4. audit_logs collection validator
AUDIT_LOGS_SCHEMA: Dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "timestamp",
            "action",
            "entityType",
            "entityId",
            "metadata",
        ],
        "properties": {
            "_id": {"bsonType": "objectId"},
            "timestamp": {
                "bsonType": "date",
                "description": "Immutable event timestamp",
            },
            "actorUserId": {
                "bsonType": ["objectId", "null"],
                "description": "Reference to users collection",
            },
            "actorNameSnapshot": {
                "bsonType": ["string", "null"],
                "description": "Name snapshot at time of event",
            },
            "actorRoleSnapshot": {
                "bsonType": ["string", "null"],
                "description": "Role snapshot at time of event",
            },
            "action": {
                "bsonType": "string",
                "description": "Action performed (e.g. DRAFT_APPROVED, CASE_REJECTED, POLICY_UPDATED)",
            },
            "entityType": {
                "enum": ["violation", "camera", "user", "settings", "person", "vehicle"],
                "description": "Target domain entity type",
            },
            "entityId": {
                "bsonType": "string",
                "description": "Target identifier string",
            },
            "notes": {"bsonType": ["string", "null"]},
            "reason": {"bsonType": ["string", "null"]},
            "metadata": {
                "bsonType": "object",
                "description": "Structured event context and diff payload",
            },
            "requestId": {
                "bsonType": ["string", "null"],
                "description": "HTTP request correlation trace ID",
            },
        },
    }
}

# 5. persons collection validator
PERSONS_SCHEMA: Dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "personReference",
            "fullName",
            "identityStatus",
            "createdAt",
            "updatedAt",
        ],
        "properties": {
            "_id": {"bsonType": "objectId"},
            "personReference": {
                "bsonType": "string",
                "description": "Unique internal person reference (e.g. TG-CIT-0104)",
            },
            "fullName": {
                "bsonType": "string",
                "description": "Full legal name per official registration",
            },
            "mobile": {
                "bsonType": ["string", "null"],
                "description": "Registered contact number (masked in UI by policy)",
            },
            "email": {"bsonType": ["string", "null"]},
            "city": {"bsonType": ["string", "null"]},
            "identityStatus": {
                "enum": ["VERIFIED", "UNVERIFIED", "MANUAL_REQUIRED"],
                "description": "Government registry verification status",
            },
            "verificationSource": {
                "bsonType": ["string", "null"],
                "description": "Authority source (e.g. STATE_VAHAN_PORTAL)",
            },
            "createdAt": {"bsonType": "date"},
            "updatedAt": {"bsonType": "date"},
        },
    }
}

# 6. vehicles collection validator
VEHICLES_SCHEMA: Dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "plateNumber",
            "registrationStatus",
            "verificationStatus",
            "createdAt",
            "updatedAt",
        ],
        "properties": {
            "_id": {"bsonType": "objectId"},
            "plateNumber": {
                "bsonType": "string",
                "description": "Normalized uppercase registration plate string",
            },
            "vehicleType": {
                "bsonType": ["string", "null"],
                "description": "Vehicle classification (e.g. Two-Wheeler Motorcycle, Scooter)",
            },
            "model": {
                "bsonType": ["string", "null"],
                "description": "Make and model description",
            },
            "registeredDate": {"bsonType": ["date", "null"]},
            "registrationStatus": {
                "enum": ["ACTIVE", "EXPIRED", "FLAGGED"],
                "description": "Vehicle registry standing",
            },
            "verificationStatus": {
                "enum": ["VERIFIED", "UNVERIFIED", "MANUAL_REQUIRED"],
                "description": "Plate verification status",
            },
            "createdAt": {"bsonType": "date"},
            "updatedAt": {"bsonType": "date"},
        },
    }
}

# 7. person_vehicles collection validator
PERSON_VEHICLES_SCHEMA: Dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "personId",
            "vehicleId",
            "relationshipType",
        ],
        "properties": {
            "_id": {"bsonType": "objectId"},
            "personId": {
                "bsonType": "objectId",
                "description": "Reference to persons collection",
            },
            "vehicleId": {
                "bsonType": "objectId",
                "description": "Reference to vehicles collection",
            },
            "relationshipType": {
                "bsonType": "string",
                "description": "Relationship category (e.g. REGISTERED_OWNER, CO_OWNER, DRIVER)",
            },
            "validFrom": {"bsonType": ["date", "null"]},
            "validTo": {"bsonType": ["date", "null"]},
            "verificationSource": {"bsonType": ["string", "null"]},
        },
    }
}

# 8. system_settings collection validator
SYSTEM_SETTINGS_SCHEMA: Dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "key",
            "minConfidenceThreshold",
            "autoFlagPillionWithoutHelmet",
            "autoFlagTripleRiding",
            "requireSecondaryReviewForNightDetections",
            "dataRetentionDays",
            "defaultDraftPenaltyInr",
            "updatedAt",
        ],
        "properties": {
            "_id": {"bsonType": "objectId"},
            "key": {
                "bsonType": "string",
                "description": "Unique settings partition key (e.g. default)",
            },
            "minConfidenceThreshold": {
                "bsonType": ["double", "int"],
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Minimum confidence required to flag violation",
            },
            "autoFlagPillionWithoutHelmet": {
                "bsonType": "bool",
                "description": "Flag pillion rider non-compliance",
            },
            "autoFlagTripleRiding": {
                "bsonType": "bool",
                "description": "Flag cases with 3+ riders",
            },
            "requireSecondaryReviewForNightDetections": {
                "bsonType": "bool",
                "description": "Require dual officer sign-off for night frames",
            },
            "dataRetentionDays": {
                "bsonType": ["int", "long"],
                "minimum": 1,
                "description": "Evidence retention policy window in days",
            },
            "defaultDraftPenaltyInr": {
                "bsonType": ["double", "int", "long"],
                "minimum": 0,
                "description": "Default draft penalty amount estimate in INR",
            },
            "updatedBy": {
                "bsonType": ["objectId", "null"],
                "description": "Reference to users collection for admin who modified settings",
            },
            "updatedAt": {"bsonType": "date"},
        },
    }
}

# 9. notifications collection validator
NOTIFICATIONS_SCHEMA: Dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "personId",
            "date",
            "type",
            "status",
            "title",
            "preview",
        ],
        "properties": {
            "_id": {"bsonType": "objectId"},
            "personId": {
                "bsonType": "objectId",
                "description": "Reference to persons collection",
            },
            "violationId": {
                "bsonType": ["objectId", "null"],
                "description": "Reference to violations collection if tied to a case",
            },
            "date": {"bsonType": "date"},
            "type": {
                "enum": ["SMS", "EMAIL", "PORTAL"],
                "description": "Communication dispatch channel",
            },
            "status": {
                "enum": ["PENDING", "DELIVERED", "FAILED"],
                "description": "Dispatch delivery status",
            },
            "title": {"bsonType": "string"},
            "preview": {"bsonType": "string"},
            "providerReference": {
                "bsonType": ["string", "null"],
                "description": "SMS gateway or email dispatch tracking ID",
            },
        },
    }
}

# 10. officer_shifts collection validator
OFFICER_SHIFTS_SCHEMA: Dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "officerId",
            "shiftStart",
            "status",
            "createdAt",
            "updatedAt",
        ],
        "properties": {
            "_id": {"bsonType": "objectId"},
            "officerId": {
                "bsonType": "objectId",
                "description": "Reference to users collection for the officer",
            },
            "shiftStart": {"bsonType": "date"},
            "shiftEnd": {"bsonType": ["date", "null"]},
            "status": {
                "enum": ["ON_DUTY", "ON_LEAVE", "BREAK"],
                "description": "Current shift status",
            },
            "createdAt": {"bsonType": "date"},
            "updatedAt": {"bsonType": "date"},
        },
    }
}

# 11. model_runs collection validator
MODEL_RUNS_SCHEMA: Dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "cameraId",
            "modelName",
            "modelVersion",
            "processedAt",
            "processingTimeMs",
            "resultSummary",
            "status",
        ],
        "properties": {
            "_id": {"bsonType": "objectId"},
            "cameraId": {
                "bsonType": "objectId",
                "description": "Reference to cameras collection",
            },
            "modelName": {
                "bsonType": "string",
                "description": "Model architecture name (e.g. YOLOv8n-Traffic)",
            },
            "modelVersion": {"bsonType": "string"},
            "processedAt": {"bsonType": "date"},
            "processingTimeMs": {
                "bsonType": ["double", "int", "long"],
                "minimum": 0,
                "description": "Inference and parsing execution duration in ms",
            },
            "resultSummary": {
                "bsonType": "object",
                "description": "Counts of detections, candidate flags, and inference telemetry",
            },
            "status": {
                "enum": ["SUCCESS", "FAILED"],
                "description": "Model execution outcome",
            },
            "errorMessage": {
                "bsonType": ["string", "null"],
                "description": "Sanitized error message if failed",
            },
        },
    }
}

# Mapping of collection name to schema definition
COLLECTION_SCHEMAS: Dict[str, Dict[str, Any]] = {
    COLLECTION_USERS: USERS_SCHEMA,
    COLLECTION_CAMERAS: CAMERAS_SCHEMA,
    COLLECTION_VIOLATIONS: VIOLATIONS_SCHEMA,
    COLLECTION_AUDIT_LOGS: AUDIT_LOGS_SCHEMA,
    COLLECTION_PERSONS: PERSONS_SCHEMA,
    COLLECTION_VEHICLES: VEHICLES_SCHEMA,
    COLLECTION_PERSON_VEHICLES: PERSON_VEHICLES_SCHEMA,
    COLLECTION_SYSTEM_SETTINGS: SYSTEM_SETTINGS_SCHEMA,
    COLLECTION_NOTIFICATIONS: NOTIFICATIONS_SCHEMA,
    COLLECTION_OFFICER_SHIFTS: OFFICER_SHIFTS_SCHEMA,
    COLLECTION_MODEL_RUNS: MODEL_RUNS_SCHEMA,
}
