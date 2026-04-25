"""API v1 router - aggregates all module routers"""
from fastapi import APIRouter

from app.core.custom_route import CustomAPIRoute

# Import module routers
from app.modules.admin.router import router as admin_router
from app.modules.api_keys.router import router as api_keys_router
from app.modules.auth.router import router as auth_router
from app.modules.jobs.router import router as jobs_router
from app.modules.resumes.router import router as resumes_router
from app.modules.applications.router import router as applications_router
from app.modules.workflow.router import router as workflow_router
from app.modules.users.router import router as users_router
from app.modules.users.profile_router import router as user_profile_router

# Create main API router with custom route class
api_router = APIRouter(route_class=CustomAPIRoute)

# Include module routers
api_router.include_router(admin_router)
api_router.include_router(auth_router)
api_router.include_router(jobs_router)
api_router.include_router(resumes_router)
api_router.include_router(applications_router)
api_router.include_router(workflow_router)
api_router.include_router(users_router)
api_router.include_router(user_profile_router)
api_router.include_router(api_keys_router)
