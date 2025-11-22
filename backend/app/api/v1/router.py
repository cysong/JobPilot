"""API v1 router - aggregates all module routers"""
from fastapi import APIRouter

api_router = APIRouter()

# Module routers will be added here in subsequent stages
# Example:
# from app.modules.auth.router import router as auth_router
# api_router.include_router(auth_router)
