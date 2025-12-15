"""API v1 router - aggregates all module routers"""
from fastapi import APIRouter

from app.core.custom_route import CustomAPIRoute

# Import module routers
from app.modules.auth.router import router as auth_router
from app.modules.jobs.router import router as jobs_router
from app.modules.resumes.router import router as resumes_router
from app.modules.applications.router import router as applications_router

# Create main API router with custom route class
api_router = APIRouter(route_class=CustomAPIRoute)

# Include module routers
api_router.include_router(auth_router)
api_router.include_router(jobs_router)
api_router.include_router(resumes_router)
api_router.include_router(applications_router)
