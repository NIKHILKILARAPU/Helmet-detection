"""
Database Package for TrafficGuard AI.

Exports connection managers, initialization utilities, collection names,
JSON Schema validators, and index specifications.
"""

from typing import Any, Dict, Optional
from pymongo.database import Database

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
from app.db.connection import (
    mongo_manager,
    get_db,
    get_client,
    close_mongo_connection,
    DatabaseConnectionError,
)
from app.db.schemas import COLLECTION_SCHEMAS
from app.db.indexes import COLLECTION_INDEXES
from app.db.default_settings import DEFAULT_SYSTEM_SETTINGS, DEFAULT_SETTINGS_KEY


def initialize_database(
    db: Optional[Database] = None,
    uri: Optional[str] = None,
    db_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Lazy import wrapper to prevent runpy circular module warnings on CLI execution."""
    from app.db.init_db import initialize_database as _init_db
    return _init_db(db=db, uri=uri, db_name=db_name)


__all__ = [
    "ALL_COLLECTIONS",
    "COLLECTION_USERS",
    "COLLECTION_CAMERAS",
    "COLLECTION_VIOLATIONS",
    "COLLECTION_AUDIT_LOGS",
    "COLLECTION_PERSONS",
    "COLLECTION_VEHICLES",
    "COLLECTION_PERSON_VEHICLES",
    "COLLECTION_SYSTEM_SETTINGS",
    "COLLECTION_NOTIFICATIONS",
    "COLLECTION_OFFICER_SHIFTS",
    "COLLECTION_MODEL_RUNS",
    "mongo_manager",
    "get_db",
    "get_client",
    "close_mongo_connection",
    "DatabaseConnectionError",
    "initialize_database",
    "COLLECTION_SCHEMAS",
    "COLLECTION_INDEXES",
    "DEFAULT_SYSTEM_SETTINGS",
    "DEFAULT_SETTINGS_KEY",
]
