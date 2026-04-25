"""Authentication API endpoints"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import create_access_token, get_current_user, require_jwt_only
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    MessageResponse,
    ResetPasswordRequest,
    Token,
    UserLogin,
    UserRegister,
    UserResponse,
    VerifyTokenRequest,
)
from app.modules.auth.service import (
    authenticate_user,
    change_password,
    confirm_email_change,
    create_user,
    forgot_password,
    request_email_change,
    resend_verification_email,
    reset_password,
    verify_email,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    user = await create_user(db, user_data)
    return user


@router.post("/login", response_model=Token)
async def login(login_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate user and return JWT token."""
    user = await authenticate_user(db, email=login_data.email, password=login_data.password)

    if not user:
        raise UnauthorizedError("Incorrect email or password")

    if not user.is_active:
        raise ForbiddenError("Inactive user account")

    access_token = create_access_token(data={"sub": user.email})

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current authenticated user information."""
    return current_user


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password_route(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Request password reset instructions."""
    await forgot_password(db, payload)
    return MessageResponse(
        message="If an account exists, we have sent password reset instructions."
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password_route(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reset password with a one-time token."""
    await reset_password(db, payload)
    return MessageResponse(message="Password has been reset successfully.")


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email_route(
    payload: VerifyTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify email with a one-time token."""
    await verify_email(db, payload)
    return MessageResponse(message="Email verified successfully.")


@router.post("/resend-verification-email", response_model=MessageResponse)
async def resend_verification_email_route(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_jwt_only),
):
    """Re-send the email verification message."""
    await resend_verification_email(db, current_user)
    if current_user.email_verified_at:
        return MessageResponse(message="Email is already verified.")
    return MessageResponse(message="Verification email sent.")


@router.post("/change-password", response_model=MessageResponse)
async def change_password_route(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_jwt_only),
):
    """Change password for the authenticated user."""
    await change_password(db, current_user, payload)
    return MessageResponse(message="Password changed successfully.")


@router.post("/change-email/request", response_model=MessageResponse)
async def change_email_request_route(
    payload: ChangeEmailRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_jwt_only),
):
    """Request a change of the current email address."""
    await request_email_change(db, current_user, payload)
    return MessageResponse(message="Email change confirmation sent.")


@router.post("/change-email/confirm", response_model=MessageResponse)
async def change_email_confirm_route(
    payload: VerifyTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Confirm a pending email-change request."""
    await confirm_email_change(db, payload)
    return MessageResponse(message="Email changed successfully.")
