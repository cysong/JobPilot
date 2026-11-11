"""Validate a match_judge output before it is stored (docs/job_matching_v3_design.md §6.4).

Structural problems raise ``JudgmentStructureError`` so the caller can retry the
LLM call. Content problems (unverifiable quotes, rejections without grounds,
flag/tier conflicts) are fixed or flagged and reported in ``validation``; the
tier itself is always the LLM's.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from pydantic import ValidationError

from agent_configs.schemas import MatchJudgment
from app.modules.matching.judge.input_builder import CandidateConditions
from app.modules.matching.text import quote_in

# Tolerance when comparing the LLM's relevant_years with dated work history.
YEARS_TOLERANCE = 0.5


_TIER_ORDER = "ABCD"


def capped_tier(
    tier: str, *, people_management_gap: bool, family_relation: str | None
) -> tuple[str, list[str]]:
    """Code-level ceilings on the LLM tier (calibration 2026-11-11).

    - The job needs a people manager and the candidate never managed people: at most C.
    - The job is only in an adjacent role family of the candidate's resumes: at most B
      (14% of adjacent A's held up on review, against 35% for same-family A's).
    Returns the final tier and the rules that lowered it.
    """
    applied: list[str] = []

    def cap(current: str, ceiling: str, rule: str) -> str:
        if _TIER_ORDER.index(current) < _TIER_ORDER.index(ceiling):
            applied.append(rule)
            return ceiling
        return current

    if people_management_gap:
        tier = cap(tier, "C", "people_management_required")
    if family_relation == "adjacent":
        tier = cap(tier, "B", "adjacent_family")
    return tier, applied


class JudgmentStructureError(ValueError):
    """The output cannot be used as-is; the LLM call should be retried."""


@dataclass
class JudgeOutcome:
    status: str  # "rated" | "rejected"
    resume_id: str
    tier: str
    tier_reason: str
    tech_level: str
    experience_level: str
    reject_code: str | None
    reject_reason: str | None
    reject_quote: str | None
    judgment: dict[str, Any]
    validation: dict[str, Any] = field(default_factory=dict)


def validate_judgment(
    raw: MatchJudgment | Mapping[str, Any],
    *,
    candidate_ids: Sequence[str],
    job_text: str,
    resume_texts: Mapping[str, str],
    skill_texts: Sequence[str],
    conditions: CandidateConditions,
    history_years: Mapping[str, float],
    family_relation: str | None = None,
) -> JudgeOutcome:
    try:
        judgment = raw if isinstance(raw, MatchJudgment) else MatchJudgment.model_validate(raw)
    except ValidationError as exc:
        raise JudgmentStructureError(f"schema validation failed: {exc.errors()[:3]}") from exc

    if judgment.best_resume_id not in candidate_ids:
        raise JudgmentStructureError(f"best_resume_id {judgment.best_resume_id!r} is not a candidate")
    if (judgment.decision == "rejected") != (judgment.rejection is not None):
        raise JudgmentStructureError("decision and rejection are inconsistent")

    data = judgment.model_dump()
    fixes: list[str] = []
    flags: list[str] = []

    # Constraint quotes must exist in the JD, otherwise the requirement is dropped.
    for key in ("work_rights", "security_clearance"):
        check = data[key]
        if check["requirement"] != "none" and not quote_in(check["quote"], job_text):
            fixes.append(f"constraint_quote_not_found:{key}")
            data[key] = {"requirement": "none", "quote": None, "satisfied": None}
    location = data["work_location"]
    if location["requirement"] != "none" and not quote_in(location["quote"], job_text):
        fixes.append("constraint_quote_not_found:work_location")
        data["work_location"] = {"requirement": "none", "country": None, "quote": None, "satisfied": None}
    languages = data["languages"]
    if languages["required_languages"] and not quote_in(languages["quote"], job_text):
        fixes.append("constraint_quote_not_found:languages")
        data["languages"] = {"required_languages": [], "quote": None, "satisfied": None}
    employment = data["employment"]
    if employment["kind"] != "employment" and not quote_in(employment["quote"], job_text):
        fixes.append("constraint_quote_not_found:employment")
        data["employment"] = {"kind": "employment", "quote": None}
    data["other_constraints"] = [c for c in data["other_constraints"] if quote_in(c["quote"], job_text)]
    people = data["people_management"]
    if people["required"] and not quote_in(people["job_quote"], job_text):
        fixes.append("people_management_quote_not_found")
        people["required"], people["job_quote"] = False, None

    # A rejection needs a real JD sentence and a known candidate status.
    if data["decision"] == "rejected":
        rejection = data["rejection"]
        status_by_code = {
            "WORK_RIGHTS": conditions.work_rights,
            "SECURITY_CLEARANCE": conditions.security_clearance,
            "WORK_LOCATION": conditions.country,
            "LANGUAGE": ", ".join(conditions.languages) or None,
            "NOT_EMPLOYMENT": "n/a",  # about the job, not the candidate
        }
        if not quote_in(rejection["quote"], job_text):
            fixes.append("rejection_quote_not_found")
            data["decision"], data["rejection"] = "rated", None
        elif not status_by_code.get(rejection["code"]):
            fixes.append("rejection_on_unknown_status")
            data["decision"], data["rejection"] = "rated", None

    best_text = resume_texts.get(judgment.best_resume_id, "")
    unverified = 0
    total_quotes = 0
    evidence_items = [item["evidence"] for item in data["tech_items"]] + data["experience_evidence"]
    evidence_items.append(people)  # its job_quote was verified above; this checks resume_quote
    for evidence in evidence_items:
        if evidence.get("job_quote"):
            total_quotes += 1
            if not quote_in(evidence["job_quote"], job_text):
                unverified += 1
                evidence["job_quote_unverified"] = True
        if evidence.get("resume_quote"):
            total_quotes += 1
            if not quote_in(evidence["resume_quote"], best_text, *skill_texts):
                unverified += 1
                evidence["resume_quote_unverified"] = True

    limit = history_years.get(judgment.best_resume_id)
    if (
        judgment.relevant_years is not None
        and limit is not None
        and judgment.relevant_years > limit + YEARS_TOLERANCE
    ):
        flags.append("years_exceeds_history")

    if judgment.is_different_track and judgment.tier != "D":
        flags.append("tier_flag_conflict:different_track")
    if judgment.seniority_mismatch and judgment.tier != "C":
        flags.append("tier_flag_conflict:seniority_mismatch")

    tier, adjustments = capped_tier(
        judgment.tier,
        people_management_gap=people["required"] and not people["candidate_has"],
        family_relation=family_relation,
    )

    rejection = data["rejection"]
    return JudgeOutcome(
        status="rejected" if data["decision"] == "rejected" else "rated",
        resume_id=judgment.best_resume_id,
        tier=tier,
        tier_reason=judgment.tier_reason,
        tech_level=judgment.tech_level,
        experience_level=judgment.experience_level,
        reject_code=rejection["code"] if rejection else None,
        reject_reason=rejection["reason"] if rejection else None,
        reject_quote=rejection["quote"] if rejection else None,
        judgment=data,
        validation={
            "consistency_fixes": fixes,
            "flags": flags,
            "quotes_total": total_quotes,
            "quotes_unverified": unverified,
            **({"llm_tier": judgment.tier, "tier_adjustments": adjustments} if adjustments else {}),
        },
    )
