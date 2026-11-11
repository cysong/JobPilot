"""Pydantic schemas for Agent structured outputs."""
from __future__ import annotations

from typing import Any, Literal, Optional

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


class SkillEvidence(BaseModel):
    """Structured evidence for where a skill is demonstrated in the resume."""

    category: str = Field(
        ...,
        description=(
            "Normalized source category: experience, project, education, summary, "
            "certification, or other. Never use skills-list categories."
        ),
    )
    source_label: Optional[str] = Field(
        default=None,
        description="Short identifier for the source, such as company/role, project name, or school/program",
    )
    quotes: list[str] = Field(
        default_factory=list,
        description="Short verbatim snippets from the resume showing this skill in use",
    )


class Skill(BaseModel):
    """Standardized skill with proficiency."""

    name: str = Field(..., description="Standardized skill name (e.g., 'Python', 'React', 'Docker')")
    proficiency: ProficiencyLevel = Field(..., description="Proficiency level")
    extracted_from: list[SkillEvidence] = Field(
        default_factory=list,
        description=(
            "Evidence sources for this skill from non-skills-list resume sections only. "
            "Use normalized categories like experience, project, education, summary, "
            "certification, or other."
        ),
    )


class WorkExperience(BaseModel):
    """Work experience entry."""

    company: str = Field(..., description="Company name")
    role: str = Field(..., description="Job title/role")
    duration: list[str] = Field(
        ...,
        description="Start and end date [from, to]",
        min_length=2,
        max_length=2,
    )
    key_achievements: list[str] = Field(default_factory=list, description="Key achievements")
    technologies_used: list[str] = Field(default_factory=list, description="Technologies used")


class AnalyzedResume(BaseModel):
    """Structured resume analysis output."""

    # Schema version (class-level constant)
    __version__ = "v1.2.0"

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

    content: str = Field(..., description="Complete cover letter in markdown/plain text")


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


class TailoredResume(BaseModel):
    """Tailored resume content container."""

    __version__ = "v1.0.0"

    content: str = Field(..., description="Tailored resume content in markdown")


class TranslatedText(BaseModel):
    """Generic translation result with notes."""

    __version__ = "v1.0.0"

    content: str = Field(..., description="Translated content preserving original format")
    notes: list[str] = Field(default_factory=list, description="Notes about untranslatable parts or placeholders kept as-is")


class MatchAnalysis(BaseModel):
    """AI match analysis output."""

    __version__ = "v1.0.0"

    ai_match_score: float = Field(..., ge=0, le=100)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    tailoring_suggestions: list[str] = Field(default_factory=list)
    hidden_matches: list[str] = Field(default_factory=list)
    coverletter_strategies: list[str] = Field(
        default_factory=list,
        description="3 concise angles to emphasize in a cover letter (e.g., technical edge, industry experience, culture fit)",
        min_length=0,
        max_length=5,
    )



# ===== Matching v3 (docs/job_matching_v3_design.md) =====
# Role family keys are validated in code against role_families.yaml rather than
# enumerated here, so the families config can change without a schema change.


class TitleClassificationItem(BaseModel):
    """Role family for one normalized job title."""

    title_key: str = Field(..., description="The title_key exactly as given in the input")
    role_family: Optional[str] = Field(
        ..., description="One family key from the catalog, or null when ambiguous"
    )
    ambiguous: bool = Field(
        ..., description="True when the title alone cannot decide the family (e.g. 'engineer', 'consultant')"
    )


class TitleClassificationBatch(BaseModel):
    """Batch output of the title_classifier agent."""

    __version__ = "c1"

    items: list[TitleClassificationItem]


class JobFamilyReading(BaseModel):
    """Role family decided by reading the title plus a JD excerpt."""

    __version__ = "r1"

    role_family: str = Field(..., description="One family key from the catalog")
    reason: str = Field(..., description="One short sentence explaining the choice")


class JudgeEvidence(BaseModel):
    job_quote: Optional[str] = Field(..., description="Verbatim text from the job description, or null")
    resume_quote: Optional[str] = Field(..., description="Verbatim text from the chosen resume or skill library, or null")


class JudgeTechItem(BaseModel):
    requirement: str = Field(..., description="The job requirement, verbatim")
    is_core: bool = Field(..., description="True when this requirement defines the role")
    relation: Literal["same", "substitute", "missing"]
    evidence: JudgeEvidence


class WorkRightsCheck(BaseModel):
    requirement: Literal["none", "right_to_work", "pr_or_citizen", "citizen"]
    quote: Optional[str] = Field(..., description="Verbatim JD sentence; null when requirement is none")
    satisfied: Optional[bool] = Field(..., description="Null when the candidate status is unknown")


