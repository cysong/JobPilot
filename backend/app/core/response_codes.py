"""Unified business response codes for JobPilot API."""
from enum import Enum
from typing import Dict


class ResponseCode(int, Enum):
    """Simplified response codes for scenarios needing special frontend handling."""

    # Success
    SUCCESS = 0

    # Authentication (special handling required)
    UNAUTHORIZED = 401  # Not logged in -> redirect to login
    TOKEN_EXPIRED = 419  # Token expired -> refresh token
    FORBIDDEN = 403  # No permission -> show permission denied

    # Business rules (special UI required)
    RESUME_LIMIT_EXCEEDED = 1001  # Resume limit reached -> show upgrade button
    QUOTA_EXCEEDED = 1002  # AI quota exhausted -> show recharge prompt

    # Common errors (use HTTP status codes directly)
    BAD_REQUEST = 400  # Invalid parameters
    NOT_FOUND = 404  # Resource not found
    CONFLICT = 409  # Resource conflict
    INTERNAL_ERROR = 500  # Server error

    @property
    def message(self) -> str:
        """Return the default message for the response code."""
        return RESPONSE_MESSAGES.get(self, "Unknown error")


RESPONSE_MESSAGES: Dict[ResponseCode, str] = {
    ResponseCode.SUCCESS: "Operation succeeded",
    ResponseCode.UNAUTHORIZED: "Unauthorized, please login",
    ResponseCode.TOKEN_EXPIRED: "Login expired, please reauthenticate",
    ResponseCode.FORBIDDEN: "Forbidden",
    ResponseCode.RESUME_LIMIT_EXCEEDED: "Resume limit reached",
    ResponseCode.QUOTA_EXCEEDED: "AI quota exhausted",
    ResponseCode.BAD_REQUEST: "Invalid request parameters",
    ResponseCode.NOT_FOUND: "Resource not found",
    ResponseCode.CONFLICT: "Resource conflict",
    ResponseCode.INTERNAL_ERROR: "Internal server error",
}
