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

from sqlalchemy import case, select, func, delete, Integer, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.users.models import UserSkill
from app.modules.users.schemas import ProfilePreferencesUpdate, UserProfileUpdate
from app.modules.resumes.models import Resume, ResumeSkill
from app.shared.enums import ProficiencyLevel
from app.shared.skills import canonical_skill_name, highest_proficiency, is_known_canonical, proficiency_rank, skill_key


# ============================================
# Skill Aggregation
# ============================================

SKILL_AGGREGATION_LOCK_NS = 731001  # pg advisory lock namespace for per-user skill aggregation


async def aggregate_user_skills(
    db: AsyncSession,
    user_id: int,
    affected_skill_names: Optional[List[str]] = None,
    *,
    commit: bool = True,
) -> Dict[str, Any]:
    """
    Aggregate user skills from resume_skills to user_skills.

    This function:
    1. Reads the skills of the user's non-draft, non-deleted resumes and groups
       them by ``skill_key`` (case, punctuation and known aliases ignored)
    2. Takes the highest proficiency by rank (not SQL MAX, which compares the
       stored strings alphabetically)
    3. Updates or creates one user_skills row per skill, merging rows that
       already exist under several spellings into one
    4. Respects manual skills (is_manual=True) by not overwriting their proficiency
    5. Cleans up orphaned auto skills (full sync only)

    Args:
        db: Database session
        user_id: User ID
        affected_skill_names: Optional list of specific skills to update (for incremental updates)
        commit: Commit at the end (the resync script passes False for dry runs)

    Returns:
        dict: Summary with total_skills, manual_skills, auto_skills counts
    """
    # Concurrent workers can aggregate the same user at once (e.g. several resumes
    # analysed together); serialise per user so the read-then-insert below cannot
    # race on uk_user_skill. Released when this transaction commits.
    await db.execute(text("SELECT pg_advisory_xact_lock(:ns, :user_id)"),
                     {"ns": SKILL_AGGREGATION_LOCK_NS, "user_id": user_id})

    affected_keys = {skill_key(name) for name in affected_skill_names} if affected_skill_names else None

    # Step 1: resume skills grouped by skill identity
    resume_rows = (await db.execute(
        select(ResumeSkill.skill_name, ResumeSkill.proficiency_level, ResumeSkill.created_at)
        .join(Resume, Resume.id == ResumeSkill.resume_id)
        .where(
            ResumeSkill.user_id == user_id,
            Resume.is_draft.is_(False),
            Resume.is_deleted.is_(False),
        )
    )).all()

    groups: dict[str, dict[str, Any]] = {}
    for name, level, created_at in resume_rows:
        key = skill_key(name)
        if not key or (affected_keys is not None and key not in affected_keys):
            continue
        group = groups.setdefault(key, {"names": {}, "levels": [], "count": 0, "last_seen": None})
        seen_count, seen_at = group["names"].get(name, (0, None))
        group["names"][name] = (seen_count + 1, _latest(seen_at, created_at))
        group["levels"].append(level)
        group["count"] += 1
        group["last_seen"] = _latest(group["last_seen"], created_at)

    existing_by_key: dict[str, list[UserSkill]] = {}
    for skill in (await db.execute(select(UserSkill).where(UserSkill.user_id == user_id))).scalars().all():
        key = skill_key(skill.skill_name)
        if affected_keys is None or key in affected_keys:
            existing_by_key.setdefault(key, []).append(skill)

    # Step 2: pick one surviving row per skill; the rest are merged away
    keepers: dict[str, UserSkill] = {}
    to_delete: list[UserSkill] = []
    for key, rows in existing_by_key.items():
        keeper = _pick_keeper(rows)
        if key not in groups and not keeper.is_manual and affected_keys is None:
            to_delete.extend(rows)  # orphaned auto skill (full sync only)
            continue
        keepers[key] = keeper
        to_delete.extend(row for row in rows if row is not keeper)

    # Delete before renaming so the renames cannot collide on uk_user_skill.
    for skill in to_delete:
        await db.delete(skill)
    if to_delete:
        await db.flush()

    # Step 3: update or create
    now = datetime.now(timezone.utc)
    for key, group in groups.items():
        keeper = keepers.get(key)
        display_name = _display_name(group["names"], keeper)
        level = highest_proficiency(group["levels"]) or ProficiencyLevel.INTERMEDIATE
        if keeper is not None:
            keeper.skill_name = display_name
            if not keeper.is_manual:
                keeper.proficiency_level = level
            keeper.source_count = group["count"]
            keeper.last_seen_at = group["last_seen"]
            keeper.updated_at = now
        else:
            db.add(UserSkill(
                id=str(uuid4()),
                user_id=user_id,
                skill_name=display_name,
                proficiency_level=level,
                is_manual=False,
                source_count=group["count"],
                last_seen_at=group["last_seen"],
            ))

    # Manual skills merged above may have lost their resume sources entirely.
    for key, keeper in keepers.items():
        if key not in groups and keeper.is_manual:
            keeper.skill_name = canonical_skill_name(keeper.skill_name)

    if commit:
        await db.commit()
    else:
        await db.flush()

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


