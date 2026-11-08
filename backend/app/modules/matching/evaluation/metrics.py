"""Evaluation metrics for matching v3 (docs/job_matching_v3_design.md §8.3). Pure functions.

Input rows are plain dicts, one per (item, repeat):
    user_id, job_id, repeat_index, item_kind, label, applied_resume_id,
    title, company, family, prefilter, location_check, status, tier,
    reject_code, resume_id, tier_reason, judged, validation, usage
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable, Sequence

PASSED_PREFILTER = {"same", "adjacent", "location_rejected"}
TIER_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}
OUTCOME_KEYS = ("A", "B", "C", "D", "REJECTED", "FILTERED", "FAILED")


def outcome(row: dict) -> str:
    """Single outcome label for distributions and confusion matrices."""
    if row.get("prefilter") == "filtered" and not row.get("judged"):
        return "FILTERED"
    if row.get("status") == "rejected":
        return "REJECTED"
    if row.get("status") in ("failed_final", "failed_retryable") or not row.get("tier"):
        return "FAILED"
    return row["tier"]


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def _distribution(rows: Iterable[dict]) -> dict[str, int]:
    counts = Counter(outcome(r) for r in rows)
    return {k: counts.get(k, 0) for k in OUTCOME_KEYS}


def compute_metrics(rows: Sequence[dict], *, family_stats: dict[str, Any] | None = None) -> dict[str, Any]:
    first = [r for r in rows if r.get("repeat_index", 0) == 0]
    by_kind: dict[str, list[dict]] = defaultdict(list)
    for r in first:
        by_kind[r["item_kind"]].append(r)

    interviewed = by_kind["interviewed"]
    applied = by_kind["applied"] + interviewed
    randoms = by_kind["random"] + by_kind["random_filtered"]

    def passed(r: dict) -> bool:
        return r.get("prefilter") in PASSED_PREFILTER

    prefilter = {
        "interviewed_total": len(interviewed),
        "interviewed_pass_rate": _ratio(sum(passed(r) for r in interviewed), len(interviewed)),
        "interviewed_judged_d": sum(1 for r in interviewed if r.get("tier") == "D"),
        "applied_total": len(applied),
        "applied_pass_rate": _ratio(sum(passed(r) for r in applied), len(applied)),
        "applied_location_rejected": sum(1 for r in applied if r.get("prefilter") == "location_rejected"),
        "applied_d_rate": _ratio(sum(1 for r in applied if r.get("tier") == "D"), len(applied)),
        "applied_missed": [
            {"job_id": r["job_id"], "title": r.get("title"), "family": r.get("family")}
            for r in applied if not passed(r)
        ],
        "random_total": len(randoms),
        "random_filter_rate": _ratio(sum(1 for r in randoms if not passed(r)), len(randoms)),
        "relation_counts": dict(Counter(r["prefilter"] for r in first if passed(r))),
        "location_unknown_rate": _ratio(
            sum(1 for r in first if r.get("location_check") == "unknown"),
            sum(1 for r in first if passed(r)),
        ),
    }

    filtered_judged = [r for r in by_kind["random_filtered"] if r.get("judged")]
    prefilter_misses = {
        "judged": len(filtered_judged),
        "ab_rate": _ratio(sum(1 for r in filtered_judged if r.get("tier") in ("A", "B")), len(filtered_judged)),
        "ab_items": [
            {"job_id": r["job_id"], "title": r.get("title"), "family": r.get("family"),
             "tier": r.get("tier"), "reason": r.get("tier_reason")}
            for r in filtered_judged if r.get("tier") in ("A", "B")
        ],
    }

    distribution = {
        "all": _distribution(first),
        "random": _distribution(by_kind["random"]),
        "applied": _distribution(applied),
    }

    return {
        "families": family_stats or {},
        "prefilter": prefilter,
        "prefilter_misses": prefilter_misses,
        "distribution": distribution,
        "stability": _stability(rows),
        "labels": _label_agreement(first),
        "best_resume": _best_resume(applied),
        "validation": _validation(first),
        "cost": _cost(rows),
    }


def _stability(rows: Sequence[dict]) -> dict[str, Any]:
    by_pair: dict[tuple, dict[int, str]] = defaultdict(dict)
    conflicts = 0
    for r in rows:
        if r.get("judged"):
            by_pair[(r["user_id"], r["job_id"])][r.get("repeat_index", 0)] = outcome(r)
            conflicts += sum(1 for f in (r.get("validation") or {}).get("flags", []) if f.startswith("tier_flag_conflict"))
    repeated = [v for v in by_pair.values() if len(v) > 1]
    agree = sum(1 for v in repeated if len(set(v.values())) == 1)
    return {
        "repeated_pairs": len(repeated),
        "agreement_rate": _ratio(agree, len(repeated)),
        "tier_flag_conflicts": conflicts,
    }


def _label_agreement(rows: Sequence[dict]) -> dict[str, Any]:
    labeled = [r for r in rows if r.get("label")]
    matrix: dict[str, Counter] = defaultdict(Counter)
    severe = []
    for r in labeled:
        gold = r["label"]
        pred = outcome(r)
        matrix[gold][pred] += 1
        g, p = TIER_ORDER.get(gold), TIER_ORDER.get(pred)
        if pred == "FILTERED" and gold in ("A", "B"):
            severe.append(r)
        elif g is not None and p is not None and abs(g - p) >= 2:
            severe.append(r)
        elif (gold == "REJECT") != (pred == "REJECTED") and {gold, pred} & {"A"}:
            severe.append(r)
    predicted_a = [r for r in labeled if outcome(r) == "A"]
    gold_ab = [r for r in labeled if r["label"] in ("A", "B")]
    return {
        "labeled": len(labeled),
        "confusion": {gold: dict(preds) for gold, preds in matrix.items()},
        "exact_rate": _ratio(sum(1 for r in labeled if r["label"] == outcome(r)
                                 or (r["label"] == "REJECT" and outcome(r) == "REJECTED")), len(labeled)),
        "a_precision": _ratio(sum(1 for r in predicted_a if r["label"] == "A"), len(predicted_a)),
        "ab_recall": _ratio(sum(1 for r in gold_ab if outcome(r) in ("A", "B")), len(gold_ab)),
        "severe_error_rate": _ratio(len(severe), len(labeled)),
        "severe_errors": [
            {"job_id": r["job_id"], "title": r.get("title"), "label": r["label"],
             "predicted": outcome(r), "reason": r.get("tier_reason")}
            for r in severe
        ],
    }


def _best_resume(applied: Sequence[dict]) -> dict[str, Any]:
    comparable = [r for r in applied if r.get("judged") and r.get("applied_resume_id") and r.get("resume_id")]
    return {
        "comparable": len(comparable),
        "agreement_rate": _ratio(
            sum(1 for r in comparable if r["resume_id"] == r["applied_resume_id"]), len(comparable)
        ),
    }


def _validation(rows: Sequence[dict]) -> dict[str, Any]:
    judged = [r for r in rows if r.get("judged") and r.get("validation")]
    fixes: Counter = Counter()
    flags: Counter = Counter()
    quotes = unverified = retries = 0
    for r in judged:
        v = r["validation"]
        fixes.update(v.get("consistency_fixes", []))
        flags.update(f.split(":")[0] for f in v.get("flags", []))
        quotes += v.get("quotes_total", 0)
        unverified += v.get("quotes_unverified", 0)
        retries += v.get("structure_retries", 0)
    return {
        "judged": len(judged),
        "consistency_fixes": dict(fixes),
        "flags": dict(flags),
        "unverified_quote_rate": _ratio(unverified, quotes),
        "structure_retries": retries,
        "failed": sum(1 for r in rows if outcome(r) == "FAILED"),
    }


def _cost(rows: Sequence[dict]) -> dict[str, Any]:
    """Spend of this run only: results reused from an earlier run are excluded, and the
    average is over successful calls (failed calls report no usage)."""
    calls = input_tokens = output_tokens = 0
    cost = 0.0
    for r in rows:
        if r.get("reused"):
            continue
        for usage in r.get("usage") or []:
            calls += 1
            input_tokens += usage.get("input_tokens") or 0
            output_tokens += usage.get("output_tokens") or 0
            cost += usage.get("estimated_cost") or 0.0
    return {
        "judge_calls": calls,
        "reused_results": sum(1 for r in rows if r.get("reused")),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": round(cost, 4),
        "avg_cost_per_judgment_usd": round(cost / calls, 5) if calls else None,
    }


def compare_runs(a: Sequence[dict], b: Sequence[dict]) -> dict[str, Any]:
    """Pairs whose outcome changed between two runs on the same dataset (repeat 0)."""
    def index(rows):
        return {(r["user_id"], r["job_id"]): r for r in rows if r.get("repeat_index", 0) == 0}

    ia, ib = index(a), index(b)
    changed = []
    for key in sorted(set(ia) & set(ib)):
        oa, ob = outcome(ia[key]), outcome(ib[key])
        if oa != ob:
            changed.append({"job_id": key[1], "title": ib[key].get("title"), "from": oa, "to": ob,
                            "label": ib[key].get("label"), "reason": ib[key].get("tier_reason")})
    transitions = Counter(f"{c['from']}->{c['to']}" for c in changed)
    return {"compared": len(set(ia) & set(ib)), "changed": len(changed),
            "transitions": dict(transitions), "items": changed}
