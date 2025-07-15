import random
import hashlib
import json
import logging
import time
import requests
from typing import Optional, Dict, Any, List
from fake_useragent import UserAgent
from app.config import settings

logger = logging.getLogger(__name__)

# Initialize UserAgent
try:
    ua = UserAgent()
except Exception as e:
    logger.warning(f"Failed to initialize UserAgent: {e}")
    ua = None


class DecodoProxyManager:
    """Manages Decodo proxy connections with authentication and session handling"""
    
    def __init__(self, username: str, password: str, proxy_endpoint: str, proxy_type: str = "http"):
        self.username = username
        self.password = password
        self.proxy_endpoint = proxy_endpoint
        self.proxy_type = proxy_type.lower()
        self.session_id = None
        self.current_proxy = None
        self.proxy_rotation_attempts = 0
        self.max_rotation_attempts = 5
        
    def _format_proxy_url(self) -> str:
        """Format proxy URL with authentication"""
        if self.proxy_type == "socks5":
            return f"socks5://{self.username}:{self.password}@{self.proxy_endpoint}"
        else:
            return f"http://{self.username}:{self.password}@{self.proxy_endpoint}"
    
    def get_proxy(self) -> Optional[str]:
        """Get current proxy URL with authentication"""
        if not self.username or not self.password or not self.proxy_endpoint:
            logger.error("Decodo proxy credentials not properly configured")
            return None
        
        proxy_url = self._format_proxy_url()
        self.current_proxy = proxy_url
        logger.info(f"Using Decodo proxy: {self.proxy_endpoint}")
        return proxy_url
    
    def rotate_proxy(self) -> Optional[str]:
        """Rotate to a new proxy session"""
        if self.proxy_rotation_attempts >= self.max_rotation_attempts:
            logger.error(f"Maximum proxy rotation attempts ({self.max_rotation_attempts}) reached")
            return None
        
        self.proxy_rotation_attempts += 1
        logger.info(f"Rotating Decodo proxy (attempt {self.proxy_rotation_attempts}/{self.max_rotation_attempts})")
        
        # For Decodo, you might need to make an API call to rotate the IP
        # This depends on your Decodo plan and API endpoints
        try:
            # Example: Make API call to rotate IP (adjust based on Decodo's API)
            # response = requests.post(
            #     f"{self.proxy_endpoint}/rotate",
            #     auth=(self.username, self.password),
            #     timeout=10
            # )
            # if response.status_code == 200:
            #     logger.info("Successfully rotated Decodo proxy IP")
            
            # For now, we'll just return the same proxy URL
            # In practice, you'd implement the actual rotation logic based on Decodo's API
            return self.get_proxy()
            
        except Exception as e:
            logger.error(f"Failed to rotate Decodo proxy: {e}")
            return self.get_proxy()
    
    def test_proxy(self) -> bool:
        """Test if the current proxy is working"""
        try:
            proxy_url = self.get_proxy()
            if not proxy_url:
                return False
            
            proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
            
            response = requests.get(
                'http://httpbin.org/ip',
                proxies=proxies,
                timeout=10
            )
            
            if response.status_code == 200:
                ip_info = response.json()
                logger.info(f"Proxy test successful. IP: {ip_info.get('origin', 'unknown')}")
                return True
            else:
                logger.warning(f"Proxy test failed with status code: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Proxy test failed: {e}")
            return False
    
    def reset_rotation_attempts(self):
        """Reset rotation attempt counter"""
        self.proxy_rotation_attempts = 0


class ProxyManager:
    def __init__(self):
        self.proxies = settings.PROXY_LIST
        self.current_index = 0
        self.decodo_manager = None
        
        # Initialize Decodo proxy if credentials are provided
        if settings.DECODO_USERNAME and settings.DECODO_PASSWORD and settings.DECODO_ENDPOINT:
            self.decodo_manager = DecodoProxyManager(
                username=settings.DECODO_USERNAME,
                password=settings.DECODO_PASSWORD,
                proxy_endpoint=settings.DECODO_ENDPOINT,
                proxy_type=settings.DECODO_PROXY_TYPE
            )
            logger.info("Decodo proxy manager initialized")
    
    def get_proxy(self) -> Optional[str]:
        """Get next proxy from the rotation, prioritizing Decodo if available"""
        # Use Decodo proxy if available
        if self.decodo_manager:
            return self.decodo_manager.get_proxy()
        
        # Fallback to regular proxy list
        if not self.proxies:
            return None
        
        if settings.ROTATE_PROXIES:
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
            return proxy
        else:
            return random.choice(self.proxies)
    
    def rotate_proxy(self) -> Optional[str]:
        """Rotate to a new proxy"""
        if self.decodo_manager:
            return self.decodo_manager.rotate_proxy()
        
        # For regular proxies, just get the next one
        return self.get_proxy()
    
    def test_current_proxy(self) -> bool:
        """Test if the current proxy is working"""
        if self.decodo_manager:
            return self.decodo_manager.test_proxy()
        return True  # Assume regular proxies work
    
    def add_proxy(self, proxy: str):
        """Add a new proxy to the list"""
        if proxy not in self.proxies:
            self.proxies.append(proxy)
    
    def remove_proxy(self, proxy: str):
        """Remove a proxy from the list"""
        if proxy in self.proxies:
            self.proxies.remove(proxy)


