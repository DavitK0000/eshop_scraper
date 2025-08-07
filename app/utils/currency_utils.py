import re


def map_currency_symbol_to_code(currency_symbol: str, domain: str = None) -> str:
    """
    Map currency symbol to 3-character ISO currency code
    
    Args:
        currency_symbol: Currency symbol (e.g., '$', '€', '£') or text containing currency
        domain: Optional domain for fallback currency detection
    
    Returns:
        3-character currency code (e.g., 'USD', 'EUR', 'GBP')
    """
    if not currency_symbol:
        return _get_default_currency_by_domain(domain)
    
    # Clean the currency symbol
    currency_symbol = currency_symbol.strip()
    
    # Common currency symbols and their codes
    currency_map = {
        '$': 'USD',
        '€': 'EUR',
        '£': 'GBP',
        '¥': 'JPY',
        '₹': 'INR',
        '₽': 'RUB',
        '₩': 'KRW',
        '₪': 'ILS',
        '₨': 'PKR',
        '₦': 'NGN',
        '₡': 'CRC',
        '₫': 'VND',
        '₱': 'PHP',
        '₲': 'PYG',
        '₴': 'UAH',
        '₵': 'GHS',
        '₸': 'KZT',
        '₺': 'TRY',
        '₼': 'AZN',
        '₾': 'GEL',
        '₿': 'BTC'
    }
    
    # First, try to extract currency symbol from the text
    # Look for currency symbols in the text
    currency_symbol_pattern = r'[\$€£¥₹₽₩₪₨₦₡₫₱₲₴₵₸₺₼₾₿]'
    symbol_match = re.search(currency_symbol_pattern, currency_symbol)
    
    if symbol_match:
        found_symbol = symbol_match.group(0)
        if found_symbol in currency_map:
            return currency_map[found_symbol]
    
    # Direct symbol mapping (for when the input is already just a symbol)
    if currency_symbol in currency_map:
        return currency_map[currency_symbol]
    
    # Check if it's already a 3-character code
    if len(currency_symbol) == 3 and currency_symbol.isupper():
        return currency_symbol
    
    # Try to match currency codes in text
    currency_pattern = r'\b(USD|EUR|GBP|JPY|INR|RUB|KRW|ILS|PKR|NGN|CRC|VND|PHP|PYG|UAH|GHS|KZT|TRY|AZN|GEL|BTC)\b'
    currency_match = re.search(currency_pattern, currency_symbol.upper())
    
    if currency_match:
        return currency_match.group(1)
    
    # Fallback to domain-based default
    return _get_default_currency_by_domain(domain)


def _get_default_currency_by_domain(domain: str) -> str:
    """Get default currency based on domain"""
    if not domain:
        return "USD"
    
    domain = domain.lower()
    
    # Amazon domains
    if 'amazon.com' in domain:
        return "USD"
    elif 'amazon.co.uk' in domain:
        return "GBP"
    elif 'amazon.de' in domain or 'amazon.fr' in domain or 'amazon.it' in domain or 'amazon.es' in domain:
        return "EUR"
    elif 'amazon.ca' in domain:
        return "CAD"
    elif 'amazon.co.jp' in domain:
        return "JPY"
    elif 'amazon.in' in domain:
        return "INR"
    elif 'amazon.com.au' in domain:
        return "AUD"
    elif 'amazon.com.br' in domain:
        return "BRL"
    elif 'amazon.com.mx' in domain:
        return "MXN"
    
    # Other common domains
    elif 'ebay.com' in domain:
        return "USD"
    elif 'ebay.co.uk' in domain:
        return "GBP"
    elif 'ebay.de' in domain or 'ebay.fr' in domain or 'ebay.it' in domain or 'ebay.es' in domain:
        return "EUR"
    elif 'ebay.nl' in domain:
        return "EUR"
    
    # European e-commerce sites
    elif 'otto.de' in domain:
        return "EUR"
    elif 'bol.com' in domain:
        return "EUR"
    elif 'cdiscount.com' in domain:
        return "EUR"
    
    # Default to USD
    return "USD" 