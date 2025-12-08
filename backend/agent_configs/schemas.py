"""Pydantic schemas for Agent structured outputs."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field
from app.shared.enums import ProficiencyLevel


class AnalyzedJob(BaseModel):
    """
    Job description analysis output (Agent response).

    Updated schema with extended fields for comprehensive job analysis.
    """

    # Schema version (class-level constant)
    __version__ = "v1.1.0"

    # Job Title Normalization
    normalized_job_title: Optional[str] = Field(
        default=None,
        description="Standardized job title stripped of seniority/modifiers (e.g., 'Backend Developer')"
    )

    # Skills Requirements
    required_skills: list[str] = Field(
        default_factory=list,
        description="Must-have technical skills explicitly mentioned"
    )
    preferred_skills: list[str] = Field(
        default_factory=list,
        description="Nice-to-have skills or preferred qualifications"
    )
    certifications: list[str] = Field(
        default_factory=list,
        description="Required or preferred certifications (e.g., AWS, PMP, CISSP)"
    )
    tech_stack: list[str] = Field(
        default_factory=list,
        description="Technologies, frameworks, and tools mentioned (e.g., React, Docker, PostgreSQL)"
    )

    # Responsibilities & Requirements
    seniority: Optional[str] = Field(
        None,
        description="Seniority level: Junior, Mid-level, Senior, Lead, etc."
    )
    key_responsibilities: list[str] = Field(
        default_factory=list,
        description="Main job responsibilities (3-5 key points, be concise)"
    )
    experience_years: Optional[str] = Field(
        None,
        description="Required experience in years (e.g., '3-5 years', '5+ years')"
    )
    education_requirement: Optional[str] = Field(
        None,
        description="Education requirement (e.g., 'Bachelor in CS', 'Master preferred')"
    )

    # Soft Requirements
    soft_skills: list[str] = Field(
        default_factory=list,
        description="Soft skills like teamwork, communication, leadership, problem-solving"
    )
    company_culture_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords describing company culture (e.g., innovative, agile, collaborative, fast-paced)"
    )

    # Agent Inference
    hiring_priorities: list[str] = Field(
        default_factory=list,
        description="Agent's inference: what does the company value most? List top 3 priorities based on job description emphasis"
    )


class Skill(BaseModel):
    """Standardized skill with proficiency."""

    name: str = Field(..., description="Standardized skill name (e.g., 'Python', 'React', 'Docker')")
    proficiency: ProficiencyLevel = Field(..., description="Proficiency level")


class WorkExperience(BaseModel):
    """Work experience entry."""

    company: str = Field(..., description="Company name")
    role: str = Field(..., description="Job title/role")
    duration: tuple[str, str] = Field(..., description="Start and end date [from, to]")
    key_achievements: list[str] = Field(default_factory=list, description="Key achievements")
    technologies_used: list[str] = Field(default_factory=list, description="Technologies used")


class AnalyzedResume(BaseModel):
    """Structured resume analysis output."""

    # Schema version (class-level constant)
    __version__ = "v1.1.0"

    # Target job titles (for downstream matching)
    target_job_titles: list[str] = Field(
        default_factory=list,
        description="3-5 suitable job titles for the candidate, ordered by relevance"
    )

    # Basic information
    candidate_name: str = Field(..., description="Candidate full name")
    current_title: str = Field(..., description="Current or most recent job title")
    total_experience_years: int = Field(..., ge=0, description="Total years of professional experience")

    # Skills (with proficiency assessment)
    technical_skills: list[Skill] = Field(default_factory=list, description="Technical skills with proficiency levels")
    soft_skills: list[str] = Field(default_factory=list, description="Soft skills list")

    # Work history
    work_experiences: list[WorkExperience] = Field(default_factory=list, description="Work experience history")

    # Achievements
    quantified_achievements: list[str] = Field(
        default_factory=list,
        description="Quantified achievements (e.g., 'Reduced latency by 40%')"
    )

    # Education (sorted by most recent first, then highest degree first)
    education: list[str] = Field(
        default_factory=list,
        description="Education history (most recent to oldest, highest to lowest degree)"
    )
    certifications: list[str] = Field(default_factory=list, description="Professional certifications")

    # Location and work authorization
    location: str = Field(..., description="Current location or preferred work location")
    relocate_willing: bool | None = Field(None, description="Willingness to relocate")
    work_right: str = Field(..., description="Work authorization/visa status")


class CoverLetterDraft(BaseModel):
    """Cover letter draft content."""

    # Schema version (class-level constant)
    __version__ = "v1.0.0"

    opening: str
    body_paragraphs: list[str]
    closing: str
    word_count: int


class ReviewResult(BaseModel):
    """Review metrics for generated content."""

    # Schema version (class-level constant)
    __version__ = "v1.0.0"

    overall_score: float
    relevance_score: float
    professionalism_score: float
    clarity_score: float
    issues: list[str]
    needs_revision: bool


SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {
    "AnalyzedJob": AnalyzedJob,
    "AnalyzedResume": AnalyzedResume,
    "CoverLetterDraft": CoverLetterDraft,
    "ReviewResult": ReviewResult,
}


__all__ = [
    "AnalyzedJob",
    "Skill",
    "WorkExperience",
    "AnalyzedResume",
    "CoverLetterDraft",
    "ReviewResult",
    "SCHEMA_REGISTRY",
]
