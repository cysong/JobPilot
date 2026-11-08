"""End-to-end test of the stage 1 evaluation pipeline on a real Postgres (LLM mocked).

dataset create -> run (with repeat) -> report -> labels export/import -> dataset v2 -> run with baseline.
"""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from tests.modules.matching.conftest import LOCAL_DB, requires_db

pytestmark = requires_db

if LOCAL_DB:
    from app.core.llm.types import ModelOverride
    from app.modules.applications.models import Application
    from app.modules.auth.models import User
    from app.modules.jobs.models import SeekJob
    from app.modules.matching.evaluation.dataset import DatasetSpec, create_dataset
    from app.modules.matching.evaluation.models import MatchEvalItem, MatchEvalPrediction
    from app.modules.matching.evaluation.runner import run_evaluation
    from app.modules.matching.labels.csv_io import export_for_labeling, import_labels
    from app.modules.matching.labels.models import MatchLabel
    from app.modules.resumes.models import Document, Resume
    from app.shared.enums import ApplicationStatus

NOW = datetime.now(timezone.utc)

# title -> (role family, tier the mocked judge returns)
JOBS = {
    1: ("Senior Java Developer", "software_dev", "A", "Christchurch", "Christchurch, Canterbury"),
    2: ("QA Engineer", "qa_test", "B", "Christchurch", "Christchurch, Canterbury"),
    3: ("Backend Engineer", "software_dev", "B", "Auckland", "Auckland CBD, Auckland"),  # location reject
    4: ("Registered Nurse", "other", "D", "Christchurch", "Christchurch, Canterbury"),  # applied, filtered
    5: ("DevOps Engineer", "devops_platform", "C", None, "New Zealand"),
    6: ("Data Engineer", "data_engineering", "C", "Christchurch", "Christchurch, Canterbury"),
    7: ("Business Analyst", "business_analysis", "D", "Christchurch", "Christchurch, Canterbury"),
    8: ("Electrical Engineer", "other_engineering", "D", "Christchurch", "Christchurch, Canterbury"),
    9: ("Full Stack Developer", "software_dev", "B", "Christchurch", "Christchurch, Canterbury"),
}
TITLE_FAMILY = {"java developer": "software_dev", "qa engineer": "qa_test", "backend engineer": "software_dev",
                "registered nurse": "other", "devops engineer": "devops_platform",
                "data engineer": "data_engineering", "business analyst": "business_analysis",
                "electrical engineer": "other_engineering", "full stack developer": "software_dev"}


async def _seed(db):
    db.add(User(id=1, email="u@example.com", hashed_password="x", full_name="U",
                preferences={"job_locations": ["Christchurch"], "work_rights": "work_visa"}))
    for job_id, (title, _, _, city, label) in JOBS.items():
        # Job 4 (applied) is the oldest so the application period covers the random jobs 5-8.
        days = 20 if job_id == 4 else job_id
        db.add(SeekJob(id=job_id, source_id=f"s{job_id}", title=title, listed_at=NOW - timedelta(days=days),
                       content=f"<p>{title} role.</p><ul><li>Must know the stack</li></ul>",
                       location_city=city, location_label=label, advertiser_name="Acme"))
    await db.flush()
    for rid, fam, title in (("res_java", "software_dev", "Java Developer"), ("res_qa", "qa_test", "SDET")):
        db.add(Document(id=f"doc_{rid}", root_id=f"doc_{rid}", content=f"## Experience\n- {title} work",
                        content_hash=f"h_{rid}", created_by=1))
        await db.flush()
        db.add(Resume(id=rid, user_id=1, document_id=f"doc_{rid}", title=title, is_draft=False,
                      is_deleted=False, role_family=fam,
                      analysis_result={"work_experiences": [{"duration": ["2016-01", "2022-01"]}]}))
    await db.flush()
    apps = [(1, ApplicationStatus.INTERVIEWING, "res_java"), (2, ApplicationStatus.APPLIED, "res_qa"),
            (3, ApplicationStatus.READY, "res_java"), (4, ApplicationStatus.APPLIED, "res_java"),
            (9, ApplicationStatus.FAILED, "res_java")]  # FAILED is excluded
    for job_id, status, rid in apps:
        db.add(Application(id=f"app{job_id}", user_id=1, job_id=job_id, source_resume_id=rid, status=status))
    await db.commit()


