from typing import Optional, List, Dict, Any
import re
import json
from app.extractors.base import BaseExtractor
from app.utils import map_currency_symbol_to_code, parse_url_domain, parse_price_with_regional_format, extract_number_from_text, sanitize_text
from app.logging_config import get_logger

logger = get_logger(__name__)


class ShopifyExtractor(BaseExtractor):
    """Shopify-specific extractor for product information"""
    
    def extract_title(self) -> Optional[str]:
        """Extract product title from Shopify page"""
        # First try to extract from structured JSON data
        product_data = self._extract_structured_product_json()
        if product_data and product_data.get('title'):
            logger.debug(f"Found Shopify title from JSON: {product_data['title'][:50]}...")
            return product_data['title']
        
        # Fallback to DOM extraction
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
                logger.debug(f"Found Shopify title with selector '{selector}': {title[:50]}...")
                return title
        
        logger.warning("No Shopify title found")
        return None
    
    def extract_price(self) -> Optional[float]:
        """Extract product price from Shopify page"""
        # First try to extract from structured JSON data
        product_data = self._extract_structured_product_json()
        if product_data:
            variants = product_data.get('variants', [])
            if variants:
                first_variant = variants[0]
                price = first_variant.get('price', '')
                if price:
                    try:
                        price_float = float(price)
                        logger.debug(f"Found Shopify price from JSON: {price_float}")
                        return price_float
                    except ValueError:
                        pass
        
        # Fallback to DOM extraction
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
            price = self.extract_price_value(selector)
            if price:
                logger.debug(f"Found Shopify price with selector '{selector}': {price}")
                return price
        
        logger.warning("No Shopify price found")
        return None
    
    def extract_description(self) -> Optional[str]:
        """Extract product description from Shopify page"""
        # First try to extract from structured JSON data
        product_data = self._extract_structured_product_json()
        if product_data and product_data.get('description'):
            logger.debug(f"Found Shopify description from JSON: {product_data['description'][:100]}...")
            return product_data['description']
        
        # Fallback to DOM extraction
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
                logger.debug(f"Found Shopify description with selector '{selector}': {description[:100]}...")
                return description
        
        logger.warning("No Shopify description found")
        return None
    
    def extract_images(self) -> List[str]:
        """Extract product images from Shopify page"""
        images = []
        
        # First try to extract from structured JSON data
        product_data = self._extract_structured_product_json()
        if product_data:
            json_images = product_data.get('images', [])
            for image in json_images:
                if isinstance(image, dict):
                    # Image is an object with src property
                    src = image.get('src', '')
                    if src:
                        # Convert to full URL if it's relative
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            src = f"https://{parse_url_domain(self.url)}{src}"
                        images.append(src)
                elif isinstance(image, str):
                    # Image is a direct URL string
                    if image.startswith('//'):
                        image = 'https:' + image
                    elif image.startswith('/'):
                        image = f"https://{parse_url_domain(self.url)}{image}"
                    images.append(image)
        
        # Fallback to DOM extraction
        if not images:
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
                found_images = self.find_elements_attr(selector, 'src')
                if found_images:
                    for img_src in found_images:
                        if img_src:
                            # Convert to full URL if it's relative
                            if img_src.startswith('//'):
                                img_src = 'https:' + img_src
                            elif img_src.startswith('/'):
                                img_src = f"https://{parse_url_domain(self.url)}{img_src}"
                            images.append(img_src)
                    break
        
        logger.debug(f"Found {len(images)} Shopify images")
        return images
    
    def extract_raw_data(self) -> Dict[str, Any]:
        """Extract raw data for debugging"""
        raw_data = super().extract_raw_data()
        raw_data['platform'] = 'shopify'
        
        # Add Shopify-specific data
        product_data = self._extract_structured_product_json()
        if product_data:
            raw_data['structured_json_found'] = True
            raw_data['product_json'] = {
                'title': product_data.get('title'),
                'vendor': product_data.get('vendor'),
                'variants_count': len(product_data.get('variants', [])),
                'images_count': len(product_data.get('images', [])),
                'options_count': len(product_data.get('options', []))
            }
        else:
            raw_data['structured_json_found'] = False
        
        return raw_data
    
    def _extract_structured_product_json(self) -> Optional[dict]:
        """Extract product JSON data from Shopify's structured data sources using all available methods"""
        try:
            all_product_data = []
            
            # Method 1: Look for Shopify's ProductJson script tags (most reliable)
            product_json_scripts = self.soup.find_all('script', id=re.compile(r'ProductJson-.*'))
            logger.debug(f"Found {len(product_json_scripts)} ProductJson script tags")
            for script in product_json_scripts:
                if script.string:
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and ('title' in data or 'variants' in data):
                            logger.debug("Found ProductJson script data")
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
                        logger.debug("Found data-product-json attribute")
                        all_product_data.append(('data-product-json', data))
                    except json.JSONDecodeError:
                        pass
            
            # Method 3: Look for JSON-LD structured data (application/ld+json)
            json_ld_scripts = self.soup.find_all('script', type='application/ld+json')
            logger.debug(f"Found {len(json_ld_scripts)} JSON-LD script tags")
            for script in json_ld_scripts:
                if script.string:
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and data.get('@type') == 'Product':
                            logger.debug("Found JSON-LD structured data")
                            converted_data = self._convert_json_ld_to_product_data(data)
                            all_product_data.append(('JSON-LD', converted_data))
                    except json.JSONDecodeError:
                        continue
            
            # Method 4: Look for window.Shopify.product data in script tags
            script_tags = self.soup.find_all('script')
            logger.debug(f"Found {len(script_tags)} total script tags")
            shopify_scripts = [s for s in script_tags if s.string and 'window.Shopify' in s.string]
            logger.debug(f"Found {len(shopify_scripts)} script tags containing 'window.Shopify'")
            
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
                            logger.debug("Found window.Shopify.product data")
                            all_product_data.append(('window.Shopify.product', data))
                        except json.JSONDecodeError:
                            continue
            
            # Method 5: Look for script tags with application/json type
            json_scripts = self.soup.find_all('script', type='application/json')
            logger.debug(f"Found {len(json_scripts)} application/json script tags")
            for script in json_scripts:
                if script.string:
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and 'product' in data:
                            logger.debug("Found application/json script with product data")
                            all_product_data.append(('application/json', data['product']))
                        elif isinstance(data, dict) and ('title' in data or 'variants' in data):
                            logger.debug("Found application/json script with product-like data")
                            all_product_data.append(('application/json', data))
                    except json.JSONDecodeError:
                        continue
            
            # Combine all found data
            if all_product_data:
                logger.debug(f"Found product data from {len(all_product_data)} different methods")
                combined_data = self._combine_product_data(all_product_data)
                return combined_data
            
            logger.debug("No structured product JSON data found")
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
                
            logger.debug(f"Merging data from {source_name}")
            
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
        
        logger.debug(f"Combined data from {len(all_product_data)} sources")
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