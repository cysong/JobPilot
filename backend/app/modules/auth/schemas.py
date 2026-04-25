"""Authentication Pydantic schemas."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.config import settings
from app.shared.enums import Role, TailoringLevel


def _validate_password_complexity(value: str) -> str:
    """Validate password complexity rules shared across auth schemas."""
    if not any(char.isdigit() for char in value):
        raise ValueError("Password must contain at least one digit")
    if not any(char.isalpha() for char in value):
        raise ValueError("Password must contain at least one letter")
    return value


class SalaryExpectation(BaseModel):
    """Expected yearly salary configuration."""

    mode: Literal["exact", "range"]
    currency: Literal["NZD"] = "NZD"
    period: Literal["yearly"] = "yearly"
    min: int | None = Field(default=None, ge=0)
    max: int | None = Field(default=None, ge=0)
    value: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_shape(self) -> "SalaryExpectation":
        if self.mode == "exact":
            if self.value is None:
                raise ValueError("salary_expectation.value is required when mode is exact")
            if self.min is not None or self.max is not None:
                raise ValueError("salary_expectation.min/max must be null when mode is exact")
        else:
            if self.min is None or self.max is None:
                raise ValueError("salary_expectation.min and max are required when mode is range")
            if self.max < self.min:
                raise ValueError("salary_expectation.max must be greater than or equal to min")
            if self.value is not None:
                raise ValueError("salary_expectation.value must be null when mode is range")
        return self


class UserPreferences(BaseModel):
    """Supported user profile preferences."""

    default_tailoring_level: TailoringLevel | None = None
    job_locations: list[str] = Field(default_factory=list)
    salary_expectation: SalaryExpectation | None = None


class UserRegister(BaseModel):
    """User registration request schema."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ...,
        min_length=settings.PASSWORD_MIN_LENGTH,
        description="User password (min 8 characters)",
    )
    full_name: str = Field(..., min_length=1, max_length=255, description="User full name")

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        """Validate password complexity."""
        return _validate_password_complexity(value)


class UserLogin(BaseModel):
    """User login request schema."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class Token(BaseModel):
    """JWT token response schema."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")


class MessageResponse(BaseModel):
    """Simple success message response."""

    message: str


class ForgotPasswordRequest(BaseModel):
    """Forgot-password request payload."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Reset-password request payload."""

    token: str = Field(..., min_length=1)
    new_password: str = Field(
        ...,
        min_length=settings.PASSWORD_MIN_LENGTH,
        description="New password (min 8 characters)",
    )

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        """Validate password complexity."""
        return _validate_password_complexity(value)


class VerifyTokenRequest(BaseModel):
    """Token-only request payload."""

    token: str = Field(..., min_length=1)


class ChangePasswordRequest(BaseModel):
    """Change-password request payload."""

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(
        ...,
        min_length=settings.PASSWORD_MIN_LENGTH,
        description="New password (min 8 characters)",
    )

    @field_validator("new_password")
    @classmethod
    def validate_changed_password(cls, value: str) -> str:
        """Validate password complexity."""
        return _validate_password_complexity(value)


class ChangeEmailRequest(BaseModel):
    """Request a change of email."""

    new_email: EmailStr
    current_password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    """User information response schema."""

    id: int
    email: str
    full_name: str
    avatar_seed: str | None = None
    role: Role
    is_active: bool
    email_verified_at: datetime | None = None
    password_changed_at: datetime | None = None
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApiKeyCreate(BaseModel):
    """Request body for creating an API key."""

    name: str = Field(..., min_length=1, max_length=100)
    expires_at: datetime | None = None


class ApiKeyResponse(BaseModel):
    """API key metadata returned in list endpoints (no plaintext)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    prefix: str
    scopes: list[str]
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Response returned exactly once at creation, including plaintext key."""

    plaintext: str
