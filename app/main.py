import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import time
import json
import os
from contextlib import asynccontextmanager

from app.config import settings
from app.api.routes import router
from app.services.cache_service import cache_service
from app.services.scraping_service import scraping_service
from app.security import security_middleware, cleanup_security_data
from app.logging_config import setup_logging, get_logger

# Setup comprehensive logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting E-commerce Scraper API...")
    
    # Test cache connection
    if cache_service.is_connected():
        logger.info("Cache service connected successfully")
    else:
        logger.warning("Cache service not available - caching will be disabled")
    
    # Clean up old security data on startup
    cleanup_security_data()
    
    yield
    
    # Shutdown
    logger.info("Shutting down E-commerce Scraper API...")


# Create FastAPI app with custom JSON encoder
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="A high-performance API for scraping product information from e-commerce websites",
    docs_url=None,
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configure JSON responses to not escape Unicode characters
@app.middleware("http")
async def json_unicode_middleware(request: Request, call_next):
    """Middleware to handle Unicode characters in JSON responses"""
    response = await call_next(request)
    
    # If it's a JSON response, ensure Unicode characters are not escaped
    if hasattr(response, 'body') and response.headers.get('content-type', '').startswith('application/json'):
        try:
            # Parse the JSON response
            data = json.loads(response.body.decode('utf-8'))
            # Re-encode with ensure_ascii=False to preserve Unicode characters
            response.body = json.dumps(data, ensure_ascii=False, default=str).encode('utf-8')
        except:
            pass
    
    return response

# Add security middleware first
app.middleware("http")(security_middleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure this properly for production
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time header to responses"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests"""
    start_time = time.time()
    
    # Log request
    logger.info(f"Request: {request.method} {request.url}")
    
    response = await call_next(request)
    
    # Log response
    process_time = time.time() - start_time
    logger.info(f"Response: {response.status_code} - {process_time:.3f}s")
    
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Include API routes
app.include_router(router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "E-commerce Scraper API",
        "version": settings.VERSION,
        "health": f"{settings.API_V1_STR}/health"
    }

@app.get("/ping")
async def ping():
    """Simple ping endpoint"""
    return {"message": "pong"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    ) 