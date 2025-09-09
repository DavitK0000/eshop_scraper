"""
Session Management Service for tracking task sessions in MongoDB.
Handles session creation, updates, and cleanup for different task types.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict

try:
    from pymongo import MongoClient, ASCENDING, DESCENDING, IndexModel
    from pymongo.errors import PyMongoError, ConnectionFailure, ServerSelectionTimeoutError
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False
    MongoClient = None

from app.config import settings
from app.models import SessionInfo

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """Session data structure for MongoDB storage"""
    short_id: str
    task_type: str
    task_id: str
    created_at: datetime
    updated_at: datetime
    user_id: Optional[str] = None
    status: str = "active"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage"""
        data = asdict(self)
        # Convert datetime objects to ISO format for JSON serialization
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Session':
        """Create Session from dictionary"""
        # Filter out MongoDB-specific fields
        filtered_data = {k: v for k, v in data.items() if not k.startswith('_')}
        
        # Convert ISO format strings back to datetime objects
        for key, value in filtered_data.items():
            if key in ['created_at', 'updated_at'] and value:
                if isinstance(value, str):
                    filtered_data[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return cls(**filtered_data)


class SessionManager:
    """MongoDB session management"""
    
    def __init__(self, connection_string: str = None, database_name: str = None):
        self.connection_string = connection_string or getattr(settings, 'MONGODB_URI', 'mongodb://localhost:27017')
        self.database_name = database_name or getattr(settings, 'MONGODB_DATABASE', 'eshop_scraper')
        self.client: Optional[MongoClient] = None
        self.database = None
        self.sessions_collection = None
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
            logger.info(f"Attempting to connect to MongoDB for sessions at: {self.connection_string}")
            self.client = MongoClient(
                self.connection_string,
                maxPoolSize=self._max_pool_size,
                serverSelectionTimeoutMS=self._server_selection_timeout,
                connectTimeoutMS=self._connect_timeout,
                socketTimeoutMS=self._socket_timeout,
                retryWrites=True,
                retryReads=True,
                minPoolSize=5,
                maxIdleTimeMS=30000,
                waitQueueTimeoutMS=5000
            )
            
            # Test connection
            logger.info("Testing MongoDB connection for sessions...")
            self.client.admin.command('ping')
            logger.info("MongoDB ping successful for sessions")
            
            self.database = self.client[self.database_name]
            self.sessions_collection = self.database.sessions
            
            # Create indexes for better performance
            logger.info("Creating MongoDB indexes for sessions...")
            self._create_indexes()
            
            logger.info(f"Successfully connected to MongoDB for sessions: {self.database_name}")
            return True
                
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB for sessions: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB for sessions: {e}")
            return False
    
    def disconnect(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            self.client = None
            self.database = None
            self.sessions_collection = None
            logger.info("MongoDB connection closed for sessions")
    
    def _create_indexes(self):
        """Create database indexes for better performance"""
        try:
            # Index on short_id for fast lookups
            self.sessions_collection.create_index(
                IndexModel([("short_id", ASCENDING)])
            )
            
            # Index on task_id for fast lookups
            self.sessions_collection.create_index(
                IndexModel([("task_id", ASCENDING)], unique=True)
            )
            
            # Index on task_type for filtering by task type
            self.sessions_collection.create_index(
                IndexModel([("task_type", ASCENDING)])
            )
            
            # Index on status for filtering by status
            self.sessions_collection.create_index(
                IndexModel([("status", ASCENDING)])
            )
            
            # Index on created_at for time-based queries
            self.sessions_collection.create_index(
                IndexModel([("created_at", DESCENDING)])
            )
            
            # Index on user_id for user-based queries
            self.sessions_collection.create_index(
                IndexModel([("user_id", ASCENDING)])
            )
            
            logger.info("MongoDB indexes created successfully for sessions")
            
        except Exception as e:
            logger.warning(f"Failed to create some indexes for sessions: {e}")
    
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
            logger.info("MongoDB connection lost for sessions, attempting to reconnect...")
            return self.connect()
        return True


class SessionService:
    """Service for managing task sessions"""
    
    def __init__(self):
        self.session_manager = SessionManager()
        self.mongodb_available = False
        
    def connect(self) -> bool:
        """Connect to MongoDB"""
        try:
            self.mongodb_available = self.session_manager.connect()
            if self.mongodb_available:
                logger.info("MongoDB connection established successfully for sessions")
            else:
                logger.warning("MongoDB connection failed for sessions - sessions will not be tracked")
            return self.mongodb_available
        except Exception as e:
            logger.error(f"Error connecting to MongoDB for sessions: {e}")
            self.mongodb_available = False
            return False
    
    def disconnect(self):
        """Disconnect from MongoDB"""
        self.session_manager.disconnect()
    
    def create_session(
        self,
        short_id: str,
        task_type: str,
        task_id: str,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Create a new session for a task
        
        Args:
            short_id: Short ID associated with the session
            task_type: Type of task (e.g., 'scraping', 'scenario_generation')
            task_id: Task ID associated with the session
            user_id: Optional user ID for the session
            
        Returns:
            bool: True if session was created successfully
        """
        try:
            if not self.mongodb_available:
                logger.warning("MongoDB not available, skipping session creation")
                return False
                
            logger.info(f"Creating session for task {task_id} (type: {task_type}, short_id: {short_id})")
            
            # Ensure connection
            if not self.session_manager.ensure_connection():
                logger.error(f"Failed to ensure MongoDB connection for session creation")
                return False
            
            # Check if session already exists for this task_id
            existing_session = self.session_manager.sessions_collection.find_one({"task_id": task_id})
            if existing_session:
                logger.warning(f"Session with task_id {task_id} already exists")
                return False
            
            # Create session
            session = Session(
                short_id=short_id,
                task_type=task_type,
                task_id=task_id,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                user_id=user_id,
                status="active"
            )
            
            # Insert the session
            result = self.session_manager.sessions_collection.insert_one(session.to_dict())
            if result.inserted_id:
                logger.info(f"Session created successfully for task {task_id} with MongoDB ID: {result.inserted_id}")
                return True
            else:
                logger.error(f"Failed to insert session for task {task_id} - no inserted_id returned")
                return False
                
        except Exception as e:
            logger.error(f"Failed to create session for task {task_id}: {e}")
            return False
    
    def update_session_status(
        self,
        task_id: str,
        status: str
    ) -> bool:
        """
        Update session status
        
        Args:
            task_id: Task ID to update
            status: New status (active, completed, failed)
            
        Returns:
            bool: True if session was updated successfully
        """
        try:
            if not self.mongodb_available:
                logger.warning("MongoDB not available, skipping session update")
                return False
                
            logger.info(f"Updating session status for task {task_id} to {status}")
            
            # Ensure connection
            if not self.session_manager.ensure_connection():
                logger.error(f"Failed to ensure MongoDB connection for session update")
                return False
            
            # Update session status
            result = self.session_manager.sessions_collection.update_one(
                {"task_id": task_id},
                {
                    "$set": {
                        "status": status,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"Session status updated successfully for task {task_id}")
                return True
            else:
                logger.warning(f"Session not found or not modified for task {task_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to update session status for task {task_id}: {e}")
            return False
    
    def remove_session(self, task_id: str) -> bool:
        """
        Remove a session
        
        Args:
            task_id: Task ID to remove session for
            
        Returns:
            bool: True if session was removed successfully
        """
        try:
            if not self.mongodb_available:
                logger.warning("MongoDB not available, skipping session removal")
                return False
                
            logger.info(f"Removing session for task {task_id}")
            
            # Ensure connection
            if not self.session_manager.ensure_connection():
                logger.error(f"Failed to ensure MongoDB connection for session removal")
                return False
            
            # Remove session
            result = self.session_manager.sessions_collection.delete_one({"task_id": task_id})
            if result.deleted_count > 0:
                logger.info(f"Session removed successfully for task {task_id}")
                return True
            else:
                logger.warning(f"Session not found for task {task_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to remove session for task {task_id}: {e}")
            return False
    
    def get_session(self, task_id: str) -> Optional[Session]:
        """
        Get session by task ID
        
        Args:
            task_id: Task ID to get session for
            
        Returns:
            Session object or None if not found
        """
        try:
            if not self.mongodb_available:
                logger.warning("MongoDB not available, cannot get session")
                return None
                
            # Ensure connection
            if not self.session_manager.ensure_connection():
                logger.error(f"Failed to ensure MongoDB connection for session retrieval")
                return None
            
            # Get session
            session_doc = self.session_manager.sessions_collection.find_one({"task_id": task_id})
            if session_doc:
                return Session.from_dict(session_doc)
            return None
                
        except Exception as e:
            logger.error(f"Failed to get session for task {task_id}: {e}")
            return None
    
    def get_sessions_by_short_id(self, short_id: str) -> List[Session]:
        """
        Get all sessions for a short_id
        
        Args:
            short_id: Short ID to get sessions for
            
        Returns:
            List of Session objects
        """
        try:
            if not self.mongodb_available:
                logger.warning("MongoDB not available, cannot get sessions")
                return []
                
            # Ensure connection
            if not self.session_manager.ensure_connection():
                logger.error(f"Failed to ensure MongoDB connection for session retrieval")
                return []
            
            # Get sessions
            sessions_docs = self.session_manager.sessions_collection.find({"short_id": short_id})
            sessions = []
            for doc in sessions_docs:
                sessions.append(Session.from_dict(doc))
            return sessions
                
        except Exception as e:
            logger.error(f"Failed to get sessions for short_id {short_id}: {e}")
            return []
    
    def cleanup_old_sessions(self, days_old: int = 7) -> int:
        """
        Clean up old completed/failed sessions
        
        Args:
            days_old: Number of days old to clean up
            
        Returns:
            Number of sessions cleaned up
        """
        try:
            if not self.mongodb_available:
                logger.warning("MongoDB not available, cannot cleanup sessions")
                return 0
                
            # Ensure connection
            if not self.session_manager.ensure_connection():
                logger.error(f"Failed to ensure MongoDB connection for session cleanup")
                return 0
            
            from datetime import timedelta
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
            cutoff_date_iso = cutoff_date.isoformat()
            
            result = self.session_manager.sessions_collection.delete_many({
                "created_at": {"$lt": cutoff_date_iso},
                "status": {"$in": ["completed", "failed"]}
            })
            
            deleted_count = result.deleted_count
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old sessions")
            else:
                logger.info("No old sessions found to clean up")
            
            return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to cleanup old sessions: {e}")
            return 0


# Global instance
session_service = SessionService()


def initialize_session_service():
    """Initialize session service and MongoDB connection"""
    return session_service.connect()


def cleanup_session_service():
    """Cleanup session service and MongoDB connection"""
    session_service.disconnect()
