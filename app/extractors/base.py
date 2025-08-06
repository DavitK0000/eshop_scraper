import logging
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup
from app.models import ProductInfo

logger = logging.getLogger(__name__)


class BaseExtractor:
    """Base class for extracting product information from HTML content"""
    
    def __init__(self, html_content: str, url: str):
        """
        Initialize extractor with HTML content
        
        Args:
            html_content: Raw HTML content from the page
            url: Original URL that was scraped
        """
        self.html_content = html_content
        self.url = url
        self.soup = BeautifulSoup(html_content, 'html.parser')
        
    def extract_product_info(self) -> ProductInfo:
        """
        Extract product information from HTML content
        
        Returns:
            ProductInfo object with extracted data
        """
        product_info = ProductInfo()
        
        try:
            # Extract basic information
            product_info.title = self.extract_title()
            product_info.price = self.extract_price()
            product_info.description = self.extract_description()
            product_info.images = self.extract_images()
            
            # Extract additional data
            product_info.raw_data = self.extract_raw_data()
            
            logger.info(f"Extracted product info: title='{product_info.title[:50]}...', price={product_info.price}")
            
        except Exception as e:
            logger.error(f"Error extracting product info: {e}")
            # Return empty product info on error
            product_info.raw_data = {'error': str(e)}
        
        return product_info
    
    def extract_title(self) -> Optional[str]:
        """Extract product title - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement extract_title")
    
    def extract_price(self) -> Optional[float]:
        """Extract product price - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement extract_price")
    
    def extract_description(self) -> Optional[str]:
        """Extract product description - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement extract_description")
    
    def extract_images(self) -> List[str]:
        """Extract product images - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement extract_images")
    
    def extract_raw_data(self) -> Dict[str, Any]:
        """Extract raw data for debugging - to be implemented by subclasses"""
        return {
            'url': self.url,
            'html_length': len(self.html_content),
            'extractor': self.__class__.__name__
        }
    
    def find_element_text(self, selector: str) -> Optional[str]:
        """Find element by CSS selector and return its text content"""
        try:
            element = self.soup.select_one(selector)
            if element:
                return element.get_text(strip=True)
        except Exception as e:
            logger.debug(f"Error finding element with selector '{selector}': {e}")
        return None
    
    def find_elements_attr(self, selector: str, attr: str) -> List[str]:
        """Find elements by CSS selector and return their attribute values"""
        try:
            elements = self.soup.select(selector)
            return [elem.get(attr) for elem in elements if elem.get(attr)]
        except Exception as e:
            logger.debug(f"Error finding elements with selector '{selector}': {e}")
        return []
    
    def extract_price_value(self, selector: str) -> Optional[float]:
        """Extract price value from element text"""
        try:
            price_text = self.find_element_text(selector)
            if price_text:
                # Remove currency symbols and non-numeric characters except decimal point
                import re
                price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
                if price_match:
                    return float(price_match.group())
        except Exception as e:
            logger.debug(f"Error extracting price from selector '{selector}': {e}")
        return None 