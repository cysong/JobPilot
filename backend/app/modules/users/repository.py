"""Repository layer for user skills."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import UserSkill
from app.shared.enums import ProficiencyLevel
from app.shared.utils import generate_id


class UserSkillRepository:
    """Upsert operations for user skills."""

    @staticmethod
    async def upsert_from_resume_analysis(
        db: AsyncSession,
        user_id: int,
        skills: list[dict],
        resume_id: str,
    ):
        """
        Upsert skills from resume analysis.

        Rules:
        - New skill: Create
        - Existing skill: Only update if new proficiency is higher
        """
        proficiency_order = {
            ProficiencyLevel.BEGINNER: 1,
            ProficiencyLevel.INTERMEDIATE: 2,
            ProficiencyLevel.ADVANCED: 3,
            ProficiencyLevel.EXPERT: 4,
        }

        for skill_data in skills:
            existing = await db.execute(
                select(UserSkill).where(
                    UserSkill.user_id == user_id,
                    UserSkill.skill_name == skill_data["name"]
                )
            )
            existing_skill = existing.scalar_one_or_none()

            new_proficiency = ProficiencyLevel(skill_data["proficiency"])

            if not existing_skill:
                new_skill = UserSkill(
                    id=generate_id("usk"),
                    user_id=user_id,
                    skill_name=skill_data["name"],
                    proficiency_level=new_proficiency,
                    is_manual=False,
                    source_count=1,
                    last_seen_at=datetime.now(timezone.utc),
                )
                db.add(new_skill)
            else:
                # Update if new proficiency is higher (and not manually set)
                if not existing_skill.is_manual:
                    if proficiency_order[new_proficiency] > proficiency_order[existing_skill.proficiency_level]:
                        existing_skill.proficiency_level = new_proficiency
                    existing_skill.source_count += 1
                    existing_skill.last_seen_at = datetime.now(timezone.utc)

    @staticmethod
    async def get_by_user_id(db: AsyncSession, user_id: int) -> list[dict]:
        """Return user skills as dictionaries for matching."""
        result = await db.execute(select(UserSkill).where(UserSkill.user_id == user_id))
        skills = []
        for skill in result.scalars().all():
            # Use manual_proficiency if set, otherwise use proficiency_level
            proficiency = skill.manual_proficiency if skill.is_manual and skill.manual_proficiency else skill.proficiency_level
            skills.append(
                {
                    "skill_name": skill.skill_name,
                    "proficiency": proficiency.value,  # Convert enum to string
                }
            )
        return skills
