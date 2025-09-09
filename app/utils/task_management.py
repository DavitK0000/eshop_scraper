"""
Task management utilities for scraping tasks.

This module provides a comprehensive interface for managing scraping tasks including:
- MongoDB operations for task persistence
- Task lifecycle management
- Fallback in-memory storage when MongoDB is not available
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any
from enum import Enum
from dataclasses import dataclass, asdict

try:
    from pymongo import MongoClient, ASCENDING, DESCENDING, IndexModel
    from pymongo.errors import PyMongoError, ConnectionFailure, ServerSelectionTimeoutError
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False
    MongoClient = None

from ..config import settings
from .url_utils import generate_task_id
from ..services.session_service import session_service

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Task type enumeration"""
    SCRAPING = "scraping"
    CONTENT_ANALYSIS = "content_analysis"
    DATA_EXTRACTION = "data_extraction"
    VIDEO_GENERATION = "video_generation"
    FINALIZE_SHORT = "finalize_short"
    IMAGE_ANALYSIS = "image_analysis"
    SCENARIO_GENERATION = "scenario_generation"
    SAVE_SCENARIO = "save_scenario"


class TaskStatus(str, Enum):
    """Task status enumeration"""
    QUEUED = "queued"
    PENDING = "pending"
    RUNNING = "running"
    FAILED = "failed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RETRYING = "retrying"


