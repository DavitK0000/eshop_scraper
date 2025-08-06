import random
import hashlib
import json
import time
import requests
from typing import Optional, Dict, Any, List
from fake_useragent import UserAgent
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

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
        # Modern desktop browsers with realistic versions
        self.user_agents = [
            # Chrome (most common)
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
            
            # Firefox
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0",
            
            # Safari
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
            
            # Edge
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
            
            # Mobile Chrome (Android)
            "Mozilla/5.0 (Linux; Android 14; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            
            # Mobile Safari (iOS)
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (iPad; CPU OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
            
            # Tablet Chrome (Android)
            "Mozilla/5.0 (Linux; Android 13; SM-X700) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Linux; Android 13; SM-X900) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            
            # European-specific browsers (for bol.com)
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
            
            # Older but still common versions
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0",
        ]
        
        # Stealth-focused user agents (less likely to be detected)
        self.stealth_user_agents = [
            # Most common real user agents
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            "Mozilla/5.0 (Linux; Android 14; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        ]
    
    def get_user_agent(self, stealth_mode: bool = False) -> str:
        """Get a random user agent"""
        if settings.ROTATE_USER_AGENTS:
            if ua and not stealth_mode:
                try:
                    return ua.random
                except Exception:
                    pass
            
            if stealth_mode:
                return random.choice(self.stealth_user_agents)
            else:
                return random.choice(self.user_agents)
        else:
            return self.stealth_user_agents[0] if stealth_mode else self.user_agents[0]
    
    def get_user_agent_for_domain(self, domain: str) -> str:
        """Get appropriate user agent for specific domain"""
        domain = domain.lower()
        
        # For European sites like bol.com, prefer European user agents
        if any(eu_domain in domain for eu_domain in ['bol.com', 'amazon.de', 'amazon.fr', 'amazon.it', 'amazon.es', 'amazon.nl', 'ebay.de', 'ebay.fr', 'ebay.it', 'ebay.es', 'ebay.nl', 'cdiscount.com', 'otto.de']):
            european_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Linux; Android 14; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            ]
            return random.choice(european_agents)
        
        # For mobile-first sites, prefer mobile user agents
        if any(mobile_domain in domain for mobile_domain in ['m.', 'mobile.', 'touch.']):
            mobile_agents = [
                "Mozilla/5.0 (Linux; Android 14; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
                "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            ]
            return random.choice(mobile_agents)
        
        # Default to stealth mode for unknown domains
        return self.get_user_agent(stealth_mode=True)


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


def parse_price_with_regional_format(price_text: str, domain: str = None) -> Optional[float]:
    """
    Parse price text considering regional number formatting differences
    
    Args:
        price_text: Price text to parse (e.g., "1,234.56", "1.234,56", "1234,56")
        domain: Optional domain for determining regional format
    
    Returns:
        Parsed price as float, or None if parsing fails
    """
    if not price_text:
        return None
    
    import re
    
    # Remove currency symbols and extra whitespace
    price_text = re.sub(r'[\$€£¥₹₽₩₪₨₦₡₫₱₲₴₵₸₺₼₾₿]', '', price_text).strip()
    
    # Determine if this is likely European format based on domain
    is_european_format = False
    if domain:
        domain = domain.lower()
        european_domains = [
            'amazon.de', 'amazon.fr', 'amazon.it', 'amazon.es', 'amazon.nl',
            'ebay.de', 'ebay.fr', 'ebay.it', 'ebay.es', 'ebay.nl',
            'bol.com', 'cdiscount.com', 'otto.de'
        ]
        is_european_format = any(eu_domain in domain for eu_domain in european_domains)
    
    # Pattern to match numbers with either format
    # This will match: 1,234.56 (US), 1.234,56 (EU), 1234,56 (EU), 1234.56 (US)
    number_pattern = r'(\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d+[.,]\d{2}|\d+)'
    match = re.search(number_pattern, price_text)
    
    if not match:
        return None
    
    number_str = match.group(1)
    
    # Enhanced logic to detect European format based on number structure
    # If we have both comma and period, determine which is decimal separator
    if ',' in number_str and '.' in number_str:
        # Count digits after each separator
        comma_parts = number_str.split(',')
        period_parts = number_str.split('.')
        
        # If comma has 2 digits after it, it's likely the decimal separator (EU format)
        if len(comma_parts[-1]) == 2 and len(period_parts[-1]) != 2:
            is_european_format = True
        # If period has 2 digits after it, it's likely the decimal separator (US format)
        elif len(period_parts[-1]) == 2 and len(comma_parts[-1]) != 2:
            is_european_format = False
        # If both have 2 digits, use domain-based decision
        elif len(comma_parts[-1]) == 2 and len(period_parts[-1]) == 2:
            pass  # Use domain-based decision
        # If neither has 2 digits, use domain-based decision
        else:
            pass  # Use domain-based decision
    # If we only have a comma, check if it's followed by exactly 2 digits (EU decimal format)
    elif ',' in number_str and '.' not in number_str:
        comma_parts = number_str.split(',')
        # If the part after comma has exactly 2 digits, it's likely EU decimal format
        if len(comma_parts) == 2 and len(comma_parts[-1]) == 2:
            is_european_format = True
        # If the part after comma has 3 digits, it's likely US thousands separator
        elif len(comma_parts) == 2 and len(comma_parts[-1]) == 3:
            is_european_format = False
        # For other cases, use domain-based decision
        else:
            pass  # Use domain-based decision
        

    
    # Parse the number based on format
    try:
        if is_european_format:
            # European format: 1.234,56 -> 1234.56 or 86,80 -> 86.80
            # Remove dots (thousands separators) and replace comma with dot
            clean_number = number_str.replace('.', '').replace(',', '.')
        else:
            # US format: 1,234.56 -> 1234.56
            # Remove commas (thousands separators)
            clean_number = number_str.replace(',', '')
        

        
        return float(clean_number)
    except ValueError:
        return None


def extract_price_from_text(price_text: str, domain: str = None) -> Optional[str]:
    """Extract price from text with regional format support"""
    if not price_text:
        return None
    
    import re
    
    # Common price patterns with regional format support
    patterns = [
        r'[\$€£¥₹₽₩₪₨₦₡₫₱₲₴₵₸₺₼₾₿]?\s*(\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d+[.,]\d{2}|\d+)',  # $1,234.56 or €1.234,56
        r'(\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d+[.,]\d{2}|\d+)\s*[\$€£¥₹₽₩₪₨₦₡₫₱₲₴₵₸₺₼₾₿]',  # 1,234.56$ or 1.234,56€
    ]
    
    for pattern in patterns:
        match = re.search(pattern, price_text)
        if match:
            return match.group(0)  # Return the full match including currency symbol
    
    return None


def extract_price_value(price_text: str, domain: str = None) -> Optional[float]:
    """
    Extract numeric price value from text, handling regional formats
    
    Args:
        price_text: Price text to parse
        domain: Optional domain for determining regional format
    
    Returns:
        Parsed price as float, or None if parsing fails
    """
    return parse_price_with_regional_format(price_text, domain)


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
        currency_symbol: Currency symbol (e.g., '$', '€', '£') or text containing currency
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
    
    # First, try to extract currency symbol from the text
    import re
    
    # Look for currency symbols in the text
    currency_symbol_pattern = r'[\$€£¥₹₽₩₪₨₦₡₫₱₲₴₵₸₺₼₾₿]'
    symbol_match = re.search(currency_symbol_pattern, currency_symbol)
    
    if symbol_match:
        found_symbol = symbol_match.group(0)
        if found_symbol in currency_map:
            return currency_map[found_symbol]
    
    # Direct symbol mapping (for when the input is already just a symbol)
    if currency_symbol in currency_map:
        return currency_map[currency_symbol]
    
    # Check if it's already a 3-character code
    if len(currency_symbol) == 3 and currency_symbol.isupper():
        return currency_symbol
    
    # Try to match currency codes in text
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
    
    # European e-commerce sites
    elif 'otto.de' in domain:
        return "EUR"
    elif 'bol.com' in domain:
        return "EUR"
    elif 'cdiscount.com' in domain:
        return "EUR"
    
    # Default to USD
    return "USD"


def extract_number_from_text(text: str) -> Optional[int]:
    """
    Extract number from text like '123 ratings', '14 reviews', '1,234 customers'
    
    Args:
        text: Text containing numbers (e.g., "14 ratings", "1,234 reviews")
    
    Returns:
        Extracted number as integer, or None if no number found
    """
    if not text:
        return None
    
    import re
    
    # Remove common words and extract numbers
    text = text.lower()
    text = re.sub(r'(ratings?|reviews?|customers?|bewertungen?|avis|évaluations?|commentaires?|mal|times|ratings?|reviews?)', '', text)
    
    # Remove commas and other non-numeric characters except digits
    text = re.sub(r'[^\d]', '', text)
    
    # Find numbers in the text
    if text:
        try:
            return int(text)
        except ValueError:
            pass
    
    # Fallback: try to find any number pattern
    numbers = re.findall(r'\d+', text)
    if numbers:
        try:
            return int(numbers[0])
        except ValueError:
            pass
    
    return None 