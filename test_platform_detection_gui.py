import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import asyncio
import threading
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import re
from typing import Optional, Dict, Any, List, Tuple
import json

# Import the platform detection logic from the scraping service
from app.services.scraping_service import ScrapingService
from app.scrapers.factory import ScraperFactory


class PlatformDetectionGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Platform Detection Test Tool")
        self.root.geometry("800x600")
        
        # Initialize scraping service
        self.scraping_service = ScrapingService()
        
        self.setup_ui()
    
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # URL input section
        ttk.Label(main_frame, text="Enter URL to test platform detection:", font=("Arial", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))
        
        # URL entry
        url_frame = ttk.Frame(main_frame)
        url_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        url_frame.columnconfigure(0, weight=1)
        
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(url_frame, textvariable=self.url_var, font=("Arial", 10))
        self.url_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        # Test button
        self.test_button = ttk.Button(url_frame, text="Test Platform Detection", command=self.test_platform_detection)
        self.test_button.grid(row=0, column=1)
        
        # Progress bar
        self.progress_var = tk.StringVar(value="Ready")
        ttk.Label(main_frame, textvariable=self.progress_var).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))
        
        # Results notebook
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        
        # URL-based detection tab
        self.url_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.url_tab, text="URL-Based Detection")
        self.setup_url_tab()
        
        # HTML-based detection tab
        self.html_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.html_tab, text="HTML-Based Detection")
        self.setup_html_tab()
        
        # Raw HTML tab
        self.raw_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.raw_tab, text="Raw HTML")
        self.setup_raw_tab()
        
        # Bind Enter key to test button
        self.url_entry.bind('<Return>', lambda e: self.test_platform_detection())
    
    def setup_url_tab(self):
        # URL-based detection results
        url_frame = ttk.Frame(self.url_tab, padding="10")
        url_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        url_frame.columnconfigure(0, weight=1)
        url_frame.rowconfigure(1, weight=1)
        
        ttk.Label(url_frame, text="URL-Based Platform Detection Results:", font=("Arial", 11, "bold")).grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        # Results text area
        self.url_results_text = scrolledtext.ScrolledText(url_frame, height=15, width=80, font=("Consolas", 9))
        self.url_results_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    def setup_html_tab(self):
        # HTML-based detection results
        html_frame = ttk.Frame(self.html_tab, padding="10")
        html_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        html_frame.columnconfigure(0, weight=1)
        html_frame.rowconfigure(1, weight=1)
        
        ttk.Label(html_frame, text="HTML-Based Platform Detection Results:", font=("Arial", 11, "bold")).grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        # Results text area
        self.html_results_text = scrolledtext.ScrolledText(html_frame, height=15, width=80, font=("Consolas", 9))
        self.html_results_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    def setup_raw_tab(self):
        # Raw HTML content
        raw_frame = ttk.Frame(self.raw_tab, padding="10")
        raw_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        raw_frame.columnconfigure(0, weight=1)
        raw_frame.rowconfigure(1, weight=1)
        
        ttk.Label(raw_frame, text="Raw HTML Content (first 2000 characters):", font=("Arial", 11, "bold")).grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        # Raw HTML text area
        self.raw_html_text = scrolledtext.ScrolledText(raw_frame, height=15, width=80, font=("Consolas", 9))
        self.raw_html_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    def test_platform_detection(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a URL")
            return
        
        # Validate URL format
        try:
            parsed = urlparse(url)
            if not parsed.scheme:
                url = "https://" + url
                self.url_var.set(url)
        except Exception as e:
            messagebox.showerror("Error", f"Invalid URL format: {e}")
            return
        
        # Disable button and show progress
        self.test_button.config(state='disabled')
        self.progress_var.set("Testing platform detection...")
        
        # Clear previous results
        self.url_results_text.delete(1.0, tk.END)
        self.html_results_text.delete(1.0, tk.END)
        self.raw_html_text.delete(1.0, tk.END)
        
        # Run detection in separate thread
        thread = threading.Thread(target=self.run_detection, args=(url,))
        thread.daemon = True
        thread.start()
    
    def run_detection(self, url):
        try:
            # Test URL-based detection
            url_results = self.test_url_based_detection(url)
            
            # Test HTML-based detection
            html_results, raw_html = self.test_html_based_detection(url)
            
            # Update UI in main thread
            self.root.after(0, self.update_results, url_results, html_results, raw_html)
            
        except Exception as e:
            self.root.after(0, self.show_error, str(e))
        finally:
            self.root.after(0, self.finish_test)
    
    def test_url_based_detection(self, url):
        """Test URL-based platform detection using ScraperFactory"""
        results = {
            'url': url,
            'domain': ScraperFactory._extract_domain(url),
            'is_supported': ScraperFactory.is_supported_domain(url),
            'supported_domains': ScraperFactory.get_supported_domains(),
            'detected_scraper': None
        }
        
        # Check if domain is supported
        if results['is_supported']:
            domain = results['domain']
            scraper_class = ScraperFactory._scrapers.get(domain)
            if scraper_class:
                results['detected_scraper'] = scraper_class.__name__
        
        return results
    
    def test_html_based_detection(self, url):
        """Test HTML-based platform detection using ScrapingService"""
        try:
            # Fetch HTML content
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            html_content = response.text
            
            # Use the scraping service's platform detection
            platform, confidence, indicators = self.scraping_service._detect_platform_from_html_safely(html_content, url)
            
            results = {
                'url': url,
                'detected_platform': platform,
                'confidence': confidence,
                'indicators': indicators,
                'html_length': len(html_content),
                'status_code': response.status_code
            }
            
            return results, html_content
            
        except Exception as e:
            return {
                'url': url,
                'error': str(e),
                'detected_platform': None,
                'confidence': 0.0,
                'indicators': [f"Error fetching HTML: {str(e)}"]
            }, ""
    
    def update_results(self, url_results, html_results, raw_html):
        # Update URL-based results
        url_text = f"URL: {url_results['url']}\n"
        url_text += f"Domain: {url_results['domain']}\n"
        url_text += f"Supported Domain: {url_results['is_supported']}\n"
        
        if url_results['detected_scraper']:
            url_text += f"Detected Scraper: {url_results['detected_scraper']}\n"
        else:
            url_text += "Detected Scraper: GenericScraper (unsupported domain)\n"
        
        url_text += f"\nSupported Domains ({len(url_results['supported_domains'])}):\n"
        for domain in sorted(url_results['supported_domains']):
            url_text += f"  - {domain}\n"
        
        self.url_results_text.insert(tk.END, url_text)
        
        # Update HTML-based results
        html_text = f"URL: {html_results['url']}\n"
        
        if 'error' in html_results:
            html_text += f"Error: {html_results['error']}\n"
        else:
            html_text += f"Detected Platform: {html_results['detected_platform']}\n"
            html_text += f"Confidence: {html_results['confidence']:.3f}\n"
            html_text += f"HTML Length: {html_results['html_length']:,} characters\n"
            html_text += f"Status Code: {html_results['status_code']}\n"
            
            if html_results['indicators']:
                html_text += f"\nDetection Indicators ({len(html_results['indicators'])}):\n"
                for i, indicator in enumerate(html_results['indicators'], 1):
                    html_text += f"  {i}. {indicator}\n"
        
        self.html_results_text.insert(tk.END, html_text)
        
        # Update raw HTML
        if raw_html:
            preview = raw_html[:2000] + "..." if len(raw_html) > 2000 else raw_html
            self.raw_html_text.insert(tk.END, preview)
        else:
            self.raw_html_text.insert(tk.END, "No HTML content available")
    
    def show_error(self, error_msg):
        messagebox.showerror("Error", f"Platform detection failed: {error_msg}")
    
    def finish_test(self):
        self.test_button.config(state='normal')
        self.progress_var.set("Test completed")


def main():
    root = tk.Tk()
    app = PlatformDetectionGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main() 