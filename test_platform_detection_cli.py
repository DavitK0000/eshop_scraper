#!/usr/bin/env python3
"""
Command-line platform detection test script
Usage: python test_platform_detection_cli.py <URL>
"""

import sys
import requests
from urllib.parse import urlparse
from app.services.scraping_service import ScrapingService
from app.scrapers.factory import ScraperFactory


def test_url_based_detection(url):
    """Test URL-based platform detection using ScraperFactory"""
    print("=" * 60)
    print("URL-BASED PLATFORM DETECTION")
    print("=" * 60)
    
    domain = ScraperFactory._extract_domain(url)
    is_supported = ScraperFactory.is_supported_domain(url)
    
    print(f"URL: {url}")
    print(f"Domain: {domain}")
    print(f"Supported Domain: {is_supported}")
    
    if is_supported:
        scraper_class = ScraperFactory._scrapers.get(domain)
        if scraper_class:
            print(f"Detected Scraper: {scraper_class.__name__}")
    else:
        print("Detected Scraper: GenericScraper (unsupported domain)")
    
    print(f"\nTotal Supported Domains: {len(ScraperFactory.get_supported_domains())}")
    print("\nSupported Domains:")
    for domain in sorted(ScraperFactory.get_supported_domains()):
        print(f"  - {domain}")


def test_html_based_detection(url):
    """Test HTML-based platform detection using ScrapingService"""
    print("\n" + "=" * 60)
    print("HTML-BASED PLATFORM DETECTION")
    print("=" * 60)
    
    scraping_service = ScrapingService()
    
    try:
        # Fetch HTML content
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        print(f"Fetching HTML from: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html_content = response.text
        
        print(f"Status Code: {response.status_code}")
        print(f"HTML Length: {len(html_content):,} characters")
        
        # Use the scraping service's platform detection
        platform, confidence, indicators = scraping_service._detect_platform_from_html_safely(html_content, url)
        
        print(f"\nDetected Platform: {platform}")
        print(f"Confidence: {confidence:.3f}")
        
        if indicators:
            print(f"\nDetection Indicators ({len(indicators)}):")
            for i, indicator in enumerate(indicators, 1):
                print(f"  {i}. {indicator}")
        else:
            print("\nNo detection indicators found")
        
        # Show first 500 characters of HTML for debugging
        print(f"\nHTML Preview (first 500 characters):")
        print("-" * 40)
        print(html_content[:500] + "..." if len(html_content) > 500 else html_content)
        
    except Exception as e:
        print(f"Error: {e}")


def main():
    if len(sys.argv) != 2:
        print("Usage: python test_platform_detection_cli.py <URL>")
        print("Example: python test_platform_detection_cli.py https://www.amazon.com/dp/B08N5WRWNW")
        sys.exit(1)
    
    url = sys.argv[1].strip()
    
    # Validate URL format
    try:
        parsed = urlparse(url)
        if not parsed.scheme:
            url = "https://" + url
            print(f"Added https:// to URL: {url}")
    except Exception as e:
        print(f"Invalid URL format: {e}")
        sys.exit(1)
    
    print(f"Testing platform detection for: {url}")
    print()
    
    # Test both detection methods
    test_url_based_detection(url)
    test_html_based_detection(url)
    
    print("\n" + "=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    main() 