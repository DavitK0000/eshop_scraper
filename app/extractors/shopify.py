from typing import Optional, List, Dict, Any
import re
import json
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
        else:
            logger.warning("No structured JSON data found for Shopify product, trying ProductJson fallback")
            # Fallback to direct ProductJson extraction
            self.product_data = self._extract_product_json_fallback()
            if self.product_data:
                logger.info("Successfully extracted Shopify product data from ProductJson fallback")
            else:
                logger.warning("No ProductJson data found for Shopify product")
    
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
                            logger.debug(f"Found ProductJson data with keys: {list(data.keys())}")
                    except json.JSONDecodeError as e:
                        logger.debug(f"Failed to parse ProductJson script: {e}")
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
                                    logger.debug(f"Found Shopify window data with keys: {list(product_data.keys())}")
                    except (json.JSONDecodeError, AttributeError) as e:
                        logger.debug(f"Failed to parse Shopify window script: {e}")
                        continue
            
            # Method 3: Look for meta tags with product information
            meta_product_data = self._extract_product_data_from_meta_tags(soup)
            if meta_product_data:
                all_product_data.append(('MetaTags', meta_product_data))
                self.fallback_sources.append('MetaTags')
                logger.debug(f"Found meta tag data with keys: {list(meta_product_data.keys())}")
            
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
            logger.debug(f"Error extracting meta tag data: {e}")
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
                        combined_data[key] = list(dict.fromkeys(combined_data[key] + value))
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
        """Extract product images from Shopify page"""
        if self.product_data:
            json_images = self.product_data.get('images', [])
            if json_images:
                # The structured data utility now handles enhanced image extraction
                # including folder pattern matching, deduplication, and filtering
                logger.info(f"Shopify: Found {len(json_images)} images from enhanced structured data extraction")
                return json_images
        
        logger.warning("No Shopify images found")
        return []
    
    def extract_currency(self) -> Optional[str]:
        """Extract currency from Shopify page"""
        if self.product_data and self.product_data.get('currency'):
            return self.product_data['currency']
        
        # Fallback to domain-based currency detection
        domain = parse_url_domain(self.url)
        return map_currency_symbol_to_code('', domain)
    
    def extract_rating(self) -> Optional[float]:
        """Extract product rating from Shopify page"""
        if self.product_data and self.product_data.get('rating'):
            rating_data = self.product_data['rating']
            if isinstance(rating_data, dict) and rating_data.get('value'):
                try:
                    return float(rating_data['value'])
                except (ValueError, TypeError):
                    pass
        
        logger.warning("No Shopify rating found")
        return None
    
    def extract_review_count(self) -> Optional[int]:
        """Extract review count from Shopify page"""
        if self.product_data and self.product_data.get('rating'):
            rating_data = self.product_data['rating']
            if isinstance(rating_data, dict) and rating_data.get('review_count'):
                try:
                    return int(rating_data['review_count'])
                except (ValueError, TypeError):
                    pass
        
        logger.warning("No Shopify review count found")
        return None
    
    def extract_rating_details(self) -> Dict[str, Any]:
        """Extract detailed rating information from Shopify page"""
        if self.product_data and self.product_data.get('rating'):
            rating_data = self.product_data['rating']
            if isinstance(rating_data, dict):
                return {
                    'value': rating_data.get('value'),
                    'review_count': rating_data.get('review_count'),
                    'best_rating': rating_data.get('best_rating'),
                    'worst_rating': rating_data.get('worst_rating')
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
            'extraction_method': self._get_extraction_method()
        }
        
        # Add fallback sources information if available
        if hasattr(self, 'fallback_sources') and self.fallback_sources:
            raw_data['fallback_sources'] = self.fallback_sources
        
        if self.product_data:
            raw_data.update({
                'product_data': self.product_data,
                'title': self.product_data.get('title'),
                'price': self.product_data.get('price'),
                'currency': self.product_data.get('currency'),
                'description': self.product_data.get('description'),
                'images': self.product_data.get('images', []),
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
            logger.debug(f"Error extracting price from variant: {e}")
            return None 