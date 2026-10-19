"""
Database Initialization Utility for TrafficGuard AI.

Initializes MongoDB collections, applies JSON Schema validators, builds indexes,
and seeds safe baseline system_settings documents.

Features:
- Idempotent: can be run repeatedly without duplicating indexes or settings.
- Safe: never drops collections or deletes existing records.
- Explicit: provides detailed logging and exits with status code 0 (success) or 1 (failure).
"""

import sys
import logging
import argparse
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pymongo.database import Database
from pymongo.errors import OperationFailure, PyMongoError

from app.config import settings
from app.db.collections import (
    ALL_COLLECTIONS,
    COLLECTION_SYSTEM_SETTINGS,
)
from app.db.schemas import COLLECTION_SCHEMAS
from app.db.indexes import COLLECTION_INDEXES
from app.db.default_settings import DEFAULT_SYSTEM_SETTINGS, DEFAULT_SETTINGS_KEY
from app.db.connection import mongo_manager, DatabaseConnectionError

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("trafficguard.db.init")


def apply_collection_validator(db: Database, col_name: str, schema: Dict[str, Any]) -> str:
    """
    Applies JSON Schema validator to a collection.
    Creates collection if missing, or modifies validator via collMod if existing.
    Returns status string: 'created' or 'updated'.
    """
    existing_collections = db.list_collection_names()
    if col_name not in existing_collections:
        db.create_collection(
            col_name,
            validator=schema,
            validationLevel="strict",
            validationAction="error",
        )
        logger.info(f"Created collection '{col_name}' with JSON Schema validator.")
        return "created"
    else:
        try:
            db.command(
                "collMod",
                col_name,
                validator=schema,
                validationLevel="strict",
                validationAction="error",
            )
            logger.info(f"Updated JSON Schema validator for existing collection '{col_name}'.")
            return "updated"
        except OperationFailure as exc:
            logger.warning(
                f"Could not apply collMod validator on collection '{col_name}': {exc}"
            )
            return f"skipped_validator ({exc.code})"


def apply_collection_indexes(db: Database, col_name: str, index_models: list) -> List[str]:
    """
    Applies indexes to a collection idempotently.
    Safe against existing indexes and logs conflicts.
    """
    if not index_models:
        return []

    collection = db[col_name]
    created_names = []

    try:
        results = collection.create_indexes(index_models)
        created_names.extend(results)
        logger.info(f"Applied {len(results)} index(es) on '{col_name}': {', '.join(results)}")
    except OperationFailure as exc:
        logger.warning(
            f"Index creation warning on '{col_name}': {exc.details if hasattr(exc, 'details') else exc}"
        )
        # Attempt individual index creation to isolate any conflict
        for model in index_models:
            try:
                res = collection.create_indexes([model])
                created_names.extend(res)
            except Exception as single_err:
                logger.error(
                    f"Failed to create specific index '{model.document.get('name', 'unnamed')}' on '{col_name}': {single_err}"
                )
    return created_names


def seed_default_settings(db: Database) -> str:
    """
    Seeds initial system_settings baseline document if missing.
    Idempotent: preserves existing user settings if already present.
    """
    col = db[COLLECTION_SYSTEM_SETTINGS]
    existing = col.find_one({"key": DEFAULT_SETTINGS_KEY})

    if existing is None:
        document = dict(DEFAULT_SYSTEM_SETTINGS)
        document["updatedAt"] = datetime.now(timezone.utc)
        result = col.insert_one(document)
        logger.info(
            f"Seeded baseline system_settings with key '{DEFAULT_SETTINGS_KEY}' (ID: {result.inserted_id})."
        )
        return "seeded"
    else:
        logger.info(
            f"Baseline system_settings with key '{DEFAULT_SETTINGS_KEY}' already exists; preserving existing configuration."
        )
        return "already_present"


