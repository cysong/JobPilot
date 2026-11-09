"""Expired = flagged (source or manual), past expires_at, or - without expires_at - listed over JOB_EXPIRY_DAYS ago."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.config import settings

from tests.modules.matching.conftest import LOCAL_DB, requires_db, session_factory  # noqa: F401

NOW = datetime.now(timezone.utc)
CASES = {  # job id -> (columns, expired?)
    1: (dict(), False),
    2: (dict(expires_at=NOW + timedelta(days=3)), False),
    3: (dict(expires_at=NOW - timedelta(hours=1)), True),
    4: (dict(is_expired=True, expires_at=NOW + timedelta(days=3)), True),
    5: (dict(manual_expired=True), True),
    6: (dict(is_expired=None, expires_at=None), False),
    7: (dict(listed_at=NOW - timedelta(days=29, hours=23)), False),
    8: (dict(listed_at=NOW - timedelta(days=30, minutes=1)), True),
    9: (dict(listed_at=NOW - timedelta(days=45), expires_at=NOW + timedelta(days=3)), False),
    10: (dict(listed_at=NOW - timedelta(days=2), expires_at=NOW - timedelta(hours=1)), True),
}

if LOCAL_DB:
    from app.core.exceptions import ConflictError
    from app.modules.applications.models import Application
    from app.modules.applications.schemas import ApplicationCreateRequest
    from app.modules.applications.service import ApplicationService
    from app.modules.auth.models import User
    from app.modules.jobs.models import SeekJob
    from app.modules.resumes.models import Document, Resume


async def _seed(db):
    db.add(User(id=1, email="u@example.com", hashed_password="x", full_name="U"))
    for job_id, (columns, _) in CASES.items():
        db.add(SeekJob(id=job_id, source_id=f"s{job_id}", title=f"Job {job_id}", **columns))
    await db.flush()
    db.add(Document(id="doc_src", root_id="doc_src", content="# CV", content_hash="h", created_by=1))
    await db.flush()
    db.add(Resume(id="res1", user_id=1, document_id="doc_src", title="CV", is_draft=False, is_deleted=False))
    await db.commit()


def test_python_form():
    from app.modules.jobs.models import SeekJob

    assert settings.JOB_EXPIRY_DAYS == 30  # the cases assume the default
    for job_id, (columns, expired) in CASES.items():
        assert SeekJob(**columns).effective_is_expired is expired, job_id


@requires_db
@pytest.mark.asyncio
async def test_sql_form_matches_and_is_never_null(session_factory):  # noqa: F811
    async with session_factory() as db:
        await _seed(db)
        live = set((await db.execute(select(SeekJob.id).where(SeekJob.effective_is_expired.is_(False)))).scalars())
        dead = set((await db.execute(select(SeekJob.id).where(SeekJob.effective_is_expired.is_(True)))).scalars())
    assert live == {i for i, (_, expired) in CASES.items() if not expired}
    assert dead == {i for i, (_, expired) in CASES.items() if expired}


def test_expiry_days_is_configurable(monkeypatch):
    from app.modules.jobs.models import SeekJob

    monkeypatch.setattr(settings, "JOB_EXPIRY_DAYS", 60)
    assert SeekJob(listed_at=NOW - timedelta(days=45)).effective_is_expired is False


@requires_db
@pytest.mark.asyncio
async def test_expired_job_cannot_be_added_to_applications(session_factory, monkeypatch):  # noqa: F811
    async def no_dispatch(*args, **kwargs):
        return None

    monkeypatch.setattr(ApplicationService, "_submit_initialization_task", staticmethod(no_dispatch))
    async with session_factory() as db:
        await _seed(db)
        user = await db.get(User, 1)
        with pytest.raises(ConflictError):
            await ApplicationService.create_application(
                db, user, ApplicationCreateRequest(job_id=3, resume_template_id="res1"))
        await db.rollback()
        user = await db.get(User, 1)
        created = await ApplicationService.create_application(
            db, user, ApplicationCreateRequest(job_id=2, resume_template_id="res1"))
        assert created.job_id == 2
        assert (await db.execute(select(Application.job_id))).scalars().all() == [2]
