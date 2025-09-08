"""
Scheduler service for running periodic tasks.

This module provides a scheduling service that runs cleanup jobs and other
periodic tasks at specified intervals.
"""

import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Callable, Dict, Any
import asyncio

from ..utils.task_management import task_manager
from ..config import settings

logger = logging.getLogger(__name__)


class SchedulerService:
    """Service for managing periodic tasks and cleanup jobs"""
    
    def __init__(self):
        self.running = False
        self.cleanup_thread: Optional[threading.Thread] = None
        self.cleanup_interval_hours = 24  # Default: 24 hours
        self.last_cleanup: Optional[datetime] = None
        self.cleanup_days_threshold = 2  # Default: remove tasks older than 2 days
        
        # Load configuration
        self._load_config()
    
    def _load_config(self):
        """Load configuration from settings"""
        try:
            # Get cleanup interval from environment or use default
            cleanup_hours = getattr(settings, 'CLEANUP_INTERVAL_HOURS', 24)
            if isinstance(cleanup_hours, str):
                cleanup_hours = int(cleanup_hours)
            self.cleanup_interval_hours = max(1, cleanup_hours)  # Minimum 1 hour
            
            # Get cleanup threshold from environment or use default
            cleanup_days = getattr(settings, 'CLEANUP_DAYS_THRESHOLD', 30)
            if isinstance(cleanup_days, str):
                cleanup_days = int(cleanup_days)
            self.cleanup_days_threshold = max(1, cleanup_days)  # Minimum 1 day
            
            logger.info(f"Scheduler configured: cleanup every {self.cleanup_interval_hours} hours, "
                       f"remove tasks older than {self.cleanup_days_threshold} days")
            
        except Exception as e:
            logger.warning(f"Failed to load scheduler configuration, using defaults: {e}")
    
    def start(self):
        """Start the scheduler service"""
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        logger.info("Starting scheduler service...")
        self.running = True
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_worker,
            daemon=True,
            name="CleanupWorker"
        )
        self.cleanup_thread.start()
        
        logger.info("Scheduler service started successfully")
    
    def stop(self):
        """Stop the scheduler service"""
        if not self.running:
            logger.warning("Scheduler is not running")
            return
        
        logger.info("Stopping scheduler service...")
        self.running = False
        
        # Wait for cleanup thread to finish
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=10)
            if self.cleanup_thread.is_alive():
                logger.warning("Cleanup thread did not stop gracefully")
        
        logger.info("Scheduler service stopped")
    
    def _cleanup_worker(self):
        """Background worker for running cleanup tasks"""
        logger.info(f"Cleanup worker started, will run every {self.cleanup_interval_hours} hours")
        
        while self.running:
            try:
                # Run initial cleanup if this is the first run
                if self.last_cleanup is None:
                    self._run_cleanup()
                
                # Calculate next cleanup time
                next_cleanup = datetime.now(timezone.utc) + timedelta(hours=self.cleanup_interval_hours)
                logger.info(f"Next cleanup scheduled for: {next_cleanup}")
                
                # Sleep until next cleanup time or until stopped
                while self.running and datetime.now(timezone.utc) < next_cleanup:
                    time.sleep(60)  # Check every minute
                
                # Run cleanup if still running
                if self.running:
                    self._run_cleanup()
                    
            except Exception as e:
                logger.error(f"Error in cleanup worker: {e}")
                # Wait a bit before retrying
                time.sleep(300)  # 5 minutes
    
    def _run_cleanup(self):
        """Execute the cleanup of old tasks"""
        try:
            logger.info("Starting scheduled cleanup of old tasks...")
            
            # Ensure task manager is connected
            if not task_manager.mongodb_available:
                logger.warning("MongoDB not available, skipping cleanup")
                return
            
            # Run cleanup
            deleted_count = task_manager.db_ops.cleanup_old_tasks(self.cleanup_days_threshold)
            
            self.last_cleanup = datetime.now(timezone.utc)
            logger.info(f"Cleanup completed: removed {deleted_count} old tasks. "
                       f"Next cleanup in {self.cleanup_interval_hours} hours")
            
        except Exception as e:
            logger.error(f"Failed to run cleanup: {e}")
            self.last_cleanup = datetime.now(timezone.utc)  # Still update timestamp to avoid immediate retry
    
    def run_cleanup_now(self) -> int:
        """Manually trigger cleanup now and return number of deleted tasks"""
        try:
            logger.info("Manual cleanup triggered")
            
            if not task_manager.mongodb_available:
                logger.warning("MongoDB not available, cannot run cleanup")
                return 0
            
            deleted_count = task_manager.db_ops.cleanup_old_tasks(self.cleanup_days_threshold)
            self.last_cleanup = datetime.now(timezone.utc)
            
            logger.info(f"Manual cleanup completed: removed {deleted_count} old tasks")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to run manual cleanup: {e}")
            return 0
    
    def get_status(self) -> Dict[str, Any]:
        """Get current scheduler status"""
        return {
            "running": self.running,
            "cleanup_interval_hours": self.cleanup_interval_hours,
            "cleanup_days_threshold": self.cleanup_days_threshold,
            "last_cleanup": self.last_cleanup.isoformat() if self.last_cleanup else None,
            "next_cleanup": (
                (self.last_cleanup + timedelta(hours=self.cleanup_interval_hours)).isoformat()
                if self.last_cleanup else None
            ),
            "mongodb_available": task_manager.mongodb_available if hasattr(task_manager, 'mongodb_available') else False
        }
    
    def update_config(self, cleanup_interval_hours: Optional[int] = None, 
                     cleanup_days_threshold: Optional[int] = None):
        """Update scheduler configuration"""
        if cleanup_interval_hours is not None:
            self.cleanup_interval_hours = max(1, cleanup_interval_hours)
            logger.info(f"Cleanup interval updated to {self.cleanup_interval_hours} hours")
        
        if cleanup_days_threshold is not None:
            self.cleanup_days_threshold = max(1, cleanup_days_threshold)
            logger.info(f"Cleanup threshold updated to {self.cleanup_days_threshold} days")
        
        # Restart scheduler if running to apply new configuration
        if self.running:
            logger.info("Restarting scheduler with new configuration...")
            self.stop()
            time.sleep(1)  # Brief pause
            self.start()


# Global scheduler instance
scheduler_service = SchedulerService()


def start_scheduler():
    """Start the global scheduler service"""
    scheduler_service.start()


def stop_scheduler():
    """Stop the global scheduler service"""
    scheduler_service.stop()


def get_scheduler_status():
    """Get the current scheduler status"""
    return scheduler_service.get_status()


def run_cleanup_now():
    """Manually trigger cleanup now"""
    return scheduler_service.run_cleanup_now()
