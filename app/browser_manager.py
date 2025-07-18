import logging
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from app.config import settings

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manager for handling different browser types and their configurations"""
    
    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.current_browser_type: Optional[str] = None
    
    async def setup_browser(self, browser_type: str, proxy: Optional[str] = None, user_agent: Optional[str] = None) -> tuple[Browser, BrowserContext, Page]:
        """
        Setup browser with specified type and configuration
        
        Args:
            browser_type: Type of browser ("chrome", "firefox", "safari")
            proxy: Optional proxy configuration
            user_agent: Optional user agent string
            
        Returns:
            Tuple of (browser, context, page)
        """
        try:
            # Start playwright if not already started
            if not self.playwright:
                self.playwright = await async_playwright().start()
            
            # Get browser configuration
            browser_config = settings.get_browser_config(browser_type)
            browser_name = browser_config["name"]
            browser_args = browser_config["args"]
            viewport = browser_config["viewport"]
            timeout = browser_config["timeout"]
            
            # Configure proxy
            proxy_config = None
            if proxy:
                proxy_config = {
                    'server': proxy,
                    'username': settings.DECODO_USERNAME if hasattr(settings, 'DECODO_USERNAME') else None,
                    'password': settings.DECODO_PASSWORD if hasattr(settings, 'DECODO_PASSWORD') else None
                }
                logger.info(f"Using proxy: {proxy}")
            
            # Launch browser based on type
            if browser_name == "chromium":
                self.browser = await self.playwright.chromium.launch(
                    headless=settings.PLAYWRIGHT_HEADLESS,
                    args=browser_args,
                    proxy=proxy_config
                )
            elif browser_name == "firefox":
                self.browser = await self.playwright.firefox.launch(
                    headless=settings.PLAYWRIGHT_HEADLESS,
                    args=browser_args,
                    proxy=proxy_config
                )
            elif browser_name == "webkit":
                self.browser = await self.playwright.webkit.launch(
                    headless=settings.PLAYWRIGHT_HEADLESS,
                    proxy=proxy_config
                )
            else:
                raise ValueError(f"Unsupported browser type: {browser_name}")
            
            # Create context with stealth options
            context_options = self._get_context_options(browser_type, user_agent)
            self.context = await self.browser.new_context(**context_options)
            self.page = await self.context.new_page()
            
            # Set viewport
            await self.page.set_viewport_size(viewport)
            
            # Set timeout
            self.page.set_default_timeout(timeout)
            
            self.current_browser_type = browser_type
            logger.info(f"Successfully setup {browser_type} browser")
            
            return self.browser, self.context, self.page
            
        except Exception as e:
            logger.error(f"Failed to setup {browser_type} browser: {e}")
            raise
    
    def _get_context_options(self, browser_type: str, user_agent: Optional[str] = None) -> Dict[str, Any]:
        """Get context options for the specified browser type"""
        options = {
            'user_agent': user_agent or self._get_default_user_agent(browser_type),
            'viewport': settings.get_browser_config(browser_type)["viewport"],
            'ignore_https_errors': True,
            'java_script_enabled': True,
        }
        
        # Browser-specific context options
        if browser_type == "chrome":
            options.update({
                'color_scheme': 'light',
                'locale': 'en-US',
                'timezone_id': 'Europe/London',
            })
        elif browser_type == "firefox":
            options.update({
                'color_scheme': 'light',
                'locale': 'en-US',
                'timezone_id': 'Europe/London',
            })
        elif browser_type == "safari":
            options.update({
                'color_scheme': 'light',
                'locale': 'en-US',
                'timezone_id': 'Europe/London',
            })
        
        return options
    
    def _get_default_user_agent(self, browser_type: str) -> str:
        """Get default user agent for the specified browser type"""
        user_agents = {
            "chrome": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "firefox": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "safari": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
        }
        return user_agents.get(browser_type, user_agents["chrome"])
    
    async def cleanup(self):
        """Cleanup browser resources"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
                
            # Reset references
            self.browser = None
            self.context = None
            self.page = None
            self.playwright = None
            self.current_browser_type = None
            
            logger.info("Browser cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during browser cleanup: {e}")
    
    def get_browser_info(self) -> Dict[str, Any]:
        """Get information about the current browser setup"""
        return {
            'browser_type': self.current_browser_type,
            'is_connected': self.browser.is_connected() if self.browser else False,
            'has_page': self.page is not None,
            'has_context': self.context is not None
        }


# Global browser manager instance
browser_manager = BrowserManager() 