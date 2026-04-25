"""API key management endpoints."""
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_jwt_only
from app.modules.api_keys import service
from app.modules.api_keys.schemas import (
    ApiKeyCreate,
    ApiKeyCreatedResponse,
    ApiKeyResponse,
)
from app.modules.auth.models import User

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


@router.post(
    "",
    response_model=ApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key_route(
    payload: ApiKeyCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_jwt_only)],
):
    """Create a new API key. The plaintext value is returned only once."""
    record, plaintext = await service.create_api_key(
        db,
        user_id=current_user.id,
        name=payload.name,
        expires_at=payload.expires_at,
    )
    return ApiKeyCreatedResponse(
        id=record.id,
        name=record.name,
        prefix=record.prefix,
        scopes=list(record.scopes or []),
        last_used_at=record.last_used_at,
        expires_at=record.expires_at,
        revoked_at=record.revoked_at,
        created_at=record.created_at,
        plaintext=plaintext,
    )


@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys_route(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_jwt_only)],
):
    """List active API keys for the current user."""
    records = await service.list_api_keys(db, user_id=current_user.id)
    return [ApiKeyResponse.model_validate(r) for r in records]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key_route(
    key_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_jwt_only)],
):
    """Revoke an API key owned by the current user."""
    await service.revoke_api_key(db, user_id=current_user.id, key_id=key_id)
    return None
