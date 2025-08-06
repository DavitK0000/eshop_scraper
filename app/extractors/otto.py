from typing import Optional, List, Dict, Any
from app.extractors.base import BaseExtractor
from app.models import ProductInfo
from app.utils import (
    sanitize_text, 
    extract_price_value, 
    parse_url_domain, 
    map_currency_symbol_to_code
)
import re
from app.logging_config import get_logger


class OttoExtractor(BaseExtractor):
    """Otto.de product information extractor"""
    
    def extract_title(self) -> Optional[str]:
        """Extract product title"""
        title_selectors = [
            '.pdp_short-info__main-name',
            '.js_pdp_short-info__main-name'
        ]
        
        for selector in title_selectors:
            title = self.find_element_text(selector)
            if title and len(title.strip()) > 5:
                return title.strip()
        return None
    
    def extract_price(self) -> Optional[float]:
        """Extract product price"""
        price_selectors = [
            '.pdp_price__price-parts',
        ]
        
        for selector in price_selectors:
            price = self.extract_price_value(selector)
            if price:
                return price
        return None
    
    def extract_currency(self) -> Optional[str]:
        """Extract product currency"""
        currency_selectors = [
            '.pdp_price__price-parts',
        ]
        
        for selector in currency_selectors:
            currency_text = self.find_element_text(selector)
            if currency_text:
                # Handle Unicode escape sequences
                if r'\u20ac' in currency_text:
                    currency_text = currency_text.replace(r'\u20ac', '€')
                
                # Use the existing utility function to map currency symbol to code
                currency = map_currency_symbol_to_code(currency_text, parse_url_domain(self.url))
                if currency:
                    return currency
        
        # If no currency found, default to EUR for Otto.de
        return "EUR"
    
    def extract_description(self) -> Optional[str]:
        """Extract product description"""
        description_parts = []
        
        # Get main description
        description_selectors = [
            '.js_pdp_description',
            '.pdp_description',
            '.product-description'
        ]
        
        for selector in description_selectors:
            desc = self.find_element_text(selector)
            if desc and len(desc.strip()) > 10:
                description_parts.append(desc.strip())
                break
        
        # Get selling points
        selling_points_selectors = [
            '.pdp_selling-points',
            '.js_pdp_selling-points',
        ]
        
        for selector in selling_points_selectors:
            selling_points = self.find_element_text(selector)
            if selling_points and len(selling_points.strip()) > 10:
                description_parts.append(selling_points.strip())
                break
        
        # Merge all description parts
        if description_parts:
            return '\n\n'.join(description_parts)
        
        return None
    
    def extract_images(self) -> List[str]:
        """Extract product images"""
        image_selectors = [
            'div.js_pdp_main-image__slide'
        ]
        
        images = []
        
        for selector in image_selectors:
            # Use soup to find image elements
            image_elements = self.soup.select(selector)
            
            for element in image_elements:
                # Try to get image from data-image-id attribute first
                image_id = element.get('data-image-id')
                if image_id:
                    image_src = f"https://i.otto.de/i/otto/{image_id}"
                    if image_src not in images:
                        images.append(image_src)
                    continue
                
                # Try to get image from src attribute
                image_src = element.get('src')
                if image_src:
                    # Handle relative URLs
                    if image_src.startswith('//'):
                        image_src = 'https:' + image_src
                    elif image_src.startswith('/'):
                        image_src = 'https://www.otto.de' + image_src
                    
                    if image_src not in images:
                        images.append(image_src)
                
                # Try to get image from data-src attribute (lazy loading)
                data_src = element.get('data-src')
                if data_src:
                    if data_src.startswith('//'):
                        data_src = 'https:' + data_src
                    elif data_src.startswith('/'):
                        data_src = 'https://www.otto.de' + data_src
                    
                    if data_src not in images:
                        images.append(data_src)
        
        return images
    
    def extract_rating(self) -> Optional[float]:
        """Extract product rating"""
        rating_selectors = [
            '.pdp_cr-rating-score',
            '.js_pdp_cr-rating-score',
        ]
        
        for selector in rating_selectors:
            rating = self.extract_rating_from_element(selector)
            if rating:
                return rating
        return None
    
    def extract_review_count(self) -> Optional[int]:
        """Extract review count"""
        review_selectors = [
            '.js_pdp_cr-rating--review-count',
        ]
        
        for selector in review_selectors:
            review_text = self.find_element_text(selector)
            if review_text:
                # Extract number from text like "123 Bewertungen" or "123 reviews"
                review_count = self.extract_number_from_text(review_text)
                if review_count:
                    return review_count
        return None
    
    def extract_specifications(self) -> Dict[str, Any]:
        """Extract product specifications"""
        specs = {}
        
        # Find all tables within the characteristics container
        spec_tables = self.soup.select('.pdp_details__characteristics-html table')
        
        for table in spec_tables:
            # Get all rows from each table
            rows = table.select('tbody tr')
            
            for row in rows:
                # Key is in td with .left class, value is in regular td
                key_elem = row.select_one('td.left')
                value_elem = row.select_one('td:not(.left)')
                
                if key_elem and value_elem:
                    key = sanitize_text(key_elem.get_text())
                    value = sanitize_text(value_elem.get_text())
                    if key and value:
                        specs[key] = value
                elif row.name == 'li':
                    # Handle list items as features
                    text = sanitize_text(row.get_text())
                    if text and len(text) > 3:
                        specs[f"Feature {len(specs) + 1}"] = text
        
        return specs 