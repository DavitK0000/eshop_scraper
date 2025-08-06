import hashlib
import hmac
import time
import secrets
import re
import os
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import redis
import json
from urllib.parse import urlparse
import ipaddress
from fastapi.responses import JSONResponse

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

# Security configuration
SECURITY_CONFIG = {
    "MAX_REQUESTS_PER_MINUTE": 60,
    "MAX_REQUESTS_PER_HOUR": 1000,
    "MAX_REQUESTS_PER_DAY": 10000,
    "BLOCKED_IPS_TTL": 3600,  # 1 hour
    "SUSPICIOUS_ACTIVITY_TTL": 1800,  # 30 minutes
    "MAX_URL_LENGTH": 2048,
    "ALLOWED_DOMAINS": [
        "amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr", "amazon.it", "amazon.es",
        "ebay.com", "ebay.co.uk", "ebay.de", "ebay.fr", "ebay.it", "ebay.es", "ebay.nl",
        "bol.com", "cdiscount.com", "otto.de", "jd.com"
    ],
    "BLOCKED_USER_AGENTS": [
        "bot", "crawler", "spider", "scraper", "curl", "wget", "python-requests"
    ],
    "MAX_CONCURRENT_REQUESTS_PER_IP": 5,
    "RATE_LIMIT_WINDOW": 60,  # seconds
}

# Initialize Redis for security features (lazy loading)
security_redis = None
security_redis_initialized = False

