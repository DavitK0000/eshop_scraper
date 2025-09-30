from typing import Optional, List, Dict, Any
from app.extractors.base import BaseExtractor
from app.models import ProductInfo
from app.utils import (
    sanitize_text, 
    extract_price_from_text, 
    extract_price_value, 
    parse_url_domain, 
    parse_price_with_regional_format
)

import re
from app.logging_config import get_logger


class CDiscountExtractor(BaseExtractor):
    """CDiscount.com product information extractor"""
    
    def extract_title(self) -> Optional[str]:
        """Extract product title"""
        title_selectors = [
            '.c-fp-heading__title',
        ]
        
        for selector in title_selectors:
            title = self.find_element_text(selector)
            if title and len(title.strip()) > 5:
                return sanitize_text(title)
        return None
    
    def extract_price(self) -> Optional[float]:
        """Extract product price"""
        price_selectors = [
            '.c-price.c-price--xl.c-price--promo',  # New CDiscount price structure
            '.c-price[itemprop="price"]',  # Price with itemprop
        ]
        
        for selector in price_selectors:
            price_data = self.extract_cdiscount_price_and_currency(selector)
            if price_data and price_data.get('price'):
                return price_data['price']
        return None
    
    def extract_currency(self) -> Optional[str]:
        """Extract product currency"""
        price_selectors = [
            '.c-price.c-price--xl.c-price--promo',  # New CDiscount price structure
            '.c-price[itemprop="price"]',  # Price with itemprop
        ]
        
        for selector in price_selectors:
            price_data = self.extract_cdiscount_price_and_currency(selector)
            if price_data and price_data.get('currency'):
                return price_data['currency']
        
        # Set currency to Euro as fallback if not found
        return "EUR"
    
    def extract_description(self) -> Optional[str]:
        """Extract product description"""
        description_selectors = [
            'div#MarketingLongDescription',  # New CDiscount description structure
        ]
        
        for selector in description_selectors:
            description = self.find_element_text(selector)
            if description and len(description.strip()) > 20:
                return sanitize_text(description)
        return None
    
    def extract_images(self) -> List[str]:
        """Extract product images"""
        image_selectors = [
            'div.c-productViewer__thumb',  # New CDiscount image structure
        ]
        
        for selector in image_selectors:
            if 'c-productViewer__thumb' in selector:
                # Use the new image extraction method for c-productViewer__thumb
                images = self.extract_cdiscount_images_from_thumbnails()
            else:
                # Use the old method for other selectors
                images = self.find_elements_attr(selector, 'src')
                if images:
                    # Process and filter image URLs
                    processed_images = []
                    for img_url in images:
                        processed_url = self.process_cdiscount_image_url(img_url)
                        if processed_url:
                            processed_images.append(processed_url)
                    images = processed_images
            
            if images:
                return images
        return []
    
    def extract_rating(self) -> Optional[float]:
        """Extract product rating"""
        rating_selectors = [
            'span.c-stars-rating__text',  # New CDiscount rating structure
        ]
        
        for selector in rating_selectors:
            rating = self.extract_cdiscount_rating(selector)
            if rating:
                return rating
        return None
    
    def extract_review_count(self) -> Optional[int]:
        """Extract review count"""
        review_count_selectors = [
            'span.c-stars-rating__label',  # New CDiscount review count structure
            '.fpProductRating .fpReviewCount',
            '.fpProductRating .fpRatingCount',
            '.review-count',
            '.rating-count',
            '.fpProductRating .fpRatingSuffix'
        ]
        
        for selector in review_count_selectors:
            review_count = self.extract_cdiscount_review_count(selector)
            if review_count:
                return review_count
        return None
    
    def extract_specifications(self) -> Dict[str, Any]:
        """Extract product specifications"""
        specs_selectors = [
            'table.table.table--fpDescTb[aria-label="Product Features"]',  # New CDiscount specifications structure
        ]
        
        for selector in specs_selectors:
            specs = self.extract_cdiscount_specifications(selector)
            if specs:
                return specs
        return {}
    
    def extract_cdiscount_images_from_thumbnails(self) -> list:
        """Extract images from div.c-productViewer__thumb elements"""
        images = []
        
        try:
            if not self.soup:
                return images
            
            # Find all thumbnail elements
            thumbnail_elements = self.soup.find_all('div', class_='c-productViewer__thumb')
            
            for thumbnail in thumbnail_elements:
                try:
                    # Look for img elements within the thumbnail
                    img_elements = thumbnail.find_all('img')
                    
                    for img in img_elements:
                        img_url = img.get('src') or img.get('data-src')
                        if img_url:
                            processed_url = self.process_cdiscount_image_url(img_url)
                            if processed_url and processed_url not in images:
                                images.append(processed_url)
                    
                    # Also check for background images in CSS
                    style = thumbnail.get('style')
                    if style:
                        # Extract background-image URL from CSS
                        background_match = re.search(r'background-image:\s*url\(["\']?([^"\']+)["\']?\)', style)
                        if background_match:
                            img_url = background_match.group(1)
                            processed_url = self.process_cdiscount_image_url(img_url)
                            if processed_url and processed_url not in images:
                                images.append(processed_url)
                
                except Exception as e:
                    logger = get_logger(__name__)
                    logger.warning(f"Error extracting image from thumbnail: {e}")
                    continue
            
        except Exception as e:
            logger = get_logger(__name__)
            logger.warning(f"Error extracting CDiscount images from thumbnails: {e}")
        
        return images
    
    def process_cdiscount_image_url(self, image_url: str) -> Optional[str]:
        """Process CDiscount image URL to get full resolution"""
        if not image_url:
            return None
        
        try:
            # CDiscount often uses relative URLs or CDN URLs
            if image_url.startswith('//'):
                image_url = f"https:{image_url}"
            elif image_url.startswith('/'):
                image_url = f"https://www.cdiscount.com{image_url}"
            elif not image_url.startswith('http'):
                image_url = f"https://www.cdiscount.com/{image_url}"
            
            # Convert thumbnail size to full resolution (115x115 -> 700x700)
            # Pattern: .../115x115/... -> .../700x700/...
            image_url = re.sub(r'/(\d+)x(\d+)/', '/700x700/', image_url)
            
            return image_url
                
        except Exception as e:
            logger = get_logger(__name__)
            logger.warning(f"Error processing CDiscount image URL {image_url}: {e}")
            return None
    
    def extract_cdiscount_rating(self, rating_selector: str) -> Optional[float]:
        """Extract rating from CDiscount rating elements"""
        try:
            rating_text = self.find_element_text(rating_selector)
            if not rating_text:
                return None
            
            # CDiscount ratings are typically out of 5
            # Look for patterns like "4.5/5", "4,5/5", "4.5 étoiles", etc.
            rating_patterns = [
                r'(\d+[.,]\d+)\s*/\s*5',  # 4.5/5 or 4,5/5 (exact format from c-stars-rating__text)
                r'(\d+[.,]\d+)\s*étoiles?',  # 4.5 étoiles
                r'(\d+[.,]\d+)\s*stars?',  # 4.5 stars
                r'(\d+[.,]\d+)',  # Just the number
                r'(\d+)\s*/\s*5',  # 4/5
                r'(\d+)\s*étoiles?',  # 4 étoiles
                r'(\d+)\s*stars?'  # 4 stars
            ]
            
            for pattern in rating_patterns:
                match = re.search(pattern, rating_text, re.IGNORECASE)
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
                    
                    try:
                        if 0 <= rating <= 5:
                            return rating
                    except ValueError:
                        continue
            
            # Also check for star-based ratings in HTML
            star_selectors = [
                f"{rating_selector} .star",
                f"{rating_selector} .star-filled",
                f"{rating_selector} .star-active",
                f"{rating_selector} .fpStar",
                f"{rating_selector} .fpStarFilled"
            ]
            
            for star_selector in star_selectors:
                stars = self.soup.select(star_selector) if self.soup else []
                if stars:
                    # Count filled stars
                    filled_stars = len(stars)
                    return min(filled_stars, 5.0)
            
            return None
            
        except Exception as e:
            logger = get_logger(__name__)
            logger.warning(f"Error extracting CDiscount rating: {e}")
            return None
    
    def extract_review_count_from_text(self, text: str) -> Optional[int]:
        """Extract review count from text using patterns"""
        if not text:
            return None
        
        # Look for patterns like "123 avis", "123 reviews", "123 évaluations"
        review_patterns = [
            r'\((\d+)\s*reviews?\)',  # (82 reviews) - exact format from u-text--body-lead
            r'(\d+)\s*avis',  # 123 avis
            r'(\d+)\s*reviews?',  # 123 reviews
            r'(\d+)\s*évaluations?',  # 123 évaluations
            r'(\d+)\s*commentaires?',  # 123 commentaires
            r'(\d+)',  # Just the number
            r'\((\d+)\)',  # (123)
        ]
        
        for pattern in review_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    count = int(match.group(1))
                    if count >= 0:
                        return count
                except ValueError:
                    continue
        
        return None
    
    def extract_cdiscount_review_count(self, review_selector: str) -> Optional[int]:
        """Extract review count from CDiscount review elements"""
        try:
            review_text = self.find_element_text(review_selector)
            if not review_text:
                return None
            
            return self.extract_review_count_from_text(review_text)
            
        except Exception as e:
            logger = get_logger(__name__)
            logger.warning(f"Error extracting CDiscount review count: {e}")
            return None
    
    def extract_cdiscount_price_and_currency(self, price_selector: str) -> Optional[dict]:
        """Extract both price and currency from CDiscount price elements"""
        try:
            result = {'price': None, 'currency': None}
            
            if not self.soup:
                return result
            
            price_element = self.soup.select_one(price_selector)
            if not price_element:
                return result
            
            # Extract currency first
            currency_elem = price_element.select_one('[itemprop="priceCurrency"]')
            if currency_elem:
                currency = currency_elem.get_text(strip=True)
                if currency:
                    # Handle Unicode escape sequences
                    if r'\u20ac' in currency:
                        currency = currency.replace(r'\u20ac', '€')
                    
                    # Use the existing utility function to map currency symbol to code
                    from app.utils import map_currency_symbol_to_code
                    result['currency'] = map_currency_symbol_to_code(currency, parse_url_domain(self.url))
            
            # First, try to get the price from the content attribute (most reliable)
            content_price = price_element.get('content')
            if content_price:
                # Use regional format-aware parsing
                domain = parse_url_domain(self.url) if self.url else None
                price_value = extract_price_value(content_price, domain)
                if price_value is not None:
                    result['price'] = price_value
                    return result
                else:
                    # Fallback to simple comma replacement
                    try:
                        domain = parse_url_domain(self.url) if self.url else None
                        price_value = parse_price_with_regional_format(content_price, domain)
                        if price_value is not None:
                            result['price'] = price_value
                            return result
                    except ValueError:
                        pass
            
            # Try to extract from the new CDiscount price structure with separate main price and cents
            if 'c-price' in price_selector:
                # Look for the main price part
                main_price_elem = price_element.select_one('#DisplayPrice')
                cents_elem = price_element.select_one('#DisplayPriceCent')
                
                if main_price_elem and cents_elem:
                    main_price = main_price_elem.get_text(strip=True)
                    cents = cents_elem.get_text(strip=True)
                    
                    if main_price and cents:
                        try:
                            # Combine main price and cents
                            full_price = f"{main_price.strip()}.{cents.strip()}"
                            domain = parse_url_domain(self.url) if self.url else None
                            price_value = parse_price_with_regional_format(full_price, domain)
                            if price_value is not None:
                                result['price'] = price_value
                                return result
                        except ValueError:
                            pass
            
            # Fallback to text extraction
            price_text = self.find_element_text(price_selector)
            if not price_text:
                return result
            
            # Extract price using the utility function with regional format support
            domain = parse_url_domain(self.url) if self.url else None
            price_value = extract_price_value(price_text, domain)
            if price_value is not None:
                result['price'] = price_value
                return result
            
            # CDiscount specific price patterns with regional format support
            price_patterns = [
                r'(\d+[.,]\d{2})\s*€',  # 123,45 € or 123.45 €
                r'(\d+)\s*€',  # 123 €
                r'€\s*(\d+[.,]\d{2})',  # € 123,45 or € 123.45
                r'€\s*(\d+)',  # € 123
                r'(\d+[.,]\d{2})',  # 123,45 or 123.45
                r'(\d+)',  # 123
                r'€(\d+[.,]\d{2})',  # €123,45 or €123.45 (no space)
                r'€(\d+)',  # €123 (no space)
            ]
            
            for pattern in price_patterns:
                match = re.search(pattern, price_text)
                if match:
                    price_str = match.group(1)
                    # Use the regional format parser instead of simple comma replacement
                    price_value = extract_price_value(price_str, domain)
                    if price_value is not None:
                        result['price'] = price_value
                        return result
            
            return result
            
        except Exception as e:
            logger = get_logger(__name__)
            logger.warning(f"Error extracting CDiscount price and currency: {e}")
            return {'price': None, 'currency': None}
    
    def extract_cdiscount_specifications(self, specs_selector: str) -> dict:
        """Extract product specifications from CDiscount table structure"""
        specs = {}
        
        try:
            if not self.soup:
                return specs
            
            table = self.soup.select_one(specs_selector)
            if not table:
                # Try alternative selectors
                alternative_selectors = [
                    'table.table.table--fpDescTb[aria-label="Product Features"]',
                    'table.table--fpDescTb[aria-label="Product Features"]',
                    'table[aria-label="Product Features"]',
                    'table.table.table--fpDescTb',
                    '.table--fpDescTb',
                    'table[class*="fpDescTb"]',
                    'table[class*="table--fpDescTb"]'
                ]
                for alt_selector in alternative_selectors:
                    table = self.soup.select_one(alt_selector)
                    if table:
                        break
                if not table:
                    return specs
            
            # Find all rows in the table
            rows = table.find_all('tbody tr')
            
            if len(rows) == 0:
                # Try without tbody
                rows = table.find_all('tr')
            
            for row in rows:
                try:
                    # Find th and td elements in this row
                    th_elements = row.find_all('th')
                    td_elements = row.find_all('td')
                    
                    # Skip header rows and section headers (rows with colspan or only th elements)
                    if row.find('th', attrs={'colspan'}) or (len(th_elements) > 0 and len(td_elements) == 0):
                        continue
                    
                    # Process rows with exactly 1 th (key) and 1 td (value)
                    if len(th_elements) == 1 and len(td_elements) == 1:
                        key_elem = th_elements[0]
                        value_elem = td_elements[0]
                        
                        key = sanitize_text(key_elem.get_text(strip=True))
                        value = sanitize_text(value_elem.get_text(strip=True))
                        
                        if key and value:
                            specs[key] = value
                    
                except Exception as e:
                    logger = get_logger(__name__)
                    logger.warning(f"Error extracting specification row: {e}")
                    continue
            
        except Exception as e:
            logger = get_logger(__name__)
            logger.warning(f"Error extracting CDiscount specifications: {e}")
        
        return specs 
    
    def detect_cdiscount_captcha(self) -> bool:
        """
        Detect CDiscount specific captcha (altcha)
        
        Returns:
            True if CDiscount captcha is detected, False otherwise
        """
        try:
            if not self.soup:
                return False
            
            # Check for CDiscount specific captcha indicators
            cdiscount_captcha_selectors = [
                'div.captcha-container',
                'altcha-widget',
                'form#altcha-form',
                '#altcha_checkbox',
                '.altcha-checkbox',
                '.altcha-main',
                '.altcha-footer'
            ]
            
            for selector in cdiscount_captcha_selectors:
                elements = self.soup.select(selector)
                if elements:
                    logger = get_logger(__name__)
                    logger.info(f"CDiscount captcha detected via selector: {selector}")
                    return True
            
            # Check for French "I'm not a robot" text
            french_text = self.soup.find(text=re.compile(r'Je ne suis pas un robot', re.IGNORECASE))
            if french_text:
                logger = get_logger(__name__)
                logger.info("CDiscount captcha detected via French text")
                return True
            
            return False
            
        except Exception as e:
            logger = get_logger(__name__)
            logger.warning(f"Error detecting CDiscount captcha: {e}")
            return False

    
 