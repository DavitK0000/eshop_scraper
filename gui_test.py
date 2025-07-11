import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import requests
import json
import threading
from datetime import datetime
import webbrowser

class ScraperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("E-commerce Scraper API Tester")
        self.root.geometry("1200x800")
        
        # API Configuration
        self.api_base_url = "http://localhost:8000/api/v1"
        self.api_key = None
        
        self.setup_ui()
        
    def setup_ui(self):
        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(7, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="E-commerce Scraper API Tester", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # API Configuration Frame
        config_frame = ttk.LabelFrame(main_frame, text="API Configuration", padding="10")
        config_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        config_frame.columnconfigure(1, weight=1)
        
        # API Endpoint Input
        ttk.Label(config_frame, text="API Endpoint:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.endpoint_var = tk.StringVar(value="http://localhost:8000/api/v1")
        self.endpoint_entry = ttk.Entry(config_frame, textvariable=self.endpoint_var, width=60)
        self.endpoint_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        
        # API Key Input
        ttk.Label(config_frame, text="API Key (optional):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(config_frame, textvariable=self.api_key_var, width=60, show="*")
        self.api_key_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        
        # Show/Hide API Key Button
        self.show_key_var = tk.BooleanVar()
        ttk.Checkbutton(config_frame, text="Show Key", 
                       variable=self.show_key_var, 
                       command=self.toggle_api_key_visibility).grid(row=1, column=2, padx=(10, 0))
        
        # URL Input
        ttk.Label(main_frame, text="Product URL:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(main_frame, textvariable=self.url_var, width=60)
        self.url_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        
        # Options Frame
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding="10")
        options_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        options_frame.columnconfigure(1, weight=1)
        
        # Force Refresh Checkbox
        self.force_refresh_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Force Refresh", 
                       variable=self.force_refresh_var).grid(row=0, column=0, sticky=tk.W)
        
        # Block Images Checkbox
        self.block_images_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Block Images", 
                       variable=self.block_images_var).grid(row=1, column=0, sticky=tk.W)
        
        # Proxy Input
        ttk.Label(options_frame, text="Proxy (optional):").grid(row=0, column=1, sticky=tk.W, padx=(20, 5))
        self.proxy_var = tk.StringVar()
        ttk.Entry(options_frame, textvariable=self.proxy_var, width=30).grid(row=0, column=2, sticky=tk.W)
        
        # User Agent Input
        ttk.Label(options_frame, text="User Agent (optional):").grid(row=1, column=1, sticky=tk.W, padx=(20, 5), pady=(10, 0))
        self.user_agent_var = tk.StringVar()
        ttk.Entry(options_frame, textvariable=self.user_agent_var, width=50).grid(row=1, column=2, sticky=tk.W, pady=(10, 0))
        
        # Buttons Frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=4, column=0, columnspan=3, pady=10)
        
        # Scrape Button
        self.scrape_button = ttk.Button(buttons_frame, text="Scrape Product", 
                                       command=self.scrape_product)
        self.scrape_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Health Check Button
        ttk.Button(buttons_frame, text="Health Check", 
                  command=self.health_check).pack(side=tk.LEFT, padx=(0, 10))
        
        # Test Connection Button
        ttk.Button(buttons_frame, text="Test Connection", 
                  command=self.test_connection).pack(side=tk.LEFT, padx=(0, 10))
        
        # Security Buttons Frame
        security_buttons_frame = ttk.Frame(main_frame)
        security_buttons_frame.grid(row=5, column=0, columnspan=3, pady=5)
        
        # Security Stats Button
        ttk.Button(security_buttons_frame, text="Security Stats", 
                  command=self.security_stats).pack(side=tk.LEFT, padx=(0, 10))
        
        # Security Status Button
        ttk.Button(security_buttons_frame, text="Security Status", 
                  command=self.security_status).pack(side=tk.LEFT, padx=(0, 10))
        
        # Cache Stats Button
        ttk.Button(security_buttons_frame, text="Cache Stats", 
                  command=self.cache_stats).pack(side=tk.LEFT, padx=(0, 10))
        
        # Clear Cache Button
        ttk.Button(security_buttons_frame, text="Clear Cache", 
                  command=self.clear_cache).pack(side=tk.LEFT, padx=(0, 10))
        
        # Progress Bar
        self.progress_var = tk.StringVar(value="Ready")
        ttk.Label(main_frame, textvariable=self.progress_var).grid(row=6, column=0, columnspan=3, pady=5)
        
        # Results Frame
        results_frame = ttk.LabelFrame(main_frame, text="Results", padding="10")
        results_frame.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Results Text Area
        self.results_text = scrolledtext.ScrolledText(results_frame, height=20, width=100)
        self.results_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Status Bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=8, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # Add some sample URLs
        self.add_sample_urls()
        
    def toggle_api_key_visibility(self):
        """Toggle API key visibility"""
        if self.show_key_var.get():
            self.api_key_entry.config(show="")
        else:
            self.api_key_entry.config(show="*")
    
    def get_headers(self):
        """Get headers for API requests including authentication"""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'E-commerce-Scraper-GUI/1.0'
        }
        
        # Add API key if provided
        api_key = self.api_key_var.get().strip()
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        
        return headers
    
    def add_sample_urls(self):
        """Add sample URLs for testing"""
        sample_urls = [
            "https://www.amazon.com/dp/B08N5WRWNW",  # Amazon product
            "https://www.ebay.com/itm/123456789",    # eBay product (placeholder)
            "https://www.jd.com/product/123456.html" # JD.com product (placeholder)
        ]
        
        # Create a dropdown for sample URLs
        sample_frame = ttk.Frame(self.root)
        sample_frame.grid(row=2, column=1, sticky=tk.E, padx=(0, 10))
        
        ttk.Label(sample_frame, text="Sample URLs:").pack(side=tk.LEFT)
        sample_combo = ttk.Combobox(sample_frame, values=sample_urls, width=40)
        sample_combo.pack(side=tk.LEFT, padx=(5, 0))
        sample_combo.bind("<<ComboboxSelected>>", lambda e: self.url_var.set(sample_combo.get()))
        
    def scrape_product(self):
        """Scrape product from URL"""
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a URL")
            return
        
        # Disable button during scraping
        self.scrape_button.config(state='disabled')
        self.progress_var.set("Scraping in progress...")
        self.status_var.set("Scraping...")
        
        # Run scraping in separate thread
        thread = threading.Thread(target=self._scrape_product_thread, args=(url,))
        thread.daemon = True
        thread.start()
        
    def _scrape_product_thread(self, url):
        """Scrape product in separate thread"""
        try:
            # Prepare request data as JSON body
            request_data = {
                'url': url,
                'force_refresh': self.force_refresh_var.get(),
                'block_images': self.block_images_var.get()
            }
            
            if self.proxy_var.get().strip():
                request_data['proxy'] = self.proxy_var.get().strip()
            
            if self.user_agent_var.get().strip():
                request_data['user_agent'] = self.user_agent_var.get().strip()
            
            # Make API request using POST method
            api_base_url = self.endpoint_var.get().strip()
            if not api_base_url:
                api_base_url = "http://localhost:8000/api/v1"
            
            headers = self.get_headers()
            
            response = requests.post(f"{api_base_url}/scrape", json=request_data, headers=headers, timeout=60)
            
            # Update UI in main thread
            self.root.after(0, self._handle_scrape_response, response)
            
        except Exception as e:
            self.root.after(0, self._handle_scrape_error, str(e))
    
    def _handle_scrape_response(self, response):
        """Handle scraping response"""
        self.scrape_button.config(state='normal')
        
        if response.status_code == 200:
            data = response.json()
            self.display_results(data)
            self.progress_var.set("Scraping completed successfully")
            self.status_var.set(f"Success - {datetime.now().strftime('%H:%M:%S')}")
        elif response.status_code == 401:
            error_msg = "Authentication failed. Please check your API key."
            self.progress_var.set("Authentication failed")
            self.status_var.set(f"Auth Error - {datetime.now().strftime('%H:%M:%S')}")
            messagebox.showerror("Authentication Error", error_msg)
        elif response.status_code == 403:
            error_msg = "Access denied. You may have exceeded rate limits or your IP is blocked."
            self.progress_var.set("Access denied")
            self.status_var.set(f"Access Denied - {datetime.now().strftime('%H:%M:%S')}")
            messagebox.showerror("Access Denied", error_msg)
        elif response.status_code == 429:
            error_msg = "Rate limit exceeded. Please wait before making another request."
            self.progress_var.set("Rate limit exceeded")
            self.status_var.set(f"Rate Limited - {datetime.now().strftime('%H:%M:%S')}")
            messagebox.showerror("Rate Limit Exceeded", error_msg)
        else:
            # Try to get detailed error information
            try:
                error_detail = response.json()
                if 'detail' in error_detail:
                    error_msg = f"Error {response.status_code}: {error_detail['detail']}"
                else:
                    error_msg = f"Error {response.status_code}: {response.text}"
            except:
                error_msg = f"Error {response.status_code}: {response.text}"
            
            self.progress_var.set("Scraping failed")
            self.status_var.set(f"Error - {datetime.now().strftime('%H:%M:%S')}")
            messagebox.showerror("Error", error_msg)
    
    def _handle_scrape_error(self, error_msg):
        """Handle scraping error"""
        self.scrape_button.config(state='normal')
        self.progress_var.set("Scraping failed")
        self.status_var.set(f"Error - {datetime.now().strftime('%H:%M:%S')}")
        messagebox.showerror("Error", f"Request failed: {error_msg}")
    
    def display_results(self, data):
        """Display scraping results"""
        self.results_text.delete(1.0, tk.END)
        
        # Format the JSON response nicely
        formatted_json = json.dumps(data, indent=2, default=str)
        self.results_text.insert(tk.END, formatted_json)
        
        # Highlight important fields
        self.highlight_json()
    
    def highlight_json(self):
        """Highlight important JSON fields"""
        # This is a simple highlighting - you could make it more sophisticated
        content = self.results_text.get(1.0, tk.END)
        
        # Highlight status
        if '"status": "completed"' in content:
            self.results_text.tag_configure("success", foreground="green")
            start = "1.0"
            while True:
                pos = self.results_text.search('"status": "completed"', start, tk.END)
                if not pos:
                    break
                end = f"{pos}+18c"
                self.results_text.tag_add("success", pos, end)
                start = end
        
        if '"status": "failed"' in content:
            self.results_text.tag_configure("error", foreground="red")
            start = "1.0"
            while True:
                pos = self.results_text.search('"status": "failed"', start, tk.END)
                if not pos:
                    break
                end = f"{pos}+15c"
                self.results_text.tag_add("error", pos, end)
                start = end
    
    def test_connection(self):
        """Test basic API connection and endpoints"""
        try:
            api_base_url = self.endpoint_var.get().strip()
            if not api_base_url:
                api_base_url = "http://localhost:8000/api/v1"
            
            headers = self.get_headers()
            test_results = []
            
            # Test 1: Root endpoint
            try:
                response = requests.get(api_base_url.replace("/api/v1", ""), timeout=5)
                test_results.append(f"Root endpoint: {response.status_code}")
            except Exception as e:
                test_results.append(f"Root endpoint: Failed - {e}")
            
            # Test 2: Health endpoint
            try:
                response = requests.get(f"{api_base_url}/health", headers=headers, timeout=5)
                test_results.append(f"Health endpoint: {response.status_code}")
                if response.status_code == 200:
                    health_data = response.json()
                    test_results.append(f"Health data: {health_data}")
            except Exception as e:
                test_results.append(f"Health endpoint: Failed - {e}")
            
            # Test 3: Simple POST request with minimal data
            try:
                test_data = {
                    'url': 'https://www.amazon.com/dp/B08N5WRWNW',
                    'force_refresh': True,
                }
                response = requests.post(f"{api_base_url}/scrape", json=test_data, headers=headers, timeout=30)
                test_results.append(f"Scrape endpoint: {response.status_code}")
                
                if response.status_code == 200:
                    scrape_data = response.json()
                    test_results.append(f"Scrape successful: {scrape_data.get('status', 'unknown')}")
                    self.display_results(scrape_data)
                    self.status_var.set(f"Connection test successful - {datetime.now().strftime('%H:%M:%S')}")
                    return
                else:
                    error_detail = response.text
                    test_results.append(f"Scrape failed: {error_detail}")
                    
            except Exception as e:
                test_results.append(f"Scrape endpoint: Failed - {e}")
            
            # Display test results
            self.display_results({
                "test_results": test_results,
                "error": "Some tests failed",
                "recommendation": "Try running the API with 'start_without_redis.bat' for testing"
            })
            self.status_var.set(f"Connection test completed - {datetime.now().strftime('%H:%M:%S')}")
                
        except Exception as e:
            error_msg = f"Connection test failed: {str(e)}"
            self.display_results({
                "error": error_msg,
                "recommendation": "Check if the API server is running and try 'start_without_redis.bat'"
            })
            self.status_var.set(f"Connection test failed - {datetime.now().strftime('%H:%M:%S')}")
    
    def health_check(self):
        """Check API health"""
        try:
            api_base_url = self.endpoint_var.get().strip()
            if not api_base_url:
                api_base_url = "http://localhost:8000/api/v1"
            headers = self.get_headers()
            response = requests.get(f"{api_base_url}/health", headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.display_results(data)
                self.status_var.set(f"Health check successful - {datetime.now().strftime('%H:%M:%S')}")
            else:
                messagebox.showerror("Error", f"Health check failed: {response.status_code}")
        except Exception as e:
            messagebox.showerror("Error", f"Health check failed: {str(e)}")
    
    def security_stats(self):
        """Get security statistics"""
        try:
            api_base_url = self.endpoint_var.get().strip()
            if not api_base_url:
                api_base_url = "http://localhost:8000/api/v1"
            headers = self.get_headers()
            response = requests.get(f"{api_base_url}/security/stats", headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.display_results(data)
                self.status_var.set(f"Security stats retrieved - {datetime.now().strftime('%H:%M:%S')}")
            else:
                messagebox.showerror("Error", f"Failed to get security stats: {response.status_code}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get security stats: {str(e)}")
    
    def security_status(self):
        """Get security status"""
        try:
            api_base_url = self.endpoint_var.get().strip()
            if not api_base_url:
                api_base_url = "http://localhost:8000/api/v1"
            headers = self.get_headers()
            response = requests.get(f"{api_base_url}/security/status", headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.display_results(data)
                self.status_var.set(f"Security status retrieved - {datetime.now().strftime('%H:%M:%S')}")
            else:
                messagebox.showerror("Error", f"Failed to get security status: {response.status_code}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get security status: {str(e)}")
    
    def cache_stats(self):
        """Get cache statistics"""
        try:
            api_base_url = self.endpoint_var.get().strip()
            if not api_base_url:
                api_base_url = "http://localhost:8000/api/v1"
            headers = self.get_headers()
            response = requests.get(f"{api_base_url}/cache/stats", headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.display_results(data)
                self.status_var.set(f"Cache stats retrieved - {datetime.now().strftime('%H:%M:%S')}")
            else:
                messagebox.showerror("Error", f"Failed to get cache stats: {response.status_code}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get cache stats: {str(e)}")
    
    def clear_cache(self):
        """Clear all cache"""
        if messagebox.askyesno("Confirm", "Are you sure you want to clear all cache?"):
            try:
                api_base_url = self.endpoint_var.get().strip()
                if not api_base_url:
                    api_base_url = "http://localhost:8000/api/v1"
                headers = self.get_headers()
                response = requests.delete(f"{api_base_url}/cache", headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    self.display_results(data)
                    self.status_var.set(f"Cache cleared - {datetime.now().strftime('%H:%M:%S')}")
                else:
                    messagebox.showerror("Error", f"Failed to clear cache: {response.status_code}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear cache: {str(e)}")

def main():
    root = tk.Tk()
    app = ScraperGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 