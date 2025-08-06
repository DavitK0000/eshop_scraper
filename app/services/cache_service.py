import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import redis
from app.config import settings
from app.models import ProductInfo, ScrapeResponse
from app.utils import generate_cache_key
from app.logging_config import get_logger
import os

logger = get_logger(__name__)


class CacheService:
    """Redis-based cache service for scraped results"""
    
    def __init__(self):
        self.redis_client = None
        self._connected = False
    
    def _connect(self):
        """Connect to Redis (lazy loading)"""
        if self.redis_client is not None:
            return
        
        # Check if Redis URL indicates Redis is not available
        redis_url = settings.REDIS_URL
        if not redis_url or redis_url == "redis://localhost:9999" or "localhost:9999" in redis_url:
            logger.info("Redis URL indicates Redis is not available - caching disabled")
            self.redis_client = None
            self._connected = False
            return
        
        # Check if we're in a no-Redis environment
        if os.getenv('REDIS_DISABLED', 'false').lower() == 'true':
            logger.info("Redis disabled via environment variable - caching disabled")
            self.redis_client = None
            self._connected = False
            return
        
        try:
            self.redis_client = redis.from_url(
                redis_url,
                db=settings.REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=2,  # Very short timeout
                socket_timeout=2
            )
            # Test connection
            self.redis_client.ping()
            self._connected = True
            logger.info("Successfully connected to Redis")
        except Exception as e:
            logger.info(f"Redis not available - caching will be disabled: {e}")
            self.redis_client = None
            self._connected = False
    
    def is_connected(self) -> bool:
        """Check if Redis is connected"""
        if self.redis_client is None:
            self._connect()
        
        if not self.redis_client:
            return False
        
        try:
            self.redis_client.ping()
            return True
        except Exception as e:
            logger.debug(f"Redis ping failed: {e}")
            self._connected = False
            return False
    
    def get_cached_result(self, url: str) -> Optional[ScrapeResponse]:
        """Get cached scraping result"""
        if not self.is_connected():
            return None
        
        try:
            cache_key = generate_cache_key(url)
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                data = json.loads(cached_data)
                # Convert string dates back to datetime objects
                data['created_at'] = datetime.fromisoformat(data['created_at'])
                if data.get('completed_at'):
                    data['completed_at'] = datetime.fromisoformat(data['completed_at'])
                
                # Reconstruct ProductInfo object
                if data.get('product_info'):
                    data['product_info'] = ProductInfo(**data['product_info'])
                
                return ScrapeResponse(**data)
            
        except Exception as e:
            logger.error(f"Error retrieving cached result: {e}")
        
        return None
    
    def cache_result(self, url: str, response: ScrapeResponse, ttl: Optional[int] = None) -> bool:
        """Cache scraping result"""
        if not self.is_connected():
            return False
        
        try:
            cache_key = generate_cache_key(url)
            ttl = ttl or settings.CACHE_TTL
            
            # Convert response to dict for JSON serialization
            data = response.dict()
            
            # Convert datetime objects to ISO format strings
            data['created_at'] = data['created_at'].isoformat()
            if data.get('completed_at'):
                data['completed_at'] = data['completed_at'].isoformat()
            
            # Store in Redis
            self.redis_client.setex(
                cache_key,
                ttl,
                json.dumps(data, default=str)
            )
            
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
            result = self.redis_client.delete(cache_key)
            if result:
                logger.info(f"Invalidated cache for {url}")
            return bool(result)
            
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            return False
    
    def clear_all_cache(self) -> bool:
        """Clear all cached results"""
        if not self.is_connected():
            return False
        
        try:
            # Get all keys with scrape_cache prefix
            pattern = "scrape_cache:*"
            keys = self.redis_client.keys(pattern)
            
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Cleared {deleted} cached results")
                return True
            else:
                logger.info("No cached results to clear")
                return True
                
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.is_connected():
            return {"error": "Redis not connected"}
        
        try:
            pattern = "scrape_cache:*"
            keys = self.redis_client.keys(pattern)
            
            stats = {
                "total_cached_items": len(keys),
                "cache_ttl": settings.CACHE_TTL,
                "redis_connected": True
            }
            
            # Get memory usage if available
            try:
                info = self.redis_client.info('memory')
                stats['redis_memory_usage'] = info.get('used_memory_human', 'N/A')
            except Exception:
                stats['redis_memory_usage'] = 'N/A'
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}


# Global cache service instance
cache_service = CacheService() 