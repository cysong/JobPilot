"""Authentication and account-security service layer."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, ConflictError, UnauthorizedError
from app.core.security import hash_password, verify_password
from app.modules.auth.email_service import AuthEmailService
from app.modules.auth.models import SecurityTokenType, User
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
