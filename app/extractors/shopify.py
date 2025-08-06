from typing import Optional, List, Dict, Any
import re
import json
from app.extractors.base import BaseExtractor
from app.utils import map_currency_symbol_to_code, parse_url_domain, parse_price_with_regional_format, extract_number_from_text, sanitize_text
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
        
        # Extract all product data from structured JSON in init
        self.product_data = self._extract_structured_product_json()
        if self.product_data:
            logger.info("Successfully extracted Shopify product data from structured JSON")
        else:
            logger.warning("No structured JSON data found for Shopify product")
    
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
        images = []
        
        if self.product_data:
            json_images = self.product_data.get('images', [])
            for image in json_images:
                if isinstance(image, dict):
                    # Image is an object with src property
                    src = image.get('src', '')
                    if src:
                        # Convert to full URL if it's relative
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            src = f"https://{parse_url_domain(self.url)}{src}"
                        images.append(src)
                elif isinstance(image, str):
                    # Image is a direct URL string
                    if image.startswith('//'):
                        image = 'https:' + image
                    elif image.startswith('/'):
                        image = f"https://{parse_url_domain(self.url)}{image}"
                    images.append(image)
        
        return images
    
    def extract_currency(self) -> Optional[str]:
        """Extract currency from Shopify page"""
        if self.product_data:
            # First try to get currency from the aggregated product data
            currency = self.product_data.get('currency', '')
            if currency:
                return currency
            
            # Fallback to variants if no direct currency
            variants = self.product_data.get('variants', [])
            if variants:
                # Try to find the first variant with a valid currency
                for variant in variants:
                    if isinstance(variant, dict):
                        variant_currency = variant.get('currency', '')
                        if variant_currency:
                            return variant_currency
        
        logger.warning("No Shopify currency found")
        return None
    
    def extract_rating(self) -> Optional[float]:
        """Extract product rating from Shopify page"""
        if self.product_data:
            rating_data = self.product_data.get('rating', {})
            
            if isinstance(rating_data, dict):
                # Try different possible rating field names
                rating_value = (
                    rating_data.get('value') or 
                    rating_data.get('ratingValue') or 
                    rating_data.get('rating') or
                    rating_data.get('averageRating') or
                    rating_data.get('score')
                )
                if rating_value:
                    try:
                        rating_float = float(rating_value)
                        return rating_float
                    except ValueError:
                        pass
            elif isinstance(rating_data, (int, float)):
                # Rating might be a direct number
                try:
                    rating_float = float(rating_data)
                    return rating_float
                except ValueError:
                    pass
        
        logger.warning("No Shopify rating found")
        return None
    
    def extract_review_count(self) -> Optional[int]:
        """Extract review count from Shopify page"""
        if self.product_data:
            rating_data = self.product_data.get('rating', {})
            
            if isinstance(rating_data, dict):
                # Try different possible review count field names
                review_count = (
                    rating_data.get('review_count') or 
                    rating_data.get('reviewCount') or 
                    rating_data.get('count') or
                    rating_data.get('numberOfReviews') or
                    rating_data.get('totalReviews') or
                    rating_data.get('reviews_count')
                )
                if review_count:
                    try:
                        count_int = int(review_count)
                        return count_int
                    except ValueError:
                        pass
        
        logger.warning("No Shopify review count found")
        return None
    
    def extract_specifications(self) -> Dict[str, Any]:
        """Extract product specifications from Shopify page"""
        specs = {}
        
        if self.product_data:
            # Extract vendor/brand
            vendor = self.product_data.get('vendor', '')
            if vendor:
                specs['vendor'] = vendor
            
            # Extract brand (separate from vendor)
            brand = self.product_data.get('brand', '')
            if brand:
                specs['brand'] = brand
            
            # Extract product type
            product_type = self.product_data.get('product_type', '')
            if product_type:
                specs['product_type'] = product_type
            
            # Extract tags
            tags = self.product_data.get('tags', [])
            if tags:
                specs['tags'] = tags
            
            # Extract SKU (from product level or variants)
            sku = self.product_data.get('sku', '')
            if not sku:
                variants = self.product_data.get('variants', [])
                if variants:
                    first_variant = variants[0]
                    sku = first_variant.get('sku', '')
            if sku:
                specs['sku'] = sku
            
            # Extract MPN and GTIN if available
            mpn = self.product_data.get('mpn', '')
            if mpn:
                specs['mpn'] = mpn
            
            gtin = self.product_data.get('gtin', '')
            if gtin:
                specs['gtin'] = gtin
            
            # Extract variant options
            options = self.product_data.get('options', [])
            for i, option in enumerate(options):
                option_name = option.get('name', f'Option {i+1}')
                option_values = option.get('values', [])
                if option_values:
                    specs[f'option_{i+1}_{option_name.lower()}'] = option_values
            
            # Extract availability
            available = self.product_data.get('available')
            if available is not None:
                specs['available'] = available
        
        return specs
    
    def extract_raw_data(self) -> Dict[str, Any]:
        """Extract raw data for debugging"""
        raw_data = super().extract_raw_data()
        raw_data['platform'] = 'shopify'
        
        # Add Shopify-specific data
        if self.product_data:
            raw_data['structured_json_found'] = True
            raw_data['product_json'] = {
                'title': self.product_data.get('title'),
                'vendor': self.product_data.get('vendor'),
                'brand': self.product_data.get('brand'),
                'variants_count': len(self.product_data.get('variants', [])),
                'images_count': len(self.product_data.get('images', [])),
                'options_count': len(self.product_data.get('options', [])),
                'tags_count': len(self.product_data.get('tags', [])),
                'sku': self.product_data.get('sku'),
                'mpn': self.product_data.get('mpn'),
                'gtin': self.product_data.get('gtin'),
                'available': self.product_data.get('available')
            }
        else:
            raw_data['structured_json_found'] = False
        
        return raw_data
    

    
    def _extract_structured_product_json(self) -> Optional[dict]:
        """Extract product JSON data from Shopify's structured data sources using all available methods"""
        try:
            all_product_data = []
            
            # Method 1: Look for Shopify's ProductJson script tags (most reliable)
            product_json_scripts = self.soup.find_all('script', id=re.compile(r'ProductJson-.*'))
            for script in product_json_scripts:
                if script.string:
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and ('title' in data or 'variants' in data):
                            all_product_data.append(('ProductJson', data))
                    except json.JSONDecodeError:
                        continue
            
            # Method 2: Look for data-product-json attribute
            product_json_element = self.soup.select_one('[data-product-json]')
            if product_json_element:
                json_data = product_json_element.get('data-product-json', '')
                if json_data:
                    try:
                        data = json.loads(json_data)
                        all_product_data.append(('data-product-json', data))
                    except json.JSONDecodeError:
                        pass
            
            # Method 3: Look for JSON-LD structured data (application/ld+json)
            json_ld_scripts = self.soup.find_all('script', type='application/ld+json')
            for script in json_ld_scripts:
                if script.string:
                    try:
                        data = json.loads(script.string)
                        # Handle both single objects and arrays of objects
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and item.get('@type') in ['Product', 'ProductGroup']:
                                    converted_data = self._convert_json_ld_to_product_data(item)
                                    all_product_data.append(('JSON-LD', converted_data))
                        elif isinstance(data, dict) and data.get('@type') in ['Product', 'ProductGroup']:
                            converted_data = self._convert_json_ld_to_product_data(data)
                            all_product_data.append(('JSON-LD', converted_data))
                    except json.JSONDecodeError:
                        continue
            
            # Method 4: Look for window.Shopify.product data in script tags
            script_tags = self.soup.find_all('script')
            shopify_scripts = [s for s in script_tags if s.string and 'window.Shopify' in s.string]
            
            for script in shopify_scripts:
                # Try to extract product data using regex
                patterns = [
                    r'window\.Shopify\.product\s*=\s*({[^}]+})',
                    r'Shopify\.product\s*=\s*({[^}]+})',
                    r'product\s*:\s*({[^}]+})',
                    r'"product":\s*({[^}]+})'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, script.string, re.DOTALL)
                    if match:
                        try:
                            json_str = match.group(1)
                            # Clean up the JSON string
                            json_str = re.sub(r'(\w+):', r'"\1":', json_str)
                            data = json.loads(json_str)
                            all_product_data.append(('window.Shopify.product', data))
                        except json.JSONDecodeError:
                            continue
            
            # Method 5: Look for script tags with application/json type
            json_scripts = self.soup.find_all('script', type='application/json')
            for script in json_scripts:
                if script.string:
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and 'product' in data:
                            all_product_data.append(('application/json', data['product']))
                        elif isinstance(data, dict) and ('title' in data or 'variants' in data):
                            all_product_data.append(('application/json', data))
                    except json.JSONDecodeError:
                        continue
            
            # Combine all found data
            if all_product_data:
                combined_data = self._combine_product_data(all_product_data)
                return combined_data
            
            return None
            
        except Exception as e:
            logger.warning(f"Error extracting structured product JSON: {e}")
            return None
    
    def _combine_product_data(self, all_product_data: list) -> dict:
        """Aggregate product data from multiple sources, intelligently combining information from all sources"""
        if not all_product_data:
            return {}
        
        # Priority order for data sources (higher index = higher priority)
        priority_order = {
            'ProductJson': 5,  # Most reliable Shopify source
            'data-product-json': 4,
            'window.Shopify.product': 3,
            'application/json': 2,
            'JSON-LD': 1,
            'generic_script': 0
        }
        
        # Sort by priority
        sorted_data = sorted(all_product_data, key=lambda x: priority_order.get(x[0], -1))
        
        # Initialize combined data structure
        combined_data = {
            'title': '',
            'description': '',
            'vendor': '',
            'brand': '',
            'price': '',
            'currency': '',
            'images': [],
            'variants': [],
            'options': [],
            'tags': [],
            'rating': {},
            'sku': '',
            'product_type': '',
            'available': True
        }
        
        # Track all unique values for aggregation
        all_titles = set()
        all_descriptions = set()
        all_vendors = set()
        all_brands = set()
        all_images = set()
        all_tags = set()
        all_skus = set()
        all_product_types = set()
        all_variants = []
        all_options = []
        all_ratings = []
        
        # Collect data from all sources
        for source_name, data in sorted_data:
            if not isinstance(data, dict):
                continue
                

            
            # Collect basic text fields
            if data.get('title'):
                all_titles.add(data['title'])
            if data.get('name'):
                all_titles.add(data['name'])
            if data.get('description'):
                all_descriptions.add(data['description'])
            if data.get('vendor'):
                all_vendors.add(data['vendor'])
            if data.get('brand'):
                all_brands.add(data['brand'])
            if data.get('sku'):
                all_skus.add(data['sku'])
            if data.get('product_type'):
                all_product_types.add(data['product_type'])
            
            # Collect images
            images = data.get('images', [])
            if isinstance(images, list):
                for img in images:
                    if isinstance(img, dict):
                        src = img.get('src', '')
                    elif isinstance(img, str):
                        src = img
                    else:
                        continue
                    
                    if src:
                        # Convert to full URL if it's relative
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            src = f"https://{parse_url_domain(self.url)}{src}"
                        all_images.add(src)
            
            # Collect tags
            tags = data.get('tags', [])
            if isinstance(tags, list):
                all_tags.update(tags)
            
            # Collect variants
            variants = data.get('variants', [])
            if isinstance(variants, list):
                all_variants.extend(variants)
            
            # Collect options
            options = data.get('options', [])
            if isinstance(options, list):
                all_options.extend(options)
            
            # Collect rating information
            rating = data.get('rating', {})
            if isinstance(rating, dict) and rating:
                all_ratings.append(rating)
            elif isinstance(rating, (int, float)):
                # Rating might be a direct number
                all_ratings.append({'value': str(rating)})
            
            # Also check for alternative rating field names
            for rating_field in ['aggregateRating', 'reviews', 'reviewData']:
                alt_rating = data.get(rating_field, {})
                if isinstance(alt_rating, dict) and alt_rating:
                    all_ratings.append(alt_rating)
        
        # Aggregate the collected data
        # Title: Use the longest/most complete title
        if all_titles:
            combined_data['title'] = max(all_titles, key=len)
        
        # Description: Use the longest/most complete description
        if all_descriptions:
            combined_data['description'] = max(all_descriptions, key=len)
        
        # Vendor: Use the first non-empty vendor
        if all_vendors:
            combined_data['vendor'] = next(iter(all_vendors))
        
        # Brand: Use the first non-empty brand
        if all_brands:
            combined_data['brand'] = next(iter(all_brands))
        
        # Images: Combine all unique images
        combined_data['images'] = list(all_images)
        
        # Tags: Combine all unique tags
        combined_data['tags'] = list(all_tags)
        
        # SKU: Use the first non-empty SKU
        if all_skus:
            combined_data['sku'] = next(iter(all_skus))
        
        # Product type: Use the first non-empty product type
        if all_product_types:
            combined_data['product_type'] = next(iter(all_product_types))
        
        # Variants: Deduplicate variants based on key properties
        if all_variants:
            unique_variants = self._deduplicate_variants(all_variants)
            combined_data['variants'] = unique_variants
        
        # Options: Deduplicate options based on name
        if all_options:
            unique_options = self._deduplicate_options(all_options)
            combined_data['options'] = unique_options
        
        # Rating: Use the most complete rating data
        if all_ratings:
            merged_rating = self._merge_rating_data(all_ratings)
            combined_data['rating'] = merged_rating
        
        # Price and currency: Extract from variants and other sources
        all_prices = []
        all_currencies = set()
        
        # Collect prices and currencies from all sources
        for source_name, data in sorted_data:
            if not isinstance(data, dict):
                continue
            
            # Direct price/currency fields
            if data.get('price'):
                all_prices.append(data['price'])
            if data.get('currency'):
                all_currencies.add(data['currency'])
            
            # Extract from variants
            variants = data.get('variants', [])
            if isinstance(variants, list):
                for variant in variants:
                    if isinstance(variant, dict):
                        variant_price = variant.get('price', '')
                        if variant_price:
                            all_prices.append(variant_price)
                        
                        variant_currency = variant.get('currency', '')
                        if variant_currency:
                            all_currencies.add(variant_currency)
        
        # Use the best price representation
        if all_prices:
            # Try to convert to float and find the best price
            valid_prices = []
            for price in all_prices:
                try:
                    # Handle different price formats
                    if isinstance(price, str):
                        # Remove currency symbols and clean up
                        cleaned_price = re.sub(r'[^\d.,]', '', price)
                        # Handle different decimal separators
                        if ',' in cleaned_price and '.' in cleaned_price:
                            # European format: 1.234,56 -> 1234.56
                            cleaned_price = cleaned_price.replace('.', '').replace(',', '.')
                        elif ',' in cleaned_price:
                            # US format with comma: 1,234.56 -> 1234.56
                            cleaned_price = cleaned_price.replace(',', '')
                        
                        price_float = float(cleaned_price)
                        valid_prices.append((price_float, price))
                    else:
                        price_float = float(price)
                        valid_prices.append((price_float, str(price)))
                except (ValueError, TypeError):
                    continue
            
            if valid_prices:
                # Use the lowest price as the base price (usually the most accurate)
                lowest_price = min(valid_prices, key=lambda x: x[0])
                combined_data['price'] = lowest_price[1]
        
        # Use the first currency found
        if all_currencies:
            combined_data['currency'] = next(iter(all_currencies))
        
        # Clean up empty fields, but preserve rating data even if empty
        cleaned_data = {}
        for k, v in combined_data.items():
            if k == 'rating':
                # Always preserve rating data structure
                cleaned_data[k] = v
            elif v:  # Only include non-empty values for other fields
                cleaned_data[k] = v
        
        combined_data = cleaned_data
        
        return combined_data
    
    def _convert_json_ld_to_product_data(self, json_ld_data: dict) -> dict:
        """Convert JSON-LD structured data to product data format"""
        product_data = {}
        
        # Basic product information
        product_data['title'] = json_ld_data.get('name', '')
        product_data['description'] = json_ld_data.get('description', '')
        
        # Brand information
        brand = json_ld_data.get('brand', {})
        if isinstance(brand, dict):
            product_data['brand'] = brand.get('name', '')
        elif isinstance(brand, str):
            product_data['brand'] = brand
        
        # Vendor information (sometimes same as brand)
        vendor = json_ld_data.get('vendor', '')
        if vendor:
            product_data['vendor'] = vendor
        
        # Extract price and currency from offers
        offers = json_ld_data.get('offers', {})
        if isinstance(offers, list) and offers:
            # Use the first offer as primary
            primary_offer = offers[0]
            if isinstance(primary_offer, dict):
                price = primary_offer.get('price', '')
                if price:
                    product_data['price'] = str(price)
                
                currency = primary_offer.get('priceCurrency', '')
                if currency:
                    product_data['currency'] = currency
                
                # Extract availability
                availability = primary_offer.get('availability', '')
                if availability:
                    product_data['available'] = 'InStock' in availability
                
                # Extract SKU
                sku = primary_offer.get('sku', '')
                if sku:
                    product_data['sku'] = sku
        elif isinstance(offers, dict):
            price = offers.get('price', '')
            if price:
                product_data['price'] = str(price)
            
            currency = offers.get('priceCurrency', '')
            if currency:
                product_data['currency'] = currency
            
            # Extract availability
            availability = offers.get('availability', '')
            if availability:
                product_data['available'] = 'InStock' in availability
            
            # Extract SKU
            sku = offers.get('sku', '')
            if sku:
                product_data['sku'] = sku
        
        # Extract images
        images = json_ld_data.get('image', [])
        if isinstance(images, str):
            images = [images]
        elif isinstance(images, list):
            # Handle both string URLs and image objects
            processed_images = []
            for img in images:
                if isinstance(img, str):
                    processed_images.append(img)
                elif isinstance(img, dict):
                    # Image object with url property
                    img_url = img.get('url', '') or img.get('src', '')
                    if img_url:
                        processed_images.append(img_url)
            images = processed_images
        product_data['images'] = images
        
        # Extract rating information from various possible locations
        rating_data = {}
        
        # Check aggregateRating (most common in JSON-LD)
        aggregate_rating = json_ld_data.get('aggregateRating', {})
        if isinstance(aggregate_rating, dict):
            rating_value = aggregate_rating.get('ratingValue', '')
            review_count = aggregate_rating.get('reviewCount', '')
            if rating_value:
                rating_data['value'] = rating_value
            if review_count:
                rating_data['review_count'] = review_count
        
        # Check for direct rating fields
        if not rating_data.get('value'):
            direct_rating = json_ld_data.get('rating', '')
            if direct_rating:
                rating_data['value'] = direct_rating
        
        # Check for review count in other fields
        if not rating_data.get('review_count'):
            review_count = json_ld_data.get('reviewCount', '') or json_ld_data.get('numberOfReviews', '')
            if review_count:
                rating_data['review_count'] = review_count
        
        # Add rating data if we found any
        if rating_data:
            product_data['rating'] = rating_data
        
        # Extract product type/category
        category = json_ld_data.get('category', '')
        if category:
            product_data['product_type'] = category
        
        # Extract MPN (Manufacturer Part Number)
        mpn = json_ld_data.get('mpn', '')
        if mpn:
            product_data['mpn'] = mpn
        
        # Extract GTIN (Global Trade Item Number)
        gtin = json_ld_data.get('gtin', '')
        if gtin:
            product_data['gtin'] = gtin
        
        return product_data
    
    def _deduplicate_variants(self, variants: list) -> list:
        """Deduplicate variants based on key properties like id, sku, or title"""
        if not variants:
            return []
        
        seen = set()
        unique_variants = []
        
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            
            # Create a unique key based on variant properties
            variant_key = None
            if variant.get('id'):
                variant_key = f"id_{variant['id']}"
            elif variant.get('sku'):
                variant_key = f"sku_{variant['sku']}"
            elif variant.get('title'):
                variant_key = f"title_{variant['title']}"
            else:
                # If no unique identifier, use the entire variant as key
                variant_key = str(sorted(variant.items()))
            
            if variant_key not in seen:
                seen.add(variant_key)
                unique_variants.append(variant)
        
        return unique_variants
    
    def _deduplicate_options(self, options: list) -> list:
        """Deduplicate options based on name"""
        if not options:
            return []
        
        seen_names = set()
        unique_options = []
        
        for option in options:
            if not isinstance(option, dict):
                continue
            
            option_name = option.get('name', '')
            if option_name and option_name not in seen_names:
                seen_names.add(option_name)
                unique_options.append(option)
        
        return unique_options
    
    def _merge_rating_data(self, ratings: list) -> dict:
        """Merge rating data from multiple sources, preferring the most complete"""
        if not ratings:
            return {}
        
        # Find the rating with the most complete information
        best_rating = max(ratings, key=lambda r: len(r) if isinstance(r, dict) else 0)
        
        # If we have multiple ratings, try to combine review counts
        total_review_count = 0
        best_rating_value = None
        
        for rating in ratings:
            if isinstance(rating, dict):
                # Try to find review count from various field names
                review_count = (
                    rating.get('review_count') or 
                    rating.get('reviewCount') or 
                    rating.get('count') or
                    rating.get('numberOfReviews') or
                    rating.get('totalReviews') or
                    rating.get('reviews_count')
                )
                if review_count:
                    try:
                        total_review_count += int(review_count)
                    except (ValueError, TypeError):
                        pass
                
                # Try to find rating value from various field names
                rating_value = (
                    rating.get('value') or 
                    rating.get('ratingValue') or 
                    rating.get('rating') or
                    rating.get('averageRating') or
                    rating.get('score')
                )
                if rating_value and not best_rating_value:
                    try:
                        best_rating_value = float(rating_value)
                    except (ValueError, TypeError):
                        pass
        
        # Create a standardized rating structure
        merged_rating = {}
        
        # Add rating value
        if best_rating_value:
            merged_rating['value'] = str(best_rating_value)
        elif best_rating.get('value'):
            merged_rating['value'] = best_rating['value']
        elif best_rating.get('ratingValue'):
            merged_rating['value'] = best_rating['ratingValue']
        
        # Add review count
        if total_review_count > 0:
            merged_rating['review_count'] = total_review_count
        elif best_rating.get('review_count'):
            merged_rating['review_count'] = best_rating['review_count']
        elif best_rating.get('reviewCount'):
            merged_rating['review_count'] = best_rating['reviewCount']
        elif best_rating.get('count'):
            merged_rating['review_count'] = best_rating['count']
        
        return merged_rating 