"""Unified API response models."""
from typing import Generic, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Unified API response format: {code, message, data}."""

    code: int = Field(description="Business response code, 0 for success")
    message: str = Field(description="Response message")
    data: Optional[T] = Field(default=None, description="Response data")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "code": 0,
                    "message": "ok",
                    "data": {"id": 1, "name": "example"},
                }
            ]
        }
    }
