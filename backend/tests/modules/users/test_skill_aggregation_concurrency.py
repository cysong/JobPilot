"""Skill aggregation for one user running in several workers at once (threads pool)."""
import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from tests.modules.matching.conftest import LOCAL_DB, requires_db, session_factory  # noqa: F401

pytestmark = requires_db

if LOCAL_DB:
    from app.modules.auth.models import User
    from app.modules.resumes.models import Document, Resume, ResumeSkill
    from app.modules.users.models import UserSkill
    from app.modules.users.service import aggregate_user_skills
    from app.shared.enums import ProficiencyLevel


@pytest.mark.asyncio
async def test_concurrent_aggregations_for_one_user_do_not_collide(session_factory):  # noqa: F811
    skills = [f"Skill {i}" for i in range(40)]
    async with session_factory() as db:
        db.add(User(id=1, email="u@example.com", hashed_password="x", full_name="U"))
        await db.flush()
        for r in range(4):
            db.add(Document(id=f"d{r}", root_id=f"d{r}", content="x", content_hash=f"h{r}", created_by=1))
            await db.flush()
            db.add(Resume(id=f"r{r}", user_id=1, document_id=f"d{r}", title=f"R{r}", is_draft=False, is_deleted=False))
            await db.flush()
            for i, name in enumerate(skills):
                db.add(ResumeSkill(id=f"rs{r}-{i}", user_id=1, resume_id=f"r{r}", skill_name=name,
                                   proficiency_level=ProficiencyLevel.INTERMEDIATE,
                                   created_at=datetime.now(timezone.utc)))
        await db.commit()

    async def run():
        async with session_factory() as db:
            return await aggregate_user_skills(db, 1)

    results = await asyncio.gather(*(run() for _ in range(4)), return_exceptions=True)
    assert not [r for r in results if isinstance(r, BaseException)], results
    async with session_factory() as db:
        assert (await db.execute(select(func.count()).select_from(UserSkill))).scalar_one() == len(skills)
