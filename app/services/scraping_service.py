import asyncio
import re
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from app.models import ProductInfo, ScrapeResponse, TaskStatus
from app.utils import generate_task_id, proxy_manager, user_agent_manager, is_valid_url
from app.config import settings
from bs4 import BeautifulSoup
from app.logging_config import get_logger

logger = get_logger(__name__)


class ScrapingService:
    """Main service for orchestrating scraping operations"""
    
    def __init__(self):
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        
        # Platform detection indicators for HTML analysis
        self.platform_indicators = {
            'shopify': {
                'patterns': [
                    r'Shopify\.theme',
                    r'shopify-section',
                    r'shopify\.analytics',
                    r'shopify\.checkout',
                    r'Shopify\.routes',
                    r'Shopify\.locale',
                    r'shop\.myshopify\.com',
                    r'window\.Shopify',
                    r'Shopify\.money_format',
                    r'Shopify\.country',
                    r'ShopifyAnalytics',
                    r'cdn\.shopify\.com',
                    r'shopifycloud\.com',
                ],
                'meta_tags': [
                    'shopify-digital-wallet',
                    'shopify-checkout-api-token',
                    'shopify-platform',
                ],
                'script_sources': [
                    'cdn.shopify.com',
                    'shopifycloud.com',
                    'monorail-edge.shopifysvc.com',
                ],
                'css_classes': [
                    'shopify-section',
                    'shopify-block',
                    'shopify-payment-button',
                ],
            },
            'woocommerce': {
                'patterns': [
                    r'wp-content\/plugins\/woocommerce',
                    r'woocommerce',
                    r'wc-ajax',
                    r'add-to-cart',
                    r'woocommerce-cart',
                    r'woocommerce-checkout',
                    r'wc_add_to_cart_params',
                    r'wc_single_product_params',
                    r'woocommerce_params',
                    r'wc_cart_fragments_params',
                    r'\.woocommerce',
                    r'WooCommerce',
                    r'wc_cart_hash',
                ],
                'meta_tags': [
                    'woocommerce-enabled',
                    'generator.*woocommerce',
                ],
                'script_sources': [
                    'woocommerce',
                    'wc-',
                ],
                'css_classes': [
                    'woocommerce',
                    'wc-toolbar',
                    'woocommerce-page',
                    'single-product',
                    'woocommerce-cart',
                    'woocommerce-checkout',
                    'wc-block',
                ],
                'body_classes': [
                    'woocommerce',
                    'woocommerce-page',
                    'single-product-summary',
                ]
            },
            'wordpress': {
                'patterns': [
                    r'wp-content',
                    r'wp-includes',
                    r'wp-admin',
                    r'wordpress',
                    r'wp_nonce',
                    r'wpdb',
                    r'wp-json',
                    r'rest_route',
                    r'wp_ajax',
                    r'WordPress',
                ],
                'meta_tags': [
                    'generator.*wordpress',
                    'generator.*WordPress',
                ],
                'script_sources': [
                    'wp-includes',
                    'wp-content',
                    'wp-admin',
                ],
                'css_classes': [
                    'wp-',
                    'wordpress',
                    'wp-block',
                ],
            },
            'squarespace': {
                'patterns': [
                    r'squarespace',
                    r'static1\.squarespace\.com',
                    r'assets\.squarespace\.com',
                    r'sqsp\.net',
                    r'squarespace-cdn',
                    r'Squarespace',
                    r'SQUARESPACE_ROLLUPS',
                    r'squarespace\.com',
                    r'Y\.Squarespace',
                ],
                'meta_tags': [
                    'squarespace-platform-preview',
                    'generator.*squarespace',
                ],
                'script_sources': [
                    'squarespace.com',
                    'squarespacestatus.com',
                    'static1.squarespace.com',
                    'assets.squarespace.com',
                ],
                'css_classes': [
                    'squarespace',
                    'sqs-',
                    'sqsrte-',
                ],
            },
            'magento': {
                'patterns': [
                    r'magento',
                    r'mage\/cookies',
                    r'skin\/frontend',
                    r'Mage\.Cookies',
                    r'MAGENTO_ROOT',
                    r'Magento',
                    r'mage\/js',
                    r'checkout\/cart',
                    r'customer\/account',
                    r'Mage\.apply',
                    r'magentosite',
                ],
                'meta_tags': [
                    'magento',
                    'generator.*magento',
                ],
                'script_sources': [
                    'magento',
                    'mage/',
                ],
                'css_classes': [
                    'magento',
                    'catalog-product',
                    'checkout-cart',
                    'page-layout-',
                    'cms-',
                ],
            },
            'webflow': {
                'patterns': [
                    r'webflow',
                    r'assets\.website-files\.com',
                    r'uploads-ssl\.webflow\.com',
                    r'Webflow',
                    r'w-node-',
                    r'w-embed',
                    r'webflow\.js',
                    r'wf-active',
                    r'wf-loading',
                ],
                'meta_tags': [
                    'webflow-platform',
                    'generator.*webflow',
                ],
                'script_sources': [
                    'webflow.com',
                    'assets.website-files.com',
                    'uploads-ssl.webflow.com',
                ],
                'css_classes': [
                    'w-node-',
                    'w-embed',
                    'w-form',
                    'w-button',
                    'w-tab',
                    'w-slider',
                ],
            },
            'wix': {
                'patterns': [
                    r'wixstatic\.com',
                    r'parastorage\.com',
                    r'static\.wixstatic\.com',
                    r'wix-code-public-path',
                    r'Wix\.com',
                    r'WixSite',
                    r'SITE_CONTAINER',
                    r'wix\.com',
                    r'wixapps\.net',
                    r'wix_typography',
                ],
                'meta_tags': [
                    'wix-platform',
                    'generator.*wix',
                ],
                'script_sources': [
                    'wix.com',
                    'wixstatic.com',
                    'parastorage.com',
                    'wixapps.net',
                ],
                'css_classes': [
                    'wixui-',
                    'SITE_CONTAINER',
                    'mesh-layout',
                    'wix-ads',
                ],
            }
        }
    
    # ============================================================================
    # PUBLIC API METHODS
    # ============================================================================
    
    async def start_scraping_task(
        self,
        url: str,
        force_refresh: bool = False,
        proxy: Optional[str] = None,
        user_agent: Optional[str] = None,
        block_images: bool = True
    ) -> ScrapeResponse:
        """
        Start a scraping task asynchronously
        
        Args:
            url: Product URL to scrape
            force_refresh: Whether to bypass cache
            proxy: Custom proxy to use
            user_agent: Custom user agent to use
            block_images: Whether to block images
            
        Returns:
            ScrapeResponse with task_id and PENDING status
        """
        task_id = generate_task_id(url)
        
        # Initialize response
        response = ScrapeResponse(
            task_id=task_id,
            status=TaskStatus.PENDING,
            url=url,
            created_at=datetime.now()
        )
        
        # Store task info
        self.active_tasks[task_id] = {
            'status': TaskStatus.PENDING,
            'created_at': datetime.now(),
            'url': url,
            'response': response
        }
        
        logger.info(f"Started scraping task {task_id} for {url}")
        return response

    async def execute_scraping_task(
        self,
        task_id: str,
        url: str,
        force_refresh: bool = False,
        proxy: Optional[str] = None,
        user_agent: Optional[str] = None,
        block_images: bool = True
    ):
        """
        Execute the actual scraping task in the background
        
        Args:
            task_id: The task ID to execute
            url: Product URL to scrape
            force_refresh: Whether to bypass cache
            proxy: Custom proxy to use
            user_agent: Custom user agent to use
            block_images: Whether to block images
        """
        logger.info(f"Starting execute_scraping_task for task_id: {task_id}, url: {url}")
        try:
            # Validate URL
            if not is_valid_url(url):
                raise ValueError(f"Invalid URL format: {url}")
            
            # Update task status
            self._update_task_status(task_id, TaskStatus.RUNNING, "Starting scraping process")
            
            # Get proxy and user agent if not provided
            if not proxy and settings.ROTATE_PROXIES:
                proxy = proxy_manager.get_proxy()
            
            if not user_agent and settings.ROTATE_USER_AGENTS:
                user_agent = user_agent_manager.get_user_agent()
            
            # First, get HTML content using browser manager with retry logic
            self._update_task_status(task_id, TaskStatus.RUNNING, "Fetching page content")
            from app.browser_manager import browser_manager
            html_content = await browser_manager.get_page_content_with_retry(url, proxy, user_agent, block_images)
            
            # Detect platform based on URL and content
            self._update_task_status(task_id, TaskStatus.RUNNING, "Detecting e-commerce platform")
            platform, platform_confidence, platform_indicators = self._detect_platform_smart(url, html_content)
            
            # Create appropriate extractor based on detected platform
            self._update_task_status(task_id, TaskStatus.RUNNING, "Creating platform-specific extractor")
            from app.extractors.factory import ExtractorFactory
            extractor = ExtractorFactory.create_extractor(platform, html_content, url)
            
            # Extract product information using the platform-specific extractor
            self._update_task_status(task_id, TaskStatus.RUNNING, "Extracting product information")
            product_info = extractor.extract_product_info()
            
            # Update task with results
            self._update_task_with_results(
                task_id, 
                TaskStatus.COMPLETED, 
                "Scraping completed successfully",
                product_info,
                platform,
                platform_confidence,
                platform_indicators
            )
            
            logger.info(f"Successfully scraped product from {url}")
            
            # Cache successful results
            try:
                from app.services.cache_service import cache_service
                response = self.active_tasks[task_id]['response']
                cache_service.cache_result(url, response)
                logger.info(f"Cached result for {url}")
            except Exception as cache_error:
                logger.warning(f"Failed to cache result: {cache_error}")
            
            # Clean up browser resources
            try:
                await browser_manager.cleanup()
            except Exception as cleanup_error:
                logger.warning(f"Cleanup failed: {cleanup_error}")
            
        except Exception as e:
            error_msg = f"Scraping failed: {str(e)}"
            logger.error(f"Error scraping {url}: {e}", exc_info=True)
            
            # Update task with error
            self._update_task_with_error(task_id, TaskStatus.FAILED, error_msg)
            
            # Clean up browser resources on error
            try:
                await browser_manager.cleanup()
            except Exception as cleanup_error:
                logger.warning(f"Cleanup failed on error: {cleanup_error}")
        
        logger.info(f"Completed execute_scraping_task for task_id: {task_id}")

    async def scrape_product(
        self,
        url: str,
        force_refresh: bool = False,
        proxy: Optional[str] = None,
        user_agent: Optional[str] = None,
        block_images: bool = True
    ) -> ScrapeResponse:
        """
        Scrape product information from URL (synchronous version for backward compatibility)
        
        Args:
            url: Product URL to scrape
            force_refresh: Whether to bypass cache
            proxy: Custom proxy to use
            user_agent: Custom user agent to use
            
        Returns:
            ScrapeResponse with product information
        """
        task_id = generate_task_id(url)
        
        # Initialize response
        response = ScrapeResponse(
            task_id=task_id,
            status=TaskStatus.PENDING,
            url=url,
            created_at=datetime.now()
        )
        
        # Store task info
        self.active_tasks[task_id] = {
            'status': TaskStatus.PENDING,
            'created_at': datetime.now(),
            'url': url
        }
        
        try:
            # Validate URL
            if not is_valid_url(url):
                raise ValueError(f"Invalid URL format: {url}")
            
            # Update task status
            self._update_task_status(task_id, TaskStatus.RUNNING, "Starting scraping process")
            
            # Get proxy and user agent if not provided
            if not proxy and settings.ROTATE_PROXIES:
                proxy = proxy_manager.get_proxy()
            
            if not user_agent and settings.ROTATE_USER_AGENTS:
                user_agent = user_agent_manager.get_user_agent()
            
            # First, get HTML content using browser manager
            self._update_task_status(task_id, TaskStatus.RUNNING, "Fetching page content")
            from app.browser_manager import browser_manager
            html_content = await browser_manager.get_page_content_with_retry(url, proxy, user_agent, block_images)
            
            # Detect platform based on URL and content
            self._update_task_status(task_id, TaskStatus.RUNNING, "Detecting e-commerce platform")
            platform, platform_confidence, platform_indicators = self._detect_platform_smart(url, html_content)
            
            # Create appropriate extractor based on detected platform
            self._update_task_status(task_id, TaskStatus.RUNNING, "Creating platform-specific extractor")
            from app.extractors.factory import ExtractorFactory
            extractor = ExtractorFactory.create_extractor(platform, html_content, url)
            
            # Extract product information using the platform-specific extractor
            self._update_task_status(task_id, TaskStatus.RUNNING, "Extracting product information")
            product_info = extractor.extract_product_info()
            
            # Store platform detection results
            response.detected_platform = platform
            response.platform_confidence = platform_confidence
            response.platform_indicators = platform_indicators
            
            logger.info(f"Platform detection for {url}: {platform} (confidence: {platform_confidence:.2f})")
            
            # Update response
            response.status = TaskStatus.COMPLETED
            response.product_info = product_info
            response.completed_at = datetime.now()
            
            # Update task status
            self._update_task_status(task_id, TaskStatus.COMPLETED, "Scraping completed successfully")
            
            logger.info(f"Successfully scraped product from {url}")
            
            # Clean up browser resources
            try:
                await browser_manager.cleanup()
            except Exception as cleanup_error:
                logger.warning(f"Cleanup failed: {cleanup_error}")
            
        except Exception as e:
            error_msg = f"Scraping failed: {str(e)}"
            logger.error(f"Error scraping {url}: {e}", exc_info=True)
            
            # Update response with error
            response.status = TaskStatus.FAILED
            response.error = error_msg
            response.completed_at = datetime.now()
            
            # Update task status
            self._update_task_status(task_id, TaskStatus.FAILED, error_msg)
            
            # Clean up browser resources on error
            try:
                await browser_manager.cleanup()
            except Exception as cleanup_error:
                logger.warning(f"Cleanup failed on error: {cleanup_error}")
        
        return response

    # ============================================================================
    # TASK MANAGEMENT METHODS
    # ============================================================================
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status"""
        task_info = self.active_tasks.get(task_id)
        if not task_info:
            logger.warning(f"Task {task_id} not found in active_tasks")
            return None
            

        return task_info
    
    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Get all active tasks"""
        return self.active_tasks.copy()
    
    def cleanup_completed_tasks(self, max_age_hours: int = 24):
        """Clean up old completed tasks"""
        cutoff_time = datetime.now().replace(hour=datetime.now().hour - max_age_hours)
        
        tasks_to_remove = []
        for task_id, task_info in self.active_tasks.items():
            if (task_info['status'] in [TaskStatus.COMPLETED, TaskStatus.FAILED] and
                task_info.get('updated_at', task_info['created_at']) < cutoff_time):
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self.active_tasks[task_id]
        
        if tasks_to_remove:
            logger.info(f"Cleaned up {len(tasks_to_remove)} old tasks")

    # ============================================================================
    # PLATFORM DETECTION METHODS
    # ============================================================================
    
    def _detect_platform_smart(self, url: str, html_content: str) -> Tuple[Optional[str], float, List[str]]:
        """
        Smart platform detection: URL-only for known platforms, URL+content for others
        Returns: (platform, confidence, indicators)
        """
        # Platforms that only need URL-based detection
        url_only_platforms = ['amazon', 'ebay', 'cdiscount', 'jd', 'otto', 'bol']
        
        # First try URL-based detection
        url_platform, url_confidence, url_indicators = self._detect_platform_from_url(url)
        
        # If it's a URL-only platform and we detected it, return immediately
        if url_platform and url_platform in url_only_platforms and url_confidence >= 0.9:
            logger.info(f"Platform detected from URL (URL-only platform): {url_platform} (confidence: {url_confidence})")
            return url_platform, url_confidence, url_indicators
        
        # For other platforms (like Shopify), try HTML analysis as well
        if url_platform and url_platform not in url_only_platforms:
            # For platforms like Shopify, check HTML content too
            html_platform, html_confidence, html_indicators = self._detect_platform_from_html_safely(html_content, url)
            
            # If both methods found the same platform, increase confidence
            if html_platform == url_platform:
                combined_confidence = min(url_confidence + html_confidence * 0.3, 1.0)
                combined_indicators = url_indicators + [f"HTML analysis confirmed: {html_platform} (confidence: {html_confidence:.2f})"]
                logger.info(f"Platform confirmed by both URL and HTML: {url_platform} (confidence: {combined_confidence:.2f})")
                return url_platform, combined_confidence, combined_indicators
            elif html_platform and html_confidence > url_confidence:
                # HTML analysis found a different platform with higher confidence
                combined_indicators = html_indicators + [f"URL analysis suggested: {url_platform} (confidence: {url_confidence:.2f})"]
                logger.info(f"Platform detected from HTML with higher confidence: {html_platform} (confidence: {html_confidence:.2f})")
                return html_platform, html_confidence, combined_indicators
            else:
                # Stick with URL detection
                logger.info(f"Platform detected from URL: {url_platform} (confidence: {url_confidence})")
                return url_platform, url_confidence, url_indicators
        
        # If URL detection failed, try HTML analysis for any platform
        html_platform, html_confidence, html_indicators = self._detect_platform_from_html_safely(html_content, url)
        if html_platform:
            logger.info(f"Platform detected from HTML analysis: {html_platform} (confidence: {html_confidence:.2f})")
            return html_platform, html_confidence, html_indicators
        
        # No platform detected
        return None, 0.0, ["No platform detected from URL or HTML analysis"]

    def _detect_platform_from_url(self, url: str) -> Tuple[Optional[str], float, List[str]]:
        """
        Detect platform from URL first
        Returns: (platform, confidence, indicators)
        """
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # URL-based platform detection
            url_platforms = {
                'amazon': {
                    'domains': ['amazon.com', 'www.amazon.com', 'amazon.co.uk', 'www.amazon.co.uk', 
                               'amazon.de', 'www.amazon.de', 'amazon.fr', 'www.amazon.fr', 
                               'amazon.it', 'www.amazon.it', 'amazon.es', 'www.amazon.es', 
                               'amazon.nl', 'www.amazon.nl', 'amazon.ca', 'www.amazon.ca', 
                               'amazon.com.au', 'www.amazon.com.au', 'amazon.co.jp', 'www.amazon.co.jp', 
                               'amazon.in', 'www.amazon.in'],
                    'confidence': 0.95,
                    'indicators': [f"Amazon domain detected: {domain}"]
                },
                'ebay': {
                    'domains': ['ebay.com', 'www.ebay.com', 'ebay.co.uk', 'www.ebay.co.uk', 
                               'ebay.de', 'www.ebay.de', 'ebay.fr', 'www.ebay.fr', 
                               'ebay.it', 'www.ebay.it', 'ebay.es', 'www.ebay.es', 
                               'ebay.ca', 'www.ebay.ca', 'ebay.nl', 'www.ebay.nl', 
                               'ebay.com.au', 'www.ebay.com.au'],
                    'confidence': 0.95,
                    'indicators': [f"eBay domain detected: {domain}"]
                },
                'otto': {
                    'domains': ['otto.de', 'www.otto.de'],
                    'confidence': 0.95,
                    'indicators': [f"Otto domain detected: {domain}"]
                },
                'bol': {
                    'domains': ['bol.com', 'www.bol.com'],
                    'confidence': 0.95,
                    'indicators': [f"Bol.com domain detected: {domain}"]
                },
                'jd': {
                    'domains': ['jd.com', 'www.jd.com', 'global.jd.com', 'www.global.jd.com'],
                    'confidence': 0.95,
                    'indicators': [f"JD.com domain detected: {domain}"]
                },
                'cdiscount': {
                    'domains': ['cdiscount.com', 'www.cdiscount.com'],
                    'confidence': 0.95,
                    'indicators': [f"CDiscount domain detected: {domain}"]
                },
                'shopify': {
                    'domains': ['myshopify.com', '*.myshopify.com', 'shop.myshopify.com'],
                    'confidence': 0.95,
                    'indicators': [f"Shopify domain detected: {domain}"]
                }
            }
            
            # Check if domain matches any known platform
            for platform, config in url_platforms.items():
                # Check exact match first
                if domain in config['domains']:
                    return platform, config['confidence'], config['indicators']
                
                # Check wildcard patterns
                for pattern in config['domains']:
                    if pattern.startswith('*.'):
                        suffix = pattern[2:]  # Remove '*.' prefix
                        if domain.endswith(suffix):
                            return platform, config['confidence'], config['indicators']
            
            # No URL-based platform detected
            return None, 0.0, [f"No known platform detected from URL domain: {domain}"]
            
        except Exception as e:
            logger.warning(f"URL-based platform detection failed for {url}: {e}")
            return None, 0.0, [f"URL-based platform detection failed: {str(e)}"]

    def _detect_platform_from_html_safely(self, html_content: str, url: str) -> Tuple[Optional[str], float, List[str]]:
        """
        Safely detect platform from HTML content with error handling
        Returns: (platform, confidence, indicators)
        """
        try:
            platform, confidence, indicators = self._analyze_content_for_platform(html_content)
            return platform, confidence, indicators
        except Exception as e:
            logger.warning(f"Platform detection from HTML failed for {url}: {e}")
            # Return default values if detection fails
            return None, 0.0, [f"Platform detection failed: {str(e)}"]

    def _analyze_content_for_platform(self, html_content: str) -> Tuple[Optional[str], float, List[str]]:
        """Analyze HTML content for platform indicators"""
        soup = BeautifulSoup(html_content, 'html.parser')
        scores = {}
        all_indicators = {}
        
        for platform, config in self.platform_indicators.items():
            score = 0
            indicators = []
            
            # Check HTML patterns (search entire HTML content)
            for pattern in config.get('patterns', []):
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                if matches:
                    match_count = len(matches)
                    pattern_score = min(0.3 * match_count, 0.6)  # Up to 0.6 for multiple matches
                    score += pattern_score
                    indicators.append(f"HTML pattern '{pattern}' found {match_count} time(s)")
            
            # Check meta tags more thoroughly
            meta_tags = soup.find_all('meta')
            for meta_pattern in config.get('meta_tags', []):
                for meta in meta_tags:
                    # Check all meta attributes
                    meta_content = ' '.join([
                        str(meta.get('content', '')),
                        str(meta.get('name', '')),
                        str(meta.get('property', '')),
                        str(meta.get('http-equiv', ''))
                    ])
                    if re.search(meta_pattern, meta_content, re.IGNORECASE):
                        score += 0.4
                        indicators.append(f"Meta tag pattern: {meta_pattern}")
                        break
            
            # Check script sources and inline scripts
            scripts = soup.find_all('script')
            for script_pattern in config.get('script_sources', []):
                for script in scripts:
                    # Check src attribute
                    src = script.get('src', '')
                    if src and script_pattern in src:
                        score += 0.3
                        indicators.append(f"External script: {script_pattern}")
                    
                    # Check inline script content
                    script_content = script.string if script.string else ''
                    if re.search(script_pattern, script_content, re.IGNORECASE):
                        score += 0.25
                        indicators.append(f"Inline script pattern: {script_pattern}")
            
            # Check CSS classes more comprehensively
            for class_pattern in config.get('css_classes', []):
                # Find all elements with matching classes
                all_elements = soup.find_all()
                matching_elements = 0
                for element in all_elements:
                    element_classes = element.get('class', [])
                    for cls in element_classes:
                        if re.search(class_pattern, cls, re.IGNORECASE):
                            matching_elements += 1
                            break
                
                if matching_elements > 0:
                    class_score = min(0.2 * matching_elements, 0.4)  # Up to 0.4 for multiple matches
                    score += class_score
                    indicators.append(f"CSS class pattern '{class_pattern}' found on {matching_elements} element(s)")
            
            # Check body classes
            body = soup.find('body')
            if body and 'body_classes' in config:
                body_classes = body.get('class', [])
                body_class_str = ' '.join(body_classes) if body_classes else ''
                for body_class_pattern in config['body_classes']:
                    if re.search(body_class_pattern, body_class_str, re.IGNORECASE):
                        score += 0.4
                        indicators.append(f"Body class pattern: {body_class_pattern}")
            
            # Check CSS link sources
            css_links = soup.find_all('link', rel='stylesheet')
            for script_pattern in config.get('script_sources', []):  # Reuse patterns for CSS
                for link in css_links:
                    href = link.get('href', '')
                    if href and script_pattern in href:
                        score += 0.2
                        indicators.append(f"CSS link: {script_pattern}")
            
            # Check for platform-specific comments in HTML
            html_comments = soup.find_all(string=lambda text: isinstance(text, str) and '<!--' in text)
            for comment in html_comments:
                for pattern in config.get('patterns', []):
                    if re.search(pattern, comment, re.IGNORECASE):
                        score += 0.1
                        indicators.append(f"HTML comment pattern: {pattern}")
            
            if score > 0:
                scores[platform] = min(score, 1.0)  # Cap at 1.0
                all_indicators[platform] = indicators
        
        # Handle platform conflicts and preferences
        if 'wordpress' in scores and 'woocommerce' in scores:
            # WooCommerce is WordPress-based, so if WooCommerce is detected with decent confidence, prefer it
            if scores['woocommerce'] >= 0.3:
                scores.pop('wordpress', None)
                all_indicators.pop('wordpress', None)
            elif scores['wordpress'] > scores['woocommerce'] * 2:
                # If WordPress score is much higher, it's likely plain WordPress
                scores.pop('woocommerce', None)
                all_indicators.pop('woocommerce', None)
        
        if not scores:
            return None, 0.0, ["No platform indicators found"]
        
        best_platform = max(scores, key=scores.get)
        confidence = scores[best_platform]
        indicators = all_indicators[best_platform]
        
        return best_platform, confidence, indicators

    # ============================================================================
    # SCRAPER CREATION METHODS
    # ============================================================================
    


    # ============================================================================
    # TASK UPDATE METHODS
    # ============================================================================
    
    def _update_task_status(self, task_id: str, status: TaskStatus, message: str = None):
        """Update task status"""
        if task_id in self.active_tasks:
            self.active_tasks[task_id].update({
                'status': status,
                'updated_at': datetime.now(),
                'message': message
            })
            logger.info(f"Updated task {task_id} status to {status}: {message}")
        else:
            logger.warning(f"Task {task_id} not found in active_tasks")
    
    def _update_task_with_results(
        self, 
        task_id: str, 
        status: TaskStatus, 
        message: str,
        product_info,
        platform: Optional[str] = None,
        platform_confidence: Optional[float] = None,
        platform_indicators: Optional[List[str]] = None
    ):
        """Update task with successful results"""
        if task_id in self.active_tasks:
            task_info = self.active_tasks[task_id]
            
            # Update the stored response object
            if 'response' in task_info:
                response = task_info['response']
                response.status = status
                response.product_info = product_info
                response.completed_at = datetime.now()
                response.detected_platform = platform
                response.platform_confidence = platform_confidence
                response.platform_indicators = platform_indicators or []
                
                logger.info(f"Updated stored response for task {task_id}: status={status}, has_product_info={bool(product_info)}")
            else:
                logger.warning(f"No stored response found for task {task_id}")
            
            # Update task info
            task_info.update({
                'status': status,
                'updated_at': datetime.now(),
                'message': message,
                'product_info': product_info,
                'platform': platform,
                'platform_confidence': platform_confidence,
                'platform_indicators': platform_indicators
            })
            
            logger.info(f"Updated task info for task {task_id}: status={status}, has_product_info={bool(product_info)}")
        else:
            logger.warning(f"Task {task_id} not found in active_tasks during result update")
    
    def _update_task_with_error(self, task_id: str, status: TaskStatus, error_message: str):
        """Update task with error"""
        if task_id in self.active_tasks:
            task_info = self.active_tasks[task_id]
            
            # Update the stored response object
            if 'response' in task_info:
                response = task_info['response']
                response.status = status
                response.error = error_message
                response.completed_at = datetime.now()
            
            # Update task info
            task_info.update({
                'status': status,
                'updated_at': datetime.now(),
                'message': error_message,
                'error': error_message
            })


# Global scraping service instance
scraping_service = ScrapingService() 