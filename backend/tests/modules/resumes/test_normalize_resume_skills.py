"""Tests for cleaning one resume's LLM skill list before it is stored."""
from __future__ import annotations

from app.modules.resumes.service import ResumeService
from app.shared.enums import ProficiencyLevel
from app.shared.skills import skill_key

EVIDENCE = [{"category": "experience", "source_label": "ACME", "quotes": ["built it"]}]


def _normalize(skills: list[dict]) -> dict[str, dict]:
    return ResumeService.normalize_resume_skills(skills)


def test_aliases_and_casing_collapse_keeping_highest_level_and_all_evidence() -> None:
    other = [{"category": "project", "source_label": "Side", "quotes": ["used it"]}]
    result = _normalize([
        {"name": "CSS3", "proficiency": "intermediate", "extracted_from": EVIDENCE},
        {"name": "css", "proficiency": "advanced", "extracted_from": other},
    ])
    assert list(result) == [skill_key("CSS")]
    entry = result[skill_key("CSS")]
    assert entry["name"] == "CSS"
    assert entry["proficiency"] == ProficiencyLevel.ADVANCED
    assert entry["extracted_from"] == EVIDENCE + other


def test_skill_without_evidence_capped_at_intermediate() -> None:
    result = _normalize([
        {"name": "Docker", "proficiency": "expert", "extracted_from": []},
        {"name": "Kubernetes", "proficiency": "advanced"},
        {"name": "Redis", "proficiency": "beginner", "extracted_from": []},
        {"name": "Python", "proficiency": "expert", "extracted_from": EVIDENCE},
    ])
    levels = {entry["name"]: entry["proficiency"] for entry in result.values()}
    assert levels == {
        "Docker": ProficiencyLevel.INTERMEDIATE,
        "Kubernetes": ProficiencyLevel.INTERMEDIATE,
        "Redis": ProficiencyLevel.BEGINNER,
        "Python": ProficiencyLevel.EXPERT,
    }
    assert result[skill_key("Docker")]["extracted_from"] is None


def test_unknown_level_defaults_to_intermediate_and_blank_names_skipped() -> None:
    result = _normalize([
        {"name": "Go", "proficiency": "guru", "extracted_from": EVIDENCE},
        {"name": "   ", "proficiency": "expert"},
        {"proficiency": "expert"},
    ])
    assert [(e["name"], e["proficiency"]) for e in result.values()] == [("Go", ProficiencyLevel.INTERMEDIATE)]
