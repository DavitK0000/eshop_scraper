from typing import Optional
from app.scrapers.base import BaseScraper
from app.models import ProductInfo
from app.utils import map_currency_symbol_to_code, parse_url_domain
import re


class OttoScraper(BaseScraper):
    """Otto.de product scraper"""
    
    async def _wait_for_site_specific_content(self):
        """Wait for Otto.de specific content to load"""
        try:
            # Wait for Otto.de specific elements
            otto_selectors = [
                '[data-testid="product-title"]',
                '.prd_title',
                '.product-title',
                '.prd_price',
                '.product-price',
                '[data-testid="price"]',
                '.prd_image',
                '.product-image'
            ]
            
            for selector in otto_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=3000)
                    break
                except:
                    continue
                    
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Otto.de specific wait failed: {e}")
    
    async def extract_product_info(self) -> ProductInfo:
        """
        Extract product information from Otto.de product page
        """
        product_info = ProductInfo()
        
        try:
            # Extract title - Otto.de uses various title selectors
            title_selectors = [
                '.pdp_short-info__main-name',
                '.js_pdp_short-info__main-name'
            ]
            
            for selector in title_selectors:
                title = self.find_element_text(selector)
                if title and len(title.strip()) > 5:
                    product_info.title = title.strip()
                    break
            
            # Extract price - Otto.de price selectors
            price_selectors = [
                '.pdp_price__price-parts',
            ]
            
            for selector in price_selectors:
                price = self.extract_price_value(selector)
                if price:
                    product_info.price = price
                    break
            
            # Extract currency from price element
            currency_selectors = [
                '.pdp_price__price-parts',
            ]
            
            for selector in currency_selectors:
                currency_text = self.find_element_text(selector)
                if currency_text:
                    
                    print(currency_text)
                    # Handle Unicode escape sequences
                    if r'\u20ac' in currency_text:
                        currency_text = currency_text.replace(r'\u20ac', '€')
                    
                    # Use the existing utility function to map currency symbol to code
                    product_info.currency = map_currency_symbol_to_code(currency_text, parse_url_domain(self.url))
                    break
            
            # If no currency found, default to EUR for Otto.de
            if not product_info.currency:
                product_info.currency = "EUR"
            
            # Extract description - merge both description and selling points
            description_parts = []
            
            # Get main description
            description_selectors = [
                '.js_pdp_description',
                '.pdp_description',
                '.product-description'
            ]
            
            for selector in description_selectors:
                desc = self.find_element_text(selector)
                if desc and len(desc.strip()) > 10:
                    description_parts.append(desc.strip())
                    break
            
            # Get selling points
            selling_points_selectors = [
                '.pdp_selling-points',
                '.js_pdp_selling-points',
            ]
            
            for selector in selling_points_selectors:
                selling_points = self.find_element_text(selector)
                if selling_points and len(selling_points.strip()) > 10:
                    description_parts.append(selling_points.strip())
                    break
            
            # Merge all description parts
            if description_parts:
                product_info.description = '\n\n'.join(description_parts)
            
            # Extract rating
            rating_selectors = [
                '.pdp_cr-rating-score',
                '.js_pdp_cr-rating-score',
            ]
            
            for selector in rating_selectors:
                rating = self.extract_rating(selector)
                if rating:
                    product_info.rating = rating
                    break
            
            # Extract review count
            review_selectors = [
                '.js_pdp_cr-rating--review-count',
            ]
            
            for selector in review_selectors:
                review_text = self.find_element_text(selector)
                if review_text:
                    # Extract number from text like "123 Bewertungen" or "123 reviews"
                    review_count = self._extract_number_from_text(review_text)
                    if review_count:
                        product_info.review_count = review_count
                        break
            
            # Extract availability
            availability_selectors = [
                '.prd_availability',
                '.product-availability',
                '[data-testid="availability"]',
                '.availability',
                '.prd_stock',
                '.product-stock'
            ]
            
            for selector in availability_selectors:
                availability = self.find_element_text(selector)
                if availability:
                    product_info.availability = availability.strip()
                    break
            
            # Extract brand
            brand_selectors = [
                '.js_pdp_short-info__brand-link',
                '.pdp_short-info__brand-link',
            ]
            
            for selector in brand_selectors:
                brand = self.find_element_text(selector)
                if brand:
                    product_info.brand = brand.strip()
                    break
            
            # Extract SKU/Product ID
            sku_selectors = [
                '.prd_sku',
                '.product-sku',
                '[data-testid="sku"]',
                '.sku',
                '.prd_id',
                '.product-id'
            ]
            
            for selector in sku_selectors:
                sku = self.find_element_text(selector)
                if sku:
                    product_info.sku = sku.strip()
                    break
            
            # Extract category
            category_selectors = [
                '.prd_category',
                '.product-category',
                '[data-testid="category"]',
                '.category',
                '.breadcrumb',
                '.prd_breadcrumb'
            ]
            
            for selector in category_selectors:
                category = self.find_element_text(selector)
                if category:
                    product_info.category = category.strip()
                    break
            
            # Extract images - Otto.de image selectors
            image_selectors = [
                '.js_pdp_alternate-images__thumbnail-list img',
                '.pdp_alternate-images__thumbnail-list img',
            ]
            
            for selector in image_selectors:
                images = self.find_elements_attr(selector, 'src')
                if images:
                    # Filter out small images and duplicates
                    filtered_images = []
                    for img in images:
                        if img and len(img) > 10 and img not in filtered_images:
                            # Convert relative URLs to absolute
                            if img.startswith('//'):
                                img = 'https:' + img
                            elif img.startswith('/'):
                                img = 'https://www.otto.de' + img
                            
                            # Remove query parameters from image URLs
                            if '?' in img:
                                img = img.split('?')[0]
                            
                            filtered_images.append(img)
                    
                    product_info.images.extend(filtered_images)
                    break
            
            # Extract specifications from all tables
            specs = {}
            
            # Find all tables within the characteristics container
            spec_tables = self.soup.select('.pdp_details__characteristics-html table')
            
            for table in spec_tables:
                # Get all rows from each table
                rows = table.select('tbody tr')
                
                for row in rows:
                    # Key is in td with .left class, value is in regular td
                    key_elem = row.select_one('td.left')
                    value_elem = row.select_one('td:not(.left)')
                    
                    if key_elem and value_elem:
                        from app.utils import sanitize_text
                        key = sanitize_text(key_elem.get_text())
                        value = sanitize_text(value_elem.get_text())
                        if key and value:
                            specs[key] = value
                    elif row.name == 'li':
                        # Handle list items as features
                        text = sanitize_text(row.get_text())
                        if text and len(text) > 3:
                            specs[f"Feature {len(specs) + 1}"] = text
            
            product_info.specifications = specs
            
            # Store raw data for debugging
            product_info.raw_data = {
                'url': self.url,
                'final_url': self.final_url,
                'redirected': self.url != self.final_url,
                'html_length': len(self.html_content) if self.html_content else 0,
                'domain': 'otto.de'
            }
            
        except Exception as e:
            # Log error but don't fail completely
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error extracting Otto.de product info: {e}")
        
        return product_info
    
    def _extract_number_from_text(self, text: str) -> Optional[int]:
        """Extract number from text like '123 Bewertungen' or '123 reviews'"""
        if not text:
            return None
        
        # Remove common words and extract numbers
        text = text.lower()
        text = re.sub(r'(bewertungen|reviews|bewertung|review|mal|times)', '', text)
        
        # Find numbers in the text
        numbers = re.findall(r'\d+', text)
        if numbers:
            return int(numbers[0])
        
        return None 