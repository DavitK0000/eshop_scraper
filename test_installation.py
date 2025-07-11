#!/usr/bin/env python3
"""
Test script to verify the installation of the E-commerce Scraper API
"""

import sys
import importlib
import subprocess
from pathlib import Path

def test_import(module_name, package_name=None):
    """Test if a module can be imported"""
    try:
        importlib.import_module(module_name)
        print(f"✓ {package_name or module_name}")
        return True
    except ImportError as e:
        print(f"✗ {package_name or module_name}: {e}")
        return False

def test_playwright():
    """Test Playwright installation"""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        print("✓ Playwright browsers")
        return True
    except Exception as e:
        print(f"✗ Playwright browsers: {e}")
        return False

def test_redis():
    """Test Redis connection"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0, socket_connect_timeout=5)
        r.ping()
        print("✓ Redis connection")
        return True
    except Exception as e:
        print(f"✗ Redis connection: {e}")
        return False

def test_app_modules():
    """Test if app modules can be imported"""
    modules = [
        ('app.config', 'App Config'),
        ('app.models', 'App Models'),
        ('app.utils', 'App Utils'),
        ('app.scrapers.base', 'Base Scraper'),
        ('app.scrapers.factory', 'Scraper Factory'),
        ('app.services.cache_service', 'Cache Service'),
        ('app.services.scraping_service', 'Scraping Service'),
        ('app.api.routes', 'API Routes'),
        ('app.main', 'Main App'),
    ]
    
    results = []
    for module, name in modules:
        results.append(test_import(module, name))
    
    return all(results)

def main():
    print("E-commerce Scraper API - Installation Test")
    print("=" * 50)
    
    # Test Python version
    python_version = sys.version_info
    if python_version >= (3, 8):
        print(f"✓ Python {python_version.major}.{python_version.minor}.{python_version.micro}")
    else:
        print(f"✗ Python version {python_version.major}.{python_version.minor}.{python_version.micro} (requires 3.8+)")
        return False
    
    print("\nTesting dependencies:")
    print("-" * 30)
    
    # Test core dependencies
    dependencies = [
        ('fastapi', 'FastAPI'),
        ('uvicorn', 'Uvicorn'),
        ('playwright', 'Playwright'),
        ('beautifulsoup4', 'BeautifulSoup4'),
        ('requests', 'Requests'),
        ('redis', 'Redis'),
        ('pydantic', 'Pydantic'),
        ('fake_useragent', 'Fake UserAgent'),
    ]
    
    dep_results = []
    for module, name in dependencies:
        dep_results.append(test_import(module, name))
    
    print("\nTesting Playwright browsers:")
    print("-" * 30)
    playwright_ok = test_playwright()
    
    print("\nTesting Redis connection:")
    print("-" * 30)
    redis_ok = test_redis()
    
    print("\nTesting app modules:")
    print("-" * 30)
    app_modules_ok = test_app_modules()
    
    print("\n" + "=" * 50)
    
    # Summary
    all_tests = dep_results + [playwright_ok, redis_ok, app_modules_ok]
    passed = sum(all_tests)
    total = len(all_tests)
    
    print(f"Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed! Installation is complete.")
        print("\nNext steps:")
        print("1. Start the API server: python -m app.main")
        print("2. Or use the batch file: start_server.bat")
        print("3. Test with GUI: python gui_test.py")
        print("4. Or use the batch file: start_gui.bat")
        return True
    else:
        print("❌ Some tests failed. Please check the errors above.")
        print("\nTroubleshooting:")
        print("1. Install missing dependencies: pip install -r requirements.txt")
        print("2. Install Playwright browsers: playwright install")
        print("3. Start Redis server")
        print("4. Check your Python environment")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 