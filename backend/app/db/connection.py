"""
MongoDB Connection Lifecycle Manager.

Provides robust connection lifecycle management with explicit ping verification,
configurable timeouts, graceful shutdown, and accurate health reporting.
Never reports a false-positive 'database ready' status.
"""

import logging
import time
from typing import Optional, Dict, Any
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, PyMongoError

from app.config import settings

logger = logging.getLogger("trafficguard.db")


class DatabaseConnectionError(Exception):
    """Raised when MongoDB connection or ping verification fails."""
    pass


class MongoDBManager:
    """Manages MongoClient lifecycle and database instances."""

    def __init__(self) -> None:
        self._client: Optional[MongoClient] = None
        self._db: Optional[Database] = None
        self._uri: str = settings.MONGO_URI
        self._db_name: str = settings.MONGO_DB_NAME

    @property
    def is_connected(self) -> bool:
        """Returns True only if client is initialized and ping succeeds."""
        if self._client is None or self._db is None:
            return False
        try:
            self._client.admin.command("ping")
            return True
        except Exception:
            return False

    def connect(
        self,
        uri: Optional[str] = None,
        db_name: Optional[str] = None,
        connect_timeout_ms: Optional[int] = None,
        server_selection_timeout_ms: Optional[int] = None,
    ) -> Database:
        """
        Establishes a connection to MongoDB and performs explicit ping verification.
        Raises DatabaseConnectionError if MongoDB is unavailable or unreachable.
        """
        target_uri = uri or settings.MONGO_URI
        target_db_name = db_name or settings.MONGO_DB_NAME
        conn_timeout = connect_timeout_ms or settings.MONGO_CONNECT_TIMEOUT_MS
        server_timeout = server_selection_timeout_ms or settings.MONGO_SERVER_SELECTION_TIMEOUT_MS

        logger.info(
            f"Connecting to MongoDB database '{target_db_name}' "
            f"(serverSelectionTimeoutMS={server_timeout}ms)..."
        )

        try:
            client: MongoClient = MongoClient(
                target_uri,
                connectTimeoutMS=conn_timeout,
                serverSelectionTimeoutMS=server_timeout,
                socketTimeoutMS=settings.MONGO_SOCKET_TIMEOUT_MS,
                appname="TrafficGuardAI",
                tz_aware=True,  # Ensures all datetimes are UTC/timezone aware
            )
            # Explicit ping verification — never assume connection succeeds without ping
            start_time = time.perf_counter()
            client.admin.command("ping")
            latency_ms = (time.perf_counter() - start_time) * 1000

            self._client = client
            self._uri = target_uri
            self._db_name = target_db_name
            self._db = client[target_db_name]

            logger.info(
                f"Successfully connected and verified MongoDB database '{target_db_name}' "
                f"in {latency_ms:.1f}ms."
            )
            return self._db

        except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
            self.close()
            error_msg = (
                f"Failed to connect to MongoDB at '{target_uri}'. "
                f"Ensure MongoDB service is running and accessible. Error: {str(exc)}"
            )
            logger.error(error_msg)
            raise DatabaseConnectionError(error_msg) from exc
        except PyMongoError as exc:
            self.close()
            error_msg = f"Unexpected PyMongo error connecting to MongoDB: {str(exc)}"
            logger.error(error_msg)
            raise DatabaseConnectionError(error_msg) from exc

    def get_database(self) -> Database:
        """Returns the active Database instance or connects if not yet initialized."""
        if self._db is None or self._client is None:
            return self.connect()
        return self._db

    def get_client(self) -> MongoClient:
        """Returns the active MongoClient instance or connects if not yet initialized."""
        if self._client is None:
            self.connect()
        assert self._client is not None
        return self._client

    def check_health(self) -> Dict[str, Any]:
        """
        Probes the MongoDB connection and reports live status with latency.
        Never returns a false-positive READY status.
        """
        if self._client is None:
            try:
                self.connect()
            except Exception as exc:
                return {
                    "status": "OFFLINE",
                    "database": self._db_name,
                    "error": str(exc),
                    "is_ready": False,
                }
        try:
            start_time = time.perf_counter()
            self._client.admin.command("ping")
            latency_ms = (time.perf_counter() - start_time) * 1000
            return {
                "status": "ONLINE",
                "database": self._db_name,
                "latency_ms": round(latency_ms, 2),
                "is_ready": True,
            }
        except Exception as exc:
            return {
                "status": "OFFLINE",
                "database": self._db_name,
                "error": str(exc),
                "is_ready": False,
            }

    def close(self) -> None:
        """Gracefully closes the MongoClient connection and resets internal state."""
        if self._client is not None:
            try:
                self._client.close()
                logger.info("MongoDB client connection closed cleanly.")
            except Exception as exc:
                logger.warning(f"Error while closing MongoClient: {exc}")
            finally:
                self._client = None
                self._db = None


# Module-level singleton manager
mongo_manager = MongoDBManager()


def get_db() -> Database:
    """Convenience accessor to obtain the active Database instance."""
    return mongo_manager.get_database()


def get_client() -> MongoClient:
    """Convenience accessor to obtain the active MongoClient instance."""
    return mongo_manager.get_client()


def close_mongo_connection() -> None:
    """Closes the active MongoDB connection."""
    mongo_manager.close()
