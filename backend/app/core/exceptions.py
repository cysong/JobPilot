"""Custom exception classes with unified response codes."""
from fastapi import status

from app.core.response_codes import ResponseCode


class JobPilotException(Exception):
    """Base exception for JobPilot application."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        response_code: ResponseCode = ResponseCode.INTERNAL_ERROR,
    ):
        self.message = message
        self.status_code = status_code
        self.response_code = response_code
        super().__init__(self.message)


class NotFoundError(JobPilotException):
    """Resource not found exception."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            response_code=ResponseCode.NOT_FOUND,
        )


class UnauthorizedError(JobPilotException):
    """Unauthorized access exception."""

    def __init__(self, message: str = "Unauthorized"):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            response_code=ResponseCode.UNAUTHORIZED,
        )


class ForbiddenError(JobPilotException):
    """Forbidden access exception."""

    def __init__(self, message: str = "Forbidden"):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            response_code=ResponseCode.FORBIDDEN,
        )


class BadRequestError(JobPilotException):
    """Bad request exception."""

    def __init__(
        self,
        message: str = "Bad request",
        response_code: ResponseCode = ResponseCode.BAD_REQUEST,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            response_code=response_code,
        )


class ConflictError(JobPilotException):
    """Conflict exception (e.g., duplicate resource)."""

    def __init__(self, message: str = "Resource conflict"):
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            response_code=ResponseCode.CONFLICT,
        )


class BusinessError(JobPilotException):
    """Business logic exception with explicit response code."""

    def __init__(
        self,
        message: str,
        *,
        response_code: ResponseCode,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            response_code=response_code,
        )
