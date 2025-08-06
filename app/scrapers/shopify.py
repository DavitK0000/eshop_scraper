from typing import Optional
from app.scrapers.base import BaseScraper
from app.models import ProductInfo
from app.utils import map_currency_symbol_to_code, parse_url_domain, parse_price_with_regional_format, extract_number_from_text, sanitize_text
from app.logging_config import get_logger
import re
import json

logger = get_logger(__name__)


class ShopifyScraper(BaseScraper):
    """Shopify product scraper"""
    
    async def _setup_image_blocking(self):
        """Setup image blocking specifically for Shopify sites"""
        if not self.block_images or not self.page:
            return
        
        try:
            # Block image requests to save bandwidth
            await self.page.route("**/*.{png,jpg,jpeg,gif,webp,svg,ico}", self._block_image_request)
            
            # Block Shopify-specific image patterns
            await self.page.route("**/cdn.shopify.com/**", self._block_image_request)
            await self.page.route("**/shopify.com/**", self._block_image_request)
            await self.page.route("**/shopifycloud.com/**", self._block_image_request)
            await self.page.route("**/monorail-edge.shopifysvc.com/**", self._block_image_request)
            
            # Block common Shopify image paths
            await self.page.route("**/images/**", self._block_image_request)
            await self.page.route("**/img/**", self._block_image_request)
            await self.page.route("**/assets/**", self._block_image_request)
            await self.page.route("**/static/**", self._block_image_request)
            await self.page.route("**/uploads/**", self._block_image_request)
            await self.page.route("**/product-images/**", self._block_image_request)
            await self.page.route("**/product_img/**", self._block_image_request)
            await self.page.route("**/productimg/**", self._block_image_request)
            
            # Block video content
            await self.page.route("**/*.{mp4,webm,ogg,mov,avi,wmv,flv}", self._block_video_request)
            await self.page.route("**/videos/**", self._block_video_request)
            await self.page.route("**/video/**", self._block_video_request)
            
            # Block Shopify-specific domains
            shopify_domains = [
                "*.cdn.shopify.com",
                "*.shopify.com",
                "*.shopifycloud.com",
                "*.monorail-edge.shopifysvc.com",
                "*.shopify-cdn.com",
                "*.shopify-assets.com"
            ]
            
            for domain in shopify_domains:
                await self.page.route(f"**/{domain}/**", self._block_image_request)
            
            logger.info("Shopify-specific image and video blocking enabled")
            
        except Exception as e:
            logger.warning(f"Failed to setup Shopify image blocking: {e}")
    
    async def _block_video_request(self, route):
        """Block video requests"""
        try:
            request_url = route.request.url
            logger.debug(f"Blocking video request: {request_url}")
            
            # Log blocked video statistics
            if not hasattr(self, '_blocked_videos_count'):
                self._blocked_videos_count = 0
            self._blocked_videos_count += 1
            
            # Abort the request to prevent video download
            await route.abort()
            
            # Log every 5th blocked video to avoid spam
            if self._blocked_videos_count % 5 == 0:
                logger.info(f"Blocked {self._blocked_videos_count} video requests so far")
                
        except Exception as e:
            logger.warning(f"Failed to block video request {route.request.url}: {e}")
            # If abort fails, continue the request
            await route.continue_()
    
    async def _wait_for_site_specific_content(self):
        """Wait for Shopify-specific content to load"""
        try:
            # Wait for Shopify-specific elements
            selectors_to_wait = [
                '[data-product-json]',
                '.product-single',
                '.product__info',
                '.product__title',
                '.product__price',
                '.product__description',
                '.product__images',
                '.product-single__title',
                '.product-single__price',
                '.product-single__description',
                '.product-single__photos',
                '.product__media',
                '.product__media-list',
                '.product__info-wrapper',
                '.product__info-container'
            ]
            
            for selector in selectors_to_wait:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000)
                    logger.info(f"Found Shopify element: {selector}")
                    break
                except:
                    continue
            
            # Wait for any product JSON data to be available
            try:
                await self.page.wait_for_function(
                    'document.querySelector("[data-product-json]") !== null || window.Shopify !== undefined',
                    timeout=5000
                )
            except:
                pass
            
            # Additional wait for dynamic content
            await self.page.wait_for_timeout(2000)
            
        except Exception as e:
            logger.warning(f"Shopify-specific content wait failed: {e}")
    
    async def extract_product_info(self) -> ProductInfo:
        """
        Extract product information from Shopify product page
        """
        product_info = ProductInfo()
        
        try:
            # First, try to extract from Shopify's Structured Product JSON (most reliable)
            product_data = self._extract_structured_product_json()
            
            if product_data:
                logger.info("Successfully extracted product data from structured JSON")
                # Extract from JSON data
                product_info.title = product_data.get('title', '')
                product_info.description = product_data.get('description', '')
                product_info.brand = product_data.get('vendor', '')
                
                # Extract price from variants
                variants = product_data.get('variants', [])
                if variants:
                    first_variant = variants[0]
                    price = first_variant.get('price', '')
                    if price:
                        product_info.price = parse_price_with_regional_format(price, parse_url_domain(self.url))
                    
                    # Extract currency
                    currency = first_variant.get('currency', '')
                    if currency:
                        product_info.currency = currency
                    else:
                        # Try to extract from page
                        currency_symbol = self.find_element_text('[data-currency]')
                        product_info.currency = map_currency_symbol_to_code(currency_symbol, parse_url_domain(self.url))
                
                # Extract images from JSON
                images = product_data.get('images', [])
                for image in images:
                    if isinstance(image, dict):
                        # Image is an object with src property
                        src = image.get('src', '')
                        if src:
                            # Convert to full URL if it's relative
                            if src.startswith('//'):
                                src = 'https:' + src
                            elif src.startswith('/'):
                                src = f"https://{parse_url_domain(self.url)}{src}"
                            product_info.images.append(src)
                    elif isinstance(image, str):
                        # Image is a direct URL string
                        if image.startswith('//'):
                            image = 'https:' + image
                        elif image.startswith('/'):
                            image = f"https://{parse_url_domain(self.url)}{image}"
                        product_info.images.append(image)
                
                # Extract availability
                if variants:
                    first_variant = variants[0]
                    available = first_variant.get('available', True)
                    product_info.availability = "In Stock" if available else "Out of Stock"
                
                # Extract SKU/ID
                if variants:
                    first_variant = variants[0]
                    product_info.sku = first_variant.get('sku', '')
                    product_info.product_id = str(first_variant.get('id', ''))
                
                # Extract specifications from options
                options = product_data.get('options', [])
                specs = {}
                for option in options:
                    name = option.get('name', '')
                    values = option.get('values', [])
                    if name and values:
                        specs[name] = ', '.join(values)
                
                product_info.specifications = specs
                
            else:
                # Fallback: Extract using keyword-based approach if structured JSON failed
                logger.info("Structured JSON extraction failed, falling back to keyword-based extraction")
                self._extract_using_keywords(product_info)
            
            # Store raw data for debugging
            product_info.raw_data = {
                'url': self.url,
                'html_length': len(self.html_content) if self.html_content else 0,
                'platform': 'shopify',
                'structured_json_found': bool(product_data)
            }
            
        except Exception as e:
            logger.error(f"Error extracting Shopify product info: {e}")
        
        return product_info
    
    def _extract_structured_product_json(self) -> Optional[dict]:
        """Extract product JSON data from Shopify's structured data sources using all available methods"""
        try:
            all_product_data = []
            
            # Method 1: Look for Shopify's ProductJson script tags (most reliable)
            product_json_scripts = self.soup.find_all('script', id=re.compile(r'ProductJson-.*'))
            logger.info(f"Found {len(product_json_scripts)} ProductJson script tags")
            for script in product_json_scripts:
                if script.string:
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and ('title' in data or 'variants' in data):
                            logger.info("Found ProductJson script data")
                            all_product_data.append(('ProductJson', data))
                    except json.JSONDecodeError:
                        continue
            
            # Method 2: Look for data-product-json attribute
            product_json_element = self.soup.select_one('[data-product-json]')
            if product_json_element:
                json_data = product_json_element.get('data-product-json', '')
                if json_data:
                    try:
                        data = json.loads(json_data)
                        logger.info("Found data-product-json attribute")
                        all_product_data.append(('data-product-json', data))
                    except json.JSONDecodeError:
                        pass
            
            # Method 3: Look for JSON-LD structured data (application/ld+json)
            json_ld_scripts = self.soup.find_all('script', type='application/ld+json')
            logger.info(f"Found {len(json_ld_scripts)} JSON-LD script tags")
            for script in json_ld_scripts:
                if script.string:
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and data.get('@type') == 'Product':
                            logger.info("Found JSON-LD structured data")
                            converted_data = self._convert_json_ld_to_product_data(data)
                            all_product_data.append(('JSON-LD', converted_data))
                    except json.JSONDecodeError:
                        continue
            
            # Method 4: Look for window.Shopify.product data in script tags
            script_tags = self.soup.find_all('script')
            logger.info(f"Found {len(script_tags)} total script tags")
            shopify_scripts = [s for s in script_tags if s.string and 'window.Shopify' in s.string]
            logger.info(f"Found {len(shopify_scripts)} script tags containing 'window.Shopify'")
            
            for script in shopify_scripts:
                # Try to extract product data using regex
                patterns = [
                    r'window\.Shopify\.product\s*=\s*({[^}]+})',
                    r'Shopify\.product\s*=\s*({[^}]+})',
                    r'product\s*:\s*({[^}]+})',
                    r'"product":\s*({[^}]+})'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, script.string, re.DOTALL)
                    if match:
                        try:
                            json_str = match.group(1)
                            # Clean up the JSON string
                            json_str = re.sub(r'(\w+):', r'"\1":', json_str)
                            data = json.loads(json_str)
                            logger.info("Found window.Shopify.product data")
                            all_product_data.append(('window.Shopify.product', data))
                        except json.JSONDecodeError:
                            continue
            
            # Method 5: Look for script tags with application/json type
            json_scripts = self.soup.find_all('script', type='application/json')
            logger.info(f"Found {len(json_scripts)} application/json script tags")
            for script in json_scripts:
                if script.string:
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and 'product' in data:
                            logger.info("Found application/json script with product data")
                            all_product_data.append(('application/json', data['product']))
                        elif isinstance(data, dict) and ('title' in data or 'variants' in data):
                            logger.info("Found application/json script with product-like data")
                            all_product_data.append(('application/json', data))
                    except json.JSONDecodeError:
                        continue
            
            # Method 6: Look for any script tag containing product data
            logger.info("Searching all script tags for product data patterns")
            for script in script_tags:
                if not script.string:
                    continue
                    
                # Look for common product data patterns
                if any(keyword in script.string for keyword in ['"title"', '"price"', '"variants"', '"product"']):
                    try:
                        # Try to find JSON object in script content
                        json_patterns = [
                            r'({[^{}]*"title"[^{}]*})',
                            r'({[^{}]*"variants"[^{}]*})',
                            r'({[^{}]*"product"[^{}]*})'
                        ]
                        
                        for pattern in json_patterns:
                            matches = re.findall(pattern, script.string, re.DOTALL)
                            for match in matches:
                                try:
                                    # Clean up potential JSON
                                    cleaned_json = re.sub(r'(\w+):', r'"\1":', match)
                                    data = json.loads(cleaned_json)
                                    if isinstance(data, dict) and ('title' in data or 'variants' in data):
                                        logger.info("Found product data in generic script tag")
                                        all_product_data.append(('generic_script', data))
                                except json.JSONDecodeError:
                                    continue
                    except Exception:
                        continue
            
            # Combine all found data
            if all_product_data:
                logger.info(f"Found product data from {len(all_product_data)} different methods")
                combined_data = self._combine_product_data(all_product_data)
                return combined_data
            
            logger.warning("No structured product JSON data found")
            return None
            
        except Exception as e:
            logger.warning(f"Error extracting structured product JSON: {e}")
            return None
    
    def _combine_product_data(self, all_product_data: list) -> dict:
        """Combine product data from multiple sources, prioritizing the most complete and reliable data"""
        if not all_product_data:
            return {}
        
        # Priority order for data sources (higher index = higher priority)
        priority_order = {
            'ProductJson': 5,  # Most reliable Shopify source
            'data-product-json': 4,
            'window.Shopify.product': 3,
            'application/json': 2,
            'JSON-LD': 1,
            'generic_script': 0
        }
        
        # Sort by priority
        sorted_data = sorted(all_product_data, key=lambda x: priority_order.get(x[0], -1))
        
        # Start with the highest priority data
        combined_data = sorted_data[-1][1].copy() if sorted_data else {}
        
        # Merge additional data from other sources
        for source_name, data in sorted_data[:-1]:  # Skip the highest priority one as it's already used as base
            if not isinstance(data, dict):
                continue
                
            logger.info(f"Merging data from {source_name}")
            
            # Merge basic fields, preferring non-empty values
            for key, value in data.items():
                if key not in combined_data or not combined_data[key]:
                    combined_data[key] = value
                elif value and isinstance(value, str) and len(value) > len(str(combined_data[key])):
                    # Prefer longer strings (more complete descriptions)
                    combined_data[key] = value
                elif value and isinstance(value, list) and len(value) > len(combined_data.get(key, [])):
                    # Prefer longer lists (more images, variants, etc.)
                    combined_data[key] = value
        
        logger.info(f"Combined data from {len(all_product_data)} sources")
        return combined_data
    
    def _convert_json_ld_to_product_data(self, json_ld_data: dict) -> dict:
        """Convert JSON-LD structured data to product data format"""
        product_data = {}
        
        product_data['title'] = json_ld_data.get('name', '')
        product_data['description'] = json_ld_data.get('description', '')
        product_data['brand'] = json_ld_data.get('brand', {}).get('name', '')
        
        # Extract price
        offers = json_ld_data.get('offers', {})
        if isinstance(offers, list) and offers:
            offers = offers[0]
        
        price = offers.get('price', '')
        if price:
            product_data['price'] = str(price)
        
        currency = offers.get('priceCurrency', '')
        if currency:
            product_data['currency'] = currency
        
        # Extract images
        images = json_ld_data.get('image', [])
        if isinstance(images, str):
            images = [images]
        product_data['images'] = images
        
        # Extract availability
        availability = offers.get('availability', '')
        if availability:
            product_data['available'] = 'InStock' in availability
        
        # Extract SKU
        sku = offers.get('sku', '')
        if sku:
            product_data['sku'] = sku
        
        return product_data
    
    def _extract_using_keywords(self, product_info: ProductInfo):
        """Extract product information using keyword-based approach"""
        try:
            # Extract title
            title_selectors = [
                '.product-single__title',
                '.product__title',
                'h1.product-single__title',
                'h1.product__title',
                '.product-title',
                'h1[class*="product"]',
                '.product__info h1',
                '.product-single__info h1',
                'h1[class*="title"]',
                '.product-name',
                '.product__name',
                'h1',
                '[data-product-title]',
                '[class*="product"][class*="title"]'
            ]
            
            for selector in title_selectors:
                title = self.find_element_text(selector)
                if title:
                    product_info.title = title
                    break
            
            # Extract price
            price_selectors = [
                '.product-single__price',
                '.product__price',
                '.price',
                '.product-price',
                '.price__regular',
                '.price__sale',
                '.price__current',
                '[data-price]',
                '.product__info .price',
                '.price__amount',
                '.price__value',
                '[class*="price"]',
                '[data-currency]',
                '.product__price .price',
                '.product-single__price .price'
            ]
            
            for selector in price_selectors:
                price = self.extract_price(selector)
                if price:
                    product_info.price = price
                    break
            
            # Extract currency
            currency_selectors = [
                '[data-currency]',
                '.price__currency',
                '.currency',
                '[class*="currency"]'
            ]
            
            for selector in currency_selectors:
                currency = self.find_element_text(selector)
                if currency:
                    product_info.currency = map_currency_symbol_to_code(currency, parse_url_domain(self.url))
                    break
            
            # Extract description
            description_selectors = [
                '.product-single__description',
                '.product__description',
                '.product-description',
                '.description',
                '.product__info .description',
                '.product-single__info .description',
                '[data-product-description]',
                '.product__details',
                '.product-details',
                '.product__content',
                '.product-content',
                '[class*="description"]',
                '[class*="details"]',
                '.product__info [class*="description"]',
                '.product__info [class*="details"]'
            ]
            
            for selector in description_selectors:
                description = self.find_element_text(selector)
                if description:
                    product_info.description = description
                    break
            
            # Extract brand
            brand_selectors = [
                '.product-single__vendor',
                '.product__vendor',
                '.vendor',
                '.brand',
                '[data-product-vendor]',
                '.product__info .vendor',
                '.product__brand',
                '.product-brand',
                '[class*="vendor"]',
                '[class*="brand"]',
                '.product__info [class*="vendor"]',
                '.product__info [class*="brand"]'
            ]
            
            for selector in brand_selectors:
                brand = self.find_element_text(selector)
                if brand:
                    product_info.brand = brand
                    break
            
            # Extract images
            image_selectors = [
                '.product-single__photo img',
                '.product__media img',
                '.product__image img',
                '.product-single__image img',
                '.product__photo img',
                '.product__media-list img',
                '.product__media-item img',
                '.product-single__photos img',
                '.product__images img'
            ]
            
            for selector in image_selectors:
                images = self.find_elements_attr(selector, 'src')
                if images:
                    for img_src in images:
                        if img_src:
                            # Convert to full URL if it's relative
                            if img_src.startswith('//'):
                                img_src = 'https:' + img_src
                            elif img_src.startswith('/'):
                                img_src = f"https://{parse_url_domain(self.url)}{img_src}"
                            product_info.images.append(img_src)
                    break
            
            # Extract availability
            availability_selectors = [
                '.product-single__stock',
                '.product__stock',
                '.availability',
                '.stock',
                '[data-availability]',
                '.product__info .availability'
            ]
            
            for selector in availability_selectors:
                availability = self.find_element_text(selector)
                if availability:
                    product_info.availability = availability
                    break
            
            # Extract rating
            rating_selectors = [
                '.product-single__rating',
                '.product__rating',
                '.rating',
                '.stars',
                '[data-rating]',
                '.product__info .rating'
            ]
            
            for selector in rating_selectors:
                rating = self.extract_rating(selector)
                if rating:
                    product_info.rating = rating
                    break
            
            # Extract review count
            review_count_selectors = [
                '.product-single__reviews-count',
                '.product__reviews-count',
                '.reviews-count',
                '.review-count',
                '[data-review-count]'
            ]
            
            for selector in review_count_selectors:
                review_count_text = self.find_element_text(selector)
                if review_count_text:
                    product_info.review_count = extract_number_from_text(review_count_text)
                    break
            
            # Extract specifications
            specs = {}
            spec_selectors = [
                '.product-single__specs',
                '.product__specs',
                '.specifications',
                '.product-specs',
                '.product__info .specs',
                '.product-single__info .specs'
            ]
            
            for selector in spec_selectors:
                spec_container = self.soup.select_one(selector)
                if spec_container:
                    spec_rows = spec_container.select('tr, .spec-row, .spec-item')
                    for row in spec_rows:
                        key_elem = row.select_one('th, .spec-key, .spec-label')
                        value_elem = row.select_one('td, .spec-value, .spec-data')
                        
                        if key_elem and value_elem:
                            key = sanitize_text(key_elem.get_text())
                            value = sanitize_text(value_elem.get_text())
                            if key and value:
                                specs[key] = value
            
            product_info.specifications = specs
            
        except Exception as e:
            logger.error(f"Error extracting from DOM: {e}")
    
    def get_image_blocking_stats(self) -> dict:
        """Get image and video blocking statistics"""
        stats = super().get_image_blocking_stats()
        stats['blocked_videos_count'] = getattr(self, '_blocked_videos_count', 0)
        return stats 