"""Tests for match planning and judge_pair orchestration (gateway mocked)."""
from __future__ import annotations

import copy
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from agents.exceptions import ModelBehaviorError

from app.core.llm.types import ModelOverride
from app.modules.matching.judge.input_builder import (
    CandidateConditions,
    CandidateResume,
    JobInput,
    SkillLibraryEntry,
)
from app.modules.matching.judge.service import (
    JobContext,
    JudgeFailure,
    UserContext,
    fallback_candidates,
    judge_pair,
    plan_match,
)
from app.modules.matching.prefilter import ResumeRef

NOW = datetime(2026, 11, 8, tzinfo=timezone.utc)

RESUMES = (
    CandidateResume("res_java", "Java Developer", "software_dev",
                    "## Experience\n- Built Java Spring services", ({"duration": ["2016-01", "2022-01"]},)),
    CandidateResume("res_qa", "SDET", "qa_test", "- Selenium automation", ()),
)
USER = UserContext(
    user_id=1,
    job_locations=("Christchurch",),
    conditions=CandidateConditions("work_visa", None),
    resumes=RESUMES,
    resume_refs=(
        ResumeRef("res_java", "software_dev", NOW),
        ResumeRef("res_qa", "qa_test", NOW - timedelta(days=1)),
    ),
    skills=(SkillLibraryEntry("Azure", "INTERMEDIATE", ("Deployed to Azure",)),),
)


def _job(city="Christchurch", label="Christchurch, Canterbury", description="- 5+ years Java\n- Azure"):
    return JobContext(
        job=JobInput(42, "Senior Java Developer", label, "Full time", NOW, description),
        location_city=city, is_expired=False, manual_expired=False, expires_at=None, company="Acme",
    )


JUDGMENT = {
    "decision": "rated", "rejection": None,
    "work_rights": {"requirement": "none", "quote": None, "satisfied": None},
    "security_clearance": {"requirement": "none", "quote": None, "satisfied": None},
    "work_location": {"requirement": "none", "country": None, "quote": None, "satisfied": None},
    "languages": {"required_languages": [], "quote": None, "satisfied": None},
    "employment": {"kind": "employment", "quote": None},
    "other_constraints": [],
    "best_resume_id": "res_java", "is_different_track": False, "seniority_mismatch": False,
    "people_management": {"required": False, "job_quote": None, "candidate_has": False, "resume_quote": None},
    "tech_level": "partial",
    "tech_items": [{"requirement": "5+ years Java", "is_core": True, "relation": "same",
                    "evidence": {"job_quote": "5+ years Java", "resume_quote": "Built Java Spring services"}}],
    "experience_level": "strong", "relevant_years": 6.0, "required_years": 5.0,
    "experience_evidence": [], "tier": "B", "tier_reason": "Java matches; Azure only via skill library.",
}


# ------------------------------------------------------------------ plan_match


def test_plan_same_family_and_location_match():
    plan = plan_match(job_family="software_dev", user=USER, job=_job())
    assert plan.prefilter == "same"
    assert plan.candidate_ids == ("res_java",)
    assert plan.location.status == "matched"


def test_plan_adjacent_when_no_same_family_resume():
    plan = plan_match(job_family="devops_platform", user=USER, job=_job())
    assert plan.prefilter == "adjacent"
    assert set(plan.candidate_ids) == {"res_java", "res_qa"}


def test_plan_filtered_for_unrelated_family():
    plan = plan_match(job_family="other", user=USER, job=_job())
    assert plan.prefilter == "filtered"
    assert plan.candidate_ids == ()


def test_plan_location_rejected_keeps_candidates():
    plan = plan_match(job_family="software_dev", user=USER, job=_job("Auckland", "Auckland CBD, Auckland"))
    assert plan.prefilter == "location_rejected"
    assert plan.candidate_ids == ("res_java",)


def test_plan_unknown_location_is_not_rejected():
    plan = plan_match(job_family="software_dev", user=USER, job=_job(None, "New Zealand"))
    assert plan.prefilter == "same"
    assert plan.location.status == "unknown"


def test_fallback_candidates_are_most_recent():
    assert fallback_candidates(USER) == ("res_java", "res_qa")


# ------------------------------------------------------------------ judge_pair


@pytest.mark.asyncio
async def test_judge_pair_success_passes_override_and_context():
    gateway = AsyncMock()
    gateway.call = AsyncMock(return_value=copy.deepcopy(JUDGMENT))
    override = ModelOverride(provider="openrouter", model="openai/gpt-6.1-sol")

    outcome, ctx = await judge_pair(
        gateway, user=USER, job=_job(), candidate_ids=["res_java"],
        model_override=override, context={"task_id": "t1"}, today=date(2026, 11, 8),
    )

    assert outcome.tier == "B"
    assert outcome.validation["structure_retries"] == 0
    agent_id, prompt = gateway.call.await_args.args
    assert agent_id == "match_judge"
    assert "=== resume_id: res_java" in prompt and "res_qa" not in prompt
    assert "- Azure (INTERMEDIATE)" in prompt  # skill library supplement
    assert gateway.call.await_args.kwargs["model_override"] is override
    assert ctx["task_id"] == "t1" and ctx["user_id"] == 1 and ctx["operation"] == "match_judge"