def _gateway(calls: list):
    async def call(agent_id, input_data, context=None, model_override=None):
        calls.append((agent_id, model_override))
        if agent_id == "title_classifier":
            titles = json.loads(input_data)["titles"]
            return {"items": [{"title_key": t["title_key"], "role_family": TITLE_FAMILY.get(t["title_key"]),
                               "ambiguous": t["title_key"] not in TITLE_FAMILY} for t in titles]}
        if agent_id == "job_family_reader":
            return {"role_family": "other", "reason": "n/a"}
        assert agent_id == "match_judge"
        resume_id = re.search(r"=== resume_id: (\S+)", input_data).group(1)
        title = re.search(r"\[JOB\]\ntitle: (.+)", input_data).group(1)
        tier = next(t for (jt, _, t, _, _) in JOBS.values() if jt == title)
        if context is not None:
            context["usage"] = {"input_tokens": 4000, "output_tokens": 1500, "estimated_cost": 0.0115}
        return {
            "decision": "rated", "rejection": None,
            "work_rights": {"requirement": "none", "quote": None, "satisfied": None},
            "security_clearance": {"requirement": "none", "quote": None, "satisfied": None},
            "best_resume_id": resume_id, "is_different_track": tier == "D", "seniority_mismatch": False,
            "tech_level": "strong" if tier == "A" else "partial",
            "tech_items": [{"requirement": "Must know the stack", "is_core": True, "relation": "same",
                            "evidence": {"job_quote": "Must know the stack", "resume_quote": None}}],
            "experience_level": "strong", "relevant_years": 5.0, "required_years": None,
            "experience_evidence": [], "tier": tier, "tier_reason": f"{title}: tier {tier}",
        }
    gateway = AsyncMock()
    gateway.call = AsyncMock(side_effect=call)
    return gateway


@pytest.mark.asyncio
async def test_full_stage1_pipeline(session_factory, tmp_path):
    calls: list = []
    gateway = _gateway(calls)
    async with session_factory() as db:
        await _seed(db)
        dataset = await create_dataset(db, gateway, DatasetSpec(name="main", user_id=1, random_n=5,
                                                                 filtered_sample=2, seed="t"))
        assert dataset.version == 1
        counts = dataset.config["counts"]
        assert counts["interviewed"] == 1
        assert counts["applied"] == 3  # 2, 3 (READY counts), 4; 9 is FAILED
        assert counts["random"] + counts["random_filtered"] == 4  # jobs 5-8 (9 excluded as applied)
        assert counts["random_filtered"] == 2  # sampled among filtered random jobs
        assert set(dataset.config["resumes"]) == {"res_java", "res_qa"}
        assert dataset.config["unclassified_jobs"] == []

    terra = ModelOverride(provider="openrouter", model="openai/gpt-6.1-terra")
    run1 = await run_evaluation(session_factory, gateway, dataset_ref="main@v1", model_override=terra,
                                repeats=2, concurrency=2)
    assert run1.status == "succeeded"
    assert all(o == terra for agent, o in calls if agent == "match_judge")

    pre = run1.metrics["prefilter"]
    assert pre["interviewed_pass_rate"] == 1.0
    assert pre["applied_location_rejected"] == 1  # job 3 in Auckland
    assert [m["job_id"] for m in pre["applied_missed"]] == [4]  # nurse: family "other"
    assert run1.metrics["stability"]["agreement_rate"] == 1.0  # mock is deterministic
    assert run1.metrics["best_resume"]["comparable"] >= 1
    assert run1.metrics["cost"]["estimated_cost_usd"] > 0
    for n in range(1, 13):
        assert f"## {n}." in run1.report_md

    async with session_factory() as db:
        preds = (await db.execute(select(MatchEvalPrediction).where(MatchEvalPrediction.run_id == run1.id))).scalars().all()
        by_job = {(p.job_id, p.repeat_index): p for p in preds}
        assert by_job[(1, 0)].tier == "A" and by_job[(1, 0)].resume_id == "res_java"
        assert by_job[(3, 0)].status == "rejected" and by_job[(3, 0)].reject_code == "LOCATION"
        assert by_job[(3, 0)].tier is None  # no LLM call for location rejections
        assert (3, 1) not in by_job  # deterministic outcomes are not repeated
        assert (1, 1) in by_job

        # Export a labeling sheet, fill it in, import it.
        sheet = tmp_path / "labels.csv"
        exported = await export_for_labeling(db, run1.id, sheet, limit=10)
        assert exported > 0
        lines = sheet.read_text().splitlines()
        assert lines[0].startswith("# label:")
        rows = list(csv.DictReader(lines[1:]))
        for row in rows:
            row["label"] = "C" if row["job_id"] == "1" else row["predicted"].replace("REJECTED", "REJECT")
            row["reason_tags"] = "TECH|EXPERIENCE" if row["job_id"] == "1" else ""
        rows[0]["label"] = ""  # left blank on purpose
        with sheet.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        result = await import_labels(db, sheet, labeled_by=1, run_id=run1.id)
        assert result.errors == []
        assert result.skipped_blank == 1
        assert result.imported == len(rows) - 1

        # Re-importing supersedes instead of overwriting.
        await import_labels(db, sheet, labeled_by=1, run_id=run1.id)
        labels = (await db.execute(select(MatchLabel))).scalars().all()
        assert len(labels) == 2 * result.imported
        assert sum(1 for label in labels if label.superseded_by is None) == result.imported
        assert all(label.predicted_model == "openai/gpt-6.1-terra" for label in labels)

        dataset2 = await create_dataset(db, gateway, DatasetSpec(name="main", user_id=1, random_n=5,
                                                                  filtered_sample=2, seed="t"))
        assert dataset2.version == 2
        labeled_items = (await db.execute(select(MatchEvalItem).where(
            MatchEvalItem.dataset_id == dataset2.id, MatchEvalItem.label.is_not(None)))).scalars().all()
        assert len(labeled_items) == result.imported

    run2 = await run_evaluation(session_factory, gateway, dataset_ref="main@v2", model_override=terra,
                                baseline_run_id=run1.id)
    assert run2.metrics["labels"]["labeled"] == result.imported
    section = run2.report_md.split("## 10.")[1].split("## 11.")[0]
    assert "Compared pairs:" in section  # baseline comparison rendered
    # Job 1 was labeled C while judged A: off by two tiers -> severe error.
    assert 1 in {e["job_id"] for e in run2.metrics["labels"]["severe_errors"]}


