"""Job detail, similar jobs and saved jobs report the caller's own state:
has_application (non-deleted application), is_viewed and last_viewed_at."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tests.modules.matching.conftest import LOCAL_DB, requires_db, session_factory  # noqa: F401

pytestmark = requires_db

NOW = datetime.now(timezone.utc)

if LOCAL_DB:
    from app.modules.applications.models import Application
    from app.modules.auth.models import User
    from app.modules.jobs.models import SeekJob, UserJobView, UserSavedJob
    from app.modules.jobs.router import get_job_detail, get_similar_jobs
    from app.modules.jobs.service import JobService
    from app.modules.resumes.models import Document, Resume
    from app.shared.enums import ApplicationStatus
    from app.shared.pagination import PaginationParams


async def _seed(db):
    """Jobs 1-3 at the same company; user 1 applied to 1, viewed 2, deleted an
    application to 3. User 2 applied to 2 (must not leak into user 1's view)."""
    for user_id in (1, 2):
        db.add(User(id=user_id, email=f"u{user_id}@example.com", hashed_password="x", full_name="U"))
    for job_id in (1, 2, 3):
        db.add(SeekJob(id=job_id, source_id=f"s{job_id}", title=f"Job {job_id}", company_name="Acme",
                       classification="IT", listed_at=NOW - timedelta(days=job_id)))
    await db.flush()
    for user_id in (1, 2):
        db.add(Document(id=f"doc{user_id}", root_id=f"doc{user_id}", content="# CV", content_hash="h", created_by=user_id))
    await db.flush()
    for user_id in (1, 2):
        db.add(Resume(id=f"res{user_id}", user_id=user_id, document_id=f"doc{user_id}", title="CV",
                      is_draft=False, is_deleted=False))
    await db.flush()
    db.add_all([
        Application(id="a1", user_id=1, job_id=1, source_resume_id="res1", status=ApplicationStatus.READY),
        Application(id="a3", user_id=1, job_id=3, source_resume_id="res1", status=ApplicationStatus.READY,
                    is_deleted=True),
        Application(id="b2", user_id=2, job_id=2, source_resume_id="res2", status=ApplicationStatus.READY),
        UserJobView(user_id=1, job_id=2, first_viewed_at=NOW, last_viewed_at=NOW, view_count=1),
        UserSavedJob(user_id=1, job_id=1),
        UserSavedJob(user_id=1, job_id=2),
    ])
    await db.commit()


def _state(item):
    return item.has_application, item.is_viewed


@pytest.mark.asyncio
async def test_job_detail(session_factory):  # noqa: F811
    async with session_factory() as db:
        await _seed(db)
        user = await db.get(User, 1)
        assert _state(await get_job_detail(1, db, user)) == (True, False)
        viewed = await get_job_detail(2, db, user)
        assert _state(viewed) == (False, True) and viewed.last_viewed_at is not None
        assert _state(await get_job_detail(3, db, user)) == (False, False)  # application deleted
        other = await db.get(User, 2)
        assert _state(await get_job_detail(2, db, other)) == (True, False)


@pytest.mark.asyncio
async def test_similar_jobs(session_factory):  # noqa: F811
    async with session_factory() as db:
        await _seed(db)
        user = await db.get(User, 1)
        items = await get_similar_jobs(3, db, user, limit=5)
        assert {item.id: _state(item) for item in items} == {1: (True, False), 2: (False, True)}


@pytest.mark.asyncio
async def test_saved_jobs(session_factory):  # noqa: F811
    async with session_factory() as db:
        await _seed(db)
        user = await db.get(User, 1)
        page = await JobService.list_saved_jobs(db, user, PaginationParams(page=1, page_size=10))
        assert {item.job.id: _state(item.job) for item in page.items} == {1: (True, False), 2: (False, True)}
