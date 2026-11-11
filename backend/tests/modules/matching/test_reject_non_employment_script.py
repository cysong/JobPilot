"""scripts/reject_non_employment_matches.py on a real Postgres."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import select

from tests.modules.matching.conftest import LOCAL_DB, requires_db

pytestmark = requires_db

if LOCAL_DB:
    from app.modules.auth.models import User
    from app.modules.jobs.models import SeekJob
    from app.modules.matching.models import JobMatch

_SPEC = importlib.util.spec_from_file_location(
    "reject_script", Path(__file__).resolve().parents[3] / "scripts" / "reject_non_employment_matches.py")


def _row(id_, job_id, status, tier=None, code=None, location_check="matched"):
    return JobMatch(id=id_, user_id=1, job_id=job_id, status=status, origin="new_job", job_family="qa_test",
                    families_version="f2", family_relation="same", location_check=location_check,
                    tier=tier, resume_id=None, reject_code=code,
                    reject_reason="x" if code else None)


@pytest.mark.asyncio
async def test_blocklisted_matches_are_rejected_and_others_untouched(session):
    script = importlib.util.module_from_spec(_SPEC)
    _SPEC.loader.exec_module(script)
    session.add(User(id=1, email="u@example.com", hashed_password="x", full_name="U"))
    for job_id, advertiser in ((1, "Crewlia"), (2, "Crewlia"), (3, "Acme Ltd"), (4, "Hired")):
        session.add(SeekJob(id=job_id, source_id=f"s{job_id}", title="QA", advertiser_name=advertiser))
    await session.flush()
    session.add_all([
        _row("m1", 1, "queued"),
        _row("m2", 2, "rejected", code="LOCATION", location_check="rejected"),
        _row("m3", 3, "queued"),
        _row("m4", 4, "rejected", tier="C", code="WORK_RIGHTS"),
    ])
    await session.commit()

    changed = await script.reclassify(session)
    await session.commit()
    assert sorted(m.id for m, _ in changed) == ["m1", "m4"]
    rows = {m.id: m for m in (await session.execute(select(JobMatch))).scalars()}
    assert (rows["m1"].status, rows["m1"].reject_code) == ("rejected", "NOT_EMPLOYMENT")
    assert rows["m4"].validation["reclassified"]["from_reject_code"] == "WORK_RIGHTS"
    assert rows["m2"].reject_code == "LOCATION" and rows["m3"].status == "queued"
    assert await script.reclassify(session) == []  # idempotent