@pytest.mark.asyncio
async def test_judge_pair_retries_structural_errors_then_succeeds():
    bad = copy.deepcopy(JUDGMENT)
    bad["best_resume_id"] = "res_unknown"
    gateway = AsyncMock()
    gateway.call = AsyncMock(side_effect=[bad, copy.deepcopy(JUDGMENT)])

    outcome, _ = await judge_pair(gateway, user=USER, job=_job(), candidate_ids=["res_java"])

    assert gateway.call.await_count == 2
    assert outcome.validation["structure_retries"] == 1


@pytest.mark.asyncio
async def test_judge_pair_gives_up_after_retries():
    bad = copy.deepcopy(JUDGMENT)
    bad["tier"] = "Z"
    gateway = AsyncMock()
    gateway.call = AsyncMock(return_value=bad)

    with pytest.raises(JudgeFailure) as info:
        await judge_pair(gateway, user=USER, job=_job(), candidate_ids=["res_java"])
    assert info.value.retryable is False
    assert gateway.call.await_count == 3


@pytest.mark.asyncio
async def test_judge_pair_retries_invalid_json_then_succeeds():
    gateway = AsyncMock()
    gateway.call = AsyncMock(side_effect=[ModelBehaviorError("Invalid JSON when parsing {"),
                                          copy.deepcopy(JUDGMENT)])

    outcome, _ = await judge_pair(gateway, user=USER, job=_job(), candidate_ids=["res_java"])

    assert gateway.call.await_count == 2
    assert outcome.validation["structure_retries"] == 1


@pytest.mark.asyncio
async def test_judge_pair_repeated_invalid_json_stays_retryable():
    gateway = AsyncMock()
    gateway.call = AsyncMock(side_effect=ModelBehaviorError("Invalid JSON when parsing {"))

    with pytest.raises(JudgeFailure) as info:
        await judge_pair(gateway, user=USER, job=_job(), candidate_ids=["res_java"])
    assert info.value.retryable is True
    assert gateway.call.await_count == 3


@pytest.mark.asyncio
async def test_judge_pair_gateway_error_is_retryable():
    gateway = AsyncMock()
    gateway.call = AsyncMock(side_effect=TimeoutError("slow"))
    with pytest.raises(JudgeFailure) as info:
        await judge_pair(gateway, user=USER, job=_job(), candidate_ids=["res_java"])
    assert info.value.retryable is True


@pytest.mark.asyncio
async def test_judge_pair_without_candidates_fails_fast():
    gateway = AsyncMock()
    with pytest.raises(JudgeFailure) as info:
        await judge_pair(gateway, user=USER, job=_job(), candidate_ids=["res_missing"])
    assert info.value.retryable is False
    gateway.call.assert_not_called()


def test_fallback_candidates_skip_resumes_without_family():
    import dataclasses
    user = dataclasses.replace(USER, resume_refs=(
        ResumeRef("res_unbound", None, NOW + timedelta(days=1)),
        *USER.resume_refs,
    ))
    assert fallback_candidates(user) == ("res_java", "res_qa")


# ------------------------------------------------------------------ judge_override


def test_judge_override_defaults_to_yaml_settings(monkeypatch):
    from app.core.config import settings
    from app.modules.matching.judge.service import judge_override

    monkeypatch.setattr(settings, "MATCH_JUDGE_MODEL", "openai/gpt-6.1-terra")
    monkeypatch.setattr(settings, "MATCH_JUDGE_REASONING_EFFORT", None)
    monkeypatch.setattr(settings, "MATCH_JUDGE_OPENROUTER_PROVIDERS", [])
    override = judge_override()
    assert override.model == "openai/gpt-6.1-terra"
    assert override.model_settings == {}


def test_judge_override_applies_configured_effort_and_hosts(monkeypatch):
    from app.core.config import settings
    from app.modules.matching.judge.service import judge_override

    monkeypatch.setattr(settings, "MATCH_LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(settings, "MATCH_JUDGE_MODEL", "deepseek/deepseek-v4.1-flash-1017")
    monkeypatch.setattr(settings, "MATCH_JUDGE_REASONING_EFFORT", "xhigh")
    monkeypatch.setattr(settings, "MATCH_JUDGE_OPENROUTER_PROVIDERS", ["deepinfra/fp8", "morph/fp8"])

    assert judge_override().model_settings == {
        "reasoning": {"effort": "xhigh"},
        "extra_body": {"provider": {"only": ["deepinfra/fp8", "morph/fp8"]}},
    }
    # Tuning for the configured model does not leak onto another model (e.g. an eval baseline).
    assert judge_override(model="openai/gpt-6.1-terra").model_settings == {}
    # Explicit arguments win; an empty host list means any host.
    assert judge_override(reasoning_effort="high", openrouter_providers=[]).model_settings == {
        "reasoning": {"effort": "high"}}


@pytest.mark.parametrize("raw", ['["morph/fp8", "river"]', "morph/fp8, river", " morph/fp8,river, "])
def test_judge_host_list_parses_json_or_comma_env(raw, monkeypatch):
    from app.core.config import Settings

    monkeypatch.setenv("MATCH_JUDGE_OPENROUTER_PROVIDERS", raw)
    assert Settings().MATCH_JUDGE_OPENROUTER_PROVIDERS == ["morph/fp8", "river"]
