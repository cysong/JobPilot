"""Admin dependencies (role checks)."""
from fastapi import Depends

from app.core.exceptions import ForbiddenError
from app.core.security import require_jwt_only
from app.modules.auth.models import User
from app.shared.enums import Role


async def require_admin(current_user: User = Depends(require_jwt_only)) -> User:
    """Ensure the current user has ADMIN role."""
    if current_user.role != Role.ADMIN:
        raise ForbiddenError("Admin access required")
    return current_user
