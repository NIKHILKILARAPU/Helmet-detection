"""
Pydantic Schemas and Domain Models Package for TrafficGuard AI.
"""

from app.schemas.common import (
    ApiResponse,
    PaginatedResponse,
    ErrorDetail,
    ErrorResponse,
    HealthCheckResponse,
    DatabaseHealthStatus,
)
from app.schemas.violations import (
    ViolationType,
    ViolationStatus,
    EvidenceQuality,
    IdentityVerificationStatus,
    BoundingBoxModel,
    EvidenceModel,
    ViolationCreate,
    ViolationResponse,
    ApproveDraftRequest,
    ApproveDraftResponse,
    RejectCaseRequest,
    RejectCaseResponse,
    ViolationFilterParams,
)
from app.schemas.cameras import (
    CameraStreamType,
    CameraStatus,
    CameraRegisterRequest,
    CameraResponse,
)
from app.schemas.stats import (
    DashboardStatsResponse,
    HourlyTrendItem,
    MonthlyTrendItem,
)
from app.schemas.settings import (
    SystemSettingsModel,
    SystemSettingsUpdate,
)

__all__ = [
    "ApiResponse",
    "PaginatedResponse",
    "ErrorDetail",
    "ErrorResponse",
    "HealthCheckResponse",
    "DatabaseHealthStatus",
    "ViolationType",
    "ViolationStatus",
    "EvidenceQuality",
    "IdentityVerificationStatus",
    "BoundingBoxModel",
    "EvidenceModel",
    "ViolationCreate",
    "ViolationResponse",
    "ApproveDraftRequest",
    "ApproveDraftResponse",
    "RejectCaseRequest",
    "RejectCaseResponse",
    "ViolationFilterParams",
    "CameraStreamType",
    "CameraStatus",
    "CameraRegisterRequest",
    "CameraResponse",
    "DashboardStatsResponse",
    "HourlyTrendItem",
    "MonthlyTrendItem",
    "SystemSettingsModel",
    "SystemSettingsUpdate",
]
