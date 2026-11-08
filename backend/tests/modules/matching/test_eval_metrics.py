"""Tests for evaluation metrics, run comparison and the unified report."""
from __future__ import annotations

import pytest

from app.modules.matching.evaluation.metrics import compare_runs, compute_metrics, outcome
from app.modules.matching.evaluation.report import render_report


def _row(job_id, kind, *, prefilter="same", tier=None, status=None, label=None, judged=None,
         repeat=0, resume_id="r1", applied_resume_id=None, validation=None, usage=None, location="matched"):
    judged = judged if judged is not None else prefilter in ("same", "adjacent") or kind == "random_filtered"
    status = status or ("rated" if judged and tier else None)
    return {
        "user_id": 1, "job_id": job_id, "repeat_index": repeat, "item_kind": kind, "label": label,
        "applied_resume_id": applied_resume_id, "title": f"Job {job_id}", "company": "Acme",
        "family": "software_dev", "prefilter": prefilter, "location_check": location,
        "status": status, "tier": tier, "reject_code": None, "resume_id": resume_id if judged else None,
        "tier_reason": f"reason {job_id}", "judged": judged,
        "validation": validation or ({"consistency_fixes": [], "flags": [], "quotes_total": 2,
                                      "quotes_unverified": 0, "structure_retries": 0} if judged else None),
        "usage": usage if usage is not None else ([{"input_tokens": 1000, "output_tokens": 500,
                                                    "estimated_cost": 0.0035}] if judged else []),
    }


ROWS = [
    _row(1, "interviewed", tier="A", applied_resume_id="r1"),
    _row(2, "interviewed", prefilter="adjacent", tier="B", applied_resume_id="r2"),
    _row(3, "applied", tier="B", applied_resume_id="r1", label="B"),
    _row(4, "applied", prefilter="filtered", judged=False),
    _row(5, "applied", prefilter="location_rejected", judged=False, status="rejected"),
    _row(6, "random", prefilter="filtered", judged=False),
    _row(7, "random", tier="C", label="C"),
    _row(8, "random", tier="A", label="C"),  # off by two -> severe
    _row(9, "random_filtered", prefilter="filtered", tier="B"),
    _row(10, "random_filtered", prefilter="filtered", tier="D"),
    _row(11, "random", tier="D", label="A"),  # severe
    _row(7, "random", tier="B", repeat=1),  # repeat disagrees
    _row(1, "interviewed", tier="A", repeat=1, applied_resume_id="r1"),
]


def test_outcome_mapping():
    assert outcome(_row(1, "random", prefilter="filtered", judged=False)) == "FILTERED"
    assert outcome(_row(1, "random_filtered", prefilter="filtered", tier="B")) == "B"  # judged sample
    assert outcome({"status": "rejected", "tier": "A", "prefilter": "same", "judged": True}) == "REJECTED"
    assert outcome({"status": "failed_final", "prefilter": "same", "judged": True}) == "FAILED"


def test_prefilter_metrics():
    pre = compute_metrics(ROWS)["prefilter"]
    assert pre["interviewed_total"] == 2
    assert pre["interviewed_pass_rate"] == 1.0
    assert pre["applied_total"] == 5
    assert pre["applied_pass_rate"] == 0.8  # job 4 missed; location_rejected still passed families
    assert pre["applied_location_rejected"] == 1
    assert pre["applied_missed"] == [{"job_id": 4, "title": "Job 4", "family": "software_dev"}]
    assert pre["random_total"] == 6
    assert pre["random_filter_rate"] == 0.5  # 6, 9, 10 filtered
    assert pre["relation_counts"] == {"same": 5, "adjacent": 1, "location_rejected": 1}


def test_prefilter_miss_sample():
    miss = compute_metrics(ROWS)["prefilter_misses"]
    assert miss["judged"] == 2
    assert miss["ab_rate"] == 0.5
    assert [x["job_id"] for x in miss["ab_items"]] == [9]


def test_distribution_uses_first_repeat_only():
    dist = compute_metrics(ROWS)["distribution"]
    assert dist["all"]["A"] == 2  # jobs 1 and 8; repeat rows ignored
    assert dist["all"]["FILTERED"] == 2
    assert dist["all"]["REJECTED"] == 1
    assert sum(dist["random"].values()) == 4


def test_stability():
    stab = compute_metrics(ROWS)["stability"]
    assert stab["repeated_pairs"] == 2
    assert stab["agreement_rate"] == 0.5


def test_label_agreement():
    lab = compute_metrics(ROWS)["labels"]
    assert lab["labeled"] == 4
    assert lab["confusion"]["C"] == {"C": 1, "A": 1}
    assert lab["a_precision"] == 0.0  # job 8 predicted A, labeled C
    assert lab["ab_recall"] == 0.5  # job 3 (B->B) yes, job 11 (A->D) no
    assert {e["job_id"] for e in lab["severe_errors"]} == {8, 11}
    assert lab["severe_error_rate"] == 0.5


def test_best_resume_agreement():
    best = compute_metrics(ROWS)["best_resume"]
    assert best["comparable"] == 3
    assert best["agreement_rate"] == pytest.approx(2 / 3, abs=1e-3)


def test_cost_counts_all_repeats():
    cost = compute_metrics(ROWS)["cost"]
    judged = sum(1 for r in ROWS if r["judged"])
    assert cost["judge_calls"] == judged
    assert cost["estimated_cost_usd"] == pytest.approx(0.0035 * judged, abs=1e-4)
    assert cost["avg_cost_per_judgment_usd"] == pytest.approx(0.0035)


def test_cost_excludes_reused_and_failed():
    rows = [
        _row(1, "applied", tier="A"),
        {**_row(2, "applied", tier="B"), "reused": True},
        {**_row(3, "applied", judged=True, status="failed_final"), "usage": []},
    ]
    cost = compute_metrics(rows)["cost"]
    assert cost["judge_calls"] == 1
    assert cost["reused_results"] == 1
    assert cost["avg_cost_per_judgment_usd"] == pytest.approx(0.0035)


def test_compare_runs():
    after = [dict(r) for r in ROWS]
    after[7] = {**after[7], "tier": "C"}  # job 8: A -> C
    diff = compare_runs(ROWS, after)
    assert diff["changed"] == 1
    assert diff["transitions"] == {"A->C": 1}
    assert diff["items"][0]["job_id"] == 8


def test_report_has_all_sections_and_na_for_missing():
    metrics = compute_metrics(ROWS, family_stats={})
    md = render_report(run={"id": "mer_1", "dataset": "main@v1", "model": "openai/gpt-6.1-terra"}, metrics=metrics)
    for n in range(1, 13):
        assert f"## {n}." in md
    assert "N/A" in md  # family stats and comparison missing
    assert "| openai/gpt-6.1-terra" not in md or "model" in md
    md2 = render_report(run={"id": "mer_2"}, metrics=metrics, comparison=compare_runs(ROWS, ROWS))
    assert "changed outcome: 0" in md2


def test_metrics_on_empty_input():
    metrics = compute_metrics([])
    assert metrics["prefilter"]["applied_pass_rate"] is None
    assert metrics["labels"]["labeled"] == 0
    render_report(run={"id": "empty"}, metrics=metrics)
