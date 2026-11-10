"""Re-derive resume_skills and user_skills with the current normalisation rules.

Fixes data written before skill names were normalised and before levels were
ranked properly (SQL MAX on the stored strings picked INTERMEDIATE over
ADVANCED / EXPERT):

1. For every resume with a stored analysis, rewrite its resume_skills from
   ``analysis_result.technical_skills`` (canonical names, in-list duplicates
   merged, skills without evidence capped at INTERMEDIATE).
2. Re-aggregate user_skills for every affected user (rows for one skill under
   several spellings merged, highest level by rank). Manual levels are kept.

Dry run by default: everything happens in one transaction that is rolled
back, and the per-user changes are printed. Pass --apply to commit.

    uv run --with greenlet python scripts/resync_skills.py [--user-id 1] [--apply]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.database import async_session_factory  # noqa: E402
from app.modules.resumes.models import Resume  # noqa: E402
from app.modules.resumes.service import ResumeService  # noqa: E402
from app.modules.users.models import UserSkill  # noqa: E402
from app.modules.users.service import aggregate_user_skills  # noqa: E402


def _level(skill: UserSkill) -> str:
    level = skill.manual_proficiency if skill.is_manual and skill.manual_proficiency else skill.proficiency_level
    return getattr(level, "value", str(level))


async def _snapshot(db, user_id: int) -> dict[str, str]:
    rows = (await db.execute(select(UserSkill).where(UserSkill.user_id == user_id))).scalars().all()
    return {row.skill_name: _level(row) for row in rows}


def _report(user_id: int, before: dict[str, str], after: dict[str, str]) -> None:
    removed = sorted(set(before) - set(after), key=str.lower)
    added = sorted(set(after) - set(before), key=str.lower)
    changed = sorted(
        (name for name in set(before) & set(after) if before[name] != after[name]), key=str.lower
    )
    print(f"\n== user {user_id}: {len(before)} -> {len(after)} skills")
    for name in changed:
        print(f"  level   {name}: {before[name]} -> {after[name]}")
    for name in removed:
        print(f"  removed {name} ({before[name]})")
    for name in added:
        print(f"  added   {name} ({after[name]})")
    if not (changed or removed or added):
        print("  no changes")


async def main(user_id: int | None, apply: bool) -> None:
    async with async_session_factory() as db:
        query = select(Resume).where(Resume.is_deleted.is_(False), Resume.analysis_result.is_not(None))
        if user_id is not None:
            query = query.where(Resume.user_id == user_id)
        resumes = (await db.execute(query)).scalars().all()
        user_ids = sorted({resume.user_id for resume in resumes})

        before = {uid: await _snapshot(db, uid) for uid in user_ids}

        for resume in resumes:
            technical_skills = (resume.analysis_result or {}).get("technical_skills") or []
            await ResumeService.update_resume_skills(
                db, resume_id=resume.id, user_id=resume.user_id, skills=technical_skills
            )
        await db.flush()

        for uid in user_ids:
            await aggregate_user_skills(db, uid, commit=False)
            _report(uid, before[uid], await _snapshot(db, uid))

        if apply:
            await db.commit()
            print(f"\nApplied: {len(resumes)} resumes, {len(user_ids)} users.")
        else:
            await db.rollback()
            print(f"\nDry run: {len(resumes)} resumes, {len(user_ids)} users. Nothing written; pass --apply to commit.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user-id", type=int, default=None, help="Only resync this user")
    parser.add_argument("--apply", action="store_true", help="Commit the changes (default: dry run)")
    args = parser.parse_args()
    asyncio.run(main(args.user_id, args.apply))
