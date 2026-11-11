"""Admin dependencies (role checks)."""
from fastapi import Depends

from app.core.exceptions import ForbiddenError
from app.core.security import get_current_user, require_jwt_only
from app.modules.auth.models import User
from app.shared.enums import Role


async def require_admin(current_user: User = Depends(require_jwt_only)) -> User:
    """Ensure the current user has ADMIN role."""
    if current_user.role != Role.ADMIN:
        raise ForbiddenError("Admin access required")
    return current_user


def require_admin_scope(scope: str):
    """Admin access from a browser session, or from an admin's API key that carries ``scope``.

    Used for the few admin endpoints automation needs (e.g. submitting match labels);
    every other admin endpoint stays session-only through ``require_admin``.
    """

    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != Role.ADMIN:
            raise ForbiddenError("Admin access required")
        if getattr(current_user, "_auth_method", None) == "api_key" and scope not in (
            getattr(current_user, "_api_key_scopes", None) or []
        ):
            raise ForbiddenError(f"API key lacks the '{scope}' scope")
        return current_user

    return dependency
