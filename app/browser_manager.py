import asyncio
import logging
from typing import Optional, Tuple
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from app.config import settings

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages Chrome browser instances with configurable headless and proxy settings"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.playwright = None
        
    async def setup_browser(self, proxy: Optional[str] = None, user_agent: Optional[str] = None) -> Tuple[Browser, BrowserContext, Page]:
        """
        Setup Chrome browser with optional proxy and user agent
        
        Args:
            proxy: Optional proxy string (e.g., "http://user:pass@host:port")
            user_agent: Optional custom user agent
            
        Returns:
            Tuple of (Browser, BrowserContext, Page) instances
        """
        try:
            # Clean up existing browser if any
            await self.cleanup()
            
            self.playwright = await async_playwright().start()
            
            # Chrome launch arguments for stealth and performance
            launch_args = [
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-background-networking',
                '--disable-default-apps',
                '--disable-sync',
                '--disable-translate',
                '--hide-scrollbars',
                '--mute-audio',
                '--no-first-run',
                '--safebrowsing-disable-auto-update',
                '--ignore-certificate-errors',
                '--ignore-ssl-errors',
                '--ignore-certificate-errors-spki-list',
                '--disable-blink-features=AutomationControlled',
                '--disable-automation',
                '--disable-ipc-flooding-protection',
                '--disable-webrtc-encryption',
                '--disable-webrtc-hw-encoding',
                '--disable-webrtc-hw-decoding',
                '--disable-webrtc-multiple-routes',
                '--disable-2d-canvas-clip-aa',
                '--disable-3d-apis',
                '--disable-accelerated-2d-canvas',
                '--disable-webgl',
                '--disable-webgl2',
                '--disable-audio-service',
                '--disable-audio-input',
                '--disable-audio-output',
                '--disable-font-subpixel-positioning',
                '--lang=en-US,en',
                '--accept-lang=en-US,en;q=0.9',
                '--memory-pressure-off',
                '--max_old_space_size=4096',
                '--disable-client-side-phishing-detection',
                '--disable-component-extensions-with-background-pages',
                '--disable-domain-reliability',
                '--disable-features=TranslateUI',
                '--disable-hang-monitor',
                '--disable-prompt-on-repost',
                '--force-color-profile=srgb',
                '--metrics-recording-only',
                '--password-store=basic',
                '--use-mock-keychain',
                '--disable-features=site-per-process',
                '--disable-site-isolation-trials',
            ]
            
            # Add proxy if provided
            if proxy:
                launch_args.append(f'--proxy-server={proxy}')
            
            # Launch Chrome browser with configurable headless setting
            self.browser = await self.playwright.chromium.launch(
                headless=settings.PLAYWRIGHT_HEADLESS,
                args=launch_args
            )
            
            # Create browser context with additional settings
            context_options = {
                'viewport': {
                    'width': settings.PLAYWRIGHT_VIEWPORT_WIDTH,
                    'height': settings.PLAYWRIGHT_VIEWPORT_HEIGHT
                },
                'user_agent': user_agent or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'ignore_https_errors': True,
                'java_script_enabled': True,
                'locale': 'en-US',
                'timezone_id': 'Europe/Amsterdam',
                'has_touch': False,
                'is_mobile': False,
                'device_scale_factor': 1,
                'color_scheme': 'light',
            }
            
            self.context = await self.browser.new_context(**context_options)
            
            # Create page
            page = await self.context.new_page()
            
            # Set timeouts
            page.set_default_timeout(settings.PLAYWRIGHT_TIMEOUT)
            page.set_default_navigation_timeout(settings.PLAYWRIGHT_TIMEOUT)
            
            logger.info(f"Chrome browser setup completed - Headless: {settings.PLAYWRIGHT_HEADLESS}, Proxy: {proxy is not None}")
            return self.browser, self.context, page
            
        except Exception as e:
            logger.error(f"Failed to setup Chrome browser: {e}")
            await self.cleanup()
            raise
    
    async def create_page(self, user_agent: Optional[str] = None, block_images: bool = True) -> Page:
        """
        Create a new page with configured settings
        
        Args:
            user_agent: Optional custom user agent
            block_images: Whether to block image requests
            
        Returns:
            Page instance
        """
        if not self.browser or not self.context:
            await self.setup_browser()
            return self.context.pages[0] if self.context.pages else await self.context.new_page()
        
        page = await self.context.new_page()
        
        # Block images and videos if requested
        if block_images:
            await page.route("**/*", self._block_resources)
        
        return page
    
    async def _block_resources(self, route):
        """Block image and video resources"""
        resource_type = route.request.resource_type
        if resource_type in ['image', 'media', 'font']:
            await route.abort()
        else:
            await route.continue_()
    
    async def get_page_content(self, url: str, proxy: Optional[str] = None, user_agent: Optional[str] = None, block_images: bool = True) -> str:
        """
        Get HTML content from a URL
        
        Args:
            url: URL to fetch
            proxy: Optional proxy
            user_agent: Optional user agent
            block_images: Whether to block images
            
        Returns:
            HTML content as string
        """
        page = None
        try:
            # Setup browser if needed
            if not self.browser:
                await self.setup_browser(proxy=proxy, user_agent=user_agent)
            
            # Create page
            page = await self.create_page(user_agent, block_images)
            
            # Navigate to URL
            logger.info(f"Navigating to: {url}")
            response = await page.goto(url, wait_until='domcontentloaded')
            
            if not response or response.status >= 400:
                raise Exception(f"Failed to load page: {response.status if response else 'No response'}")
            
            # Wait for page to load with more robust approach
            try:
                # First try to wait for network idle with shorter timeout
                await page.wait_for_load_state('networkidle', timeout=settings.BROWSER_NETWORK_IDLE_TIMEOUT)
            except Exception:
                # If network idle fails, wait for DOM content to be ready
                logger.info("Network idle timeout, waiting for DOM content instead")
                await page.wait_for_load_state('domcontentloaded', timeout=settings.BROWSER_DOM_LOAD_TIMEOUT)
                
                # Additional wait for any critical elements to load
                try:
                    await page.wait_for_timeout(settings.BROWSER_ADDITIONAL_WAIT)
                except Exception:
                    pass  # Ignore timeout on this additional wait
            
            # Get HTML content
            html_content = await page.content()
            
            logger.info(f"Successfully fetched content from {url} (length: {len(html_content)})")
            return html_content
            
        except Exception as e:
            logger.error(f"Error fetching content from {url}: {e}")
            # Log additional context for debugging
            if page:
                try:
                    current_url = page.url
                    logger.error(f"Current page URL: {current_url}")
                except:
                    pass
            raise
        finally:
            if page:
                await page.close()
    
    async def cleanup(self):
        """Clean up browser resources"""
        try:
            if self.context:
                await self.context.close()
                self.context = None
            
            if self.browser:
                await self.browser.close()
                self.browser = None
            
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
                
            logger.info("Chrome browser cleanup completed")
        except Exception as e:
            logger.error(f"Error during browser cleanup: {e}")

    async def get_page_content_with_retry(self, url: str, proxy: Optional[str] = None, user_agent: Optional[str] = None, block_images: bool = True, max_retries: int = None) -> str:
        """
        Get HTML content with retry logic for better reliability
        
        Args:
            url: URL to fetch
            proxy: Optional proxy
            user_agent: Optional user agent
            block_images: Whether to block images
            max_retries: Maximum number of retry attempts (uses config default if None)
            
        Returns:
            HTML content as string
        """
        if max_retries is None:
            max_retries = settings.BROWSER_MAX_RETRIES
            
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Attempt {attempt + 1}/{max_retries + 1} to fetch content from {url}")
                return await self.get_page_content(url, proxy, user_agent, block_images)
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries:
                    # Wait before retrying
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    
                    # Clean up and recreate browser for retry
                    try:
                        await self.cleanup()
                    except:
                        pass
                else:
                    logger.error(f"All {max_retries + 1} attempts failed for {url}")
                    raise last_error


# Global browser manager instance
browser_manager = BrowserManager() 