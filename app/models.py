from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RETRYING = "retrying"


class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ScrapeRequest(BaseModel):
    url: HttpUrl = Field(..., description="URL of the product to scrape")
    user_id: str = Field(..., description="User ID associated with the task (required)")
    proxy: Optional[str] = Field(None, description="Custom proxy to use")
    user_agent: Optional[str] = Field(None, description="Custom user agent to use")
    block_images: bool = Field(True, description="Block image downloads to save bandwidth")
    target_language: Optional[str] = Field(None, description="Target language for content extraction (e.g., 'en', 'es', 'fr')")
    priority: TaskPriority = Field(TaskPriority.NORMAL, description="Task priority level")
    session_id: Optional[str] = Field(None, description="Session ID for the task")


class ProductInfo(BaseModel):
    title: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    description: Optional[str] = None
    images: List[str] = []
    rating: Optional[float] = None
    review_count: Optional[int] = None
    specifications: Dict[str, Any] = {}


class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    url: str
    task_type: Optional[str] = Field(None, description="Type of task (e.g., 'scraping', 'media_processing')")
    progress: Optional[float] = None
    message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    priority: TaskPriority = TaskPriority.NORMAL
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    detail: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional task details and metadata including supabase_product_id")


class TaskListResponse(BaseModel):
    tasks: List[TaskStatusResponse]
    total: int
    page: int
    page_size: int


class TaskStatisticsResponse(BaseModel):
    total_tasks: int
    pending_tasks: int
    running_tasks: int
    completed_tasks: int
    failed_tasks: int
    cancelled_tasks: int
    timeout_tasks: int
    retrying_tasks: int
    avg_progress: float
    avg_duration_seconds: float


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
    services: Dict[str, str]

class VideoGenerationRequest(BaseModel):
    scene_id: str = Field(..., description="UUID of the scene to generate video for")
    user_id: str = Field(..., description="User ID who owns the scene")
class VideoGenerationResponse(BaseModel):
    task_id: str = Field(..., description="Unique task ID for tracking")
    status: TaskStatus = Field(..., description="Current status of the task")
    scene_id: str = Field(..., description="Scene ID being processed")
    user_id: str = Field(..., description="User ID who owns the scene")
    message: str = Field(..., description="Status message")
    created_at: datetime = Field(..., description="When the task was created")
    progress: Optional[float] = Field(None, description="Progress percentage (0-100)")
    current_step: Optional[str] = Field(None, description="Current processing step")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    video_url: Optional[str] = Field(None, description="Generated video URL (signed URL) when task is completed")
    image_url: Optional[str] = Field(None, description="Generated image URL when task is completed")
    error: Optional[str] = None
    completed_at: Optional[datetime] = None


class FinalizeShortRequest(BaseModel):
    user_id: str = Field(..., description="User ID associated with the task")
    short_id: str = Field(..., description="Short ID to finalize")
    upscale: bool = Field(False, description="Whether to upscale the final video")

class FinalizeShortResponse(BaseModel):
    task_id: str
    status: TaskStatus
    short_id: str
    user_id: str
    message: str
    created_at: datetime
    progress: Optional[float] = None
    current_step: Optional[str] = None
    error_message: Optional[str] = None
    thumbnail_url: Optional[str] = None
    final_video_url: Optional[str] = None
    completed_at: Optional[datetime] = None 