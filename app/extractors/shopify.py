from typing import Optional, List, Dict, Any
import re
import json
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from app.extractors.base import BaseExtractor
from app.utils import (
    map_currency_symbol_to_code, 
    parse_url_domain, 
    parse_price_with_regional_format, 
    extract_number_from_text, 
    sanitize_text,
    StructuredDataExtractor
)
from app.logging_config import get_logger

logger = get_logger(__name__)


class ShopifyExtractor(BaseExtractor):
    """Shopify-specific extractor for product information"""
    
    def __init__(self, html_content: str, url: str):
        """
        Initialize extractor with HTML content and extract all data from structured JSON
        
        Args:
            html_content: Raw HTML content from the page
            url: Original URL that was scraped
        """
        super().__init__(html_content, url)
        
        # Use the structured data utility to extract product data
        self.structured_data_extractor = StructuredDataExtractor(html_content, url)
        self.product_data = self.structured_data_extractor.extract_structured_product_data()
        
        if self.product_data:
            logger.info("Successfully extracted Shopify product data from structured JSON")
            # logger.debug(f"Structured data keys: {list(self.product_data.keys())}")
            if 'images' in self.product_data:
                pass
        else:
            logger.warning("No structured JSON data found for Shopify product, trying ProductJson fallback")
            # Fallback to direct ProductJson extraction
            self.product_data = self._extract_product_json_fallback()
            if self.product_data:
                logger.info("Successfully extracted Shopify product data from ProductJson fallback")
                # logger.debug(f"Fallback data keys: {list(self.product_data.keys())}")
                if 'images' in self.product_data:
                    pass    
            else:
                logger.warning("No ProductJson data found for Shopify product")
        
        # Detect Yotpo once during initialization
        self.yotpo_detected = self._detect_yotpo()
        if self.yotpo_detected:
            logger.info("Yotpo detected during initialization")
        self.yotpo_data = None  # Will be populated when needed
        
        # Detect Trustpilot once during initialization
        self.trustpilot_detected = self._detect_trustpilot()
        if self.trustpilot_detected:
            logger.info("Trustpilot detected during initialization")
        self.trustpilot_data = None  # Will be populated when needed
        
        # Custom CSS selectors for element-based extraction
        self.custom_rating_selectors = []
        self.custom_review_count_selectors = []
    
    def _get_yotpo_data(self) -> Optional[Dict[str, Any]]:
        """
        Get Yotpo rating data, extracting it only once if needed.
        
        Returns:
            Yotpo rating data dictionary or None if not available
        """
        if not self.yotpo_detected:
            logger.info("Yotpo not detected, returning None")
            return None
        
        if self.yotpo_data is None:
            logger.info("Extracting Yotpo data for the first time")
            self.yotpo_data = self._extract_yotpo_rating_data()
            if self.yotpo_data:
                logger.info(f"Yotpo data extracted and cached: {self.yotpo_data}")
            else:
                logger.info("No Yotpo data found")
        else:
            logger.info(f"Using cached Yotpo data: {self.yotpo_data}")
        
        return self.yotpo_data
    
    def _extract_number_from_yotpo_text(self, text: str) -> Optional[int]:
        """
        Extract number from Yotpo text content.
        
        Args:
            text: Text content that may contain review count
            
        Returns:
            Extracted number or None
        """
        if not text:
            return None
        
        try:
            # Look for patterns like "123 reviews", "123", "(123)", etc.
            number_patterns = [
                r'(\d+(?:,\d+)*)\s*reviews?',
                r'(\d+(?:,\d+)*)\s*ratings?',
                r'(\d+(?:,\d+)*)',
                r'\((\d+(?:,\d+)*)\)'
            ]
            
            for pattern in number_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    number_str = match.group(1).replace(',', '')
                    try:
                        return int(number_str)
                    except ValueError:
                        continue
            
            return None
            
        except Exception as e:
            # logger.debug(f"Error extracting number from Yotpo text: {e}")
            return None
    
    def _extract_product_json_fallback(self) -> Optional[dict]:
        """
        Fallback method to extract ProductJson data directly from Shopify pages
        when structured data extraction fails.
        
        Returns:
            Product data dictionary or None if no data found
        """
        try:
            soup = BeautifulSoup(self.html_content, 'html.parser')
            all_product_data = []
            self.fallback_sources = []  # Track which sources were used
            
            # Method 1: Look for Shopify's ProductJson script tags (most reliable)
            product_json_scripts = soup.find_all('script', id=re.compile(r'ProductJson-.*'))
            for script in product_json_scripts:
                if script.string:
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and ('title' in data or 'variants' in data):
                            all_product_data.append(('ProductJson', data))
                            self.fallback_sources.append('ProductJson')
                            # logger.debug(f"Found ProductJson data with keys: {list(data.keys())}")
                    except json.JSONDecodeError as e:
                        # logger.debug(f"Failed to parse ProductJson script: {e}")
                        continue
            
            # Method 2: Look for other Shopify-specific script patterns
            shopify_scripts = soup.find_all('script', string=re.compile(r'window\.Shopify\s*=\s*'))
            for script in shopify_scripts:
                if script.string:
                    try:
                        # Extract the JSON part from window.Shopify = {...}
                        match = re.search(r'window\.Shopify\s*=\s*({.*?});', script.string, re.DOTALL)
                        if match:
                            data = json.loads(match.group(1))
                            if isinstance(data, dict) and ('product' in data or 'currentProduct' in data):
                                product_data = data.get('product') or data.get('currentProduct')
                                if product_data and isinstance(product_data, dict):
                                    all_product_data.append(('ShopifyWindow', product_data))
                                    self.fallback_sources.append('ShopifyWindow')
                                    # logger.debug(f"Found Shopify window data with keys: {list(product_data.keys())}")
                    except (json.JSONDecodeError, AttributeError) as e:
                        # logger.debug(f"Failed to parse Shopify window script: {e}")
                        continue
            
            # Method 3: Look for meta tags with product information
            meta_product_data = self._extract_product_data_from_meta_tags(soup)
            if meta_product_data:
                all_product_data.append(('MetaTags', meta_product_data))
                self.fallback_sources.append('MetaTags')
                # logger.debug(f"Found meta tag data with keys: {list(meta_product_data.keys())}")
            
            # Combine all found data
            if all_product_data:
                combined_data = self._combine_product_json_data(all_product_data)
                return combined_data
            
            return None
            
        except Exception as e:
            logger.warning(f"Error extracting ProductJson fallback data: {e}")
            return None
    
    def _extract_product_data_from_meta_tags(self, soup: BeautifulSoup) -> Optional[dict]:
        """
        Extract product data from meta tags as a fallback method.
        
        Args:
            soup: BeautifulSoup object of the HTML content
            
        Returns:
            Dictionary with product data or None
        """
        try:
            meta_data = {}
            
            # Extract title from meta tags
            title_meta = soup.find('meta', property='og:title') or soup.find('meta', attrs={'name': 'title'})
            if title_meta and title_meta.get('content'):
                meta_data['title'] = title_meta['content']
            
            # Extract description from meta tags
            desc_meta = soup.find('meta', property='og:description') or soup.find('meta', attrs={'name': 'description'})
            if desc_meta and desc_meta.get('content'):
                meta_data['description'] = desc_meta['content']
            
            # Extract price from meta tags
            price_meta = soup.find('meta', property='product:price:amount') or soup.find('meta', attrs={'name': 'price'})
            if price_meta and price_meta.get('content'):
                meta_data['price'] = price_meta['content']
            
            # Extract currency from meta tags
            currency_meta = soup.find('meta', property='product:price:currency') or soup.find('meta', attrs={'name': 'currency'})
            if currency_meta and currency_meta.get('content'):
                meta_data['currency'] = currency_meta['content']
            
            # Extract images from meta tags
            image_metas = soup.find_all('meta', property='og:image')
            images = []
            for img_meta in image_metas:
                if img_meta.get('content'):
                    images.append(img_meta['content'])
            if images:
                meta_data['images'] = images
            
            return meta_data if meta_data else None
            
        except Exception as e:
            # logger.debug(f"Error extracting meta tag data: {e}")
            return None
    
    def _combine_product_json_data(self, all_product_data: list) -> dict:
        """
        Combine product data from multiple sources with priority handling.
        
        Args:
            all_product_data: List of (source_name, data) tuples
            
        Returns:
            Combined product data dictionary
        """
        try:
            # Define source priority (higher number = higher priority)
            source_priority = {
                'ProductJson': 3,  # Highest priority
                'ShopifyWindow': 2,
                'MetaTags': 1,     # Lowest priority
            }
            
            # Sort by priority
            all_product_data.sort(key=lambda x: source_priority.get(x[0], 0), reverse=True)
            
            combined_data = {}
            
            for source_name, data in all_product_data:
                if not isinstance(data, dict):
                    continue
                
                # Merge data with priority (later sources don't override earlier ones)
                for key, value in data.items():
                    if key not in combined_data or combined_data[key] is None:
                        combined_data[key] = value
                    elif isinstance(combined_data[key], list) and isinstance(value, list):
                        # Merge lists and remove duplicates
                        merged_list = combined_data[key] + value
                        if key == 'images':
                            # For images (strings), use dict.fromkeys to remove duplicates
                            combined_data[key] = list(dict.fromkeys(merged_list))
                        else:
                            # For other lists (potentially containing dicts), use a different approach
                            seen = set()
                            unique_items = []
                            for item in merged_list:
                                if isinstance(item, dict):
                                    # Create a hashable representation of the dict
                                    item_key = tuple(sorted(item.items()))
                                    if item_key not in seen:
                                        seen.add(item_key)
                                        unique_items.append(item)
                                else:
                                    # For non-dict items, use the value itself
                                    if item not in seen:
                                        seen.add(item)
                                        unique_items.append(item)
                            combined_data[key] = unique_items
                    elif isinstance(combined_data[key], dict) and isinstance(value, dict):
                        # Merge dictionaries
                        combined_data[key].update(value)
            
            # Process and clean up the combined data
            if 'variants' in combined_data and isinstance(combined_data['variants'], list):
                # Ensure variants have required fields
                for variant in combined_data['variants']:
                    if isinstance(variant, dict):
                        # Extract price from variant if not in main data
                        if 'price' not in combined_data and variant.get('price'):
                            combined_data['price'] = variant['price']
                        # Extract currency from variant if not in main data
                        if 'currency' not in combined_data and variant.get('currency'):
                            combined_data['currency'] = variant['currency']
            
            logger.info(f"Combined product data from {len(all_product_data)} sources: {list(combined_data.keys())}")
            return combined_data
            
        except Exception as e:
            logger.warning(f"Error combining product JSON data: {e}")
            return {}
    
    def _extract_price_from_variant(self, variant: dict) -> Optional[str]:
        """Extract price from a variant object"""
        try:
            # Try different price fields in variant
            price = variant.get('price', '')
            if not price:
                price = variant.get('priceAmount', '')
            if not price:
                price = variant.get('value', '')
            
            if price:
                # Clean up price string
                if isinstance(price, str):
                    # Remove currency symbols and extra whitespace
                    price = re.sub(r'[^\d.,]', '', price)
                    # Replace comma with dot for decimal
                    price = price.replace(',', '.')
                return str(price)
            
            return None
            
        except Exception as e:
            # logger.debug(f"Error extracting price from variant: {e}")
            return None
    
    def _detect_yotpo(self) -> bool:
        """
        Detect if the page uses Yotpo reviews.
        
        Returns:
            True if Yotpo is detected, False otherwise
        """
        try:
            soup = BeautifulSoup(self.html_content, 'html.parser')
            
            # Method 1: Check for Yotpo script tags
            yotpo_scripts = soup.find_all('script', src=re.compile(r'yotpo\.com|yotpo'))
            if yotpo_scripts:
                # logger.debug("Yotpo detected via script tags")
                return True
            
            # Method 2: Check for Yotpo div elements with various class patterns
            yotpo_class_patterns = [
                r'yotpo',
                r'Yotpo',
                r'yotpo-bottom-line',
                r'yotpo-sr-bottom-line',
                r'yotpo-widget'
            ]
            
            for pattern in yotpo_class_patterns:
                yotpo_divs = soup.find_all('div', class_=re.compile(pattern, re.IGNORECASE))
                if yotpo_divs:
                    # logger.debug(f"Yotpo detected via div elements with pattern: {pattern}")
                    return True
            
            # Method 3: Check for Yotpo in script content
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and ('yotpo' in script.string.lower() or 'Yotpo' in script.string):
                    # logger.debug("Yotpo detected via script content")
                    return True
            
            # Method 4: Check for Yotpo data attributes
            yotpo_elements = soup.find_all(attrs={'data-yotpo': True})
            if yotpo_elements:
                # logger.debug("Yotpo detected via data attributes")
                return True
            
            # Method 5: Check for Yotpo in meta tags or other attributes
            yotpo_meta = soup.find_all(attrs={'data-yotpo-product-id': True})
            if yotpo_meta:
                # logger.debug("Yotpo detected via product ID attributes")
                return True
            
            return False
            
        except Exception as e:
            # logger.debug(f"Error detecting Yotpo: {e}")
            return False
    
    def _extract_yotpo_rating_data(self) -> Dict[str, Any]:
        """
        Extract rating and review data from Yotpo elements.
        Searches for various Yotpo class patterns and data structures.
        
        Returns:
            Dictionary with rating and review count data
        """
        try:
            soup = BeautifulSoup(self.html_content, 'html.parser')
            rating_data = {}
            
            # Extract rating from various Yotpo score classes
            rating_classes = [
                'yotpo-bottom-line-score',
                'yotpo-sr-bottom-line-score',
                'yotpo-score',
                'yotpo-rating-score',
                'yotpo-stars-score'
            ]
            
            for class_name in rating_classes:
                rating_elements = soup.find_all(class_=class_name)
                logger.info(f"Found {len(rating_elements)} rating elements with class '{class_name}'")
                for rating_element in rating_elements:
                    rating_text = rating_element.get_text().strip()
                    logger.info(f"Found rating element with text: '{rating_text}'")
                    try:
                        # Try to extract numeric rating from text
                        rating_match = re.search(r'(\d+(?:\.\d+)?)', rating_text)
                        if rating_match:
                            rating = float(rating_match.group(1))
                            rating_data['value'] = rating
                            logger.info(f"Found Yotpo rating: {rating}")
                            break
                    except (ValueError, TypeError):
                        logger.warning(f"Failed to parse rating text: '{rating_text}'")
                        continue
                if 'value' in rating_data:
                    break
            
            # Extract review count from various Yotpo text classes
            review_count_classes = [
                'yotpo-bottom-line-text',
                'yotpo-sr-bottom-line-text',
                'yotpo-review-count',
                'yotpo-reviews-count',
                'yotpo-text'
            ]
            
            for class_name in review_count_classes:
                review_elements = soup.find_all(class_=class_name)
                logger.info(f"Found {len(review_elements)} review elements with class '{class_name}'")
                for review_element in review_elements:
                    review_text = review_element.get_text().strip()
                    logger.info(f"Found review element with text: '{review_text}'")
                    review_count = self._extract_number_from_yotpo_text(review_text)
                    if review_count:
                        rating_data['review_count'] = review_count
                        logger.info(f"Found Yotpo review count: {review_count}")
                        break
                    else:
                        logger.warning(f"Failed to extract review count from text: '{review_text}'")
                if 'review_count' in rating_data:
                    break
            
            # Try to extract from data attributes if available
            if not rating_data:
                yotpo_data_elements = soup.find_all(attrs={'data-yotpo-product-id': True})
                for element in yotpo_data_elements:
                    # Check for rating in data attributes
                    rating_attr = element.get('data-yotpo-rating') or element.get('data-rating')
                    if rating_attr:
                        try:
                            rating = float(rating_attr)
                            rating_data['value'] = rating
                            logger.info(f"Found Yotpo rating from data attribute: {rating}")
                        except (ValueError, TypeError):
                            pass
                    
                    # Check for review count in data attributes
                    review_count_attr = element.get('data-yotpo-review-count') or element.get('data-review-count')
                    if review_count_attr:
                        try:
                            review_count = int(review_count_attr)
                            rating_data['review_count'] = review_count
                            logger.info(f"Found Yotpo review count from data attribute: {review_count}")
                        except (ValueError, TypeError):
                            pass
            
            # Log which components were found
            if rating_data:
                components_found = []
                if 'value' in rating_data:
                    components_found.append('rating')
                if 'review_count' in rating_data:
                    components_found.append('review_count')
                logger.info(f"Yotpo data extracted successfully: {components_found}")
            else:
                logger.warning("No Yotpo data extracted - no elements found or parsing failed")
            
            return rating_data
            
        except Exception as e:
            logger.warning(f"Error extracting Yotpo rating data: {e}")
            return {}
    
    def set_custom_rating_selectors(self, selectors: List[str]):
        """
        Set custom CSS selectors for rating extraction.
        
        Args:
            selectors: List of CSS selectors to use for rating extraction
        """
        if isinstance(selectors, list):
            self.custom_rating_selectors = selectors
            logger.info(f"Set custom rating selectors: {selectors}")
        else:
            logger.warning("Custom rating selectors must be a list")
    
    def set_custom_review_count_selectors(self, selectors: List[str]):
        """
        Set custom CSS selectors for review count extraction.
        
        Args:
            selectors: List of CSS selectors to use for review count extraction
        """
        if isinstance(selectors, list):
            self.custom_review_count_selectors = selectors
            logger.info(f"Set custom review count selectors: {selectors}")
        else:
            logger.warning("Custom review count selectors must be a list")
    
    def _detect_trustpilot(self) -> bool:
        """
        Detect if the page uses a Trustpilot widget.
        
        Returns:
            True if Trustpilot is detected, False otherwise
        """
        try:
            soup = BeautifulSoup(self.html_content, 'html.parser')
            
            # Method 1: Script or iframe references to Trustpilot domains
            tp_scripts = soup.find_all('script', src=re.compile(r'trustpilot\.com|tp\.widget', re.IGNORECASE))
            if tp_scripts:
                # logger.debug("Trustpilot detected via script tags")
                return True
                
            tp_iframes = soup.find_all('iframe', src=re.compile(r'trustpilot\.com|widget\.trustpilot\.com', re.IGNORECASE))
            if tp_iframes:
                # logger.debug("Trustpilot detected via iframe")
                return True
            
            # Method 2: Elements with Trustpilot-related class names
            tp_containers = soup.find_all(attrs={"class": re.compile(r'trustpilot|trustpilot-widget|tp-widget', re.IGNORECASE)})
            if tp_containers:
                # logger.debug("Trustpilot detected via widget class names")
                return True
            
            # Method 3: Check for Trustpilot mentions in script content
            all_scripts = soup.find_all('script')
            for script in all_scripts:
                if script.string and re.search(r'trustpilot|widget\.trustpilot\.com', script.string, re.IGNORECASE):
                    # logger.debug("Trustpilot detected via script content")
                    return True
            
            return False
        except Exception as e:
            # logger.debug(f"Error detecting Trustpilot: {e}")
            return False
    
    def _get_trustpilot_data(self) -> Optional[Dict[str, Any]]:
        """
        Get Trustpilot rating data, extracting it only once if needed.
        
        Returns:
            Trustpilot rating data dictionary or None if not available
        """
        if not self.trustpilot_detected:
            logger.info("Trustpilot not detected, returning None")
            return None
        
        if self.trustpilot_data is None:
            logger.info("Extracting Trustpilot data for the first time")
            self.trustpilot_data = self._extract_trustpilot_rating_data()
            if self.trustpilot_data:
                logger.info(f"Trustpilot data extracted and cached: {self.trustpilot_data}")
            else:
                logger.info("No Trustpilot data found")
        else:
            logger.info(f"Using cached Trustpilot data: {self.trustpilot_data}")
        
        return self.trustpilot_data
    
    def _extract_trustpilot_rating_data(self) -> Dict[str, Any]:
        """
        Extract Trustpilot data by finding trustpilot-widget div and fetching data from Trustpilot API.
        
        Returns:
            Dictionary with Trustpilot data and API URL
        """
        try:
            soup = BeautifulSoup(self.html_content, 'html.parser')
            rating_data: Dict[str, Any] = {}
            
            # Find div with class "trustpilot-widget" and required data attributes
            trustpilot_widget = soup.find('div', {
                'class': re.compile(r'trustpilot-widget', re.IGNORECASE),
                'data-template-id': True,
                'data-businessunit-id': True
            })
            
            if trustpilot_widget:
                # Extract required data attributes
                data_locale = trustpilot_widget.get('data-locale', 'en-US')
                data_template_id = trustpilot_widget.get('data-template-id')
                data_businessunit_id = trustpilot_widget.get('data-businessunit-id')
                data_stars = trustpilot_widget.get('data-stars', '')
                data_review_languages = trustpilot_widget.get('data-review-languages', 'en')
                
                # Construct the Trustpilot API URL
                api_url = f"https://widget.trustpilot.com/trustbox-data/{data_template_id}?businessUnitId={data_businessunit_id}&locale={data_locale}&reviewLanguages={data_review_languages}&reviewStars={data_stars}&reviewsPerPage=15"
                
                # Fetch data from Trustpilot API
                try:
                    response = requests.get(api_url, timeout=10)
                    response.raise_for_status()
                    
                    trustpilot_data = response.json()
                    
                    # Extract data from businessEntity
                    business_entity = trustpilot_data.get('businessEntity', {})
                    if business_entity:
                        number_of_reviews = business_entity.get('numberOfReviews', {})
                        
                        rating_data = {
                            'widget_found': True,
                            'api_url': api_url,
                            'value': business_entity.get('trustScore'),  # Main rating
                            'review_count': number_of_reviews.get('total'),
                            'stars': business_entity.get('stars'),
                            'display_name': business_entity.get('displayName'),
                            'website_url': business_entity.get('websiteUrl'),
                            'review_breakdown': {
                                'one_star': number_of_reviews.get('oneStar'),
                                'two_stars': number_of_reviews.get('twoStars'),
                                'three_stars': number_of_reviews.get('threeStars'),
                                'four_stars': number_of_reviews.get('fourStars'),
                                'five_stars': number_of_reviews.get('fiveStars')
                            },
                            'data_locale': data_locale,
                            'data_template_id': data_template_id,
                            'data_businessunit_id': data_businessunit_id,
                            'data_stars': data_stars,
                            'data_review_languages': data_review_languages,
                            'widget_attributes': dict(trustpilot_widget.attrs),
                            'raw_response': trustpilot_data
                        }
                        
                        return rating_data
                    else:
                        logger.warning("No businessEntity found in Trustpilot API response")
                        return {
                            'widget_found': True,
                            'api_url': api_url,
                            'error': 'No businessEntity in response',
                            'raw_response': trustpilot_data
                        }
                        
                except requests.RequestException as e:
                    logger.error(f"Failed to fetch Trustpilot API data: {e}")
                    return {
                        'widget_found': True,
                        'api_url': api_url,
                        'error': f'API request failed: {str(e)}',
                        'data_locale': data_locale,
                        'data_template_id': data_template_id,
                        'data_businessunit_id': data_businessunit_id,
                        'data_stars': data_stars,
                        'data_review_languages': data_review_languages,
                        'widget_attributes': dict(trustpilot_widget.attrs)
                    }
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse Trustpilot API response: {e}")
                    return {
                        'widget_found': True,
                        'api_url': api_url,
                        'error': f'JSON parse failed: {str(e)}',
                        'data_locale': data_locale,
                        'data_template_id': data_template_id,
                        'data_businessunit_id': data_businessunit_id,
                        'data_stars': data_stars,
                        'data_review_languages': data_review_languages,
                        'widget_attributes': dict(trustpilot_widget.attrs)
                    }
            else:
                return {'widget_found': False}
            
        except Exception as e:
            logger.warning(f"Error extracting Trustpilot widget data: {e}")
            return {'widget_found': False, 'error': str(e)}

    
    def extract_title(self) -> Optional[str]:
        """Extract product title from Shopify page"""
        if self.product_data and self.product_data.get('title'):
            return self.product_data['title']
        
        logger.warning("No Shopify title found")
        return None
    
    def extract_price(self) -> Optional[float]:
        """Extract product price from Shopify page"""
        if self.product_data:
            # First try to get price from the aggregated product data
            price = self.product_data.get('price', '')
            if price:
                try:
                    price_float = float(price)
                    return price_float
                except ValueError:
                    pass
            
            # Fallback to variants if no direct price
            variants = self.product_data.get('variants', [])
            if variants:
                # Try to find the first variant with a valid price
                for variant in variants:
                    if isinstance(variant, dict):
                        variant_price = variant.get('price', '')
                        if variant_price:
                            try:
                                price_float = float(variant_price)
                                return price_float
                            except ValueError:
                                continue
            
            # Also check hasVariant array for price information
            has_variants = self.product_data.get('hasVariant', [])
            if has_variants:
                for variant in has_variants:
                    variant_price = self._extract_price_from_variant(variant)
                    if variant_price:
                        try:
                            price_float = float(variant_price)
                            return price_float
                        except ValueError:
                            continue
        
        logger.warning("No Shopify price found")
        return None
    
    def extract_description(self) -> Optional[str]:
        """Extract product description from Shopify page"""
        if self.product_data and self.product_data.get('description'):
            return self.product_data['description']
        
        logger.warning("No Shopify description found")
        return None
    
    def extract_images(self) -> List[str]:
        """Extract product images from Shopify page using structured data and product JSON API"""
        images = []
        
        # Extract images from structured data (JSON-LD, ProductJson, etc.)
        # logger.debug(f"Product data keys: {list(self.product_data.keys()) if self.product_data else 'None'}")
        if self.product_data and self.product_data.get('images'):
            structured_images = self.product_data['images']
            # logger.debug(f"Structured images found: {structured_images}")
            # logger.debug(f"Structured images type: {type(structured_images)}")
            
            if isinstance(structured_images, list):
                # Filter out empty or invalid image URLs and normalize them
                valid_structured_images = []
                for img in structured_images:
                    # logger.debug(f"Processing image: {img} (type: {type(img)})")
                    if img and isinstance(img, str):
                        normalized_url = self._normalize_image_url(img)
                        if normalized_url:
                            valid_structured_images.append(normalized_url)
                            # logger.debug(f"Added normalized image: {normalized_url}")
                        else:
                            pass
                    else:
                        pass
                
                if valid_structured_images:
                    images.extend(valid_structured_images)
                    logger.info(f"Found {len(valid_structured_images)} images from structured data")
                else:
                    logger.warning("No valid images found in structured data after normalization")
            elif isinstance(structured_images, str):
                # Handle single image case
                if structured_images:
                    normalized_url = self._normalize_image_url(structured_images)
                    if normalized_url:
                        images.append(normalized_url)
                        logger.info("Found 1 image from structured data")
                    else:
                        logger.warning("Failed to normalize single image from structured data")
                else:
                    logger.warning("Empty string found in structured images")
            else:
                logger.warning(f"Unexpected structured images type: {type(structured_images)}")
        else:
            logger.warning("No images found in product data or product data is None")
        
        # Extract images from Shopify product JSON API
        # logger.debug("Attempting to extract images from Shopify product JSON API...")
        api_images = self._extract_images_from_product_api()
        if api_images:
            images.extend(api_images)
            logger.info(f"Found {len(api_images)} images from product JSON API")
        else:
            logger.warning("No images found from Shopify product JSON API")
        
        # Remove duplicates while preserving order
        # logger.debug(f"Total images collected before deduplication: {len(images)}")
        # logger.debug(f"Images array contents: {images}")
        
        if images:
            unique_images = list(dict.fromkeys(images))
            logger.info(f"Total unique images found: {len(unique_images)}")
            # logger.debug(f"Unique images: {unique_images}")
            return unique_images
        
        logger.warning("No images found from any source")
        return []
    
    def _normalize_image_url(self, image_url: str) -> str:
        """
        Normalize image URL to ensure it's absolute and properly formatted.
        Removes URL parameters (everything after "?") from the final URL.
        
        Args:
            image_url: Raw image URL from the page
            
        Returns:
            Normalized absolute image URL without parameters
        """
        # logger.debug(f"Normalizing image URL: {image_url}")
        
        if not image_url or not isinstance(image_url, str):
            # logger.debug(f"Invalid image URL: {image_url}")
            return ""
        
        # Handle protocol-relative URLs (starting with //)
        if image_url.startswith('//'):
            normalized = 'https:' + image_url
            # logger.debug(f"Protocol-relative URL normalized to: {normalized}")
        elif image_url.startswith('/'):
            # Handle relative URLs (starting with /)
            from urllib.parse import urlparse
            parsed_url = urlparse(self.url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            normalized = base_url + image_url
            # logger.debug(f"Relative URL normalized to: {normalized}")
        elif not image_url.startswith(('http://', 'https://')):
            # Handle relative URLs without leading slash
            from urllib.parse import urlparse, urljoin
            parsed_url = urlparse(self.url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            normalized = urljoin(base_url, image_url)
            # logger.debug(f"Relative URL without slash normalized to: {normalized}")
        else:
            # URL already absolute
            normalized = image_url
            # logger.debug(f"URL already absolute: {image_url}")
        
        # Remove URL parameters (everything after "?" or "%3F")
        if '?' in normalized:
            normalized = normalized.split('?')[0]
            # logger.debug(f"Removed parameters from URL: {normalized}")
        elif '%3F' in normalized:
            normalized = normalized.split('%3F')[0]
            # logger.debug(f"Removed URL-encoded parameters from URL: {normalized}")
        
        return normalized
    
    def _extract_images_from_product_api(self) -> List[str]:
        """Extract images from Shopify product JSON API"""
        try:
            # Extract product JSON URL from the main URL
            product_json_url = self._build_product_json_url()
            if not product_json_url:
                # logger.debug("No product JSON URL could be built")
                return []
            
            # logger.debug(f"Fetching images from Shopify API: {product_json_url}")
            
            # Fetch JSON data from the API endpoint
            response = requests.get(product_json_url, timeout=10)
            response.raise_for_status()
            
            product_data = response.json()
            
            # Extract images from the JSON structure
            images = []
            image_objects = product_data.get('product', {}).get('images', [])
            
            if isinstance(image_objects, list):
                # logger.debug(f"Found {len(image_objects)} image objects in product JSON API")
                for img_obj in image_objects:
                    if isinstance(img_obj, dict):
                        # Try multiple possible image URL fields
                        src = img_obj.get('src', '') or img_obj.get('url', '') or img_obj.get('image', '')
                        if src:
                            # Normalize the image URL
                            normalized_src = self._normalize_image_url(src)
                            if normalized_src:
                                images.append(normalized_src)
                                # logger.debug(f"Added normalized image URL: {normalized_src}")
                            else:
                                pass
                        else:
                            pass
            else:
                pass
            
            logger.info(f"Successfully extracted {len(images)} images from Shopify product JSON API")
            return images
            
        except requests.RequestException as e:
            logger.warning(f"Request failed when fetching Shopify product JSON API: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Shopify product JSON API response: {e}")
            return []
        except Exception as e:
            logger.warning(f"Unexpected error extracting images from Shopify product JSON API: {e}")
            return []
    
    def _build_product_json_url(self) -> Optional[str]:
        """Build Shopify product JSON API URL from the main product URL"""
        try:
            from urllib.parse import urlparse, urljoin
            
            parsed_url = urlparse(self.url)
            path = parsed_url.path
            
            # Handle various Shopify URL patterns
            # Pattern 1: /products/{product-handle}
            # Pattern 2: /collections/{collection}/products/{product-handle}
            # Pattern 3: /pages/{page}/products/{product-handle}
            # Pattern 4: /{locale}/products/{product-handle} (for international stores)
            # Pattern 5: /{country}/products/{product-handle} (for country-specific stores)
            # Pattern 6: /{language}-{country}/products/{product-handle} (for localized stores)
            
            # Use regex to find product handle more reliably
            import re
            product_pattern = r'/products/([^/?]+)'
            match = re.search(product_pattern, path)
            
            if match:
                product_handle = match.group(1)
                # Clean up the product handle - remove any trailing slashes or fragments
                product_handle = product_handle.rstrip('/')
                
                if product_handle:
                    # Build the JSON API URL
                    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                    json_url = f"{base_url}/products/{product_handle}.json"
                    
                    return json_url
            
            # Alternative approach: try to extract from the full path
            path_parts = [part for part in path.split('/') if part]
            
            # Look for 'products' in the path and get the next part
            try:
                products_index = path_parts.index('products')
                if products_index + 1 < len(path_parts):
                    product_handle = path_parts[products_index + 1]
                    # Clean up the product handle
                    product_handle = product_handle.split('?')[0].split('#')[0]
                    
                    if product_handle:
                        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                        json_url = f"{base_url}/products/{product_handle}.json"
                        
                        return json_url
            except ValueError:
                # 'products' not found in path
                pass
            
            # Third approach: try to find any URL that contains 'products' and extract the handle
            # This handles cases where the URL structure might be unusual
            if 'products' in path:
                # Find the position of 'products' in the path
                products_pos = path.find('/products/')
                if products_pos != -1:
                    # Extract everything after '/products/'
                    after_products = path[products_pos + 10:]  # 10 = len('/products/')
                    # Take the first part (before any additional slashes or query params)
                    product_handle = after_products.split('/')[0].split('?')[0].split('#')[0]
                    
                    if product_handle:
                        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                        json_url = f"{base_url}/products/{product_handle}.json"
                        
                        return json_url
            
            return None
            
        except Exception:
            return None
    
    def extract_currency(self) -> Optional[str]:
        """Extract currency from Shopify page"""
        if self.product_data and self.product_data.get('currency'):
            return self.product_data['currency']
        
        # Fallback to domain-based currency detection
        domain = parse_url_domain(self.url)
        return map_currency_symbol_to_code('', domain)
    
    def extract_rating(self) -> Optional[float]:
        """Extract product rating from Shopify page"""
        # First try structured data
        if self.product_data and self.product_data.get('rating'):
            rating_data = self.product_data['rating']
            if isinstance(rating_data, dict) and rating_data.get('value'):
                try:
                    return float(rating_data['value'])
                except (ValueError, TypeError):
                    pass
        
        # Fallback to Yotpo if structured data fails
        logger.info("Attempting Yotpo fallback for rating extraction")
        yotpo_data = self._get_yotpo_data()
        logger.info(f"Yotpo data for rating extraction: {yotpo_data}")
        if yotpo_data and yotpo_data.get('value'):
            try:
                rating = float(yotpo_data['value'])
                logger.info(f"Successfully extracted Yotpo rating: {rating}")
                return rating
            except (ValueError, TypeError):
                logger.warning(f"Failed to convert Yotpo rating to float: {yotpo_data['value']}")
                pass
        else:
            logger.info("No Yotpo rating data available")
        
        # Fallback to Trustpilot if Yotpo not available
        logger.info("Attempting Trustpilot fallback for rating extraction")
        trustpilot_data = self._get_trustpilot_data()
        logger.info(f"Trustpilot data for rating extraction: {trustpilot_data}")
        if trustpilot_data and trustpilot_data.get('value'):
            try:
                rating = float(trustpilot_data['value'])
                logger.info(f"Successfully extracted Trustpilot rating: {rating}")
                return rating
            except (ValueError, TypeError):
                logger.warning(f"Failed to convert Trustpilot rating to float: {trustpilot_data['value']}")
                pass
        else:
            logger.info("No Trustpilot rating data available")
        
        # Fallback to element-based extraction if all else fails
        logger.info("Attempting element-based rating fallback")
        rating = self._extract_rating_from_elements()
        if rating:
            logger.info(f"Successfully extracted rating {rating} using element-based fallback")
            return rating
        else:
            logger.warning("No rating found from any source")
        
        return None
    
    def extract_review_count(self) -> Optional[int]:
        """Extract review count from Shopify page"""
        # First try structured data
        if self.product_data and self.product_data.get('rating'):
            rating_data = self.product_data['rating']
            if isinstance(rating_data, dict) and rating_data.get('review_count'):
                try:
                    return int(rating_data['review_count'])
                except (ValueError, TypeError):
                    pass
        
        # Fallback to Yotpo if structured data fails
        logger.info("Attempting Yotpo fallback for review count extraction")
        yotpo_data = self._get_yotpo_data()
        logger.info(f"Yotpo data for review count extraction: {yotpo_data}")
        if yotpo_data and yotpo_data.get('review_count'):
            try:
                review_count = int(yotpo_data['review_count'])
                logger.info(f"Successfully extracted Yotpo review count: {review_count}")
                return review_count
            except (ValueError, TypeError):
                logger.warning(f"Failed to convert Yotpo review count to int: {yotpo_data['review_count']}")
                pass
        else:
            logger.info("No Yotpo review count data available")
        
        # Fallback to Trustpilot if Yotpo not available
        logger.info("Attempting Trustpilot fallback for review count extraction")
        trustpilot_data = self._get_trustpilot_data()
        logger.info(f"Trustpilot data for review count extraction: {trustpilot_data}")
        if trustpilot_data and trustpilot_data.get('review_count'):
            try:
                review_count = int(trustpilot_data['review_count'])
                logger.info(f"Successfully extracted Trustpilot review count: {review_count}")
                return review_count
            except (ValueError, TypeError):
                logger.warning(f"Failed to convert Trustpilot review count to int: {trustpilot_data['review_count']}")
                pass
        else:
            logger.info("No Trustpilot review count data available")
        
        # Fallback to element-based extraction if all else fails
        logger.info("Attempting element-based review count fallback")
        review_count = self._extract_review_count_from_elements()
        if review_count:
            logger.info(f"Successfully extracted review count {review_count} using element-based fallback")
            return review_count
        else:
            logger.warning("No review count found from any source")
        
        return None
    
    def extract_rating_details(self) -> Dict[str, Any]:
        """Extract detailed rating information from Shopify page"""
        # First try structured data
        if self.product_data and self.product_data.get('rating'):
            rating_data = self.product_data['rating']
            if isinstance(rating_data, dict):
                return {
                    'value': rating_data.get('value'),
                    'review_count': rating_data.get('review_count'),
                    'best_rating': rating_data.get('best_rating'),
                    'worst_rating': rating_data.get('worst_rating')
                }
        
        # Fallback to Yotpo if structured data fails
        yotpo_data = self._get_yotpo_data()
        if yotpo_data:
            return {
                'value': yotpo_data.get('value'),
                'review_count': yotpo_data.get('review_count'),
                'source': 'yotpo'
            }
        
        # Fallback to Trustpilot
        trustpilot_data = self._get_trustpilot_data()
        if trustpilot_data:
            return {
                'value': trustpilot_data.get('value'),
                'review_count': trustpilot_data.get('review_count'),
                'source': 'trustpilot'
            }
        
        # Final fallback to element-based extraction
        element_rating = self._extract_rating_from_elements()
        element_review_count = self._extract_review_count_from_elements()
        
        if element_rating or element_review_count:
            return {
                'value': element_rating,
                'review_count': element_review_count,
                'source': 'element_extraction'
            }
        
        return {}
    
    def extract_specifications(self) -> Dict[str, Any]:
        """Extract product specifications from Shopify page"""
        specs = {}
        
        if self.product_data:
            # Extract brand/vendor information
            if self.product_data.get('brand'):
                specs['brand'] = self.product_data['brand']
            
            if self.product_data.get('vendor'):
                specs['vendor'] = self.product_data['vendor']
            
            # Extract SKU
            if self.product_data.get('sku'):
                specs['sku'] = self.product_data['sku']
            
            # Extract availability
            if 'available' in self.product_data:
                specs['available'] = self.product_data['available']
            
            # Extract variants information and convert to frontend-friendly format
            # variants = self.product_data.get('variants', [])
            # if variants:
            #     specs['variants'] = self._convert_variants_to_key_value(variants)
        
        return specs
    
    def _convert_variants_to_key_value(self, variants: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Convert variants array to a frontend-friendly key-value structure.
        
        Args:
            variants: List of variant dictionaries
            
        Returns:
            Dictionary with variant information in key-value format
        """
        try:
            variant_info = {}
            
            if not variants:
                return variant_info
            
            # Extract common variant properties
            variant_info['total_variants'] = len(variants)
            
            # Extract available variants count
            available_variants = [v for v in variants if v.get('available', True)]
            variant_info['available_variants'] = len(available_variants)
            
            # Extract price range if multiple variants
            prices = []
            for variant in variants:
                if variant.get('price'):
                    try:
                        price = float(variant['price'])
                        prices.append(price)
                    except (ValueError, TypeError):
                        continue
            
            if prices:
                variant_info['price_range'] = {
                    'min': min(prices),
                    'max': max(prices),
                    'currency': variants[0].get('currency', 'USD')
                }
            
            # Extract option types (like Size, Color, etc.)
            option_types = set()
            for variant in variants:
                if variant.get('option1'):
                    option_types.add('option1')
                if variant.get('option2'):
                    option_types.add('option2')
                if variant.get('option3'):
                    option_types.add('option3')
            
            if option_types:
                variant_info['option_types'] = list(option_types)
            
            # Extract unique option values
            option_values = {}
            for option_type in option_types:
                values = set()
                for variant in variants:
                    option_value = variant.get(option_type)
                    if option_value:
                        values.add(str(option_value))
                if values:
                    option_values[option_type] = list(values)
            
            if option_values:
                variant_info['option_values'] = option_values
            
            # Extract variant IDs and titles for reference
            variant_details = []
            for variant in variants:
                variant_detail = {
                    'id': variant.get('id'),
                    'title': variant.get('title'),
                    'price': variant.get('price'),
                    'available': variant.get('available', True)
                }
                
                # Add option values
                for option_type in option_types:
                    option_value = variant.get(option_type)
                    if option_value:
                        variant_detail[option_type] = option_value
                
                variant_details.append(variant_detail)
            
            if variant_details:
                variant_info['variant_details'] = variant_details
            
            # Add raw variants count for reference
            variant_info['raw_variants_count'] = len(variants)
            
            return variant_info
            
        except Exception as e:
            logger.warning(f"Error converting variants to key-value format: {e}")
            # Fallback to simple count if conversion fails
            return {
                'total_variants': len(variants),
                'raw_variants_count': len(variants)
            }
    
    def extract_raw_data(self) -> Dict[str, Any]:
        """Extract raw data from Shopify page"""
        raw_data = {
            'platform': 'shopify',
            'url': self.url,
            'structured_json_found': bool(self.product_data),
            'extraction_method': self._get_extraction_method(),
            'yotpo_detected': self.yotpo_detected,
            'trustpilot_detected': self.trustpilot_detected
        }
        
        # Add fallback sources information if available
        if hasattr(self, 'fallback_sources') and self.fallback_sources:
            raw_data['fallback_sources'] = self.fallback_sources
        
        # Add Yotpo data if detected and used
        yotpo_data = self._get_yotpo_data()
        if yotpo_data:
            raw_data['yotpo_data'] = yotpo_data
        
        # Add Trustpilot data if detected and used
        trustpilot_data = self._get_trustpilot_data()
        if trustpilot_data:
            raw_data['trustpilot_data'] = trustpilot_data
        
        if self.product_data:
            raw_data.update({
                'product_data': self.product_data,
                'title': self.product_data.get('title'),
                'price': self.product_data.get('price'),
                'currency': self.product_data.get('currency'),
                'description': self.product_data.get('description'),
                'brand': self.product_data.get('brand'),
                'vendor': self.product_data.get('vendor'),
                'sku': self.product_data.get('sku'),
                'available': self.product_data.get('available'),
                'rating': self.product_data.get('rating', {})
            })
        else:
            raw_data['structured_json_found'] = False
        
        return raw_data
    
    def _get_extraction_method(self) -> str:
        """
        Determine which extraction method was used to get the product data.
        
        Returns:
            String describing the extraction method used
        """
        if not self.product_data:
            return 'none'
        
        # Check if this was extracted via structured data or fallback
        # We can determine this by checking if the structured data extractor was successful
        if hasattr(self, 'structured_data_extractor'):
            # If we have product data but the structured data extractor didn't find it initially,
            # it means we used the fallback method
            if self.product_data and not self.structured_data_extractor.extract_structured_product_data():
                # Include specific sources if available
                if hasattr(self, 'fallback_sources') and self.fallback_sources:
                    return f'product_json_fallback({",".join(self.fallback_sources)})'
                else:
                    return 'product_json_fallback'
            else:
                return 'structured_data'
        
        return 'unknown'
    
    def _extract_rating_from_elements(self) -> Optional[float]:
        """
        Fallback method to extract rating from DOM elements when structured data and
        third-party widgets (Yotpo, Trustpilot) fail.
        
        Returns:
            Rating value as float or None if not found
        """
        try:
            soup = BeautifulSoup(self.html_content, 'html.parser')
            rating = None
            
            # Combine default and custom selectors
            selectors_to_try = self.custom_rating_selectors + [
                # Star rating patterns
                '[class*="rating"]',
                '[class*="stars"]',
                '[class*="score"]',
                '[class*="review"]',
                # Data attributes
                '[data-rating]',
                '[data-score]',
                '[data-review-rating]',
                # ARIA labels
                '[aria-label*="rating"]',
                '[aria-label*="stars"]',
                # Common rating classes
                '.rating',
                '.stars',
                '.score',
                '.review-rating',
                '.product-rating'
            ]
            
            for selector in selectors_to_try:
                elements = soup.select(selector)
                for element in elements:
                    # Try to extract rating from text content
                    text = element.get_text().strip()
                    if text:
                        # Look for patterns like "4.5", "4.5/5", "4.5 out of 5", etc.
                        rating_patterns = [
                            r'(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)',  # 4.5/5
                            r'(\d+(?:\.\d+)?)\s*out\s*of\s*(\d+(?:\.\d+)?)',  # 4.5 out of 5
                            r'(\d+(?:\.\d+)?)\s*stars?',  # 4.5 stars
                            r'(\d+(?:\.\d+)?)',  # Just 4.5
                        ]
                        
                        for pattern in rating_patterns:
                            match = re.search(pattern, text, re.IGNORECASE)
                            if match:
                                try:
                                    rating_value = float(match.group(1))
                                    # If it's a ratio (like 4.5/5), normalize to 5-star scale
                                    if len(match.groups()) > 1 and match.group(2):
                                        max_rating = float(match.group(2))
                                        if max_rating != 5.0:
                                            rating_value = (rating_value / max_rating) * 5.0
                                    
                                    # Validate rating is in reasonable range
                                    if 0.0 <= rating_value <= 5.0:
                                        rating = rating_value
                                        logger.info(f"Found rating {rating} from element with selector '{selector}'")
                                        break
                                except (ValueError, TypeError):
                                    continue
                    
                    # Try to extract from data attributes
                    if not rating:
                        data_rating = element.get('data-rating') or element.get('data-score')
                        if data_rating:
                            try:
                                rating_value = float(data_rating)
                                if 0.0 <= rating_value <= 5.0:
                                    rating = rating_value
                                    logger.info(f"Found rating {rating} from data attribute in element with selector '{selector}'")
                                    break
                            except (ValueError, TypeError):
                                continue
                
                if rating:
                    break
            
            if rating:
                logger.info(f"Successfully extracted rating {rating} using element-based fallback")
            else:
                pass
            
            return rating
            
        except Exception as e:
            logger.warning(f"Error in element-based rating extraction: {e}")
            return None
    
    def _extract_review_count_from_elements(self) -> Optional[int]:
        """
        Fallback method to extract review count from DOM elements when structured data and
        third-party widgets (Yotpo, Trustpilot) fail.
        
        Returns:
            Review count as integer or None if not found
        """
        try:
            soup = BeautifulSoup(self.html_content, 'html.parser')
            review_count = None
            
            # Combine default and custom selectors
            selectors_to_try = self.custom_review_count_selectors + [
                # Review count patterns
                '[class*="review"]',
                '[class*="reviews"]',
                '[class*="count"]',
                '[class*="total"]',
                # Data attributes
                '[data-review-count]',
                '[data-count]',
                '[data-total]',
                # Common review classes
                '.review-count',
                '.reviews-count',
                '.total-reviews',
                '.review-total'
            ]
            
            for selector in selectors_to_try:
                elements = soup.select(selector)
                for element in elements:
                    # Try to extract review count from text content
                    text = element.get_text().strip()
                    if text:
                        # Look for patterns like "123 reviews", "123", "(123)", etc.
                        count_patterns = [
                            r'(\d+(?:,\d+)*)\s*reviews?',  # 123 reviews
                            r'(\d+(?:,\d+)*)\s*ratings?',  # 123 ratings
                            r'(\d+(?:,\d+)*)',  # Just 123
                            r'\((\d+(?:,\d+)*)\)',  # (123)
                        ]
                        
                        for pattern in count_patterns:
                            match = re.search(pattern, text, re.IGNORECASE)
                            if match:
                                try:
                                    count_str = match.group(1).replace(',', '')
                                    count_value = int(count_str)
                                    if count_value > 0:
                                        review_count = count_value
                                        logger.info(f"Found review count {review_count} from element with selector '{selector}'")
                                        break
                                except (ValueError, TypeError):
                                    continue
                    
                    # Try to extract from data attributes
                    if not review_count:
                        data_count = element.get('data-review-count') or element.get('data-count')
                        if data_count:
                            try:
                                count_value = int(data_count)
                                if count_value > 0:
                                    review_count = count_value
                                    logger.info(f"Found review count {review_count} from data attribute in element with selector '{selector}'")
                                    break
                            except (ValueError, TypeError):
                                continue
                
                if review_count:
                    break
            
            if review_count:
                logger.info(f"Successfully extracted review count {review_count} using element-based fallback")
            else:
                pass
            
            return review_count
            
        except Exception as e:
            logger.warning(f"Error in element-based review count extraction: {e}")
            return None 