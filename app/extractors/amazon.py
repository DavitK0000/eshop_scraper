from typing import Optional, List
from app.extractors.base import BaseExtractor
from app.utils import map_currency_symbol_to_code, parse_url_domain, parse_price_with_regional_format, extract_number_from_text, sanitize_text
from app.logging_config import get_logger
import re
import json

logger = get_logger(__name__)


class AmazonExtractor(BaseExtractor):
    """Amazon-specific extractor for product information"""
    
    def extract_title(self) -> Optional[str]:
        """Extract product title from Amazon page"""
        title = self.find_element_text('#productTitle')
        if title:
            return title
        
        logger.warning("No Amazon title found")
        return None
    
    def extract_price(self) -> Optional[float]:
        """Extract product price from Amazon page"""
        price_whole = self.find_element_text('.a-price-whole')
        price_fraction = self.find_element_text('.a-price-fraction')
        if price_whole:
            price_str = price_whole + (price_fraction or '0')
            # price = parse_price_with_regional_format(price_str, parse_url_domain(self.url))
            price = float(price_str)
            if price:
                return price
        
        logger.warning("No Amazon price found")
        return None
    
    def extract_currency(self) -> Optional[str]:
        """Extract currency from Amazon page"""
        currency_symbol = self.find_element_text('.a-price-symbol')
        if currency_symbol:
            currency = map_currency_symbol_to_code(currency_symbol, parse_url_domain(self.url))
            return currency
        return None
    
    def extract_description(self) -> Optional[str]:
        """Extract product description from Amazon page"""
        # Try feature bullets first
        description = self.find_element_text('div#feature-bullets ul.a-unordered-list')
        if description:
            return description
        
        # Try product facts desktop
        description = self.find_element_text('div#productFactsDesktop_feature_div ul.a-unordered-list')
        if description:
            return description
        
        logger.warning("No Amazon description found")
        return None
    
    def extract_rating(self) -> Optional[float]:
        """Extract product rating from Amazon page"""
        rating_text = self.find_element_text('.a-icon-alt')
        if rating_text and 'out of 5 stars' in rating_text:
            try:
                rating = float(rating_text.split(' out of 5 stars')[0])
                return rating
            except ValueError:
                pass
        
        logger.warning("No Amazon rating found")
        return None
    
    def extract_review_count(self) -> Optional[int]:
        """Extract review count from Amazon page"""
        review_count_text = self.find_element_text('#acrCustomerReviewText')
        if review_count_text:
            review_count = extract_number_from_text(review_count_text)
            if review_count:
                return review_count
        
        logger.warning("No Amazon review count found")
        return None
    
    def extract_images(self) -> List[str]:
        """Extract product images from Amazon page using the same logic as the scraper"""
        images = []
        
        # Extract images from JavaScript data (more comprehensive)
        script_tags = self.soup.find_all('script', type='text/javascript')
        for script in script_tags:
            if script.string and 'colorImages' in script.string:
                try:
                    # Find the colorImages data in the script
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
                                    images.append(img_obj['hiRes'])
                                elif 'large' in img_obj and img_obj['large']:
                                    images.append(img_obj['large'])
                        except json.JSONDecodeError:
                            # Fallback to regex extraction if JSON parsing fails
                            hi_res_pattern = r'"hiRes":"([^"]+)"'
                            hi_res_matches = re.findall(hi_res_pattern, script.string)
                            for url in hi_res_matches:
                                images.append(url)
                except Exception as e:
                    logger.warning(f"Error parsing image script data: {e}")
        
        # Fallback to DOM extraction if no images found from script
        if not images:
            image_elements = self.soup.select('div#main-image-container ul.a-unordered-list li')
            for img in image_elements:
                img_tag = img.select_one('div.imgTagWrapperimg')
                if img_tag:
                    src = img_tag.get('data-old-hires')
                    if src:
                        images.append(src)
        
        return images
    
    def extract_specifications(self) -> dict:
        """Extract specifications from Amazon page using the same logic as the scraper"""
        specs = {}
        
        # Extract specifications from all aplus-tech-spec-table elements
        spec_tables = self.soup.select('table.aplus-tech-spec-table')
        
        for table in spec_tables:
            spec_elements = table.select('tbody>tr')
            for element in spec_elements:
                key_elem = element.select_one('th, td:first-child')
                value_elem = element.select_one('td:last-child')
                if key_elem and value_elem:
                    key = sanitize_text(key_elem.get_text())
                    value = sanitize_text(value_elem.get_text())
                    if key and value:
                        # If key already exists, append the new value
                        if key in specs:
                            specs[key] = specs[key] + " " + value
                        else:
                            specs[key] = value
        
        # Additional table selectors for specifications
        additional_table_selectors = [
            'table#productDetails_techSpec_section_1',
            'table#productDetails_techSpec_section_2',
            'table#productDetails_techSpec_section_3',
            'table#productDetails_detailBullets_sections1',
            'table#productDetails_detailBullets_sections2',
            'table#productDetails_detailBullets_sections3',
            'table.aplus-v2',
            'table.aplus',
            'table.prodDetTable',
            'table#prodDetails',
            'table#technicalSpecifications_section_1',
            'table#technicalSpecifications_section_2',
            'table#technicalSpecifications_section_3',
            'table#productDetailsTable',
            'table#specs-table',
            'table.specs-table',
            'table.tech-specs',
            'table.product-specs',
            'table#asinDetailBullets_feature_div table',
            'table#detail-bullets table',
            'table#feature-bullets table',
            'table.a-expander-content table',
            'table.a-expander-partial table',
            'table#aplus table',
            'table#aplus-3p table',
            'table#aplus-3p-content table'
        ]
        
        # Extract from additional table selectors
        for selector in additional_table_selectors:
            tables = self.soup.select(selector)
            for table in tables:
                spec_rows = table.select('tbody tr, tr')
                for row in spec_rows:
                    key_elem = row.select_one('th, td:first-child, .a-text-bold, .a-list-item .a-text-bold')
                    value_elem = row.select_one('td:last-child, .a-list-item span:not(.a-text-bold), .a-list-item')
                    
                    if key_elem and value_elem:
                        key = sanitize_text(key_elem.get_text())
                        value = sanitize_text(value_elem.get_text())
                        if key and value and key != value:  # Avoid duplicate key-value pairs
                            # If key already exists, append the new value
                            if key in specs:
                                specs[key] = specs[key] + " " + value
                            else:
                                specs[key] = value
        
        # If no specifications found, try alternative method
        if not specs:
            detail_bullets = self.soup.select('div#detailBullets_feature_div>ul>li')
            for bullet in detail_bullets:
                key_elem = bullet.select_one('span.a-list-item>span.a-text-bold')
                value_elem = bullet.select_one('span.a-list-item>span:not(.a-text-bold)')
                
                if key_elem and value_elem:
                    key = sanitize_text(key_elem.get_text())
                    value = sanitize_text(value_elem.get_text())
                    if key and value:
                        specs[key] = value
        
        # Additional bullet point selectors
        additional_bullet_selectors = [
            'div#feature-bullets ul li',
            'div#feature-bullets_feature_div ul li',
            'div#feature-bullets_feature_div ul.a-unordered-list li',
            'div#feature-bullets_feature_div ul.a-list-unordered li',
            'div#feature-bullets_feature_div ul.a-list-ordered li',
            'div#feature-bullets_feature_div ul.a-vertical-stack li',
            'div#feature-bullets_feature_div ul.a-spacing-base li',
            'div#feature-bullets_feature_div ul.a-spacing-mini li',
            'div#feature-bullets_feature_div ul.a-spacing-none li',
            'div#feature-bullets_feature_div ul.a-spacing-small li',
            'div#feature-bullets_feature_div ul.a-spacing-medium li',
            'div#feature-bullets_feature_div ul.a-spacing-large li',
            'div#feature-bullets_feature_div ul.a-spacing-extra-large li'
        ]
        
        # Extract from additional bullet point selectors
        for selector in additional_bullet_selectors:
            bullets = self.soup.select(selector)
            for bullet in bullets:
                key_elem = bullet.select_one('span.a-text-bold, .a-text-bold, strong, b')
                value_elem = bullet.select_one('span:not(.a-text-bold), :not(.a-text-bold)')
                
                if key_elem and value_elem:
                    key = sanitize_text(key_elem.get_text())
                    value = sanitize_text(value_elem.get_text())
                    if key and value and key != value:
                        specs[key] = value
        
        return specs 