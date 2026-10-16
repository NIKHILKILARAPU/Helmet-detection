"""
Common API Models, Response Envelopes, and Health Status Schemas.
"""

from typing import Generic, TypeVar, Optional, List, Any, Dict
from pydantic import BaseModel, Field
from datetime import datetime, timezone

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Detailed validation or domain error item."""
    field: Optional[str] = Field(None, description="Location of the field with error")
    message: str = Field(..., description="Human-readable error description")
    error_type: Optional[str] = Field(None, description="Error type identifier")


class ErrorResponse(BaseModel):
    """Standardized API error response payload across all endpoints."""
    success: bool = Field(False, description="Always False for error responses")
    error_code: str = Field(..., description="Machine-readable error category")
    message: str = Field(..., description="Primary error message")
    details: Optional[List[ErrorDetail]] = Field(None, description="Validation failure details if applicable")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: Optional[str] = Field(None, description="Trace request identifier")


class ApiResponse(BaseModel, Generic[T]):
    """Standardized API success response envelope."""
    success: bool = Field(True, description="Always True for successful responses")
    data: T = Field(..., description="Payload data")
    message: Optional[str] = Field(None, description="Informational message")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PaginatedResponse(BaseModel, Generic[T]):
    """Standardized paginated list response envelope."""
    success: bool = Field(True, description="Always True for successful responses")
    data: List[T] = Field(..., description="List of items for current page")
    total: int = Field(..., description="Total items matching query filter")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, le=100, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total available pages")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DatabaseHealthStatus(BaseModel):
    """Live database status derived from real MongoDB ping."""
    status: str = Field(..., description="ONLINE or OFFLINE")
    database: str = Field(..., description="Target database name")
    is_ready: bool = Field(..., description="True if database responds to ping")
    latency_ms: Optional[float] = Field(None, description="Roundtrip ping latency in milliseconds")
    error: Optional[str] = Field(None, description="Error details if unreachable")


class HealthCheckResponse(BaseModel):
    """Overall microservices and infrastructure health response."""
    status: str = Field(..., description="Overall health: ONLINE or DEGRADED")
    service: str = Field("FastAPI Traffic Enforcement Gateway", description="Service name")
    version: str = Field("1.0.0", description="API version")
    database: DatabaseHealthStatus = Field(..., description="Real live MongoDB connectivity telemetry")
    yolo_model: str = Field(..., description="YOLO model operational status: READY or DEMO_STANDIN")
    message: str = Field(..., description="System status summary")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