class TaskPriority(str, Enum):
    """Task priority enumeration"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Task:
    """Unified task structure for all types of tasks"""
    task_id: str
    task_type: TaskType
    task_status: TaskStatus
    task_status_message: str = ""
    task_metadata: Dict[str, Any] = None
    task_priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = None
    updated_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    total_steps: int = 1
    current_step: int = 0
    current_step_name: str = ""
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    # Note: result_data removed since results are saved in Supabase, not in tasks
    url: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = datetime.now(timezone.utc)
        if self.task_metadata is None:
            self.task_metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage"""
        data = asdict(self)
        # Convert datetime objects to ISO format for JSON serialization
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """Create Task from dictionary"""
        # Filter out MongoDB-specific fields
        filtered_data = {k: v for k, v in data.items() if not k.startswith('_')}
        
        # Convert ISO format strings back to datetime objects
        for key, value in filtered_data.items():
            if key in ['created_at', 'updated_at', 'started_at', 'completed_at'] and value:
                if isinstance(value, str):
                    filtered_data[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return cls(**filtered_data)


class MongoDBManager:
    """MongoDB connection and operation manager"""
    
    def __init__(self, connection_string: str = None, database_name: str = None):
        self.connection_string = connection_string or getattr(settings, 'MONGODB_URI', 'mongodb://localhost:27017')
        self.database_name = database_name or getattr(settings, 'MONGODB_DATABASE', 'eshop_scraper')
        self.client: Optional[MongoClient] = None
        self.database = None
        self.tasks_collection = None
        self._connection_pool_size = getattr(settings, 'MONGODB_POOL_SIZE', 10)
        self._max_pool_size = getattr(settings, 'MONGODB_MAX_POOL_SIZE', 100)
        self._server_selection_timeout = getattr(settings, 'MONGODB_SERVER_SELECTION_TIMEOUT', 5000)
        self._connect_timeout = getattr(settings, 'MONGODB_CONNECT_TIMEOUT', 20000)
        self._socket_timeout = getattr(settings, 'MONGODB_SOCKET_TIMEOUT', 30000)
        
    def connect(self) -> bool:
        """Establish connection to MongoDB"""
        if not MONGODB_AVAILABLE:
            logger.error("MongoDB dependencies not available. Install pymongo.")
            return False
            
        try:
            logger.info(f"Attempting to connect to MongoDB at: {self.connection_string}")
            self.client = MongoClient(
                self.connection_string,
                maxPoolSize=self._max_pool_size,
                serverSelectionTimeoutMS=self._server_selection_timeout,
                connectTimeoutMS=self._connect_timeout,
                socketTimeoutMS=self._socket_timeout,
                retryWrites=True,
                retryReads=True,
                # Connection pool settings for persistence
                minPoolSize=5,
                maxIdleTimeMS=30000,
                waitQueueTimeoutMS=5000
            )
            
            # Test connection
            logger.info("Testing MongoDB connection...")
            self.client.admin.command('ping')
            logger.info("MongoDB ping successful")
            
            self.database = self.client[self.database_name]
            self.tasks_collection = self.database.tasks
            
            # Create indexes for better performance
            logger.info("Creating MongoDB indexes...")
            self._create_indexes()
            
            logger.info(f"Successfully connected to MongoDB: {self.database_name}")
            return True
                
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {e}")
            return False
    
    def disconnect(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            self.client = None
            self.database = None
            self.tasks_collection = None
            logger.info("MongoDB connection closed")
    
    def _create_indexes(self):
        """Create database indexes for better performance"""
        try:
            # Index on task_id for fast lookups
            self.tasks_collection.create_index(
                IndexModel([("task_id", ASCENDING)], unique=True)
            )
            
            # Index on task_type for filtering by task type
            self.tasks_collection.create_index(
                IndexModel([("task_type", ASCENDING)])
            )
            
            # Index on task_status for filtering by status
            self.tasks_collection.create_index(
                IndexModel([("task_status", ASCENDING)])
            )
            
            # Index on created_at for time-based queries
            self.tasks_collection.create_index(
                IndexModel([("created_at", DESCENDING)])
            )
            
            # Index on user_id for user-based queries
            self.tasks_collection.create_index(
                IndexModel([("user_id", ASCENDING)])
            )
            
            logger.info("MongoDB indexes created successfully")
            
        except Exception as e:
            logger.warning(f"Failed to create some indexes: {e}")
    
    def health_check(self) -> bool:
        """Check if MongoDB connection is healthy"""
        try:
            if not self.client:
                return False
            self.client.admin.command('ping')
            return True
        except Exception:
            return False
    
    def ensure_connection(self) -> bool:
        """Ensure MongoDB connection is active, reconnect if needed"""
        if not self.health_check():
            logger.info("MongoDB connection lost, attempting to reconnect...")
            return self.connect()
        return True
    
    def monitor_connection(self):
        """Monitor connection health and reconnect if needed"""
        try:
            if not self.health_check():
                logger.warning("MongoDB connection unhealthy, reconnecting...")
                self.connect()
        except Exception as e:
            logger.error(f"Error monitoring MongoDB connection: {e}")
            self.connect()


class TaskDatabaseOperations:
    """Database operations for tasks"""
    
    def __init__(self, mongodb_manager: MongoDBManager):
        self.mongodb = mongodb_manager
    
    def create_task(self, task: Task) -> bool:
        """Create a new task"""
        try:
            logger.info(f"Attempting to create task {task.task_id} in MongoDB")
            
            # Ensure connection
            if not self.mongodb.ensure_connection():
                logger.error(f"Failed to ensure MongoDB connection for task {task.task_id}")
                return False
                
            # Ensure task_id is unique
            logger.info(f"Checking if task {task.task_id} already exists...")
            existing_task = self.mongodb.tasks_collection.find_one({"task_id": task.task_id})
            if existing_task:
                logger.warning(f"Task with ID {task.task_id} already exists")
                return False
            
            # Insert the task
            logger.info(f"Inserting task {task.task_id} into MongoDB...")
            task_dict = task.to_dict()
            logger.info(f"Task data to insert: {task_dict}")
            
            result = self.mongodb.tasks_collection.insert_one(task_dict)
            if result.inserted_id:
                logger.info(f"Task {task.task_id} created successfully with MongoDB ID: {result.inserted_id}")
                return True
            else:
                logger.error(f"Failed to insert task {task.task_id} - no inserted_id returned")
                return False
                
        except Exception as e:
            logger.error(f"Failed to create task {task.task_id}: {e}")
            return False
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        try:
            if not self.mongodb.ensure_connection():
                return None
                
            task_doc = self.mongodb.tasks_collection.find_one({"task_id": task_id})
            if task_doc:
                return Task.from_dict(task_doc)
            return None
                
        except Exception as e:
            logger.error(f"Failed to get task {task_id}: {e}")
            return None
    
    def update_task(self, task_id: str, update_data: Dict[str, Any]) -> bool:
        """Update task with provided data"""
        try:
            if not self.mongodb.ensure_connection():
                return False
                
            # Add updated_at timestamp
            update_data["updated_at"] = datetime.now(timezone.utc)
            
            result = self.mongodb.tasks_collection.update_one(
                {"task_id": task_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info(f"Task {task_id} updated successfully")
                return True
            else:
                logger.warning(f"Task {task_id} not found or not modified")
                return False
                    
        except Exception as e:
            logger.error(f"Failed to update task {task_id}: {e}")
            return False
    
    def delete_task(self, task_id: str) -> bool:
        """Delete a task"""
        try:
            if not self.mongodb.ensure_connection():
                return False
                
            result = self.mongodb.tasks_collection.delete_one({"task_id": task_id})
            if result.deleted_count > 0:
                logger.info(f"Task {task_id} deleted successfully")
                return True
            return False
                
        except Exception as e:
            logger.error(f"Failed to delete task {task_id}: {e}")
            return False
    
    def cleanup_old_tasks(self, days_old: int = 30) -> int:
        """Clean up old completed/failed tasks"""
        try:
            if not self.mongodb.ensure_connection():
                return 0
                
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
            cutoff_date_iso = cutoff_date.isoformat()
            
            result = self.mongodb.tasks_collection.delete_many({
                "created_at": {"$lt": cutoff_date_iso}
            })
            
            deleted_count = result.deleted_count
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old tasks")
            else:
                logger.info("No old tasks found to clean up")
            
            return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to cleanup old tasks: {e}")
            return 0


class TaskManager:
    """High-level task manager for all task types"""
    
    def __init__(self):
        self.mongodb = MongoDBManager()
        self.db_ops = TaskDatabaseOperations(self.mongodb)
        
        # Fallback in-memory storage for when MongoDB is not available
        self.fallback_tasks: Dict[str, Task] = {}
        self.mongodb_available = False
        
        # Default steps for different task types
        self.default_steps = {
            TaskType.SCRAPING: [
                "Initializing",
                "Fetching page content",
                "Detecting e-commerce platform",
                "Creating platform-specific extractor",
                "Extracting product information",
                "Finalizing results"
            ],

            TaskType.CONTENT_ANALYSIS: [
                "Initializing",
                "Processing content",
                "Performing analysis",
                "Generating insights",
                "Finalizing results"
            ],
            TaskType.DATA_EXTRACTION: [
                "Initializing",
                "Connecting to data source",
                "Extracting data",
                "Processing extracted data",
                "Formatting output",
                "Finalizing results"
            ],
            TaskType.VIDEO_GENERATION: [
                "Initializing",
                "Downloading media files",
                "Processing media content",
                "Applying transformations",
                "Encoding output",
                "Finalizing results"
            ],
            TaskType.FINALIZE_SHORT: [
                "Initializing",
                "Fetching video scenes",
                "Generating thumbnail",
                "Downloading videos",
                "Merging videos",
                "Adding watermark (if needed)",
                "Upscaling video (if requested)",
                "Uploading final video",
                "Finalizing results"
            ]
        }
    
    def connect(self) -> bool:
        """Connect to MongoDB"""
        try:
            self.mongodb_available = self.mongodb.connect()
            if self.mongodb_available:
                logger.info("MongoDB connection established successfully")
            else:
                logger.warning("MongoDB connection failed - using fallback in-memory storage")
            return self.mongodb_available
        except Exception as e:
            logger.error(f"Error connecting to MongoDB: {e}")
            self.mongodb_available = False
            return False
    
    def disconnect(self):
        """Disconnect from MongoDB"""
        self.mongodb.disconnect()
    
    def monitor_connections(self):
        """Monitor and maintain database connections"""
        try:
            self.mongodb.monitor_connection()
        except Exception as e:
            logger.error(f"Error monitoring MongoDB connection: {e}")
            # Try to reconnect
            self.connect()
    
    def ensure_connections(self) -> bool:
        """Ensure all database connections are active"""
        try:
            return self.mongodb.ensure_connection()
        except Exception as e:
            logger.error(f"Error ensuring MongoDB connection: {e}")
            return self.connect()
    
    def create_task(
        self,
        task_type: TaskType,
        task_metadata: Dict[str, Any],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        priority: TaskPriority = TaskPriority.NORMAL
    ) -> str:
        """
        Create a new task of any type
        
        Args:
            task_type: Type of task to create
            task_metadata: Task-specific metadata
            user_id: Optional user ID for the task
            session_id: Optional session ID for the task
            priority: Task priority
            
        Returns:
            task_id: The created task ID
        """
        try:
            logger.info(f"Creating {task_type} task with metadata: {task_metadata}")
            
            # Generate task ID
            task_id = generate_task_id(f"{task_type}_{datetime.now(timezone.utc).timestamp()}")
            logger.info(f"Generated task ID: {task_id}")
            
            # Extract common fields from metadata
            url = task_metadata.get('url')
            logger.info(f"Extracted URL: {url}")
            
            # Create task
            task = Task(
                task_id=task_id,
                task_type=task_type,
                task_status=TaskStatus.QUEUED,
                task_status_message="Task created and queued",
                task_metadata=task_metadata,
                task_priority=priority,
                url=url,
                user_id=user_id,
                session_id=session_id,
                total_steps=len(self.default_steps.get(task_type, [1]))
            )
            
            logger.info(f"Created Task object: {task.to_dict()}")
            
            # Try to save to MongoDB first
            if self.mongodb_available:
                logger.info(f"Saving task to MongoDB...")
                task_created = self.db_ops.create_task(task)
                if task_created:
                    logger.info(f"Created {task_type} task {task_id} in MongoDB")
                    
                    # Create session for the task if short_id is available and task is not scraping
                    short_id = task_metadata.get('short_id')
                    if short_id and task_type != TaskType.SCRAPING:
                        logger.info(f"Creating session for task {task_id} with short_id {short_id}")
                        session_service.create_session(
                            short_id=short_id,
                            task_type=task_type.value,
                            task_id=task_id,
                            user_id=user_id
                        )
                    elif task_type == TaskType.SCRAPING:
                        logger.info(f"Skipping session creation for scraping task {task_id}")
                    
                    return task_id
                else:
                    logger.warning(f"Failed to create task {task_id} in MongoDB, using fallback storage")
            
            # Fallback to in-memory storage
            logger.info(f"Storing task {task_id} in fallback in-memory storage")
            self.fallback_tasks[task_id] = task
            logger.info(f"Created {task_type} task {task_id} in fallback storage")
            return task_id
            
        except Exception as e:
            logger.error(f"Error creating {task_type} task: {e}")
            raise
    

    def start_task(self, task_id: str) -> bool:
        """Start a task by updating its status to RUNNING"""
        try:
            # Try MongoDB first
            if self.mongodb_available:
                # Update task status to running
                success = self.db_ops.update_task(task_id, {
                    "task_status": TaskStatus.RUNNING,
                    "task_status_message": "Task started",
                    "started_at": datetime.now(timezone.utc),
                    "progress": 0.0
                })
                
                if success:
                    logger.info(f"Started task {task_id} in MongoDB")
                    return True
                else:
                    logger.warning(f"Failed to start task {task_id} in MongoDB, using fallback")
            
            # Fallback to in-memory storage
            if task_id in self.fallback_tasks:
                task = self.fallback_tasks[task_id]
                task.task_status = TaskStatus.RUNNING
                task.task_status_message = "Task started"
                task.started_at = datetime.now(timezone.utc)
                task.progress = 0.0
                task.updated_at = datetime.now(timezone.utc)
                logger.info(f"Started task {task_id} in fallback storage")
                return True
            else:
                logger.error(f"Task {task_id} not found in fallback storage")
                return False
                
        except Exception as e:
            logger.error(f"Error starting task {task_id}: {e}")
            return False
    
    def update_task_progress(
        self,
        task_id: str,
        step_number: int,
        step_name: str,
        progress: Optional[float] = None
    ) -> bool:
        """Update task progress to a specific step"""
        try:
            # Try MongoDB first
            if self.mongodb_available:
                task = self.db_ops.get_task(task_id)
                if task:
                    total_steps = task.total_steps
                    
                    # Calculate progress if not provided
                    if progress is None:
                        progress = (step_number / total_steps) * 100 if total_steps > 0 else 0
                    
                    # Update task progress
                    success = self.db_ops.update_task(task_id, {
                        "current_step": step_number,
                        "current_step_name": step_name,
                        "progress": progress,
                        "task_status_message": step_name
                    })
                    
                    if success:
                        return True
                    else:
                        logger.warning(f"Failed to update progress for task {task_id} in MongoDB, using fallback")
            
            # Fallback to in-memory storage
            if task_id in self.fallback_tasks:
                task = self.fallback_tasks[task_id]
                task.current_step = step_number
                task.current_step_name = step_name
                if progress is None:
                    progress = (step_number / task.total_steps) * 100 if task.total_steps > 0 else 0
                task.progress = progress
                task.task_status_message = step_name
                task.updated_at = datetime.now(timezone.utc)
                return True
            else:
                logger.error(f"Task {task_id} not found in fallback storage")
                return False
                
        except Exception as e:
            logger.error(f"Error updating task step for {task_id}: {e}")
            return False
    
    def complete_task(
        self,
        task_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Mark a task as completed with optional metadata"""
        try:
            # Get task info first to check task type
            task = None
            if self.mongodb_available:
                task = self.db_ops.get_task(task_id)
            elif task_id in self.fallback_tasks:
                task = self.fallback_tasks[task_id]
            
            # Try MongoDB first
            if self.mongodb_available:
                # Update task status to completed
                update_data = {
                    "task_status": TaskStatus.COMPLETED,
                    "task_status_message": "Task completed successfully",
                    "progress": 100.0,
                    "completed_at": datetime.now(timezone.utc)
                }
                
                # Add metadata to task if provided
                if metadata:
                    for key, value in metadata.items():
                        if value is not None:
                            update_data[f"task_metadata.{key}"] = value
                
                success = self.db_ops.update_task(task_id, update_data)
                
                if success:
                    logger.info(f"Completed task {task_id} in MongoDB")
                    
                    # Remove session if task is not scenario_generation and not scraping
                    if task and task.task_type != TaskType.SCENARIO_GENERATION and task.task_type != TaskType.SCRAPING:
                        logger.info(f"Removing session for completed task {task_id} (type: {task.task_type})")
                        session_service.remove_session(task_id)
                    
                    return True
                else:
                    logger.warning(f"Failed to complete task {task_id} in MongoDB, using fallback")
            
            # Fallback to in-memory storage
            if task_id in self.fallback_tasks:
                task = self.fallback_tasks[task_id]
                task.task_status = TaskStatus.COMPLETED
                task.task_status_message = "Task completed successfully"
                task.progress = 100.0
                task.completed_at = datetime.now(timezone.utc)
                
                # Store metadata in task if provided
                if metadata:
                    if not task.task_metadata:
                        task.task_metadata = {}
                    for key, value in metadata.items():
                        if value is not None:
                            task.task_metadata[key] = value
                
                task.updated_at = datetime.now(timezone.utc)
                logger.info(f"Completed task {task_id} in fallback storage")
                
                # Remove session if task is not scenario_generation and not scraping
                if task.task_type != TaskType.SCENARIO_GENERATION and task.task_type != TaskType.SCRAPING:
                    logger.info(f"Removing session for completed task {task_id} (type: {task.task_type})")
                    session_service.remove_session(task_id)
                
                return True
            else:
                logger.error(f"Task {task_id} not found in fallback storage")
                return False
                
        except Exception as e:
            logger.error(f"Error completing task {task_id}: {e}")
            return False
    
    def fail_task(
        self,
        task_id: str,
        error_message: str,
        retry: bool = False
    ) -> bool:
        """Mark a task as failed"""
        try:
            # Get task info first to check task type
            task = None
            if self.mongodb_available:
                task = self.db_ops.get_task(task_id)
            elif task_id in self.fallback_tasks:
                task = self.fallback_tasks[task_id]
            
            # Try MongoDB first
            if self.mongodb_available:
                if retry:
                    # Increment retry count
                    self.db_ops.update_task(task_id, {
                        "$inc": {"retry_count": 1}
                    })
                    
                    # Check if we should retry
                    task = self.db_ops.get_task(task_id)
                    if task and task.retry_count < task.max_retries:
                        # Mark as retrying
                        success = self.db_ops.update_task(task_id, {
                            "task_status": TaskStatus.RETRYING,
                            "task_status_message": f"Retrying task (attempt {task.retry_count + 1})",
                            "error_message": error_message
                        })
                        logger.info(f"Task {task_id} marked for retry (attempt {task.retry_count + 1}) in MongoDB")
                        return success
                    else:
                        # Max retries exceeded, mark as failed
                        logger.warning(f"Task {task_id} exceeded max retries, marking as failed")
                
                # Mark as failed
                success = self.db_ops.update_task(task_id, {
                    "task_status": TaskStatus.FAILED,
                    "task_status_message": "Task failed",
                    "error_message": error_message,
                    "completed_at": datetime.now(timezone.utc)
                })
                
                if success:
                    logger.info(f"Failed task {task_id} in MongoDB: {error_message}")
                    
                    # Remove session if task is not scenario_generation and not scraping
                    if task and task.task_type != TaskType.SCENARIO_GENERATION and task.task_type != TaskType.SCRAPING:
                        logger.info(f"Removing session for failed task {task_id} (type: {task.task_type})")
                        session_service.remove_session(task_id)
                    
                    return True
                else:
                    logger.warning(f"Failed to mark task {task_id} as failed in MongoDB, using fallback")
            
            # Fallback to in-memory storage
            if task_id in self.fallback_tasks:
                task = self.fallback_tasks[task_id]
                if retry:
                    task.retry_count += 1
                    if task.retry_count < task.max_retries:
                        task.task_status = TaskStatus.RETRYING
                        task.task_status_message = f"Retrying task (attempt {task.retry_count + 1})"
                        task.error_message = error_message
                        logger.info(f"Task {task_id} marked for retry (attempt {task.retry_count + 1}) in fallback storage")
                        return True
                    else:
                        logger.warning(f"Task {task_id} exceeded max retries, marking as failed")
                
                task.task_status = TaskStatus.FAILED
                task.task_status_message = "Task failed"
                task.error_message = error_message
                task.completed_at = datetime.now(timezone.utc)
                task.updated_at = datetime.now(timezone.utc)
                logger.info(f"Failed task {task_id} in fallback storage: {error_message}")
                
                # Remove session if task is not scenario_generation and not scraping
                if task.task_type != TaskType.SCENARIO_GENERATION and task.task_type != TaskType.SCRAPING:
                    logger.info(f"Removing session for failed task {task_id} (type: {task.task_type})")
                    session_service.remove_session(task_id)
                
                return True
            else:
                logger.error(f"Task {task_id} not found in fallback storage")
                return False
                
        except Exception as e:
            logger.error(f"Error failing task {task_id}: {e}")
            return False
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running or pending task"""
        try:
            # Get task info first to check task type
            task = None
            if self.mongodb_available:
                task = self.db_ops.get_task(task_id)
            elif task_id in self.fallback_tasks:
                task = self.fallback_tasks[task_id]
            
            success = self.db_ops.update_task(task_id, {
                "task_status": TaskStatus.CANCELLED,
                "task_status_message": "Task cancelled by user",
                "completed_at": datetime.now(timezone.utc)
            })
            
            if success:
                logger.info(f"Cancelled task {task_id}")
                
                # Remove session if task is not scenario_generation and not scraping
                if task and task.task_type != TaskType.SCENARIO_GENERATION and task.task_type != TaskType.SCRAPING:
                    logger.info(f"Removing session for cancelled task {task_id} (type: {task.task_type})")
                    session_service.remove_session(task_id)
                
                return True
            else:
                logger.error(f"Failed to cancel task {task_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {e}")
            return False
    
    def get_task_status(self, task_id: str) -> Optional[Task]:
        """Get task status"""
        # Try MongoDB first
        if self.mongodb_available:
            task = self.db_ops.get_task(task_id)
            if task:
                return task
        
        # Fallback to in-memory storage
        if task_id in self.fallback_tasks:
            return self.fallback_tasks[task_id]
        
        return None
    
    def cleanup_old_tasks(self, days_old: int = 30) -> int:
        """Clean up old completed/failed tasks"""
        # Only cleanup from MongoDB if available
        if self.mongodb_available:
            return self.db_ops.cleanup_old_tasks(days_old)
        
        # For fallback storage, just return 0 (no cleanup needed for in-memory)
        return 0


# Global instances
task_manager = TaskManager()


# Single unified function for creating tasks
def create_task(
    task_type: TaskType,
    url: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    priority: TaskPriority = TaskPriority.NORMAL,
    **kwargs
) -> str:
    """
    Create a new task of the specified type with flexible parameters
    
    Args:
        task_type: Type of task to create (TaskType enum)
        url: Optional URL for the task
        user_id: Optional user ID for the task
        session_id: Optional session ID for the task
        priority: Task priority (default: NORMAL)
        **kwargs: Additional task-specific parameters that will be added to metadata
        
    Returns:
        task_id: The created task ID
        
    Examples:
        # Create scraping task
        task_id = create_task(
            TaskType.SCRAPING,
            url="https://example.com",
            force_refresh=True,
            block_images=False
        )
        

        
        # Create content analysis task
        task_id = create_task(
            TaskType.CONTENT_ANALYSIS,
            content="Some content to analyze",
            analysis_type="sentiment"
        )
    """
    try:
        logger.info(f"Creating {task_type.value} task with parameters: {kwargs}")
        
        # Build metadata with all provided parameters
        metadata = {
            "request_type": task_type.value,
            "url": url,
            **kwargs
        }
        
        # Remove None values from metadata
        metadata = {k: v for k, v in metadata.items() if v is not None}
        
        logger.info(f"Task metadata: {metadata}")
        
        task_id = task_manager.create_task(
            task_type=task_type,
            task_metadata=metadata,
            user_id=user_id,
            session_id=session_id,
            priority=priority
        )
        
        logger.info(f"Successfully created {task_type.value} task with ID: {task_id}")
        return task_id
        
    except Exception as e:
        logger.error(f"Error creating {task_type.value} task: {e}")
        raise


def start_task(task_id: str) -> bool:
    """Start a task"""
    try:
        logger.info(f"Starting task: {task_id}")
        result = task_manager.start_task(task_id)
        if result:
            logger.info(f"Successfully started task: {task_id}")
        else:
            logger.error(f"Failed to start task: {task_id}")
        return result
    except Exception as e:
        logger.error(f"Error starting task {task_id}: {e}")
        return False


def update_task_progress(
    task_id: str,
    step_number: int,
    step_name: str,
    progress: Optional[float] = None
) -> bool:
    """Update task progress"""
    return task_manager.update_task_progress(task_id, step_number, step_name, progress)


def complete_task(task_id: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
    """Complete a task"""
    return task_manager.complete_task(task_id, metadata)


def fail_task(task_id: str, error_message: str, retry: bool = False) -> bool:
    """Fail a task"""
    return task_manager.fail_task(task_id, error_message, retry)


def get_task_status(task_id: str) -> Optional[Task]:
    """Get task status"""
    return task_manager.get_task_status(task_id)


def initialize_task_manager():
    """Initialize task manager and MongoDB connection"""
    return task_manager.connect()


def cleanup_task_manager():
    """Cleanup task manager and MongoDB connection"""
    task_manager.disconnect()
