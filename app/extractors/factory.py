from typing import Optional
from app.extractors.base import BaseExtractor
from app.extractors.generic import GenericExtractor
from app.extractors.amazon import AmazonExtractor
from app.extractors.shopify import ShopifyExtractor
from app.extractors.ebay import EbayExtractor
from app.extractors.otto import OttoExtractor
from app.extractors.bol import BolExtractor
from app.extractors.jd import JDExtractor
from app.extractors.cdiscount import CDiscountExtractor
from app.logging_config import get_logger

logger = get_logger(__name__)


class ExtractorFactory:
    """Factory for creating appropriate extractors based on platform detection"""
    
    # Platform to extractor mapping
    _platform_extractors = {
        'amazon': AmazonExtractor,
        'shopify': ShopifyExtractor,
        'ebay': EbayExtractor,
        'otto': OttoExtractor,
        'bol': BolExtractor,
        'jd': JDExtractor,
        'cdiscount': CDiscountExtractor,
    }
    
    @classmethod
    def create_extractor(cls, platform: Optional[str], html_content: str, url: str) -> BaseExtractor:
        """
        Create appropriate extractor based on detected platform
        
        Args:
            platform: Detected platform name
            html_content: Raw HTML content from the page
            url: Original URL that was scraped
            
        Returns:
            BaseExtractor instance
        """
        if platform and platform.lower() in cls._platform_extractors:
            extractor_class = cls._platform_extractors[platform.lower()]
            extractor = extractor_class(html_content, url)
            logger.info(f"Created {extractor_class.__name__} for platform: {platform}")
            return extractor
        else:
            # Use generic extractor for unsupported platforms
            extractor = GenericExtractor(html_content, url)
            logger.info(f"Created GenericExtractor for platform: {platform or 'unknown'}")
            return extractor
    
    @classmethod
    def get_supported_platforms(cls) -> list:
        """Get list of supported platforms"""
        return list(cls._platform_extractors.keys())
    
    @classmethod
    def is_platform_supported(cls, platform: str) -> bool:
        """Check if platform is supported"""
        return platform.lower() in cls._platform_extractors 