def initialize_database(
    db: Optional[Database] = None,
    uri: Optional[str] = None,
    db_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full database initialization routine:
    1. Connects and verifies connection via ping
    2. Creates all 11 collections and applies JSON Schema validators
    3. Builds performance and constraint indexes
    4. Seeds safe baseline system_settings document
    5. Returns a structured initialization report
    """
    target_db = db
    should_close = False

    if target_db is None:
        target_db = mongo_manager.connect(uri=uri, db_name=db_name)
        should_close = True

    report: Dict[str, Any] = {
        "database_name": target_db.name,
        "collections": {},
        "indexes": {},
        "settings_status": None,
        "success": False,
    }

    try:
        logger.info(f"--- Starting Database Initialization for '{target_db.name}' ---")

        # 1. Process all 11 collections: validators & indexes
        for col_name in ALL_COLLECTIONS:
            schema = COLLECTION_SCHEMAS.get(col_name, {})
            indexes = COLLECTION_INDEXES.get(col_name, [])

            # Apply Schema Validator
            val_status = apply_collection_validator(target_db, col_name, schema)
            report["collections"][col_name] = val_status

            # Apply Indexes
            applied_indexes = apply_collection_indexes(target_db, col_name, indexes)
            report["indexes"][col_name] = applied_indexes

        # 2. Seed Baseline System Settings
        settings_status = seed_default_settings(target_db)
        report["settings_status"] = settings_status

        report["success"] = True
        logger.info("--- Database Initialization Completed Successfully ---")
        return report

    except PyMongoError as exc:
        logger.error(f"Database initialization encountered an unhandled PyMongo error: {exc}")
        report["error"] = str(exc)
        report["success"] = False
        raise
    finally:
        if should_close:
            mongo_manager.close()


def main() -> int:
    """CLI entrypoint for database initialization."""
    parser = argparse.ArgumentParser(
        description="TrafficGuard AI — MongoDB Database Initialization Utility"
    )
    parser.add_argument(
        "--uri",
        type=str,
        default=None,
        help=f"MongoDB connection URI (defaults to env MONGO_URI: {settings.MONGO_URI})",
    )
    parser.add_argument(
        "--db-name",
        type=str,
        default=None,
        help=f"Database name (defaults to env MONGO_DB_NAME: {settings.MONGO_DB_NAME})",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify connection health without applying schema or indexes",
    )

    args = parser.parse_args()

    effective_uri = args.uri or settings.MONGO_URI
    effective_db = args.db_name or settings.MONGO_DB_NAME

    print("=" * 70)
    print("  TrafficGuard AI — Database Initialization & Health Utility")
    print(f"  Target URI:      {effective_uri}")
    print(f"  Target Database: {effective_db}")
    print("=" * 70)

    try:
        if args.verify_only:
            logger.info("Running in verification-only mode...")
            mongo_manager.connect(uri=effective_uri, db_name=effective_db)
            health = mongo_manager.check_health()
            mongo_manager.close()
            print(f"[OK] MongoDB Connection Verified. Status: {health.get('status')}, Latency: {health.get('latency_ms')}ms")
            return 0

        # Run full initialization
        report = initialize_database(uri=effective_uri, db_name=effective_db)
        print("\nInitialization Summary:")
        print(f"  Database:        {report['database_name']}")
        print(f"  Collections:     {len(report['collections'])} processed")
        print(f"  Default Settings:{report['settings_status']}")
        print("  Status:          SUCCESS (Exit 0)")
        return 0

    except DatabaseConnectionError as conn_err:
        print("\n" + "!" * 70)
        print("  [ERROR] Database Connection Failed!")
        print(f"  Details: {conn_err}")
        print("\n  Troubleshooting Steps:")
        print("  1. Verify MongoDB is installed and running on your system:")
        print("     - Windows: Start-Service MongoDB  (or net start MongoDB)")
        print("     - Linux:   sudo systemctl status mongod")
        print("  2. Ensure the connection URI is correct:")
        print("     - Set MONGO_URI in backend/.env (e.g. mongodb://localhost:27017)")
        print("  3. For MongoDB Atlas or remote hosts:")
        print("     - Ensure your IP address is whitelisted in Atlas Network Access")
        print("!" * 70)
        return 1
    

    except Exception as exc:
        print(f"\n[FATAL] Unexpected error during initialization: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
