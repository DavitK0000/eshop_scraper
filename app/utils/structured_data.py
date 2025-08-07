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
                    extracted_data.append(('JSON-LD-Rating', new_product))
            
            return extracted_data
            
        except Exception as e:
            logger.debug(f"Error extracting data from JSON-LD item: {e}")
            return []
    
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
        if images:
            enhanced_images = self._enhance_images_from_json_ld_clues(images)
            product_data['images'] = enhanced_images
        else:
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
            logger.debug(f"Error extracting price from offer: {e}")
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
            logger.debug(f"Error extracting currency from offer: {e}")
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
            logger.debug(f"Error extracting rating data: {e}")
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
                combined_data[key] = list(dict.fromkeys(combined_data[key]))
        
        return combined_data
    
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
        Filter images to only include those with width >= min_width and exclude SVG and GIF images.
        
        Args:
            images: List of image URLs to filter
            min_width: Minimum width in pixels (default: 1024)
            
        Returns:
            Filtered list of image URLs that meet the minimum width requirement and are not SVG or GIF
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
            
            # Skip GIF images (usually animations)
            if self._is_gif_image(image_url):
                logger.debug(f"Filtered out GIF image: {image_url}")
                continue
            
            # Check if image meets minimum width requirement
            if self._check_image_width(image_url, min_width):
                filtered_images.append(image_url)
            else:
                logger.info(f"Filtered out image below minimum width ({min_width}px): {image_url}")
        
        return filtered_images
    
    def _is_svg_image(self, image_url: str) -> bool:
        """Check if image URL points to an SVG file"""
        if not image_url:
            return False
        
        # Check file extension
        if image_url.lower().endswith('.svg'):
            return True
        
        # Check for SVG in URL path
        if '.svg' in image_url.lower():
            return True
        
        # Check for SVG in query parameters
        if 'svg' in image_url.lower():
            return True
        
        return False
    
    def _is_gif_image(self, image_url: str) -> bool:
        """Check if image URL points to a GIF file"""
        if not image_url:
            return False
        
        # Check file extension
        if image_url.lower().endswith('.gif'):
            return True
        
        # Check for GIF in URL path
        if '.gif' in image_url.lower():
            return True
        
        # Check for GIF in query parameters
        if 'gif' in image_url.lower():
            return True
        
        return False
    
    def _deduplicate_images_by_base_url(self, images: List[str]) -> List[str]:
        """
        Remove duplicate images that have the same base URL but different parameters.
        
        Args:
            images: List of image URLs to deduplicate
            
        Returns:
            Deduplicated list of image URLs
        """
        if not images:
            return []
        
        # Group images by base URL
        image_groups = {}
        for image_url in images:
            if not image_url:
                continue
            
            base_url = self._get_base_url_without_params(image_url)
            if base_url not in image_groups:
                image_groups[base_url] = []
            image_groups[base_url].append(image_url)
        
        # Select the best image from each group
        deduplicated_images = []
        for base_url, url_list in image_groups.items():
            if len(url_list) == 1:
                # Only one image in group, use it directly
                deduplicated_images.append(url_list[0])
            else:
                # Multiple images in group, select the best one
                best_image = self._select_best_image_from_group(url_list)
                deduplicated_images.append(best_image)
        
        return deduplicated_images
    
    def _select_best_image_from_group(self, url_list: List[str]) -> str:
        """
        Select the best image from a group of URLs that share the same base URL.
        
        Args:
            url_list: List of image URLs to choose from
            
        Returns:
            The best image URL from the group
        """
        if not url_list:
            return ""
        
        if len(url_list) == 1:
            return url_list[0]
        
        # Priority order for image selection
        priority_patterns = [
            r'large', r'big', r'high', r'full', r'original',  # Large images
            r'2048', r'1920', r'1600', r'1440', r'1200',      # High resolution
            r'1024', r'800', r'600',                          # Medium resolution
            r'thumb', r'small', r'mini', r'tiny'              # Small images (avoid)
        ]
        
        best_score = -1
        best_url = url_list[0]  # Default to first URL
        
        for url in url_list:
            url_lower = url.lower()
            score = 0
            
            # Check for priority patterns
            for i, pattern in enumerate(priority_patterns):
                if re.search(pattern, url_lower):
                    # Higher priority for earlier patterns (larger images)
                    score += len(priority_patterns) - i
                    break
            
            # Bonus for URLs with size parameters
            if re.search(r'[?&](w|width|h|height)=\d+', url_lower):
                score += 5
            
            # Penalty for URLs with 'thumb' or 'small' in the path
            if re.search(r'thumb|small|mini|tiny', url_lower):
                score -= 10
            
            # Bonus for URLs without many parameters (cleaner URLs)
            param_count = url.count('&') + url.count('?')
            score -= param_count
            
            if score > best_score:
                best_score = score
                best_url = url
        
        return best_url
    
    def _check_image_width(self, image_url: str, min_width: int) -> bool:
        """
        Check if image meets minimum width requirement.
        
        Args:
            image_url: Image URL to check
            min_width: Minimum width in pixels
            
        Returns:
            True if image meets minimum width requirement, False otherwise
        """
        if not image_url:
            return False
        
        # First try to extract width from URL
        width = self._extract_width_from_url(image_url)
        if width:
            logger.debug(f"Extracted width {width}px from URL: {image_url}")
            if width >= min_width:
                return True
            else:
                logger.info(f"Image width {width}px is below minimum {min_width}px: {image_url}")
                return False
        
        # If no width in URL, try to extract from img tag attributes
        width = self._extract_width_from_img_tag(image_url)
        if width:
            logger.debug(f"Extracted width {width}px from img tag: {image_url}")
            if width >= min_width:
                return True
            else:
                logger.info(f"Image width {width}px is below minimum {min_width}px: {image_url}")
                return False
        
        # If we can't determine width, assume it's acceptable
        # (better to include than exclude)
        logger.debug(f"Could not determine width for image, assuming acceptable: {image_url}")
        return True
    
    def _extract_width_from_url(self, image_url: str) -> Optional[int]:
        """Extract width from image URL parameters"""
        if not image_url:
            return None
        
        # Look for width parameters in URL
        width_patterns = [
            r'[?&]w=(\d+)',
            r'[?&]width=(\d+)',
            r'[?&]x=(\d+)',
            r'_(\d+)x\d+\.',  # _800x600.jpg
            r'(\d+)x\d+\.',   # 800x600.jpg
            r'_(\d+)\.',      # _800.jpg
            r'(\d+)\.',       # 800.jpg
            # Handle widthxheight format in URL path (e.g., 300x300, 800x600)
            r'(\d+)x\d+',     # 300x300, 800x600, etc.
        ]
        
        for pattern in width_patterns:
            match = re.search(pattern, image_url)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _extract_width_from_img_tag(self, image_url: str) -> Optional[int]:
        """
        Extract width from img tag attributes in the HTML.
        
        Args:
            image_url: Image URL to find in img tags
            
        Returns:
            Width in pixels if found, None otherwise
        """
        if not image_url:
            return None
        
        # Find img tags with this URL
        img_tags = self.soup.find_all('img', src=image_url)
        if not img_tags:
            # Try with different URL variations
            base_url = self._get_base_url_without_params(image_url)
            img_tags = self.soup.find_all('img')
            img_tags = [img for img in img_tags if self._urls_match(img.get('src', ''), base_url)]
        
        for img_tag in img_tags:
            width = self._extract_width_from_img_tag_attributes(img_tag)
            if width:
                return width
        
        return None
    
    def _extract_width_from_img_tag_attributes(self, img_tag) -> Optional[int]:
        """
        Extract width from img tag attributes.
        
        Args:
            img_tag: BeautifulSoup img tag element
            
        Returns:
            Width in pixels if found, None otherwise
        """
        if not img_tag:
            return None
        
        # Check width attribute
        width_attr = img_tag.get('width')
        if width_attr:
            try:
                return int(width_attr)
            except (ValueError, TypeError):
                pass
        
        # Check style attribute for width
        style_attr = img_tag.get('style', '')
        if style_attr:
            width_match = re.search(r'width:\s*(\d+)px', style_attr)
            if width_match:
                try:
                    return int(width_match.group(1))
                except (ValueError, IndexError):
                    pass
        
        # Check data attributes
        for attr_name in ['data-width', 'data-original-width', 'data-src-width']:
            width_attr = img_tag.get(attr_name)
            if width_attr:
                try:
                    return int(width_attr)
                except (ValueError, TypeError):
                    pass
        
        return None
    
    def _extract_top_level_folder_from_url(self, url: str) -> Optional[str]:
        """
        Extract top-level folder pattern from image URL.
        
        Args:
            url: Image URL
            
        Returns:
            Folder pattern if found, None otherwise
        """
        if not url:
            return None
        
        try:
            parsed = urlparse(url)
            path_parts = parsed.path.strip('/').split('/')
            
            if len(path_parts) >= 2:
                # Return first two parts of path (e.g., "images/products")
                return '/'.join(path_parts[:2])
            elif len(path_parts) == 1:
                # Return single path part
                return path_parts[0]
            else:
                # Check if it's a subdomain
                if self._is_image_subdomain(parsed.netloc):
                    return parsed.netloc
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting folder pattern from URL {url}: {e}")
            return None
    
    def _is_image_subdomain(self, netloc: str) -> bool:
        """
        Check if netloc is an image subdomain.
        
        Args:
            netloc: Network location (domain)
            
        Returns:
            True if it's an image subdomain, False otherwise
        """
        if not netloc:
            return False
        
        netloc_lower = netloc.lower()
        
        # Common image subdomain patterns
        image_subdomains = [
            'images', 'img', 'cdn', 'static', 'assets', 'media',
            'photos', 'pics', 'pictures', 'uploads', 'files'
        ]
        
        # Check if any part of the domain contains image-related keywords
        for subdomain in image_subdomains:
            if subdomain in netloc_lower:
                return True
        
        return False
    
    def _find_images_by_folder_patterns(self, folder_patterns: set) -> List[str]:
        """
        Find additional images in img tags that match the given folder patterns.
        
        Args:
            folder_patterns: Set of folder patterns to search for
            
        Returns:
            List of additional image URLs found
        """
        if not folder_patterns:
            return []
        
        additional_images = []
        img_tags = self.soup.find_all('img')
        
        for img_tag in img_tags:
            src = img_tag.get('src', '')
            if not src:
                continue
            
            # Check if this image matches any of our folder patterns
            for pattern in folder_patterns:
                if pattern in src:
                    additional_images.append(src)
                    break
        
        return additional_images
    
    def _urls_match(self, url1: str, url2: str) -> bool:
        """
        Check if two URLs match (ignoring parameters).
        
        Args:
            url1: First URL
            url2: Second URL
            
        Returns:
            True if URLs match, False otherwise
        """
        if not url1 or not url2:
            return False
        
        # Get base URLs without parameters
        base1 = self._get_base_url_without_params(url1)
        base2 = self._get_base_url_without_params(url2)
        
        return base1 == base2
    
    def _get_base_url_without_params(self, url: str) -> str:
        """
        Get base URL without query parameters and fragments.
        
        Args:
            url: URL to process
            
        Returns:
            Base URL without parameters
        """
        if not url:
            return ""
        
        try:
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            return base_url
        except Exception:
            return url 