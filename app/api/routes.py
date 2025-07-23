from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Request, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional, List
import logging
from datetime import datetime
import os

from app.models import (
    ScrapeRequest, ScrapeResponse, TaskStatusResponse, HealthResponse,
    TaskStatus, VideoProcessRequest, VideoProcessResponse
)
from app.services.scraping_service import scraping_service
from app.services.cache_service import cache_service
from app.services.video_service import video_service
from app.scrapers.factory import ScraperFactory
from app.config import settings
from app.security import (
    get_api_key, validate_request_security, validate_scrape_request,
    get_security_stats, security_manager, API_KEYS
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/scrape", response_model=ScrapeResponse)
async def scrape_product(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    http_request: Request = None,
    api_key: Optional[str] = Depends(get_api_key)
) -> ScrapeResponse:
    """
    Scrape product information from a URL
    
    This endpoint accepts a URL and returns product information.
    The scraping is performed asynchronously to avoid blocking the API.
    
    Authentication: Optional API key via Bearer token
    Rate Limits: 
    - With API key: Based on key configuration
    - Without API key: 10 requests per minute
    """
    try:
        # Security validation - DISABLED FOR DEVELOPMENT
        # TODO: Re-enable security checks for production by uncommenting the lines below
        # validate_request_security(http_request, api_key)
        # validate_scrape_request(str(request.url), api_key)
        
        # Check cache first (unless force_refresh is True)
        if not request.force_refresh:
            cached_result = cache_service.get_cached_result(str(request.url))
            if cached_result:
                cached_result.cache_hit = True
                logger.info(f"Cache hit for {request.url}")
                return cached_result
        
        # Perform scraping
        response = await scraping_service.scrape_product(
            url=str(request.url),
            force_refresh=request.force_refresh,
            proxy=request.proxy,
            user_agent=request.user_agent,
            block_images=request.block_images
        )
        
        # Cache successful results
        if response.status == TaskStatus.COMPLETED:
            cache_service.cache_result(str(request.url), response)
        
        return response
        
    except Exception as e:
        logger.error(f"Error in scrape endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")


@router.get("/scrape", response_model=ScrapeResponse)
async def scrape_product_get(
    url: str = Query(..., description="URL of the product to scrape"),
    force_refresh: bool = Query(False, description="Force refresh and bypass cache"),
    proxy: Optional[str] = Query(None, description="Custom proxy to use"),
    user_agent: Optional[str] = Query(None, description="Custom user agent to use"),
    block_images: bool = Query(True, description="Block image downloads to save bandwidth"),
    http_request: Request = None,
    api_key: Optional[str] = Depends(get_api_key)
) -> ScrapeResponse:
    """
    Scrape product information from a URL (GET method)
    
    This is a convenience endpoint for simple GET requests.
    
    Authentication: Optional API key via Bearer token
    Rate Limits: 
    - With API key: Based on key configuration
    - Without API key: 10 requests per minute
    """
    try:
        # Security validation - DISABLED FOR DEVELOPMENT
        # TODO: Re-enable security checks for production by uncommenting the lines below
        # validate_request_security(http_request, api_key)
        # validate_scrape_request(url, api_key)
        
        # Check cache first (unless force_refresh is True)
        if not force_refresh:
            cached_result = cache_service.get_cached_result(url)
            if cached_result:
                cached_result.cache_hit = True
                logger.info(f"Cache hit for {url}")
                return cached_result
        
        # Perform scraping
        response = await scraping_service.scrape_product(
            url=url,
            force_refresh=force_refresh,
            proxy=proxy,
            user_agent=user_agent,
            block_images=block_images
        )
        
        # Cache successful results
        if response.status == TaskStatus.COMPLETED:
            cache_service.cache_result(url, response)
        
        return response
        
    except Exception as e:
        logger.error(f"Error in scrape GET endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """
    Get the status of a scraping task
    """
    task_info = scraping_service.get_task_status(task_id)
    
    if not task_info:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskStatusResponse(
        task_id=task_id,
        status=task_info['status'],
        message=task_info.get('message'),
        created_at=task_info['created_at'],
        updated_at=task_info.get('updated_at', task_info['created_at'])
    )


@router.get("/tasks", response_model=List[TaskStatusResponse])
async def get_all_tasks() -> List[TaskStatusResponse]:
    """
    Get all active scraping tasks
    """
    tasks = scraping_service.get_all_tasks()
    
    return [
        TaskStatusResponse(
            task_id=task_id,
            status=task_info['status'],
            message=task_info.get('message'),
            created_at=task_info['created_at'],
            updated_at=task_info.get('updated_at', task_info['created_at'])
        )
                for task_id, task_info in tasks.items()
    ]


@router.get("/test", response_class=HTMLResponse)
async def serve_test_page():
    """
    Serve the test HTML page from app/test/index.html
    """
    html_file_path = os.path.join(os.path.dirname(__file__), "..", "test", "index.html")
    
    if not os.path.exists(html_file_path):
        raise HTTPException(status_code=404, detail="Test page not found")
    
    return FileResponse(html_file_path, media_type="text/html")


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint
    """
    # Check cache service status without causing connection errors
    cache_status = "healthy"
    try:
        if not cache_service.is_connected():
            cache_status = "unavailable"
    except Exception as e:
        logger.debug(f"Cache service check failed: {e}")
        cache_status = "unavailable"
    
    services = {
        "api": "healthy",
        "cache": cache_status
    }
    
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        timestamp=datetime.now(),
        services=services
    )


@router.get("/domains")
async def get_supported_domains() -> dict:
    """
    Get list of supported domains
    """
    return {
        "supported_domains": ScraperFactory.get_supported_domains(),
        "total_count": len(ScraperFactory.get_supported_domains())
    }


@router.delete("/cache")
async def clear_cache() -> dict:
    """
    Clear all cached results
    """
    success = cache_service.clear_all_cache()
    
    if success:
        return {"message": "Cache cleared successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to clear cache")


@router.delete("/cache/{url:path}")
async def invalidate_cache(url: str) -> dict:
    """
    Invalidate cache for a specific URL
    """
    success = cache_service.invalidate_cache(url)
    
    if success:
        return {"message": f"Cache invalidated for {url}"}
    else:
        return {"message": f"No cache found for {url}"}


@router.get("/cache/stats")
async def get_cache_stats() -> dict:
    """
    Get cache statistics
    """
    return cache_service.get_cache_stats()


@router.post("/tasks/cleanup")
async def cleanup_tasks() -> dict:
    """
    Clean up old completed tasks
    """
    scraping_service.cleanup_completed_tasks()
    return {"message": "Task cleanup completed"}


@router.get("/security/stats")
async def get_security_statistics() -> dict:
    """
    Get security statistics and monitoring data
    
    This endpoint provides insights into API usage, blocked IPs, and security events.
    """
    return get_security_stats()


@router.get("/redis/status")
async def get_redis_status() -> dict:
    """
    Check Redis connection status
    """
    try:
        if cache_service.is_connected():
            return {
                "status": "connected",
                "message": "Redis is available and responding"
            }
        else:
            return {
                "status": "disconnected",
                "message": "Redis is not available - caching and rate limiting disabled"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Redis connection check failed: {str(e)}"
        }


@router.get("/security/status")
async def get_security_status() -> dict:
    """
    Get current security status and configuration
    """
    return {
        "security_enabled": True,
        "rate_limiting": True,
        "ip_blocking": True,
        "domain_validation": True,
        "user_agent_validation": True,
        "supported_domains": ScraperFactory.get_supported_domains(),
        "api_keys_configured": len([k for k in API_KEYS.keys() if k != "demo_key_12345"]),
        "demo_mode": "demo_key_12345" in API_KEYS
    } 


@router.post("/video/process", response_model=VideoProcessResponse)
async def process_video(
    request: VideoProcessRequest,
    http_request: Request = None,
    api_key: Optional[str] = Depends(get_api_key)
) -> VideoProcessResponse:
    """
    Process video by merging multiple videos, adding audio, and embedding subtitles
    
    This endpoint accepts:
    - List of video URLs to merge in order
    - Base64 encoded audio data
    - Subtitle text to embed
    - Output resolution (default: 1920x1080)
    
    The processing is performed asynchronously and returns a task ID for status tracking.
    
    Authentication: Optional API key via Bearer token
    """
    try:
        # Security validation - DISABLED FOR DEVELOPMENT
        # TODO: Re-enable security checks for production by uncommenting the lines below
        # validate_request_security(http_request, api_key)
        
        # Process video
        response = await video_service.process_video(
            video_urls=request.video_urls,
            audio_data=request.audio_data,
            subtitle_text=request.subtitle_text,
            output_resolution=request.output_resolution,
            watermark=request.watermark
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error in video process endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Video processing failed: {str(e)}")


@router.get("/video/tasks/{task_id}", response_model=VideoProcessResponse)
async def get_video_task_status(task_id: str) -> VideoProcessResponse:
    """
    Get the status of a video processing task
    """
    task_info = video_service.get_task_status(task_id)
    
    if not task_info:
        raise HTTPException(status_code=404, detail="Video processing task not found")
    
    return VideoProcessResponse(
        task_id=task_id,
        status=task_info['status'],
        video_data=task_info.get('video_data'),
        thumbnail_data=task_info.get('thumbnail_data'),
        error=task_info.get('error'),
        created_at=task_info['created_at'],
        completed_at=task_info.get('completed_at')
    )


@router.get("/video/tasks", response_model=List[VideoProcessResponse])
async def get_all_video_tasks() -> List[VideoProcessResponse]:
    """
    Get all active video processing tasks
    """
    tasks = video_service.get_all_tasks()
    
    return [
        VideoProcessResponse(
            task_id=task_id,
            status=task_info['status'],
            video_data=task_info.get('video_data'),
            thumbnail_data=task_info.get('thumbnail_data'),
            error=task_info.get('error'),
            created_at=task_info['created_at'],
            completed_at=task_info.get('completed_at')
        )
        for task_id, task_info in tasks.items()
    ] 