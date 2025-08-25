#!/usr/bin/env python3
"""
Test script for Altcha captcha handling on Cdiscount
"""

import os
import sys
from dotenv import load_dotenv

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.browser_manager import browser_manager
from app.extractors.cdiscount import CDiscountExtractor
from app.utils.captcha_handler import captcha_handler
from app.services.captcha_solver_service import altcha_local_solver

def test_captcha_detection():
    """Test captcha detection functionality"""
    print("=== Testing Captcha Detection ===")
    
    # Check captcha handler status
    handler_status = captcha_handler.get_captcha_info()
    print(f"Captcha Handler Status: {handler_status}")
    
    # Check local Altcha solver status
    solver_status = altcha_local_solver.get_solver_status()
    print(f"Local Altcha Solver Status: {solver_status}")
    
    print()

def test_cdiscount_scraping_with_captcha():
    """Test CDiscount scraping with captcha handling"""
    print("=== Testing CDiscount Scraping with Captcha Handling ===")
    
    # Example CDiscount product URL
    test_url = "https://www.cdiscount.com/example-product-url"
    
    try:
        # Setup browser
        print("Setting up browser...")
        browser, context, page = browser_manager.setup_browser()
        
        # Navigate to the URL
        print(f"Navigating to: {test_url}")
        page.goto(test_url)
        
        # Check for captcha
        print("Checking for captcha...")
        if captcha_handler.detect_altcha_captcha(page):
            print("Captcha detected! Attempting to solve...")
            
            # Try to solve captcha
            if captcha_handler.solve_altcha_captcha(page, strategy="auto"):
                print("Captcha solved successfully!")
                
                # Now try to extract product information
                print("Extracting product information...")
                extractor = CDiscountExtractor(page.content(), test_url)
                
                # Use the new captcha-handling extraction method
                product_info = extractor.extract_with_captcha_handling()
                
                if product_info:
                    print("Product information extracted successfully!")
                    print(f"Title: {product_info.title}")
                    print(f"Price: {product_info.price}")
                    print(f"Currency: {product_info.currency}")
                else:
                    print("Failed to extract product information")
            else:
                print("Failed to solve captcha")
        else:
            print("No captcha detected")
            
    except Exception as e:
        print(f"Error during testing: {e}")
    
    finally:
        # Cleanup
        browser_manager.cleanup()
        print()

def test_manual_captcha_solving():
    """Test manual captcha solving"""
    print("=== Testing Manual Captcha Solving ===")
    
    test_url = "https://www.cdiscount.com/example-product-url"
    
    try:
        # Setup browser
        print("Setting up browser...")
        browser, context, page = browser_manager.setup_browser()
        
        # Navigate to the URL
        print(f"Navigating to: {test_url}")
        page.goto(test_url)
        
        # Check for captcha
        if captcha_handler.detect_altcha_captcha(page):
            print("Captcha detected! Waiting for manual solving...")
            print("Please solve the captcha manually in the browser window...")
            
            # Wait for manual solving
            if captcha_handler.solve_altcha_captcha(page, strategy="manual"):
                print("Captcha solved manually!")
            else:
                print("Manual solving failed or timed out")
        else:
            print("No captcha detected")
            
    except Exception as e:
        print(f"Error during testing: {e}")
    
    finally:
        # Cleanup
        browser_manager.cleanup()
        print()

def main():
    """Main test function"""
    print("Altcha Captcha Handling Test Suite")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    # Test captcha detection
    test_captcha_detection()
    
    # Test CDiscount scraping with captcha handling
    test_cdiscount_scraping_with_captcha()
    
    # Test manual captcha solving (uncomment if you want to test this)
    # test_manual_captcha_solving()
    
    print("Test suite completed!")

if __name__ == "__main__":
    main()