def _latest(a: Optional[datetime], b: Optional[datetime]) -> Optional[datetime]:
    if a is None:
        return b
    if b is None:
        return a
    return max(a, b)


def _pick_keeper(rows: List[UserSkill]) -> UserSkill:
    """The row that survives a merge: a manual one (highest manual level) first."""
    def sort_key(skill: UserSkill) -> tuple:
        manual_level = skill.manual_proficiency or skill.proficiency_level
        return (
            1 if skill.is_manual else 0,
            proficiency_rank(manual_level) if skill.is_manual else 0,
            skill.source_count or 0,
        )
    return max(rows, key=sort_key)


def _display_name(names: Dict[str, tuple], keeper: Optional[UserSkill]) -> str:
    """Curated canonical spelling > the user's manual spelling > most used / most recent spelling."""
    candidate = next(iter(names))
    if is_known_canonical(candidate):
        return canonical_skill_name(candidate)
    if keeper is not None and keeper.is_manual:
        return keeper.skill_name
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    return max(names.items(), key=lambda item: (item[1][0], item[1][1] or epoch))[0]


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
    normalized_skill = canonical_skill_name(skill_name)
    key = skill_key(normalized_skill)

    # Same skill under another spelling ("pytest" vs "Pytest", "CSS3" vs "CSS") counts as existing.
    existing_names = (await db.execute(
        select(UserSkill.skill_name).where(UserSkill.user_id == user_id)
    )).scalars().all()
    existing = next((name for name in existing_names if skill_key(name) == key), None)

    if existing:
        raise ValueError(f"Skill '{skill_name}' already exists for this user as '{existing}'")

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
    """Return the stored profile preferences for a user, plus a work rights hint."""
    user = await db.get(User, user_id)
    if not user:
        return {}
    preferences = dict(user.preferences or {})
    preferences["work_right_hint"] = await _latest_resume_work_right(db, user_id)
    return preferences


async def _latest_resume_work_right(db: AsyncSession, user_id: int) -> str | None:
    analyses = (await db.execute(
        select(Resume.analysis_result)
        .where(Resume.user_id == user_id, Resume.is_draft.is_(False), Resume.is_deleted.is_(False),
               Resume.analysis_result.is_not(None))
        .order_by(Resume.updated_at.desc())
        .limit(5)
    )).scalars().all()
    for analysis in analyses:
        value = (analysis or {}).get("work_right")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


async def update_profile_preferences(
    db: AsyncSession,
    user_id: int,
    payload: ProfilePreferencesUpdate,
) -> dict[str, Any]:
    """Persist the profile preferences sent in the payload.

    Only fields present in the request are written; other stored keys are kept, so
    a client that does not know a newer preference cannot erase it.
    """
    user = await db.get(User, user_id)
    if not user:
        return {}

    updates = payload.model_dump(mode="json", exclude_unset=True)
    user.preferences = {**(user.preferences or {}), **updates}
    user.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(user)
    # Same shape as GET, including the derived work_right_hint, so a client
    # that renders the response does not see the hint vanish after saving.
    preferences = dict(user.preferences or {})
    preferences["work_right_hint"] = await _latest_resume_work_right(db, user_id)
    return preferences
