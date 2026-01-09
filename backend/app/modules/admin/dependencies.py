"""Admin dependencies (role checks)."""
from fastapi import Depends

from app.core.exceptions import ForbiddenError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.shared.enums import Role


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Ensure the current user has ADMIN role."""
    if current_user.role != Role.ADMIN:
        raise ForbiddenError("Admin access required")
    return current_user
