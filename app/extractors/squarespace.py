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


class SquarespaceExtractor(BaseExtractor):
    """Extractor for Squarespace-based e-commerce sites"""
    
    def __init__(self, html_content: str, url: str):
        super().__init__(html_content, url)
        self.platform = "squarespace"
        
        # Try to extract data from structured data first
        self.structured_data_extractor = StructuredDataExtractor(html_content, url)
        self.product_data = self.structured_data_extractor.extract_structured_product_data()
        
        if self.product_data:
            logger.info("Successfully extracted Squarespace product data from structured JSON")
        else:
            logger.info("No structured JSON data found, will use HTML extraction")
        
        # Extract Squarespace-specific data
        self.sq_data = self._extract_squarespace_data()
    
    def _extract_squarespace_data(self) -> Optional[Dict[str, Any]]:
        """Extract Squarespace-specific data from the page"""
        try:
            soup = BeautifulSoup(self.html_content, 'html.parser')
            sq_data = {}
            
            # Look for Squarespace script tags with product data
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'window.Squarespace' in script.string:
                    try:
                        # Extract Squarespace data
                        match = re.search(r'window\.Squarespace\s*=\s*({.*?});', script.string, re.DOTALL)
                        if match:
                            data = json.loads(match.group(1))
                            sq_data['squarespace'] = data
                            logger.info("Found Squarespace data")
                    except (json.JSONDecodeError, AttributeError):
                        continue
                
                if script.string and 'window.SQ' in script.string:
                    try:
                        # Extract SQ data
                        match = re.search(r'window\.SQ\s*=\s*({.*?});', script.string, re.DOTALL)
                        if match:
                            data = json.loads(match.group(1))
                            sq_data['sq'] = data
                            logger.info("Found SQ data")
                    except (json.JSONDecodeError, AttributeError):
                        continue
                
                if script.string and 'window.SQUARESPACE_CONTEXT' in script.string:
                    try:
                        # Extract context data
                        match = re.search(r'window\.SQUARESPACE_CONTEXT\s*=\s*({.*?});', script.string, re.DOTALL)
                        if match:
                            data = json.loads(match.group(1))
                            sq_data['context'] = data
                            logger.info("Found Squarespace context data")
                    except (json.JSONDecodeError, AttributeError):
                        continue
            
            # Look for Squarespace-specific meta tags
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                if meta.get('name') == 'product:price:amount':
                    sq_data['meta_price'] = meta.get('content')
                elif meta.get('name') == 'product:price:currency':
                    sq_data['meta_currency'] = meta.get('content')
                elif meta.get('name') == 'product:availability':
                    sq_data['meta_availability'] = meta.get('content')
            
            # Look for Squarespace-specific data attributes
            data_elements = soup.find_all(attrs={'data-sqs-product': True})
            for element in data_elements:
                try:
                    product_data = json.loads(element.get('data-sqs-product'))
                    sq_data['product_element'] = product_data
                    logger.info("Found Squarespace product element data")
                except (json.JSONDecodeError, AttributeError):
                    continue
            
            return sq_data if sq_data else None
            
        except Exception as e:
            logger.warning(f"Error extracting Squarespace data: {e}")
            return None
    
    def extract_title(self) -> Optional[str]:
        """Extract product title from Squarespace page"""
        # Try structured data first
        if self.product_data and self.product_data.get('title'):
            return self.product_data['title']
        
        # Try Squarespace-specific data
        if self.sq_data:
            if self.sq_data.get('product_element') and self.sq_data['product_element'].get('title'):
                return self.sq_data['product_element']['title']
            if self.sq_data.get('context') and self.sq_data['context'].get('product'):
                product = self.sq_data['context']['product']
                if product.get('title'):
                    return product['title']
        
        # Fallback to HTML extraction
        selectors = [
            'h1.product-title',
            '.product-title',
            'h1.product-name',
            '.product-name',
            'h1.title',
            '.title',
            'h1',
            '.product-title',
            '[data-sqs-product-title]',
            '.product h1',
            '.sqs-product h1',
        ]
        
        for selector in selectors:
            title = self.find_element_text(selector)
            if title and len(title.strip()) > 0:
                return title.strip()
        
        return None
    
    def extract_price(self) -> Optional[float]:
        """Extract product price from Squarespace page"""
        # Try structured data first
        if self.product_data and self.product_data.get('price'):
            try:
                price_float = float(self.product_data['price'])
                return price_float
            except (ValueError, TypeError):
                pass
        
        # Try Squarespace-specific data
        if self.sq_data:
            if self.sq_data.get('product_element') and self.sq_data['product_element'].get('price'):
                try:
                    return float(self.sq_data['product_element']['price'])
                except (ValueError, TypeError):
                    pass
            
            if self.sq_data.get('context') and self.sq_data['context'].get('product'):
                product = self.sq_data['context']['product']
                if product.get('price'):
                    try:
                        return float(product['price'])
                    except (ValueError, TypeError):
                        pass
        
        # Fallback to HTML extraction
        price_selectors = [
            '.product-price',
            '.product-price .price',
            '.product-price .amount',
            '.price',
            '.amount',
            '[data-sqs-product-price]',
            '.product .price',
            '.sqs-product .price',
            '.product-price-current',
            '.product-price-sales',
        ]
        
        for selector in price_selectors:
            price_text = self.find_element_text(selector)
            if price_text:
                price = self.extract_price_value(price_text)
                if price:
                    return price
        
        return None
    
    def extract_description(self) -> Optional[str]:
        """Extract product description from Squarespace page"""
        # Try structured data first
        if self.product_data and self.product_data.get('description'):
            return self.product_data['description']
        
        # Try Squarespace-specific data
        if self.sq_data:
            if self.sq_data.get('product_element') and self.sq_data['product_element'].get('description'):
                return self.sq_data['product_element']['description']
            if self.sq_data.get('context') and self.sq_data['context'].get('product'):
                product = self.sq_data['context']['product']
                if product.get('description'):
                    return product['description']
        
        # Fallback to HTML extraction
        desc_selectors = [
            '.product-description',
            '.product-description .description',
            '.description',
            '.product-info .description',
            '.sqs-product .description',
            '[data-sqs-product-description]',
            '.product .description',
            '.product-description-content',
        ]
        
        for selector in desc_selectors:
            desc = self.find_element_text(selector)
            if desc and len(desc.strip()) > 0:
                return desc.strip()
        
        return None
    
    def extract_images(self) -> List[str]:
        """Extract product images from Squarespace page"""
        images = []
        
        # Try structured data first
        if self.product_data and self.product_data.get('images'):
            images.extend(self.product_data['images'])
        
        # Try Squarespace-specific data
        if self.sq_data:
            if self.sq_data.get('product_element') and self.sq_data['product_element'].get('images'):
                product_images = self.sq_data['product_element']['images']
                if isinstance(product_images, list):
                    for img in product_images:
                        if isinstance(img, dict) and img.get('url'):
                            images.append(img['url'])
                        elif isinstance(img, str):
                            images.append(img)
            
            if self.sq_data.get('context') and self.sq_data['context'].get('product'):
                product = self.sq_data['context']['product']
                if product.get('images'):
                    context_images = product['images']
                    if isinstance(context_images, list):
                        for img in context_images:
                            if isinstance(img, dict) and img.get('url'):
                                images.append(img['url'])
                            elif isinstance(img, str):
                                images.append(img)
        
        # Fallback to HTML extraction
        image_selectors = [
            '.product-image img',
            '.product-image',
            '.product-gallery img',
            '.product-gallery .image img',
            '.sqs-product img',
            '.sqs-product .image img',
            '[data-sqs-product-image] img',
            '[data-sqs-product-image]',
            '.product .image img',
            '.product .image',
            '.product-image-container img',
            '.product-image-container',
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
        """Extract currency from Squarespace page"""
        # Try structured data first
        if self.product_data and self.product_data.get('currency'):
            return self.product_data['currency']
        
        # Try Squarespace-specific data
        if self.sq_data:
            if self.sq_data.get('meta_currency'):
                return self.sq_data['meta_currency']
            if self.sq_data.get('product_element') and self.sq_data['product_element'].get('currency'):
                return self.sq_data['product_element']['currency']
            if self.sq_data.get('context') and self.sq_data['context'].get('product'):
                product = self.sq_data['context']['product']
                if product.get('currency'):
                    return product['currency']
        
        # Fallback to domain-based currency detection
        domain = parse_url_domain(self.url)
        return map_currency_symbol_to_code('', domain)
    
    def extract_rating(self) -> Optional[float]:
        """Extract product rating from Squarespace page"""
        # Try structured data first
        if self.product_data and self.product_data.get('rating'):
            rating_data = self.product_data['rating']
            if isinstance(rating_data, dict) and rating_data.get('value'):
                try:
                    return float(rating_data['value'])
                except (ValueError, TypeError):
                    pass
        
        # Try Squarespace-specific data
        if self.sq_data:
            if self.sq_data.get('product_element') and self.sq_data['product_element'].get('rating'):
                try:
                    return float(self.sq_data['product_element']['rating'])
                except (ValueError, TypeError):
                    pass
            if self.sq_data.get('context') and self.sq_data['context'].get('product'):
                product = self.sq_data['context']['product']
                if product.get('rating'):
                    try:
                        return float(product['rating'])
                    except (ValueError, TypeError):
                        pass
        
        # Fallback to HTML extraction
        rating_selectors = [
            '.product-rating',
            '.product-rating .rating',
            '.rating',
            '.rating .rating-value',
            '.rating .rating-score',
            '[data-sqs-product-rating]',
            '.product .rating',
            '.sqs-product .rating',
        ]
        
        for selector in rating_selectors:
            rating = self.extract_rating_from_element(selector)
            if rating:
                return rating
        
        return None
    
    def extract_review_count(self) -> Optional[int]:
        """Extract review count from Squarespace page"""
        # Try structured data first
        if self.product_data and self.product_data.get('rating'):
            rating_data = self.product_data['rating']
            if isinstance(rating_data, dict) and rating_data.get('review_count'):
                try:
                    return int(rating_data['review_count'])
                except (ValueError, TypeError):
                    pass
        
        # Try Squarespace-specific data
        if self.sq_data:
            if self.sq_data.get('product_element') and self.sq_data['product_element'].get('review_count'):
                try:
                    return int(self.sq_data['product_element']['review_count'])
                except (ValueError, TypeError):
                    pass
            if self.sq_data.get('context') and self.sq_data['context'].get('product'):
                product = self.sq_data['context']['product']
                if product.get('review_count'):
                    try:
                        return int(product['review_count'])
                    except (ValueError, TypeError):
                        pass
        
        # Fallback to HTML extraction
        review_selectors = [
            '.product-reviews',
            '.product-reviews .review-count',
            '.review-count',
            '.reviews-count',
            '[data-sqs-product-review-count]',
            '.product .reviews',
            '.sqs-product .reviews',
        ]
        
        for selector in review_selectors:
            review_count = self.extract_number_from_text(self.find_element_text(selector))
            if review_count:
                return review_count
        
        return None
    
    def extract_specifications(self) -> Dict[str, Any]:
        """Extract product specifications from Squarespace page"""
        specs = {}
        
        # Try structured data first
        if self.product_data:
            if self.product_data.get('brand'):
                specs['brand'] = self.product_data['brand']
            if self.product_data.get('sku'):
                specs['sku'] = self.product_data['sku']
            if 'available' in self.product_data:
                specs['available'] = self.product_data['available']
        
        # Try Squarespace-specific data
        if self.sq_data:
            if self.sq_data.get('product_element'):
                product = self.sq_data['product_element']
                if product.get('brand'):
                    specs['brand'] = product['brand']
                if product.get('sku'):
                    specs['sku'] = product['sku']
                if 'available' in product:
                    specs['available'] = product['available']
            
            if self.sq_data.get('context') and self.sq_data['context'].get('product'):
                product = self.sq_data['context']['product']
                if product.get('brand'):
                    specs['brand'] = product['brand']
                if product.get('sku'):
                    specs['sku'] = product['sku']
                if 'available' in product:
                    specs['available'] = product['available']
        
        # Extract specifications from HTML
        spec_selectors = [
            '.product-info .product-info-item',
            '.product-info .product-info-value',
            '.product-info',
            '.sqs-product .product-info',
            '[data-sqs-product-specifications]',
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
        
        return specs
    
    def extract_raw_data(self) -> Dict[str, Any]:
        """Extract raw data from Squarespace page"""
        raw_data = {
            'platform': 'squarespace',
            'url': self.url,
            'structured_json_found': bool(self.product_data),
            'squarespace_data_found': bool(self.sq_data)
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
        
        if self.sq_data:
            raw_data['squarespace_data'] = self.sq_data
        
        return raw_data 