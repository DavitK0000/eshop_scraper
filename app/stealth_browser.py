import random
import time
import logging
from typing import Dict, Any, Optional
from playwright.async_api import Page, BrowserContext

logger = logging.getLogger(__name__)


class StealthBrowser:
    """Advanced stealth browser configuration to avoid bot detection"""
    
    @staticmethod
    def get_stealth_browser_args() -> list:
        """Get browser arguments for stealth mode"""
        return [
            # Basic stealth flags
            '--disable-blink-features=AutomationControlled',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor',
            '--disable-ipc-flooding-protection',
            
            # Disable automation indicators
            '--disable-automation',
            '--disable-dev-shm-usage',
            '--disable-setuid-sandbox',
            '--no-first-run',
            '--no-zygote',
            '--no-sandbox',
            
            # Performance and stability
            '--disable-gpu',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-background-networking',
            
            # Disable unnecessary features
            '--disable-plugins',
            '--disable-extensions',
            '--disable-default-apps',
            '--disable-sync',
            '--disable-translate',
            '--hide-scrollbars',
            '--mute-audio',
            '--safebrowsing-disable-auto-update',
            
            # WebRTC and media
            '--disable-webrtc-encryption',
            '--disable-webrtc-hw-encoding',
            '--disable-webrtc-hw-decoding',
            '--disable-webrtc-multiple-routes',
            '--disable-webrtc-hw-vp8-encoding',
            '--disable-webrtc-hw-vp8-decoding',
            
            # Canvas and WebGL fingerprinting
            '--disable-2d-canvas-clip-aa',
            '--disable-3d-apis',
            '--disable-accelerated-2d-canvas',
            '--disable-webgl',
            '--disable-webgl2',
            
            # Audio fingerprinting
            '--disable-audio-service',
            '--disable-audio-input',
            '--disable-audio-output',
            
            # Font fingerprinting
            '--disable-font-subpixel-positioning',
            '--disable-font-subpixel-positioning',
            
            # Language and locale
            '--lang=en-US,en',
            '--accept-lang=en-US,en;q=0.9',
            
            # Memory and performance
            '--memory-pressure-off',
            '--max_old_space_size=4096',
            
            # Network
            '--disable-background-networking',
            '--disable-background-timer-throttling',
            '--disable-client-side-phishing-detection',
            '--disable-component-extensions-with-background-pages',
            '--disable-default-apps',
            '--disable-domain-reliability',
            '--disable-features=TranslateUI',
            '--disable-hang-monitor',
            '--disable-ipc-flooding-protection',
            '--disable-prompt-on-repost',
            '--disable-renderer-backgrounding',
            '--disable-sync',
            '--force-color-profile=srgb',
            '--metrics-recording-only',
            '--no-first-run',
            '--password-store=basic',
            '--use-mock-keychain',
            
            # Additional stealth
            '--disable-features=site-per-process',
            '--disable-site-isolation-trials',
            '--disable-features=VizDisplayCompositor',
        ]
    
    @staticmethod
    async def setup_stealth_page(page: Page, user_agent: str, domain: str = None) -> None:
        """Setup page with stealth features"""
        try:
            # Set realistic viewport
            viewports = [
                {'width': 1920, 'height': 1080},
                {'width': 1366, 'height': 768},
                {'width': 1440, 'height': 900},
                {'width': 1536, 'height': 864},
                {'width': 1280, 'height': 720},
            ]
            viewport = random.choice(viewports)
            await page.set_viewport_size(viewport)
            
            # Set user agent
            await page.set_extra_http_headers({'User-Agent': user_agent})
            
            # Set additional headers for realism
            await page.set_extra_http_headers({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            })
            
            # Inject stealth scripts
            await StealthBrowser._inject_stealth_scripts(page)
            
            # Set timezone and locale
            await StealthBrowser._set_timezone_and_locale(page)
            
            # Set geolocation (for European sites like bol.com)
            if domain and any(eu_domain in domain.lower() for eu_domain in ['bol.com', 'amazon.de', 'amazon.fr', 'amazon.it', 'amazon.es', 'amazon.nl']):
                await StealthBrowser._set_european_location(page)
            
            logger.info(f"Stealth page setup completed for {domain or 'unknown domain'}")
            
        except Exception as e:
            logger.error(f"Failed to setup stealth page: {e}")
    
    @staticmethod
    async def _inject_stealth_scripts(page: Page) -> None:
        """Inject JavaScript to hide automation indicators"""
        stealth_scripts = [
            # Remove webdriver property
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            """,
            
            # Override permissions
            """
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            """,
            
            # Override plugins
            """
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            """,
            
            # Override languages
            """
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            """,
            
            # Override chrome
            """
            window.chrome = {
                runtime: {},
            };
            """,
            
            # Override permissions
            """
            const originalQuery = window.navigator.permissions.query;
            return originalQuery = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            """,
            
            # Override webgl
            """
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel(R) Iris(TM) Graphics 6100';
                }
                return getParameter.apply(this, arguments);
            };
            """,
            
            # Override canvas fingerprinting
            """
            const originalGetContext = HTMLCanvasElement.prototype.getContext;
            HTMLCanvasElement.prototype.getContext = function(type, ...args) {
                const context = originalGetContext.apply(this, [type, ...args]);
                if (type === '2d') {
                    const originalFillText = context.fillText;
                    context.fillText = function(...args) {
                        return originalFillText.apply(this, args);
                    };
                }
                return context;
            };
            """,
        ]
        
        for script in stealth_scripts:
            try:
                await page.add_init_script(script)
            except Exception as e:
                logger.warning(f"Failed to inject stealth script: {e}")
    
    @staticmethod
    async def _set_timezone_and_locale(page: Page) -> None:
        """Set realistic timezone and locale"""
        try:
            # Set timezone to a common European timezone
            await page.add_init_script("""
                Object.defineProperty(Intl, 'DateTimeFormat', {
                    get: function() {
                        return function(locale, options) {
                            if (options && options.timeZone) {
                                return new Intl.DateTimeFormat(locale, options);
                            }
                            return new Intl.DateTimeFormat(locale, { timeZone: 'Europe/Amsterdam' });
                        };
                    }
                });
            """)
        except Exception as e:
            logger.warning(f"Failed to set timezone: {e}")
    
    @staticmethod
    async def _set_european_location(page: Page) -> None:
        """Set European geolocation for European sites"""
        try:
            # Set geolocation to Netherlands (for bol.com)
            await page.context.grant_permissions(['geolocation'])
            await page.set_geolocation({
                'latitude': 52.3676,
                'longitude': 4.9041,
                'accuracy': 100
            })
        except Exception as e:
            logger.warning(f"Failed to set geolocation: {e}")
    
    @staticmethod
    async def simulate_human_behavior(page: Page) -> None:
        """Simulate human-like behavior"""
        try:
            # Random mouse movements
            await StealthBrowser._random_mouse_movements(page)
            
            # Random scrolling
            await StealthBrowser._random_scrolling(page)
            
            # Random delays
            await StealthBrowser._random_delays(page)
            
        except Exception as e:
            logger.warning(f"Failed to simulate human behavior: {e}")
    
    @staticmethod
    async def _random_mouse_movements(page: Page) -> None:
        """Simulate random mouse movements"""
        try:
            # Get page dimensions
            viewport = page.viewport_size
            if not viewport:
                return
            
            # Generate 3-7 random mouse movements
            num_movements = random.randint(3, 7)
            for _ in range(num_movements):
                x = random.randint(100, viewport['width'] - 100)
                y = random.randint(100, viewport['height'] - 100)
                await page.mouse.move(x, y)
                await page.wait_for_timeout(random.randint(100, 300))
                
        except Exception as e:
            logger.warning(f"Failed to simulate mouse movements: {e}")
    
    @staticmethod
    async def _random_scrolling(page: Page) -> None:
        """Simulate random scrolling behavior"""
        try:
            # Scroll down a bit
            await page.evaluate("window.scrollBy(0, Math.random() * 200 + 100)")
            await page.wait_for_timeout(random.randint(500, 1500))
            
            # Sometimes scroll back up
            if random.random() < 0.3:
                await page.evaluate("window.scrollBy(0, -Math.random() * 100 - 50)")
                await page.wait_for_timeout(random.randint(300, 800))
                
        except Exception as e:
            logger.warning(f"Failed to simulate scrolling: {e}")
    
    @staticmethod
    async def _random_delays(page: Page) -> None:
        """Add random delays to simulate human behavior"""
        delay = random.randint(500, 2000)
        await page.wait_for_timeout(delay)
    
    @staticmethod
    def get_stealth_context_options() -> Dict[str, Any]:
        """Get context options for stealth mode"""
        return {
            'viewport': {
                'width': random.choice([1920, 1366, 1440, 1536, 1280]),
                'height': random.choice([1080, 768, 900, 864, 720])
            },
            'user_agent': None,  # Will be set separately
            'locale': 'en-US',
            'timezone_id': 'Europe/Amsterdam',
            'geolocation': {
                'latitude': 52.3676,
                'longitude': 4.9041,
                'accuracy': 100
            },
            'permissions': ['geolocation'],
            'ignore_https_errors': True,
            'java_script_enabled': True,
            'has_touch': False,
            'is_mobile': False,
            'device_scale_factor': 1,
            'color_scheme': 'light',
        } 