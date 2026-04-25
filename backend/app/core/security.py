"""Security utilities for authentication and authorization"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAYS)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT access token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise UnauthorizedError("Could not validate credentials")


async def _resolve_jwt_user(db: AsyncSession, token: str):
    """Resolve a User from a JWT bearer token."""
    from app.modules.auth.service import get_user_by_email

    payload = decode_access_token(token)
    email: str = payload.get("sub")
    if email is None:
        raise UnauthorizedError("Could not validate credentials")

    user = await get_user_by_email(db, email=email)
    if user is None:
        raise UnauthorizedError("User not found")
    if not user.is_active:
        raise ForbiddenError("Inactive user account")
    return user


async def _resolve_api_key_user(db: AsyncSession, token: str):
    """Resolve a User from an API key bearer token."""
    from app.modules.api_keys.service import verify_api_key
    from app.modules.auth.service import get_user_by_id

    record = await verify_api_key(db, token)
    user = await get_user_by_id(db, user_id=record.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Invalid credentials")
    return user, record


def _is_api_key(token: str) -> bool:
    from app.modules.api_keys.models import API_KEY_PREFIX

    return token.startswith(API_KEY_PREFIX)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """Resolve the current user from either a JWT or an API key bearer token."""
    if not credentials or not credentials.credentials:
        raise UnauthorizedError("Authorization header missing or invalid")

    token = credentials.credentials
    if _is_api_key(token):
        user, record = await _resolve_api_key_user(db, token)
        # Stash auth metadata on the user object for downstream consumers
        # (logging, future scope checks, per-key rate limiting).
        user._auth_method = "api_key"
        user._api_key_id = record.id
        user._api_key_scopes = list(record.scopes or [])
        return user

    user = await _resolve_jwt_user(db, token)
    user._auth_method = "jwt"
    user._api_key_id = None
    user._api_key_scopes = None
    return user


async def require_jwt_only(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """Strict dependency that rejects API key callers — for sensitive endpoints."""
    if not credentials or not credentials.credentials:
        raise UnauthorizedError("Authorization header missing or invalid")

    token = credentials.credentials
    if _is_api_key(token):
        raise UnauthorizedError("This endpoint does not accept API keys")

    user = await _resolve_jwt_user(db, token)
    user._auth_method = "jwt"
    user._api_key_id = None
    user._api_key_scopes = None
    return user
