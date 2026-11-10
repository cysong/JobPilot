"""Tests for skill name normalisation and proficiency ordering."""
from __future__ import annotations

import pytest

from app.shared.enums import ProficiencyLevel
from app.shared.skills import (
    canonical_skill_name,
    highest_proficiency,
    is_known_canonical,
    proficiency_rank,
    skill_key,
    to_proficiency,
)


@pytest.mark.parametrize(
    "a, b",
    [
        ("Pytest", "pytest"),
        ("Shell Scripting", "Shell scripting"),
        ("Node.js", "NodeJS"),
        ("Node.js", "node js"),
        ("CI/CD", "CICD"),
        ("CI/CD", "Continuous Integration and Continuous Delivery"),
        ("CSS", "CSS3"),
        ("HTML", "HTML5"),
        ("JMeter", "Apache JMeter"),
        ("JPA", "Java Persistence API"),
        ("Shell Scripting", "Shell"),
        ("Kubernetes", "k8s"),
        ("JavaScript", "JS"),
    ],
)
def test_same_skill_same_key(a: str, b: str) -> None:
    assert skill_key(a) == skill_key(b)


@pytest.mark.parametrize(
    "a, b",
    [
        ("C", "C++"),
        ("C", "C#"),
        ("C++", "C#"),
        ("Java", "JavaScript"),
        ("Spring Framework", "Spring Boot"),
        ("AWS", "Amazon S3"),
        ("SQL", "MySQL"),
    ],
)
def test_different_skills_different_keys(a: str, b: str) -> None:
    assert skill_key(a) != skill_key(b)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("CSS3", "CSS"),
        ("apache jmeter", "JMeter"),
        ("Continuous Integration and Continuous Delivery", "CI/CD"),
        ("nodejs", "Node.js"),
        ("  Some   Niche Tool ", "Some Niche Tool"),  # unknown: only whitespace tidied
        ("pytest", "pytest"),  # unknown casing is left to the aggregation's majority vote
    ],
)
def test_canonical_skill_name(raw: str, expected: str) -> None:
    assert canonical_skill_name(raw) == expected


def test_is_known_canonical() -> None:
    assert is_known_canonical("css3")
    assert not is_known_canonical("Some Niche Tool")


def test_rank_follows_level_order_not_alphabet() -> None:
    ranks = [proficiency_rank(level) for level in ("beginner", "intermediate", "advanced", "expert")]
    assert ranks == sorted(ranks) and len(set(ranks)) == 4
    assert proficiency_rank("garbage") == 0
    assert proficiency_rank(None) == 0


def test_highest_proficiency() -> None:
    # Alphabetical MAX would pick INTERMEDIATE here.
    levels = [ProficiencyLevel.EXPERT, ProficiencyLevel.INTERMEDIATE, ProficiencyLevel.ADVANCED]
    assert highest_proficiency(levels) == ProficiencyLevel.EXPERT
    assert highest_proficiency(["BEGINNER", "advanced", None, "bad"]) == ProficiencyLevel.ADVANCED
    assert highest_proficiency([]) is None


def test_to_proficiency_accepts_names_and_values() -> None:
    assert to_proficiency("EXPERT") == ProficiencyLevel.EXPERT
    assert to_proficiency(" expert ") == ProficiencyLevel.EXPERT
    assert to_proficiency("unknown") is None
