"""
User module Pydantic schemas.

This module contains request/response schemas for user-related APIs,
including user skill management.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.shared.enums import ProficiencyLevel


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
