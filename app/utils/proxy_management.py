import random
import requests
from typing import Optional
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


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
    """Main proxy manager that handles both regular proxies and Decodo proxies"""
    
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