"""Tests for match_judge output validation."""
from __future__ import annotations

import copy

import pytest

from app.modules.matching.judge.input_builder import CandidateConditions
from app.modules.matching.judge.validator import JudgmentStructureError, capped_tier, validate_judgment

JD = (
    "Senior .NET Developer\n"
    "This role is based in our Sydney office.\n"
    "Fluent Japanese is required.\n"
    "A full NZ driver licence is required.\n"
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
    "work_location": {"requirement": "none", "country": None, "quote": None, "satisfied": None},
    "languages": {"required_languages": [], "quote": None, "satisfied": None},
    "employment": {"kind": "employment", "quote": None},
    "other_constraints": [],
    "best_resume_id": "res_1",
    "is_different_track": False,
    "seniority_mismatch": False,
    "people_management": {"required": False, "job_quote": None, "candidate_has": False, "resume_quote": None},
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


def _validate(raw, *, wr="citizen", sc=None, years=6.5, candidates=("res_1", "res_2"),
              languages=("English", "Chinese"), relation=None):
    return validate_judgment(
        raw,
        candidate_ids=list(candidates),
        job_text=JD,
        resume_texts={"res_1": RESUME, "res_2": "other resume"},
        skill_texts=SKILLS,
        conditions=CandidateConditions(work_rights=wr, security_clearance=sc, languages=tuple(languages)),
        history_years={"res_1": years, "res_2": 1.0},
        family_relation=relation,
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


def test_work_location_rejection():
    raw = _judgment(
        decision="rejected",
        rejection={"code": "WORK_LOCATION", "reason": "On site in Sydney.",
                   "quote": "This role is based in our Sydney office."},
        work_location={"requirement": "onsite_outside_candidate_country", "country": "Australia",
                       "quote": "This role is based in our Sydney office.", "satisfied": False},
    )
    out = _validate(raw)
    assert out.status == "rejected"
    assert out.reject_code == "WORK_LOCATION"


def test_language_rejection_needs_known_languages():
    raw = _judgment(
        decision="rejected",
        rejection={"code": "LANGUAGE", "reason": "Japanese required.", "quote": "Fluent Japanese is required."},
        languages={"required_languages": ["Japanese"], "quote": "Fluent Japanese is required.", "satisfied": False},
    )
    assert _validate(raw).status == "rejected"
    reverted = _validate(raw, languages=())
    assert reverted.status == "rated"
    assert "rejection_on_unknown_status" in reverted.validation["consistency_fixes"]


def test_location_and_language_checks_need_real_quotes():
    raw = _judgment(
        work_location={"requirement": "resident_outside_candidate_country", "country": "USA",
                       "quote": "Must live in the USA.", "satisfied": False},
        languages={"required_languages": ["German"], "quote": "German is required.", "satisfied": False},
    )
    out = _validate(raw)
    assert out.judgment["work_location"]["requirement"] == "none"
    assert out.judgment["languages"]["required_languages"] == []
    assert "constraint_quote_not_found:work_location" in out.validation["consistency_fixes"]
    assert "constraint_quote_not_found:languages" in out.validation["consistency_fixes"]


def test_other_constraints_keep_only_quoted():
    raw = _judgment(other_constraints=[
        {"requirement": "Driver licence", "quote": "A full NZ driver licence is required."},
        {"requirement": "Police vetting", "quote": "Police vetting will be done."},
    ])
    out = _validate(raw)
    assert [c["requirement"] for c in out.judgment["other_constraints"]] == ["Driver licence"]


# ------------------------------------------------------------------ v3: employment, people, caps

def test_non_employment_rejection_needs_no_candidate_status():
    raw = _judgment(decision="rejected",
                    rejection={"code": "NOT_EMPLOYMENT", "reason": "Gig platform.",
                               "quote": "This role is based in our Sydney office."},
                    employment={"kind": "non_employment", "quote": "This role is based in our Sydney office."})
    out = _validate(raw)
    assert (out.status, out.reject_code) == ("rejected", "NOT_EMPLOYMENT")


def test_non_employment_without_jd_quote_is_dropped():
    out = _validate(_judgment(employment={"kind": "non_employment", "quote": "Paid per task"}))
    assert out.judgment["employment"] == {"kind": "employment", "quote": None}
    assert "constraint_quote_not_found:employment" in out.validation["consistency_fixes"]


def test_people_management_gap_caps_at_c():
    people = {"required": True, "job_quote": "Applicants must be NZ citizens or permanent residents.",
              "candidate_has": False, "resume_quote": None}
    out = _validate(_judgment(people_management=people))
    assert out.tier == "C" and out.validation["llm_tier"] == "A"
    assert out.validation["tier_adjustments"] == ["people_management_required"]
    assert out.judgment["tier"] == "A"  # the stored judgment keeps the LLM's answer


def test_people_management_requirement_needs_a_jd_quote():
    people = {"required": True, "job_quote": "Manage a team of 6", "candidate_has": False, "resume_quote": None}
    out = _validate(_judgment(people_management=people))
    assert out.tier == "A" and "people_management_quote_not_found" in out.validation["consistency_fixes"]


def test_candidate_with_people_management_is_not_capped():
    people = {"required": True, "job_quote": "Applicants must be NZ citizens or permanent residents.",
              "candidate_has": True, "resume_quote": "Deployed to Azure App Service"}
    out = _validate(_judgment(people_management=people))
    assert out.tier == "A" and "tier_adjustments" not in out.validation


def test_adjacent_family_caps_a_at_b():
    out = _validate(_judgment(), relation="adjacent")
    assert out.tier == "B" and out.validation["tier_adjustments"] == ["adjacent_family"]
    assert _validate(_judgment(), relation="same").tier == "A"
    assert _validate(_judgment(tier="C"), relation="adjacent").tier == "C"


def test_capped_tier_rules_combine():
    assert capped_tier("A", people_management_gap=True, family_relation="adjacent") == (
        "C", ["people_management_required"])
    assert capped_tier("B", people_management_gap=False, family_relation="adjacent") == ("B", [])
    assert capped_tier("D", people_management_gap=True, family_relation="adjacent") == ("D", [])
