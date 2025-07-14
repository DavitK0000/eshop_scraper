from typing import Optional
from app.scrapers.base import BaseScraper
from app.models import ProductInfo
from bs4 import BeautifulSoup


class EbayScraper(BaseScraper):
    """eBay product scraper"""
    
    async def extract_product_info(self) -> ProductInfo:
        """
        Extract product information from eBay product page
        This is a placeholder implementation
        """
        product_info = ProductInfo()
        
        try:
            # Placeholder selectors - these will need to be updated based on actual eBay page structure
            product_info.title = self.find_element_text('h1.x-item-title__mainTitle')
            
            # Extract price and currency together
            price_text = self.find_element_text('.x-price-primary')
            if price_text:
                price, currency = self._extract_price_and_currency(price_text)
                product_info.price = price
                product_info.currency = currency
            
            # Extract description from seller's HTML content (inside iframe)
            description_text = ""
            description_html = ""
            
            try:
                # Try to get description from iframe
                iframe = self.soup.select_one('iframe#desc_ifr')
                if iframe:
                    # Get iframe src URL
                    iframe_src = iframe.get('src')
                    if iframe_src:
                        # Make iframe src absolute if it's relative
                        if iframe_src.startswith('//'):
                            iframe_src = 'https:' + iframe_src
                        elif iframe_src.startswith('/'):
                            iframe_src = 'https://www.ebay.com' + iframe_src
                        
                        # Navigate to iframe content
                        await self.page.goto(iframe_src, wait_until='domcontentloaded', timeout=30000)
                        iframe_content = await self.page.content()
                        iframe_soup = BeautifulSoup(iframe_content, 'html.parser')
                        
                        # Extract description from iframe
                        description_element = iframe_soup.select_one('div.x-item-description-child')
                        if description_element:
                            description_html = str(description_element)
                            description_text = description_element.get_text(separator=' ', strip=True)
                        
                        # Navigate back to main page
                        await self.page.goto(self.url, wait_until='domcontentloaded', timeout=30000)
                        self.html_content = await self.page.content()
                        self.soup = BeautifulSoup(self.html_content, 'html.parser')
                
                # If iframe method failed, try direct extraction from main page
                if not description_text:
                    description_element = self.soup.select_one('div.x-item-description-child')
                    if description_element:
                        description_html = str(description_element)
                        description_text = description_element.get_text(separator=' ', strip=True)
                
                # Store description
                if description_text:
                    product_info.description = description_text
                    if not hasattr(product_info, 'raw_data'):
                        product_info.raw_data = {}
                    product_info.raw_data['description_html'] = description_html
                    
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to extract description from iframe: {e}")
                
                # Fallback to direct extraction
                description_element = self.soup.select_one('div.x-item-description-child')
                if description_element:
                    description_html = str(description_element)
                    description_text = description_element.get_text(separator=' ', strip=True)
                    product_info.description = description_text
                    if not hasattr(product_info, 'raw_data'):
                        product_info.raw_data = {}
                    product_info.raw_data['description_html'] = description_html
            product_info.rating = self.extract_rating('div.ux-summary span.ux-summary__start--rating span.ux-textspans')
            product_info.review_count = self._extract_review_count('div.ux-summary span.ux-summary__count span.ux-textspans')
            product_info.seller = self.find_element_text('.x-seller-overview__seller-name')
            product_info.availability = self.find_element_text('.x-item-condition__text')
            
            # Extract images with improved logic
            image_selectors = [
                'div.ux-image-carousel-item img',
                '.x-item-image__image',
                '.ux-image-magnify img',
                '.ux-image-carousel img'
            ]
            
            # Use a set to avoid duplicates
            unique_images = set()
            
            for selector in image_selectors:
                # Get both src and data-zoom-src attributes
                src_images = self.find_elements_attr(selector, 'src')
                zoom_images = self.find_elements_attr(selector, 'data-zoom-src')
                
                # Also get srcset images (high resolution versions)
                elements = self.soup.select(selector)
                srcset_images = []
                for element in elements:
                    srcset = element.get('srcset', '')
                    if srcset:
                        # Parse srcset to get the highest resolution image
                        srcset_parts = srcset.split(',')
                        for part in srcset_parts:
                            part = part.strip()
                            if part:
                                # Extract URL from srcset (format: "url width" or just "url")
                                url_part = part.split()[0] if ' ' in part else part
                                if url_part and url_part.startswith('http'):
                                    srcset_images.append(url_part)
                
                # Add all images to the set
                for img_url in src_images + zoom_images + srcset_images:
                    if img_url and img_url.strip():
                        # Clean the URL
                        img_url = img_url.strip()
                        # Remove any query parameters that might cause issues
                        if '?' in img_url:
                            img_url = img_url.split('?')[0]
                        unique_images.add(img_url)
            
            # Convert set back to list and add to product_info
            product_info.images.extend(list(unique_images))
            
            # Fallback: If we didn't find enough images, try alternative selectors
            if len(unique_images) < 2:
                logger.info("Few images found, trying alternative selectors...")
                
                # Try more generic selectors
                fallback_selectors = [
                    'img[src*="ebayimg.com"]',
                    'img[data-zoom-src*="ebayimg.com"]',
                    '.ux-image img',
                    '.image-treatment img',
                    '[class*="image"] img',
                    '[class*="carousel"] img'
                ]
                
                for selector in fallback_selectors:
                    fallback_images = self.find_elements_attr(selector, 'src')
                    fallback_zoom_images = self.find_elements_attr(selector, 'data-zoom-src')
                    
                    for img_url in fallback_images + fallback_zoom_images:
                        if img_url and img_url.strip():
                            img_url = img_url.strip()
                            if '?' in img_url:
                                img_url = img_url.split('?')[0]
                            unique_images.add(img_url)
                
                logger.info(f"After fallback selectors: {len(unique_images)} total unique images")
            
            # Log the number of images found for debugging
            logger.info(f"Found {len(unique_images)} unique images for eBay product")
            
            # Debug: Log the actual HTML structure around image carousel
            carousel_elements = self.soup.select('div.ux-image-carousel-item')
            logger.info(f"Found {len(carousel_elements)} carousel item elements")
            
            for i, carousel_item in enumerate(carousel_elements[:3]):  # Log first 3 items
                img_elements = carousel_item.select('img')
                logger.info(f"Carousel item {i}: {len(img_elements)} img elements")
                for j, img in enumerate(img_elements):
                    src = img.get('src', '')
                    zoom_src = img.get('data-zoom-src', '')
                    logger.info(f"  Image {j}: src='{src[:50]}...', zoom_src='{zoom_src[:50]}...'")
            
            # Extract specifications from dl.ux-labels-values
            specs = {}
            spec_elements = self.soup.select('dl.ux-labels-values')
            for dl_element in spec_elements:
                # Get all dt (key) and dd (value) pairs
                dt_elements = dl_element.select('dt')
                dd_elements = dl_element.select('dd')
                
                # Match dt and dd elements by their position
                for i in range(min(len(dt_elements), len(dd_elements))):
                    key_elem = dt_elements[i]
                    value_elem = dd_elements[i]
                    
                    if key_elem and value_elem:
                        from app.utils import sanitize_text
                        key = sanitize_text(key_elem.get_text())
                        value = sanitize_text(value_elem.get_text())
                        if key and value:
                            specs[key] = value
            
            product_info.specifications = specs
            
            # Store raw data for debugging
            product_info.raw_data = {
                'url': self.url,
                'html_length': len(self.html_content) if self.html_content else 0
            }
            
        except Exception as e:
            # Log error but don't fail completely
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error extracting eBay product info: {e}")
        
        return product_info
    
    def _extract_price_and_currency(self, price_text: str) -> tuple[str, str]:
        """
        Extract price and currency from text like '$309.99' or '€299.99'
        Returns tuple of (price, currency)
        """
        import re
        
        if not price_text:
            return None, None
        
        # Common currency symbols and their codes
        currency_map = {
            '$': 'USD',
            '€': 'EUR',
            '£': 'GBP',
            '¥': 'JPY',
            '₹': 'INR',
            '₽': 'RUB',
            '₩': 'KRW',
            '₪': 'ILS',
            '₨': 'PKR',
            '₦': 'NGN',
            '₡': 'CRC',
            '₫': 'VND',
            '₱': 'PHP',
            '₲': 'PYG',
            '₴': 'UAH',
            '₵': 'GHS',
            '₸': 'KZT',
            '₺': 'TRY',
            '₼': 'AZN',
            '₾': 'GEL',
            '₿': 'BTC'
        }
        
        # Remove any extra whitespace
        price_text = price_text.strip()
        
        # Try to match currency symbol at the beginning
        for symbol, currency_code in currency_map.items():
            if price_text.startswith(symbol):
                # Extract the price part (everything after the symbol)
                price_part = price_text[len(symbol):].strip()
                # Clean up the price (remove any non-numeric characters except decimal point)
                price = re.sub(r'[^\d.,]', '', price_part)
                # Replace comma with dot for decimal
                price = price.replace(',', '.')
                return price, currency_code
        
        # If no currency symbol found, try to extract from text patterns
        # Look for currency codes like USD, EUR, GBP, etc.
        currency_pattern = r'\b(USD|EUR|GBP|JPY|INR|RUB|KRW|ILS|PKR|NGN|CRC|VND|PHP|PYG|UAH|GHS|KZT|TRY|AZN|GEL|BTC)\b'
        currency_match = re.search(currency_pattern, price_text.upper())
        
        if currency_match:
            currency_code = currency_match.group(1)
            # Remove the currency code from the text and extract price
            price_part = re.sub(currency_pattern, '', price_text, flags=re.IGNORECASE).strip()
            price = re.sub(r'[^\d.,]', '', price_part)
            price = price.replace(',', '.')
            return price, currency_code
        
        # If still no currency found, default based on domain
        price = re.sub(r'[^\d.,]', '', price_text)
        price = price.replace(',', '.')
        
        # Default currency based on eBay domain
        if 'ebay.com' in self.url:
            default_currency = "USD"
        elif 'ebay.co.uk' in self.url:
            default_currency = "GBP"
        elif 'ebay.de' in self.url or 'ebay.fr' in self.url or 'ebay.it' in self.url or 'ebay.es' in self.url:
            default_currency = "EUR"
        else:
            default_currency = "USD"
        
        return price, default_currency
    
    def _extract_review_count(self, selector: str) -> Optional[int]:
        """
        Extract review count from text like '41 product ratings' or '123 reviews'
        """
        import re
        import logging
        
        logger = logging.getLogger(__name__)
        
        review_text = self.find_element_text(selector)
        logger.info(f"Review count selector '{selector}' returned text: '{review_text}'")
        
        if not review_text:
            logger.warning(f"No text found for review count selector: {selector}")
            return None
        
        # Remove any extra whitespace
        review_text = review_text.strip()
        logger.info(f"Cleaned review text: '{review_text}'")
        
        # Try multiple patterns to extract the number
        patterns = [
            r'^(\d+(?:,\d+)*)',  # Number at beginning
            r'(\d+(?:,\d+)*)',   # Any number
            r'(\d+)',            # Simple number
        ]
        
        for pattern in patterns:
            match = re.search(pattern, review_text)
            if match:
                number_str = match.group(1).replace(',', '')
                try:
                    result = int(number_str)
                    logger.info(f"Successfully extracted review count: {result} from '{review_text}'")
                    return result
                except ValueError:
                    logger.warning(f"Failed to convert '{number_str}' to int")
                    continue
        
        logger.warning(f"Could not extract review count from text: '{review_text}'")
        return None 