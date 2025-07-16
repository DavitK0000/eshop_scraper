from typing import Optional
from urllib.parse import urlparse
from app.scrapers.base import BaseScraper
from app.scrapers.amazon import AmazonScraper
from app.scrapers.ebay import EbayScraper
from app.scrapers.jd import JDScraper
from app.scrapers.otto import OttoScraper
from app.scrapers.bol import BolScraper
from app.scrapers.cdiscount import CDiscountScraper


class ScraperFactory:
    """Factory class to create appropriate scrapers based on URL"""
    
    _scrapers = {
        'amazon.com': AmazonScraper,
        'www.amazon.com': AmazonScraper,
        'amazon.co.uk': AmazonScraper,
        'www.amazon.co.uk': AmazonScraper,
        'amazon.de': AmazonScraper,
        'www.amazon.de': AmazonScraper,
        'amazon.fr': AmazonScraper,
        'www.amazon.fr': AmazonScraper,
        'amazon.it': AmazonScraper,
        'www.amazon.it': AmazonScraper,
        'amazon.es': AmazonScraper,
        'www.amazon.es': AmazonScraper,
        'amazon.nl': AmazonScraper,
        'www.amazon.nl': AmazonScraper,
        'amazon.ca': AmazonScraper,
        'www.amazon.ca': AmazonScraper,
        'amazon.com.au': AmazonScraper,
        'www.amazon.com.au': AmazonScraper,
        'amazon.co.jp': AmazonScraper,
        'www.amazon.co.jp': AmazonScraper,
        'amazon.in': AmazonScraper,
        'www.amazon.in': AmazonScraper,
        'ebay.com': EbayScraper,
        'www.ebay.com': EbayScraper,
        'ebay.co.uk': EbayScraper,
        'www.ebay.co.uk': EbayScraper,
        'ebay.de': EbayScraper,
        'www.ebay.de': EbayScraper,
        'ebay.fr': EbayScraper,
        'www.ebay.fr': EbayScraper,
        'ebay.it': EbayScraper,
        'www.ebay.it': EbayScraper,
        'ebay.es': EbayScraper,
        'www.ebay.es': EbayScraper,
        'ebay.ca': EbayScraper,
        'www.ebay.ca': EbayScraper,
        'ebay.nl': EbayScraper,
        'www.ebay.nl': EbayScraper,
        'ebay.com.au': EbayScraper,
        'www.ebay.com.au': EbayScraper,
        'jd.com': JDScraper,
        'www.jd.com': JDScraper,
        'global.jd.com': JDScraper,
        'www.global.jd.com': JDScraper,
        'otto.de': OttoScraper,
        'www.otto.de': OttoScraper,
        'bol.com': BolScraper,
        'www.bol.com': BolScraper,
        'cdiscount.com': CDiscountScraper,
        'www.cdiscount.com': CDiscountScraper,
    }
    
    @classmethod
    def create_scraper(cls, url: str, proxy: Optional[str] = None, user_agent: Optional[str] = None, block_images: bool = True) -> BaseScraper:
        """
        Create appropriate scraper based on URL domain
        
        Args:
            url: Product URL to scrape
            proxy: Optional proxy to use
            user_agent: Optional user agent to use
            block_images: Whether to block image downloads to save bandwidth
            
        Returns:
            BaseScraper instance
        """
        domain = cls._extract_domain(url)
        scraper_class = cls._scrapers.get(domain)
        
        if scraper_class:
            return scraper_class(url, proxy, user_agent, block_images)
        else:
            # Return a generic scraper for unsupported domains
            return GenericScraper(url, proxy, user_agent, block_images)
    
    @classmethod
    def _extract_domain(cls, url: str) -> str:
        """Extract domain from URL"""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return ""
    
    @classmethod
    def is_supported_domain(cls, url: str) -> bool:
        """Check if domain is supported"""
        domain = cls._extract_domain(url)
        return domain in cls._scrapers
    
    @classmethod
    def get_supported_domains(cls) -> list:
        """Get list of supported domains"""
        return list(cls._scrapers.keys())


class GenericScraper(BaseScraper):
    """Generic scraper for unsupported domains"""
    
    async def extract_product_info(self):
        """
        Generic product information extraction
        This is a basic implementation that tries common selectors
        """
        from app.models import ProductInfo
        
        product_info = ProductInfo()
        
        try:
            # Try common selectors for product information
            common_selectors = {
                'title': [
                    'h1',
                    '.product-title',
                    '.product-name',
                    '[data-testid="product-title"]',
                    '.title',
                    'h1.product-title'
                ],
                'price': [
                    '.price',
                    '.product-price',
                    '.current-price',
                    '[data-testid="price"]',
                    '.amount',
                    '.value'
                ],
                'description': [
                    '.description',
                    '.product-description',
                    '.summary',
                    '[data-testid="description"]',
                    '.content'
                ],
                'images': [
                    '.product-image img',
                    '.gallery img',
                    '.main-image img',
                    '[data-testid="product-image"]',
                    '.image img'
                ]
            }
            
            # Extract title
            for selector in common_selectors['title']:
                title = self.find_element_text(selector)
                if title:
                    product_info.title = title
                    break
            
            # Extract price
            for selector in common_selectors['price']:
                price = self.extract_price_value(selector)
                if price:
                    product_info.price = price
                    break
            
            # Extract description
            for selector in common_selectors['description']:
                desc = self.find_element_text(selector)
                if desc:
                    product_info.description = desc
                    break
            
            # Extract images
            for selector in common_selectors['images']:
                images = self.find_elements_attr(selector, 'src')
                if images:
                    product_info.images.extend(images)
                    break
            
            # Store raw data
            product_info.raw_data = {
                'url': self.url,
                'html_length': len(self.html_content) if self.html_content else 0,
                'domain': ScraperFactory._extract_domain(self.url)
            }
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in generic scraper: {e}")
        
        return product_info 