def _init_security_redis():
    """Initialize security Redis connection (lazy loading)"""
    global security_redis, security_redis_initialized
    
    if security_redis_initialized:
        return
    
    # Check if Redis URL indicates Redis is not available
    redis_url = settings.REDIS_URL
    if not redis_url or redis_url == "redis://localhost:9999" or "localhost:9999" in redis_url:
        logger.info("Redis URL indicates Redis is not available - security features disabled")
        security_redis = None
        security_redis_initialized = True
        return
    
    # Check if we're in a no-Redis environment
    if os.getenv('REDIS_DISABLED', 'false').lower() == 'true':
        logger.info("Redis disabled via environment variable - security features disabled")
        security_redis = None
        security_redis_initialized = True
        return
    
    try:
        security_redis = redis.from_url(redis_url, db=1, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
        # Test the connection
        security_redis.ping()
        logger.info("Security Redis connected successfully")
    except Exception as e:
        logger.info(f"Security Redis not available - security features will be disabled: {e}")
        security_redis = None
    
    security_redis_initialized = True

# API Key management
API_KEYS = {
    # Demo key for testing (replace with your actual keys)
    "demo_key_19990802": {
        "name": "Demo User",
        "rate_limit": 100,  # requests per minute
        "daily_limit": 1000,
        "allowed_domains": SECURITY_CONFIG["ALLOWED_DOMAINS"],
        "created_at": datetime.now().isoformat()
    }
}

# Load API keys from environment
def load_api_keys_from_env():
    """Load API keys from environment variables"""
    for i in range(1, 11):  # Support up to 10 API keys
        key = os.getenv(f"API_KEY_{i}")
        name = os.getenv(f"API_KEY_{i}_NAME", f"User_{i}")
        rate_limit = int(os.getenv(f"API_KEY_{i}_RATE_LIMIT", "100"))
        daily_limit = int(os.getenv(f"API_KEY_{i}_DAILY_LIMIT", "1000"))
        
        if key:
            API_KEYS[key] = {
                "name": name,
                "rate_limit": rate_limit,
                "daily_limit": daily_limit,
                "allowed_domains": SECURITY_CONFIG["ALLOWED_DOMAINS"],
                "created_at": datetime.now().isoformat()
            }

# Load API keys on module import
load_api_keys_from_env()

class SecurityManager:
    """Manages security features for the API"""
    
    def __init__(self):
        self.redis = None
        self.blocked_ips = set()
        self.suspicious_ips = set()
    
    def _get_redis(self):
        """Get Redis connection (lazy loading)"""
        if self.redis is None:
            _init_security_redis()
            self.redis = security_redis
        return self.redis
    
    def is_ip_blocked(self, ip: str) -> bool:
        """Check if IP is blocked"""
        redis_client = self._get_redis()
        if not redis_client:
            return ip in self.blocked_ips
        
        return redis_client.exists(f"blocked_ip:{ip}")
    
    def block_ip(self, ip: str, reason: str = "Abuse detected"):
        """Block an IP address"""
        redis_client = self._get_redis()
        if not redis_client:
            self.blocked_ips.add(ip)
            return
        
        redis_client.setex(
            f"blocked_ip:{ip}",
            SECURITY_CONFIG["BLOCKED_IPS_TTL"],
            json.dumps({"reason": reason, "blocked_at": datetime.now().isoformat()})
        )
        logger.warning(f"IP {ip} blocked: {reason}")
    
    def is_suspicious_activity(self, ip: str) -> bool:
        """Check for suspicious activity patterns"""
        redis_client = self._get_redis()
        if not redis_client:
            return ip in self.suspicious_ips
        
        return redis_client.exists(f"suspicious:{ip}")
    
    def mark_suspicious(self, ip: str, reason: str):
        """Mark IP as suspicious"""
        redis_client = self._get_redis()
        if not redis_client:
            self.suspicious_ips.add(ip)
            return
        
        redis_client.setex(
            f"suspicious:{ip}",
            SECURITY_CONFIG["SUSPICIOUS_ACTIVITY_TTL"],
            json.dumps({"reason": reason, "marked_at": datetime.now().isoformat()})
        )
    
    def check_rate_limit(self, identifier: str, limit: int, window: int = 60) -> bool:
        """Check rate limit for an identifier (IP or API key)"""
        redis_client = self._get_redis()
        if not redis_client:
            return True  # Skip rate limiting if Redis is not available
        
        key = f"rate_limit:{identifier}:{int(time.time() // window)}"
        current = redis_client.incr(key)
        
        if current == 1:
            redis_client.expire(key, window)
        
        return current <= limit
    
    def get_client_identifier(self, request: Request) -> str:
        """Get unique identifier for rate limiting"""
        # Try to get real IP from headers
        real_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or
            request.headers.get("X-Real-IP") or
            request.headers.get("X-Client-IP") or
            request.client.host
        )
        return real_ip
    
    def validate_url(self, url: str, allowed_domains: List[str]) -> bool:
        """Validate URL against allowed domains"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove port if present
            if ":" in domain:
                domain = domain.split(":")[0]
            
            # Check if domain is in allowed list
            return any(domain.endswith(allowed_domain) for allowed_domain in allowed_domains)
        except Exception:
            return False
    
    def validate_user_agent(self, user_agent: str) -> bool:
        """Validate user agent for suspicious patterns"""
        if not user_agent:
            return False
        
        user_agent_lower = user_agent.lower()
        return not any(blocked in user_agent_lower for blocked in SECURITY_CONFIG["BLOCKED_USER_AGENTS"])
    
    def is_valid_ip(self, ip: str) -> bool:
        """Check if IP address is valid and not private"""
        try:
            ip_obj = ipaddress.ip_address(ip)
            return not ip_obj.is_private and not ip_obj.is_loopback
        except ValueError:
            return False

# Global security manager instance
security_manager = SecurityManager()

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)

def get_api_key(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[str]:
    """Extract and validate API key from request"""
    if not credentials:
        return None
    
    api_key = credentials.credentials
    if api_key in API_KEYS:
        return api_key
    
    return None

def validate_request_security(request: Request, api_key: Optional[str] = None):
    """Validate request security - DISABLED FOR DEVELOPMENT"""
    # DEVELOPMENT MODE: Skip all security validation
    # TODO: Re-enable security checks for production by uncommenting the code below
    pass
    
    # PRODUCTION CODE (commented out for development):
    # client_ip = security_manager.get_client_identifier(request)
    # 
    # # Check if IP is blocked
    # if security_manager.is_ip_blocked(client_ip):
    #     raise HTTPException(status_code=403, detail="Access denied")
    # 
    # # Check for suspicious activity
    # if security_manager.is_suspicious_activity(client_ip):
    #     raise HTTPException(status_code=429, detail="Too many requests")
    # 
    # # Rate limiting
    # if api_key:
    #     # API key rate limiting
    #     key_info = API_KEYS[api_key]
    #     if not security_manager.check_rate_limit(f"api:{api_key}", key_info["rate_limit"]):
    #         raise HTTPException(status_code=429, detail="Rate limit exceeded")
    #     
    #     # Daily limit check
    #     daily_key = f"daily:{api_key}:{datetime.now().strftime('%Y-%m-%d')}"
    #     if not security_manager.check_rate_limit(daily_key, key_info["daily_limit"], 86400):
    #         raise HTTPException(status_code=429, detail="Daily limit exceeded")
    # else:
    #     # Anonymous rate limiting (more restrictive)
    #     if not security_manager.check_rate_limit(f"ip:{client_ip}", 10):  # 10 requests per minute
    #         security_manager.mark_suspicious(client_ip, "Rate limit exceeded")
    #         raise HTTPException(status_code=429, detail="Rate limit exceeded")
    # 
    # # Validate user agent
    # user_agent = request.headers.get("User-Agent", "")
    # if not security_manager.validate_user_agent(user_agent):
    #     security_manager.mark_suspicious(client_ip, "Suspicious user agent")
    #     raise HTTPException(status_code=400, detail="Invalid user agent")
    # 
    # # Check for concurrent requests
    # if not security_manager.check_rate_limit(f"concurrent:{client_ip}", SECURITY_CONFIG["MAX_CONCURRENT_REQUESTS_PER_IP"], 1):
    #     raise HTTPException(status_code=429, detail="Too many concurrent requests")

def validate_scrape_request(url: str, api_key: Optional[str] = None):
    """Validate scrape request parameters - DISABLED FOR DEVELOPMENT"""
    # DEVELOPMENT MODE: Skip all URL validation
    # TODO: Re-enable URL validation for production by uncommenting the code below
    pass
    
    # PRODUCTION CODE (commented out for development):
    # # URL length validation
    # if len(url) > SECURITY_CONFIG["MAX_URL_LENGTH"]:
    #     raise HTTPException(status_code=400, detail="URL too long")
    # 
    # # URL format validation
    # if not url.startswith(("http://", "https://")):
    #     raise HTTPException(status_code=400, detail="Invalid URL format")
    # 
    # # Domain validation
    # allowed_domains = API_KEYS.get(api_key, {}).get("allowed_domains", SECURITY_CONFIG["ALLOWED_DOMAINS"]) if api_key else SECURITY_CONFIG["ALLOWED_DOMAINS"]
    # 
    # if not security_manager.validate_url(url, allowed_domains):
    #     raise HTTPException(status_code=400, detail="Domain not supported")

def log_security_event(event_type: str, details: Dict):
    """Log security events"""
    logger.warning(f"Security event - {event_type}: {json.dumps(details)}")
    
    _init_security_redis()
    if security_redis:
        try:
            security_redis.lpush(
                "security_events",
                json.dumps({
                    "type": event_type,
                    "timestamp": datetime.now().isoformat(),
                    "details": details
                })
            )
            security_redis.ltrim("security_events", 0, 999)  # Keep last 1000 events
        except Exception as e:
            logger.warning(f"Failed to log security event to Redis: {e}")

# Middleware for security checks
async def security_middleware(request: Request, call_next):
    """Security middleware for all requests - DISABLED FOR DEVELOPMENT"""
    # DEVELOPMENT MODE: Pass all requests without security checks
    # TODO: Re-enable security checks for production by uncommenting the code below
    
    # Simply pass the request through without any validation
    response = await call_next(request)
    return response
    
    # PRODUCTION CODE (commented out for development):
    # client_ip = security_manager.get_client_identifier(request)
    # 
    # # Basic security checks
    # try:
    #     # Check if IP is blocked (only if Redis is available)
    #     _init_security_redis()
    #     if security_redis and security_manager.is_ip_blocked(client_ip):
    #         return JSONResponse(
    #             status_code=403,
    #             content={"detail": "Access denied"}
    #         )
    #     
    #     # Check for suspicious activity (only if Redis is available)
    #     if security_redis and security_manager.is_suspicious_activity(client_ip):
    #         return JSONResponse(
    #             status_code=429,
    #             content={"detail": "Too many requests"}
    #         )
    #     
    #     # Log request for monitoring (only if Redis is available)
    #     if security_redis:
    #         try:
    #             security_redis.incr(f"requests:{client_ip}:{datetime.now().strftime('%Y-%m-%d')}")
    #         except Exception as e:
    #             logger.warning(f"Failed to log request to Redis: {e}")
    #     
    #     response = await call_next(request)
    #     
    #     # Log security events for certain response codes (only if Redis is available)
    #     if response.status_code in [403, 429, 400] and security_redis:
    #         try:
    #             log_security_event("security_violation", {
    #                 "ip": client_ip,
    #                 "status_code": response.status_code,
    #                 "path": str(request.url.path),
    #                 "method": request.method
    #             })
    #         except Exception as e:
    #             logger.warning(f"Failed to log security event: {e}")
    #     
    #     return response
    #     
    # except Exception as e:
    #     logger.error(f"Security middleware error: {e}")
    #     # If there's a Redis connection error, still allow the request to proceed
    #     if "Error 10061" in str(e) or "Connection refused" in str(e):
    #         logger.warning("Redis connection failed - proceeding without security checks")
    #         try:
    #             response = await call_next(request)
    #             return response
    #         except Exception as inner_e:
    #             logger.error(f"Request processing failed: {inner_e}")
    #             return JSONResponse(
    #                 status_code=500,
    #                 content={"detail": "Internal server error"}
    #             )
    #     else:
    #         return JSONResponse(
    #             status_code=500,
    #             content={"detail": "Internal server error"}
    #         )

# Utility functions for monitoring
def get_security_stats() -> Dict:
    """Get security statistics"""
    _init_security_redis()
    if not security_redis:
        return {"error": "Redis not available"}
    
    stats = {
        "blocked_ips": len(security_redis.keys("blocked_ip:*")),
        "suspicious_ips": len(security_redis.keys("suspicious:*")),
        "total_requests_today": 0,
        "security_events": []
    }
    
    # Count today's requests
    today = datetime.now().strftime('%Y-%m-%d')
    request_keys = security_redis.keys(f"requests:*:{today}")
    for key in request_keys:
        stats["total_requests_today"] += int(security_redis.get(key) or 0)
    
    # Get recent security events
    events = security_redis.lrange("security_events", 0, 9)
    stats["security_events"] = [json.loads(event) for event in events]
    
    return stats

def cleanup_security_data():
    """Clean up old security data"""
    _init_security_redis()
    if not security_redis:
        logger.info("Redis not available - skipping security data cleanup")
        return
    
    try:
        # Clean up old rate limit keys (older than 1 hour)
        old_keys = security_redis.keys("rate_limit:*")
        for key in old_keys:
            if security_redis.ttl(key) == -1:  # No expiration set
                security_redis.delete(key)
        
        # Clean up old request counters (older than 7 days)
        old_request_keys = security_redis.keys("requests:*")
        for key in old_request_keys:
            date_str = key.split(":")[-1]
            try:
                key_date = datetime.strptime(date_str, '%Y-%m-%d')
                if (datetime.now() - key_date).days > 7:
                    security_redis.delete(key)
            except ValueError:
                continue
        
        logger.info("Security data cleanup completed successfully")
    except Exception as e:
        logger.warning(f"Security data cleanup failed: {e}")
        # Don't raise the exception - allow the application to start 