"""FastAPI application entry point"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.exceptions import JobPilotException
from app.api.v1.router import api_router
from fastapi_cache import FastAPICache
from app.core.cache import RedisBackend
from redis import asyncio as aioredis


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    print("JobPilot API is starting up...")
    print(f"Allowed Origins: {settings.CORS_ORIGINS}")

    # Initialize cache
    if settings.CACHE_ENABLED:
        redis = aioredis.from_url(
            settings.REDIS_URL, encoding="utf8", decode_responses=False)
        FastAPICache.init(RedisBackend(redis), prefix="jobpilot:cache")
        print("Cache initialized with Redis backend")

    yield

    # Shutdown
    print("JobPilot API is shutting down...")


# Create FastAPI application
app = FastAPI(
    title="JobPilot API",
    version="0.1.0",
    description="AI-powered job application assistant",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(JobPilotException)
async def jobpilot_exception_handler(request: Request, exc: JobPilotException):
    """Handle custom JobPilot exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    if settings.ENVIRONMENT == "development":
        # In development, show detailed error
        import traceback
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error",
                "error": str(exc),
                "traceback": traceback.format_exc()
            }
        )
    else:
        # In production, hide details
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"}
        )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT
    }


# Include API router
app.include_router(api_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development"
    )
