"""Authentication Pydantic schemas"""
from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import Optional

from app.shared.enums import Role
from app.core.config import settings


class UserRegister(BaseModel):
    """User registration request schema"""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ...,
        min_length=settings.PASSWORD_MIN_LENGTH,
        description="User password (min 8 characters)"
    )
    full_name: str = Field(..., min_length=1, max_length=255, description="User full name")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password complexity"""
        if not any(char.isdigit() for char in v):
            raise ValueError("Password must contain at least one digit")
        if not any(char.isalpha() for char in v):
            raise ValueError("Password must contain at least one letter")
        return v


class UserLogin(BaseModel):
    """User login request schema"""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class Token(BaseModel):
    """JWT token response schema"""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")


class UserResponse(BaseModel):
    """User information response schema"""

    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2: allow ORM models
