from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime, timezone


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


class ImageAnalysisRequest(BaseModel):
    product_id: str = Field(..., description="Product ID to analyze images for")
    user_id: str = Field(..., description="User ID associated with the task")

class ImageAnalysisResult(BaseModel):
    image_url: str
    description: str
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    analyzed_at: Optional[datetime] = None
    objects: Optional[List[str]] = None
    colors: Optional[List[str]] = None
    style: Optional[str] = None
    mood: Optional[str] = None
    text: Optional[List[str]] = None
    productFeatures: Optional[List[str]] = None
    videoScenarios: Optional[List[str]] = None
    targetAudience: Optional[str] = None
    useCases: Optional[List[str]] = None 
class ImageAnalysisResponse(BaseModel):
    task_id: str
    status: TaskStatus
    product_id: str
    user_id: str
    message: str
    created_at: datetime
    progress: Optional[float] = None
    current_step: Optional[str] = None
    error_message: Optional[str] = None
    total_images: Optional[int] = None
    analyzed_images: Optional[int] = None
    failed_images: Optional[int] = None
    analyzedData: Optional[Dict[str, ImageAnalysisResult]] = None
    completed_at: Optional[datetime] = None


# Scenario Generation Models
class ScenarioGenerationRequest(BaseModel):
    short_id: Optional[str] = Field(None, description="Short ID if updating existing short")
    product_id: str = Field(..., description="Product ID to generate scenario for")
    user_id: str = Field(..., description="User ID associated with the task")
    style: str = Field(..., description="Video style (e.g., 'trendy-influencer-vlog', 'cinematic-storytelling')")
    mood: str = Field(..., description="Video mood (e.g., 'energetic', 'calm', 'professional')")
    video_length: int = Field(..., description="Video length in seconds (15, 20, 30, 45, or 60)")
    resolution: str = Field(..., description="Video resolution (e.g., '720:1280', '1280:720')")
    target_language: str = Field(..., description="Target language for content (e.g., 'en-US', 'es-ES')")
    environment: Optional[str] = Field(None, description="Environment context for the video (e.g., 'indoor', 'outdoor', 'studio', 'home', 'office')")


class DetectedDemographics(BaseModel):
    target_gender: str = Field(..., description="Target gender (male, female, unisex, children, adults, seniors, all-ages)")
    age_group: str = Field(..., description="Age group (children, teens, young-adults, adults, seniors, all-ages)")
    product_type: str = Field(..., description="Product category/type")
    demographic_context: str = Field(..., description="Description of target audience for character consistency")


class Scene(BaseModel):
    scene_id: str = Field(..., description="Unique identifier for this scene")
    scene_number: int = Field(..., description="Scene number")
    description: str = Field(..., description="Human-readable scene description")
    duration: int = Field(..., description="Duration in seconds (must be exactly 5)")
    image_prompt: str = Field(..., description="Detailed prompt for first frame image generation")
    visual_prompt: str = Field(..., description="Safe video prompt for video generation")
    product_reference_image_url: str = Field(..., description="Reference image URL from product")
    image_reasoning: str = Field(..., description="Why this image was chosen for this scene")
    generated_image_url: Optional[str] = Field(None, description="Generated image URL from RunwayML")


class AudioScript(BaseModel):
    hook: str = Field(..., description="Attention-grabbing opening (20-25% of total duration)")
    main: str = Field(..., description="Main content about product benefits (50-60% of total duration)")
    cta: str = Field(..., description="Call-to-action (15-20% of total duration)")
    hashtags: List[str] = Field(..., description="5-8 relevant hashtags")


class GeneratedScenario(BaseModel):
    title: str = Field(..., description="Scenario title")
    description: str = Field(..., description="Brief description of the scenario approach")
    detected_demographics: Optional[DetectedDemographics] = Field(None, description="AI-detected demographic information")
    scenes: List[Scene] = Field(..., description="List of scenes for the video")
    audio_script: AudioScript = Field(..., description="Audio script with timing")
    total_duration: int = Field(..., description="Total duration of the video")
    style: str = Field(..., description="Style of the video")
    mood: str = Field(..., description="Mood of the video")
    resolution: str = Field(..., description="Resolution of the video")
    environment: Optional[str] = Field(None, description="Environment context for the video")
    thumbnail_prompt: Optional[str] = Field(None, description="AI-generated prompt for thumbnail image generation")
    thumbnail_url: Optional[str] = Field(None, description="Generated thumbnail image URL from RunwayML")


class ScenarioGenerationResponse(BaseModel):
    task_id: str = Field(..., description="Unique task ID for tracking")
    status: TaskStatus = Field(..., description="Current status of the task")
    short_id: str = Field(..., description="Short ID associated with the scenario")
    user_id: str = Field(..., description="User ID who owns the scenario")
    message: str = Field(..., description="Status message")
    created_at: datetime = Field(..., description="When the task was created")
    progress: Optional[float] = Field(None, description="Progress percentage (0-100)")
    current_step: Optional[str] = Field(None, description="Current processing step")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    scenario: Optional[GeneratedScenario] = Field(None, description="Generated scenario when task is completed")
    completed_at: Optional[datetime] = Field(None, description="When the task was completed")

# Save Scenario Models
class SaveScenarioRequest(BaseModel):
    short_id: str = Field(..., description="Short ID to save scenario for")
    user_id: str = Field(..., description="User ID who owns the scenario")
    scenario: str = Field(..., description="Scenario JSON string to save")

class SaveScenarioResponse(BaseModel):
    task_id: str = Field(..., description="Unique task ID for tracking")
    status: TaskStatus = Field(..., description="Current status of the task")
    short_id: str = Field(..., description="Short ID associated with the scenario")
    user_id: str = Field(..., description="User ID who owns the scenario")
    message: str = Field(..., description="Status message")
    created_at: datetime = Field(..., description="When the task was created")
    progress: Optional[float] = Field(None, description="Progress percentage (0-100)")
    current_step: Optional[str] = Field(None, description="Current processing step")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    scenario_id: Optional[str] = Field(None, description="Generated scenario ID when task is completed")
    completed_at: Optional[datetime] = Field(None, description="When the task was completed")


# Test Audio Models
class TestAudioRequest(BaseModel):
    voice_id: str = Field(..., description="ElevenLabs voice ID for test audio")
    language: str = Field(..., description="Language code for the test audio (e.g., 'en-US', 'es', 'fr')")
    user_id: str = Field(..., description="User ID associated with the request")

class TestAudioResponse(BaseModel):
    voice_id: str = Field(..., description="Voice ID used for test audio")
    language: str = Field(..., description="Language code used")
    audio_url: str = Field(..., description="URL of the test audio")
    user_id: str = Field(..., description="User ID who requested the audio")
    created_at: datetime = Field(..., description="When the test audio was generated")
    is_cached: bool = Field(False, description="Whether this was a cached result")
    message: str = Field(..., description="Status message")


# Session Management Models
class SessionInfo(BaseModel):
    short_id: str = Field(..., description="Short ID associated with the session")
    task_type: str = Field(..., description="Type of task (e.g., 'scraping', 'scenario_generation')")
    task_id: str = Field(..., description="Task ID associated with the session")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When the session was created")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When the session was last updated")
    user_id: Optional[str] = Field(None, description="User ID associated with the session")
    status: str = Field("active", description="Session status (active, completed, failed)")