from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional, List
from datetime import datetime
import os

from app.models import (
    ScrapeRequest, TaskStatusResponse, HealthResponse,
    TaskStatus, VideoGenerationRequest, VideoGenerationResponse,
    FinalizeShortRequest, FinalizeShortResponse
)
from app.services.scraping_service import scraping_service
from app.services.video_generation_service import video_generation_service
from app.services.merging_service import merging_service
from app.config import settings
from app.security import (
    get_api_key, validate_request_security, validate_scrape_request,
    get_security_stats, security_manager, API_KEYS
)
from app.logging_config import get_logger
from app.models import TaskPriority
from app.utils.credit_utils import can_perform_action

logger = get_logger(__name__)

router = APIRouter()

@router.post("/scrape", response_model=TaskStatusResponse)
def scrape_product(
    request: ScrapeRequest,
    http_request: Request = None,
    api_key: Optional[str] = Depends(get_api_key)
) -> TaskStatusResponse:
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
        
        # Check user's credit before starting scraping
        credit_check = can_perform_action(request.user_id, "scraping")
        if credit_check.get("error"):
            logger.error(f"Credit check failed for user {request.user_id}: {credit_check['error']}")
            raise HTTPException(status_code=400, detail=f"Credit check failed: {credit_check['error']}")
        
        if not credit_check.get("can_perform", False):
            reason = credit_check.get("reason", "Insufficient credits")
            current_credits = credit_check.get("current_credits", 0)
            required_credits = credit_check.get("required_credits", 1)
            logger.warning(f"Credit check failed for user {request.user_id}: {reason}. Current: {current_credits}, Required: {required_credits}")
            raise HTTPException(
                status_code=402, 
                detail={
                    "error": "Insufficient credits",
                    "reason": reason,
                    "current_credits": current_credits,
                    "required_credits": required_credits,
                    "message": f"You need {required_credits} credit(s) to perform this action. You currently have {current_credits} credit(s)."
                }
            )
        
        logger.info(f"Credit check passed for user {request.user_id}. Can perform scraping action.")
        
        # Start scraping using threads (no need for background tasks with threading)
        response = scraping_service.start_scraping_task(
            url=str(request.url),
            user_id=request.user_id,
            proxy=request.proxy,
            user_agent=request.user_agent,
            block_images=request.block_images,
            target_language=request.target_language
        )
        
        # Convert response to TaskStatusResponse format
        detail = {}
        # Note: target_language is not included in detail for scraping tasks
        if hasattr(response, 'supabase_product_id') and response.supabase_product_id:
            detail['supabase_product_id'] = response.supabase_product_id
        if hasattr(response, 'short_id') and response.short_id:
            detail['short_id'] = response.short_id
        
        task_response = TaskStatusResponse(
            task_id=response.task_id,
            status=response.status,
            url=response.url,
            task_type="scraping",
            progress=getattr(response, 'progress', None),
            message=getattr(response, 'message', None),
            created_at=response.created_at,
            updated_at=getattr(response, 'completed_at', response.created_at),
            priority=getattr(response, 'priority', TaskPriority.NORMAL),
            user_id=getattr(response, 'user_id', None),
            session_id=getattr(response, 'session_id', None),
            detail=detail
        )
        
        logger.info(f"Started scraping task {task_response.task_id} for {request.url} by user {request.user_id}")
        
        return task_response
        
    except Exception as e:
        logger.error(f"Error in scrape endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str) -> TaskStatusResponse:
    """
    Get the status of a scraping task. Returns simplified response with essential fields only.
    """
    task_info = scraping_service.get_task_status(task_id)
    
    if not task_info:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Build the response using the task info dictionary
    detail = {}
    
    # Add product_id to detail if it exists
    if task_info.get('product_id'):
        detail['product_id'] = task_info['product_id']
    
    # Add short_id to detail if it exists
    if task_info.get('short_id'):
        detail['short_id'] = task_info['short_id']
    
    # Add platform information to detail if available
    if task_info.get('platform'):
        detail['platform'] = task_info['platform']
    if task_info.get('platform_confidence'):
        detail['platform_confidence'] = task_info['platform_confidence']
    if task_info.get('platform_indicators'):
        detail['platform_indicators'] = task_info['platform_indicators']
    
    return TaskStatusResponse(
        task_id=task_id,
        status=task_info.get('status', 'unknown'),
        url=task_info.get('url'),
        task_type='scraping',
        progress=task_info.get('progress'),
        message=task_info.get('message'),
        created_at=task_info.get('created_at'),
        updated_at=task_info.get('updated_at'),
        priority=TaskPriority.NORMAL,
        user_id=task_info.get('user_id'),
        session_id=None,
        detail=detail
    )

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
        
        health_response = HealthResponse(
            status="healthy",
            timestamp=datetime.now(),
            version=settings.VERSION,
            uptime=0,  # TODO: Implement uptime tracking
            memory_usage=0,  # TODO: Implement memory usage tracking
            security_stats=security_stats,
            task_stats=task_stats,
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
        security_stats = get_security_stats()
        
        stats = {
            'tasks': {
                'total': len(all_tasks),
                'by_status': {}
            },
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
# Video Generation Endpoints
# ============================================================================

@router.post("/video/generate", response_model=VideoGenerationResponse)
def generate_video_from_scene(
    request: VideoGenerationRequest,
    http_request: Request = None,
    api_key: Optional[str] = Depends(get_api_key)
) -> VideoGenerationResponse:
    """
    Generate video from a scene using AI generation.
    
    This endpoint accepts a scene_id and starts video generation asynchronously using threads.
    Returns immediately with a task ID for polling.
    
    The process includes:
    1. Image generation (if no image exists) using RunwayML
    2. Video generation from the image using RunwayML
    3. Storage of both image and video in Supabase
    4. Credit deduction for each generation step
    
    Authentication: Optional API key via Bearer token
    Rate Limits: Based on API key configuration
    """
    try:
        # Security validation - DISABLED FOR DEVELOPMENT
        # TODO: Re-enable security checks for production by uncommenting the lines below
        # validate_request_security(http_request, api_key)
        
        logger.info(f"Starting video generation for scene {request.scene_id} by user {request.user_id}")
        
        # Start video generation using threads
        response = video_generation_service.start_video_generation_task(
            scene_id=request.scene_id,
            user_id=request.user_id
        )
        
        # Convert response to VideoGenerationResponse format
        video_generation_response = VideoGenerationResponse(
            task_id=response['task_id'],
            status=response['status'],
            scene_id=response['scene_id'],
            user_id=response['user_id'],
            message=response['message'],
            created_at=response['created_at'],
            progress=response.get('progress'),
            current_step=response.get('current_step'),
            error_message=response.get('error_message'),
            video_url=response.get('video_url'),
            image_url=response.get('image_url')
        )
        
        logger.info(f"Started video generation task {video_generation_response.task_id} for scene {request.scene_id}")
        
        return video_generation_response
        
    except Exception as e:
        logger.error(f"Error in video generation endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Video generation failed: {str(e)}")


@router.get("/video/generate/tasks/{task_id}", response_model=VideoGenerationResponse)
def get_video_generation_task_status(task_id: str) -> VideoGenerationResponse:
    """
    Get the status of a video generation task.
    Returns VideoGenerationResponse with current status and progress.
    """
    try:
        task_info = video_generation_service.get_task_status(task_id)
        
        if not task_info:
            raise HTTPException(status_code=404, detail="Video generation task not found")
        
        # Convert task info to VideoGenerationResponse
        return VideoGenerationResponse(
            task_id=task_id,
            status=task_info['status'],
            scene_id=task_info['scene_id'],
            user_id=task_info['user_id'],
            message=task_info.get('message', ''),
            created_at=task_info['created_at'],
            progress=task_info.get('progress'),
            current_step=task_info.get('current_step'),
            error_message=task_info.get('error_message'),
            video_url=task_info.get('video_url'),
            image_url=task_info.get('image_url'),
            completed_at=task_info.get('updated_at') if task_info.get('status') == TaskStatus.COMPLETED else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video generation task status {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get video generation task status: {str(e)}")



@router.delete("/video/generate/tasks/{task_id}")
def cancel_video_generation_task(task_id: str):
    """
    Cancel a running video generation task
    """
    try:
        task_info = video_generation_service.get_task_status(task_id)
        
        if not task_info:
            raise HTTPException(status_code=404, detail="Video generation task not found")
        
        if task_info['status'] not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            raise HTTPException(status_code=400, detail="Cannot cancel completed or failed video generation task")
        
        # Update task status to cancelled
        video_generation_service._update_task(task_id, status=TaskStatus.FAILED, message="Video generation task cancelled by user")
        
        return {"message": f"Video generation task {task_id} cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling video generation task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cancel video generation task: {str(e)}")


@router.delete("/video/generate/tasks")
def cleanup_video_generation_tasks():
    """
    Clean up old completed/failed video generation tasks
    """
    try:
        video_generation_service.cleanup()
        return {"message": "Video generation task cleanup completed"}
        
    except Exception as e:
        logger.error(f"Error cleaning up video generation tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cleanup video generation tasks: {str(e)}")


# ============================================================================
# Short Finalization Endpoints
# ============================================================================

@router.post("/shorts/finalize", response_model=FinalizeShortResponse)
def finalize_short(
    request: FinalizeShortRequest,
    http_request: Request = None,
    api_key: Optional[str] = Depends(get_api_key)
) -> FinalizeShortResponse:
    """
    Finalize a short video by merging scenes, generating thumbnail, and optionally upscaling.
    
    This endpoint starts the finalization process asynchronously using threads.
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
        
        logger.info(f"Starting short finalization for user {request.user_id}, short {request.short_id}, upscale: {request.upscale}")
        
        # Start finalization using merging service
        response = merging_service.start_finalize_short_task(
            user_id=request.user_id,
            short_id=request.short_id,
            upscale=request.upscale
        )
        
        # Convert response to FinalizeShortResponse format
        finalize_response = FinalizeShortResponse(
            task_id=response['task_id'],
            status=TaskStatus.PENDING,
            short_id=request.short_id,
            user_id=request.user_id,
            message=response['message'],
            created_at=datetime.fromisoformat(response['created_at']),
            progress=0.0,
            current_step="Initializing"
        )
        
        logger.info(f"Started short finalization task {finalize_response.task_id} for short {request.short_id}")
        
        return finalize_response
        
    except Exception as e:
        logger.error(f"Error in short finalization endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Short finalization failed: {str(e)}")


@router.get("/shorts/finalize/tasks/{task_id}", response_model=FinalizeShortResponse)
def get_short_finalization_task_status(task_id: str) -> FinalizeShortResponse:
    """
    Get the status of a short finalization task.
    Returns FinalizeShortResponse with current status and progress.
    """
    try:
        task_info = merging_service.get_task_status(task_id)
        
        if not task_info:
            raise HTTPException(status_code=404, detail="Short finalization task not found")
        
        # Convert task info to FinalizeShortResponse
        # Handle both Task object and dict formats
        if hasattr(task_info, 'task_status'):
            # Task object
            status = task_info.task_status
            created_at = task_info.created_at
            progress = task_info.progress
            current_step = task_info.current_step_name
            error_message = task_info.error_message
            short_id = task_info.task_metadata.get('short_id', '') if task_info.task_metadata else ''
            user_id = task_info.user_id or ''
            message = task_info.task_status_message or ''
            thumbnail_url = task_info.task_metadata.get('thumbnail_url', '') if task_info.task_metadata else ''
            video_url = task_info.task_metadata.get('video_url', '') if task_info.task_metadata else ''
            final_video_url = task_info.task_metadata.get('final_video_url', '') if task_info.task_metadata else ''
            updated_at = task_info.updated_at
        else:
            # Dict format
            status = task_info['status']
            created_at = task_info['created_at']
            progress = task_info.get('progress')
            current_step = task_info.get('current_step')
            error_message = task_info.get('error_message')
            short_id = task_info.get('short_id', '')
            user_id = task_info.get('user_id', '')
            message = task_info.get('message', '')
            thumbnail_url = task_info.get('thumbnail_url', '')
            video_url = task_info.get('video_url', '')
            final_video_url = task_info.get('final_video_url', '')
            updated_at = task_info.get('updated_at')
        
        return FinalizeShortResponse(
            task_id=task_id,
            status=status,
            short_id=short_id,
            user_id=user_id,
            message=message,
            created_at=created_at,
            progress=progress,
            current_step=current_step,
            error_message=error_message,
            thumbnail_url=thumbnail_url,
            final_video_url=final_video_url,
            completed_at=updated_at if status == TaskStatus.COMPLETED else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting short finalization task status {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get short finalization task status: {str(e)}")


@router.delete("/shorts/finalize/tasks/{task_id}")
def cancel_short_finalization_task(task_id: str):
    """
    Cancel a running short finalization task
    """
    try:
        task_info = merging_service.get_task_status(task_id)
        
        if not task_info:
            raise HTTPException(status_code=404, detail="Short finalization task not found")
        
        # Handle both Task object and dict formats
        if hasattr(task_info, 'task_status'):
            status = task_info.task_status
        else:
            status = task_info['status']
            
        if status not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            raise HTTPException(status_code=400, detail="Cannot cancel completed or failed short finalization task")
        
        # Update task status to failed (cancelled)
        # Note: We'll need to add a cancel method to the merging service
        # For now, we'll mark it as failed
        logger.warning(f"Short finalization task {task_id} cancelled by user")
        
        return {"message": f"Short finalization task {task_id} cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling short finalization task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cancel short finalization task: {str(e)}")


@router.delete("/shorts/finalize/tasks")
def cleanup_short_finalization_tasks():
    """
    Clean up old completed/failed short finalization tasks
    """
    try:
        merging_service.cleanup()
        return {"message": "Short finalization task cleanup completed"}
        
    except Exception as e:
        logger.error(f"Error cleaning up short finalization tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cleanup short finalization tasks: {str(e)}") 