"""Authentication and account-security service layer."""
import hashlib
import logging
import secrets
from datetime import datetime, timezone
from threading import Lock
from typing import Optional
from uuid import uuid4

from fastapi_cache import FastAPICache
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError, UnauthorizedError
from app.core.security import hash_password, verify_password
from app.modules.auth.email_service import AuthEmailService
from app.modules.auth.models import (
    API_KEY_PREFIX,
    API_KEY_PREFIX_LENGTH,
    ApiKey,
    SecurityTokenType,
    User,
)
from app.modules.auth.schemas import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserRegister,
    VerifyTokenRequest,
)
from app.modules.auth.token_service import (
    SecurityTokenRateLimitError,
    consume_security_token,
    create_security_token,
)
from app.shared.enums import Role
from app.core.cache import jcache


# @jcache("user:{email}")
async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Get user by email address."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """Get user by ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user_data: UserRegister) -> User:
    """Create a new user account."""
    existing_user = await get_user_by_email(db, email=user_data.email)
    if existing_user:
        raise ConflictError("Email already registered")

    db_user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        role=Role(settings.DEFAULT_USER_ROLE),
        is_active=True,
        preferences={},
    )

    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    # Registration should remain successful even if email delivery is temporarily unavailable.
    try:
        plain_token = await create_security_token(
            db=db,
            user_id=db_user.id,
            token_type=SecurityTokenType.EMAIL_VERIFY,
        )
        await AuthEmailService.send_verification_email(db_user.email, plain_token)
    except Exception:
        pass

    return db_user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    """Authenticate user with email and password."""
    user = await get_user_by_email(db, email=email)

    if not user:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user


async def forgot_password(db: AsyncSession, payload: ForgotPasswordRequest) -> None:
    """Send password-reset instructions when the account exists."""
    user = await get_user_by_email(db, email=payload.email)
    if not user:
        return

    try:
        plain_token = await create_security_token(
            db=db,
            user_id=user.id,
            token_type=SecurityTokenType.PASSWORD_RESET,
        )
    except SecurityTokenRateLimitError:
        # Keep the forgot-password response uniform to avoid account enumeration.
        return

    await AuthEmailService.send_password_reset_email(user.email, plain_token)


async def reset_password(db: AsyncSession, payload: ResetPasswordRequest) -> None:
    """Reset password using a valid password-reset token."""
    record = await consume_security_token(
        db=db,
        token=payload.token,
        token_type=SecurityTokenType.PASSWORD_RESET,
    )

    user = await get_user_by_id(db, record.user_id)
    if not user:
        raise BadRequestError("Invalid or expired token")

    user.hashed_password = hash_password(payload.new_password)
    user.password_changed_at = datetime.now(timezone.utc)

    await db.commit()


async def verify_email(db: AsyncSession, payload: VerifyTokenRequest) -> User:
    """Verify the current email using a valid token."""
    record = await consume_security_token(
        db=db,
        token=payload.token,
        token_type=SecurityTokenType.EMAIL_VERIFY,
    )

    user = await get_user_by_id(db, record.user_id)
    if not user:
        raise BadRequestError("Invalid or expired token")

    user.email_verified_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


async def resend_verification_email(db: AsyncSession, current_user: User) -> None:
    """Re-send email-verification instructions for the current user."""
    if current_user.email_verified_at:
        return

    plain_token = await create_security_token(
        db=db,
        user_id=current_user.id,
        token_type=SecurityTokenType.EMAIL_VERIFY,
    )
    await AuthEmailService.send_verification_email(current_user.email, plain_token)


async def change_password(
    db: AsyncSession,
    current_user: User,
    payload: ChangePasswordRequest,
) -> User:
    """Change password for the authenticated user."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise UnauthorizedError("Current password is incorrect")

    current_user.hashed_password = hash_password(payload.new_password)
    current_user.password_changed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(current_user)
    return current_user


async def request_email_change(
    db: AsyncSession,
    current_user: User,
    payload: ChangeEmailRequest,
) -> None:
    """Request an email change for the authenticated user."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise UnauthorizedError("Current password is incorrect")

    normalized_email = payload.new_email.strip().lower()
    if normalized_email == current_user.email.lower():
        raise BadRequestError("New email must be different from the current email")

    existing_user = await get_user_by_email(db, normalized_email)
    if existing_user:
        raise ConflictError("Email already registered")

    plain_token = await create_security_token(
        db=db,
        user_id=current_user.id,
        token_type=SecurityTokenType.EMAIL_CHANGE,
        target_email=normalized_email,
    )
    await AuthEmailService.send_email_change_confirmation_email(normalized_email, plain_token)


