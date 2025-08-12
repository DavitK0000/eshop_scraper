#!/usr/bin/env python3
"""
Test script for the new Bigcommerce and Squarespace extractors
"""

import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.extractors.factory import ExtractorFactory
from app.logging_config import get_logger

logger = get_logger(__name__)

def test_extractor_factory():
    """Test that the new extractors are properly registered in the factory"""
    print("Testing ExtractorFactory...")
    
    # Check if new platforms are supported
    supported_platforms = ExtractorFactory.get_supported_platforms()
    print(f"Supported platforms: {supported_platforms}")
    
    # Check specific platforms
    assert 'bigcommerce' in supported_platforms, "Bigcommerce not found in supported platforms"
    assert 'squarespace' in supported_platforms, "Squarespace not found in supported platforms"
    
    print("✓ Bigcommerce and Squarespace are properly registered in ExtractorFactory")
    
    # Test platform support checking
    assert ExtractorFactory.is_platform_supported('bigcommerce'), "Bigcommerce not recognized as supported"
    assert ExtractorFactory.is_platform_supported('squarespace'), "Squarespace not recognized as supported"
    
    print("✓ Platform support checking works correctly")

def test_extractor_creation():
    """Test that the new extractors can be created"""
    print("\nTesting extractor creation...")
    
    # Test HTML content
    test_html = """
    <html>
        <head>
            <title>Test Product</title>
        </head>
        <body>
            <h1>Test Product Title</h1>
            <div class="price">$99.99</div>
            <div class="description">Test product description</div>
        </body>
    </html>
    """
    test_url = "https://example.com/product"
    
    # Test Bigcommerce extractor creation
    try:
        bigcommerce_extractor = ExtractorFactory.create_extractor('bigcommerce', test_html, test_url)
        print(f"✓ Bigcommerce extractor created: {type(bigcommerce_extractor).__name__}")
        assert bigcommerce_extractor.platform == "bigcommerce", "Bigcommerce extractor platform not set correctly"
    except Exception as e:
        print(f"✗ Failed to create Bigcommerce extractor: {e}")
        return False
    
    # Test Squarespace extractor creation
    try:
        squarespace_extractor = ExtractorFactory.create_extractor('squarespace', test_html, test_url)
        print(f"✓ Squarespace extractor created: {type(squarespace_extractor).__name__}")
        assert squarespace_extractor.platform == "squarespace", "Squarespace extractor platform not set correctly"
    except Exception as e:
        print(f"✗ Failed to create Squarespace extractor: {e}")
        return False
    
    return True

def test_extractor_methods():
    """Test that the new extractors have the required methods"""
    print("\nTesting extractor methods...")
    
    test_html = """
    <html>
        <head>
            <title>Test Product</title>
        </head>
        <body>
            <h1>Test Product Title</h1>
            <div class="price">$99.99</div>
            <div class="description">Test product description</div>
        </body>
    </html>
    """
    test_url = "https://example.com/product"
    
    # Test Bigcommerce extractor methods
    bigcommerce_extractor = ExtractorFactory.create_extractor('bigcommerce', test_html, test_url)
    required_methods = [
        'extract_title', 'extract_price', 'extract_description', 
        'extract_images', 'extract_currency', 'extract_rating', 
        'extract_review_count', 'extract_specifications', 'extract_raw_data'
    ]
    
    for method_name in required_methods:
        assert hasattr(bigcommerce_extractor, method_name), f"Bigcommerce extractor missing method: {method_name}"
    
    print("✓ Bigcommerce extractor has all required methods")
    
    # Test Squarespace extractor methods
    squarespace_extractor = ExtractorFactory.create_extractor('squarespace', test_html, test_url)
    
    for method_name in required_methods:
        assert hasattr(squarespace_extractor, method_name), f"Squarespace extractor missing method: {method_name}"
    
    print("✓ Squarespace extractor has all required methods")

def main():
    """Run all tests"""
    print("Testing new Bigcommerce and Squarespace extractors...\n")
    
    try:
        test_extractor_factory()
        test_extractor_creation()
        test_extractor_methods()
        
        print("\n🎉 All tests passed! The new extractors are working correctly.")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 