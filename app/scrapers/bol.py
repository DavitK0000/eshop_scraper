from typing import Optional
from app.scrapers.base import BaseScraper
from app.models import ProductInfo
from app.utils import sanitize_text, extract_price_value, parse_url_domain, parse_price_with_regional_format
from app.logging_config import get_logger
import random
import time

logger = get_logger(__name__)


class BolScraper(BaseScraper):
    """Bol.com product scraper with enhanced stealth features"""
    
    async def _wait_for_site_specific_content(self):
        """Wait for bol.com specific content to load with enhanced stealth"""
        try:
            # First, simulate human-like behavior
            await self._simulate_bol_user_behavior()
            
            # Check if we got a proper page (not a bot detection page)
            await self._check_bol_page_validity()
            
            # Wait for bol.com specific elements
            selectors_to_wait = [
                '[data-testid="product-title"]',
                '.product-title',
                '.product-name',
                '[data-testid="price"]',
                '.price',
                '.product-price',
                '.product-image',
                '[data-testid="product-image"]',
                '.pdp-header',
                '.product-details',
                '.product-info'
            ]
            
            for selector in selectors_to_wait:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000)
                    logger.info(f"Found bol.com element: {selector}")
                    break
                except:
                    continue
                    
        except Exception as e:
            logger.warning(f"Bol.com specific wait failed: {e}")
    
    async def _check_bol_page_validity(self):
        """Check if the bol.com page is valid and not a bot detection page"""
        try:
            # Get current page content
            content = await self.page.content()
            
            # Check for very short content (bot detection or error page)
            if len(content) < 5000:
                logger.warning(f"Bol.com returned very short content ({len(content)} characters)")
                
                # Check for common bot detection indicators
                bot_indicators = [
                    'captcha',
                    'robot',
                    'bot',
                    'automation',
                    'blocked',
                    'access denied',
                    'temporarily unavailable',
                    'rate limit',
                    'too many requests',
                    'security check',
                    'verification',
                    'challenge'
                ]
                
                content_lower = content.lower()
                detected_indicators = [indicator for indicator in bot_indicators if indicator in content_lower]
                
                if detected_indicators:
                    logger.error(f"Bot detection indicators found: {detected_indicators}")
                    raise Exception(f"Bol.com bot detection triggered: {detected_indicators}")
                
                # Check for empty or minimal content
                if len(content) < 1000:
                    logger.error("Bol.com returned minimal content - likely blocked")
                    raise Exception("Bol.com returned minimal content")
                
                # Check page title for error indicators
                try:
                    title = await self.page.title()
                    if any(error_word in title.lower() for error_word in ['error', 'blocked', 'unavailable', 'denied']):
                        logger.error(f"Bol.com error page detected: {title}")
                        raise Exception(f"Bol.com error page: {title}")
                except:
                    pass
            
            # Check for bol.com specific error pages
            error_selectors = [
                '.error-page',
                '.error-message',
                '.blocked-page',
                '.captcha-container',
                '.security-check',
                '.verification-required'
            ]
            
            for selector in error_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        error_text = await element.text_content()
                        logger.error(f"Bol.com error page detected with selector {selector}: {error_text}")
                        raise Exception(f"Bol.com error page: {error_text}")
                except:
                    continue
            
            logger.info("Bol.com page validity check passed")
            
        except Exception as e:
            logger.error(f"Bol.com page validity check failed: {e}")
            raise
    
    async def get_page_content(self) -> str:
        """Override to add bol.com specific content validation and retry logic"""
        try:
            # Get content using parent method
            content = await super().get_page_content()
            
            # Check for short content and handle it
            if len(content) < 5000:
                logger.warning(f"Bol.com returned short content ({len(content)} characters), attempting recovery")
                
                # Try to handle short content
                if await self._handle_bol_short_content():
                    content = await self.page.content()
                    logger.info("Successfully recovered bol.com content")
                else:
                    logger.error("Failed to recover bol.com content")
                    raise Exception("Bol.com content recovery failed")
            
            # Additional bol.com specific validation
            if len(content) < 5000:
                logger.warning(f"Bol.com returned short content ({len(content)} characters)")
                
                # Check if it's a valid product page
                if not any(indicator in content.lower() for indicator in ['product', 'bol.com', 'price', 'title']):
                    logger.error("Bol.com content doesn't appear to be a valid product page")
                    raise Exception("Invalid bol.com product page content")
            
            return content
            
        except Exception as e:
            logger.error(f"Bol.com content retrieval failed: {e}")
            raise
    
    async def _simulate_bol_user_behavior(self):
        """Simulate realistic user behavior for bol.com"""
        try:
            # Random delay before interaction
            await self.page.wait_for_timeout(random.randint(1000, 3000))
            
            # Sometimes scroll down to see more content
            if random.random() < 0.7:
                await self.page.evaluate("window.scrollBy(0, Math.random() * 300 + 200)")
                await self.page.wait_for_timeout(random.randint(500, 1500))
            
            # Sometimes scroll back up
            if random.random() < 0.3:
                await self.page.evaluate("window.scrollBy(0, -Math.random() * 150 - 100)")
                await self.page.wait_for_timeout(random.randint(300, 800))
            
            # Random mouse movements
            viewport = self.page.viewport_size
            if viewport:
                for _ in range(random.randint(2, 5)):
                    x = random.randint(100, viewport['width'] - 100)
                    y = random.randint(100, viewport['height'] - 100)
                    await self.page.mouse.move(x, y)
                    await self.page.wait_for_timeout(random.randint(100, 300))
            
            # Sometimes hover over product images
            try:
                image_selectors = [
                    '[data-testid="product-image"] img',
                    '.product-image img',
                    '.gallery img',
                    '.main-image img'
                ]
                
                for selector in image_selectors:
                    try:
                        image = await self.page.query_selector(selector)
                        if image and random.random() < 0.4:
                            await image.hover()
                            await self.page.wait_for_timeout(random.randint(200, 600))
                            break
                    except:
                        continue
            except Exception as e:
                logger.debug(f"Image hover simulation failed: {e}")
                
        except Exception as e:
            logger.warning(f"Bol.com user behavior simulation failed: {e}")
    
    async def _setup_bol_cookies(self):
        """Setup realistic cookies for bol.com"""
        try:
            # Common cookies that real users have
            cookies = [
                {
                    'name': 'bol_cookie_consent',
                    'value': 'accepted',
                    'domain': '.bol.com',
                    'path': '/'
                },
                {
                    'name': 'bol_language',
                    'value': 'nl',
                    'domain': '.bol.com',
                    'path': '/'
                },
                {
                    'name': 'bol_currency',
                    'value': 'EUR',
                    'domain': '.bol.com',
                    'path': '/'
                }
            ]
            
            await self.page.context.add_cookies(cookies)
            logger.info("Bol.com cookies set successfully")
            
        except Exception as e:
            logger.warning(f"Failed to set Bol.com cookies: {e}")
    
    async def _handle_bol_short_content(self) -> bool:
        """Handle bol.com short content issues with retry logic"""
        try:
            # Wait a bit longer for content to load
            await self.page.wait_for_timeout(random.randint(2000, 5000))
            
            # Try to scroll to trigger more content loading
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await self.page.wait_for_timeout(1000)
            await self.page.evaluate("window.scrollTo(0, 0)")
            await self.page.wait_for_timeout(1000)
            
            # Wait for network to be idle
            await self.page.wait_for_load_state('networkidle', timeout=10000)
            
            # Check content again
            content = await self.page.content()
            if len(content) > 5000:
                logger.info("Bol.com content loaded successfully after retry")
                return True
            
            # If still short, try refreshing the page
            logger.info("Bol.com content still short, attempting page refresh")
            await self.page.reload(wait_until='domcontentloaded')
            await self.page.wait_for_timeout(random.randint(3000, 6000))
            
            content = await self.page.content()
            if len(content) > 5000:
                logger.info("Bol.com content loaded successfully after refresh")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to handle bol.com short content: {e}")
            return False
    
    async def _enhanced_bol_stealth(self):
        """Enhanced stealth features specifically for bol.com"""
        try:
            # Set more realistic headers for bol.com
            await self.page.set_extra_http_headers({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'nl-NL,nl;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
                'Referer': 'https://www.bol.com/be/fr',
                'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
            })
            
            # Inject bol.com specific stealth scripts
            # await self.page.add_init_script("""
            #     // Bol.com specific stealth
            #     Object.defineProperty(navigator, 'webdriver', {
            #         get: () => undefined,
            #     });
                
            #     // Override performance timing
            #     const originalGetEntries = Performance.prototype.getEntries;
            #     Performance.prototype.getEntries = function() {
            #         const entries = originalGetEntries.call(this);
            #         return entries.filter(entry => !entry.name.includes('automation'));
            #     };
                
            #     // Override user agent
            #     Object.defineProperty(navigator, 'userAgent', {
            #         get: () => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            #     });
            # """)
            
            logger.info("Enhanced bol.com stealth features applied")
            
        except Exception as e:
            logger.warning(f"Failed to apply enhanced bol.com stealth: {e}")
    
    async def setup_browser(self):
        """Setup browser with Bol.com specific stealth features"""
        await super().setup_browser()
        
        # Setup Bol.com specific features
        # await self._setup_bol_cookies()
        await self._enhanced_bol_stealth()
        
        # Set Bol.com specific headers with more realistic values
        await self.page.set_extra_http_headers({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'max-age=0',
            'Priority': 'u=0, i',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.bol.com/',
            'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        })
        
        # Set realistic viewport for Dutch users
        await self.page.set_viewport_size({'width': 1920, 'height': 1080})
        
        # Set timezone to Netherlands
        await self.page.add_init_script("""
            Object.defineProperty(Intl, 'DateTimeFormat', {
                get: function() {
                    return function(locale, options) {
                        if (locale === 'nl-NL') {
                            return new Intl.DateTimeFormat('nl-NL', options);
                        }
                        return new Intl.DateTimeFormat(locale, options);
                    };
                }
            });
        """)
    
    async def extract_product_info(self) -> ProductInfo:
        """
        Extract product information from Bol.com product page
        """
        product_info = ProductInfo()
        
        try:
            # Extract title - Bol.com uses various selectors for product titles
            title_selectors = [
                '[data-testid="product-title"]',
                '.product-title',
                '.product-name',
            ]
            
            for selector in title_selectors:
                title = self.find_element_text(selector)
                if title and len(title.strip()) > 5:
                    product_info.title = title
                    break
            
            # Extract price - Bol.com price selectors
            price_selectors = [
                '[data-test="price"]',
                '.promo-price',
            ]
            
            for selector in price_selectors:
                price = self.extract_bol_price(selector)
                if price:
                    product_info.price = price
                    break
            
            # Set currency to Euro (Bol.com standard)
            product_info.currency = "EUR"
            
            # Extract description
            description_selectors = [
                '[data-test="product-description"]',
                '.product-description',
                '.description',
                '[data-test="description"]',
            ]
            
            for selector in description_selectors:
                description = self.find_element_text(selector)
                if description and len(description.strip()) > 20:
                    product_info.description = description
                    break
            
            # Extract rating from Bol.com specific structure
            rating_selectors = [
                '.pdp-header__rating',
                '.star-rating-experiment',
                '.text-neutral-text-high',
                '[data-test="rating"]',
            ]
            
            for selector in rating_selectors:
                rating = self.extract_bol_rating(selector)
                if rating:
                    product_info.rating = rating
                    break
            
            # Extract review count from Bol.com specific structure
            review_count_selectors = [
                '[data-test="rating-suffix"]',
                '.pdp-header__rating',
            ]
            
            for selector in review_count_selectors:
                review_count = self.extract_bol_review_count(selector)
                if review_count:
                    product_info.review_count = review_count
                    break
            
            # Extract availability
            availability_selectors = [
                '[data-testid="availability"]',
                '.availability',
                '.stock',
                '.product-availability',
                '.delivery-info',
                '[data-testid="delivery"]',
                '.delivery'
            ]
            
            for selector in availability_selectors:
                availability = self.find_element_text(selector)
                if availability:
                    product_info.availability = availability
                    break
            
            # Extract brand
            brand_selectors = [
                '[data-testid="brand"]',
                '.brand',
                '.product-brand',
                '.manufacturer',
                '[data-testid="manufacturer"]',
                '.brand-name'
            ]
            
            for selector in brand_selectors:
                brand = self.find_element_text(selector)
                if brand:
                    product_info.brand = brand
                    break
            
            # Extract seller
            seller_selectors = [
                '[data-testid="seller"]',
                '.seller',
                '.product-seller',
                '.vendor',
                '[data-testid="vendor"]',
                '.seller-name'
            ]
            
            for selector in seller_selectors:
                seller = self.find_element_text(selector)
                if seller:
                    product_info.seller = seller
                    break
            
            # Extract SKU
            sku_selectors = [
                '[data-testid="sku"]',
                '.sku',
                '.product-sku',
                '.product-id',
                '[data-testid="product-id"]',
                '.item-number'
            ]
            
            for selector in sku_selectors:
                sku = self.find_element_text(selector)
                if sku:
                    product_info.sku = sku
                    break
            
            # Extract category
            category_selectors = [
                '[data-testid="category"]',
                '.category',
                '.product-category',
                '.breadcrumb',
                '.breadcrumbs',
                '[data-testid="breadcrumb"]',
                '.nav-breadcrumb'
            ]
            
            for selector in category_selectors:
                category = self.find_element_text(selector)
                if category:
                    product_info.category = category
                    break
            
            # Extract images from Bol.com specific structure
            image_selectors = [
                '[data-testid="product-image"] img',
                '.product-image img',
                '.gallery img',
                '.main-image img',
                '.product-photo img',
                '[data-testid="image"] img',
                '.image img',
                '.product-media img'
            ]
            
            for selector in image_selectors:
                images = self.find_elements_attr(selector, 'src')
                if images:
                    # Filter and process Bol.com images
                    filtered_images = []
                    for img in images:
                        if img and len(img) > 10 and img not in filtered_images:
                            # Ensure it's a valid image URL
                            if img.startswith('http') or img.startswith('//'):
                                # Process Bol.com image URLs to get larger versions
                                processed_img = self.process_bol_image_url(img)
                                if processed_img:
                                    filtered_images.append(processed_img)
                    product_info.images.extend(filtered_images)
                    break
            
            # Extract specifications from Bol.com specific structure
            specs = {}
            spec_selectors = [
                '.spcs .specs__list',
                '.specs .specs__list',
                '[data-testid="specifications"] tr',
                '.specifications tr',
                '.product-specs tr',
                '.specs tr',
                '.technical-details tr',
                '.product-details tr',
                '[data-testid="product-details"] tr'
            ]
            
            for selector in spec_selectors:
                if selector.startswith('.spcs') or selector.startswith('.specs'):
                    # Handle Bol.com specific dl/dt/dd structure
                    spec_elements = self.soup.select(f"{selector} .specs__row")
                    for element in spec_elements:
                        key_elem = element.select_one('.specs__title')
                        value_elem = element.select_one('.specs__value')
                        if key_elem and value_elem:
                            from app.utils import sanitize_text
                            key = sanitize_text(key_elem.get_text())
                            value = sanitize_text(value_elem.get_text())
                            if key and value and len(key.strip()) > 0:
                                specs[key.strip()] = value.strip()
                else:
                    # Handle traditional table structure
                    spec_elements = self.soup.select(selector)
                    for element in spec_elements:
                        key_elem = element.select_one('th, td:first-child, .spec-key, .spec-name')
                        value_elem = element.select_one('td:last-child, .spec-value, .spec-desc')
                        if key_elem and value_elem:
                            from app.utils import sanitize_text
                            key = sanitize_text(key_elem.get_text())
                            value = sanitize_text(value_elem.get_text())
                            if key and value and len(key.strip()) > 0:
                                specs[key.strip()] = value.strip()
                
                if specs:
                    break
            
            product_info.specifications = specs
            
            # Store raw data for debugging
            product_info.raw_data = {
                'url': self.url,
                'final_url': self.final_url,
                'html_length': len(self.html_content) if self.html_content else 0,
                'domain': 'bol.com',
                'was_redirected': self.was_redirected()
            }
            
            logger.info(f"Successfully extracted product info from bol.com: {product_info.title}")
            
        except Exception as e:
            logger.error(f"Error extracting Bol.com product info: {e}")
            # Don't fail completely, return what we have
        
        return product_info
    
    def process_bol_image_url(self, image_url: str) -> Optional[str]:
        """
        Process Bol.com image URLs to get larger versions
        Converts URLs like: https://media.s-bol.com/72GLkKVnV9Ej/qxxmw30/59x210.jpg
        To: https://media.s-bol.com/72GLkKVnV9Ej/qxxmw30/550x550.jpg
        """
        if not image_url:
            return None
        
        try:
            import re
            from urllib.parse import urlparse
            
            # Check if it's a Bol.com media URL
            if 'media.s-bol.com' not in image_url:
                return image_url  # Return original if not Bol.com URL
            
            # Parse the URL
            parsed_url = urlparse(image_url)
            path_parts = parsed_url.path.split('/')
            
            # Find the filename part (last part of the path)
            if len(path_parts) >= 2:
                filename = path_parts[-1]
                
                # Extract the base path (everything except the filename)
                base_path = '/'.join(path_parts[:-1])
                
                # Check if filename contains dimensions (e.g., "59x210.jpg")
                dimension_match = re.search(r'(\d+)x(\d+)\.(\w+)$', filename)
                if dimension_match:
                    # Replace dimensions with 550x550
                    extension = dimension_match.group(3)
                    new_filename = f"550x550.{extension}"
                    
                    # Reconstruct the URL
                    new_path = f"{base_path}/{new_filename}"
                    new_url = f"{parsed_url.scheme}://{parsed_url.netloc}{new_path}"
                    
                    logger.info(f"Processed Bol.com image URL: {image_url} -> {new_url}")
                    return new_url
            
            # If we can't process it, return the original URL
            return image_url
            
        except Exception as e:
            logger.error(f"Error processing Bol.com image URL {image_url}: {e}")
            return image_url  # Return original URL on error
    
    def extract_bol_rating(self, rating_selector: str) -> Optional[float]:
        """
        Extract rating from Bol.com specific rating structure
        Handles ratings like: "4,0/5" or aria-label="Gemiddeld 4.0 van de 5 sterren uit 144 reviews"
        """
        if not self.soup:
            return None
        
        try:
            # Find the rating element
            rating_element = self.soup.select_one(rating_selector)
            if not rating_element:
                return None
            
            # First try to get rating from aria-label (most reliable)
            aria_label = rating_element.get('aria-label', '')
            if aria_label:
                import re
                # Look for pattern like "Gemiddeld 4.0 van de 5 sterren"
                match = re.search(r'(\d+[.,]\d+)\s+van\s+de\s+(\d+)', aria_label)
                if match:
                    rating_str = match.group(1)
                    max_rating = float(match.group(2))
                    # Use regional format-aware parsing
                    domain = parse_url_domain(self.url) if self.url else None
                    rating_value = extract_price_value(rating_str, domain)
                    if rating_value is not None:
                        rating = rating_value
                    else:
                        # Fallback to simple comma replacement
                        rating = float(rating_str.replace(',', '.'))
                    return (rating / max_rating) * 5.0
            
            # Try to get rating from visible text like "4,0/5"
            rating_text = rating_element.get_text()
            if rating_text:
                import re
                # Look for pattern like "4,0/5" or "4.0/5"
                match = re.search(r'(\d+[.,]\d+)\s*/\s*(\d+)', rating_text)
                if match:
                    rating_str = match.group(1)
                    max_rating = float(match.group(2))
                    # Use regional format-aware parsing
                    domain = parse_url_domain(self.url) if self.url else None
                    rating_value = extract_price_value(rating_str, domain)
                    if rating_value is not None:
                        rating = rating_value
                    else:
                        # Fallback to simple comma replacement
                        rating = float(rating_str.replace(',', '.'))
                    return (rating / max_rating) * 5.0
                
                # Look for just a number like "4,0" or "4.0"
                match = re.search(r'(\d+[.,]\d+)', rating_text)
                if match:
                    rating_str = match.group(1)
                    # Use regional format-aware parsing
                    domain = parse_url_domain(self.url) if self.url else None
                    rating_value = extract_price_value(rating_str, domain)
                    if rating_value is not None:
                        rating = rating_value
                    else:
                        # Fallback to simple comma replacement
                        rating = float(rating_str.replace(',', '.'))
                    return min(rating, 5.0)  # Cap at 5.0
            
            # Fallback to the original extract_rating method
            return self.extract_rating(rating_selector)
            
        except Exception as e:
            logger.error(f"Error extracting Bol.com rating: {e}")
            # Fallback to the original method
            return self.extract_rating(rating_selector)
    
    def extract_bol_review_count(self, review_selector: str) -> Optional[int]:
        """
        Extract review count from Bol.com specific structure
        Handles text like: "Bekijk 144 reviews" or aria-label="... uit 144 reviews"
        """
        if not self.soup:
            return None
        
        try:
            # Find the review element
            review_element = self.soup.select_one(review_selector)
            if not review_element:
                return None
            
            # First try to get review count from aria-label
            aria_label = review_element.get('aria-label', '')
            if aria_label:
                import re
                # Look for pattern like "... uit 144 reviews"
                match = re.search(r'uit\s+(\d+)\s+reviews', aria_label)
                if match:
                    return int(match.group(1))
            
            # Try to get review count from visible text
            review_text = review_element.get_text()
            if review_text:
                import re
                # Look for pattern like "Bekijk 144 reviews" or "144 reviews"
                match = re.search(r'(\d+)\s+reviews', review_text)
                if match:
                    return int(match.group(1))
                
                # Look for any number in the text
                numbers = re.findall(r'\d+', review_text)
                if numbers:
                    return int(numbers[0])
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting Bol.com review count: {e}")
            return None
    
    def extract_bol_price(self, price_selector: str) -> Optional[float]:
        """
        Extract price from Bol.com specific price structure
        Handles split prices like: <span class="promo-price" data-test="price">14<sup class="promo-price__fraction" data-test="price-fraction">44</sup></span>
        """
        if not self.soup:
            return None
        
        try:
            # Find the price element
            price_element = self.soup.select_one(price_selector)
            if not price_element:
                return None
            
            # Get the main price text (before any sup/fraction elements)
            main_price_text = ""
            for content in price_element.contents:
                if hasattr(content, 'name') and content.name == 'sup':
                    # Skip sup elements, we'll handle them separately
                    continue
                elif hasattr(content, 'string') and content.string:
                    main_price_text += content.string.strip()
                elif isinstance(content, str):
                    main_price_text += content.strip()
            
            # Look for fraction/sup elements
            fraction_element = price_element.select_one('sup[data-test="price-fraction"], .promo-price__fraction, sup')
            fraction_text = ""
            if fraction_element:
                fraction_text = fraction_element.get_text().strip()
            
            # Combine main price and fraction
            if main_price_text and fraction_text:
                # Handle cases like "14" + "44" = "14.44"
                combined_price = f"{main_price_text}.{fraction_text}"
            elif main_price_text:
                combined_price = main_price_text
            else:
                # Fallback to the original extract_price method
                price_text = self.find_element_text(price_selector)
                if price_text:
                    domain = parse_url_domain(self.url) if self.url else None
                    return extract_price_value(price_text, domain)
                return None
            
            # Clean up the price and convert to float
            import re
            # Remove any non-numeric characters except decimal point
            cleaned_price = re.sub(r'[^\d.]', '', combined_price)
            
            # Ensure we have a valid price format and convert to float
            if re.match(r'^\d+(\.\d{1,2})?$', cleaned_price):
                domain = parse_url_domain(self.url) if self.url else None
                price_value = parse_price_with_regional_format(cleaned_price, domain)
                return price_value
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting Bol.com price: {e}")
            # Fallback to the original method
            price_text = self.find_element_text(price_selector)
            if price_text:
                domain = parse_url_domain(self.url) if self.url else None
                return extract_price_value(price_text, domain)
            return None 