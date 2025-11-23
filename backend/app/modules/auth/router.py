"""Authentication API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token, get_current_user
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    UserRegister,
    UserLogin,
    Token,
    UserResponse
)
from app.modules.auth.service import (
    create_user,
    authenticate_user
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user account

    Args:
        user_data: User registration data (email, password, full_name)
        db: Database session

    Returns:
        Created user information

    Raises:
        400 Bad Request: If email already exists
    """
    user = await create_user(db, user_data)
    return user


@router.post("/login", response_model=Token)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user and return JWT token

    Args:
        login_data: User login credentials (email, password)
        db: Database session

    Returns:
        JWT access token

    Raises:
        401 Unauthorized: If credentials are invalid
    """
    user = await authenticate_user(db, email=login_data.email, password=login_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account"
        )

    # Create JWT token with user email as subject
    access_token = create_access_token(data={"sub": user.email})

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current authenticated user information

    Requires valid JWT token in Authorization header

    Args:
        current_user: Current authenticated user (from JWT token)

    Returns:
        Current user information
    """
    return current_user
