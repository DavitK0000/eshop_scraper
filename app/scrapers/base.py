from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, Page
import logging
import os
import re
from datetime import datetime
from urllib.parse import urlparse
from app.models import ProductInfo
from app.utils import sanitize_text, extract_price_from_text, extract_rating_from_text, proxy_manager
from app.config import settings

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class for all scrapers"""
    
    def __init__(self, url: str, proxy: Optional[str] = None, user_agent: Optional[str] = None, block_images: bool = True):
        self.url = url
        self.original_url = url  # Store original URL
        self.final_url = url     # Will be updated if redirect occurs
        self.proxy = proxy
        self.user_agent = user_agent
        self.block_images = block_images  # Whether to block image downloads
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.html_content: Optional[str] = None
        self.soup: Optional[BeautifulSoup] = None
        self.proxy_rotation_attempts = 0
        self.max_proxy_rotation_attempts = 3

    
    def _is_ip_blocked(self) -> bool:
        """Check if the page contains IP blocking indicators"""
        if not self.html_content:
            return False
        
        blocking_indicators = [
            "has been temporarily blocked",
            "access temporarily unavailable",
            "rate limit exceeded",
            "too many requests"
        ]
        
        content_lower = self.html_content.lower()
        
        for indicator in blocking_indicators:
            if indicator.lower() in content_lower:
                logger.warning(f"IP blocking detected: {indicator}")
                return True
        
        return False
    
    async def _handle_ip_blocking(self) -> bool:
        """Handle IP blocking by rotating proxy and retrying"""
        if self.proxy_rotation_attempts >= self.max_proxy_rotation_attempts:
            logger.error(f"Maximum proxy rotation attempts ({self.max_proxy_rotation_attempts}) reached")
            return False
        
        if not self._is_ip_blocked():
            return True
        
        logger.info(f"IP blocking detected, attempting proxy rotation (attempt {self.proxy_rotation_attempts + 1}/{self.max_proxy_rotation_attempts})...")
        
        # Get a new proxy using the improved rotation method
        new_proxy = proxy_manager.rotate_proxy()
        if not new_proxy:
            logger.error("No proxies available for rotation")
            return False
        
        logger.info(f"Rotating to new proxy: {new_proxy}")
        
        # Cleanup current browser
        await self.cleanup()
        
        # Update proxy and retry
        self.proxy = new_proxy
        self.proxy_rotation_attempts += 1
        
        # Re-setup browser with new proxy
        await self.setup_browser()
        
        # Navigate to the page again
        await self.page.goto(self.url, wait_until='domcontentloaded', timeout=300000)
        await self._wait_for_dynamic_content()
        
        # Get updated content
        self.html_content = await self.page.content()
        self.soup = BeautifulSoup(self.html_content, 'html.parser')
        
        # Check if blocking is resolved
        if self._is_ip_blocked():
            logger.warning("IP blocking persists even with new proxy, will retry...")
            return await self._handle_ip_blocking()  # Recursive retry
        
        logger.info("IP blocking resolved with new proxy")
        return True
    
    async def _setup_image_blocking(self):
        """Setup image blocking to save bandwidth"""
        if not self.block_images or not self.page:
            return
        
        try:
            # Block image requests to save bandwidth
            await self.page.route("**/*.{png,jpg,jpeg,gif,webp,svg,ico}", self._block_image_request)
            
            # Also block common image CDN patterns
            await self.page.route("**/images/**", self._block_image_request)
            await self.page.route("**/img/**", self._block_image_request)
            await self.page.route("**/assets/**", self._block_image_request)
            await self.page.route("**/static/**", self._block_image_request)
            
            # Block specific image domains commonly used by e-commerce sites
            image_domains = [
                "*.amazonaws.com",
                "*.cloudfront.net",
                "*.akamaized.net",
                "*.cdn77.org",
                "*.fastly.net",
                "*.imgix.net",
                "*.cloudinary.com",
                "*.res.cloudinary.com",
                # # Add CDiscount specific domains
                # "*.cdiscount.com",
                "image.cdiscount.com",
                "*.cdiscount-static.com",
                "*.cdiscount-cdn.com",
                # # Add eBay specific domains
                # "*.ebay.com",
                "*.ebayimg.com",
                "*.ebaystatic.com",
                "*.ebaycdn.com",
                # "i.ebayimg.com",
                # "thumbs.ebaystatic.com",
                # "pics.ebaystatic.com",
                # # Add other common e-commerce image domains
                # "*.bol.com",
                # "*.otto.de",
                # "*.amazon.com",
                # "*.amazonaws.com",
                # "*.jd.com",
                # "*.alibaba.com",
                # "*.aliexpress.com"
            ]
            
            for domain in image_domains:
                await self.page.route(f"**/{domain}/**", self._block_image_request)
            
            # Block any URL containing image-related keywords
            image_keywords = [
                "**/image/**",
                "**/img/**", 
                "**/photo/**",
                "**/picture/**",
                "**/thumbnail/**",
                "**/thumb/**",
                "**/gallery/**",
                "**/media/**",
                "**/uploads/**",
                "**/product-images/**",
                "**/product-images/**",
                "**/product_img/**",
                "**/productimg/**"
            ]
            
            for keyword in image_keywords:
                await self.page.route(keyword, self._block_image_request)
            
            # Block any URL with image file extensions in path
            await self.page.route("**/*.png/**", self._block_image_request)
            await self.page.route("**/*.jpg/**", self._block_image_request)
            await self.page.route("**/*.jpeg/**", self._block_image_request)
            await self.page.route("**/*.gif/**", self._block_image_request)
            await self.page.route("**/*.webp/**", self._block_image_request)
            await self.page.route("**/*.svg/**", self._block_image_request)
            await self.page.route("**/*.ico/**", self._block_image_request)
            
            logger.info("Comprehensive image blocking enabled to save bandwidth")
            
        except Exception as e:
            logger.warning(f"Failed to setup image blocking: {e}")
    

    
    async def _block_image_request(self, route):
        """Block image requests with detailed logging"""
        try:
            request_url = route.request.url
            logger.debug(f"Blocking image request: {request_url}")
            
            # Log blocked image statistics
            if not hasattr(self, '_blocked_images_count'):
                self._blocked_images_count = 0
            self._blocked_images_count += 1
            
            # Abort the request to prevent image download
            await route.abort()
            
            # Log every 10th blocked image to avoid spam
            if self._blocked_images_count % 10 == 0:
                logger.info(f"Blocked {self._blocked_images_count} image requests so far")
                
        except Exception as e:
            logger.warning(f"Failed to block image request {route.request.url}: {e}")
            # If abort fails, continue the request
            await route.continue_()
    

    
    async def setup_browser(self):
        """Setup Playwright browser with proxy and user agent"""
        try:
            self.playwright = await async_playwright().start()
            
            browser_args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                # Additional bandwidth optimization flags
                '--disable-images',
                '--disable-plugins',
                '--disable-extensions',
                '--disable-default-apps',
                '--disable-sync',
                '--disable-translate',
                '--disable-features=VizDisplayCompositor',
                '--disable-ipc-flooding-protection',
            ]
            
            # Configure proxy using Playwright's built-in proxy support
            proxy_config = None
            if self.proxy:
                # The proxy should already be in the correct format from env
                # Format expected: http://host:port or https://host:port
                proxy_config = {
                    'server': self.proxy,
                    'username': settings.DECODO_USERNAME if hasattr(settings, 'DECODO_USERNAME') else None,
                    'password': settings.DECODO_PASSWORD if hasattr(settings, 'DECODO_PASSWORD') else None
                }
                logger.info(f"Using proxy: {self.proxy}")
            
            self.browser = await self.playwright.chromium.launch(
                headless=settings.PLAYWRIGHT_HEADLESS,
                args=browser_args,
                proxy=proxy_config
            )
            
            self.page = await self.browser.new_page()
            
            # Set user agent
            if self.user_agent:
                await self.page.set_extra_http_headers({'User-Agent': self.user_agent})
            
            # Set viewport
            await self.page.set_viewport_size({
                'width': settings.PLAYWRIGHT_VIEWPORT_WIDTH,
                'height': settings.PLAYWRIGHT_VIEWPORT_HEIGHT
            })
            
            # Set timeout
            self.page.set_default_timeout(settings.PLAYWRIGHT_TIMEOUT)
            
            # Setup image blocking to save bandwidth
            await self._setup_image_blocking()
            
            logger.info(f"Browser setup completed for {self.url}")
            
        except Exception as e:
            logger.error(f"Failed to setup browser: {e}")
            raise
    
    async def get_page_content(self) -> str:
        """Get HTML content from the page"""
        try:
            if not self.page:
                await self.setup_browser()
            
            # Navigate to the page with optimized waiting
            await self.page.goto(self.url, wait_until='domcontentloaded', timeout=300000)
                        
            # Check for redirects and update final URL
            current_url = self.page.url
            if current_url != self.url:
                self.final_url = current_url
                logger.info(f"URL redirected from {self.url} to {self.final_url}")
            
            # Wait for dynamic content to load
            await self._wait_for_dynamic_content()
            
            # Get the HTML content
            self.html_content = await self.page.content()
                        
            # Create BeautifulSoup object
            self.soup = BeautifulSoup(self.html_content, 'html.parser')
            
            # Check for IP blocking and handle it
            if self._is_ip_blocked():
                logger.info("IP blocking detected, attempting to resolve with proxy rotation...")
                if not await self._handle_ip_blocking():
                    logger.error("Failed to resolve IP blocking with proxy rotation")
                    # Continue anyway, but log the issue
                else:
                    logger.info("Successfully resolved IP blocking with proxy rotation")
            
            logger.info(f"Successfully retrieved content from {self.final_url}")
            logger.info(f"HTML content length: {len(self.html_content)}")
            
            # Debug: Check if we have meaningful content
            if len(self.html_content) < 1000:
                logger.warning(f"HTML content seems too short: {len(self.html_content)} characters")
            
            # Debug: Check page title
            try:
                title = await self.page.title()
                logger.info(f"Page title: {title}")
            except:
                pass
            
            return self.html_content
            
        except Exception as e:
            logger.error(f"Failed to get page content from {self.url}: {e}")
            raise
    
    async def _wait_for_dynamic_content(self):
        """Wait for dynamic content to load via API calls"""
        try:
            # Wait for network to be idle (API calls completed)
            await self.page.wait_for_load_state('networkidle', timeout=10000)
            
            # # Call site-specific wait method if implemented
            # await self._wait_for_site_specific_content()
            
            # # Wait for common product data selectors to appear
            # selectors_to_wait = [
            #     '[data-testid*="product"]',
            #     '[class*="product"]',
            #     '[id*="product"]',
            #     '.price',
            #     '.product-title',
            #     '.product-name',
            #     'h1',
            #     '[data-price]',
            #     '[data-product]',
            #     '[data-testid*="title"]',
            #     '[data-testid*="price"]',
            #     '.product-info',
            #     '.product-details'
            # ]
            
            # Try to wait for at least one product-related element
            # found_element = False
            # for selector in selectors_to_wait:
            #     try:
            #         await self.page.wait_for_selector(selector, timeout=2000)
            #         logger.info(f"Found product element: {selector}")
            #         found_element = True
            #         break
            #     except:
            #         continue
            
            # If no product elements found, try a more generic approach
            if True:
            # if not found_element:
                logger.info("No specific product elements found, using generic wait")
                # Wait for any content to be present
                await self.page.wait_for_function(
                    'document.body && document.body.innerHTML.length > 1000',
                    timeout=5000
                )
            
            # Additional wait for any remaining dynamic content
            await self.page.wait_for_timeout(1000)
            
        except Exception as e:
            logger.warning(f"Dynamic content wait failed: {e}")
            # Continue anyway - some sites might not need this
    
    async def _wait_for_site_specific_content(self):
        """Override this method in specific scrapers for site-specific waiting"""
        pass
        
    async def cleanup(self):
        """Cleanup browser resources"""
        try:
            # Log image blocking statistics before cleanup
            if hasattr(self, '_blocked_images_count') and self._blocked_images_count > 0:
                logger.info(f"Final image blocking statistics: {self._blocked_images_count} images blocked")
            
            if self.page:
                await self.page.close()
            if self.browser:
                await self.browser.close()
            if hasattr(self, 'playwright'):
                await self.playwright.stop()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def get_image_blocking_stats(self) -> dict:
        """Get image blocking statistics"""
        stats = {
            'block_images_enabled': self.block_images,
            'blocked_images_count': getattr(self, '_blocked_images_count', 0)
        }
        return stats
    
    @abstractmethod
    async def extract_product_info(self) -> ProductInfo:
        """Extract product information from the page"""
        pass
    
    async def scrape(self) -> ProductInfo:
        """Main scraping method"""
        try:
            await self.get_page_content()
            product_info = await self.extract_product_info()
            return product_info
        finally:
            await self.cleanup()
    
    def find_element_text(self, selector: str, default: str = "") -> str:
        """Find element text by CSS selector"""
        if not self.soup:
            return default
        
        element = self.soup.select_one(selector)
        if element:
            from app.utils import sanitize_text
            return sanitize_text(element.get_text())
        return default
    
    def find_element_attr(self, selector: str, attr: str, default: str = "") -> str:
        """Find element attribute by CSS selector"""
        if not self.soup:
            return default
        
        element = self.soup.select_one(selector)
        if element:
            return element.get(attr, default)
        return default
    
    def find_elements_attr(self, selector: str, attr: str) -> list:
        """Find multiple elements attributes by CSS selector"""
        if not self.soup:
            return []
        
        elements = self.soup.select(selector)
        return [element.get(attr, "") for element in elements if element.get(attr)]
    
    def extract_price(self, price_selector: str) -> Optional[str]:
        """Extract price from element"""
        price_text = self.find_element_text(price_selector)
        return extract_price_from_text(price_text)
    
    def extract_rating(self, rating_selector: str) -> Optional[float]:
        """Extract rating from element"""
        rating_text = self.find_element_text(rating_selector)
        return extract_rating_from_text(rating_text)
    
    def was_redirected(self) -> bool:
        """Check if the URL was redirected"""
        return self.original_url != self.final_url
    
    def get_redirect_info(self) -> Dict[str, str]:
        """Get redirect information"""
        return {
            'original_url': self.original_url,
            'final_url': self.final_url,
            'redirected': self.was_redirected()
        } 