"""Standard error response format used across the application."""

from typing import Any

from fastapi.responses import JSONResponse


class AppError(Exception):
    """Application-level error with structured response."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


def error_response(code: str, message: str, status_code: int, details: dict | None = None) -> JSONResponse:
    """Build a standardised JSON error response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            }
        },
    )
