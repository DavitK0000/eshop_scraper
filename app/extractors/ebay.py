from typing import Optional, List, Dict, Any
from app.extractors.base import BaseExtractor
from app.models import ProductInfo
from bs4 import BeautifulSoup
from app.utils import (
    sanitize_text, 
    extract_price_value, 
    parse_url_domain, 
    map_currency_symbol_to_code
)
import re
import json
import requests
import httpx
from urllib.parse import urlparse
from app.logging_config import get_logger


class EbayExtractor(BaseExtractor):
    """eBay product information extractor"""
    
    def _extract_description_from_html(self, html_content: str) -> tuple[str, str]:
        """
        Extract description text and HTML from HTML content
        
        Args:
            html_content: HTML content to parse
            
        Returns:
            tuple: (description_text, description_html)
        """
        if not html_content:
            return "", ""
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Try multiple selectors for description content
            description_selectors = [
                'h2#subtitle',
            ]
            
            description_text = ""
            description_html = ""
            
            for selector in description_selectors:
                description_element = soup.select_one(selector)
                if description_element:
                    description_html = str(description_element)
                    description_text = description_element.get_text(separator=' ', strip=True)
                    if description_text.strip():
                        logger = get_logger(__name__)
                        logger.info(f"Found description using selector: {selector}")
                        break
            
            # If still no description, try to get all text content
            if not description_text:
                description_text = soup.get_text(separator=' ', strip=True)
                description_html = str(soup.find('body')) if soup.find('body') else str(soup)
            
            return description_text, description_html
            
        except Exception as e:
            logger = get_logger(__name__)
            logger.warning(f"Failed to extract description from HTML: {e}")
            return "", ""
    
    def extract_title(self) -> Optional[str]:
        """Extract product title"""
        return self.find_element_text('h1.x-item-title__mainTitle')
    
    def extract_price(self) -> Optional[float]:
        """Extract product price"""
        price_text = self.find_element_text('.x-price-primary')
        if price_text:
            price, _ = self._extract_price_and_currency(price_text)
            return price
        return None
    
    def extract_currency(self) -> Optional[str]:
        """Extract product currency"""
        price_text = self.find_element_text('.x-price-primary')
        if price_text:
            _, currency = self._extract_price_and_currency(price_text)
            return currency
        return None
    
    def extract_description(self) -> Optional[str]:
        """Extract product description"""
        description_text = ""
        
        try:
            # Method 1: Try to fetch iframe content using requests (simple crawl)
            iframe = self.soup.select_one('iframe#desc_ifr')
            if iframe and iframe.get('src'):
                iframe_src = iframe.get('src')
                
                # Make sure the URL is absolute
                if iframe_src.startswith('//'):
                    iframe_src = 'https:' + iframe_src
                elif iframe_src.startswith('/'):
                    # Extract domain from current URL
                    parsed_url = urlparse(self.url)
                    iframe_src = f"{parsed_url.scheme}://{parsed_url.netloc}{iframe_src}"
                
                try:
                    logger = get_logger(__name__)
                    
                    # Create headers similar to a real browser
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Referer': self.url,
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                    }
                    
                    # Fetch iframe content using requests
                    response = requests.get(
                        iframe_src, 
                        headers=headers, 
                        timeout=30,
                        allow_redirects=True
                    )
                    
                    if response.status_code == 200:
                        iframe_content = response.text
                        
                        # Use the dedicated function to extract description
                        description_text, _ = self._extract_description_from_html(iframe_content)
                        if description_text:
                            logger.info("Found description using requests method")
                    
                    else:
                        logger.warning(f"Failed to fetch iframe content: HTTP {response.status_code}")
                
                except Exception as request_error:
                    logger = get_logger(__name__)
                    logger.warning(f"Failed to fetch iframe content with requests: {request_error}")
            
            # Method 2: Try httpx as another alternative (synchronous version)
            if not description_text and iframe and iframe.get('src'):
                try:
                    logger = get_logger(__name__)
                    
                    # Create headers similar to a real browser
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Referer': self.url,
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                    }
                    
                    # Fetch iframe content using httpx synchronously
                    with httpx.Client(timeout=30.0) as client:
                        response = client.get(iframe_src, headers=headers)
                        if response.status_code == 200:
                            iframe_content = response.text
                            
                            # Use the dedicated function to extract description
                            description_text, _ = self._extract_description_from_html(iframe_content)
                            if description_text:
                                logger.info("Found description using httpx method")
                        
                        else:
                            logger.warning(f"Failed to fetch iframe content with httpx: HTTP {response.status_code}")
                
                except Exception as httpx_error:
                    logger = get_logger(__name__)
                    logger.warning(f"Failed to fetch iframe content with httpx: {httpx_error}")
            
        except Exception as e:
            logger = get_logger(__name__)
            logger.warning(f"Failed to extract description from iframe: {e}")
            
            # Fallback to direct extraction
            description_element = self.soup.select_one('div.x-item-description-child')
            if description_element:
                description_text = description_element.get_text(separator=' ', strip=True)
        
        return description_text if description_text else None
    
    def extract_images(self) -> List[str]:
        """Extract product images"""
        image_selectors = [
            'div.ux-image-carousel-item.image img',
        ]
        
        # Use a set to avoid duplicates
        unique_images = set()
        
        for selector in image_selectors:
            # Get both src and data-zoom-src attributes
            src_images = self.find_elements_attr(selector, 'src')
            zoom_images = self.find_elements_attr(selector, 'data-zoom-src')
            srcset_images = self.find_elements_attr(selector, 'srcset')
            
            # Add all images to the set
            for img_url in zoom_images:
                if img_url and img_url.strip():
                    # Clean the URL
                    img_url = img_url.strip()
                    # Remove any query parameters that might cause issues
                    if '?' in img_url:
                        img_url = img_url.split('?')[0]
                    unique_images.add(img_url)
        
        # Fallback: If we didn't find enough images, try alternative selectors
        if len(unique_images) < 2:
            logger = get_logger(__name__)
            logger.info("Few images found, trying alternative selectors...")
            
            # Try more generic selectors
            fallback_selectors = [
                'img[src*="ebayimg.com"]',
                'img[data-zoom-src*="ebayimg.com"]',
                '.ux-image img',
                '.image-treatment img',
                '[class*="image"] img',
                '[class*="carousel"] img'
            ]
            
            for selector in fallback_selectors:
                fallback_images = self.find_elements_attr(selector, 'src')
                fallback_zoom_images = self.find_elements_attr(selector, 'data-zoom-src')
                
                for img_url in fallback_images + fallback_zoom_images:
                    if img_url and img_url.strip():
                        img_url = img_url.strip()
                        if '?' in img_url:
                            img_url = img_url.split('?')[0]
                        unique_images.add(img_url)
            
            logger.info(f"After fallback selectors: {len(unique_images)} total unique images")
        
        # Log the number of images found for debugging
        logger = get_logger(__name__)
        logger.info(f"Found {len(unique_images)} unique images for eBay product")
        
        # Debug: Log the actual HTML structure around image carousel
        carousel_elements = self.soup.select('div.ux-image-carousel-item')
        logger.info(f"Found {len(carousel_elements)} carousel item elements")
        
        for i, carousel_item in enumerate(carousel_elements[:3]):  # Log first 3 items
            img_elements = carousel_item.select('img')
            logger.info(f"Carousel item {i}: {len(img_elements)} img elements")
            for j, img in enumerate(img_elements):
                src = img.get('src', '')
                zoom_src = img.get('data-zoom-src', '')
                logger.info(f"  Image {j}: src='{src[:50]}...', zoom_src='{zoom_src[:50]}...'")
        
        return list(unique_images)
    
    def extract_rating(self) -> Optional[float]:
        """Extract product rating"""
        return self.extract_rating_from_element('div.ux-summary span.ux-summary__start--rating span.ux-textspans')
    
    def extract_review_count(self) -> Optional[int]:
        """Extract review count"""
        return self._extract_review_count('div.ux-summary span.ux-summary__count span.ux-textspans')
    
    def extract_specifications(self) -> Dict[str, Any]:
        """Extract product specifications"""
        specs = {}
        spec_elements = self.soup.select('dl.ux-labels-values')
        for dl_element in spec_elements:
            # Get all dt (key) and dd (value) pairs
            dt_elements = dl_element.select('dt')
            dd_elements = dl_element.select('dd')
            
            # Match dt and dd elements by their position
            for i in range(min(len(dt_elements), len(dd_elements))):
                key_elem = dt_elements[i]
                value_elem = dd_elements[i]
                
                if key_elem and value_elem:
                    key = sanitize_text(key_elem.get_text())
                    value = sanitize_text(value_elem.get_text())
                    if key and value:
                        specs[key] = value
        
        return specs
    
    def _extract_price_and_currency(self, price_text: str) -> tuple[str, str]:
        """
        Extract price and currency from text using utility functions
        Returns tuple of (price, currency)
        """
        logger = get_logger(__name__)
        
        if not price_text:
            return None, None
        
        # Remove any extra whitespace
        price_text = price_text.strip()
        logger.info(f"Processing price text: '{price_text}'")
        
        # Use utility functions for currency and price extraction
        
        # Extract currency using utility function
        currency = map_currency_symbol_to_code(price_text, parse_url_domain(self.url) if self.url else None)
        
        # Extract price value using utility function
        price = extract_price_value(price_text, parse_url_domain(self.url) if self.url else None)
        
        if price is not None:
            logger.info(f"Extracted price: '{price}', currency: '{currency}' from '{price_text}'")
            return price, currency
        else:
            logger.warning(f"Failed to extract price from text: '{price_text}'")
            return None, currency
    
    def _extract_review_count(self, selector: str) -> Optional[int]:
        """
        Extract review count from text like '41 product ratings' or '123 reviews'
        """
        logger = get_logger(__name__)
        
        review_text = self.find_element_text(selector)
        logger.info(f"Review count selector '{selector}' returned text: '{review_text}'")
        
        if not review_text:
            logger.warning(f"No text found for review count selector: {selector}")
            return None
        
        # Remove any extra whitespace
        review_text = review_text.strip()
        logger.info(f"Cleaned review text: '{review_text}'")
        
        # Try multiple patterns to extract the number
        patterns = [
            r'^(\d+(?:,\d+)*)',  # Number at beginning
            r'(\d+(?:,\d+)*)',   # Any number
            r'(\d+)',            # Simple number
        ]
        
        for pattern in patterns:
            match = re.search(pattern, review_text)
            if match:
                number_str = match.group(1).replace(',', '')
                try:
                    result = int(number_str)
                    logger.info(f"Successfully extracted review count: {result} from '{review_text}'")
                    return result
                except ValueError:
                    logger.warning(f"Failed to convert '{number_str}' to int")
                    continue
        
        logger.warning(f"Could not extract review count from text: '{review_text}'")
        return None 