"""API key business logic."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, UnauthorizedError
from app.modules.api_keys.models import (
    API_KEY_PREFIX,
    API_KEY_PREFIX_LENGTH,
    ApiKey,
)


def _hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _generate_plaintext() -> str:
    return f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"


async def create_api_key(
    db: AsyncSession,
    *,
    user_id: int,
    name: str,
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    """Create a new API key. Returns (record, plaintext)."""
    plaintext = _generate_plaintext()
    record = ApiKey(
        id=str(uuid4()),
        user_id=user_id,
        name=name,
        prefix=plaintext[:API_KEY_PREFIX_LENGTH],
        key_hash=_hash_key(plaintext),
        scopes=[],
        expires_at=expires_at,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record, plaintext


async def list_api_keys(db: AsyncSession, *, user_id: int) -> list[ApiKey]:
    """List all non-revoked API keys for a user, newest first."""
    stmt = (
        select(ApiKey)
        .where(ApiKey.user_id == user_id, ApiKey.revoked_at.is_(None))
        .order_by(ApiKey.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def revoke_api_key(db: AsyncSession, *, user_id: int, key_id: str) -> None:
    """Soft-delete an API key the user owns."""
    stmt = select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id)
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None or record.revoked_at is not None:
        raise NotFoundError("API key not found")
    record.revoked_at = datetime.now(timezone.utc)
    await db.commit()


async def verify_api_key(db: AsyncSession, plaintext: str) -> ApiKey:
    """Validate an API key and update last_used_at. Raises UnauthorizedError on any failure."""
    if not plaintext.startswith(API_KEY_PREFIX):
        raise UnauthorizedError("Invalid credentials")

    prefix = plaintext[:API_KEY_PREFIX_LENGTH]
    key_hash = _hash_key(plaintext)
    now = datetime.now(timezone.utc)

    stmt = select(ApiKey).where(
        ApiKey.prefix == prefix,
        ApiKey.key_hash == key_hash,
    )
    record = (await db.execute(stmt)).scalar_one_or_none()

    if (
        record is None
        or record.revoked_at is not None
        or (record.expires_at is not None and record.expires_at <= now)
    ):
        raise UnauthorizedError("Invalid credentials")

    record.last_used_at = now
    await db.commit()
    return record