async def confirm_email_change(db: AsyncSession, payload: VerifyTokenRequest) -> User:
    """Confirm a pending email-change request."""
    record = await consume_security_token(
        db=db,
        token=payload.token,
        token_type=SecurityTokenType.EMAIL_CHANGE,
    )

    if not record.target_email:
        raise BadRequestError("Invalid or expired token")

    user = await get_user_by_id(db, record.user_id)
    if not user:
        raise BadRequestError("Invalid or expired token")

    existing_user = await get_user_by_email(db, record.target_email)
    if existing_user and existing_user.id != user.id:
        raise ConflictError("Email already registered")

    user.email = record.target_email
    user.email_verified_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


# --- API key management -----------------------------------------------------


def _hash_api_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _generate_api_key_plaintext() -> str:
    return f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"


async def create_api_key(
    db: AsyncSession,
    *,
    user_id: int,
    name: str,
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    """Create a new API key. Returns (record, plaintext)."""
    plaintext = _generate_api_key_plaintext()
    record = ApiKey(
        id=str(uuid4()),
        user_id=user_id,
        name=name,
        prefix=plaintext[:API_KEY_PREFIX_LENGTH],
        key_hash=_hash_api_key(plaintext),
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


# Throttle window for last_used_at writes. UI shows relative time ("2h ago"),
# so minute-grain accuracy is plenty.
_API_KEY_LAST_USED_THROTTLE_SECONDS = 60
_API_KEY_LAST_USED_REDIS_KEY = "jobpilot:api_key_last_used:"

# Per-process fallback when Redis is unreachable. Bounded to avoid unbounded
# growth from forgotten or revoked keys still cached in memory.
_API_KEY_LAST_USED_LOCAL_CAP = 10_000
_api_key_last_used_local: dict[str, datetime] = {}
_api_key_last_used_lock = Lock()
_logger = logging.getLogger(__name__)


async def _should_persist_api_key_last_used(api_key_id: str) -> bool:
    """Return True if last_used_at should be flushed to the DB right now.

    Redis SET NX EX gives a single-roundtrip cross-process throttle; if Redis
    is unreachable, fall back to a per-process bounded map so we still skip
    redundant writes within one worker.
    """
    try:
        redis = FastAPICache.get_backend().redis  # type: ignore[attr-defined]
        won = await redis.set(
            f"{_API_KEY_LAST_USED_REDIS_KEY}{api_key_id}",
            b"1",
            nx=True,
            ex=_API_KEY_LAST_USED_THROTTLE_SECONDS,
        )
        return bool(won)
    except Exception as exc:
        _logger.debug("api_key last_used redis throttle unavailable: %s", exc)
        return _local_should_persist_api_key_last_used(api_key_id)


def _local_should_persist_api_key_last_used(api_key_id: str) -> bool:
    now = datetime.now(timezone.utc)
    with _api_key_last_used_lock:
        previous = _api_key_last_used_local.get(api_key_id)
        if previous and (now - previous).total_seconds() < _API_KEY_LAST_USED_THROTTLE_SECONDS:
            return False
        if (
            len(_api_key_last_used_local) >= _API_KEY_LAST_USED_LOCAL_CAP
            and api_key_id not in _api_key_last_used_local
        ):
            oldest_key = min(_api_key_last_used_local, key=_api_key_last_used_local.get)
            _api_key_last_used_local.pop(oldest_key, None)
        _api_key_last_used_local[api_key_id] = now
        return True


async def verify_api_key(db: AsyncSession, plaintext: str) -> ApiKey:
    """Validate an API key. Raises UnauthorizedError on any failure.

    last_used_at is throttled (see _should_persist_api_key_last_used) so a
    single key under sustained load only writes the column at most once per
    minute across the whole fleet.
    """
    if not plaintext.startswith(API_KEY_PREFIX):
        raise UnauthorizedError("Invalid credentials")

    prefix = plaintext[:API_KEY_PREFIX_LENGTH]
    key_hash = _hash_api_key(plaintext)
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

    if await _should_persist_api_key_last_used(record.id):
        await db.execute(
            update(ApiKey).where(ApiKey.id == record.id).values(last_used_at=now)
        )
        await db.commit()

    return record