class UserAgentManager:
    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        ]
    
    def get_user_agent(self) -> str:
        """Get a random user agent"""
        if settings.ROTATE_USER_AGENTS:
            if ua:
                try:
                    return ua.random
                except Exception:
                    pass
            return random.choice(self.user_agents)
        else:
            return self.user_agents[0]


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
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.netloc.lower()


def is_valid_url(url: str) -> bool:
    """Validate URL format"""
    from urllib.parse import urlparse
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def sanitize_text(text: str) -> str:
    """Clean and sanitize text content"""
    if not text:
        return ""
    
    # Remove extra whitespace
    text = " ".join(text.split())
    
    # Remove common unwanted characters
    text = text.replace('\xa0', ' ')  # Non-breaking space
    text = text.replace('\u200b', '')  # Zero-width space
    
    return text.strip()


def extract_price_from_text(price_text: str) -> Optional[str]:
    """Extract price from text"""
    if not price_text:
        return None
    
    import re
    
    # Common price patterns
    patterns = [
        r'[\$€£¥₹]?\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?',  # $1,234.56
        r'[\$€£¥₹]?\s*\d+(?:\.\d{2})?',  # $123.45
        r'\d+(?:\.\d{2})?\s*[\$€£¥₹]',  # 123.45$
    ]
    
    for pattern in patterns:
        match = re.search(pattern, price_text)
        if match:
            return match.group()
    
    return None


def extract_rating_from_text(rating_text: str) -> Optional[float]:
    """Extract rating from text"""
    if not rating_text:
        return None
    
    import re
    
    # Look for rating patterns like "4.5", "4.5/5", "4.5 out of 5"
    patterns = [
        r'(\d+\.?\d*)\s*out\s*of\s*(\d+)',
        r'(\d+\.?\d*)\s*/\s*(\d+)',
        r'(\d+\.?\d*)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, rating_text)
        if match:
            if len(match.groups()) == 2:
                # Convert to 5-star scale
                rating = float(match.group(1))
                max_rating = float(match.group(2))
                return (rating / max_rating) * 5
            else:
                rating = float(match.group(1))
                return min(rating, 5.0)  # Cap at 5.0
    
    return None


# Global instances
proxy_manager = ProxyManager()
user_agent_manager = UserAgentManager()


def map_currency_symbol_to_code(currency_symbol: str, domain: str = None) -> str:
    """
    Map currency symbol to 3-character ISO currency code
    
    Args:
        currency_symbol: Currency symbol (e.g., '$', '€', '£')
        domain: Optional domain for fallback currency detection
    
    Returns:
        3-character currency code (e.g., 'USD', 'EUR', 'GBP')
    """
    if not currency_symbol:
        return _get_default_currency_by_domain(domain)
    
    # Clean the currency symbol
    currency_symbol = currency_symbol.strip()
    
    # Common currency symbols and their codes
    currency_map = {
        '$': 'USD',
        '€': 'EUR',
        '£': 'GBP',
        '¥': 'JPY',
        '₹': 'INR',
        '₽': 'RUB',
        '₩': 'KRW',
        '₪': 'ILS',
        '₨': 'PKR',
        '₦': 'NGN',
        '₡': 'CRC',
        '₫': 'VND',
        '₱': 'PHP',
        '₲': 'PYG',
        '₴': 'UAH',
        '₵': 'GHS',
        '₸': 'KZT',
        '₺': 'TRY',
        '₼': 'AZN',
        '₾': 'GEL',
        '₿': 'BTC'
    }
    
    # Direct symbol mapping
    if currency_symbol in currency_map:
        return currency_map[currency_symbol]
    
    # Check if it's already a 3-character code
    if len(currency_symbol) == 3 and currency_symbol.isupper():
        return currency_symbol
    
    # Try to match currency codes in text
    import re
    currency_pattern = r'\b(USD|EUR|GBP|JPY|INR|RUB|KRW|ILS|PKR|NGN|CRC|VND|PHP|PYG|UAH|GHS|KZT|TRY|AZN|GEL|BTC)\b'
    currency_match = re.search(currency_pattern, currency_symbol.upper())
    
    if currency_match:
        return currency_match.group(1)
    
    # Fallback to domain-based default
    return _get_default_currency_by_domain(domain)


def _get_default_currency_by_domain(domain: str) -> str:
    """Get default currency based on domain"""
    if not domain:
        return "USD"
    
    domain = domain.lower()
    
    # Amazon domains
    if 'amazon.com' in domain:
        return "USD"
    elif 'amazon.co.uk' in domain:
        return "GBP"
    elif 'amazon.de' in domain or 'amazon.fr' in domain or 'amazon.it' in domain or 'amazon.es' in domain:
        return "EUR"
    elif 'amazon.ca' in domain:
        return "CAD"
    elif 'amazon.co.jp' in domain:
        return "JPY"
    elif 'amazon.in' in domain:
        return "INR"
    elif 'amazon.com.au' in domain:
        return "AUD"
    elif 'amazon.com.br' in domain:
        return "BRL"
    elif 'amazon.com.mx' in domain:
        return "MXN"
    
    # Other common domains
    elif 'ebay.com' in domain:
        return "USD"
    elif 'ebay.co.uk' in domain:
        return "GBP"
    elif 'ebay.de' in domain or 'ebay.fr' in domain or 'ebay.it' in domain or 'ebay.es' in domain:
        return "EUR"
    elif 'ebay.nl' in domain:
        return "EUR"
    
    # Default to USD
    return "USD" 