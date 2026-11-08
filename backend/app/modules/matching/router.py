"""Matching v3 endpoints: role families and resume binding (users), labels and
title families (admins). Match results live under /jobs/matches."""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.admin.dependencies import require_admin
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.matching import service
from app.modules.matching.schemas import (
    MatchLabelCreate,
    MatchLabelInfo,
    ResumeRoleFamilyResponse,
    ResumeRoleFamilyUpdate,
    RoleFamilyInfo,
    TitleFamilyListResponse,
    TitleFamilyUpdate,
    TitleFamilyUpdateResponse,
)

router = APIRouter(prefix="/matching", tags=["matching"])
admin_router = APIRouter(prefix="/admin/matching", tags=["admin-matching"], dependencies=[Depends(require_admin)])


@router.get("/role-families", response_model=list[RoleFamilyInfo])
async def list_role_families(current_user: Annotated[User, Depends(get_current_user)]):
    """Role families a resume can be bound to."""
    return service.list_role_families()


@router.put("/resumes/{resume_id}/role-family", response_model=ResumeRoleFamilyResponse)
async def set_resume_role_family(
    resume_id: str,
    payload: ResumeRoleFamilyUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Bind a resume to a role family (null excludes it from matching)."""
    return await service.set_resume_role_family(db, current_user, resume_id, payload.role_family)


@admin_router.post("/labels", response_model=MatchLabelInfo, status_code=201)
async def create_label(
    payload: MatchLabelCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    """Label the admin's own result for a job (append-only)."""
    return await service.create_label(db, admin, payload)


@admin_router.get("/title-families", response_model=TitleFamilyListResponse)
async def list_title_families(
    db: Annotated[AsyncSession, Depends(get_db)],
    q: Optional[str] = Query(None, max_length=200),
    role_family: Optional[str] = None,
    status: Optional[str] = Query(None, pattern="^(classified|ambiguous)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_title_families(db, q=q, role_family=role_family, status=status,
                                             limit=limit, offset=offset)


@admin_router.put("/title-families", response_model=TitleFamilyUpdateResponse)
async def update_title_family(
    payload: TitleFamilyUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    """Pin a title to a family, or to ambiguous so its jobs' descriptions are read."""
    return await service.update_title_family(db, admin, payload.title, payload.role_family)
