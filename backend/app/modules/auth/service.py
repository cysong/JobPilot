"""Authentication service layer - business logic"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.modules.auth.models import User
from app.modules.auth.schemas import UserRegister
from app.core.security import hash_password, verify_password
from app.core.config import settings
from app.shared.enums import Role


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Get user by email address

    Args:
        db: Database session
        email: User email address

    Returns:
        User object if found, None otherwise
    """
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """Get user by ID

    Args:
        db: Database session
        user_id: User ID

    Returns:
        User object if found, None otherwise
    """
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user_data: UserRegister) -> User:
    """Create a new user account

    Args:
        db: Database session
        user_data: User registration data

    Returns:
        Created user object

    Raises:
        HTTPException: If email already exists
    """
    # Check if email already exists
    existing_user = await get_user_by_email(db, email=user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create new user
    db_user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        role=Role(settings.DEFAULT_USER_ROLE),  # Use default role from config
        is_active=True
    )

    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    return db_user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    """Authenticate user with email and password

    Args:
        db: Database session
        email: User email address
        password: Plain text password

    Returns:
        User object if authentication successful, None otherwise
    """
    user = await get_user_by_email(db, email=email)

    if not user:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user
