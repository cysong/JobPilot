"""Render the unified evaluation report (docs/job_matching_v3_design.md §8.3). Pure functions.

Sections are fixed; missing data is written as "N/A" so reports stay comparable.
"""
from __future__ import annotations

from typing import Any

NA = "N/A"


def _fmt(value: Any) -> str:
    if value is None:
        return NA
    if isinstance(value, float):
        return f"{value:.1%}" if 0 <= value <= 1 else f"{value:.2f}"
    return str(value)


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return NA
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(_fmt(c) if not isinstance(c, str) else c for c in row) + " |" for row in rows]
    return "\n".join(out)


def render_report(*, run: dict[str, Any], metrics: dict[str, Any], comparison: dict[str, Any] | None = None) -> str:
    m = metrics
    pre, miss, dist = m["prefilter"], m["prefilter_misses"], m["distribution"]
    lines: list[str] = [f"# Matching evaluation report — {run.get('id', NA)}", ""]

    lines += ["## 1. Run", _table(["Item", "Value"], [[k, str(v)] for k, v in run.items() if k != "id"]), ""]

    fam = m.get("families") or {}
    lines += ["## 2. Role family classification"]
    if fam:
        lines += [
            f"- Jobs classified: {fam.get('classified', NA)} / {fam.get('jobs', NA)}"
            f" (failed {fam.get('failed', NA)}, pending {fam.get('pending', NA)})",
            f"- Read from JD (ambiguous titles): {_fmt(fam.get('jd_read_rate'))}",
            "",
            _table(["Family", "Jobs"], [[k, v] for k, v in sorted((fam.get("by_family") or {}).items(),
                                                              key=lambda kv: -kv[1])]),
        ]
    else:
        lines.append(NA)
    lines.append("")

    lines += [
        "## 3. Prefilter",
        _table(["Metric", "Value", "Target"], [
            ["Interviewed jobs passing prefilter", _fmt(pre["interviewed_pass_rate"]) + f" of {pre['interviewed_total']}", "100%"],
            ["Interviewed jobs judged D", _fmt(pre["interviewed_judged_d"]), "0"],
            ["Applied jobs passing prefilter", _fmt(pre["applied_pass_rate"]) + f" of {pre['applied_total']}", ">= 98%"],
            ["Applied jobs rejected by location", _fmt(pre["applied_location_rejected"]), "0"],
            ["Applied jobs judged D", _fmt(pre["applied_d_rate"]), "low"],
            ["Random jobs filtered out", _fmt(pre["random_filter_rate"]) + f" of {pre['random_total']}", "-"],
            ["Location unknown (of passed)", _fmt(pre["location_unknown_rate"]), "-"],
            ["Passed by relation", str(pre["relation_counts"] or NA), "-"],
        ]),
        "",
        "Applied jobs missed by the prefilter:",
        _table(["Job", "Title", "Family"], [[str(x["job_id"]), x["title"] or "", x["family"] or ""]
                                             for x in pre["applied_missed"]]),
        "",
    ]

    lines += [
        "## 4. Prefilter misses (filtered random jobs, judged anyway)",
        f"- Judged: {miss['judged']}; judged A/B: {_fmt(miss['ab_rate'])}",
        _table(["Job", "Title", "Family", "Tier", "Reason"],
               [[str(x["job_id"]), x["title"] or "", x["family"] or "", x["tier"] or "", x["reason"] or ""]
                for x in miss["ab_items"]]),
        "",
    ]

    keys = list(dist["all"].keys())
    lines += [
        "## 5. Outcome distribution",
        _table(["Subset", *keys], [[name, *[d[k] for k in keys]] for name, d in dist.items()]),
        "",
    ]

    stab = m["stability"]
    lines += [
        "## 6. Stability",
        f"- Repeated pairs: {stab['repeated_pairs']}; same outcome on every repeat: {_fmt(stab['agreement_rate'])}",
        f"- Tier/flag conflicts: {stab['tier_flag_conflicts']}",
        "",
    ]

    lab = m["labels"]
    confusion_rows = []
    cols = ["A", "B", "C", "D", "REJECTED", "FILTERED", "FAILED"]
    for gold in ("A", "B", "C", "D", "REJECT"):
        if gold in lab["confusion"]:
            confusion_rows.append([gold, *[lab["confusion"][gold].get(c, 0) for c in cols]])
    lines += [
        "## 7. Agreement with admin labels",
        f"- Labeled pairs: {lab['labeled']}; exact: {_fmt(lab['exact_rate'])};"
        f" A precision: {_fmt(lab['a_precision'])}; A+B recall: {_fmt(lab['ab_recall'])};"
        f" severe errors: {_fmt(lab['severe_error_rate'])}",
        "",
        _table(["Label \\ Predicted", *cols], confusion_rows),
        "",
    ]

    best = m["best_resume"]
    lines += [
        "## 8. Best resume vs resume actually used",
        f"- Comparable: {best['comparable']}; same resume: {_fmt(best['agreement_rate'])}",
        "",
    ]

    val = m["validation"]
    lines += [
        "## 9. Output validation",
        f"- Judged: {val['judged']}; failed: {val['failed']}; structure retries: {val['structure_retries']}",
        f"- Unverified quotes: {_fmt(val['unverified_quote_rate'])}",
        f"- Consistency fixes: {val['consistency_fixes'] or NA}",
        f"- Flags: {val['flags'] or NA}",
        "",
    ]

    lines.append("## 10. Comparison with baseline")
    if comparison:
        lines += [
            f"- Compared pairs: {comparison['compared']}; changed outcome: {comparison['changed']}",
            f"- Transitions: {comparison['transitions'] or NA}",
            _table(["Job", "Title", "From", "To", "Label"],
                   [[str(c["job_id"]), c["title"] or "", c["from"], c["to"], c["label"] or ""]
                    for c in comparison["items"][:50]]),
        ]
    else:
        lines.append(NA)
    lines.append("")

    lines += [
        "## 11. Severe errors",
        _table(["Job", "Title", "Label", "Predicted", "Reason"],
               [[str(e["job_id"]), e["title"] or "", e["label"], e["predicted"], e["reason"] or ""]
                for e in lab["severe_errors"]]),
        "",
    ]

    cost = m["cost"]
    lines += [
        "## 12. Cost",
        f"- Judge calls: {cost['judge_calls']} (plus {cost.get('reused_results', 0)} results reused from an earlier run);"
        f" input tokens: {cost['input_tokens']};"
        f" output tokens: {cost['output_tokens']}",
        f"- Estimated cost: ${cost['estimated_cost_usd']}; per judgment:"
        f" {('$' + str(cost['avg_cost_per_judgment_usd'])) if cost['avg_cost_per_judgment_usd'] is not None else NA}",
        "",
    ]
    return "\n".join(lines)