class ClearanceCheck(BaseModel):
    requirement: Literal["none", "obtainable", "must_hold"]
    quote: Optional[str] = Field(..., description="Verbatim JD sentence; null when requirement is none")
    satisfied: Optional[bool] = Field(..., description="Null when the candidate status is unknown")


class WorkLocationCheck(BaseModel):
    requirement: Literal["none", "onsite_outside_candidate_country", "resident_outside_candidate_country"]
    country: Optional[str] = Field(..., description="Country the job requires, or null when requirement is none")
    quote: Optional[str] = Field(..., description="Verbatim JD sentence; null when requirement is none")
    satisfied: Optional[bool] = Field(..., description="Null when nothing is required")


class LanguageCheck(BaseModel):
    required_languages: list[str] = Field(
        ..., description="Spoken/written languages the JD explicitly requires (not programming languages)"
    )
    quote: Optional[str] = Field(..., description="Verbatim JD sentence; null when nothing is required")
    satisfied: Optional[bool] = Field(..., description="Null when the candidate languages are unknown")


class EmploymentCheck(BaseModel):
    kind: Literal["employment", "non_employment"] = Field(
        ..., description="non_employment: crowd work, paid-per-task / hourly gig platforms, AI training or evaluation tasks"
    )
    quote: Optional[str] = Field(..., description="Verbatim JD sentence showing non-employment; null for employment")


class PeopleManagementCheck(BaseModel):
    required: bool = Field(..., description="True when the JD requires managing people (direct reports, hiring, performance)")
    job_quote: Optional[str] = Field(..., description="Verbatim JD sentence; null when not required")
    candidate_has: bool = Field(..., description="True when a dated work entry in the chosen resume shows managing people")
    resume_quote: Optional[str] = Field(..., description="Verbatim resume text; null when the candidate has none")


class OtherConstraint(BaseModel):
    requirement: str = Field(..., description="Short description, e.g. 'Full NZ driver licence'")
    quote: str = Field(..., description="Verbatim JD sentence")


class JudgeRejection(BaseModel):
    code: Literal["WORK_RIGHTS", "SECURITY_CLEARANCE", "WORK_LOCATION", "LANGUAGE", "NOT_EMPLOYMENT"]
    reason: str = Field(..., description="One sentence")
    quote: str = Field(..., description="Verbatim JD sentence stating the requirement")


class MatchJudgment(BaseModel):
    """Output of the match_judge agent. Field order is deliberate: checks before conclusions."""

    __version__ = "j3"

    decision: Literal["rated", "rejected"]
    rejection: Optional[JudgeRejection] = Field(..., description="Required when decision is rejected, else null")
    work_rights: WorkRightsCheck
    security_clearance: ClearanceCheck
    work_location: WorkLocationCheck
    languages: LanguageCheck
    employment: EmploymentCheck
    other_constraints: list[OtherConstraint] = Field(
        ..., description="Other hard requirements the candidate should know about (not used to reject)"
    )
    best_resume_id: str = Field(..., description="One of the candidate resume ids")
    is_different_track: bool = Field(..., description="True when the job is a different career track (tier D)")
    seniority_mismatch: bool = Field(..., description="True when seniority is severely mismatched (tier C)")
    people_management: PeopleManagementCheck
    tech_level: Literal["strong", "partial", "weak"]
    tech_items: list[JudgeTechItem] = Field(..., description="Core and must-have requirements, at most 12")
    experience_level: Literal["strong", "partial", "none"]
    relevant_years: Optional[float] = Field(..., description="Years of relevant dated work experience")
    required_years: Optional[float] = Field(..., description="Minimum years stated in the JD, or null")
    experience_evidence: list[JudgeEvidence]
    tier: Literal["A", "B", "C", "D"]
    tier_reason: str = Field(..., description="1-2 sentences citing concrete requirements and evidence")


SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {
    "AnalyzedJob": AnalyzedJob,
    "Skill": Skill,
    "WorkExperience": WorkExperience,
    "AnalyzedResume": AnalyzedResume,
    "CoverLetterDraft": CoverLetterDraft,
    "ReviewResult": ReviewResult,
    "TailoredResume": TailoredResume,
    "TranslatedText": TranslatedText,
    "MatchAnalysis": MatchAnalysis,
    "TitleClassificationBatch": TitleClassificationBatch,
    "JobFamilyReading": JobFamilyReading,
    "MatchJudgment": MatchJudgment,
}


__all__ = [
    "AnalyzedJob",
    "Skill",
    "WorkExperience",
    "AnalyzedResume",
    "CoverLetterDraft",
    "ReviewResult",
    "TailoredResume",
    "MatchAnalysis",
    "TitleClassificationBatch",
    "JobFamilyReading",
    "MatchJudgment",
    "SCHEMA_REGISTRY",
]
