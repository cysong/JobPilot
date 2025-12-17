"""Admin dependencies (role checks)."""
from fastapi import Depends, HTTPException, status

from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.shared.enums import Role


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Ensure the current user has ADMIN role."""
    if current_user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
