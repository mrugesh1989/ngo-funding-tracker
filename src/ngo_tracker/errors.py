"""Typed application errors shared across service and API layers."""


class AppError(Exception):
    """Base for expected, handled failures.

    Args:
        message: Human-readable error description safe to expose to clients.
        code: Stable machine-readable error code for API responses and logs.
        status: HTTP status the API boundary should map this error to.
    """

    def __init__(self, message: str, *, code: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


class ValidationError(AppError):
    """Raised when caller input fails domain validation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="validation_error", status=422)


class NotFoundError(AppError):
    """Raised when a requested entity does not exist."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="not_found", status=404)


class AuthorizationError(AppError):
    """Raised when the caller lacks the plan or key required for a feature."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="forbidden", status=403)


class ExternalServiceError(AppError):
    """Raised when an upstream data provider fails.

    Args:
        message: Description of the failure (no upstream internals).
        retryable: Whether the caller may retry the operation.
    """

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message, code="external_service_error", status=502)
        self.retryable = retryable
