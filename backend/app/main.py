"""FastAPI application entry point"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis import asyncio as aioredis

from prometheus_fastapi_instrumentator import Instrumentator

from app import models  # noqa: F401  # Register all ORM models for metadata consistency
from app.api.v1.router import api_router
from app.core.cache import RedisBackend
from app.core.config import settings
from app.core.custom_route import CustomAPIRoute
from app.core.exceptions import JobPilotException
from app.core.logging_config import configure_logging
from app.core.metrics import api_error_total
from app.core.queue_observer import observe_queue_lengths
from app.core.response_codes import ResponseCode
from fastapi_cache import FastAPICache

configure_logging("api")


def _endpoint_label(request: Request) -> str:
    """Resolve the route pattern (e.g. ``/api/v1/jobs/{job_id}``) for metric labels.

    Unmatched paths (404s, middleware errors, bot scans for /.env etc.) collapse
    to the literal "<unresolved>" — without this clamp every probed URL would
    add a new time series and blow up Prometheus memory.
    """
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    return "<unresolved>"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print("JobPilot API is starting up...")
    print(f"Allowed Origins: {settings.CORS_ORIGINS}")

    # Initialize cache
    if settings.CACHE_ENABLED:
        redis = aioredis.from_url(
            settings.REDIS_URL, encoding="utf8", decode_responses=False
        )
        FastAPICache.init(RedisBackend(redis), prefix="jobpilot:cache")
        print("Cache initialized with Redis backend")

    # Start Celery queue-length observer for Prometheus gauge
    queue_observer_task = asyncio.create_task(observe_queue_lengths())

    yield

    # Shutdown
    print("JobPilot API is shutting down...")
    queue_observer_task.cancel()
    try:
        await queue_observer_task
    except asyncio.CancelledError:
        pass


# Create FastAPI application
app = FastAPI(
    title="JobPilot API",
    version="0.1.0",
    description="AI-powered job application assistant",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    # Disable trailing-slash redirects: 307 responses drop Authorization
    # headers in most HTTP clients, breaking API key callers.
    redirect_slashes=False,
)

# Apply custom route class globally (includes health endpoint)
app.router.route_class = CustomAPIRoute

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler for FastAPI HTTPException
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Convert FastAPI HTTPException to unified response format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": exc.detail, "data": None},
    )


# Global exception handler for JobPilot exceptions
@app.exception_handler(JobPilotException)
async def jobpilot_exception_handler(request: Request, exc: JobPilotException):
    api_error_total.labels(
        endpoint=_endpoint_label(request),
        code=str(int(exc.response_code)),
        exception_type=type(exc).__name__,
    ).inc()
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": int(exc.response_code), "message": exc.message, "data": None},
    )


# Fallback exception handler
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    api_error_total.labels(
        endpoint=_endpoint_label(request),
        code=str(int(ResponseCode.INTERNAL_ERROR)),
        exception_type=type(exc).__name__,
    ).inc()
    if settings.ENVIRONMENT == "development":
        import traceback

        debug_data = {
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": int(ResponseCode.INTERNAL_ERROR),
                "message": "Internal server error",
                "data": debug_data,
            },
        )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": int(ResponseCode.INTERNAL_ERROR),
            "message": "Internal server error",
            "data": None,
        },
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
    }


# Prometheus metrics endpoint (/metrics)
# Skipped in development: prometheus_client hangs on Windows with uvicorn's spawn reloader
if settings.ENVIRONMENT != "development":
    Instrumentator().instrument(app).expose(app)

# Include API router
app.include_router(api_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development",
    )
