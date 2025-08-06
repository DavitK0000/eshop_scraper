from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional, List
import asyncio
from datetime import datetime
import os

from app.models import (
    ScrapeRequest, ScrapeResponse, TaskStatusResponse, HealthResponse,
    TaskStatus
)
from app.services.scraping_service import scraping_service
from app.services.cache_service import cache_service
from app.config import settings
from app.security import (
    get_api_key, validate_request_security, validate_scrape_request,
    get_security_stats, security_manager, API_KEYS
)
from app.logging_config import get_logger

logger = get_logger(__name__)

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
    
    This endpoint accepts a URL and starts scraping asynchronously.
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
        
        # Start scraping asynchronously
        response = await scraping_service.start_scraping_task(
            url=str(request.url),
            force_refresh=request.force_refresh,
            proxy=request.proxy,
            user_agent=request.user_agent,
            block_images=request.block_images
        )
        
        # Add the actual scraping work to background tasks
        logger.info(f"Adding background task for task_id: {response.task_id}")
        background_tasks.add_task(
            scraping_service.execute_scraping_task,
            response.task_id,
            str(request.url),
            request.force_refresh,
            request.proxy,
            request.user_agent,
            request.block_images
        )
        logger.info(f"Background task added for task_id: {response.task_id}")
        
        return response
        
    except Exception as e:
        logger.error(f"Error in scrape endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")


@router.get("/tasks/{task_id}", response_model=ScrapeResponse)
async def get_task_status(task_id: str) -> ScrapeResponse:
    """
    Get the status of a scraping task. Returns full ScrapeResponse when completed.
    """
    task_info = scraping_service.get_task_status(task_id)
    
    if not task_info:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task_info['response']


@router.get("/tasks", response_model=List[TaskStatusResponse])
async def get_all_tasks() -> List[TaskStatusResponse]:
    """
    Get status of all active tasks
    """
    tasks = scraping_service.get_all_tasks()
    return [
        TaskStatusResponse(
            task_id=task_id,
            status=task_info['status'],
            url=task_info['url'],
            created_at=task_info['created_at'],
            updated_at=task_info.get('updated_at', task_info['created_at']),
            message=task_info.get('message', '')
        )
        for task_id, task_info in tasks.items()
    ]


@router.get("/test", response_class=HTMLResponse)
async def serve_test_page():
    """
    Serve a simple test page for manual testing
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>E-commerce Scraper API Test</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 800px; margin: 0 auto; }
            .form-group { margin-bottom: 20px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input[type="text"], input[type="url"] { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
            button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
            button:hover { background: #0056b3; }
            .result { margin-top: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 4px; background: #f9f9f9; }
            .error { color: red; }
            .success { color: green; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>E-commerce Scraper API Test</h1>
            <p>Test the scraping API with a product URL:</p>
            
            <div class="form-group">
                <label for="url">Product URL:</label>
                <input type="url" id="url" placeholder="https://www.amazon.com/dp/B08N5WRWNW" />
            </div>
            
            <div class="form-group">
                <label>
                    <input type="checkbox" id="forceRefresh" />
                    Force Refresh (bypass cache)
                </label>
            </div>
            
            <button onclick="scrapeProduct()">Scrape Product</button>
            
            <div id="result" class="result" style="display: none;"></div>
        </div>
        
        <script>
            async function scrapeProduct() {
                const url = document.getElementById('url').value;
                const forceRefresh = document.getElementById('forceRefresh').checked;
                const resultDiv = document.getElementById('result');
                
                if (!url) {
                    resultDiv.innerHTML = '<span class="error">Please enter a URL</span>';
                    resultDiv.style.display = 'block';
                    return;
                }
                
                resultDiv.innerHTML = 'Scraping in progress...';
                resultDiv.style.display = 'block';
                
                try {
                    const response = await fetch('/api/v1/scrape', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            url: url,
                            force_refresh: forceRefresh
                        })
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok) {
                        resultDiv.innerHTML = `
                            <h3>Task Started</h3>
                            <p><strong>Task ID:</strong> ${data.task_id}</p>
                            <p><strong>Status:</strong> ${data.status}</p>
                            <p><strong>URL:</strong> ${data.url}</p>
                            <p><strong>Created:</strong> ${data.created_at}</p>
                            <p>Use the task ID to poll for results: <code>/api/v1/tasks/${data.task_id}</code></p>
                        `;
                    } else {
                        resultDiv.innerHTML = `<span class="error">Error: ${data.detail}</span>`;
                    }
                } catch (error) {
                    resultDiv.innerHTML = `<span class="error">Request failed: ${error.message}</span>`;
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint
    """
    try:
        # Check cache service
        cache_status = "healthy" if cache_service.is_connected() else "unavailable"
        
        # Check scraping service
        scraping_status = "healthy"
        
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now(),
            version=settings.VERSION,
            services={
                "cache": cache_status,
                "scraping": scraping_status
            }
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.now(),
            version=settings.VERSION,
            services={
                "cache": "error",
                "scraping": "error"
            }
        ) 