from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup
import re
import json
from app.extractors.base import BaseExtractor
from app.models import ProductInfo
from app.logging_config import get_logger
from app.utils.structured_data import StructuredDataExtractor
from app.utils import (
    map_currency_symbol_to_code, 
    parse_url_domain, 
    parse_price_with_regional_format, 
    extract_number_from_text, 
    sanitize_text
)

logger = get_logger(__name__)


class BigcommerceExtractor(BaseExtractor):
    """Extractor for Bigcommerce-based e-commerce sites"""
    
    def __init__(self, html_content: str, url: str):
        super().__init__(html_content, url)
        self.platform = "bigcommerce"
        
        # Try to extract data from structured data first
        self.structured_data_extractor = StructuredDataExtractor(html_content, url)
        self.product_data = self.structured_data_extractor.extract_structured_product_data()
        
        if self.product_data:
            logger.info("Successfully extracted Bigcommerce product data from structured JSON")
        else:
            logger.info("No structured JSON data found, will use HTML extraction")
        
        # Extract Bigcommerce-specific data
        self.bc_data = self._extract_bigcommerce_data()
    
    def _extract_bigcommerce_data(self) -> Optional[Dict[str, Any]]:
        """Extract Bigcommerce-specific data from the page"""
        try:
            soup = BeautifulSoup(self.html_content, 'html.parser')
            bc_data = {}
            
            # Look for Bigcommerce script tags with product data
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'window.product_attributes' in script.string:
                    try:
                        # Extract product attributes
                        match = re.search(r'window\.product_attributes\s*=\s*({.*?});', script.string, re.DOTALL)
                        if match:
                            data = json.loads(match.group(1))
                            bc_data['product_attributes'] = data
                            logger.info("Found Bigcommerce product_attributes data")
                    except (json.JSONDecodeError, AttributeError):
                        continue
                
                if script.string and ('window.BCData' in script.string or 'var BCData' in script.string):
                    try:
                        # Extract BCData - handle both window.BCData and var BCData patterns
                        match = re.search(r'(?:window\.BCData|var BCData)\s*=\s*({.*?});', script.string, re.DOTALL)
                        if match:
                            data = json.loads(match.group(1))
                            bc_data['bc_data'] = data
                            logger.info("Found Bigcommerce BCData")
                    except (json.JSONDecodeError, AttributeError):
                        continue
                
                if script.string and 'window.product' in script.string:
                    try:
                        # Extract product data
                        match = re.search(r'window\.product\s*=\s*({.*?});', script.string, re.DOTALL)
                        if match:
                            data = json.loads(match.group(1))
                            bc_data['product'] = data
                            logger.info("Found Bigcommerce product data")
                    except (json.JSONDecodeError, AttributeError):
                        continue
            
            # Look for Bigcommerce-specific meta tags
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                if meta.get('name') == 'product:price:amount':
                    bc_data['meta_price'] = meta.get('content')
                elif meta.get('name') == 'product:price:currency':
                    bc_data['meta_currency'] = meta.get('content')
                elif meta.get('name') == 'product:availability':
                    bc_data['meta_availability'] = meta.get('content')
            
            return bc_data if bc_data else None
            
        except Exception as e:
            logger.warning(f"Error extracting Bigcommerce data: {e}")
            return None
    
    def extract_title(self) -> Optional[str]:
        """Extract product title from Bigcommerce page"""
        # Try structured data first
        if self.product_data and self.product_data.get('title'):
            return self.product_data['title']
        
        # Try Bigcommerce-specific data
        if self.bc_data:
            if self.bc_data.get('product') and self.bc_data['product'].get('name'):
                return self.bc_data['product']['name']
            if self.bc_data.get('product_attributes') and self.bc_data['product_attributes'].get('name'):
                return self.bc_data['product_attributes']['name']
            if self.bc_data.get('bc_data') and self.bc_data['bc_data'].get('product_attributes'):
                # BCData might have product info in product_attributes
                pass  # Will be handled in other methods
        
        # Fallback to HTML extraction
        selectors = [
            'h1.productView-title',
            '.productView-title',
            'h1.product-name',
            '.product-name',
            'h1.title',
            '.title',
            'h1',
            '.product-title',
            '[data-test-id="product-title"]',
            '.productView h1',
        ]
        
        for selector in selectors:
            title = self.find_element_text(selector)
            if title and len(title.strip()) > 0:
                return title.strip()
        
        return None
    
    def extract_price(self) -> Optional[float]:
        """Extract product price from Bigcommerce page"""
        # Try structured data first
        if self.product_data and self.product_data.get('price'):
            try:
                price_float = float(self.product_data['price'])
                return price_float
            except (ValueError, TypeError):
                pass
        
        # Try Bigcommerce-specific data
        if self.bc_data:
            if self.bc_data.get('product') and self.bc_data['product'].get('price'):
                try:
                    return float(self.bc_data['product']['price'])
                except (ValueError, TypeError):
                    pass
            
            if self.bc_data.get('product_attributes') and self.bc_data['product_attributes'].get('price'):
                try:
                    return float(self.bc_data['product_attributes']['price'])
                except (ValueError, TypeError):
                    pass
            
            # Handle BCData product_attributes price structure
            if self.bc_data.get('bc_data') and self.bc_data['bc_data'].get('product_attributes'):
                product_attrs = self.bc_data['bc_data']['product_attributes']
                if product_attrs.get('price'):
                    price_data = product_attrs['price']
                    # Try different price fields in order of preference
                    for price_field in ['with_tax', 'without_tax', 'sale_price_with_tax', 'non_sale_price_with_tax']:
                        if price_data.get(price_field) and price_data[price_field].get('value'):
                            try:
                                return float(price_data[price_field]['value'])
                            except (ValueError, TypeError):
                                continue
        
        # Fallback to HTML extraction
        price_selectors = [
            '.price .price-current',
            '.price .price-current .price-value',
            '.price .price-current .price-sales',
            '.price .price-current .price-non-sale',
            '.productView-price .price-current',
            '.productView-price .price-current .price-value',
            '.price-current',
            '.price-value',
            '.price-sales',
            '.price-non-sale',
            '[data-test-id="product-price"]',
            '.productView-price',
            '.price',
        ]
        
        for selector in price_selectors:
            price_text = self.find_element_text(selector)
            if price_text:
                price = self.extract_price_value(price_text)
                if price:
                    return price
        
        return None
    
    def extract_description(self) -> Optional[str]:
        """Extract product description from Bigcommerce page"""
        # Try structured data first
        if self.product_data and self.product_data.get('description'):
            return self.product_data['description']
        
        # Try Bigcommerce-specific data
        if self.bc_data:
            if self.bc_data.get('product') and self.bc_data['product'].get('description'):
                return self.bc_data['product']['description']
            if self.bc_data.get('product_attributes') and self.bc_data['product_attributes'].get('description'):
                return self.bc_data['product_attributes']['description']
        
        # Fallback to HTML extraction
        desc_selectors = [
            '.productView-description',
            '.product-description',
            '.productView-info .productView-info-value',
            '.product-info .product-info-value',
            '.description',
            '.product-description-content',
            '[data-test-id="product-description"]',
            '.productView-info',
            '.product-info',
            # Accordion-based description
            '.accordion-item.product-description .tab-value.product-desc-content',
            '.accordion-item.product-description .tab-content__wrap .tab-value',
            '.accordion-item.product-description .accordion-content .tab-value',
        ]
        
        for selector in desc_selectors:
            desc = self.find_element_text(selector)
            if desc and len(desc.strip()) > 0:
                return desc.strip()
        
        return None
    
    def extract_images(self) -> List[str]:
        """Extract product images from Bigcommerce page"""
        images = []
        
        # Try structured data first
        if self.product_data and self.product_data.get('images'):
            images.extend(self.product_data['images'])
        
        # Try Bigcommerce-specific data
        if self.bc_data:
            if self.bc_data.get('product') and self.bc_data['product'].get('images'):
                product_images = self.bc_data['product']['images']
                if isinstance(product_images, list):
                    for img in product_images:
                        if isinstance(img, dict) and img.get('url'):
                            images.append(img['url'])
                        elif isinstance(img, str):
                            images.append(img)
            
            if self.bc_data.get('product_attributes') and self.bc_data['product_attributes'].get('images'):
                attr_images = self.bc_data['product_attributes']['images']
                if isinstance(attr_images, list):
                    for img in attr_images:
                        if isinstance(img, dict) and img.get('url'):
                            images.append(img['url'])
                        elif isinstance(img, str):
                            images.append(img)
        
        # Fallback to HTML extraction
        image_selectors = [
            '.productView-image img',
            '.productView-image .productView-img-original img',
            '.productView-image .productView-img-original',
            '.product-image img',
            '.product-image',
            '.productView-thumbnails img',
            '.productView-thumbnails .productView-thumbnail img',
            '.productView-thumbnails .productView-thumbnail',
            '[data-test-id="product-image"] img',
            '[data-test-id="product-image"]',
            '.productView-image',
            '.product-image',
        ]
        
        for selector in image_selectors:
            img_elements = self.soup.select(selector)
            for img in img_elements:
                src = img.get('src') or img.get('data-src') or img.get('data-lazy')
                if src:
                    # Normalize URL
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        from urllib.parse import urlparse
                        parsed_url = urlparse(self.url)
                        src = f"{parsed_url.scheme}://{parsed_url.netloc}{src}"
                    
                    if src not in images:
                        images.append(src)
        
        # Remove duplicates while preserving order
        unique_images = list(dict.fromkeys(images))
        return unique_images
    
    def extract_currency(self) -> Optional[str]:
        """Extract currency from Bigcommerce page"""
        # Try structured data first
        if self.product_data and self.product_data.get('currency'):
            return self.product_data['currency']
        
        # Try Bigcommerce-specific data
        if self.bc_data:
            if self.bc_data.get('meta_currency'):
                return self.bc_data['meta_currency']
            if self.bc_data.get('product') and self.bc_data['product'].get('currency'):
                return self.bc_data['product']['currency']
            
            # Handle BCData product_attributes currency
            if self.bc_data.get('bc_data') and self.bc_data['bc_data'].get('product_attributes'):
                product_attrs = self.bc_data['bc_data']['product_attributes']
                if product_attrs.get('price'):
                    price_data = product_attrs['price']
                    # Try different price fields for currency
                    for price_field in ['with_tax', 'without_tax', 'sale_price_with_tax', 'non_sale_price_with_tax']:
                        if price_data.get(price_field) and price_data[price_field].get('currency'):
                            return price_data[price_field]['currency']
        
        # Fallback to domain-based currency detection
        domain = parse_url_domain(self.url)
        return map_currency_symbol_to_code('', domain)
    
    def extract_rating(self) -> Optional[float]:
        """Extract product rating from Bigcommerce page"""
        # Try structured data first
        if self.product_data and self.product_data.get('rating'):
            rating_data = self.product_data['rating']
            if isinstance(rating_data, dict) and rating_data.get('value'):
                try:
                    return float(rating_data['value'])
                except (ValueError, TypeError):
                    pass
        
        # Try Bigcommerce-specific data
        if self.bc_data:
            if self.bc_data.get('product') and self.bc_data['product'].get('rating'):
                try:
                    return float(self.bc_data['product']['rating'])
                except (ValueError, TypeError):
                    pass
        
        # Fallback to HTML extraction
        rating_selectors = [
            '.rating .rating-value',
            '.rating .rating-score',
            '.productView-rating .rating-value',
            '.productView-rating .rating-score',
            '.rating-value',
            '.rating-score',
            '[data-test-id="product-rating"]',
            '.productView-rating',
            '.rating',
        ]
        
        for selector in rating_selectors:
            rating = self.extract_rating_from_element(selector)
            if rating:
                return rating
        
        return None
    
    def extract_review_count(self) -> Optional[int]:
        """Extract review count from Bigcommerce page"""
        # Try structured data first
        if self.product_data and self.product_data.get('rating'):
            rating_data = self.product_data['rating']
            if isinstance(rating_data, dict) and rating_data.get('review_count'):
                try:
                    return int(rating_data['review_count'])
                except (ValueError, TypeError):
                    pass
        
        # Try Bigcommerce-specific data
        if self.bc_data:
            if self.bc_data.get('product') and self.bc_data['product'].get('review_count'):
                try:
                    return int(self.bc_data['product']['review_count'])
                except (ValueError, TypeError):
                    pass
        
        # Fallback to HTML extraction
        review_selectors = [
            '.rating .rating-count',
            '.rating .review-count',
            '.productView-rating .rating-count',
            '.productView-rating .review-count',
            '.rating-count',
            '.review-count',
            '[data-test-id="product-review-count"]',
            '.productView-rating',
            '.rating',
        ]
        
        for selector in review_selectors:
            review_count = self.extract_number_from_text(self.find_element_text(selector))
            if review_count:
                return review_count
        
        return None
    
    def extract_specifications(self) -> Dict[str, Any]:
        """Extract product specifications from Bigcommerce page"""
        specs = {}
        
        # Try structured data first
        if self.product_data:
            if self.product_data.get('brand'):
                specs['brand'] = self.product_data['brand']
            if self.product_data.get('sku'):
                specs['sku'] = self.product_data['sku']
            if 'available' in self.product_data:
                specs['available'] = self.product_data['available']
        
        # Try Bigcommerce-specific data
        if self.bc_data:
            if self.bc_data.get('product'):
                product = self.bc_data['product']
                if product.get('brand'):
                    specs['brand'] = product['brand']
                if product.get('sku'):
                    specs['sku'] = product['sku']
                if 'available' in product:
                    specs['available'] = product['available']
            
            if self.bc_data.get('product_attributes'):
                attrs = self.bc_data['product_attributes']
                if attrs.get('brand'):
                    specs['brand'] = attrs['brand']
                if attrs.get('sku'):
                    specs['sku'] = attrs['sku']
                if 'available' in attrs:
                    specs['available'] = attrs['available']
            
            # Handle BCData product_attributes
            if self.bc_data.get('bc_data') and self.bc_data['bc_data'].get('product_attributes'):
                attrs = self.bc_data['bc_data']['product_attributes']
                if attrs.get('sku'):
                    specs['sku'] = attrs['sku']
                if 'instock' in attrs:
                    specs['available'] = attrs['instock']
                if 'purchasable' in attrs:
                    specs['purchasable'] = attrs['purchasable']
                if attrs.get('upc'):
                    specs['upc'] = attrs['upc']
                if attrs.get('mpn'):
                    specs['mpn'] = attrs['mpn']
                if attrs.get('gtin'):
                    specs['gtin'] = attrs['gtin']
                if attrs.get('weight'):
                    specs['weight'] = attrs['weight']
        
        # Extract specifications from HTML
        spec_selectors = [
            '.productView-info .productView-info-value',
            '.product-info .product-info-value',
            '.productView-info',
            '.product-info',
            '[data-test-id="product-specifications"]',
        ]
        
        for selector in spec_selectors:
            spec_elements = self.soup.select(selector)
            for element in spec_elements:
                # Look for label-value pairs
                label_elem = element.find_previous_sibling(class_=re.compile(r'label|title'))
                if label_elem:
                    label = label_elem.get_text(strip=True)
                    value = element.get_text(strip=True)
                    if label and value:
                        specs[label] = value
        
        # Extract specifications from accordion format
        accordion_specs = self.soup.select('.accordion-item.details .tab-content__wrap')
        for spec_wrap in accordion_specs:
            # Look for span (label) and div.tab-value (value) pairs
            label_elem = spec_wrap.find('span')
            value_elem = spec_wrap.find('div', class_='tab-value')
            
            if label_elem and value_elem:
                label = label_elem.get_text(strip=True)
                value = value_elem.get_text(strip=True)
                if label and value:
                    specs[label] = value
        
        return specs
    
    def extract_raw_data(self) -> Dict[str, Any]:
        """Extract raw data from Bigcommerce page"""
        raw_data = {
            'platform': 'bigcommerce',
            'url': self.url,
            'structured_json_found': bool(self.product_data),
            'bigcommerce_data_found': bool(self.bc_data)
        }
        
        if self.product_data:
            raw_data.update({
                'product_data': self.product_data,
                'title': self.product_data.get('title'),
                'price': self.product_data.get('price'),
                'currency': self.product_data.get('currency'),
                'description': self.product_data.get('description'),
                'brand': self.product_data.get('brand'),
                'sku': self.product_data.get('sku'),
                'available': self.product_data.get('available'),
                'rating': self.product_data.get('rating', {})
            })
        
        if self.bc_data:
            raw_data['bigcommerce_data'] = self.bc_data
        
        return raw_data 