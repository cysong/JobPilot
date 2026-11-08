"""Tests for job title normalization (role family cache key)."""
from __future__ import annotations

import pytest

from app.modules.matching.families.normalize import TITLE_KEY_MAX_LENGTH, normalize_title


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Senior Software Engineer", "software engineer"),
        ("Software Engineer - Senior", "software engineer"),
        ("Intermediate Full Stack Developer", "full stack developer"),
        ("Junior QA Engineer", "qa engineer"),
        ("Graduate Data Analyst", "data analyst"),
        ("Lead Developer", "developer"),
        ("Principal Engineer", "engineer"),
        ("Staff Software Engineer", "software engineer"),
        ("Sr. Java Developer", "java developer"),
        ("Contract DevOps Engineer", "devops engineer"),
        ("Data Engineer (Fixed Term, 12 months)", "data engineer"),
        ("Fixed-term Business Analyst", "business analyst"),
        ("Part Time IT Support Technician", "it support technician"),
        ("Software Engineer II", "software engineer"),
        ("Support Engineer Level 2", "support engineer"),
        ("Senior C++ Software Engineer", "c++ software engineer"),
        ("Senior Software Engineer – C# / .NET / Azure / SQL", "software engineer - c# / .net / azure / sql"),
        ("Technical Lead - Data Platform", "technical lead - data platform"),
        ("Tech Lead", "tech lead"),
        ("Team Lead", "team lead"),
        ("Head of Engineering", "head of engineering"),
        ("Engineering Manager", "engineering manager"),
        ("Mobile App Tester (Remote)", "mobile app tester"),
        ("  Software   Developer  ", "software developer"),
        ("Kaiwhakahaere Pūnaha", "kaiwhakahaere punaha"),
        ("Intermediate/Senior Backend Engineer (.NET)", "backend engineer"),
        ("Entry Level Support Engineer", "support engineer"),
        ("Intern - Data Analyst", "data analyst"),
        ("Core Network DevOps Principal Engineer - 12 month FTC", "core network devops principal engineer"),
        ("Health & Safety Systems Advisor - Maternity Cover", "health & safety systems advisor"),
        ("Data Engineer - 6-month contract", "data engineer"),
        ("Principal Software Engineer", "software engineer"),
        ("Graduate Software Developer", "software developer"),
    ],
)
def test_normalize_title(title, expected):
    assert normalize_title(title) == expected


@pytest.mark.parametrize("title", ["Senior", "Lead", "Contract", "Graduate"])
def test_never_empties_a_non_empty_title(title):
    assert normalize_title(title) == title.lower()


def test_empty_and_none():
    assert normalize_title(None) == ""
    assert normalize_title("") == ""


def test_seniority_variants_share_a_key():
    keys = {
        normalize_title(t)
        for t in ["Senior Software Engineer", "Software Engineer", "Junior Software Engineer", "Lead Software Engineer"]
    }
    assert keys == {"software engineer"}


def test_key_is_truncated():
    assert len(normalize_title("a" * 800)) == TITLE_KEY_MAX_LENGTH
