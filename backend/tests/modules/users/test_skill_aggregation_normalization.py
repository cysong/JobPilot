"""Skill aggregation: spelling variants merge, levels rank properly, manual levels stick."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from tests.modules.matching.conftest import LOCAL_DB, requires_db, session_factory  # noqa: F401

pytestmark = requires_db

if LOCAL_DB:
    from app.modules.auth.models import User
    from app.modules.resumes.models import Document, Resume, ResumeSkill
    from app.modules.resumes.service import ResumeService
    from app.modules.users.models import UserSkill
    from app.modules.users.service import aggregate_user_skills, create_user_skill
    from app.shared.enums import ProficiencyLevel as P

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


async def _seed(db, resumes: dict[str, list[tuple[str, "P"]]], drafts: set[str] = frozenset()):
    db.add(User(id=1, email="u@example.com", hashed_password="x", full_name="U"))
    await db.flush()
    for i, (rid, skills) in enumerate(resumes.items()):
        db.add(Document(id=f"d-{rid}", root_id=f"d-{rid}", content="x", content_hash=f"h-{rid}", created_by=1))
        await db.flush()
        db.add(Resume(id=rid, user_id=1, document_id=f"d-{rid}", title=rid,
                      is_draft=rid in drafts, is_deleted=False))
        await db.flush()
        for j, (name, level) in enumerate(skills):
            db.add(ResumeSkill(id=f"{rid}-{j}", user_id=1, resume_id=rid, skill_name=name,
                               proficiency_level=level, created_at=T0 + timedelta(days=i)))
    await db.commit()


async def _user_skills(db) -> dict[str, tuple]:
    rows = (await db.execute(select(UserSkill).where(UserSkill.user_id == 1))).scalars().all()
    return {r.skill_name: (r.proficiency_level, r.is_manual, r.source_count) for r in rows}


@pytest.mark.asyncio
async def test_highest_level_by_rank_not_alphabet(session_factory):  # noqa: F811
    async with session_factory() as db:
        await _seed(db, {
            "r1": [("Docker", P.EXPERT)],
            "r2": [("Docker", P.INTERMEDIATE)],
            "r3": [("Docker", P.ADVANCED)],
        })
        await aggregate_user_skills(db, 1)
        assert await _user_skills(db) == {"Docker": (P.EXPERT, False, 3)}


@pytest.mark.asyncio
async def test_spelling_variants_merge_into_one_skill(session_factory):  # noqa: F811
    async with session_factory() as db:
        await _seed(db, {
            "r1": [("pytest", P.BEGINNER), ("CSS3", P.INTERMEDIATE)],
            "r2": [("Pytest", P.ADVANCED), ("CSS", P.BEGINNER)],
            "r3": [("Pytest", P.BEGINNER)],
        })
        await aggregate_user_skills(db, 1)
        # Unknown casing: majority spelling wins. Known alias: curated name wins.
        assert await _user_skills(db) == {
            "Pytest": (P.ADVANCED, False, 3),
            "CSS": (P.INTERMEDIATE, False, 2),
        }


@pytest.mark.asyncio
async def test_existing_duplicate_rows_are_merged_and_manual_level_kept(session_factory):  # noqa: F811
    async with session_factory() as db:
        await _seed(db, {"r1": [("Shell Scripting", P.ADVANCED)], "r2": [("Shell", P.BEGINNER)]})
        # Rows written by the old exact-match aggregation, one of them edited by hand.
        db.add_all([
            UserSkill(id="a", user_id=1, skill_name="Shell", proficiency_level=P.BEGINNER,
                      is_manual=False, source_count=1),
            UserSkill(id="b", user_id=1, skill_name="Shell scripting", proficiency_level=P.EXPERT,
                      is_manual=True, manual_proficiency=P.EXPERT, source_count=1),
        ])
        await db.commit()

        await aggregate_user_skills(db, 1)
        skills = await _user_skills(db)
        assert skills == {"Shell Scripting": (P.EXPERT, True, 2)}


@pytest.mark.asyncio
async def test_draft_resumes_do_not_count_and_orphans_are_removed(session_factory):  # noqa: F811
    async with session_factory() as db:
        await _seed(db, {"r1": [("Java", P.INTERMEDIATE)], "draft": [("Java", P.EXPERT), ("Rust", P.EXPERT)]},
                    drafts={"draft"})
        db.add(UserSkill(id="old", user_id=1, skill_name="Rust", proficiency_level=P.EXPERT,
                         is_manual=False, source_count=1))
        await db.commit()

        await aggregate_user_skills(db, 1)
        assert await _user_skills(db) == {"Java": (P.INTERMEDIATE, False, 1)}


@pytest.mark.asyncio
async def test_dry_run_aggregation_does_not_commit(session_factory):  # noqa: F811
    async with session_factory() as db:
        await _seed(db, {"r1": [("Go", P.ADVANCED)]})
        await aggregate_user_skills(db, 1, commit=False)
        await db.rollback()
        assert await _user_skills(db) == {}


@pytest.mark.asyncio
async def test_update_resume_skills_matches_existing_rows_by_key(session_factory):  # noqa: F811
    async with session_factory() as db:
        await _seed(db, {"r1": [("pytest", P.BEGINNER), ("Pytest", P.BEGINNER), ("Old Tool", P.BEGINNER)]})
        evidence = [{"category": "experience", "source_label": "X", "quotes": ["q"]}]
        kept, deleted = await ResumeService.update_resume_skills(db, "r1", 1, [
            {"name": "PyTest", "proficiency": "advanced", "extracted_from": evidence},
            {"name": "CSS3", "proficiency": "expert", "extracted_from": []},
        ])
        await db.commit()

        rows = (await db.execute(select(ResumeSkill).where(ResumeSkill.resume_id == "r1"))).scalars().all()
        assert kept == 2 and deleted == 2  # duplicate "Pytest" row and "Old Tool"
        assert {(r.skill_name, r.proficiency_level) for r in rows} == {
            ("PyTest", P.ADVANCED),
            ("CSS", P.INTERMEDIATE),  # no evidence -> capped
        }


@pytest.mark.asyncio
async def test_manual_create_rejects_other_spelling_of_existing_skill(session_factory):  # noqa: F811
    async with session_factory() as db:
        await _seed(db, {})
        created = await create_user_skill(db, 1, "css3", P.ADVANCED)
        assert created.skill_name == "CSS"
        with pytest.raises(ValueError):
            await create_user_skill(db, 1, "CSS", P.BEGINNER)
