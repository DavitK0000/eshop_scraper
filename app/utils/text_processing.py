import re
from typing import Optional


def sanitize_text(text: str) -> str:
    """Clean and sanitize text content"""
    if not text:
        return ""
    
    # Remove extra whitespace
    text = " ".join(text.split())
    
    # Remove common unwanted characters
    text = text.replace('\xa0', ' ')  # Non-breaking space
    text = text.replace('\u200b', '')  # Zero-width space
    
    return text.strip()


def parse_price_with_regional_format(price_text: str, domain: str = None) -> Optional[float]:
    """
    Parse price text considering regional number formatting differences
    
    Args:
        price_text: Price text to parse (e.g., "1,234.56", "1.234,56", "1234,56")
        domain: Optional domain for determining regional format
    
    Returns:
        Parsed price as float, or None if parsing fails
    """
    if not price_text:
        return None
    
    # Remove currency symbols and extra whitespace
    price_text = re.sub(r'[\$€£¥₹₽₩₪₨₦₡₫₱₲₴₵₸₺₼₾₿]', '', price_text).strip()
    
    # Determine if this is likely European format based on domain
    is_european_format = False
    if domain:
        domain = domain.lower()
        european_domains = [
            'amazon.de', 'amazon.fr', 'amazon.it', 'amazon.es', 'amazon.nl',
            'ebay.de', 'ebay.fr', 'ebay.it', 'ebay.es', 'ebay.nl',
            'bol.com', 'cdiscount.com', 'otto.de'
        ]
        is_european_format = any(eu_domain in domain for eu_domain in european_domains)
    
    # Pattern to match numbers with either format
    # This will match: 1,234.56 (US), 1.234,56 (EU), 1234,56 (EU), 1234.56 (US)
    number_pattern = r'(\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d+[.,]\d{2}|\d+)'
    match = re.search(number_pattern, price_text)
    
    if not match:
        return None
    
    number_str = match.group(1)
    
    # Enhanced logic to detect European format based on number structure
    # If we have both comma and period, determine which is decimal separator
    if ',' in number_str and '.' in number_str:
        # Count digits after each separator
        comma_parts = number_str.split(',')
        period_parts = number_str.split('.')
        
        # If comma has 2 digits after it, it's likely the decimal separator (EU format)
        if len(comma_parts[-1]) == 2 and len(period_parts[-1]) != 2:
            is_european_format = True
        # If period has 2 digits after it, it's likely the decimal separator (US format)
        elif len(period_parts[-1]) == 2 and len(comma_parts[-1]) != 2:
            is_european_format = False
        # If both have 2 digits, use domain-based decision
        elif len(comma_parts[-1]) == 2 and len(period_parts[-1]) == 2:
            pass  # Use domain-based decision
        # If neither has 2 digits, use domain-based decision
        else:
            pass  # Use domain-based decision
    # If we only have a comma, check if it's followed by exactly 2 digits (EU decimal format)
    elif ',' in number_str and '.' not in number_str:
        comma_parts = number_str.split(',')
        # If the part after comma has exactly 2 digits, it's likely EU decimal format
        if len(comma_parts) == 2 and len(comma_parts[-1]) == 2:
            is_european_format = True
        # If the part after comma has 3 digits, it's likely US thousands separator
        elif len(comma_parts) == 2 and len(comma_parts[-1]) == 3:
            is_european_format = False
        # For other cases, use domain-based decision
        else:
            pass  # Use domain-based decision
    
    # Parse the number based on format
    try:
        if is_european_format:
            # European format: 1.234,56 -> 1234.56 or 86,80 -> 86.80
            # Remove dots (thousands separators) and replace comma with dot
            clean_number = number_str.replace('.', '').replace(',', '.')
        else:
            # US format: 1,234.56 -> 1234.56
            # Remove commas (thousands separators)
            clean_number = number_str.replace(',', '')
        
        return float(clean_number)
    except ValueError:
        return None


def extract_price_from_text(price_text: str, domain: str = None) -> Optional[str]:
    """Extract price from text with regional format support"""
    if not price_text:
        return None
    
    # Common price patterns with regional format support
    patterns = [
        r'[\$€£¥₹₽₩₪₨₦₡₫₱₲₴₵₸₺₼₾₿]?\s*(\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d+[.,]\d{2}|\d+)',  # $1,234.56 or €1.234,56
        r'(\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d+[.,]\d{2}|\d+)\s*[\$€£¥₹₽₩₪₨₦₡₫₱₲₴₵₸₺₼₾₿]',  # 1,234.56$ or 1.234,56€
    ]
    
    for pattern in patterns:
        match = re.search(pattern, price_text)
        if match:
            return match.group(0)  # Return the full match including currency symbol
    
    return None


def extract_price_value(price_text: str, domain: str = None) -> Optional[float]:
    """
    Extract numeric price value from text, handling regional formats
    
    Args:
        price_text: Price text to parse
        domain: Optional domain for determining regional format
    
    Returns:
        Parsed price as float, or None if parsing fails
    """
    return parse_price_with_regional_format(price_text, domain)


def extract_rating_from_text(rating_text: str) -> Optional[float]:
    """Extract rating from text"""
    if not rating_text:
        return None
    
    # Look for rating patterns like "4.5", "4.5/5", "4.5 out of 5"
    patterns = [
        r'(\d+\.?\d*)\s*out\s*of\s*(\d+)',
        r'(\d+\.?\d*)\s*/\s*(\d+)',
        r'(\d+\.?\d*)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, rating_text)
        if match:
            if len(match.groups()) == 2:
                # Convert to 5-star scale
                rating = float(match.group(1))
                max_rating = float(match.group(2))
                return (rating / max_rating) * 5
            else:
                rating = float(match.group(1))
                return min(rating, 5.0)  # Cap at 5.0
    
    return None


def extract_number_from_text(text: str) -> Optional[int]:
    """
    Extract number from text like '123 ratings', '14 reviews', '1,234 customers'
    
    Args:
        text: Text containing numbers (e.g., "14 ratings", "1,234 reviews")
    
    Returns:
        Extracted number as integer, or None if no number found
    """
    if not text:
        return None
    
    # Remove common words and extract numbers
    text = text.lower()
    text = re.sub(r'(ratings?|reviews?|customers?|bewertungen?|avis|évaluations?|commentaires?|mal|times|ratings?|reviews?)', '', text)
    
    # Remove commas and other non-numeric characters except digits
    text = re.sub(r'[^\d]', '', text)
    
    # Find numbers in the text
    if text:
        try:
            return int(text)
        except ValueError:
            pass
    
    # Fallback: try to find any number pattern
    numbers = re.findall(r'\d+', text)
    if numbers:
        try:
            return int(numbers[0])
        except ValueError:
            pass
    
    return None 