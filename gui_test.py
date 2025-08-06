import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import requests
import json
import threading
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ScraperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("E-commerce Scraper API Tester")
        self.root.geometry("1000x700")
        
        # API Configuration
        self.api_base_url = "http://localhost:8000/api/v1"
        
        # Polling state
        self.is_polling = False
        self.polling_task_id = None
        
        self.setup_ui()
        
        # Bind window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def setup_ui(self):
        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(6, weight=1)
        
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
        
        # Test Connection Button
        ttk.Button(config_frame, text="Test Connection", 
                  command=self.test_connection).grid(row=0, column=2, padx=(10, 0))
        
        # URL Input
        ttk.Label(main_frame, text="Product URL:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(main_frame, textvariable=self.url_var, width=60)
        self.url_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        
        # Add Sample URLs Button
        ttk.Button(main_frame, text="Add Sample URLs", 
                  command=self.add_sample_urls).grid(row=2, column=2, padx=(10, 0))
        
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
        
        # Action Buttons Frame
        action_frame = ttk.Frame(main_frame)
        action_frame.grid(row=4, column=0, columnspan=3, pady=10)
        
        # Scrape Button
        self.scrape_button = ttk.Button(action_frame, text="Scrape Product", 
                                       command=self.scrape_product, style="Accent.TButton")
        self.scrape_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Stop Polling Button
        self.stop_button = ttk.Button(action_frame, text="Stop Polling", 
                                     command=self.stop_polling, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT)
        
        # Status Label
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, 
                                font=("Arial", 10, "bold"))
        status_label.grid(row=5, column=0, columnspan=3, pady=(10, 5))
        
        # Results Frame
        results_frame = ttk.LabelFrame(main_frame, text="Results", padding="10")
        results_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Results Text Area
        self.results_text = scrolledtext.ScrolledText(results_frame, height=15, width=80, 
                                                     font=("Consolas", 9))
        self.results_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Add sample URLs
        self.add_sample_urls()
    
    def add_sample_urls(self):
        """Add sample URLs for testing"""
        sample_urls = [
            "https://www.amazon.com/dp/B08N5WRWNW",  # Amazon product
            "https://www.ebay.com/itm/123456789",    # eBay product
            "https://www.jd.com/product/123456",     # JD.com product
        ]
        
        if not self.url_var.get():
            self.url_var.set(sample_urls[0])
    
    def scrape_product(self):
        """Start scraping process"""
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a URL")
            return
        
        # Validate URL format
        if not url.startswith(('http://', 'https://')):
            url = "https://" + url
            self.url_var.set(url)
        
        # Start scraping in background thread
        threading.Thread(target=self._scrape_product_thread, args=(url,), daemon=True).start()
    
    def _scrape_product_thread(self, url):
        """Scrape product in background thread"""
        try:
            self.root.after(0, lambda: self.status_var.set("Starting scraping..."))
            self.root.after(0, lambda: self.scrape_button.config(state=tk.DISABLED))
            
            # Prepare request data
            request_data = {
                "url": url,
                "force_refresh": self.force_refresh_var.get(),
                "block_images": self.block_images_var.get()
            }
            
            # Add optional parameters
            if self.proxy_var.get().strip():
                request_data["proxy"] = self.proxy_var.get().strip()
            if self.user_agent_var.get().strip():
                request_data["user_agent"] = self.user_agent_var.get().strip()
            
            # Make API request
            api_url = f"{self.endpoint_var.get()}/scrape"
            self.root.after(0, lambda: self.status_var.set("Sending request to API..."))
            
            response = requests.post(api_url, json=request_data, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Check if task was created successfully
            if data.get('status') == 'pending':
                task_id = data.get('task_id')
                self.root.after(0, lambda: self.status_var.set(f"Task created: {task_id}"))
                self.root.after(0, lambda: self.results_text.insert(tk.END, f"Task created: {task_id}\n"))
                
                # Start polling for results
                self.start_polling(task_id)
            else:
                self.root.after(0, lambda: self.status_var.set("Unexpected response"))
                self.root.after(0, lambda: self.results_text.insert(tk.END, f"Response: {json.dumps(data, indent=2)}\n"))
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            self.root.after(0, lambda: self.status_var.set("Request failed"))
            self.root.after(0, lambda: self.results_text.insert(tk.END, f"Error: {error_msg}\n"))
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.root.after(0, lambda: self.status_var.set("Error occurred"))
            self.root.after(0, lambda: self.results_text.insert(tk.END, f"Error: {error_msg}\n"))
        finally:
            self.root.after(0, lambda: self.scrape_button.config(state=tk.NORMAL))
    
    def start_polling(self, task_id):
        """Start polling for task results"""
        self.polling_task_id = task_id
        self.is_polling = True
        self.root.after(0, lambda: self.stop_button.config(state=tk.NORMAL))
        
        # Start polling in background thread
        threading.Thread(target=self._poll_task_status, args=(task_id,), daemon=True).start()
    
    def _poll_task_status(self, task_id):
        """Poll task status in background thread"""
        start_time = datetime.now()
        max_wait_time = 300  # 5 minutes
        
        while self.is_polling:
            try:
                # Check if we've been waiting too long
                if (datetime.now() - start_time).seconds > max_wait_time:
                    self.root.after(0, self._handle_polling_timeout)
                    break
                
                # Get task status
                api_url = f"{self.endpoint_var.get()}/tasks/{task_id}"
                response = requests.get(api_url, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                status = data.get('status')
                
                self.root.after(0, lambda: self.status_var.set(f"Task {task_id}: {status}"))
                
                if status == 'completed':
                    # Task completed successfully
                    self.root.after(0, lambda: self._handle_scrape_response(data))
                    break
                elif status == 'failed':
                    # Task failed
                    error_msg = data.get('error', 'Unknown error')
                    self.root.after(0, lambda: self._handle_task_failure(error_msg))
                    break
                elif status in ['pending', 'running']:
                    # Task still in progress, wait and try again
                    import time
                    time.sleep(2)
                else:
                    # Unknown status
                    self.root.after(0, lambda: self.status_var.set(f"Unknown status: {status}"))
                    break
                    
            except requests.exceptions.RequestException as e:
                error_msg = f"Polling request failed: {str(e)}"
                self.root.after(0, lambda: self._handle_task_failure(error_msg))
                break
            except Exception as e:
                error_msg = f"Polling error: {str(e)}"
                self.root.after(0, lambda: self._handle_task_failure(error_msg))
                break
        
        # Stop polling
        self.is_polling = False
        self.root.after(0, lambda: self.stop_button.config(state=tk.DISABLED))
    
    def stop_polling(self):
        """Stop polling for task results"""
        self.is_polling = False
        self.root.after(0, lambda: self.stop_button.config(state=tk.DISABLED))
        self.root.after(0, lambda: self.status_var.set("Polling stopped"))
    
    def _handle_scrape_response(self, data):
        """Handle successful scrape response"""
        self.status_var.set("Scraping completed successfully")
        
        # Display results
        self.results_text.insert(tk.END, "\n" + "="*50 + "\n")
        self.results_text.insert(tk.END, "SCRAPING COMPLETED\n")
        self.results_text.insert(tk.END, "="*50 + "\n")
        
        # Display basic info
        self.results_text.insert(tk.END, f"Task ID: {data.get('task_id')}\n")
        self.results_text.insert(tk.END, f"URL: {data.get('url')}\n")
        self.results_text.insert(tk.END, f"Status: {data.get('status')}\n")
        self.results_text.insert(tk.END, f"Platform: {data.get('detected_platform', 'Unknown')}\n")
        self.results_text.insert(tk.END, f"Confidence: {data.get('platform_confidence', 0):.2f}\n")
        
        # Display product info if available
        product_info = data.get('product_info')
        if product_info:
            self.results_text.insert(tk.END, "\n" + "-"*30 + "\n")
            self.results_text.insert(tk.END, "PRODUCT INFORMATION\n")
            self.results_text.insert(tk.END, "-"*30 + "\n")
            
            if product_info.get('title'):
                self.results_text.insert(tk.END, f"Title: {product_info['title']}\n")
            if product_info.get('price'):
                self.results_text.insert(tk.END, f"Price: ${product_info['price']}\n")
            if product_info.get('description'):
                desc = product_info['description'][:200] + "..." if len(product_info['description']) > 200 else product_info['description']
                self.results_text.insert(tk.END, f"Description: {desc}\n")
            if product_info.get('images'):
                self.results_text.insert(tk.END, f"Images: {len(product_info['images'])} found\n")
        
        # Display full response for debugging
        self.results_text.insert(tk.END, "\n" + "-"*30 + "\n")
        self.results_text.insert(tk.END, "FULL RESPONSE\n")
        self.results_text.insert(tk.END, "-"*30 + "\n")
        self.results_text.insert(tk.END, json.dumps(data, indent=2))
        self.results_text.insert(tk.END, "\n")
        
        # Scroll to top
        self.results_text.see(tk.END)
    
    def _handle_task_failure(self, error_msg):
        """Handle task failure"""
        self.status_var.set("Task failed")
        self.results_text.insert(tk.END, f"\nERROR: {error_msg}\n")
        self.results_text.see(tk.END)
    
    def _handle_polling_timeout(self):
        """Handle polling timeout"""
        self.status_var.set("Polling timeout")
        self.results_text.insert(tk.END, "\nTIMEOUT: Task took too long to complete\n")
        self.results_text.see(tk.END)
    
    def test_connection(self):
        """Test API connection"""
        threading.Thread(target=self._test_connection_thread, daemon=True).start()
    
    def _test_connection_thread(self):
        """Test connection in background thread"""
        try:
            self.root.after(0, lambda: self.status_var.set("Testing connection..."))
            
            api_url = f"{self.endpoint_var.get()}/health"
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            status = data.get('status', 'unknown')
            
            if status == 'healthy':
                self.root.after(0, lambda: self.status_var.set("Connection successful"))
                self.root.after(0, lambda: messagebox.showinfo("Success", "API connection successful!"))
            else:
                self.root.after(0, lambda: self.status_var.set("API unhealthy"))
                self.root.after(0, lambda: messagebox.showwarning("Warning", f"API status: {status}"))
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Connection failed: {str(e)}"
            self.root.after(0, lambda: self.status_var.set("Connection failed"))
            self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.root.after(0, lambda: self.status_var.set("Connection error"))
            self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
    
    def on_closing(self):
        """Handle window closing"""
        if self.is_polling:
            if messagebox.askokcancel("Quit", "A scraping task is still running. Do you want to quit anyway?"):
                self.is_polling = False
                self.root.destroy()
        else:
            self.root.destroy()


def main():
    root = tk.Tk()
    app = ScraperGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main() 