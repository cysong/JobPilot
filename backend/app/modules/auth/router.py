"""Authentication API endpoints"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import create_access_token, get_current_user
from app.modules.auth.models import User
from app.modules.auth.schemas import Token, UserLogin, UserRegister, UserResponse
from app.modules.auth.service import authenticate_user, create_user

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
