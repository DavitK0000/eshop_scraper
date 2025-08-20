from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional, List
from datetime import datetime
import os

from app.models import (
    ScrapeRequest, ScrapeResponse, TaskStatusResponse, HealthResponse,
    TaskStatus, VideoProcessRequest, VideoProcessResponse
)
from app.services.scraping_service import scraping_service
from app.services.cache_service import cache_service
from app.services.video_service import VideoProcessingService
from app.config import settings
from app.security import (
    get_api_key, validate_request_security, validate_scrape_request,
    get_security_stats, security_manager, API_KEYS
)
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Initialize video processing service
video_service = VideoProcessingService()


@router.post("/scrape", response_model=ScrapeResponse)
def scrape_product(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    http_request: Request = None,
    api_key: Optional[str] = Depends(get_api_key)
) -> ScrapeResponse:
    """
    Scrape product information from a URL
    
    This endpoint accepts a URL and starts scraping asynchronously using threads.
    Returns immediately with a task ID for polling.
    
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
        
        # Start scraping using threads (no need for background tasks with threading)
        response = scraping_service.start_scraping_task(
            url=str(request.url),
            force_refresh=request.force_refresh,
            proxy=request.proxy,
            user_agent=request.user_agent,
            block_images=request.block_images,
            target_language=request.target_language
        )
        
        logger.info(f"Started scraping task {response.task_id} for {request.url}")
        
        return response
        
    except Exception as e:
        logger.error(f"Error in scrape endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")


@router.get("/tasks/{task_id}", response_model=ScrapeResponse)
def get_task_status(task_id: str) -> ScrapeResponse:
    """
    Get the status of a scraping task. Returns full ScrapeResponse when completed.
    """
    task_info = scraping_service.get_task_status(task_id)
    
    if not task_info:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task_info['response']


@router.get("/tasks", response_model=List[TaskStatusResponse])
def get_all_tasks() -> List[TaskStatusResponse]:
    """
    Get all active scraping tasks
    """
    try:
        tasks = scraping_service.get_all_tasks()
        task_responses = []
        
        for task_id, task_info in tasks.items():
            task_response = TaskStatusResponse(
                task_id=task_id,
                status=task_info['status'],
                url=task_info['url'],
                created_at=task_info['created_at'],
                updated_at=task_info.get('updated_at'),
                message=task_info.get('message', ''),
                has_product_info=bool(task_info.get('product_info')),
                platform=task_info.get('platform'),
                platform_confidence=task_info.get('platform_confidence'),
                target_language=task_info.get('target_language')
            )
            task_responses.append(task_response)
        
        return task_responses
        
    except Exception as e:
        logger.error(f"Error getting all tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get tasks: {str(e)}")


@router.get("/test", response_class=HTMLResponse)
def serve_test_page():
    """
    Serve a simple test page for testing the scraper
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>E-commerce Scraper Test</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 800px; margin: 0 auto; }
            .form-group { margin-bottom: 20px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input[type="text"], input[type="url"] { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
            button { background-color: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
            button:hover { background-color: #0056b3; }
            .result { margin-top: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 4px; background-color: #f9f9f9; }
            .loading { color: #666; font-style: italic; }
            .error { color: #dc3545; }
            .success { color: #28a745; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>E-commerce Scraper Test</h1>
            <p>Enter a product URL to test the scraper:</p>
            
            <form id="scrapeForm">
                <div class="form-group">
                    <label for="url">Product URL:</label>
                    <input type="url" id="url" name="url" required placeholder="https://example.com/product">
                </div>
                
                <div class="form-group">
                    <label for="proxy">Proxy (optional):</label>
                    <input type="text" id="proxy" name="proxy" placeholder="http://user:pass@host:port">
                </div>
                
                <div class="form-group">
                    <label for="userAgent">User Agent (optional):</label>
                    <input type="text" id="userAgent" name="userAgent" placeholder="Custom user agent string">
                </div>
                
                <div class="form-group">
                    <label for="targetLanguage">Target Language (optional):</label>
                    <input type="text" id="targetLanguage" name="targetLanguage" placeholder="en, es, fr, de, etc.">
                </div>
                
                <div class="form-group">
                    <label>
                        <input type="checkbox" id="blockImages" name="blockImages" checked>
                        Block images for faster scraping
                    </label>
                </div>
                
                <div class="form-group">
                    <label>
                        <input type="checkbox" id="forceRefresh" name="forceRefresh">
                        Force refresh (bypass cache)
                    </label>
                </div>
                
                <button type="submit">Start Scraping</button>
            </form>
            
            <div id="result" class="result" style="display: none;">
                <h3>Scraping Result:</h3>
                <div id="resultContent"></div>
            </div>
        </div>

        <script>
            document.getElementById('scrapeForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                
                const url = document.getElementById('url').value;
                const proxy = document.getElementById('proxy').value;
                const userAgent = document.getElementById('userAgent').value;
                const targetLanguage = document.getElementById('targetLanguage').value;
                const blockImages = document.getElementById('blockImages').checked;
                const forceRefresh = document.getElementById('forceRefresh').checked;
                
                const resultDiv = document.getElementById('result');
                const resultContent = document.getElementById('resultContent');
                
                resultDiv.style.display = 'block';
                resultContent.innerHTML = '<div class="loading">Starting scraping...</div>';
                
                try {
                    // Start scraping
                    const response = await fetch('/api/v1/scrape', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            url: url,
                            proxy: proxy || null,
                            user_agent: userAgent || null,
                            target_language: targetLanguage || null,
                            block_images: blockImages,
                            force_refresh: forceRefresh
                        })
                    });
                    
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    
                    const data = await response.json();
                    
                    if (data.status === 'PENDING') {
                        resultContent.innerHTML = `
                            <div class="success">
                                <p><strong>Task started successfully!</strong></p>
                                <p>Task ID: ${data.task_id}</p>
                                <p>Status: ${data.status}</p>
                                <p>Message: ${data.message}</p>
                                <p>Polling for results...</p>
                            </div>
                        `;
                        
                        // Poll for results
                        pollForResults(data.task_id, resultContent);
                    } else {
                        resultContent.innerHTML = `
                            <div class="success">
                                <p><strong>Scraping completed!</strong></p>
                                <p>Task ID: ${data.task_id}</p>
                                <p>Status: ${data.status}</p>
                                <p>Message: ${data.message}</p>
                                ${data.product_info ? '<p>Product information extracted successfully!</p>' : ''}
                            </div>
                        `;
                    }
                    
                } catch (error) {
                    resultContent.innerHTML = `<div class="error">Error: ${error.message}</div>`;
                }
            });
            
            async function pollForResults(taskId, resultContent) {
                const maxAttempts = 60; // 5 minutes with 5-second intervals
                let attempts = 0;
                
                const poll = async () => {
                    try {
                        const response = await fetch(`/api/v1/tasks/${taskId}`);
                        
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        
                        const data = await response.json();
                        
                        if (data.status === 'COMPLETED') {
                            resultContent.innerHTML = `
                                <div class="success">
                                    <p><strong>Scraping completed successfully!</strong></p>
                                    <p>Task ID: ${data.task_id}</p>
                                    <p>Status: ${data.status}</p>
                                    <p>Message: ${data.message}</p>
                                    <p>Platform: ${data.detected_platform || 'Unknown'}</p>
                                    <p>Platform Confidence: ${data.platform_confidence ? (data.platform_confidence * 100).toFixed(1) + '%' : 'Unknown'}</p>
                                    ${data.product_info ? '<p>Product information extracted successfully!</p>' : ''}
                                </div>
                            `;
                            return;
                        } else if (data.status === 'FAILED') {
                            resultContent.innerHTML = `
                                <div class="error">
                                    <p><strong>Scraping failed!</strong></p>
                                    <p>Task ID: ${data.task_id}</p>
                                    <p>Status: ${data.status}</p>
                                    <p>Error: ${data.error || data.message}</p>
                                </div>
                            `;
                            return;
                        } else if (data.status === 'RUNNING') {
                            resultContent.innerHTML = `
                                <div class="loading">
                                    <p><strong>Scraping in progress...</strong></p>
                                    <p>Task ID: ${data.task_id}</p>
                                    <p>Status: ${data.status}</p>
                                    <p>Message: ${data.message}</p>
                                    <p>Polling for results... (Attempt ${attempts + 1}/${maxAttempts})</p>
                                </div>
                            `;
                        }
                        
                        attempts++;
                        if (attempts < maxAttempts) {
                            setTimeout(poll, 5000); // Poll every 5 seconds
                        } else {
                            resultContent.innerHTML = `
                                <div class="error">
                                    <p><strong>Polling timeout!</strong></p>
                                    <p>Task ID: ${taskId}</p>
                                    <p>Status: ${data.status}</p>
                                    <p>Message: Maximum polling attempts reached. Check task status manually.</p>
                                </div>
                            `;
                        }
                        
                    } catch (error) {
                        resultContent.innerHTML = `<div class="error">Error polling for results: ${error.message}</div>`;
                    }
                };
                
                poll();
            }
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)


@router.get("/health", response_model=HealthResponse)
def health_check():
    """
    Health check endpoint
    """
    try:
        # Get security stats
        security_stats = get_security_stats()
        
        # Get task stats
        all_tasks = scraping_service.get_all_tasks()
        task_stats = {
            'total_tasks': len(all_tasks),
            'pending_tasks': len([t for t in all_tasks.values() if t['status'] == TaskStatus.PENDING]),
            'running_tasks': len([t for t in all_tasks.values() if t['status'] == TaskStatus.RUNNING]),
            'completed_tasks': len([t for t in all_tasks.values() if t['status'] == TaskStatus.COMPLETED]),
            'failed_tasks': len([t for t in all_tasks.values() if t['status'] == TaskStatus.FAILED])
        }
        
        # Get cache stats
        cache_stats = cache_service.get_stats()
        
        health_response = HealthResponse(
            status="healthy",
            timestamp=datetime.now(),
            version=settings.VERSION,
            uptime=0,  # TODO: Implement uptime tracking
            memory_usage=0,  # TODO: Implement memory usage tracking
            security_stats=security_stats,
            task_stats=task_stats,
            cache_stats=cache_stats
        )
        
        return health_response
        
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/stats")
def get_stats():
    """
    Get detailed statistics about the scraper
    """
    try:
        # Get all available stats
        all_tasks = scraping_service.get_all_tasks()
        cache_stats = cache_service.get_stats()
        security_stats = get_security_stats()
        
        stats = {
            'tasks': {
                'total': len(all_tasks),
                'by_status': {}
            },
            'cache': cache_stats,
            'security': security_stats,
            'timestamp': datetime.now().isoformat()
        }
        
        # Count tasks by status
        for task in all_tasks.values():
            status = task['status'].value if hasattr(task['status'], 'value') else str(task['status'])
            if status not in stats['tasks']['by_status']:
                stats['tasks']['by_status'][status] = 0
            stats['tasks']['by_status'][status] += 1
        
        return JSONResponse(content=stats)
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.delete("/tasks/{task_id}")
def cancel_task(task_id: str):
    """
    Cancel a running task
    """
    try:
        task_info = scraping_service.get_task_status(task_id)
        
        if not task_info:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task_info['status'] not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            raise HTTPException(status_code=400, detail="Cannot cancel completed or failed task")
        
        # Update task status to cancelled
        scraping_service._update_task_status(task_id, TaskStatus.FAILED, "Task cancelled by user")
        
        return {"message": f"Task {task_id} cancelled successfully"}
        
    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cancel task: {str(e)}")


@router.delete("/tasks")
def cleanup_tasks():
    """
    Clean up old completed/failed tasks
    """
    try:
        scraping_service.cleanup_completed_tasks()
        return {"message": "Task cleanup completed"}
        
    except Exception as e:
        logger.error(f"Error cleaning up tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cleanup tasks: {str(e)}")


# ============================================================================
# Video Processing Endpoints
# ============================================================================

@router.post("/video/process", response_model=VideoProcessResponse)
def process_video(
    request: VideoProcessRequest,
    api_key: Optional[str] = Depends(get_api_key)
) -> VideoProcessResponse:
    """
    Process video by merging multiple videos, adding audio, and embedding subtitles.
    
    This endpoint accepts video URLs, audio data, and optional subtitle text.
    Returns immediately with a task ID for polling.
    
    Authentication: Optional API key via Bearer token
    """
    try:
        # Security validation - DISABLED FOR DEVELOPMENT
        # TODO: Re-enable security checks for production
        # validate_request_security(http_request, api_key)
        
        logger.info(f"Starting video processing task with {len(request.video_urls)} videos")
        
        response = video_service.process_video(
            video_urls=request.video_urls,
            audio_data=request.audio_data,
            subtitle_text=request.subtitle_text,
            output_resolution=request.output_resolution,
            watermark=request.watermark
        )
        
        logger.info(f"Started video processing task {response.task_id}")
        
        return response
        
    except Exception as e:
        logger.error(f"Error in video processing endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Video processing failed: {str(e)}")


@router.get("/video/tasks/{task_id}", response_model=VideoProcessResponse)
def get_video_task_status(task_id: str) -> VideoProcessResponse:
    """
    Get the status of a video processing task.
    Returns full VideoProcessResponse when completed.
    """
    try:
        task_info = video_service.get_task_status(task_id)
        
        if not task_info:
            raise HTTPException(status_code=404, detail="Video task not found")
        
        # Convert task info to VideoProcessResponse
        return VideoProcessResponse(
            task_id=task_id,
            status=task_info['status'],
            video_data=task_info.get('video_data'),
            thumbnail_data=task_info.get('thumbnail_data'),
            error=task_info.get('error'),
            created_at=task_info['created_at'],
            completed_at=task_info.get('completed_at')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video task status {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get video task status: {str(e)}")


@router.get("/video/tasks")
def get_all_video_tasks():
    """
    Get all video processing tasks
    """
    try:
        tasks = video_service.get_all_tasks()
        return tasks
        
    except Exception as e:
        logger.error(f"Error getting all video tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get video tasks: {str(e)}")


@router.delete("/video/tasks/{task_id}")
def cancel_video_task(task_id: str):
    """
    Cancel a running video processing task
    """
    try:
        task_info = video_service.get_task_status(task_id)
        
        if not task_info:
            raise HTTPException(status_code=404, detail="Video task not found")
        
        if task_info['status'] not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            raise HTTPException(status_code=400, detail="Cannot cancel completed or failed video task")
        
        # Update task status to cancelled
        video_service._update_task_status(task_id, TaskStatus.FAILED, "Video task cancelled by user")
        
        return {"message": f"Video task {task_id} cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling video task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cancel video task: {str(e)}")


@router.delete("/video/tasks")
def cleanup_video_tasks():
    """
    Clean up old completed/failed video processing tasks
    """
    try:
        video_service.cleanup()
        return {"message": "Video task cleanup completed"}
        
    except Exception as e:
        logger.error(f"Error cleaning up video tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cleanup video tasks: {str(e)}") 