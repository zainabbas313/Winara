from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import logging
import time
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
import redis

import uvicorn
import logging
from core.config.config import settings
from routers import auth, users, teams, verticals, bids, receivables, analytics

# Import utilities
from utils.exceptions import AnalyticsError, ValidationError, PermissionError as CustomPermissionError
from utils.rate_limiter import set_rate_limiter
from core.config.config import settings 

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    
    # Startup
    logger.info("Starting analytics application...")
    
    # Initialize Redis connection for rate limiting and caching
    redis_client = None
    if settings.REDIS_URL:
        try:
            redis_client = redis.from_url(settings.REDIS_URL)
            await redis_client.ping()  # Test connection
            set_rate_limiter(redis_client)
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Using in-memory fallback.")
    
    # Create export directory if it doesn't exist
    import os
    os.makedirs(settings.EXPORT_DIRECTORY, exist_ok=True)
    
    logger.info("Analytics application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down analytics application...")
    
    if redis_client:
        await redis_client.close()
    
    logger.info("Analytics application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Centralized Upwork bidding management system with comprehensive analytics and role-based access control"
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure appropriately for production
)


# Custom middleware for request logging and timing
# @app.middleware("http")
# async def log_requests(request: Request, call_next):
#     """Log all requests with timing information."""
#     start_time = time.time()
    
#     # Log request
#     logger.info(f"Request: {request.method} {request.url.path}")
    
#     # Process request
#     response = await call_next(request)
    
#     # Calculate duration
#     duration = (time.time() - start_time) * 1000
    
#     # Log response
#     logger.info(f"Response: {response.status_code} - {duration:.2f}ms")
    
#     # Add timing header
#     response.headers["X-Process-Time"] = str(duration)
    
#     return response


# Global exception handlers
@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Handle validation errors."""
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "error": "Validation Error",
            "message": exc.message,
            "details": exc.details
        }
    )


@app.exception_handler(CustomPermissionError)
async def permission_error_handler(request: Request, exc: CustomPermissionError):
    """Handle permission errors."""
    return JSONResponse(
        status_code=403,
        content={
            "success": False,
            "error": "Permission Denied",
            "message": exc.message,
            "details": exc.details
        }
    )


@app.exception_handler(AnalyticsError)
async def analytics_error_handler(request: Request, exc: AnalyticsError):
    """Handle analytics-specific errors."""
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Analytics Error",
            "message": exc.message,
            "details": exc.details if not settings.SENSITIVE_DATA_MASKING else {}
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": "HTTP Error",
            "message": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal Server Error",
            "message": "An unexpected error occurred" if settings.SENSITIVE_DATA_MASKING else str(exc)
        }
    )



@app.middleware("http")
async def debug_middleware(request: Request, call_next):
    logger.info(f"=== REQUEST DEBUG ===")
    logger.info(f"Method: {request.method}")
    logger.info(f"URL: {request.url}")
    logger.info(f"Path: {request.url.path}")
    logger.info(f"Query params: {dict(request.query_params)}")
    
    try:
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code}")
        return response
    except HTTPException as e:
        logger.error(f"HTTPException in route: {e.detail}")
        logger.error(f"Status code: {e.status_code}")
        raise
    except Exception as e:
        logger.error(f"Unhandled exception in route: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

# API routes
app.include_router(auth.router, prefix=settings.API_V1_STR, tags=["Authentication"])
app.include_router(users.router, prefix=settings.API_V1_STR, tags=["Users"])
app.include_router(teams.router, prefix=settings.API_V1_STR, tags=["Teams"])
app.include_router(verticals.router, prefix=settings.API_V1_STR, tags=["Verticals"])
app.include_router(bids.router, prefix=settings.API_V1_STR, tags=["Bids"])
app.include_router(receivables.router, prefix=settings.API_V1_STR, tags=["Receivables"])
app.include_router(analytics.router, prefix=settings.API_V1_STR, tags=["Analytics"])
# app.mount("/analytics", StaticFiles(directory="exports"), name="analytics_exports")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Application health check."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0",
        "analytics_enabled": True,
        "cache_enabled": settings.CACHE_ENABLED,
        "rate_limiting_enabled": settings.RATE_LIMIT_ENABLED
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to Upwork Bidders Management API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health_url": "/health"
    }

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=5500,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info"
    )