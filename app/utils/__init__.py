# Import all utility functions and classes
from .proxy_management import ProxyManager, DecodoProxyManager
from .user_agent_management import UserAgentManager
from .text_processing import (
    sanitize_text,
    parse_price_with_regional_format,
    extract_price_from_text,
    extract_price_value,
    extract_rating_from_text,
    extract_number_from_text
)
from .url_utils import (
    generate_task_id,
    generate_cache_key,
    parse_url_domain,
    is_valid_url
)
from .currency_utils import (
    map_currency_symbol_to_code,
    _get_default_currency_by_domain
)
from .structured_data import StructuredDataExtractor

# Create global instances
proxy_manager = ProxyManager()
user_agent_manager = UserAgentManager()

# Export everything for backward compatibility
__all__ = [
    # Classes
    'ProxyManager',
    'DecodoProxyManager', 
    'UserAgentManager',
    'StructuredDataExtractor',
    
    # Global instances
    'proxy_manager',
    'user_agent_manager',
    
    # Text processing functions
    'sanitize_text',
    'parse_price_with_regional_format',
    'extract_price_from_text',
    'extract_price_value',
    'extract_rating_from_text',
    'extract_number_from_text',
    
    # URL utilities
    'generate_task_id',
    'generate_cache_key',
    'parse_url_domain',
    'is_valid_url',
    
    # Currency utilities
    'map_currency_symbol_to_code',
    '_get_default_currency_by_domain',
] 

def cleanup_windows_asyncio():
    """Windows-specific cleanup for asyncio overlapped objects"""
    import platform
    if platform.system() == "Windows":
        try:
            import asyncio
            import gc
            
            # Get the current event loop if it exists
            try:
                loop = asyncio.get_running_loop()
                # Cancel all pending tasks
                for task in asyncio.all_tasks(loop):
                    if not task.done():
                        task.cancel()
            except RuntimeError:
                # No running loop
                pass
            
            # Force garbage collection
            gc.collect()
            
        except Exception:
            pass 