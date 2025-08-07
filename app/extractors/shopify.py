from typing import Optional, List, Dict, Any
import re
import json
from urllib.parse import urlparse
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
        
        # Filter to keep only the largest size variant for each unique image
        if images:
            images = self._get_largest_image_variants(images)
        
        # Final filter: Remove images with width < 1024px
        if images:
            original_count = len(images)
            images = self._filter_images_by_minimum_width(images, min_width=1024)
            if len(images) < original_count:
                logger.info(f"Final width filtering: {original_count} images -> {len(images)} images (min width: 1024px)")
        
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
            
            # Also check hasVariant array for currency information
            has_variants = self.product_data.get('hasVariant', [])
            if has_variants:
                for variant in has_variants:
                    variant_currency = self._extract_currency_from_variant(variant)
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
    
    def extract_rating_details(self) -> Dict[str, Any]:
        """Extract detailed rating information including best/worst ratings"""
        if self.product_data:
            rating_data = self.product_data.get('rating', {})
            
            if isinstance(rating_data, dict):
                details = {}
                
                # Extract rating value
                rating_value = rating_data.get('value')
                if rating_value:
                    try:
                        details['rating_value'] = float(rating_value)
                    except ValueError:
                        pass
                
                # Extract review count
                review_count = rating_data.get('review_count')
                if review_count:
                    try:
                        details['review_count'] = int(review_count)
                    except ValueError:
                        pass
                
                # Extract best rating (usually 5 for 5-star systems)
                best_rating = rating_data.get('best_rating')
                if best_rating:
                    try:
                        details['best_rating'] = float(best_rating)
                    except ValueError:
                        pass
                
                # Extract worst rating (usually 1 for 5-star systems)
                worst_rating = rating_data.get('worst_rating')
                if worst_rating:
                    try:
                        details['worst_rating'] = float(worst_rating)
                    except ValueError:
                        pass
                
                return details
        
        return {}
    
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
                'available': self.product_data.get('available'),
                'rating': self.product_data.get('rating', {})
            }
        else:
            raw_data['structured_json_found'] = False
        
        return raw_data
    

    
    def _extract_structured_product_json(self) -> Optional[dict]:
        """Extract product JSON data from Shopify's structured data sources using ProductJson and JSON-LD methods only"""
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
            
            # Method 2: Look for JSON-LD structured data (application/ld+json)
            json_ld_scripts = self.soup.find_all('script', type='application/ld+json')
            for script in json_ld_scripts:
                if script.string:
                    try:
                        data = json.loads(script.string)
                        # Process the JSON-LD data (handles @graph, arrays, and single objects)
                        processed_data = self._process_json_ld_data(data)
                        all_product_data.extend(processed_data)
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
    
    def _process_json_ld_data(self, data: Any) -> List[tuple]:
        """
        Process JSON-LD data and extract product information.
        Handles @graph arrays, regular arrays, and single objects.
        
        Args:
            data: JSON-LD data (dict, list, or other)
            
        Returns:
            List of (source_name, data) tuples
        """
        processed_data = []
        
        try:
            if isinstance(data, dict):
                # Check if this is a @graph container
                if '@graph' in data and isinstance(data['@graph'], list):
                    # Process @graph array
                    logger.debug("Found @graph array in JSON-LD data")
                    for item in data['@graph']:
                        if isinstance(item, dict):
                            item_data = self._extract_data_from_json_ld_item(item)
                            if item_data:
                                processed_data.extend(item_data)
                else:
                    # Single object
                    item_data = self._extract_data_from_json_ld_item(data)
                    if item_data:
                        processed_data.extend(item_data)
            
            elif isinstance(data, list):
                # Array of objects
                logger.debug("Found array in JSON-LD data")
                for item in data:
                    if isinstance(item, dict):
                        item_data = self._extract_data_from_json_ld_item(item)
                        if item_data:
                            processed_data.extend(item_data)
            
            return processed_data
            
        except Exception as e:
            logger.debug(f"Error processing JSON-LD data: {e}")
            return []
    
    def _extract_data_from_json_ld_item(self, item: dict) -> List[tuple]:
        """
        Extract product data from a single JSON-LD item.
        
        Args:
            item: Single JSON-LD object
            
        Returns:
            List of (source_name, data) tuples
        """
        extracted_data = []
        
        try:
            item_type = item.get('@type', '')
            
            # Extract product information from Product or ProductGroup types
            if item_type in ['Product', 'ProductGroup']:
                converted_data = self._convert_json_ld_to_product_data(item)
                extracted_data.append(('JSON-LD', converted_data))
            
            # Extract rating information from AggregateRating or Rating types
            elif item_type in ['AggregateRating', 'Rating']:
                rating_data = self._extract_json_ld_rating_data(item)
                if rating_data:
                    # Create a product entry with just rating data
                    new_product = {'rating': rating_data}
                    extracted_data.append(('JSON-LD', new_product))
            
            return extracted_data
            
        except Exception as e:
            logger.debug(f"Error extracting data from JSON-LD item: {e}")
            return []
    
    def _combine_product_data(self, all_product_data: list) -> dict:
        """Aggregate product data from multiple sources, intelligently combining information from all sources"""
        if not all_product_data:
            return {}
        
        # Priority order for data sources (higher index = higher priority)
        priority_order = {
            'ProductJson': 2,  # Most reliable Shopify source
            'JSON-LD': 1,      # Structured data
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
        
        # Images: Combine all unique images and filter to largest size variants
        if all_images:
            combined_data['images'] = self._get_largest_image_variants(list(all_images))
        else:
            combined_data['images'] = []
        
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
            
            # Extract from hasVariant array
            has_variants = data.get('hasVariant', [])
            if isinstance(has_variants, list):
                for variant in has_variants:
                    variant_price = self._extract_price_from_variant(variant)
                    if variant_price:
                        all_prices.append(variant_price)
                    
                    variant_currency = self._extract_currency_from_variant(variant)
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
                price = self._extract_price_from_offer(primary_offer)
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
            price = self._extract_price_from_offer(offers)
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
        
        # If no price found in offers, check hasVariant array for price information
        if not product_data.get('price'):
            has_variants = json_ld_data.get('hasVariant', [])
            if isinstance(has_variants, list):
                for variant in has_variants:
                    price = self._extract_price_from_variant(variant)
                    if price:
                        product_data['price'] = price
                        # Also extract currency from variant if not already found
                        if not product_data.get('currency'):
                            currency = self._extract_currency_from_variant(variant)
                            if currency:
                                product_data['currency'] = currency
                        break
        
        # Extract images
        images = json_ld_data.get('image', [])
        if isinstance(images, str):
            images = [images]
        elif isinstance(images, dict):
            # Handle single ImageObject (not array)
            processed_images = []
            img_url = images.get('url', '') or images.get('src', '') or images.get('image', '')
            if img_url:
                processed_images.append(img_url)
            images = processed_images
        elif isinstance(images, list):
            # Handle array of images (both strings and objects)
            processed_images = []
            for img in images:
                if isinstance(img, str):
                    processed_images.append(img)
                elif isinstance(img, dict):
                    # Image object with url property
                    img_url = img.get('url', '') or img.get('src', '') or img.get('image', '')
                    if img_url:
                        processed_images.append(img_url)
            images = processed_images
        
        # Enhanced image extraction: Use JSON-LD images as clues to find additional images
        enhanced_images = self._enhance_images_from_json_ld_clues(images)
        product_data['images'] = enhanced_images
        
        # Extract rating information from various possible locations
        rating_data = {}
        
        # Check aggregateRating (most common in JSON-LD)
        aggregate_rating = json_ld_data.get('aggregateRating', {})
        if isinstance(aggregate_rating, dict):
            rating_value = aggregate_rating.get('ratingValue', '')
            review_count = aggregate_rating.get('reviewCount', '')
            best_rating = aggregate_rating.get('bestRating', '')
            worst_rating = aggregate_rating.get('worstRating', '')
            
            if rating_value:
                rating_data['value'] = str(rating_value)
            if review_count:
                rating_data['review_count'] = str(review_count)
            if best_rating:
                rating_data['best_rating'] = str(best_rating)
            if worst_rating:
                rating_data['worst_rating'] = str(worst_rating)
        
        # Check for direct rating fields
        if not rating_data.get('value'):
            direct_rating = json_ld_data.get('rating', '')
            if direct_rating:
                rating_data['value'] = str(direct_rating)
        
        # Check for review count in other fields
        if not rating_data.get('review_count'):
            review_count = json_ld_data.get('reviewCount', '') or json_ld_data.get('numberOfReviews', '')
            if review_count:
                rating_data['review_count'] = str(review_count)
        
        # Check for alternative rating field names
        if not rating_data.get('value'):
            for field in ['score', 'averageRating', 'average']:
                rating_value = json_ld_data.get(field, '')
                if rating_value:
                    rating_data['value'] = str(rating_value)
                    break
        
        # Check for alternative review count field names
        if not rating_data.get('review_count'):
            for field in ['count', 'totalReviews', 'reviews_count']:
                review_count = json_ld_data.get(field, '')
                if review_count:
                    rating_data['review_count'] = str(review_count)
                    break
        
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
    
    def _extract_price_from_offer(self, offer: dict) -> Optional[str]:
        """
        Extract price from an offer object, handling various price formats.
        
        Args:
            offer: Offer object from JSON-LD structured data
            
        Returns:
            Price string if found, None otherwise
        """
        try:
            # First try direct price field
            price = offer.get('price', '')
            if price:
                return str(price)
            
            # Check for highPrice and lowPrice (AggregateOffer format)
            high_price = offer.get('highPrice', '')
            low_price = offer.get('lowPrice', '')
            
            if high_price and low_price:
                # If both high and low prices exist, use the low price (usually the base price)
                return str(low_price)
            elif low_price:
                # If only low price exists, use it
                return str(low_price)
            elif high_price:
                # If only high price exists, use it
                return str(high_price)
            
            # Check for alternative price field names
            for price_field in ['amount', 'value', 'cost', 'priceAmount']:
                price = offer.get(price_field, '')
                if price:
                    return str(price)
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting price from offer: {e}")
            return None
    
    def _extract_json_ld_rating_data(self, json_ld_data: dict) -> Optional[dict]:
        """Extract rating data from JSON-LD structured data with @type AggregateRating or Rating"""
        rating_data = {}
        
        # Handle AggregateRating type
        if json_ld_data.get('@type') == 'AggregateRating':
            # Extract rating value
            rating_value = json_ld_data.get('ratingValue', '')
            if rating_value:
                rating_data['value'] = str(rating_value)
            
            # Extract review count
            review_count = json_ld_data.get('reviewCount', '')
            if review_count:
                rating_data['review_count'] = str(review_count)
            
            # Extract best rating (usually 5 for 5-star systems)
            best_rating = json_ld_data.get('bestRating', '')
            if best_rating:
                rating_data['best_rating'] = str(best_rating)
            
            # Extract worst rating (usually 1 for 5-star systems)
            worst_rating = json_ld_data.get('worstRating', '')
            if worst_rating:
                rating_data['worst_rating'] = str(worst_rating)
        
        # Handle Rating type
        elif json_ld_data.get('@type') == 'Rating':
            # Extract rating value
            rating_value = json_ld_data.get('ratingValue', '')
            if rating_value:
                rating_data['value'] = str(rating_value)
            
            # Extract best rating
            best_rating = json_ld_data.get('bestRating', '')
            if best_rating:
                rating_data['best_rating'] = str(best_rating)
            
            # Extract worst rating
            worst_rating = json_ld_data.get('worstRating', '')
            if worst_rating:
                rating_data['worst_rating'] = str(worst_rating)
            
            # Extract review count if available
            review_count = json_ld_data.get('reviewCount', '')
            if review_count:
                rating_data['review_count'] = str(review_count)
        
        # Also check for alternative field names that might be used
        if not rating_data.get('value'):
            # Try alternative rating field names
            for field in ['rating', 'score', 'averageRating', 'average']:
                rating_value = json_ld_data.get(field, '')
                if rating_value:
                    rating_data['value'] = str(rating_value)
                    break
        
        if not rating_data.get('review_count'):
            # Try alternative review count field names
            for field in ['count', 'numberOfReviews', 'totalReviews', 'reviews_count']:
                review_count = json_ld_data.get(field, '')
                if review_count:
                    rating_data['review_count'] = str(review_count)
                    break
        
        return rating_data if rating_data else None
    
    def _extract_price_from_variant(self, variant: dict) -> Optional[str]:
        """Extract price from a variant object (handles both direct price and offers)"""
        if not isinstance(variant, dict):
            return None
        
        # Check direct price field in variant
        direct_price = variant.get('price', '')
        if direct_price:
            return str(direct_price)
        
        # Check variant offers
        variant_offers = variant.get('offers', {})
        if isinstance(variant_offers, list) and variant_offers:
            variant_offer = variant_offers[0]
            if isinstance(variant_offer, dict):
                price = variant_offer.get('price', '')
                if price:
                    return str(price)
        elif isinstance(variant_offers, dict):
            price = variant_offers.get('price', '')
            if price:
                return str(price)
        
        return None
    
    def _extract_currency_from_variant(self, variant: dict) -> Optional[str]:
        """Extract currency from a variant object (handles both direct currency and offers)"""
        if not isinstance(variant, dict):
            return None
        
        # Check direct currency field in variant
        direct_currency = variant.get('currency', '')
        if direct_currency:
            return direct_currency
        
        # Check variant offers
        variant_offers = variant.get('offers', {})
        if isinstance(variant_offers, list) and variant_offers:
            variant_offer = variant_offers[0]
            if isinstance(variant_offer, dict):
                currency = variant_offer.get('priceCurrency', '')
                if currency:
                    return currency
        elif isinstance(variant_offers, dict):
            currency = variant_offers.get('priceCurrency', '')
            if currency:
                return currency
        
        return None
    
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
        
        # Add best rating and worst rating if available
        best_rating_value = best_rating.get('best_rating') or best_rating.get('bestRating')
        if best_rating_value:
            merged_rating['best_rating'] = str(best_rating_value)
        
        worst_rating_value = best_rating.get('worst_rating') or best_rating.get('worstRating')
        if worst_rating_value:
            merged_rating['worst_rating'] = str(worst_rating_value)
        
        return merged_rating 
    
    def _enhance_images_from_json_ld_clues(self, json_ld_images: List[str]) -> List[str]:
        """
        Enhance image extraction by using JSON-LD image URLs as clues to find additional images
        from img tags that share the same top-level folder path.
        
        Args:
            json_ld_images: List of image URLs extracted from JSON-LD structured data
            
        Returns:
            Enhanced list of image URLs including both JSON-LD images and related img tag images
        """
        if not json_ld_images:
            return []
        
        enhanced_images = list(json_ld_images)  # Start with JSON-LD images
        found_folder_patterns = set()
        
        # Extract folder patterns from JSON-LD images
        for image_url in json_ld_images:
            if not image_url:
                continue
            
            # Parse the URL to extract the top-level folder
            folder_pattern = self._extract_top_level_folder_from_url(image_url)
            if folder_pattern:
                found_folder_patterns.add(folder_pattern)
                # Log the type of pattern found
                if self._is_image_subdomain(folder_pattern):
                    logger.debug(f"Found image subdomain pattern: {folder_pattern}")
                else:
                    logger.debug(f"Found folder pattern from JSON-LD image: {folder_pattern}")
        
        # If we found folder patterns, search for additional images in img tags
        if found_folder_patterns:
            additional_images = self._find_images_by_folder_patterns(found_folder_patterns)
            if additional_images:
                logger.info(f"Enhanced image extraction: Found {len(additional_images)} additional images using folder patterns")
                enhanced_images.extend(additional_images)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_images = []
        for img in enhanced_images:
            if img and img not in seen:
                seen.add(img)
                unique_images.append(img)
        
        if len(unique_images) > len(json_ld_images):
            logger.info(f"Image extraction enhanced: {len(json_ld_images)} JSON-LD images + {len(unique_images) - len(json_ld_images)} additional images = {len(unique_images)} total")
        
        # Deduplicate images with same base URL path (different parameters)
        deduplicated_images = self._deduplicate_images_by_base_url(unique_images)
        
        if len(deduplicated_images) < len(unique_images):
            dedup_count = len(unique_images) - len(deduplicated_images)
            logger.info(f"Image deduplication: {len(unique_images)} images -> {len(deduplicated_images)} images (removed {dedup_count} duplicates)")
        
        # Filter images by minimum width (1024px)
        filtered_images = self._filter_images_by_minimum_width(deduplicated_images, min_width=1024)
        
        if len(filtered_images) < len(unique_images):
            filtered_count = len(unique_images) - len(filtered_images)
            logger.info(f"Image filtering: {len(unique_images)} images -> {len(filtered_images)} images (filtered out {filtered_count} images)")
        
        return filtered_images
    
    def _filter_images_by_minimum_width(self, images: List[str], min_width: int = 1024) -> List[str]:
        """
        Filter images to only include those with width >= min_width and exclude SVG images.
        
        Args:
            images: List of image URLs to filter
            min_width: Minimum width in pixels (default: 1024)
            
        Returns:
            Filtered list of image URLs that meet the minimum width requirement and are not SVG
        """
        if not images:
            return []
        
        filtered_images = []
        
        for image_url in images:
            if not image_url:
                continue
            
            # Skip SVG images (icons, logos, graphics)
            if self._is_svg_image(image_url):
                logger.debug(f"Filtered out SVG image: {image_url}")
                continue
            
            # Check if image meets minimum width requirement
            if self._check_image_width(image_url, min_width):
                filtered_images.append(image_url)
            else:
                logger.debug(f"Filtered out image (width < {min_width}px): {image_url}")
        
        return filtered_images
    
    def _is_svg_image(self, image_url: str) -> bool:
        """
        Check if an image URL is an SVG file.
        
        Args:
            image_url: Image URL to check
            
        Returns:
            True if the image is SVG, False otherwise
        """
        if not image_url:
            return False
        
        # Check for SVG file extensions
        svg_extensions = ['.svg', '.svgz']
        lower_url = image_url.lower()
        
        # Check file extension
        for ext in svg_extensions:
            if ext in lower_url:
                return True
        
        # Check for SVG in URL path or query parameters
        if 'svg' in lower_url:
            # Additional checks to avoid false positives
            # Skip if it's part of a larger word or path
            if any(pattern in lower_url for pattern in ['/svg/', 'svg/', '.svg', 'svg=']):
                return True
        
        return False
    
    def _deduplicate_images_by_base_url(self, images: List[str]) -> List[str]:
        """
        Deduplicate images by grouping them by base URL path and keeping the highest resolution version.
        
        Args:
            images: List of image URLs to deduplicate
            
        Returns:
            Deduplicated list of image URLs (highest resolution for each base URL)
        """
        if not images:
            return []
        
        # Group images by base URL (without parameters)
        image_groups = {}
        
        for image_url in images:
            if not image_url:
                continue
            
            # Get base URL without parameters
            base_url = self._get_base_url_without_params(image_url)
            
            if base_url not in image_groups:
                image_groups[base_url] = []
            image_groups[base_url].append(image_url)
        
        # For each group, select the best image (highest resolution)
        deduplicated_images = []
        
        for base_url, url_list in image_groups.items():
            if len(url_list) == 1:
                # Only one URL for this base, keep it
                deduplicated_images.append(url_list[0])
            else:
                # Multiple URLs, select the best one
                best_url = self._select_best_image_from_group(url_list)
                deduplicated_images.append(best_url)
                logger.debug(f"Deduplicated {len(url_list)} images for base URL: {base_url} -> {best_url}")
        
        return deduplicated_images
    
    def _select_best_image_from_group(self, url_list: List[str]) -> str:
        """
        Select the best image from a group of URLs with the same base path.
        Prioritizes highest resolution and best quality.
        
        Args:
            url_list: List of image URLs with the same base path
            
        Returns:
            Best image URL from the group
        """
        if not url_list:
            return ""
        
        if len(url_list) == 1:
            return url_list[0]
        
        # Score each URL based on various factors
        scored_urls = []
        
        for url in url_list:
            score = 0
            
            # Extract width and height from URL parameters
            width = self._extract_width_from_url(url)
            height = self._extract_height_from_url(url)
            
            if width and height:
                # Calculate total pixels (resolution)
                pixels = width * height
                score += pixels
            
            # Bonus for specific high-resolution indicators
            if width:
                if width >= 2400:
                    score += 1000
                elif width >= 2000:
                    score += 800
                elif width >= 1600:
                    score += 600
                elif width >= 1200:
                    score += 400
            
            # Bonus for quality parameters
            if 'quality=100' in url.lower() or 'q=100' in url.lower():
                score += 500
            elif 'quality=90' in url.lower() or 'q=90' in url.lower():
                score += 300
            elif 'quality=80' in url.lower() or 'q=80' in url.lower():
                score += 100
            
            # Bonus for specific size indicators in URL
            if any(size in url.lower() for size in ['2400', '2000', '1600', '1200']):
                score += 200
            
            # Penalty for small sizes
            if width and width < 800:
                score -= 1000
            
            scored_urls.append((url, score))
        
        # Sort by score (highest first) and return the best
        scored_urls.sort(key=lambda x: x[1], reverse=True)
        return scored_urls[0][0]
    
    def _extract_height_from_url(self, image_url: str) -> Optional[int]:
        """
        Extract height from URL parameters (e.g., ?h=1024, &height=1200).
        
        Args:
            image_url: Image URL to extract height from
            
        Returns:
            Height in pixels if found, None otherwise
        """
        try:
            parsed = urlparse(image_url)
            query_params = parsed.query
            
            # Common height parameters
            height_params = ['h', 'height', 'y']
            
            for param in height_params:
                if f'{param}=' in query_params:
                    # Extract the value after the parameter
                    pattern = rf'{param}=(\d+)'
                    match = re.search(pattern, query_params)
                    if match:
                        return int(match.group(1))
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting height from URL {image_url}: {e}")
            return None
    
    def _check_image_width(self, image_url: str, min_width: int) -> bool:
        """
        Check if an image URL meets the minimum width requirement.
        
        Args:
            image_url: Image URL to check
            min_width: Minimum width in pixels
            
        Returns:
            True if image width >= min_width, False otherwise
        """
        try:
            # Try to extract width from URL parameters first (common in CDN URLs)
            width_from_url = self._extract_width_from_url(image_url)
            if width_from_url and width_from_url >= min_width:
                return True
            
            # Try to extract width from img tag attributes
            width_from_tag = self._extract_width_from_img_tag(image_url)
            if width_from_tag and width_from_tag >= min_width:
                return True
            
            # Check if this image came from a srcset (should already be filtered for high resolution)
            if 'w=' in image_url and any(width_str in image_url for width_str in ['1200', '1600', '2000', '2600', '3500']):
                # This looks like a high-resolution image from srcset
                return True
            
            # For Shopify URLs, try to get the largest size variant
            if 'shopify.com' in image_url:
                large_variant = self._get_shopify_large_image_variant(image_url)
                if large_variant:
                    # Check if the large variant URL indicates it's a large image
                    if any(size in large_variant.lower() for size in ['large', 'master', '2048', '1600', '1200']):
                        return True
            
            # If we can't determine width, assume it's acceptable (don't filter out)
            # This prevents accidentally removing valid images we can't measure
            return True
            
        except Exception as e:
            logger.debug(f"Error checking image width for {image_url}: {e}")
            # If we can't check, assume it's acceptable
            return True
    
    def _extract_width_from_url(self, image_url: str) -> Optional[int]:
        """
        Extract width from URL parameters (e.g., ?w=1024, &width=1200).
        
        Args:
            image_url: Image URL to extract width from
            
        Returns:
            Width in pixels if found, None otherwise
        """
        try:
            parsed = urlparse(image_url)
            query_params = parsed.query
            
            # Common width parameters
            width_params = ['w', 'width', 'size', 'dimension']
            
            for param in width_params:
                if f'{param}=' in query_params:
                    # Extract the value after the parameter
                    pattern = rf'{param}=(\d+)'
                    match = re.search(pattern, query_params)
                    if match:
                        return int(match.group(1))
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting width from URL {image_url}: {e}")
            return None
    
    def _extract_width_from_img_tag(self, image_url: str) -> Optional[int]:
        """
        Extract width from img tag attributes in the HTML.
        Also checks srcset for width information.
        
        Args:
            image_url: Image URL to find corresponding img tag for
            
        Returns:
            Width in pixels if found in img tag, None otherwise
        """
        try:
            # Find img tag with matching src or srcset
            img_tags = self.soup.find_all('img')
            
            for img_tag in img_tags:
                # Check src attribute
                src = img_tag.get('src', '')
                if src:
                    src = self._normalize_image_url(src)
                    # Check if this img tag corresponds to our image URL
                    if src == image_url or self._urls_match(src, image_url):
                        return self._extract_width_from_img_tag_attributes(img_tag)
                
                # Check srcset attribute
                srcset = img_tag.get('srcset', '')
                if srcset:
                    # Parse srcset and find matching URL
                    srcset_items = self._parse_srcset(srcset)
                    for url, width in srcset_items:
                        normalized_url = self._normalize_image_url(url)
                        if normalized_url == image_url or self._urls_match(normalized_url, image_url):
                            if width > 0:
                                return width
                            else:
                                # If no width in srcset, check tag attributes
                                return self._extract_width_from_img_tag_attributes(img_tag)
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting width from img tag for {image_url}: {e}")
            return None
    
    def _extract_width_from_img_tag_attributes(self, img_tag) -> Optional[int]:
        """
        Extract width from img tag attributes (width attribute and style).
        
        Args:
            img_tag: BeautifulSoup img tag element
            
        Returns:
            Width in pixels if found, None otherwise
        """
        try:
            # Extract width from img tag attributes
            width_attr = img_tag.get('width', '')
            if width_attr:
                try:
                    return int(width_attr)
                except ValueError:
                    pass
            
            # Also check style attribute for width
            style_attr = img_tag.get('style', '')
            if style_attr:
                width_match = re.search(r'width:\s*(\d+)px', style_attr)
                if width_match:
                    return int(width_match.group(1))
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting width from img tag attributes: {e}")
            return None
    
    def _get_shopify_large_image_variant(self, image_url: str) -> Optional[str]:
        """
        Get the large size variant of a Shopify image URL.
        
        Args:
            image_url: Original Shopify image URL
            
        Returns:
            Large size variant URL if possible, None otherwise
        """
        try:
            # Shopify image URL patterns
            # Original: https://cdn.shopify.com/s/files/1/1234/5678/products/image.jpg
            # Large: https://cdn.shopify.com/s/files/1/1234/5678/products/image.jpg?width=2048
            
            if 'shopify.com' in image_url and 'products' in image_url:
                # Add width parameter for large size
                separator = '&' if '?' in image_url else '?'
                return f"{image_url}{separator}width=2048"
            
            return None
            
        except Exception as e:
            logger.debug(f"Error getting Shopify large image variant for {image_url}: {e}")
            return None
    
    def _urls_match(self, url1: str, url2: str) -> bool:
        """
        Check if two URLs match (ignoring query parameters and fragments).
        
        Args:
            url1: First URL
            url2: Second URL
            
        Returns:
            True if URLs match (ignoring query params), False otherwise
        """
        try:
            parsed1 = urlparse(url1)
            parsed2 = urlparse(url2)
            
            # Compare scheme, netloc, and path
            return (parsed1.scheme == parsed2.scheme and 
                   parsed1.netloc == parsed2.netloc and 
                   parsed1.path == parsed2.path)
            
        except Exception:
            return False 
    
    def _extract_top_level_folder_from_url(self, url: str) -> Optional[str]:
        """
        Extract the top-level folder pattern from an image URL.
        
        Examples:
        - "https://cdn.shopify.com/s/files/1/1234/5678/products/image.jpg" -> "cdn.shopify.com/s/files/1/1234/5678/products"
        - "https://images.example.com/products/abc123/main.jpg" -> "images.example.com"
        - "https://media.example.com/assets/images/product.jpg" -> "media.example.com"
        
        Args:
            url: Image URL to extract folder pattern from
            
        Returns:
            Folder pattern string or None if extraction fails
        """
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                return None
            
            # Get the path and split into components
            path_parts = [part for part in parsed.path.split('/') if part]
            
            # For Shopify URLs, look for the pattern: /s/files/1/1234/5678/products/
            if 'shopify.com' in parsed.netloc and len(path_parts) >= 5:
                if path_parts[0] == 's' and path_parts[1] == 'files':
                    # Shopify pattern: /s/files/1/1234/5678/products/
                    if len(path_parts) >= 5:
                        return f"{parsed.netloc}/s/files/{path_parts[2]}/{path_parts[3]}/{path_parts[4]}"
            
            # For image/media/CDN subdomains, use just the domain (no subfolders)
            if self._is_image_subdomain(parsed.netloc):
                return parsed.netloc
            
            # For other URLs, take the first two path components as the folder pattern
            if len(path_parts) >= 2:
                return f"{parsed.netloc}/{path_parts[0]}/{path_parts[1]}"
            elif len(path_parts) == 1:
                return f"{parsed.netloc}/{path_parts[0]}"
            else:
                return parsed.netloc
                
        except Exception as e:
            logger.debug(f"Error extracting folder pattern from URL {url}: {e}")
            return None
    
    def _is_image_subdomain(self, netloc: str) -> bool:
        """
        Check if a domain is an image/media/CDN subdomain.
        
        Args:
            netloc: Domain name (e.g., "images.example.com")
            
        Returns:
            True if it's an image subdomain, False otherwise
        """
        # Common image/media/CDN subdomain prefixes
        image_subdomains = [
            'images', 'image', 'img', 'media', 'cdn', 'static', 'assets', 
            'files', 'uploads', 'photos', 'pics', 'pictures', 'thumbnails',
            'cache', 'storage', 'content', 'resources', 'public'
        ]
        
        # Split domain into parts
        domain_parts = netloc.split('.')
        
        # Check if the first part (subdomain) is in our list
        if len(domain_parts) >= 2:
            subdomain = domain_parts[0].lower()
            return subdomain in image_subdomains
        
        return False
    
    def _find_images_by_folder_patterns(self, folder_patterns: set) -> List[str]:
        """
        Find additional images from img tags that match the given folder patterns.
        Handles both src and srcset attributes.
        
        Args:
            folder_patterns: Set of folder patterns to search for
            
        Returns:
            List of additional image URLs found in img tags
        """
        additional_images = []
        
        # Find all img tags in the HTML
        img_tags = self.soup.find_all('img')
        logger.debug(f"Searching {len(img_tags)} img tags for folder patterns: {folder_patterns}")
        
        for img_tag in img_tags:
            # First check src attribute
            src = img_tag.get('src', '')
            if src:
                src = self._normalize_image_url(src)
                # Check if this image URL matches any of our folder patterns
                for pattern in folder_patterns:
                    if pattern in src:
                        additional_images.append(src)
                        logger.debug(f"Found matching image from src: {src} (matches pattern: {pattern})")
                        break
            
            # Then check srcset attribute (higher priority for responsive images)
            srcset = img_tag.get('srcset', '')
            if srcset:
                srcset_images = self._parse_srcset_and_filter_by_pattern(srcset, folder_patterns)
                additional_images.extend(srcset_images)
                if srcset_images:
                    logger.debug(f"Found {len(srcset_images)} matching images from srcset")
        
        return additional_images
    
    def _normalize_image_url(self, url: str) -> str:
        """
        Convert relative image URLs to absolute URLs.
        
        Args:
            url: Image URL to normalize
            
        Returns:
            Normalized absolute URL
        """
        if not url:
            return url
        
        # Convert relative URLs to absolute
        if url.startswith('//'):
            url = 'https:' + url
        elif url.startswith('/'):
            url = f"https://{parse_url_domain(self.url)}{url}"
        elif not url.startswith('http'):
            # Handle relative URLs without leading slash
            url = f"https://{parse_url_domain(self.url)}/{url}"
        
        return url
    
    def _parse_srcset_and_filter_by_pattern(self, srcset: str, folder_patterns: set) -> List[str]:
        """
        Parse srcset attribute and filter images by folder patterns.
        Returns the highest resolution images that match the patterns.
        
        Args:
            srcset: srcset attribute value
            folder_patterns: Set of folder patterns to match against
            
        Returns:
            List of matching image URLs (highest resolution for each unique image)
        """
        try:
            # Parse srcset into (url, width) tuples
            srcset_items = self._parse_srcset(srcset)
            
            # Group by base URL (without width parameters) and find highest resolution
            image_groups = {}
            for url, width in srcset_items:
                # Normalize URL
                normalized_url = self._normalize_image_url(url)
                
                # Get base URL without parameters for grouping
                base_url = self._get_base_url_without_params(normalized_url)
                
                # Check if this image matches any folder pattern
                matches_pattern = False
                for pattern in folder_patterns:
                    if pattern in normalized_url:
                        matches_pattern = True
                        break
                
                if matches_pattern:
                    # Group by base URL and keep the highest resolution
                    if base_url not in image_groups or width > image_groups[base_url][1]:
                        image_groups[base_url] = (normalized_url, width)
            
            # Return the highest resolution URLs
            return [url for url, width in image_groups.values()]
            
        except Exception as e:
            logger.debug(f"Error parsing srcset: {e}")
            return []
    
    def _parse_srcset(self, srcset: str) -> List[tuple]:
        """
        Parse srcset attribute into list of (url, width) tuples.
        
        Args:
            srcset: srcset attribute value
            
        Returns:
            List of (url, width) tuples
        """
        items = []
        
        try:
            # Split by commas and handle each item
            for item in srcset.split(','):
                item = item.strip()
                if not item:
                    continue
                
                # Split by whitespace to separate URL from width descriptor
                parts = item.split()
                if len(parts) >= 2:
                    url = parts[0].strip()
                    width_descriptor = parts[1].strip()
                    
                    # Extract width from descriptor (e.g., "1200w" -> 1200)
                    if width_descriptor.endswith('w'):
                        try:
                            width = int(width_descriptor[:-1])
                            items.append((url, width))
                        except ValueError:
                            # If width parsing fails, still include the URL with width 0
                            items.append((url, 0))
                    else:
                        # If no width descriptor, include with width 0
                        items.append((url, 0))
                elif len(parts) == 1:
                    # Single URL without width descriptor
                    items.append((parts[0].strip(), 0))
            
        except Exception as e:
            logger.debug(f"Error parsing srcset item: {e}")
        
        return items
    
    def _get_base_url_without_params(self, url: str) -> str:
        """
        Get base URL without any query parameters.
        
        Args:
            url: Image URL
            
        Returns:
            Base URL without any parameters
        """
        try:
            parsed = urlparse(url)
            # Return URL with scheme, netloc, and path only (no query parameters or fragments)
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            
        except Exception as e:
            logger.debug(f"Error getting base URL: {e}")
            return url 