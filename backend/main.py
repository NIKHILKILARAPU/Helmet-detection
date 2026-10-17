"""
FastAPI Application Entrypoint for TrafficGuard AI.

Configures:
- Real MongoDB health check and readiness probes
- Centralized exception handlers for consistent errors
- Strict request validation with typed Pydantic models
- CORS middleware for frontend communication
- Graceful shutdown lifecycle management
"""

from contextlib import asynccontextmanager
import os
import uvicorn
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db.connection import mongo_manager, close_mongo_connection
from app.core.exceptions import DatabaseUnavailableError
from app.core.error_handlers import register_error_handlers
from app.schemas.common import (
    HealthCheckResponse,
    DatabaseHealthStatus,
    ApiResponse,
)
from app.api.auth import router as auth_router
from app.api.violations import router as violations_router
from app.api.stats import router as stats_router
from app.api.camera import router as camera_router
from app.api.persons import router as persons_router
from app.api.vehicles import router as vehicles_router
from app.api.settings import router as settings_router
from app.api.operations import router as operations_router
from app.api.audit import router as audit_router
from app.api.detections import router as detections_router
from app.models.yolo_inference import yolo_engine
from app.models.roboflow_inference import roboflow_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager handling graceful shutdown."""
    # Startup actions
    yield
    # Shutdown actions: cleanly close database connection pools
    close_mongo_connection()


app = FastAPI(
    title="TrafficGuard AI — Government Enforcement API",
    version="1.0.0",
    description="Python FastAPI backend powering Smart Helmet Detection & E-Challan Draft Management",
    lifespan=lifespan,
)

# Register centralized exception handlers for consistent errors & status codes
register_error_handlers(app)

# CORS Middleware allowing Frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    f"{settings.API_PREFIX}/health",
    response_model=HealthCheckResponse,
    tags=["system"],
    summary="Comprehensive microservices health status",
)
async def health_check():
    """
    Performs real live connectivity check against MongoDB and reports operational telemetry.
    Never returns a hardcoded or false-positive database ready state.
    """
    db_health_raw = mongo_manager.check_health()
    db_health = DatabaseHealthStatus(
        status=db_health_raw.get("status", "OFFLINE"),
        database=db_health_raw.get("database", settings.MONGO_DB_NAME),
        is_ready=db_health_raw.get("is_ready", False),
        latency_ms=db_health_raw.get("latency_ms"),
        error=db_health_raw.get("error"),
    )

    provider = (settings.INFERENCE_PROVIDER or "roboflow").lower()
    if provider == "roboflow":
        model_ready = roboflow_engine.is_configured()
    else:
        model_ready = yolo_engine.is_model_loaded()
    yolo_status = "READY" if model_ready else "UNAVAILABLE"
    overall_status = "ONLINE" if db_health.is_ready else "DEGRADED"

    msg = (
        "All government enforcement microservices operational"
        if db_health.is_ready
        else f"Gateway operational, but MongoDB is {db_health.status}. Running in degraded/mock mode."
    )

    return HealthCheckResponse(
        status=overall_status,
        service="FastAPI Traffic Enforcement Gateway",
        version="1.0.0",
        database=db_health,
        yolo_model=yolo_status,
        message=msg,
    )


@app.get(
    f"{settings.API_PREFIX}/health/db",
    response_model=ApiResponse[DatabaseHealthStatus],
    tags=["system"],
    summary="Dedicated MongoDB live ping readiness probe",
)
async def db_readiness_probe():
    """
    Strict database readiness probe.
    Returns HTTP 200 with latency if reachable, or HTTP 503 if unreachable.
    """
    db_health_raw = mongo_manager.check_health()
    if not db_health_raw.get("is_ready", False):
        raise DatabaseUnavailableError(
            message=f"MongoDB at '{settings.MONGO_URI}' is offline: {db_health_raw.get('error', 'Unreachable')}"
        )

    db_health = DatabaseHealthStatus(
        status="ONLINE",
        database=db_health_raw.get("database", settings.MONGO_DB_NAME),
        is_ready=True,
        latency_ms=db_health_raw.get("latency_ms"),
    )
    return ApiResponse(
        success=True,
        data=db_health,
        message="MongoDB connection verified and operational.",
    )


# Static evidence files mount (safely serves local frame images)
uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "uploads"))
os.makedirs(os.path.join(uploads_dir, "evidence"), exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")


# Register API routers
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(detections_router, prefix=settings.API_PREFIX)
app.include_router(violations_router, prefix=settings.API_PREFIX)
app.include_router(stats_router, prefix=settings.API_PREFIX)
app.include_router(camera_router, prefix=settings.API_PREFIX)
app.include_router(persons_router, prefix=settings.API_PREFIX)
app.include_router(vehicles_router, prefix=settings.API_PREFIX)
app.include_router(settings_router, prefix=settings.API_PREFIX)
app.include_router(operations_router, prefix=settings.API_PREFIX)
app.include_router(audit_router, prefix=settings.API_PREFIX)


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)
