from typing import Optional, List, Dict, Any
from app.extractors.base import BaseExtractor
from app.models import ProductInfo
from app.utils import (
    sanitize_text, 
    extract_price_value, 
    parse_url_domain, 
    parse_price_with_regional_format
)
import re
from app.logging_config import get_logger


class BolExtractor(BaseExtractor):
    """Bol.com product information extractor"""
    
    def extract_title(self) -> Optional[str]:
        """Extract product title"""
        title_selectors = [
            '[data-testid="product-title"]',
            '.product-title',
            '.product-name',
        ]
        
        for selector in title_selectors:
            title = self.find_element_text(selector)
            if title and len(title.strip()) > 5:
                return title
        return None
    
    def extract_price(self) -> Optional[float]:
        """Extract product price"""
        price_selectors = [
            '[data-test="price"]',
            '.promo-price',
        ]
        
        for selector in price_selectors:
            price = self.extract_bol_price(selector)
            if price:
                return price
        return None
    
    def extract_currency(self) -> Optional[str]:
        """Extract product currency"""
        # Set currency to Euro (Bol.com standard)
        return "EUR"
    
    def extract_description(self) -> Optional[str]:
        """Extract product description"""
        description_selectors = [
            '[data-test="product-description"]',
            '.product-description',
            '.description',
            '[data-test="description"]',
        ]
        
        for selector in description_selectors:
            description = self.find_element_text(selector)
            if description and len(description.strip()) > 20:
                return description
        return None
    
    def extract_images(self) -> List[str]:
        """Extract product images"""
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
                return filtered_images
        return []
    
    def extract_rating(self) -> Optional[float]:
        """Extract product rating"""
        rating_selectors = [
            '.pdp-header__rating',
            '.star-rating-experiment',
            '.text-neutral-text-high',
            '[data-test="rating"]',
        ]
        
        for selector in rating_selectors:
            rating = self.extract_bol_rating(selector)
            if rating:
                return rating
        return None
    
    def extract_review_count(self) -> Optional[int]:
        """Extract review count"""
        review_count_selectors = [
            '[data-test="rating-suffix"]',
            '.pdp-header__rating',
        ]
        
        for selector in review_count_selectors:
            review_count = self.extract_bol_review_count(selector)
            if review_count:
                return review_count
        return None
    
    def extract_specifications(self) -> Dict[str, Any]:
        """Extract product specifications"""
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
                        key = sanitize_text(key_elem.get_text())
                        value = sanitize_text(value_elem.get_text())
                        if key and value and len(key.strip()) > 0:
                            specs[key.strip()] = value.strip()
            
            if specs:
                break
        
        return specs
    
    def process_bol_image_url(self, image_url: str) -> Optional[str]:
        """
        Process Bol.com image URLs to get larger versions
        Converts URLs like: https://media.s-bol.com/72GLkKVnV9Ej/qxxmw30/59x210.jpg
        To: https://media.s-bol.com/72GLkKVnV9Ej/qxxmw30/550x550.jpg
        """
        if not image_url:
            return None
        
        try:
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
                    
                    logger = get_logger(__name__)
                    logger.info(f"Processed Bol.com image URL: {image_url} -> {new_url}")
                    return new_url
            
            # If we can't process it, return the original URL
            return image_url
            
        except Exception as e:
            logger = get_logger(__name__)
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
            return self.extract_rating_from_element(rating_selector)
            
        except Exception as e:
            logger = get_logger(__name__)
            logger.error(f"Error extracting Bol.com rating: {e}")
            # Fallback to the original method
            return self.extract_rating_from_element(rating_selector)
    
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
                # Look for pattern like "... uit 144 reviews"
                match = re.search(r'uit\s+(\d+)\s+reviews', aria_label)
                if match:
                    return int(match.group(1))
            
            # Try to get review count from visible text
            review_text = review_element.get_text()
            if review_text:
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
            logger = get_logger(__name__)
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
            # Remove any non-numeric characters except decimal point
            cleaned_price = re.sub(r'[^\d.]', '', combined_price)
            
            # Ensure we have a valid price format and convert to float
            if re.match(r'^\d+(\.\d{1,2})?$', cleaned_price):
                domain = parse_url_domain(self.url) if self.url else None
                price_value = parse_price_with_regional_format(cleaned_price, domain)
                return price_value
            
            return None
            
        except Exception as e:
            logger = get_logger(__name__)
            logger.error(f"Error extracting Bol.com price: {e}")
            # Fallback to the original method
            price_text = self.find_element_text(price_selector)
            if price_text:
                domain = parse_url_domain(self.url) if self.url else None
                return extract_price_value(price_text, domain)
            return None 