"""Utilities for one-time security tokens."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from fastapi import status

from app.core.exceptions import BadRequestError, JobPilotException
from app.core.response_codes import ResponseCode
from app.modules.auth.models import SecurityTokenType, UserSecurityToken


class SecurityTokenRateLimitError(JobPilotException):
    """Raised when token generation exceeds the configured rate limit."""

    def __init__(self) -> None:
        super().__init__(
            "Too many requests. Please try again later.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            response_code=ResponseCode.TOO_MANY_REQUESTS,
        )


def hash_security_token(token: str) -> str:
    """Hash a plain token before persisting it."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _token_expiration(token_type: SecurityTokenType) -> datetime:
    """Return expiration timestamp for a security token type."""
    now = datetime.now(timezone.utc)
    if token_type == SecurityTokenType.PASSWORD_RESET:
        return now + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    if token_type == SecurityTokenType.EMAIL_VERIFY:
        return now + timedelta(hours=settings.EMAIL_VERIFY_TOKEN_EXPIRE_HOURS)
    if token_type == SecurityTokenType.EMAIL_CHANGE:
        return now + timedelta(hours=settings.EMAIL_CHANGE_TOKEN_EXPIRE_HOURS)
    raise ValueError(f"Unsupported security token type: {token_type}")


async def _ensure_rate_limit(
    db: AsyncSession,
    user_id: int,
    token_type: SecurityTokenType,
) -> None:
    """Enforce DB-backed token generation rate limits."""
    window_start = datetime.now(timezone.utc) - timedelta(
        minutes=settings.SECURITY_TOKEN_RATE_LIMIT_WINDOW_MINUTES
    )
    stmt = select(func.count(UserSecurityToken.id)).where(
        UserSecurityToken.user_id == user_id,
        UserSecurityToken.token_type == token_type.value,
        UserSecurityToken.created_at >= window_start,
    )
    recent_count = (await db.execute(stmt)).scalar_one()
    if recent_count >= settings.SECURITY_TOKEN_RATE_LIMIT_MAX_COUNT:
        raise SecurityTokenRateLimitError()


async def _invalidate_existing_tokens(
    db: AsyncSession,
    user_id: int,
    token_type: SecurityTokenType,
) -> None:
    """Mark older tokens of the same type as consumed before creating a new one."""
    now = datetime.now(timezone.utc)
    stmt = select(UserSecurityToken).where(
        UserSecurityToken.user_id == user_id,
        UserSecurityToken.token_type == token_type.value,
        UserSecurityToken.consumed_at.is_(None),
        UserSecurityToken.expires_at > now,
    )
    records = (await db.execute(stmt)).scalars().all()
    for record in records:
        record.consumed_at = now


async def create_security_token(
    db: AsyncSession,
    user_id: int,
    token_type: SecurityTokenType,
    *,
    target_email: str | None = None,
) -> str:
    """Create a new one-time token and persist only its hash."""
    await _ensure_rate_limit(db, user_id, token_type)
    await _invalidate_existing_tokens(db, user_id, token_type)

    plain_token = secrets.token_urlsafe(32)
    record = UserSecurityToken(
        id=str(uuid4()),
        user_id=user_id,
        token_hash=hash_security_token(plain_token),
        token_type=token_type.value,
        target_email=target_email,
        expires_at=_token_expiration(token_type),
    )
    db.add(record)
    await db.commit()
    return plain_token


async def consume_security_token(
    db: AsyncSession,
    *,
    token: str,
    token_type: SecurityTokenType,
) -> UserSecurityToken:
    """Consume a valid token exactly once and return its DB record."""
    now = datetime.now(timezone.utc)
    stmt = select(UserSecurityToken).where(
        UserSecurityToken.token_hash == hash_security_token(token),
        UserSecurityToken.token_type == token_type.value,
    )
    record = (await db.execute(stmt)).scalar_one_or_none()

    if not record or record.consumed_at is not None or record.expires_at <= now:
        raise BadRequestError("Invalid or expired token")

    record.consumed_at = now
    await db.commit()
    await db.refresh(record)
    return record
