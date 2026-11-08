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
    data["other_constraints"] = [c for c in data["other_constraints"] if quote_in(c["quote"], job_text)]

    # A rejection needs a real JD sentence and a known candidate status.
    if data["decision"] == "rejected":
        rejection = data["rejection"]
        status_by_code = {
            "WORK_RIGHTS": conditions.work_rights,
            "SECURITY_CLEARANCE": conditions.security_clearance,
            "WORK_LOCATION": conditions.country,
            "LANGUAGE": ", ".join(conditions.languages) or None,
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

    rejection = data["rejection"]
    return JudgeOutcome(
        status="rejected" if data["decision"] == "rejected" else "rated",
        resume_id=judgment.best_resume_id,
        tier=judgment.tier,
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
        },
    )
