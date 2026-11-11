"""Tests for match_judge input building and work history years."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.modules.matching.judge.input_builder import (
    CandidateConditions,
    CandidateResume,
    JobInput,
    SkillLibraryEntry,
    build_judge_input,
    skill_library_supplement,
    work_history_years,
)

JAVA = CandidateResume(
    id="res_java",
    title="Java Developer",
    role_family="software_dev",
    content="## Experience\n- Built services with Java, Spring Boot and Kafka\n- Used C# on a side project",
)
JOB = JobInput(
    id=7,
    title="Senior .NET Developer",
    location_label="Christchurch, Canterbury",
    work_types_label="Full time",
    listed_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
    description="- 5+ years C#\n- Azure",
)


def test_sections_are_ordered_for_prefix_caching():
    text = build_judge_input(
        conditions=CandidateConditions(work_rights="work_visa", security_clearance=None),
        resumes=[JAVA],
        extra_skills=[SkillLibraryEntry("Azure", "INTERMEDIATE", ["Deployed to Azure App Service"])],
        job=JOB,
    )
    order = [text.index(h) for h in (
        "[CANDIDATE CONDITIONS]", "[CANDIDATE RESUMES]", "[ADDITIONAL SKILLS FROM SKILL LIBRARY]", "[JOB]"
    )]
    assert order == sorted(order)
    assert text.rstrip().endswith("- Azure")  # the job description is last
    assert "work_rights: work_visa" in text
    assert "security_clearance: unknown" in text
    assert "located_in: New Zealand" in text
    assert "languages: unknown" in text
    assert "=== resume_id: res_java" in text
    assert '- Azure (INTERMEDIATE). evidence: "Deployed to Azure App Service"' in text
    assert "listed_at: 2026-11-01" in text


def test_prefix_is_identical_across_jobs_for_the_same_user():
    common = dict(
        conditions=CandidateConditions("citizen", "holds"), resumes=[JAVA], extra_skills=[]
    )
    a = build_judge_input(job=JOB, **common)
    b = build_judge_input(job=JobInput(8, "Other", None, None, None, "x"), **common)
    prefix = a[: a.index("[JOB]")]
    assert b.startswith(prefix)
    assert "(none)" in prefix  # no extra skills


def test_manual_skill_without_evidence():
    text = build_judge_input(
        conditions=CandidateConditions(None, None),
        resumes=[JAVA],
        extra_skills=[SkillLibraryEntry("Terraform", "BEGINNER", [])],
        job=JOB,
    )
    assert "- Terraform (BEGINNER). evidence: (added manually)" in text


def test_skill_library_supplement_only_returns_unmentioned_skills():
    skills = [
        SkillLibraryEntry("Java", "EXPERT"),
        SkillLibraryEntry("Kafka", "ADVANCED"),
        SkillLibraryEntry("C#", "BEGINNER"),
        SkillLibraryEntry("C", "BEGINNER"),  # must not match inside "C#"
        SkillLibraryEntry("Azure", "INTERMEDIATE"),
        SkillLibraryEntry("Script", "BEGINNER"),  # must not match inside "JavaScript"-like words
        SkillLibraryEntry("  ", "BEGINNER"),
    ]
    names = [s.skill_name for s in skill_library_supplement(skills, [JAVA])]
    assert names == ["Azure", "C", "Script"]


@pytest.mark.parametrize(
    ("experiences", "expected"),
    [
        ([{"duration": ["2020-01", "2020-12"]}], 1.0),
        ([{"duration": ["2015-08", "2020-08"]}, {"duration": ["2021-04", "2022-08"]}], 6.5),
        # Overlapping roles are not double counted.
        ([{"duration": ["2020-01", "2021-12"]}, {"duration": ["2021-01", "2022-12"]}], 3.0),
        ([{"duration": ["2025-02", "Present"]}], 1.83),
        ([{"duration": ["2019"]}], 7.92),  # open-ended entry runs to today (Jan 2019..Nov 2026)
        ([{"duration": ["bad", "2020-01"]}, {"duration": []}, {}], 0.0),
        ([{"duration": ["2022-01", "2021-01"]}], 0.0),  # end before start ignored
        ([], 0.0),
    ],
)
def test_work_history_years(experiences, expected):
    assert work_history_years(experiences, today=date(2026, 11, 8)) == pytest.approx(expected, abs=0.01)


def test_conditions_include_country_and_languages():
    text = build_judge_input(
        conditions=CandidateConditions("work_visa", "not_eligible", country="New Zealand",
                                       languages=("English", "Chinese")),
        resumes=[JAVA], extra_skills=[], job=JOB,
    )
    assert "languages: English, Chinese (Mandarin, Cantonese)" in text


def test_describe_languages_adds_varieties():
    from app.modules.matching.judge.input_builder import describe_languages

    assert describe_languages(["Mandarin", "english"]) == "Mandarin (Chinese), english"
    assert describe_languages(["chinese"]) == "chinese (Mandarin, Cantonese)"
