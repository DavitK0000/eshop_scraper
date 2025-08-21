from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from app.config import settings
from app.models import TaskStatusResponse
from app.utils import generate_cache_key
from app.logging_config import get_logger

logger = get_logger(__name__)


class CacheService:
    """In-memory cache service for scraped results (Redis removed)"""
    
    def __init__(self):
        self._cache = {}
        self._connected = True
    
    def _connect(self):
        """Connect method - always succeeds for in-memory cache"""
        pass
    
    def is_connected(self) -> bool:
        """Check if cache is available"""
        return self._connected
    
    def get_cached_result(self, url: str) -> Optional[TaskStatusResponse]:
        """Get cached scraping result"""
        if not self.is_connected():
            return None
        
        try:
            cache_key = generate_cache_key(url)
            cached_data = self._cache.get(cache_key)
            
            if cached_data:
                # Check if cache entry has expired
                if datetime.now() > cached_data['expires_at']:
                    # Remove expired entry
                    del self._cache[cache_key]
                    return None
                
                # Return cached data
                return cached_data['data']
            
        except Exception as e:
            logger.error(f"Error retrieving cached result: {e}")
        
        return None
    
    def cache_result(self, url: str, response: TaskStatusResponse, ttl: Optional[int] = None) -> bool:
        """Cache scraping result"""
        if not self.is_connected():
            return False
        
        try:
            cache_key = generate_cache_key(url)
            ttl = ttl or settings.CACHE_TTL
            
            # Calculate expiration time
            expires_at = datetime.now() + timedelta(seconds=ttl)
            
            # Store in memory cache
            self._cache[cache_key] = {
                'data': response,
                'expires_at': expires_at
            }
            
            logger.info(f"Cached result for {url} with TTL {ttl}s")
            return True
            
        except Exception as e:
            logger.error(f"Error caching result: {e}")
            return False
    
    def invalidate_cache(self, url: str) -> bool:
        """Remove cached result for URL"""
        if not self.is_connected():
            return False
        
        try:
            cache_key = generate_cache_key(url)
            if cache_key in self._cache:
                del self._cache[cache_key]
                logger.info(f"Invalidated cache for {url}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            return False
    
    def clear_all_cache(self) -> bool:
        """Clear all cached results"""
        if not self.is_connected():
            return False
        
        try:
            # Clear all cache entries
            cache_size = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared {cache_size} cached results")
            return True
                
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.is_connected():
            return {"error": "Cache not available"}
        
        try:
            # Clean up expired entries first
            current_time = datetime.now()
            expired_keys = [
                key for key, value in self._cache.items() 
                if current_time > value['expires_at']
            ]
            for key in expired_keys:
                del self._cache[key]
            
            stats = {
                "total_cached_items": len(self._cache),
                "cache_ttl": settings.CACHE_TTL,
                "cache_type": "in-memory",
                "expired_entries_cleaned": len(expired_keys)
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}


# Global cache service instance
cache_service = CacheService() 