@pytest.mark.asyncio
async def test_judged_limit_and_repeat_sample(session_factory):
    calls: list = []
    gateway = _gateway(calls)
    async with session_factory() as db:
        await _seed(db)
        await create_dataset(db, gateway, DatasetSpec(name="main", user_id=1, random_n=5,
                                                      filtered_sample=2, seed="t"))
    full = await run_evaluation(session_factory, gateway, dataset_ref="main@v1")
    llm_pairs = full.config["llm_pairs"]
    assert llm_pairs >= 4

    calls.clear()
    run = await run_evaluation(session_factory, gateway, dataset_ref="main@v1", judged_limit=3,
                               repeats=2, repeat_sample=2, sample_seed="s")
    judge_calls = [c for c in calls if c[0] == "match_judge"]
    assert len(judge_calls) == 3 + 2
    assert run.config["llm_pairs"] == 3 and run.config["repeat_sample"] == 2
    async with session_factory() as db:
        preds = (await db.execute(select(MatchEvalPrediction).where(MatchEvalPrediction.run_id == run.id))).scalars().all()
    judged_jobs = {p.job_id for p in preds if p.repeat_index == 0 and p.tier}
    repeated_jobs = {p.job_id for p in preds if p.repeat_index == 1}
    assert len(judged_jobs) == 3
    assert repeated_jobs <= judged_jobs and len(repeated_jobs) == 2
    # Pairs that never reach the LLM (location rejection, filtered) are still evaluated.
    assert any(p.reject_code == "LOCATION" for p in preds)

    # Same seed, larger limit: the smaller sample is a subset.
    calls.clear()
    bigger = await run_evaluation(session_factory, gateway, dataset_ref="main@v1", judged_limit=4, sample_seed="s")
    async with session_factory() as db:
        big_jobs = {p.job_id for p in (await db.execute(
            select(MatchEvalPrediction).where(MatchEvalPrediction.run_id == bigger.id))).scalars() if p.tier}
    assert judged_jobs <= big_jobs
