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


class ProductInfo(BaseModel):
    title: Optional[str] = None
    price: Optional[str] = None
    currency: Optional[str] = None
    description: Optional[str] = None
    images: List[str] = []
    availability: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    seller: Optional[str] = None
    brand: Optional[str] = None
    sku: Optional[str] = None
    category: Optional[str] = None
    specifications: Dict[str, Any] = {}
    raw_data: Dict[str, Any] = {}


class ScrapeResponse(BaseModel):
    task_id: str
    status: TaskStatus
    url: str
    product_info: Optional[ProductInfo] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    cache_hit: bool = False


class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    progress: Optional[float] = None
    message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
    services: Dict[str, str] 