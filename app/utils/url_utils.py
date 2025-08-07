import hashlib
import time
from urllib.parse import urlparse


def generate_task_id(url: str) -> str:
    """Generate a unique task ID based on URL"""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    timestamp = str(int(time.time()))
    return f"task_{url_hash}_{timestamp}"


def generate_cache_key(url: str) -> str:
    """Generate cache key for URL"""
    return f"scrape_cache:{hashlib.md5(url.encode()).hexdigest()}"


def parse_url_domain(url: str) -> str:
    """Extract domain from URL"""
    parsed = urlparse(url)
    return parsed.netloc.lower()


def is_valid_url(url: str) -> bool:
    """Validate URL format"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False 