from typing import Optional, List, Dict, Any
from app.extractors.base import BaseExtractor
from app.utils import map_currency_symbol_to_code, parse_url_domain, extract_number_from_text
from app.logging_config import get_logger

logger = get_logger(__name__)


class GenericExtractor(BaseExtractor):
    """Generic extractor for unsupported platforms"""
    
    def extract_title(self) -> Optional[str]:
        """Extract product title using common selectors"""
        common_selectors = [
            'h1',
            '.product-title',
            '.product-name',
            '[data-testid="product-title"]',
            '.title',
            'h1.product-title',
            '.product-name h1',
            '.product-info h1',
            '.product-details h1',
            'h1[itemprop="name"]',
            '.product-header h1',
            '.product-main h1'
        ]
        
        for selector in common_selectors:
            title = self.find_element_text(selector)
            if title:
                return title
        
        logger.warning("No title found with any common selector")
        return None
    
    def extract_price(self) -> Optional[float]:
        """Extract product price using common selectors"""
        common_selectors = [
            '.price',
            '.product-price',
            '.current-price',
            '[data-testid="price"]',
            '.amount',
            '.value',
            '.price-current',
            '.price-main',
            '.product-price .price',
            '.price-wrapper .price',
            '[itemprop="price"]',
            '.price-box .price',
            '.product-cost',
            '.product-value'
        ]
        
        for selector in common_selectors:
            price = self.extract_price_value(selector)
            if price:
                return price
        
        logger.warning("No price found with any common selector")
        return None
    
    def extract_description(self) -> Optional[str]:
        """Extract product description using common selectors"""
        common_selectors = [
            '.description',
            '.product-description',
            '.summary',
            '[data-testid="description"]',
            '.content',
            '.product-summary',
            '.product-details',
            '.product-info',
            '.product-content',
            '[itemprop="description"]',
            '.product-overview',
            '.product-text',
            '.product-detail',
            '.product-specs'
        ]
        
        for selector in common_selectors:
            desc = self.find_element_text(selector)
            if desc and len(desc) > 10:  # Ensure it's not just a few characters
                return desc
        
        logger.warning("No description found with any common selector")
        return None
    
    def extract_images(self) -> List[str]:
        """Extract product images using common selectors"""
        common_selectors = [
            '.product-image img',
            '.gallery img',
            '.main-image img',
            '[data-testid="product-image"]',
            '.image img',
            '.product-photo img',
            '.product-gallery img',
            '.product-images img',
            '.product-picture img',
            '.product-img img',
            '.product-thumbnail img',
            '.product-main-image img',
            '.product-hero img',
            '.product-visual img'
        ]
        
        for selector in common_selectors:
            images = self.find_elements_attr(selector, 'src')
            if images:
                # Filter out empty or invalid URLs
                valid_images = [img for img in images if img and img.startswith(('http://', 'https://'))]
                if valid_images:
                    return valid_images
        
        logger.warning("No images found with any common selector")
        return []
    
    def extract_currency(self) -> Optional[str]:
        """Extract currency using common selectors"""
        currency_selectors = [
            '[data-currency]',
            '.currency',
            '.price-currency',
            '[itemprop="priceCurrency"]',
            '.price .currency',
            '.amount .currency',
            '.value .currency'
        ]
        
        for selector in currency_selectors:
            currency = self.find_element_text(selector)
            if currency:
                # Map currency symbol to code
                currency_code = map_currency_symbol_to_code(currency, parse_url_domain(self.url))
                if currency_code:
                    return currency_code
        
        # Try to extract from price elements
        price_elements = self.soup.select('[class*="price"]')
        for element in price_elements:
            price_text = element.get_text()
            if price_text:
                # Look for currency symbols in price text
                currency_code = map_currency_symbol_to_code(price_text, parse_url_domain(self.url))
                if currency_code:
                    return currency_code
        
        logger.warning("No currency found with any common selector")
        return None
    
    def extract_rating(self) -> Optional[float]:
        """Extract rating using common selectors"""
        rating_selectors = [
            '.rating',
            '.product-rating',
            '[data-rating]',
            '[itemprop="ratingValue"]',
            '.stars',
            '.star-rating',
            '.product-stars',
            '.review-rating',
            '.rating-value'
        ]
        
        for selector in rating_selectors:
            rating = self.extract_rating_from_element(selector)
            if rating:
                return rating
        
        logger.warning("No rating found with any common selector")
        return None
    
    def extract_review_count(self) -> Optional[int]:
        """Extract review count using common selectors"""
        review_count_selectors = [
            '.review-count',
            '.reviews-count',
            '[data-review-count]',
            '[itemprop="reviewCount"]',
            '.rating + span',
            '.stars + span',
            '.product-reviews-count',
            '.review-count-text'
        ]
        
        for selector in review_count_selectors:
            review_count_text = self.find_element_text(selector)
            if review_count_text:
                review_count = extract_number_from_text(review_count_text)
                if review_count:
                    return review_count
        
        logger.warning("No review count found with any common selector")
        return None
    
    def extract_specifications(self) -> Dict[str, Any]:
        """Extract specifications using common selectors"""
        specs = {}
        
        # Try to extract from specification tables/lists
        spec_selectors = [
            '.specifications',
            '.product-specs',
            '.product-specifications',
            '.specs',
            '.product-details',
            '.product-info',
            '[class*="specification"]',
            '[class*="detail"]'
        ]
        
        for selector in spec_selectors:
            spec_element = self.soup.select_one(selector)
            if spec_element:
                # Extract key-value pairs from definition lists
                spec_items = spec_element.select('dt, .spec-label, .detail-label, .spec-key, .detail-key')
                for item in spec_items:
                    key = item.get_text(strip=True)
                    value_element = item.find_next_sibling('dd') or item.find_next_sibling('.spec-value') or item.find_next_sibling('.detail-value') or item.find_next_sibling('.spec-val') or item.find_next_sibling('.detail-val')
                    if value_element:
                        value = value_element.get_text(strip=True)
                        if key and value:
                            specs[key.lower().replace(' ', '_')] = value
                
                # If we found specs, break
                if specs:
                    break
        
        # Try to extract from meta tags
        if not specs:
            meta_specs = {
                'brand': self.soup.find('meta', attrs={'property': 'product:brand'})['content'] if self.soup.find('meta', attrs={'property': 'product:brand'}) else None,
                'category': self.soup.find('meta', attrs={'property': 'product:category'})['content'] if self.soup.find('meta', attrs={'property': 'product:category'}) else None,
                'availability': self.soup.find('meta', attrs={'property': 'product:availability'})['content'] if self.soup.find('meta', attrs={'property': 'product:availability'}) else None,
            }
            
            # Add non-None values
            for key, value in meta_specs.items():
                if value:
                    specs[key] = value
        
        return specs
    
    def extract_raw_data(self) -> dict:
        """Extract additional raw data for debugging"""
        raw_data = super().extract_raw_data()
        
        # Add some basic page analysis
        raw_data.update({
            'page_title': self.soup.title.string if self.soup.title else None,
            'meta_description': self.soup.find('meta', attrs={'name': 'description'})['content'] if self.soup.find('meta', attrs={'name': 'description'}) else None,
            'meta_keywords': self.soup.find('meta', attrs={'name': 'keywords'})['content'] if self.soup.find('meta', attrs={'name': 'keywords'}) else None,
            'h1_count': len(self.soup.find_all('h1')),
            'h2_count': len(self.soup.find_all('h2')),
            'img_count': len(self.soup.find_all('img')),
            'link_count': len(self.soup.find_all('a')),
            'form_count': len(self.soup.find_all('form')),
            'script_count': len(self.soup.find_all('script')),
            'css_count': len(self.soup.find_all('link', rel='stylesheet')),
        })
        
        return raw_data 