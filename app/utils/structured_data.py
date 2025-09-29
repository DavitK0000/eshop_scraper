from typing import Optional, List, Dict, Any, Tuple
import json
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from app.logging_config import get_logger

logger = get_logger(__name__)


class StructuredDataExtractor:
    """Utility class for extracting structured data (JSON-LD) from HTML content"""
    
    def __init__(self, html_content: str, url: str):
        """
        Initialize with HTML content
        
        Args:
            html_content: Raw HTML content from the page
            url: Original URL that was scraped
        """
        self.html_content = html_content
        self.url = url
        self.soup = BeautifulSoup(html_content, 'html.parser')
    
    def extract_structured_product_data(self) -> Optional[dict]:
        """
        Extract product data from structured JSON sources (JSON-LD and ProductJson)
        
        Returns:
            Combined product data dictionary or None if no data found
        """
        try:
            all_product_data = []
            
            # Method 1: Look for ProductJson script tags (common in e-commerce platforms)
            product_json_scripts = self.soup.find_all('script', id=re.compile(r'(ProductJson-.*|WH-ProductJson-.*)'))
            for script in product_json_scripts:
                print(script.string)
                if script.string:
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and ('title' in data or 'variants' in data):
                            all_product_data.append(('ProductJson', data))
                    except json.JSONDecodeError:
                        print("Error parsing json")
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
                    # logger.debug("Found @graph array in JSON-LD data")
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
                # logger.debug("Found array in JSON-LD data")
                for item in data:
                    if isinstance(item, dict):
                        item_data = self._extract_data_from_json_ld_item(item)
                        if item_data:
                            processed_data.extend(item_data)
            
            return processed_data
            
        except Exception as e:
            # logger.debug(f"Error processing JSON-LD data: {e}")
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
                    extracted_data.append(('JSON-LD-Rating', new_product))
            
            return extracted_data
            
        except Exception as e:
            # logger.debug(f"Error extracting data from JSON-LD item: {e}")
            return []
    
    def _normalize_image_url(self, image_url: str) -> str:
        """
        Normalize image URL by handling protocol-relative URLs and other common URL issues.
        
        Args:
            image_url: Image URL to normalize
            
        Returns:
            Normalized absolute URL
        """
        if not image_url:
            return image_url
        
        # Handle protocol-relative URLs (starting with //)
        if image_url.startswith('//'):
            image_url = 'https:' + image_url
        # Handle relative URLs (starting with /)
        elif image_url.startswith('/'):
            # Use the base URL from the page to make it absolute
            parsed_base = urlparse(self.url)
            image_url = f"{parsed_base.scheme}://{parsed_base.netloc}{image_url}"
        # Handle relative URLs without leading slash
        elif not image_url.startswith(('http://', 'https://')):
            # Use the base URL from the page to make it absolute
            parsed_base = urlparse(self.url)
            image_url = f"{parsed_base.scheme}://{parsed_base.netloc}/{image_url}"
        
        return image_url

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
                
                currency = self._extract_currency_from_offer(primary_offer)
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
            
            currency = self._extract_currency_from_offer(offers)
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
        
        # Extract images directly from JSON-LD data
        images = json_ld_data.get('image', [])
        if isinstance(images, str):
            images = [images]
        elif isinstance(images, dict):
            # Handle single ImageObject (not array)
            processed_images = []
            img_url = images.get('url', '') or images.get('src', '') or images.get('image', '')
            if img_url:
                processed_images.append(self._normalize_image_url(img_url))
            images = processed_images
        elif isinstance(images, list):
            # Handle array of images (both strings and objects)
            processed_images = []
            for img in images:
                if isinstance(img, str):
                    processed_images.append(self._normalize_image_url(img))
                elif isinstance(img, dict):
                    # Image object with url property
                    img_url = img.get('url', '') or img.get('src', '') or img.get('image', '')
                    if img_url:
                        processed_images.append(self._normalize_image_url(img_url))
            images = processed_images
        
        product_data['images'] = images
        
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
        
        if rating_data:
            product_data['rating'] = rating_data
        
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
            
            # Check for priceSpecification array (nested price structure)
            price_specifications = offer.get('priceSpecification', [])
            if isinstance(price_specifications, list) and price_specifications:
                # Use the first price specification
                price_spec = price_specifications[0]
                if isinstance(price_spec, dict):
                    price = price_spec.get('price', '')
                    if price:
                        return str(price)
            elif isinstance(price_specifications, dict):
                # Single price specification object
                price = price_specifications.get('price', '')
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
            # logger.debug(f"Error extracting price from offer: {e}")
            return None
    
    def _extract_currency_from_offer(self, offer: dict) -> Optional[str]:
        """
        Extract currency from an offer object, handling various currency formats.
        
        Args:
            offer: Offer object from JSON-LD structured data
            
        Returns:
            Currency string if found, None otherwise
        """
        try:
            # First try direct priceCurrency field
            currency = offer.get('priceCurrency', '')
            if currency:
                return currency
            
            # Check for priceSpecification array (nested currency structure)
            price_specifications = offer.get('priceSpecification', [])
            if isinstance(price_specifications, list) and price_specifications:
                # Use the first price specification
                price_spec = price_specifications[0]
                if isinstance(price_spec, dict):
                    currency = price_spec.get('priceCurrency', '')
                    if currency:
                        return currency
            elif isinstance(price_specifications, dict):
                # Single price specification object
                currency = price_specifications.get('priceCurrency', '')
                if currency:
                    return currency
            
            # Check for alternative currency field names
            for currency_field in ['currency', 'currencyCode', 'currency_code']:
                currency = offer.get(currency_field, '')
                if currency:
                    return currency
            
            return None
            
        except Exception as e:
            # logger.debug(f"Error extracting currency from offer: {e}")
            return None
    
    def _extract_json_ld_rating_data(self, json_ld_data: dict) -> Optional[dict]:
        """Extract rating data from JSON-LD rating object"""
        try:
            rating_data = {}
            
            # Extract rating value
            rating_value = json_ld_data.get('ratingValue', '')
            if rating_value:
                rating_data['value'] = str(rating_value)
            
            # Extract review count
            review_count = json_ld_data.get('reviewCount', '')
            if review_count:
                rating_data['review_count'] = str(review_count)
            
            # Extract best/worst rating
            best_rating = json_ld_data.get('bestRating', '')
            if best_rating:
                rating_data['best_rating'] = str(best_rating)
            
            worst_rating = json_ld_data.get('worstRating', '')
            if worst_rating:
                rating_data['worst_rating'] = str(worst_rating)
            
            return rating_data if rating_data else None
            
        except Exception as e:
            # logger.debug(f"Error extracting rating data: {e}")
            return None
    
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
    
    def _combine_product_data(self, all_product_data: list) -> dict:
        """
        Combine multiple product data sources into a single dictionary.
        Prioritizes data from more reliable sources and merges complementary information.
        
        Args:
            all_product_data: List of (source_name, data) tuples
            
        Returns:
            Combined product data dictionary
        """
        combined_data = {}
        ratings = []
        
        # Sort by source priority (ProductJson first, then JSON-LD)
        source_priority = {
            'ProductJson': 1,
            'JSON-LD': 2,
            'JSON-LD-Rating': 3
        }
        
        sorted_data = sorted(all_product_data, key=lambda x: source_priority.get(x[0], 999))
        
        for source_name, data in sorted_data:
            if not isinstance(data, dict):
                continue
            
            # Handle rating data separately
            if source_name == 'JSON-LD-Rating':
                if 'rating' in data:
                    ratings.append(data['rating'])
                continue
            
            # Merge main product data
            for key, value in data.items():
                if key == 'rating':
                    # Collect rating data for later merging
                    ratings.append(value)
                elif key not in combined_data or not combined_data[key]:
                    # Use value if key doesn't exist or is empty
                    combined_data[key] = value
                elif isinstance(value, list) and isinstance(combined_data[key], list):
                    # Merge lists (for images, variants, etc.)
                    combined_data[key].extend(value)
                elif isinstance(value, dict) and isinstance(combined_data[key], dict):
                    # Merge dictionaries
                    combined_data[key].update(value)
        
        # Merge rating data
        if ratings:
            combined_rating = self._merge_rating_data(ratings)
            if combined_rating:
                combined_data['rating'] = combined_rating
        
        # Clean up lists (remove duplicates)
        for key in ['images', 'variants']:
            if key in combined_data and isinstance(combined_data[key], list):
                if key == 'images':
                    # For images (strings), use dict.fromkeys to remove duplicates
                    combined_data[key] = list(dict.fromkeys(combined_data[key]))
                elif key == 'variants':
                    # For variants (dicts), use a different approach to remove duplicates
                    seen = set()
                    unique_variants = []
                    for variant in combined_data[key]:
                        if isinstance(variant, dict):
                            # Create a hashable representation of the variant
                            variant_key = self._create_hashable_key(variant)
                            if variant_key not in seen:
                                seen.add(variant_key)
                                unique_variants.append(variant)
                        else:
                            # For non-dict variants, use the value itself
                            if variant not in seen:
                                seen.add(variant)
                                unique_variants.append(variant)
                    combined_data[key] = unique_variants
        
        return combined_data
    
    def _create_hashable_key(self, obj: Any) -> tuple:
        """
        Create a hashable key from a dictionary or other object.
        Recursively handles nested dictionaries and lists.
        
        Args:
            obj: Object to convert to hashable key
            
        Returns:
            Hashable tuple representation
        """
        if isinstance(obj, dict):
            # Sort items and recursively convert values
            sorted_items = []
            for key, value in sorted(obj.items()):
                sorted_items.append((key, self._create_hashable_key(value)))
            return tuple(sorted_items)
        elif isinstance(obj, list):
            # Convert list to tuple and recursively convert items
            return tuple(self._create_hashable_key(item) for item in obj)
        elif isinstance(obj, (str, int, float, bool, type(None))):
            # These types are already hashable
            return obj
        else:
            # For other types, convert to string
            return str(obj)
    
    def _merge_rating_data(self, ratings: list) -> dict:
        """
        Merge multiple rating data sources into a single rating object.
        
        Args:
            ratings: List of rating dictionaries
            
        Returns:
            Merged rating dictionary
        """
        if not ratings:
            return {}
        
        merged_rating = {}
        
        # Collect all rating values
        rating_values = []
        review_counts = []
        best_ratings = []
        worst_ratings = []
        
        for rating in ratings:
            if isinstance(rating, dict):
                if 'value' in rating:
                    rating_values.append(rating['value'])
                if 'review_count' in rating:
                    review_counts.append(rating['review_count'])
                if 'best_rating' in rating:
                    best_ratings.append(rating['best_rating'])
                if 'worst_rating' in rating:
                    worst_ratings.append(rating['worst_rating'])
        
        # Use the first non-empty value for each field
        if rating_values:
            merged_rating['value'] = rating_values[0]
        if review_counts:
            merged_rating['review_count'] = review_counts[0]
        if best_ratings:
            merged_rating['best_rating'] = best_ratings[0]
        if worst_ratings:
            merged_rating['worst_rating'] = worst_ratings[0]
        
        return merged_rating 