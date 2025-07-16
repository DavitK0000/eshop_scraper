from typing import Optional
from app.scrapers.base import BaseScraper
from app.models import ProductInfo
from bs4 import BeautifulSoup
from app.utils import sanitize_text, extract_price_value, parse_url_domain, map_currency_symbol_to_code


class EbayScraper(BaseScraper):
    """eBay product scraper"""
    
    def _extract_description_from_html(self, html_content: str) -> tuple[str, str]:
        """
        Extract description text and HTML from HTML content
        
        Args:
            html_content: HTML content to parse
            
        Returns:
            tuple: (description_text, description_html)
        """
        if not html_content:
            return "", ""
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Try multiple selectors for description content
            description_selectors = [
                'h2#subtitle',
            ]
            
            description_text = ""
            description_html = ""
            
            for selector in description_selectors:
                description_element = soup.select_one(selector)
                if description_element:
                    description_html = str(description_element)
                    description_text = description_element.get_text(separator=' ', strip=True)
                    if description_text.strip():
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info(f"Found description using selector: {selector}")
                        break
            
            # If still no description, try to get all text content
            if not description_text:
                description_text = soup.get_text(separator=' ', strip=True)
                description_html = str(soup.find('body')) if soup.find('body') else str(soup)
            
            return description_text, description_html
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to extract description from HTML: {e}")
            return "", ""
    
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
                # Method 1: Try to fetch iframe content using requests (simple crawl)
                iframe = self.soup.select_one('iframe#desc_ifr')
                if iframe and iframe.get('src'):
                    iframe_src = iframe.get('src')
                    
                    # Make sure the URL is absolute
                    if iframe_src.startswith('//'):
                        iframe_src = 'https:' + iframe_src
                    elif iframe_src.startswith('/'):
                        # Extract domain from current URL
                        from urllib.parse import urlparse
                        parsed_url = urlparse(self.url)
                        iframe_src = f"{parsed_url.scheme}://{parsed_url.netloc}{iframe_src}"
                    
                    try:
                        import requests
                        import logging
                        logger = logging.getLogger(__name__)
                        
                        # Create headers similar to a real browser
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                            'Referer': self.url,
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                            'Accept-Language': 'en-US,en;q=0.5',
                            'Accept-Encoding': 'gzip, deflate',
                            'Connection': 'keep-alive',
                            'Upgrade-Insecure-Requests': '1',
                        }
                        
                        # Get cookies from the current page if available
                        cookies = {}
                        if hasattr(self, 'page') and hasattr(self.page, 'context'):
                            try:
                                # Get cookies from Playwright context
                                playwright_cookies = await self.page.context.cookies()
                                cookies = {cookie['name']: cookie['value'] for cookie in playwright_cookies}
                            except Exception as cookie_error:
                                logger.warning(f"Failed to get cookies from Playwright: {cookie_error}")
                        
                        # Fetch iframe content using requests
                        response = requests.get(
                            iframe_src, 
                            headers=headers, 
                            cookies=cookies, 
                            timeout=30,
                            allow_redirects=True
                        )
                        
                        if response.status_code == 200:
                            iframe_content = response.text
                            
                            # Use the dedicated function to extract description
                            description_text, description_html = self._extract_description_from_html(iframe_content)
                            if description_text:
                                logger.info("Found description using requests method")
                        
                        else:
                            logger.warning(f"Failed to fetch iframe content: HTTP {response.status_code}")
                    
                    except Exception as request_error:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to fetch iframe content with requests: {request_error}")
                
                # Method 2: Try JavaScript method as fallback
                if not description_text and hasattr(self, 'page') and self.page:
                    try:
                        # Use JavaScript to extract iframe content
                        iframe_content = await self.page.evaluate("""
                            () => {
                                const iframe = document.querySelector('iframe#desc_ifr');
                                if (iframe && iframe.contentDocument) {
                                    return iframe.contentDocument.body.innerHTML;
                                }
                                return null;
                            }
                        """)
                        
                        if iframe_content:
                            # Use the dedicated function to extract description
                            description_text, description_html = self._extract_description_from_html(iframe_content)
                            if description_text:
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.info("Found description using JavaScript method")
                    
                    except Exception as js_error:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"JavaScript iframe access failed: {js_error}")
                
                # Method 3: Try httpx as another alternative
                if not description_text and iframe and iframe.get('src'):
                    try:
                        import httpx
                        import logging
                        logger = logging.getLogger(__name__)
                        
                        # Create headers similar to a real browser
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                            'Referer': self.url,
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                            'Accept-Language': 'en-US,en;q=0.5',
                        }
                        
                        # Get cookies from the current page if available
                        cookies = {}
                        if hasattr(self, 'page') and hasattr(self.page, 'context'):
                            try:
                                # Get cookies from Playwright context
                                playwright_cookies = await self.page.context.cookies()
                                cookies = {cookie['name']: cookie['value'] for cookie in playwright_cookies}
                            except Exception as cookie_error:
                                logger.warning(f"Failed to get cookies from Playwright: {cookie_error}")
                        
                        # Fetch iframe content using httpx
                        async with httpx.AsyncClient(cookies=cookies, timeout=30.0) as client:
                            response = await client.get(iframe_src, headers=headers)
                            if response.status_code == 200:
                                iframe_content = response.text
                                
                                # Use the dedicated function to extract description
                                description_text, description_html = self._extract_description_from_html(iframe_content)
                                if description_text:
                                    logger.info("Found description using httpx method")
                            
                            else:
                                logger.warning(f"Failed to fetch iframe content with httpx: HTTP {response.status_code}")
                    
                    except Exception as httpx_error:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to fetch iframe content with httpx: {httpx_error}")
                
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
                'div.ux-image-carousel-item.image img',
            ]
            
            # Use a set to avoid duplicates
            unique_images = set()
            
            for selector in image_selectors:
                # Get both src and data-zoom-src attributes
                src_images = self.find_elements_attr(selector, 'src')
                zoom_images = self.find_elements_attr(selector, 'data-zoom-src')
                srcset_images = self.find_elements_attr(selector, 'srcset')
                
                
                # Add all images to the set
                for img_url in zoom_images:
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
                        from app.utils import sanitize_text, extract_price_value, parse_url_domain
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
        Extract price and currency from text using utility functions
        Returns tuple of (price, currency)
        """
        import logging
        
        logger = logging.getLogger(__name__)
        
        if not price_text:
            return None, None
        
        # Remove any extra whitespace
        price_text = price_text.strip()
        logger.info(f"Processing price text: '{price_text}'")
        
        # Use utility functions for currency and price extraction
        
        # Extract currency using utility function
        currency = map_currency_symbol_to_code(price_text, parse_url_domain(self.url) if self.url else None)
        
        # Extract price value using utility function
        price = extract_price_value(price_text, parse_url_domain(self.url) if self.url else None)
        
        if price is not None:
            logger.info(f"Extracted price: '{price}', currency: '{currency}' from '{price_text}'")
            return price, currency
        else:
            logger.warning(f"Failed to extract price from text: '{price_text}'")
            return None, currency
    
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