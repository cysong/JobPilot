"""Pagination utilities"""
from pydantic import BaseModel, Field, AliasChoices
from typing import Generic, TypeVar, List
from math import ceil

T = TypeVar('T')


class PaginationParams(BaseModel):
    """Pagination query parameters"""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        validation_alias=AliasChoices("page_size", "size"),
    )

    def get_offset(self) -> int:
        """Calculate offset for database query"""
        return (self.page - 1) * self.page_size

    def get_limit(self) -> int:
        """Get limit for database query"""
        return self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response"""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        page: int,
        page_size: int
    ) -> "PaginatedResponse[T]":
        """Create paginated response"""
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if page_size > 0 else 0
        )
