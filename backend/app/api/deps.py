"""Global API dependencies"""
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db

# Re-export for convenience
__all__ = ["get_db"]
