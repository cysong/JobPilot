"""Duplicate listings on a real Postgres: grouping at discover, copied results, one list entry."""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select, update

from tests.modules.matching.conftest import LOCAL_DB, requires_db

pytestmark = requires_db

if LOCAL_DB:
    from app.modules.auth.models import User
    from app.modules.jobs.models import SeekJob
    from app.modules.matching import service
    from app.modules.matching.families.classifier import classify_missing_titles, resolve_pending_jobs
    from app.modules.matching.families.models import JobRoleFamily
    from app.modules.matching.models import JobMatch
    from app.modules.matching.pipeline import discover_new_jobs, enqueue_matches, judge_queued_matches
    from tests.modules.matching.test_pipeline import NOW, _gateway, _seed

LONG_JD = "<p>" + " ".join(f"Java Spring requirement number {i} for the backend platform." for i in range(40)) + "</p>"


async def _seed_with_repost(db):
    await _seed(db, qa_family="qa_test")
    # Job 1 reposted on another platform (job 8) a day later, same description.
    await db.execute(update(SeekJob).where(SeekJob.id == 1).values(content=LONG_JD, advertiser_name="Kāinga Ora"))
    db.add(SeekJob(id=8, source="linkedin", source_id="s8", title="Senior Java Developer",
                   listed_at=NOW - timedelta(hours=12), content=LONG_JD + "<p>Apply on LinkedIn.</p>",
                   advertiser_name="Kainga Ora - Homes and Communities",
                   location_city="Christchurch", location_label="Christchurch, Canterbury"))
    await db.commit()


@pytest.mark.asyncio
async def test_repost_is_grouped_judged_once_and_listed_once(session_factory):
    calls: list = []
    gateway = _gateway(calls)
    async with session_factory() as db:
        await _seed_with_repost(db)
        assert await discover_new_jobs(db) == 6
        await classify_missing_titles(db, gateway)
        await resolve_pending_jobs(db, gateway)
        families = {r.job_id: r.duplicate_of for r in (await db.execute(select(JobRoleFamily))).scalars()}
        assert families[8] == 1 and families[1] is None and families[2] is None
        await enqueue_matches(db)

    stats = await judge_queued_matches(session_factory, gateway)
    async with session_factory() as db:
        rows = {m.job_id: m for m in (await db.execute(select(JobMatch))).scalars()}
    judged_titles = [c for c in calls if c == "match_judge"]
    # Jobs 1, 2, 3(location), 5, 8: the repost copies job 1's result when judged after it.
    if stats.get("copied"):
        copy, source = (rows[8], rows[1]) if rows[8].duplicate_of else (rows[1], rows[8])
        assert copy.duplicate_of == source.id and copy.ai_call_id is None
        assert copy.tier == source.tier and copy.validation["copied_from"] == source.id
        assert len(judged_titles) == 3
    else:  # both judged in the same chunk: still one list entry
        assert len(judged_titles) == 4

    async with session_factory() as db:
        user = await db.get(User, 1)
        listed = await service.list_matches(db, user)
        ids = [i.job.id for i in listed.items]
        assert len({1, 8} & set(ids)) == 1
        entry = next(i for i in listed.items if i.job.id in (1, 8))
        assert entry.match.other_listing_count == 1
        assert listed.counts.A + listed.counts.B == len(listed.items)  # job 5 is adjacent: capped at B
        detail = await service.get_match_detail(db, user, entry.job.id)
        assert [o.job_id for o in detail.other_listings] == [8 if entry.job.id == 1 else 1]


@pytest.mark.asyncio
async def test_copied_results_do_not_use_the_daily_limit(session_factory, monkeypatch):
    from app.core.config import settings

    calls: list = []
    gateway = _gateway(calls)
    monkeypatch.setattr(settings, "MATCH_JUDGE_CONCURRENCY", 1)  # judge one at a time: the repost copies
    async with session_factory() as db:
        await _seed_with_repost(db)
        await discover_new_jobs(db)
        await classify_missing_titles(db, gateway)
        await resolve_pending_jobs(db, gateway)
        await enqueue_matches(db)
    stats = await judge_queued_matches(session_factory, gateway)
    assert stats["copied"] == 1 and calls.count("match_judge") == 3
    async with session_factory() as db:
        copy = (await db.execute(select(JobMatch).where(JobMatch.duplicate_of.is_not(None)))).scalar_one()
        assert copy.judged_at is not None
