import os
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "E-commerce Scraper API"
    VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Server Settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # Redis Settings
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    
    # Celery Settings
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    
    # Scraping Settings
    DEFAULT_TIMEOUT: int = int(os.getenv("DEFAULT_TIMEOUT", "30"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour
    
    # Browser Settings
    # Available browsers: "chrome", "firefox", "safari"
    DEFAULT_BROWSER: str = "chrome"
    
    # Platform-specific browser selection
    # Format: {"platform_domain": "browser_name"}
    PLATFORM_BROWSERS: Dict[str, str] = {
        # Amazon platforms - use Chrome for better compatibility
        "amazon.com": "chrome",
        "amazon.co.uk": "chrome", 
        "amazon.de": "chrome",
        "amazon.fr": "chrome",
        "amazon.it": "chrome",
        "amazon.es": "chrome",
        "amazon.nl": "chrome",
        "amazon.ca": "chrome",
        "amazon.com.au": "chrome",
        "amazon.co.jp": "chrome",
        "amazon.in": "chrome",
        
        # eBay platforms - use Firefox for better stealth
        "ebay.com": "firefox",
        "ebay.co.uk": "firefox",
        "ebay.de": "firefox", 
        "ebay.fr": "firefox",
        "ebay.it": "firefox",
        "ebay.es": "firefox",
        "ebay.ca": "firefox",
        "ebay.nl": "firefox",
        "ebay.com.au": "firefox",
        
        # JD.com - use Chrome for better performance
        "jd.com": "chrome",
        "global.jd.com": "chrome",
        
        # European platforms - use Firefox for better compatibility
        "otto.de": "firefox",
        "bol.com": "chrome",
        "cdiscount.com": "firefox",
    }
    
    # Browser-specific configurations
    BROWSER_CONFIGS: Dict[str, Dict] = {
        "chrome": {
            "name": "chromium",
            "args": [
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-ipc-flooding-protection',
                '--disable-automation',
                '--disable-dev-shm-usage',
                '--disable-setuid-sandbox',
                '--no-first-run',
                '--no-zygote',
                '--no-sandbox',
                '--disable-gpu',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-background-networking',
                '--disable-plugins',
                '--disable-extensions',
                '--disable-default-apps',
                '--disable-sync',
                '--disable-translate',
                '--hide-scrollbars',
                '--mute-audio',
                '--safebrowsing-disable-auto-update',
                '--disable-webrtc-encryption',
                '--disable-webrtc-hw-encoding',
                '--disable-webrtc-hw-decoding',
                '--disable-webrtc-multiple-routes',
                '--disable-webrtc-hw-vp8-encoding',
                '--disable-webrtc-hw-vp8-decoding',
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
                '--disable-features=site-per-process',
                '--disable-site-isolation-trials',
                '--disable-features=VizDisplayCompositor',
            ],
            "viewport": {"width": 1920, "height": 1080},
            "timeout": 30000,
        },
        "firefox": {
            "name": "firefox",
            "args": [
                '--no-remote',
                '--width=1920',
                '--height=1080',
                '--devtools',
            ],
            "firefox_user_prefs": {
                "permissions.default.geo": 2,  # Block geolocation
                "geo.enabled": False,  # Disable geolocation service
                "geo.provider.use_corelocation": False,  # Disable core location
                "geo.provider.use_gpsd": False,  # Disable GPS daemon
                "geo.provider.use_mls": False,  # Disable Mozilla Location Service
            },
            "viewport": {"width": 1920, "height": 1080},
            "timeout": 30000,
        },
        "safari": {
            "name": "webkit",
            "args": [
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-ipc-flooding-protection',
                '--disable-automation',
                '--disable-dev-shm-usage',
                '--disable-setuid-sandbox',
                '--no-first-run',
                '--no-zygote',
                '--no-sandbox',
                '--disable-gpu',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-background-networking',
                '--disable-plugins',
                '--disable-extensions',
                '--disable-default-apps',
                '--disable-sync',
                '--disable-translate',
                '--hide-scrollbars',
                '--mute-audio',
                '--safebrowsing-disable-auto-update',
                '--disable-webrtc-encryption',
                '--disable-webrtc-hw-encoding',
                '--disable-webrtc-hw-decoding',
                '--disable-webrtc-multiple-routes',
                '--disable-webrtc-hw-vp8-encoding',
                '--disable-webrtc-hw-vp8-decoding',
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
                '--disable-features=site-per-process',
                '--disable-site-isolation-trials',
                '--disable-features=VizDisplayCompositor',
            ],
            "viewport": {"width": 1920, "height": 1080},
            "timeout": 30000,
        }
    }
    
    # Proxy Settings
    PROXY_LIST: List[str] = os.getenv("PROXY_LIST", "").split(",") if os.getenv("PROXY_LIST") else []
    ROTATE_PROXIES: bool = os.getenv("ROTATE_PROXIES", "True").lower() == "true"
    MAX_PROXY_ROTATION_ATTEMPTS: int = int(os.getenv("MAX_PROXY_ROTATION_ATTEMPTS", "3"))
    
    # Decodo Proxy Settings
    DECODO_USERNAME: str = os.getenv("DECODO_USERNAME", "")
    DECODO_PASSWORD: str = os.getenv("DECODO_PASSWORD", "")
    DECODO_ENDPOINT: str = os.getenv("DECODO_ENDPOINT", "")
    DECODO_PROXY_TYPE: str = os.getenv("DECODO_PROXY_TYPE", "http")  # http, https, socks5
    DECODO_ENABLED: bool = os.getenv("DECODO_ENABLED", "False").lower() == "true"
    
    # User Agent Settings
    ROTATE_USER_AGENTS: bool = os.getenv("ROTATE_USER_AGENTS", "True").lower() == "true"
    
    # Playwright Settings
    PLAYWRIGHT_HEADLESS: bool = os.getenv("PLAYWRIGHT_HEADLESS", "True").lower() == "true"
    PLAYWRIGHT_TIMEOUT: int = int(os.getenv("PLAYWRIGHT_TIMEOUT", "30000"))
    PLAYWRIGHT_VIEWPORT_WIDTH: int = int(os.getenv("PLAYWRIGHT_VIEWPORT_WIDTH", "1920"))
    PLAYWRIGHT_VIEWPORT_HEIGHT: int = int(os.getenv("PLAYWRIGHT_VIEWPORT_HEIGHT", "1080"))
    
    # Browser Manager Settings
    BROWSER_NETWORK_IDLE_TIMEOUT: int = int(os.getenv("BROWSER_NETWORK_IDLE_TIMEOUT", "5000"))
    BROWSER_DOM_LOAD_TIMEOUT: int = int(os.getenv("BROWSER_DOM_LOAD_TIMEOUT", "10000"))
    BROWSER_ADDITIONAL_WAIT: int = int(os.getenv("BROWSER_ADDITIONAL_WAIT", "2000"))
    BROWSER_MAX_RETRIES: int = int(os.getenv("BROWSER_MAX_RETRIES", "2"))
    BROWSER_PAGE_COMPLETION_TIMEOUT: int = int(os.getenv("BROWSER_PAGE_COMPLETION_TIMEOUT", "15000"))
    
    # Browser Operation Timeouts (new settings to prevent blocking)
    BROWSER_SCROLL_TIMEOUT: int = int(os.getenv("BROWSER_SCROLL_TIMEOUT", "5000"))  # 5 seconds per scroll
    BROWSER_SCROLL_WAIT_TIMEOUT: int = int(os.getenv("BROWSER_SCROLL_WAIT_TIMEOUT", "2000"))  # 2 seconds wait after scroll
    BROWSER_CLEANUP_TIMEOUT: int = int(os.getenv("BROWSER_CLEANUP_TIMEOUT", "10000"))  # 10 seconds for cleanup
    BROWSER_PAGE_FETCH_TIMEOUT: int = int(os.getenv("BROWSER_PAGE_FETCH_TIMEOUT", "120000"))  # 2 minutes for page fetch
    BROWSER_ENABLE_SCROLLING: bool = os.getenv("BROWSER_ENABLE_SCROLLING", "True").lower() == "true"  # Enable/disable scrolling
    
    # Stealth Settings
    ENABLE_STEALTH_MODE: bool = os.getenv("ENABLE_STEALTH_MODE", "True").lower() == "true"
    ENABLE_HUMAN_BEHAVIOR: bool = os.getenv("ENABLE_HUMAN_BEHAVIOR", "True").lower() == "true"
    ENABLE_FINGERPRINT_EVASION: bool = os.getenv("ENABLE_FINGERPRINT_EVASION", "True").lower() == "true"
    ENABLE_COOKIE_MANAGEMENT: bool = os.getenv("ENABLE_COOKIE_MANAGEMENT", "True").lower() == "true"
    STEALTH_DELAY_MIN: int = int(os.getenv("STEALTH_DELAY_MIN", "1000"))
    STEALTH_DELAY_MAX: int = int(os.getenv("STEALTH_DELAY_MAX", "3000"))
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_TO_FILE: bool = os.getenv("LOG_TO_FILE", "True").lower() == "true"
    LOG_FILE_MAX_SIZE: int = int(os.getenv("LOG_FILE_MAX_SIZE", "10485760"))  # 10MB
    LOG_FILE_BACKUP_COUNT: int = int(os.getenv("LOG_FILE_BACKUP_COUNT", "5"))
    
    @classmethod
    def get_browser_for_domain(cls, domain: str) -> str:
        """Get the appropriate browser for a given domain"""
        # Remove www. prefix for matching
        clean_domain = domain.replace("www.", "")
        return cls.PLATFORM_BROWSERS.get(clean_domain, cls.DEFAULT_BROWSER)
    
    @classmethod
    def get_browser_config(cls, browser_name: str) -> Dict:
        """Get configuration for a specific browser"""
        return cls.BROWSER_CONFIGS.get(browser_name, cls.BROWSER_CONFIGS[cls.DEFAULT_BROWSER])


settings = Settings() 