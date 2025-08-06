from typing import Optional
from urllib.parse import urlparse
from app.scrapers.base import BaseScraper


class ScraperFactory:
    """Factory class to create generic scrapers - platform detection handled by ScrapingService"""
    
    @classmethod
    def create_generic_scraper(cls, url: str, proxy: Optional[str] = None, user_agent: Optional[str] = None, block_images: bool = True) -> BaseScraper:
        """
        Create a generic scraper for unsupported platforms
        
        Args:
            url: Product URL to scrape
            proxy: Optional proxy to use
            user_agent: Optional user agent to use
            block_images: Whether to block image downloads to save bandwidth
            
        Returns:
            BaseScraper instance
        """
        scraper = GenericScraper(url, proxy, user_agent, block_images)
        from app.config import settings
        domain = cls._extract_domain(url)
        browser_type = settings.get_browser_for_domain(domain)
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Created GenericScraper for {domain} using {browser_type} browser")
        return scraper
    
    @classmethod
    def _extract_domain(cls, url: str) -> str:
        """Extract domain from URL"""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return ""


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