from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup
import re
from app.extractors.base import BaseExtractor
from app.models import ProductInfo
from app.logging_config import get_logger
from app.utils.structured_data import StructuredDataExtractor

logger = get_logger(__name__)


class WooCommerceExtractor(BaseExtractor):
    """Extractor for WooCommerce-based e-commerce sites"""
    
    def __init__(self, html_content: str, url: str):
        super().__init__(html_content, url)
        self.platform = "woocommerce"
        
        # Try to extract data from structured data first
        self.structured_data_extractor = StructuredDataExtractor(html_content, url)
        self.product_data = self.structured_data_extractor.extract_structured_product_data()
        
        if self.product_data:
            logger.info("Successfully extracted WooCommerce product data from structured JSON")
        else:
            logger.info("No structured JSON data found, will use HTML extraction")
    
    def extract_title(self) -> Optional[str]:
        """Extract product title from WooCommerce page"""
        # Try structured data first
        if self.product_data and self.product_data.get('title'):
            return self.product_data['title']
        
        # Fallback to HTML extraction
        selectors = [
            'h1.product_title',
            '.product_title',
            'h1.entry-title',
            '.entry-title',
            'h1.title',
            '.product-name h1',
            '.product-name .title',
            'h1',
            '.product-title',
            '.woocommerce-loop-product__title',
        ]
        
        for selector in selectors:
            title = self.find_element_text(selector)
            if title and len(title.strip()) > 0:
                return title.strip()
        
        return None
    
    def extract_price(self) -> Optional[float]:
        """Extract product price from WooCommerce page"""
        # Try structured data first
        if self.product_data and self.product_data.get('price'):
            try:
                price_float = float(self.product_data['price'])
                return price_float
            except (ValueError, TypeError):
                pass
        
        # Fallback to HTML extraction
        price_selectors = [
            '.price .amount',
            '.price .woocommerce-Price-amount',
            '.price .woocommerce-Price-amount bdi',
            '.price del .amount',
            '.price ins .amount',
            '.woocommerce-Price-amount',
            '.woocommerce-Price-amount bdi',
            '.product-price .amount',
            '.product-price .woocommerce-Price-amount',
            '.single-product .price .amount',
            '.single-product .price .woocommerce-Price-amount',
            '.price',
            '.amount',
            '.woocommerce-variation-price .amount',
            '.woocommerce-variation-price .woocommerce-Price-amount',
        ]
        
        for selector in price_selectors:
            price_text = self.find_element_text(selector)
            if price_text:
                price = self.extract_price_value(price_text)
                if price:
                    return price
        
        return None
    
    def extract_description(self) -> Optional[str]:
        """Extract product description from WooCommerce page"""
        # Try structured data first
        if self.product_data and self.product_data.get('description'):
            return self.product_data['description']
        
        # Fallback to HTML extraction
        desc_selectors = [
            '.woocommerce-product-details__short-description',
            '.product-description',
            '.description',
            '.woocommerce-Tabs-panel--description',
            '.woocommerce-tabs .description',
            '.entry-content',
            '.product-summary .description',
            '.woocommerce-product-details__description',
            '.product .description',
            '.woocommerce-product-details__tab-description',
        ]
        
        for selector in desc_selectors:
            description = self.find_element_text(selector)
            if description and len(description.strip()) > 10:
                return description.strip()
        
        return None
    
    def extract_images(self) -> List[str]:
        """Extract product images from WooCommerce page"""
        # Try structured data first (now with enhanced image extraction)
        if self.product_data and self.product_data.get('images'):
            structured_images = self.product_data['images']
            if isinstance(structured_images, list) and structured_images:
                # The structured data utility now handles enhanced image extraction
                # including folder pattern matching, deduplication, and filtering
                cleaned_images = []
                for img_url in structured_images:
                    if img_url:
                        if img_url.startswith('//'):
                            img_url = 'https:' + img_url
                        elif img_url.startswith('/'):
                            img_url = self._make_absolute_url(img_url)
                        cleaned_images.append(img_url)
                if cleaned_images:
                    logger.info(f"WooCommerce: Found {len(cleaned_images)} images from enhanced structured data extraction")
                    return cleaned_images
        
        # Fallback to HTML extraction (simplified since structured data is preferred)
        images = []
        
        # WooCommerce specific image selectors
        image_selectors = [
            '.woocommerce-product-gallery__image img',
            '.product-gallery img',
            '.woocommerce-product-gallery img',
            '.product-images img',
            '.product-image img',
            '.woocommerce-product-gallery__wrapper img',
            '.flex-control-nav img',
            '.flex-active-slide img',
            '.product-thumbnails img',
            '.woocommerce-product-gallery__trigger img',
            '.woocommerce-product-gallery__image a img',
            '.product .images img',
            '.single-product .images img',
            '.woocommerce-product-gallery__image a',
            '.product-gallery a',
        ]
        
        for selector in image_selectors:
            img_urls = self.find_elements_attr(selector, 'src')
            for img_url in img_urls:
                if img_url and img_url not in images:
                    # Clean up image URL
                    if img_url.startswith('//'):
                        img_url = 'https:' + img_url
                    elif img_url.startswith('/'):
                        img_url = self._make_absolute_url(img_url)
                    images.append(img_url)
        
        # Also check for data attributes that might contain image URLs
        data_attrs = ['data-src', 'data-lazy-src', 'data-original']
        for attr in data_attrs:
            img_urls = self.find_elements_attr('img', attr)
            for img_url in img_urls:
                if img_url and img_url not in images:
                    if img_url.startswith('//'):
                        img_url = 'https:' + img_url
                    elif img_url.startswith('/'):
                        img_url = self._make_absolute_url(img_url)
                    images.append(img_url)
        
        # Remove duplicates and return
        if images:
            logger.info(f"WooCommerce: Found {len(images)} images from HTML extraction")
        return list(dict.fromkeys(images))
    
    def extract_currency(self) -> Optional[str]:
        """Extract currency from WooCommerce page"""
        # Try structured data first
        if self.product_data and self.product_data.get('currency'):
            return self.product_data['currency']
        
        # Fallback to HTML extraction
        # Check for currency in price elements
        price_elements = self.soup.find_all(class_=re.compile(r'price|amount'))
        for element in price_elements:
            text = element.get_text()
            # Look for currency symbols
            currency_patterns = [
                r'[\$€£¥₹₽₩₪₦₨₫₴₸₺₼₾₿]',
                r'(USD|EUR|GBP|JPY|INR|RUB|KRW|ILS|NGN|PKR|VND|UAH|KZT|TRY|AZN|GEL)',
            ]
            for pattern in currency_patterns:
                match = re.search(pattern, text)
                if match:
                    return match.group(0)
        
        return None
    
    def extract_rating(self) -> Optional[float]:
        """Extract product rating from WooCommerce page"""
        # Try structured data first
        if self.product_data and self.product_data.get('rating'):
            rating_data = self.product_data['rating']
            if isinstance(rating_data, dict) and rating_data.get('value'):
                try:
                    return float(rating_data['value'])
                except (ValueError, TypeError):
                    pass
        
        # Fallback to HTML extraction
        rating_selectors = [
            '.woocommerce-product-rating .star-rating',
            '.star-rating',
            '.woocommerce-product-rating .stars',
            '.product-rating .star-rating',
            '.rating .star-rating',
            '.woocommerce-product-rating',
            '.product-rating',
            '.rating',
        ]
        
        for selector in rating_selectors:
            rating = self.extract_rating_from_element(selector)
            if rating:
                return rating
        
        return None
    
    def extract_review_count(self) -> Optional[int]:
        """Extract review count from WooCommerce page"""
        # Try structured data first
        if self.product_data and self.product_data.get('rating'):
            rating_data = self.product_data['rating']
            if isinstance(rating_data, dict) and rating_data.get('review_count'):
                try:
                    return int(rating_data['review_count'])
                except (ValueError, TypeError):
                    pass
        
        # Fallback to HTML extraction
        review_selectors = [
            '.woocommerce-review-link',
            '.reviews_tab a',
            '.woocommerce-product-rating .woocommerce-review-link',
            '.product-rating .review-link',
            '.rating .review-count',
            '.woocommerce-product-rating .count',
        ]
        
        for selector in review_selectors:
            text = self.find_element_text(selector)
            if text:
                count = self.extract_number_from_text(text)
                if count:
                    return count
        
        return None
    
    def extract_specifications(self) -> Dict[str, Any]:
        """Extract product specifications from WooCommerce page"""
        specs = {}
        
        # WooCommerce specific specification selectors
        spec_selectors = [
            '.woocommerce-product-attributes',
            '.product-attributes',
            '.woocommerce-product-attributes-item',
            '.product-attributes-item',
            '.woocommerce-Tabs-panel--additional_information',
            '.woocommerce-tabs .additional_information',
            '.product-additional-information',
            '.woocommerce-product-attributes__item',
        ]
        
        for selector in spec_selectors:
            spec_elements = self.soup.select(selector)
            for element in spec_elements:
                # Look for key-value pairs
                key_elements = element.find_all(class_=re.compile(r'label|key|name'))
                value_elements = element.find_all(class_=re.compile(r'value|content'))
                
                for key_elem, value_elem in zip(key_elements, value_elements):
                    key = key_elem.get_text().strip()
                    value = value_elem.get_text().strip()
                    if key and value:
                        specs[key] = value
        
        return specs
    
    def extract_raw_data(self) -> Dict[str, Any]:
        """Extract raw data from WooCommerce page"""
        raw_data = {
            'platform': self.platform,
            'url': self.url,
            'woocommerce_data': {}
        }
        
        # Extract WooCommerce specific data
        # Check for WooCommerce JavaScript variables
        scripts = self.soup.find_all('script')
        for script in scripts:
            if script.string:
                script_content = script.string
                
                # Look for WooCommerce variables
                wc_vars = [
                    'wc_add_to_cart_params',
                    'wc_single_product_params',
                    'woocommerce_params',
                    'wc_cart_fragments_params',
                ]
                
                for var in wc_vars:
                    if var in script_content:
                        # Try to extract the variable value
                        pattern = rf'{var}\s*=\s*(\{{.*?\}})'
                        match = re.search(pattern, script_content, re.DOTALL)
                        if match:
                            try:
                                import json
                                raw_data['woocommerce_data'][var] = json.loads(match.group(1))
                            except:
                                raw_data['woocommerce_data'][var] = match.group(1)
        
        return raw_data
    
    def _make_absolute_url(self, relative_url: str) -> str:
        """Convert relative URL to absolute URL"""
        from urllib.parse import urljoin
        return urljoin(self.url, relative_url) 