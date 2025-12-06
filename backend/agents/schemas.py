"""Pydantic schemas for Agent structured outputs."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class AnalyzedJob(BaseModel):
    """
    Job description analysis output (Agent response).

    Updated schema with extended fields for comprehensive job analysis.
    """

    # Schema version (class-level constant)
    __version__ = "v1.0.0"

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


class AnalyzedResume(BaseModel):
    """Resume analysis output."""

    # Schema version (class-level constant)
    __version__ = "v1.0.0"

    technical_skills: list[str]
    soft_skills: list[str]
    work_experiences: list[dict[str, Any]]
    quantified_achievements: list[str]


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
    "AnalyzedResume",
    "CoverLetterDraft",
    "ReviewResult",
    "SCHEMA_REGISTRY",
]
