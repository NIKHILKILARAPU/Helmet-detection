"""
Custom Application Exceptions with Explicit HTTP Status Codes and Error Codes.
"""

from typing import Optional, List, Any
from app.schemas.common import ErrorDetail


class AppException(Exception):
    """Base exception for application domain errors."""

    def __init__(
        self,
        status_code: int = 400,
        error_code: str = "BAD_REQUEST",
        message: str = "An application error occurred",
        details: Optional[List[ErrorDetail]] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details or []


class NotFoundError(AppException):
    """Resource not found (HTTP 404)."""

    def __init__(
        self,
        message: str = "Resource not found",
        entity: str = "Resource",
        entity_id: Optional[str] = None,
    ) -> None:
        detail_msg = f"{entity} '{entity_id}' not found." if entity_id else message
        super().__init__(
            status_code=404,
            error_code="RESOURCE_NOT_FOUND",
            message=detail_msg,
            details=[ErrorDetail(field=entity.lower(), message=detail_msg, error_type="NOT_FOUND")],
        )


class ValidationError(AppException):
    """Business rule or state validation failure (HTTP 400)."""

    def __init__(
        self,
        message: str = "Validation failed",
        details: Optional[List[ErrorDetail]] = None,
    ) -> None:
        super().__init__(
            status_code=400,
            error_code="BUSINESS_VALIDATION_ERROR",
            message=message,
            details=details or [],
        )


class ConflictError(AppException):
    """Entity conflict or unique constraint collision (HTTP 409)."""

    def __init__(
        self,
        message: str = "Conflict with existing resource state",
        entity: str = "Resource",
        identifier: Optional[str] = None,
    ) -> None:
        detail_msg = f"{entity} with identifier '{identifier}' already exists." if identifier else message
        super().__init__(
            status_code=409,
            error_code="RESOURCE_CONFLICT",
            message=detail_msg,
            details=[ErrorDetail(field=entity.lower(), message=detail_msg, error_type="CONFLICT")],
        )


class DatabaseUnavailableError(AppException):
    """MongoDB service unavailable or ping timeout (HTTP 503)."""

    def __init__(
        self,
        message: str = "MongoDB database service is currently unavailable or unreachable.",
    ) -> None:
        super().__init__(
            status_code=503,
            error_code="DATABASE_UNAVAILABLE",
            message=message,
            details=[ErrorDetail(field="database", message=message, error_type="SERVICE_UNAVAILABLE")],
        )


class UnauthorizedError(AppException):
    """Authentication required (HTTP 401)."""

    def __init__(self, message: str = "Authentication required to perform this action.") -> None:
        super().__init__(
            status_code=401,
            error_code="UNAUTHORIZED",
            message=message,
        )


class ForbiddenError(AppException):
    """Role permission denied (HTTP 403)."""

    def __init__(self, message: str = "Access forbidden for current user role.") -> None:
        super().__init__(
            status_code=403,
            error_code="FORBIDDEN",
            message=message,
        )


class ModelNotAvailableError(AppException):
    """AI Model weights missing or unreadable (HTTP 503)."""

    def __init__(
        self,
        message: str = "Trained model weights are not available on this server.",
        expected_path: Optional[str] = None,
        expected_classes: Optional[List[str]] = None,
    ) -> None:
        details = []
        if expected_path:
            details.append(
                ErrorDetail(
                    field="model_path",
                    message=f"Expected model weights file at: {expected_path}",
                    error_type="FILE_MISSING",
                )
            )
        if expected_classes:
            details.append(
                ErrorDetail(
                    field="expected_classes",
                    message=f"Required classes for helmet violation detection: {', '.join(expected_classes)}",
                    error_type="CLASSES_REQUIRED",
                )
            )
        super().__init__(
            status_code=503,
            error_code="MODEL_NOT_AVAILABLE",
            message=message,
            details=details,
        )


class RemoteInferenceError(AppException):
    """Remote inference service (e.g. Roboflow) failure, timeout, or configuration issue."""

    def __init__(
        self,
        message: str = "Remote AI inference service encountered an error.",
        status_code: int = 502,
        error_code: str = "REMOTE_INFERENCE_ERROR",
        details: Optional[List[ErrorDetail]] = None,
    ) -> None:
        super().__init__(
            status_code=status_code,
            error_code=error_code,
            message=message,
            details=details or [],
        )


