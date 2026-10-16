"""
Centralized Error Handlers for FastAPI Application.

Ensures consistent JSON error formats, HTTP status codes, and security
across validation, domain, HTTP, and unexpected exceptions.
"""

import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException
from app.schemas.common import ErrorResponse, ErrorDetail

logger = logging.getLogger("trafficguard.api.errors")


def register_error_handlers(app: FastAPI) -> None:
    """Registers standard exception handlers on the FastAPI application."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        logger.warning(
            f"AppException [{exc.error_code}] on {request.method} {request.url.path}: {exc.message}"
        )
        payload = ErrorResponse(
            success=False,
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
            request_id=request.headers.get("x-request-id"),
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump(mode="json"))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.info(f"Validation error on {request.method} {request.url.path}: {exc.errors()}")
        details = []
        for err in exc.errors():
            loc = " -> ".join([str(x) for x in err.get("loc", []) if x != "body"])
            msg = err.get("msg", "Invalid value")
            err_type = err.get("type", "value_error")
            details.append(ErrorDetail(field=loc or "body", message=msg, error_type=err_type))

        payload = ErrorResponse(
            success=False,
            error_code="VALIDATION_ERROR",
            message="Request payload or parameters failed validation schema checks.",
            details=details,
            request_id=request.headers.get("x-request-id"),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=payload.model_dump(mode="json"),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        logger.warning(f"HTTPException {exc.status_code} on {request.method} {request.url.path}: {exc.detail}")
        payload = ErrorResponse(
            success=False,
            error_code=f"HTTP_{exc.status_code}",
            message=str(exc.detail),
            request_id=request.headers.get("x-request-id"),
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump(mode="json"))

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(f"Unhandled internal server error on {request.method} {request.url.path}: {exc}")
        payload = ErrorResponse(
            success=False,
            error_code="INTERNAL_SERVER_ERROR",
            message="An internal server error occurred while processing your request.",
            request_id=request.headers.get("x-request-id"),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=payload.model_dump(mode="json"),
        )
