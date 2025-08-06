from typing import Optional, List, Dict, Any
from app.extractors.base import BaseExtractor
from app.models import ProductInfo
from app.utils import (
    sanitize_text, 
    extract_price_value
)
from app.logging_config import get_logger


class JDExtractor(BaseExtractor):
    """JD.com product information extractor"""
    
    def extract_title(self) -> Optional[str]:
        """Extract product title"""
        return self.find_element_text('.sku-name')
    
    def extract_price(self) -> Optional[float]:
        """Extract product price"""
        return self.extract_price_value('.p-price .price')
    
    def extract_currency(self) -> Optional[str]:
        """Extract product currency"""
        # JD.com typically uses CNY (Chinese Yuan)
        return "CNY"
    
    def extract_description(self) -> Optional[str]:
        """Extract product description"""
        return self.find_element_text('.news')
    
    def extract_images(self) -> List[str]:
        """Extract product images"""
        image_selectors = [
            '.spec-img img',
            '.zoom-thumb img',
            '.spec-n1 img'
        ]
        
        for selector in image_selectors:
            images = self.find_elements_attr(selector, 'src')
            if images:
                return images
        return []
    
    def extract_rating(self) -> Optional[float]:
        """Extract product rating"""
        return self.extract_rating_from_element('.comment-item .comment-star')
    
    def extract_review_count(self) -> Optional[int]:
        """Extract review count"""
        review_count_text = self.find_element_text('.comment-count')
        if review_count_text:
            return self.extract_number_from_text(review_count_text)
        return None
    
    def extract_specifications(self) -> Dict[str, Any]:
        """Extract product specifications"""
        specs = {}
        spec_elements = self.soup.select('.parameter2 li, .Ptable-item')
        for element in spec_elements:
            key_elem = element.select_one('.dt, .Ptable-item-name')
            value_elem = element.select_one('.dd, .Ptable-item-value')
            if key_elem and value_elem:
                key = sanitize_text(key_elem.get_text())
                value = sanitize_text(value_elem.get_text())
                if key and value:
                    specs[key] = value
        
        return specs 