from typing import Optional, List, Dict, Any, Tuple
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse, parse_qs
from app.models import ProductInfo
from app.logging_config import get_logger

logger = get_logger(__name__)


class BaseExtractor:
    """Base class for extracting product information from HTML content"""
    
    def __init__(self, html_content: str, url: str):
        """
        Initialize extractor with HTML content
        
        Args:
            html_content: Raw HTML content from the page
            url: Original URL that was scraped
        """
        self.html_content = html_content
        self.url = url
        self.soup = BeautifulSoup(html_content, 'html.parser')
    
    def _extract_image_size_from_url(self, image_url: str) -> Tuple[str, int]:
        """
        Extract image size information from URL and return base URL and size.
        
        Args:
            image_url: The image URL that may contain size parameters
            
        Returns:
            Tuple of (base_url, size) where size is the pixel dimension (width or height)
        """
        if not image_url:
            return image_url, 0
        
        # Parse the URL
        parsed = urlparse(image_url)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        # Common size patterns in URL path
        size_patterns = [
            r'_(\d+)x(\d+)\.',  # _800x600.jpg
            r'_(\d+)\.',        # _800.jpg
            r'(\d+)x(\d+)\.',   # 800x600.jpg
            r'(\d+)\.',         # 800.jpg
            r'_(\d+)x',         # _800x
            r'x(\d+)\.',        # x600.jpg
        ]
        
        # Check path for size patterns
        for pattern in size_patterns:
            match = re.search(pattern, path)
            if match:
                if len(match.groups()) == 2:
                    # Width x Height format
                    width, height = int(match.group(1)), int(match.group(2))
                    size = max(width, height)  # Use the larger dimension
                    # Remove size from path to get base URL
                    base_path = re.sub(pattern, '.', path)
                    base_url = f"{parsed.scheme}://{parsed.netloc}{base_path}{parsed.params}"
                    if parsed.query:
                        base_url += f"?{parsed.query}"
                    if parsed.fragment:
                        base_url += f"#{parsed.fragment}"
                    return base_url, size
                elif len(match.groups()) == 1:
                    # Single dimension format
                    size = int(match.group(1))
                    # Remove size from path to get base URL
                    base_path = re.sub(pattern, '.', path)
                    base_url = f"{parsed.scheme}://{parsed.netloc}{base_path}{parsed.params}"
                    if parsed.query:
                        base_url += f"?{parsed.query}"
                    if parsed.fragment:
                        base_url += f"#{parsed.fragment}"
                    return base_url, size
        
        # Check query parameters for size
        size_params = ['width', 'height', 'w', 'h', 'size', 'dimension']
        for param in size_params:
            if param in query:
                try:
                    size = int(query[param][0])
                    # Remove size parameter from query
                    new_query = query.copy()
                    del new_query[param]
                    # Rebuild query string
                    new_query_str = '&'.join([f"{k}={v[0]}" for k, v in new_query.items()])
                    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}{parsed.params}"
                    if new_query_str:
                        base_url += f"?{new_query_str}"
                    if parsed.fragment:
                        base_url += f"#{parsed.fragment}"
                    return base_url, size
                except (ValueError, IndexError):
                    continue
        
        # No size information found
        return image_url, 0
    
    def _get_largest_image_variants(self, image_urls: List[str]) -> List[str]:
        """
        Filter image URLs to keep only the largest size variant for each unique image.
        
        Args:
            image_urls: List of image URLs that may contain size variants
            
        Returns:
            List of image URLs with only the largest size for each unique image
        """
        if not image_urls:
            return []
        
        # Group images by their base URL
        image_groups = {}
        
        for url in image_urls:
            base_url, size = self._extract_image_size_from_url(url)
            
            if base_url not in image_groups:
                image_groups[base_url] = []
            
            image_groups[base_url].append((url, size))
        
        # For each group, keep the URL with the largest size
        largest_images = []
        for base_url, variants in image_groups.items():
            if variants:
                # Sort by size (descending) and take the first (largest)
                largest_variant = max(variants, key=lambda x: x[1])
                largest_images.append(largest_variant[0])
        
        return largest_images
    
    def extract_product_info(self) -> ProductInfo:
        """
        Extract product information from HTML content
        
        Returns:
            ProductInfo object with extracted data
        """
        product_info = ProductInfo()
        
        try:
            # Extract basic information
            product_info.title = self.extract_title()
            product_info.price = self.extract_price()
            product_info.currency = self.extract_currency()
            product_info.description = self.extract_description()
            product_info.images = self.extract_images()
            product_info.rating = self.extract_rating()
            product_info.review_count = self.extract_review_count()
            product_info.specifications = self.extract_specifications()
            
            logger.info(f"Extracted product info: title='{product_info.title[:50] if product_info.title else 'None'}...', price={product_info.price}")
            
        except Exception as e:
            logger.error(f"Error extracting product info: {e}")
        
        return product_info
    
    def extract_title(self) -> Optional[str]:
        """Extract product title - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement extract_title")
    
    def extract_price(self) -> Optional[float]:
        """Extract product price - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement extract_price")
    
    def extract_description(self) -> Optional[str]:
        """Extract product description - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement extract_description")
    
    def extract_images(self) -> List[str]:
        """Extract product images - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement extract_images")
    
    def extract_currency(self) -> Optional[str]:
        """Extract product currency - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement extract_currency")
    
    def extract_rating(self) -> Optional[float]:
        """Extract product rating - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement extract_rating")
    
    def extract_review_count(self) -> Optional[int]:
        """Extract product review count - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement extract_review_count")
    
    def extract_specifications(self) -> Dict[str, Any]:
        """Extract product specifications - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement extract_specifications")
    
    def extract_raw_data(self) -> Dict[str, Any]:
        """Extract raw data for debugging - to be implemented by subclasses"""
        return {
            'url': self.url,
            'html_length': len(self.html_content),
            'extractor': self.__class__.__name__
        }
    
    def find_element_text(self, selector: str) -> Optional[str]:
        """Find element by CSS selector and return its text content"""
        try:
            element = self.soup.select_one(selector)
            if element:
                return element.get_text(strip=True)
        except Exception as e:
            return None
    
    def find_elements_attr(self, selector: str, attr: str) -> List[str]:
        """Find elements by CSS selector and return their attribute values"""
        try:
            elements = self.soup.select(selector)
            return [elem.get(attr) for elem in elements if elem.get(attr)]
        except Exception as e:
            return []
    
    def extract_price_value(self, selector: str) -> Optional[float]:
        """Extract price value from element text"""
        try:
            price_text = self.find_element_text(selector)
            if price_text:
                # Use the utility function for better price extraction
                from app.utils import extract_price_value, parse_url_domain
                domain = parse_url_domain(self.url) if self.url else None
                return extract_price_value(price_text, domain)
        except Exception as e:
            return None
    
    def extract_price(self, price_selector: str) -> Optional[str]:
        """Extract price from element - matches scraper base class method"""
        price_text = self.find_element_text(price_selector)
        if price_text:
            from app.utils import extract_price_from_text
            return extract_price_from_text(price_text)
        return None
    
    def extract_rating_from_element(self, selector: str) -> Optional[float]:
        """Extract rating from element text or attributes"""
        try:
            element = self.soup.select_one(selector)
            if not element:
                return None
            
            # First try to get rating from aria-label (most reliable)
            aria_label = element.get('aria-label', '')
            if aria_label:
                import re
                # Look for patterns like "4.5 out of 5", "4,5 von 5", etc.
                rating_patterns = [
                    r'(\d+[.,]\d+)\s+(?:out\s+of|von|of)\s+(\d+)',
                    r'(\d+[.,]\d+)\s*/\s*(\d+)',
                    r'(\d+[.,]\d+)\s+stars?',
                    r'(\d+[.,]\d+)',
                    r'(\d+)\s+(?:out\s+of|von|of)\s+(\d+)',
                    r'(\d+)\s*/\s*(\d+)',
                    r'(\d+)\s+stars?'
                ]
                
                for pattern in rating_patterns:
                    match = re.search(pattern, aria_label, re.IGNORECASE)
                    if match:
                        rating_str = match.group(1)
                        max_rating = float(match.group(2)) if len(match.groups()) > 1 else 5.0
                        
                        # Use regional format-aware parsing
                        from app.utils import extract_price_value, parse_url_domain
                        domain = parse_url_domain(self.url) if self.url else None
                        rating_value = extract_price_value(rating_str, domain)
                        if rating_value is not None:
                            rating = rating_value
                        else:
                            # Fallback to simple comma replacement
                            rating = float(rating_str.replace(',', '.'))
                        
                        return (rating / max_rating) * 5.0
            
            # Try to get rating from visible text
            rating_text = element.get_text()
            if rating_text:
                import re
                # Look for patterns like "4.5/5", "4,5/5", etc.
                rating_patterns = [
                    r'(\d+[.,]\d+)\s*/\s*(\d+)',
                    r'(\d+[.,]\d+)\s+stars?',
                    r'(\d+[.,]\d+)',
                    r'(\d+)\s*/\s*(\d+)',
                    r'(\d+)\s+stars?'
                ]
                
                for pattern in rating_patterns:
                    match = re.search(pattern, rating_text, re.IGNORECASE)
                    if match:
                        rating_str = match.group(1)
                        max_rating = float(match.group(2)) if len(match.groups()) > 1 else 5.0
                        
                        # Use regional format-aware parsing
                        from app.utils import extract_price_value, parse_url_domain
                        domain = parse_url_domain(self.url) if self.url else None
                        rating_value = extract_price_value(rating_str, domain)
                        if rating_value is not None:
                            rating = rating_value
                        else:
                            # Fallback to simple comma replacement
                            rating = float(rating_str.replace(',', '.'))
                        
                        return (rating / max_rating) * 5.0
            
            # Check for star-based ratings in HTML
            star_selectors = [
                f"{selector} .star",
                f"{selector} .star-filled",
                f"{selector} .star-active",
                f"{selector} .filled",
                f"{selector} .active"
            ]
            
            for star_selector in star_selectors:
                stars = self.soup.select(star_selector)
                if stars:
                    # Count filled stars
                    filled_stars = len(stars)
                    return min(filled_stars, 5.0)
            
            return None
            
        except Exception as e:
            return None
    
    def extract_rating(self, rating_selector: str) -> Optional[float]:
        """Extract rating from element - matches scraper base class method"""
        rating_text = self.find_element_text(rating_selector)
        if rating_text:
            from app.utils import extract_rating_from_text
            return extract_rating_from_text(rating_text)
        return None
    
    def extract_number_from_text(self, text: str) -> Optional[int]:
        """Extract number from text using patterns"""
        if not text:
            return None
        
        try:
            import re
            # Look for patterns like "123 reviews", "123 avis", etc.
            number_patterns = [
                r'(\d+(?:,\d+)*)\s+(?:reviews?|avis|bewertungen?|évaluations?|commentaires?)',
                r'(\d+(?:,\d+)*)',
                r'(\d+)'
            ]
            
            for pattern in number_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    number_str = match.group(1).replace(',', '')
                    try:
                        return int(number_str)
                    except ValueError:
                        continue
            
            return None
            
        except Exception as e:
            return None
    
    def detect_captcha(self) -> bool:
        """
        Detect if a captcha is present on the page
        
        Returns:
            True if captcha is detected, False otherwise
        """
        try:
            if not self.soup:
                logger.info("No soup available for captcha detection")
                return False
            
            logger.info("Starting captcha detection...")
            
            # Check for common captcha indicators
            captcha_indicators = [
                # CDiscount specific captcha
                'div.captcha-container',
                'altcha-widget',
                'altcha-checkbox',
                '#altcha_checkbox',
                'form#altcha-form',
                
                # Generic captcha indicators
                'div[class*="captcha"]',
                'div[id*="captcha"]',
                'iframe[src*="captcha"]',
                'iframe[src*="recaptcha"]',
                'div[class*="recaptcha"]',
                'div[id*="recaptcha"]',
                'div[class*="hcaptcha"]',
                'div[id*="hcaptcha"]',
                'div[class*="turnstile"]',
                'div[id*="turnstile"]',
                
                # Text indicators
                'text*="Je ne suis pas un robot"',  # French "I'm not a robot"
                'text*="I\'m not a robot"',
                'text*="Ich bin kein Roboter"',  # German
                'text*="No soy un robot"',  # Spanish
                'text*="Non sono un robot"',  # Italian
            ]
            
            # Log HTML content snippet for debugging
            html_snippet = self.html_content[:1000] if self.html_content else "No HTML content"
            logger.info(f"HTML content snippet (first 1000 chars): {html_snippet}")
            
            for indicator in captcha_indicators:
                if indicator.startswith('text*='):
                    # Text-based search
                    text_pattern = indicator.split('text*=')[1].strip('"\'')
                    found_text = self.soup.find(text=re.compile(text_pattern, re.IGNORECASE))
                    if found_text:
                        logger.info(f"Captcha detected via text pattern '{text_pattern}': {found_text}")
                        return True
                else:
                    # CSS selector search
                    elements = self.soup.select(indicator)
                    if elements:
                        logger.info(f"Captcha detected via selector '{indicator}': found {len(elements)} elements")
                        # Log the found elements for debugging
                        for i, elem in enumerate(elements[:3]):  # Log first 3 elements
                            logger.info(f"  Element {i+1}: {elem}")
                        return True
            
            # Additional check: look for any element containing "captcha" in class or id
            all_elements = self.soup.find_all(attrs={'class': re.compile(r'captcha', re.IGNORECASE)})
            all_elements.extend(self.soup.find_all(attrs={'id': re.compile(r'captcha', re.IGNORECASE)}))
            
            if all_elements:
                logger.info(f"Found {len(all_elements)} elements with 'captcha' in class/id")
                for elem in all_elements[:3]:
                    logger.info(f"  Captcha element: {elem}")
                return True
            
            logger.info("No captcha detected")
            return False
            
        except Exception as e:
            logger.warning(f"Error detecting captcha: {e}")
            return False
    
    def solve_captcha(self, page=None) -> bool:
        """
        Solve captcha by interacting with the browser
        
        Args:
            page: Playwright page object (optional, will be created if not provided)
            
        Returns:
            True if captcha was solved successfully, False otherwise
        """
        try:
            if not self.detect_captcha():
                logger.info("No captcha detected, skipping captcha solving")
                return True
            
            logger.info("Captcha detected, attempting to solve...")
            
            # If no page provided, we can't solve captcha
            if not page:
                logger.warning("No browser page provided for captcha solving")
                return False
            
            # Try to solve CDiscount specific captcha (altcha)
            if self._solve_altcha_captcha(page):
                logger.info("Successfully solved altcha captcha")
                return True
            
            # Try to solve generic checkbox captcha
            if self._solve_checkbox_captcha(page):
                logger.info("Successfully solved checkbox captcha")
                return True
            
            logger.warning("Could not solve captcha")
            return False
            
        except Exception as e:
            logger.error(f"Error solving captcha: {e}")
            return False
    
    def _solve_altcha_captcha(self, page) -> bool:
        """
        Solve altcha captcha specifically
        
        Args:
            page: Playwright page object
            
        Returns:
            True if solved successfully, False otherwise
        """
        try:
            # Wait for altcha widget to be present
            page.wait_for_selector('altcha-widget', timeout=10000)
            
            # Find and click the checkbox
            checkbox_selector = '#altcha_checkbox'
            page.wait_for_selector(checkbox_selector, timeout=10000)
            
            # Click the checkbox
            page.click(checkbox_selector)
            logger.info("Clicked altcha checkbox")
            
            # Wait for captcha to be solved (state changes from unverified to verified)
            try:
                page.wait_for_function(
                    """
                    () => {
                        const widget = document.querySelector('altcha-widget');
                        if (!widget) return false;
                        const altchaDiv = widget.querySelector('.altcha');
                        return altchaDiv && altchaDiv.getAttribute('data-state') === 'verified';
                    }
                    """,
                    timeout=30000
                )
                logger.info("Altcha captcha verified successfully")
                return True
            except Exception as e:
                logger.warning(f"Altcha verification timeout: {e}")
                # Sometimes the state doesn't change immediately, wait a bit more
                page.wait_for_timeout(3000)
                return True
            
        except Exception as e:
            logger.warning(f"Error solving altcha captcha: {e}")
            return False
    
    def _solve_checkbox_captcha(self, page) -> bool:
        """
        Solve generic checkbox captcha
        
        Args:
            page: Playwright page object
            
        Returns:
            True if solved successfully, False otherwise
        """
        try:
            # Common checkbox captcha selectors
            checkbox_selectors = [
                'input[type="checkbox"][id*="captcha"]',
                'input[type="checkbox"][class*="captcha"]',
                'input[type="checkbox"][name*="captcha"]',
                'div[class*="captcha"] input[type="checkbox"]',
                'div[id*="captcha"] input[type="checkbox"]',
                '.recaptcha-checkbox',
                '.hcaptcha-checkbox',
                '.turnstile-checkbox',
            ]
            
            for selector in checkbox_selectors:
                try:
                    if page.locator(selector).count() > 0:
                        page.click(selector)
                        logger.info(f"Clicked checkbox captcha: {selector}")
                        
                        # Wait a bit for the captcha to process
                        page.wait_for_timeout(3000)
                        return True
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            logger.warning(f"Error solving checkbox captcha: {e}")
            return False 