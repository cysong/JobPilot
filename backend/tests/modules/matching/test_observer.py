"""Matching gauges read from job_matches (real Postgres)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tests.modules.matching.conftest import LOCAL_DB, requires_db

pytestmark = requires_db

if LOCAL_DB:
    from app.core.metrics import match_queue_depth, match_tier_24h
    from app.modules.auth.models import User
    from app.modules.jobs.models import SeekJob
    from app.modules.matching.models import JobMatch
    from app.modules.matching.observer import collect_match_gauges, publish
    from app.modules.resumes.models import Document, Resume

NOW = datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_collect_and_publish_match_gauges(session):
    session.add(User(id=1, email="u@example.com", hashed_password="x", full_name="U"))
    for job_id in range(1, 8):
        session.add(SeekJob(id=job_id, source_id=f"s{job_id}", title="Dev", listed_at=NOW))
    await session.flush()
    session.add(Document(id="doc1", root_id="doc1", content="resume", content_hash="h", created_by=1))
    await session.flush()
    session.add(Resume(id="res1", user_id=1, document_id="doc1", title="R", is_draft=False, is_deleted=False))
    await session.flush()
    base = {"user_id": 1, "job_family": "software_dev", "families_version": "f2", "family_relation": "same",
            "location_check": "matched"}
    session.add_all([
        JobMatch(id="q1", job_id=1, status="queued", origin="new_job", queued_at=NOW - timedelta(hours=30), **base),
        JobMatch(id="q2", job_id=2, status="queued", origin="backfill", queued_at=NOW - timedelta(days=3), **base),
        JobMatch(id="r1", job_id=3, status="failed_retryable", origin="new_job", judged_at=NOW, **base),
        JobMatch(id="a1", job_id=4, status="rated", tier="A", origin="new_job", judged_at=NOW, resume_id="res1",
                 **base),
        JobMatch(id="b1", job_id=5, status="rated", tier="B", origin="new_job", resume_id="res1",
                 judged_at=NOW - timedelta(hours=2), **base),
        JobMatch(id="old", job_id=6, status="rated", tier="A", origin="new_job", resume_id="res1",
                 judged_at=NOW - timedelta(days=2), **base),
        JobMatch(id="f1", job_id=7, status="failed_final", origin="new_job", judged_at=NOW, **base),
    ])
    await session.commit()

    values = await collect_match_gauges(session, now=NOW)
    assert values["depth"] == 3  # two queued + one retry pending
    assert 29.9 * 3600 < values["oldest_age"] < 30.1 * 3600  # backfill row ignored
    assert values["judged"] == {"rated": 2, "rejected": 0, "failed_retryable": 1, "failed_final": 1}
    assert values["tiers"] == {"A": 1, "B": 1, "C": 0, "D": 0}

    publish(values)
    assert match_queue_depth._value.get() == 3
    assert match_tier_24h.labels(tier="A")._value.get() == 1


@pytest.mark.asyncio
async def test_empty_queue_gauges(session):
    values = await collect_match_gauges(session, now=NOW)
    assert values["depth"] == 0 and values["oldest_age"] == 0.0
