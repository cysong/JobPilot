"""
User skill management service layer.

This module provides business logic for:
1. Skill aggregation (from resume_skills to user_skills)
2. User skill CRUD operations
3. Helper functions for skill management
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import uuid4

from sqlalchemy import case, select, func, delete, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.users.models import UserSkill
from app.modules.users.schemas import ProfilePreferencesUpdate, UserProfileUpdate
from app.modules.resumes.models import ResumeSkill
from app.shared.enums import ProficiencyLevel


# ============================================
# Skill Aggregation
# ============================================

async def aggregate_user_skills(
    db: AsyncSession,
    user_id: int,
    affected_skill_names: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Aggregate user skills from resume_skills to user_skills.

    This function:
    1. Queries all resume_skills for the user, grouped by skill_name
    2. For each skill, takes the MAX proficiency level
    3. Updates or creates entries in user_skills
    4. Respects manual skills (is_manual=True) by not overwriting their proficiency
    5. Cleans up orphaned skills (skills that no longer exist in any resume)

    Args:
        db: Database session
        user_id: User ID
        affected_skill_names: Optional list of specific skills to update (for incremental updates)

    Returns:
        dict: Summary with total_skills, manual_skills, auto_skills counts
    """
    # Step 1: Query resume_skills aggregated by skill_name
    query = (
        select(
            ResumeSkill.skill_name,
            func.max(ResumeSkill.proficiency_level).label('max_proficiency'),
            func.count().label('source_count'),
            func.max(ResumeSkill.created_at).label('last_seen_at')
        )
        .where(ResumeSkill.user_id == user_id)
        .group_by(ResumeSkill.skill_name)
    )

    if affected_skill_names:
        query = query.where(ResumeSkill.skill_name.in_(affected_skill_names))

    result = await db.execute(query)
    resume_skills_agg = result.all()

    # Step 2: Update or create user_skills
    for skill_name, max_prof, count, last_seen in resume_skills_agg:
        stmt = select(UserSkill).where(
            UserSkill.user_id == user_id,
            UserSkill.skill_name == skill_name
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if existing:
            # Update existing skill
            if existing.is_manual:
                # Manual skill: only update metadata, keep proficiency
                existing.source_count = count
                existing.last_seen_at = last_seen
            else:
                # Auto skill: update proficiency and metadata
                existing.proficiency_level = max_prof
                existing.source_count = count
                existing.last_seen_at = last_seen

            existing.updated_at = datetime.now(timezone.utc)
        else:
            # Create new skill
            new_skill = UserSkill(
                id=str(uuid4()),
                user_id=user_id,
                skill_name=skill_name,
                proficiency_level=max_prof,
                is_manual=False,
                source_count=count,
                last_seen_at=last_seen
            )
            db.add(new_skill)

    # Step 3: Clean up orphaned skills (only if full sync, not incremental)
    if not affected_skill_names:
        all_resume_skill_names = {row[0] for row in resume_skills_agg}

        stmt = select(UserSkill).where(
            UserSkill.user_id == user_id,
            UserSkill.is_manual == False,
            UserSkill.skill_name.notin_(all_resume_skill_names) if all_resume_skill_names else True
        )
        orphaned_skills = (await db.execute(stmt)).scalars().all()

        for skill in orphaned_skills:
            await db.delete(skill)

    await db.commit()

    # Step 4: Get summary counts
    summary_stmt = select(
        func.count(UserSkill.id).label('total'),
        func.sum(func.cast(UserSkill.is_manual, Integer)).label('manual'),
    ).where(UserSkill.user_id == user_id)

    summary_result = (await db.execute(summary_stmt)).one()
    total_count = summary_result.total or 0
    manual_count = summary_result.manual or 0

    return {
        "total_skills": total_count,
        "manual_skills": manual_count,
        "auto_skills": total_count - manual_count,
    }


# ============================================
# User Skill CRUD Operations
# ============================================

async def get_user_skills(
    db: AsyncSession,
    user_id: int
) -> List[UserSkill]:
    """
    Get all skills for a user, ordered by proficiency and name.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        List of UserSkill objects
    """
    # Order proficiency by custom weight (expert > advanced > intermediate > beginner)
    proficiency_weight = case(
        (UserSkill.proficiency_level == ProficiencyLevel.EXPERT, 4),
        (UserSkill.proficiency_level == ProficiencyLevel.ADVANCED, 3),
        (UserSkill.proficiency_level == ProficiencyLevel.INTERMEDIATE, 2),
        (UserSkill.proficiency_level == ProficiencyLevel.BEGINNER, 1),
        else_=0,
    )

    stmt = (
        select(UserSkill)
        .where(UserSkill.user_id == user_id)
        .order_by(
            proficiency_weight.desc(),
            UserSkill.skill_name.asc()
        )
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_user_skill(
    db: AsyncSession,
    user_id: int,
    skill_name: str,
    proficiency_level: ProficiencyLevel
) -> UserSkill:
    """
    Manually create a new skill for a user.

    Args:
        db: Database session
        user_id: User ID
        skill_name: Skill name
        proficiency_level: Proficiency level

    Returns:
        Created UserSkill object

    Raises:
        ValueError: If skill already exists for this user
    """
    normalized_skill = skill_name.strip()

    # Check if skill already exists
    existing_stmt = select(UserSkill).where(
        UserSkill.user_id == user_id,
        func.lower(UserSkill.skill_name) == normalized_skill.lower()
    )
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()

    if existing:
        raise ValueError(f"Skill '{skill_name}' already exists for this user")

    # Create new manual skill
    new_skill = UserSkill(
        id=str(uuid4()),
        user_id=user_id,
        skill_name=normalized_skill,
        proficiency_level=proficiency_level,
        is_manual=True,
        manual_proficiency=proficiency_level,
        source_count=0,
        last_seen_at=None
    )

    db.add(new_skill)
    await db.commit()
    await db.refresh(new_skill)

    return new_skill


async def update_user_skill(
    db: AsyncSession,
    user_id: int,
    skill_id: str,
    proficiency_level: ProficiencyLevel
) -> UserSkill:
    """
    Update skill proficiency level (marks it as manual).

    Args:
        db: Database session
        user_id: User ID (for authorization check)
        skill_id: Skill ID to update
        proficiency_level: New proficiency level

    Returns:
        Updated UserSkill object

    Raises:
        ValueError: If skill not found or doesn't belong to user
    """
    stmt = select(UserSkill).where(
        UserSkill.id == skill_id,
        UserSkill.user_id == user_id
    )
    skill = (await db.execute(stmt)).scalar_one_or_none()

    if not skill:
        raise ValueError(f"Skill with ID {skill_id} not found or doesn't belong to user")

    # Update skill and mark as manual
    skill.proficiency_level = proficiency_level
    skill.is_manual = True
    skill.manual_proficiency = proficiency_level
    skill.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(skill)

    return skill


async def delete_user_skill(
    db: AsyncSession,
    user_id: int,
    skill_id: str
) -> bool:
    """
    Delete a user skill.

    Note: This only deletes from user_skills, not from resume_skills.
    If the skill exists in resumes, it will be re-created on next aggregation.

    Args:
        db: Database session
        user_id: User ID (for authorization check)
        skill_id: Skill ID to delete

    Returns:
        True if deleted, False if not found

    Raises:
        ValueError: If skill doesn't belong to user
    """
    stmt = select(UserSkill).where(
        UserSkill.id == skill_id,
        UserSkill.user_id == user_id
    )
    skill = (await db.execute(stmt)).scalar_one_or_none()

    if not skill:
        return False

    await db.delete(skill)
    await db.commit()

    return True


async def get_skill_by_id(
    db: AsyncSession,
    user_id: int,
    skill_id: str
) -> Optional[UserSkill]:
    """
    Get a specific skill by ID.

    Args:
        db: Database session
        user_id: User ID (for authorization)
        skill_id: Skill ID

    Returns:
        UserSkill if found, None otherwise
    """
    stmt = select(UserSkill).where(
        UserSkill.id == skill_id,
        UserSkill.user_id == user_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ============================================
# Helper Functions
# ============================================

def compare_proficiency(level1: ProficiencyLevel, level2: ProficiencyLevel) -> int:
    """
    Compare two proficiency levels.

    Args:
        level1: First proficiency level
        level2: Second proficiency level

    Returns:
        -1 if level1 < level2, 0 if equal, 1 if level1 > level2
    """
    weights = {
        ProficiencyLevel.BEGINNER: 1,
        ProficiencyLevel.INTERMEDIATE: 2,
        ProficiencyLevel.ADVANCED: 3,
        ProficiencyLevel.EXPERT: 4,
    }

    weight1 = weights[level1]
    weight2 = weights[level2]

    if weight1 < weight2:
        return -1
    elif weight1 > weight2:
        return 1
    else:
        return 0


async def update_user_profile(
    db: AsyncSession,
    user: User,
    payload: UserProfileUpdate,
) -> User:
    """Update the user's identity fields (full_name, avatar_seed)."""
    changed = False

    if payload.full_name is not None:
        new_name = payload.full_name.strip()
        if not new_name:
            raise ValueError("full_name cannot be empty")
        if new_name != user.full_name:
            user.full_name = new_name
            changed = True

    if "avatar_seed" in payload.model_fields_set:
        new_seed = payload.avatar_seed.strip() if payload.avatar_seed else None
        if new_seed != user.avatar_seed:
            user.avatar_seed = new_seed or None
            changed = True

    if changed:
        user.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)

    return user


async def get_profile_preferences(
    db: AsyncSession,
    user_id: int,
) -> dict[str, Any]:
    """Return the stored profile preferences for a user."""
    user = await db.get(User, user_id)
    if not user:
        return {}
    return dict(user.preferences or {})


async def update_profile_preferences(
    db: AsyncSession,
    user_id: int,
    payload: ProfilePreferencesUpdate,
) -> dict[str, Any]:
    """Persist the supported profile preferences for a user."""
    user = await db.get(User, user_id)
    if not user:
        return {}

    user.preferences = {
        "default_tailoring_level": (
            payload.default_tailoring_level.value
            if payload.default_tailoring_level is not None
            else None
        ),
        "job_locations": payload.job_locations,
        "salary_expectation": (
            payload.salary_expectation.model_dump()
            if payload.salary_expectation is not None
            else None
        ),
    }
    user.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(user)
    return dict(user.preferences or {})
