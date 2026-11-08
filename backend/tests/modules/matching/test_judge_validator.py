"""Tests for match_judge output validation."""
from __future__ import annotations

import copy

import pytest

from app.modules.matching.judge.input_builder import CandidateConditions
from app.modules.matching.judge.validator import JudgmentStructureError, validate_judgment

JD = (
    "Senior .NET Developer\n"
    "- 5+ years of C# and .NET\n"
    "- Experience with Microsoft Azure\n"
    "Applicants must be NZ citizens or permanent residents.\n"
    "Must be able to obtain a NZ Government security clearance."
)
RESUME = "## Experience\n- Built ASP.NET Core APIs in C# for 6 years\n- Deployed to Azure App Service"
SKILLS = ["Kubernetes (ADVANCED) Ran clusters on AKS"]

BASE = {
    "decision": "rated",
    "rejection": None,
    "work_rights": {"requirement": "pr_or_citizen",
                    "quote": "Applicants must be NZ citizens or permanent residents.", "satisfied": True},
    "security_clearance": {"requirement": "none", "quote": None, "satisfied": None},
    "best_resume_id": "res_1",
    "is_different_track": False,
    "seniority_mismatch": False,
    "tech_level": "strong",
    "tech_items": [
        {"requirement": "5+ years of C# and .NET", "is_core": True, "relation": "same",
         "evidence": {"job_quote": "5+ years of C# and .NET",
                      "resume_quote": "Built ASP.NET Core APIs in C# for 6 years"}},
        {"requirement": "Kubernetes", "is_core": False, "relation": "same",
         "evidence": {"job_quote": None, "resume_quote": "Ran clusters on AKS"}},
    ],
    "experience_level": "strong",
    "relevant_years": 6.0,
    "required_years": 5.0,
    "experience_evidence": [{"job_quote": None, "resume_quote": "Deployed to Azure App Service"}],
    "tier": "A",
    "tier_reason": "6 years of C#/.NET on Azure matches the core stack.",
}


def _validate(raw, *, wr="citizen", sc=None, years=6.5, candidates=("res_1", "res_2")):
    return validate_judgment(
        raw,
        candidate_ids=list(candidates),
        job_text=JD,
        resume_texts={"res_1": RESUME, "res_2": "other resume"},
        skill_texts=SKILLS,
        conditions=CandidateConditions(work_rights=wr, security_clearance=sc),
        history_years={"res_1": years, "res_2": 1.0},
    )


def _judgment(**changes):
    data = copy.deepcopy(BASE)
    data.update(changes)
    return data


def test_clean_judgment_passes_through():
    out = _validate(_judgment())
    assert out.status == "rated"
    assert (out.tier, out.tech_level, out.experience_level, out.resume_id) == ("A", "strong", "strong", "res_1")
    assert out.reject_code is None
    assert out.validation == {"consistency_fixes": [], "flags": [], "quotes_total": 4, "quotes_unverified": 0}


def test_valid_rejection():
    raw = _judgment(
        decision="rejected",
        rejection={"code": "WORK_RIGHTS", "reason": "Requires PR; candidate has a work visa.",
                   "quote": "Applicants must be NZ citizens or permanent residents."},
        tier="B",
    )
    out = _validate(raw, wr="work_visa")
    assert out.status == "rejected"
    assert out.reject_code == "WORK_RIGHTS"
    assert out.tier == "B"  # tier kept for reference


def test_rejection_with_invented_quote_is_reverted():
    raw = _judgment(
        decision="rejected",
        rejection={"code": "WORK_RIGHTS", "reason": "x", "quote": "Must be a NZ citizen."},
    )
    out = _validate(raw, wr="work_visa")
    assert out.status == "rated"
    assert out.reject_code is None
    assert "rejection_quote_not_found" in out.validation["consistency_fixes"]


def test_rejection_on_unknown_status_is_reverted():
    raw = _judgment(
        decision="rejected",
        rejection={"code": "SECURITY_CLEARANCE", "reason": "x",
                   "quote": "Must be able to obtain a NZ Government security clearance."},
    )
    out = _validate(raw, sc=None)
    assert out.status == "rated"
    assert "rejection_on_unknown_status" in out.validation["consistency_fixes"]


def test_constraint_with_unfound_quote_is_dropped():
    raw = _judgment(security_clearance={"requirement": "must_hold", "quote": "Current Secret clearance", "satisfied": False})
    out = _validate(raw, sc="eligible")
    assert out.judgment["security_clearance"] == {"requirement": "none", "quote": None, "satisfied": None}
    assert "constraint_quote_not_found:security_clearance" in out.validation["consistency_fixes"]


def test_unverified_quotes_are_flagged_not_dropped():
    raw = _judgment()
    raw["tech_items"][0]["evidence"]["resume_quote"] = "Led a team of 20 .NET engineers"
    raw["experience_evidence"][0]["job_quote"] = "10+ years required"
    out = _validate(raw)
    assert out.validation["quotes_unverified"] == 2
    assert out.judgment["tech_items"][0]["evidence"]["resume_quote_unverified"] is True
    assert out.judgment["experience_evidence"][0]["job_quote_unverified"] is True


def test_skill_library_quotes_are_accepted():
    out = _validate(_judgment())
    assert "resume_quote_unverified" not in out.judgment["tech_items"][1]["evidence"]


def test_years_beyond_history_are_flagged():
    assert "years_exceeds_history" in _validate(_judgment(relevant_years=9.0), years=6.5).validation["flags"]
    assert _validate(_judgment(relevant_years=6.9), years=6.5).validation["flags"] == []


def test_flag_tier_conflicts_keep_llm_tier():
    out = _validate(_judgment(is_different_track=True, tier="C", seniority_mismatch=True))
    assert out.tier == "C"
    assert out.validation["flags"] == ["tier_flag_conflict:different_track"]
    out = _validate(_judgment(seniority_mismatch=True, tier="B"))
    assert out.tier == "B"
    assert out.validation["flags"] == ["tier_flag_conflict:seniority_mismatch"]


@pytest.mark.parametrize(
    "raw",
    [
        _judgment(best_resume_id="res_9"),
        _judgment(decision="rejected", rejection=None),
        _judgment(rejection={"code": "WORK_RIGHTS", "reason": "x", "quote": "y"}),
        _judgment(tier="E"),
        {k: v for k, v in BASE.items() if k != "tier"},
    ],
)
def test_structural_problems_raise_for_retry(raw):
    with pytest.raises(JudgmentStructureError):
        _validate(raw)
