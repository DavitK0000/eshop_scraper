#!/usr/bin/env python3
"""
Test script to verify timeout fixes in browser manager
"""

import asyncio
import logging
from app.browser_manager import browser_manager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_timeout_fix():
    """Test the timeout fixes with a problematic URL"""
    
    # Test URL that was causing timeout issues
    test_url = "https://www.allbirds.com/products/mens-tree-runners"
    
    try:
        logger.info(f"Testing timeout fix with URL: {test_url}")
        
        # Try to get content with retry logic
        html_content = await browser_manager.get_page_content_with_retry(test_url)
        
        logger.info(f"Success! Retrieved {len(html_content)} characters of HTML content")
        
        # Check if we got meaningful content
        if len(html_content) > 1000:
            logger.info("✅ Test passed: Got substantial HTML content")
        else:
            logger.warning("⚠️ Test warning: Got minimal HTML content")
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise
    finally:
        # Clean up
        await browser_manager.cleanup()

if __name__ == "__main__":
    asyncio.run(test_timeout_fix()) 