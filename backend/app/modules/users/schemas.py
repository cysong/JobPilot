"""
User module Pydantic schemas.

This module contains request/response schemas for user-related APIs,
including user skill management.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.modules.auth.schemas import SalaryExpectation, UserPreferences
from app.shared.enums import ProficiencyLevel, TailoringLevel


NZ_JOB_LOCATION_OPTIONS = [
    "Auckland",
    "Wellington",
    "Christchurch",
    "Hamilton",
    "Tauranga",
    "Dunedin",
    "Palmerston North",
    "Queenstown",
    "Napier-Hastings",
    "Nelson",
]


# ============================================
# User Skill Schemas
# ============================================

class UserSkillBase(BaseModel):
    """Base schema for user skill"""
    skill_name: str = Field(..., min_length=1, max_length=100, description="Skill name")
    proficiency_level: ProficiencyLevel = Field(..., description="Proficiency level")


class UserSkillCreate(UserSkillBase):
    """Schema for creating a new user skill manually"""
    pass


class UserSkillUpdate(BaseModel):
    """Schema for updating user skill proficiency"""
    proficiency_level: ProficiencyLevel = Field(..., description="New proficiency level")


class UserSkillResponse(UserSkillBase):
    """Schema for user skill response"""
    id: str = Field(..., description="Skill ID")
    user_id: int = Field(..., description="User ID")
    is_manual: bool = Field(..., description="Whether manually edited by user")
    manual_proficiency: Optional[ProficiencyLevel] = Field(None, description="User-set proficiency if manually edited")
    source_count: int = Field(..., description="How many resumes mention this skill")
    last_seen_at: Optional[datetime] = Field(None, description="Last time this skill appeared in a resume")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"from_attributes": True}


class UserSkillListResponse(BaseModel):
    """Schema for user skill list response"""
    items: list[UserSkillResponse] = Field(..., description="List of user skills")
    total: int = Field(..., description="Total number of skills")
    manual_count: int = Field(..., description="Number of manually added/edited skills")
    auto_count: int = Field(..., description="Number of auto-extracted skills")


class SkillSyncResponse(BaseModel):
    """Schema for skill sync response"""
    message: str = Field(..., description="Success message")
    total_skills: int = Field(..., description="Total skills after sync")
    manual_skills: int = Field(..., description="Manual skills count")
    auto_skills: int = Field(..., description="Auto skills count")


class UserProfileUpdate(BaseModel):
    """Update user identity fields (name & avatar)."""

    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    avatar_seed: str | None = Field(default=None, max_length=64)


class ProfilePreferencesResponse(UserPreferences):
    """User profile preferences payload."""


class ProfilePreferencesUpdate(BaseModel):
    """Update profile preferences payload."""

    default_tailoring_level: TailoringLevel | None = Field(default=None)
    job_locations: list[str] = Field(default_factory=list)
    salary_expectation: SalaryExpectation | None = None

    @field_validator("default_tailoring_level", mode="before")
    @classmethod
    def validate_default_tailoring_level(
        cls, value: TailoringLevel | str | None
    ) -> TailoringLevel | None:
        if value is None:
            return value
        if isinstance(value, TailoringLevel):
            return value
        normalized = value.strip().lower()
        if normalized not in {item.value for item in TailoringLevel}:
            raise ValueError(
                "default_tailoring_level must be one of 'light', 'moderate', or 'deep'"
            )
        return TailoringLevel(normalized)

    @field_validator("job_locations")
    @classmethod
    def validate_job_locations(cls, value: list[str]) -> list[str]:
        normalized_locations: list[str] = []
        seen: set[str] = set()
        allowed_map = {item.lower(): item for item in NZ_JOB_LOCATION_OPTIONS}

        for raw_item in value:
            item = raw_item.strip()
            if not item:
                continue
            canonical = allowed_map.get(item.lower())
            if canonical is None:
                raise ValueError(f"Unsupported job location: {item}")
            if canonical.lower() in seen:
                continue
            seen.add(canonical.lower())
            normalized_locations.append(canonical)

        return normalized_locations
