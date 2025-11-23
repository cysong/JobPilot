"""
Authentication dependencies for FastAPI endpoints.
"""

# Import get_current_user from core.security
# This file exists to provide a clean import path for other modules
from app.core.security import get_current_user

__all__ = ["get_current_user"]
