"""Pydantic schemas for Agent structured outputs."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class AnalyzedJob(BaseModel):
    """Job description analysis output."""

    required_skills: list[str]
    optional_skills: list[str]
    soft_skills: list[str]
    experience_years: str
    markdown_content: str
    translated_content: str


class AnalyzedResume(BaseModel):
    """Resume analysis output."""

    technical_skills: list[str]
    soft_skills: list[str]
    work_experiences: list[dict[str, Any]]
    quantified_achievements: list[str]


class CoverLetterDraft(BaseModel):
    """Cover letter draft content."""

    opening: str
    body_paragraphs: list[str]
    closing: str
    word_count: int


class ReviewResult(BaseModel):
    """Review metrics for generated content."""

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
