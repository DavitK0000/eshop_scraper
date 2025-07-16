from typing import Optional
from app.scrapers.base import BaseScraper
from app.models import ProductInfo
from app.utils import map_currency_symbol_to_code, parse_url_domain


class AmazonScraper(BaseScraper):
    """Amazon product scraper"""
    
    async def extract_product_info(self) -> ProductInfo:
        """
        Extract product information from Amazon product page
        This is a placeholder implementation
        """
        product_info = ProductInfo()
        
        try:
            # Placeholder selectors - these will need to be updated based on actual Amazon page structure
            product_info.title = self.find_element_text('#productTitle')
            price_whole = self.find_element_text('.a-price-whole')
            price_fraction = self.find_element_text('.a-price-fraction')
            if price_whole:
                price_str = price_whole + (price_fraction or '0')
                product_info.price = float(price_str.replace(',', '.'))
            
            # Extract currency symbol and convert to 3-character code
            currency_symbol = self.find_element_text('.a-price-symbol')
            product_info.currency = map_currency_symbol_to_code(currency_symbol, parse_url_domain(self.url))
            
            product_info.description = self.find_element_text('div#feature-bullets>ul.a-unordered-list')
            product_info.rating = self.extract_rating('.a-icon-alt')
            product_info.review_count = self.find_element_text('#acrCustomerReviewText')
            product_info.availability = self.find_element_text('#availability')
            product_info.brand = self.find_element_text('#bylineInfo')
            
            # Extract images from JavaScript data (more comprehensive)
            script_tags = self.soup.find_all('script', type='text/javascript')
            for script in script_tags:
                if script.string and 'colorImages' in script.string:
                    try:
                        # Find the colorImages data in the script
                        import re
                        import json
                        
                        # Look for the colorImages object
                        pattern = r"'colorImages':\s*\{[^}]*'initial':\s*(\[[^\]]*\])"
                        match = re.search(pattern, script.string, re.DOTALL)
                        
                        if match:
                            # Extract the JSON array
                            images_data_str = match.group(1)
                            # Clean up the string to make it valid JSON
                            images_data_str = re.sub(r'(\w+):', r'"\1":', images_data_str)
                            images_data_str = re.sub(r'(\w+)\s*:', r'"\1":', images_data_str)
                            
                            try:
                                images_data = json.loads(images_data_str)
                                for img_obj in images_data:
                                    if 'hiRes' in img_obj and img_obj['hiRes']:
                                        product_info.images.append(img_obj['hiRes'])
                                    elif 'large' in img_obj and img_obj['large']:
                                        product_info.images.append(img_obj['large'])
                            except json.JSONDecodeError:
                                # Fallback to regex extraction if JSON parsing fails
                                hi_res_pattern = r'"hiRes":"([^"]+)"'
                                hi_res_matches = re.findall(hi_res_pattern, script.string)
                                for url in hi_res_matches:
                                    product_info.images.append(url)
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Error parsing image script data: {e}")
            
            # Fallback to DOM extraction if no images found from script
            if not product_info.images:
                image_elements = self.soup.select('div#main-image-container ul.a-unordered-list li')
                for img in image_elements:
                    img_tag = img.select_one('div.imgTagWrapperimg')
                    if img_tag:
                        src = img_tag.get('data-old-hires')
                        if src:
                            product_info.images.append(src)
            
            # Extract specifications from all aplus-tech-spec-table elements
            specs = {}
            spec_tables = self.soup.select('table.aplus-tech-spec-table')
            
            for table in spec_tables:
                spec_elements = table.select('tbody>tr')
                for element in spec_elements:
                    key_elem = element.select_one('th, td:first-child')
                    value_elem = element.select_one('td:last-child')
                    if key_elem and value_elem:
                        from app.utils import sanitize_text
                        key = sanitize_text(key_elem.get_text())
                        value = sanitize_text(value_elem.get_text())
                        if key and value:
                            # If key already exists, append the new value
                            if key in specs:
                                specs[key] = specs[key] + " " + value
                            else:
                                specs[key] = value
            
            product_info.specifications = specs
            
            # If no specifications found, try alternative method
            if not specs:
                detail_bullets = self.soup.select('div#detailBullets_feature_div>ul>li')
                for bullet in detail_bullets:
                    key_elem = bullet.select_one('span.a-list-item>span.a-text-bold')
                    value_elem = bullet.select_one('span.a-list-item>span:not(.a-text-bold)')
                    
                    if key_elem and value_elem:
                        from app.utils import sanitize_text
                        key = sanitize_text(key_elem.get_text())
                        value = sanitize_text(value_elem.get_text())
                        if key and value:
                            specs[key] = value
                
                product_info.specifications = specs
            
            # Third specification extraction method
            if not specs:
                tech_spec_table = self.soup.select_one('table#productDetails_techSpec_section_1')
                if tech_spec_table:
                    spec_rows = tech_spec_table.select('tbody tr')
                    for row in spec_rows:
                        key_elem = row.select_one('th')
                        value_elem = row.select_one('td')
                        
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
            logger.error(f"Error extracting Amazon product info: {e}")
        
        return product_info 