from typing import Optional, List
from app.extractors.base import BaseExtractor
from app.logging_config import get_logger

logger = get_logger(__name__)


class AmazonExtractor(BaseExtractor):
    """Amazon-specific extractor for product information"""
    
    def extract_title(self) -> Optional[str]:
        """Extract product title from Amazon page"""
        selectors = [
            '#productTitle',
            '.product-title',
            'h1.a-size-large',
            '.a-size-large.a-spacing-none',
            '[data-automation-id="product-title"]',
            '.a-size-large.a-color-base'
        ]
        
        for selector in selectors:
            title = self.find_element_text(selector)
            if title:
                logger.debug(f"Found Amazon title with selector '{selector}': {title[:50]}...")
                return title
        
        logger.warning("No Amazon title found")
        return None
    
    def extract_price(self) -> Optional[float]:
        """Extract product price from Amazon page"""
        selectors = [
            '.a-price-whole',
            '.a-price .a-offscreen',
            '.a-price-current .a-offscreen',
            '.a-price-range .a-offscreen',
            '.a-price .a-price-whole',
            '.a-price-current .a-price-whole',
            '.a-price-range .a-price-whole',
            '.a-price .a-price-symbol + .a-price-whole',
            '.a-price-current .a-price-symbol + .a-price-whole',
            '.a-price-range .a-price-symbol + .a-price-whole'
        ]
        
        for selector in selectors:
            price = self.extract_price_value(selector)
            if price:
                logger.debug(f"Found Amazon price with selector '{selector}': {price}")
                return price
        
        # Try to find price in span elements
        price_spans = self.soup.find_all('span', class_='a-price-whole')
        for span in price_spans:
            price_text = span.get_text(strip=True)
            if price_text:
                try:
                    # Remove commas and convert to float
                    price = float(price_text.replace(',', ''))
                    logger.debug(f"Found Amazon price in span: {price}")
                    return price
                except ValueError:
                    continue
        
        logger.warning("No Amazon price found")
        return None
    
    def extract_description(self) -> Optional[str]:
        """Extract product description from Amazon page"""
        selectors = [
            '#productDescription p',
            '.a-expander-content p',
            '.a-section.a-spacing-medium.a-spacing-top-small p',
            '.a-section.a-spacing-base p',
            '.a-section.a-spacing-small p',
            '.a-section.a-spacing-medium p',
            '.a-section.a-spacing-large p',
            '.a-section.a-spacing-base .a-text-left p',
            '.a-section.a-spacing-medium .a-text-left p',
            '.a-section.a-spacing-large .a-text-left p'
        ]
        
        descriptions = []
        for selector in selectors:
            desc_elements = self.soup.select(selector)
            for element in desc_elements:
                text = element.get_text(strip=True)
                if text and len(text) > 20:  # Ensure meaningful content
                    descriptions.append(text)
        
        if descriptions:
            # Join multiple description parts
            full_description = ' '.join(descriptions)
            logger.debug(f"Found Amazon description: {full_description[:100]}...")
            return full_description
        
        logger.warning("No Amazon description found")
        return None
    
    def extract_images(self) -> List[str]:
        """Extract product images from Amazon page"""
        # Amazon image selectors
        selectors = [
            '#landingImage',
            '.a-dynamic-image',
            '.a-image-stretch-vertical',
            '.a-image-stretch-horizontal',
            '.a-image-stretch-vertical img',
            '.a-image-stretch-horizontal img',
            '.a-image-stretch-vertical .a-dynamic-image',
            '.a-image-stretch-horizontal .a-dynamic-image',
            '.a-image-stretch-vertical .a-image-stretch-vertical',
            '.a-image-stretch-horizontal .a-image-stretch-horizontal'
        ]
        
        images = []
        for selector in selectors:
            img_elements = self.soup.select(selector)
            for img in img_elements:
                src = img.get('src') or img.get('data-src')
                if src and src.startswith(('http://', 'https://')):
                    # Convert to high-resolution version
                    if '_SS' in src:
                        # Replace with higher resolution
                        src = src.replace('_SS', '_SL1500')
                    elif '._SS' in src:
                        src = src.replace('._SS', '._SL1500')
                    
                    if src not in images:
                        images.append(src)
        
        # Also look for data-old-hires attribute (high-res images)
        for img in self.soup.find_all('img', attrs={'data-old-hires': True}):
            src = img.get('data-old-hires')
            if src and src.startswith(('http://', 'https://')) and src not in images:
                images.append(src)
        
        logger.debug(f"Found {len(images)} Amazon images")
        return images
    
    def extract_raw_data(self) -> dict:
        """Extract additional Amazon-specific data"""
        raw_data = super().extract_raw_data()
        
        # Amazon-specific data
        raw_data.update({
            'amazon_asin': self._extract_asin(),
            'amazon_rating': self._extract_rating(),
            'amazon_review_count': self._extract_review_count(),
            'amazon_availability': self._extract_availability(),
            'amazon_seller': self._extract_seller(),
            'amazon_brand': self._extract_brand(),
            'amazon_model': self._extract_model(),
            'amazon_color': self._extract_color(),
            'amazon_size': self._extract_size(),
        })
        
        return raw_data
    
    def _extract_asin(self) -> Optional[str]:
        """Extract Amazon ASIN from URL or page"""
        # Try to extract from URL first
        if '/dp/' in self.url:
            parts = self.url.split('/dp/')
            if len(parts) > 1:
                asin = parts[1].split('/')[0].split('?')[0]
                if len(asin) == 10:
                    return asin
        
        # Try to find in page data
        scripts = self.soup.find_all('script')
        for script in scripts:
            if script.string and 'ASIN' in script.string:
                import re
                asin_match = re.search(r'"ASIN":"([A-Z0-9]{10})"', script.string)
                if asin_match:
                    return asin_match.group(1)
        
        return None
    
    def _extract_rating(self) -> Optional[float]:
        """Extract product rating"""
        rating_selectors = [
            '.a-icon-alt',
            '.a-icon-star-small .a-icon-alt',
            '.a-icon-star .a-icon-alt',
            '.a-icon-star-medium .a-icon-alt',
            '.a-icon-star-large .a-icon-alt'
        ]
        
        for selector in rating_selectors:
            rating_text = self.find_element_text(selector)
            if rating_text and 'out of 5 stars' in rating_text:
                try:
                    rating = float(rating_text.split(' out of 5 stars')[0])
                    return rating
                except ValueError:
                    continue
        
        return None
    
    def _extract_review_count(self) -> Optional[int]:
        """Extract review count"""
        review_selectors = [
            '#acrCustomerReviewText',
            '.a-size-base.a-color-secondary',
            '.a-size-small.a-color-secondary'
        ]
        
        for selector in review_selectors:
            review_text = self.find_element_text(selector)
            if review_text and 'reviews' in review_text.lower():
                try:
                    import re
                    count_match = re.search(r'(\d+(?:,\d+)*)', review_text)
                    if count_match:
                        count = int(count_match.group(1).replace(',', ''))
                        return count
                except ValueError:
                    continue
        
        return None
    
    def _extract_availability(self) -> Optional[str]:
        """Extract product availability"""
        availability_selectors = [
            '#availability',
            '.a-size-medium.a-color-success',
            '.a-size-medium.a-color-price',
            '.a-size-medium.a-color-state'
        ]
        
        for selector in availability_selectors:
            availability = self.find_element_text(selector)
            if availability:
                return availability
        
        return None
    
    def _extract_seller(self) -> Optional[str]:
        """Extract seller information"""
        seller_selectors = [
            '#merchant-info',
            '.a-size-small.a-color-secondary',
            '.a-size-base.a-color-secondary'
        ]
        
        for selector in seller_selectors:
            seller = self.find_element_text(selector)
            if seller and ('sold by' in seller.lower() or 'shipped by' in seller.lower()):
                return seller
        
        return None
    
    def _extract_brand(self) -> Optional[str]:
        """Extract brand information"""
        brand_selectors = [
            '#bylineInfo',
            '.a-size-base.a-color-secondary',
            '.a-size-small.a-color-secondary'
        ]
        
        for selector in brand_selectors:
            brand = self.find_element_text(selector)
            if brand and 'by' in brand.lower():
                return brand
        
        return None
    
    def _extract_model(self) -> Optional[str]:
        """Extract model information"""
        # Look for model in product details
        detail_rows = self.soup.find_all('tr', class_='a-spacing-small')
        for row in detail_rows:
            label = row.find('td', class_='a-span3')
            value = row.find('td', class_='a-span9')
            if label and value:
                label_text = label.get_text(strip=True).lower()
                if 'model' in label_text:
                    return value.get_text(strip=True)
        
        return None
    
    def _extract_color(self) -> Optional[str]:
        """Extract color information"""
        color_selectors = [
            '#variation_color_name .selection',
            '.a-size-base.a-color-secondary',
            '.a-size-small.a-color-secondary'
        ]
        
        for selector in color_selectors:
            color = self.find_element_text(selector)
            if color and len(color) < 50:  # Color names are usually short
                return color
        
        return None
    
    def _extract_size(self) -> Optional[str]:
        """Extract size information"""
        size_selectors = [
            '#variation_size_name .selection',
            '.a-size-base.a-color-secondary',
            '.a-size-small.a-color-secondary'
        ]
        
        for selector in size_selectors:
            size = self.find_element_text(selector)
            if size and len(size) < 50:  # Size names are usually short
                return size
        
        return None 