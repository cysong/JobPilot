"""API v1 router - aggregates all module routers"""
from fastapi import APIRouter

# Import module routers
from app.modules.auth.router import router as auth_router
from app.modules.jobs.router import router as jobs_router

# Create main API router
api_router = APIRouter()

# Include module routers
api_router.include_router(auth_router)
api_router.include_router(jobs_router)
