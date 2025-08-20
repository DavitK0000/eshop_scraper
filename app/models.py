from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ScrapeRequest(BaseModel):
    url: HttpUrl = Field(..., description="URL of the product to scrape")
    force_refresh: bool = Field(False, description="Force refresh and bypass cache")
    proxy: Optional[str] = Field(None, description="Custom proxy to use")
    user_agent: Optional[str] = Field(None, description="Custom user agent to use")
    block_images: bool = Field(True, description="Block image downloads to save bandwidth")
    target_language: Optional[str] = Field(None, description="Target language for content extraction (e.g., 'en', 'es', 'fr')")


class ProductInfo(BaseModel):
    title: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    description: Optional[str] = None
    images: List[str] = []
    rating: Optional[float] = None
    review_count: Optional[int] = None
    specifications: Dict[str, Any] = {}


class ScrapeResponse(BaseModel):
    task_id: str
    status: TaskStatus
    url: str
    product_info: Optional[ProductInfo] = None
    error: Optional[str] = None
    message: Optional[str] = Field(None, description="Current status message (e.g., 'Detecting platform', 'Extracting product info')")
    created_at: datetime
    completed_at: Optional[datetime] = None
    cache_hit: bool = False
    # Platform detection info
    detected_platform: Optional[str] = Field(None, description="Detected e-commerce platform")
    platform_confidence: Optional[float] = Field(None, description="Platform detection confidence (0.0 to 1.0)")
    platform_indicators: List[str] = Field(default_factory=list, description="Platform detection indicators")
    target_language: Optional[str] = Field(None, description="Target language for content extraction")


class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    progress: Optional[float] = None
    message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    target_language: Optional[str] = Field(None, description="Target language for content extraction")


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
    services: Dict[str, str]


class VideoProcessRequest(BaseModel):
    video_urls: List[str] = Field(..., description="List of video URLs to merge in order")
    audio_data: str = Field(..., description="Base64 encoded audio data")
    subtitle_text: Optional[str] = Field(None, description="Subtitle text to embed in the video (optional)")
    output_resolution: str = Field("1920x1080", description="Output video resolution")
    watermark: bool = Field(False, description="Add 'PromoNexAI' watermark to the center of the video")


class VideoProcessResponse(BaseModel):
    task_id: str
    status: TaskStatus
    video_data: Optional[str] = Field(None, description="Base64 encoded final video data")
    thumbnail_data: Optional[str] = Field(None, description="Base64 encoded thumbnail image")
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None 