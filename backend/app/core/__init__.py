"""
Core Application Utilities, Exception Definitions, and Handlers.
"""

from app.core.exceptions import (
    AppException,
    NotFoundError,
    ValidationError,
    ConflictError,
    DatabaseUnavailableError,
    UnauthorizedError,
    ForbiddenError,
)
from app.core.error_handlers import register_error_handlers

__all__ = [
    "AppException",
    "NotFoundError",
    "ValidationError",
    "ConflictError",
    "DatabaseUnavailableError",
    "UnauthorizedError",
    "ForbiddenError",
    "register_error_handlers",
]
