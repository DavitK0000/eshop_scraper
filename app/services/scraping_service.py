import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from app.models import ProductInfo, ScrapeResponse, TaskStatus
from app.scrapers.factory import ScraperFactory
from app.utils import generate_task_id, proxy_manager, user_agent_manager, is_valid_url
from app.config import settings

logger = logging.getLogger(__name__)


class ScrapingService:
    """Main service for orchestrating scraping operations"""
    
    def __init__(self):
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
    
    async def scrape_product(
        self,
        url: str,
        force_refresh: bool = False,
        proxy: Optional[str] = None,
        user_agent: Optional[str] = None,
        block_images: bool = True
    ) -> ScrapeResponse:
        """
        Scrape product information from URL
        
        Args:
            url: Product URL to scrape
            force_refresh: Whether to bypass cache
            proxy: Custom proxy to use
            user_agent: Custom user agent to use
            
        Returns:
            ScrapeResponse with product information
        """
        task_id = generate_task_id(url)
        
        # Initialize response
        response = ScrapeResponse(
            task_id=task_id,
            status=TaskStatus.PENDING,
            url=url,
            created_at=datetime.now()
        )
        
        # Store task info
        self.active_tasks[task_id] = {
            'status': TaskStatus.PENDING,
            'created_at': datetime.now(),
            'url': url
        }
        
        try:
            # Validate URL
            if not is_valid_url(url):
                raise ValueError(f"Invalid URL format: {url}")
            
            # Update task status
            self._update_task_status(task_id, TaskStatus.RUNNING, "Starting scraping process")
            
            # Get proxy and user agent if not provided
            if not proxy and settings.ROTATE_PROXIES:
                proxy = proxy_manager.get_proxy()
            
            if not user_agent and settings.ROTATE_USER_AGENTS:
                user_agent = user_agent_manager.get_user_agent()
            
            # Create scraper
            scraper = ScraperFactory.create_scraper(url, proxy, user_agent, block_images)
            
            # Perform scraping with retry logic
            product_info = await self._scrape_with_retry(scraper)
            
            # Update response
            response.status = TaskStatus.COMPLETED
            response.product_info = product_info
            response.completed_at = datetime.now()
            
            # Update task status
            self._update_task_status(task_id, TaskStatus.COMPLETED, "Scraping completed successfully")
            
            logger.info(f"Successfully scraped product from {url}")
            
        except Exception as e:
            error_msg = f"Scraping failed: {str(e)}"
            logger.error(f"Error scraping {url}: {e}")
            
            # Update response with error
            response.status = TaskStatus.FAILED
            response.error = error_msg
            response.completed_at = datetime.now()
            
            # Update task status
            self._update_task_status(task_id, TaskStatus.FAILED, error_msg)
        
        return response
    
    async def _scrape_with_retry(self, scraper) -> ProductInfo:
        """Scrape with retry logic"""
        last_exception = None
        
        for attempt in range(settings.MAX_RETRIES):
            try:
                logger.info(f"Scraping attempt {attempt + 1}/{settings.MAX_RETRIES}")
                return await scraper.scrape()
                
            except Exception as e:
                last_exception = e
                logger.warning(f"Scraping attempt {attempt + 1} failed: {e}")
                
                if attempt < settings.MAX_RETRIES - 1:
                    # Wait before retry (exponential backoff)
                    wait_time = 2 ** attempt
                    logger.info(f"Waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)
        
        # All retries failed
        raise last_exception or Exception("Scraping failed after all retries")
    
    def _update_task_status(self, task_id: str, status: TaskStatus, message: str = None):
        """Update task status"""
        if task_id in self.active_tasks:
            self.active_tasks[task_id].update({
                'status': status,
                'updated_at': datetime.now(),
                'message': message
            })
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status"""
        return self.active_tasks.get(task_id)
    
    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Get all active tasks"""
        return self.active_tasks.copy()
    
    def cleanup_completed_tasks(self, max_age_hours: int = 24):
        """Clean up old completed tasks"""
        cutoff_time = datetime.now().replace(hour=datetime.now().hour - max_age_hours)
        
        tasks_to_remove = []
        for task_id, task_info in self.active_tasks.items():
            if (task_info['status'] in [TaskStatus.COMPLETED, TaskStatus.FAILED] and
                task_info.get('updated_at', task_info['created_at']) < cutoff_time):
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self.active_tasks[task_id]
        
        if tasks_to_remove:
            logger.info(f"Cleaned up {len(tasks_to_remove)} old tasks")


# Global scraping service instance
scraping_service = ScrapingService() 