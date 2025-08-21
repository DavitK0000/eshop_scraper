import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import requests
import json
import threading
import logging
from datetime import datetime
import urllib3
import ssl

# Disable SSL warnings for development
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
        
        # Create session with SSL verification disabled for development
        self.session = requests.Session()
        self.session.verify = False
        
        self.setup_ui()
        
        # Bind window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def validate_endpoint_url(self, url):
        """Validate the endpoint URL format and return (url, error) tuple"""
        if not url or not url.strip():
            return None, "Endpoint URL cannot be empty"
        
        url = url.strip()
        
        # Check if URL starts with http:// or https://
        if not url.startswith(('http://', 'https://')):
            return None, "Endpoint URL must start with http:// or https://"
        
        # Check if URL has a valid format
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if not parsed.netloc:
                return None, "Invalid URL format - missing hostname"
            return url, None
        except Exception:
            return None, "Invalid URL format"
    
    def setup_ui(self):
        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(11, weight=1)
        
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
        
        # SSL Verification Toggle
        self.ssl_verify_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(config_frame, text="Verify SSL Certificates", 
                       variable=self.ssl_verify_var).grid(row=1, column=0, sticky=tk.W, pady=5)
        
        # URL Input
        ttk.Label(main_frame, text="Product URL:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(main_frame, textvariable=self.url_var, width=60)
        self.url_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        
        # Add Sample URLs Button
        ttk.Button(main_frame, text="Add Sample URLs", 
                  command=self.add_sample_urls).grid(row=2, column=2, padx=(10, 0))
        
        # User ID Input (Required)
        ttk.Label(main_frame, text="User ID (Required):", foreground="red").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.user_id_var = tk.StringVar()
        self.user_id_entry = ttk.Entry(main_frame, textvariable=self.user_id_var, width=60)
        self.user_id_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        
        # Add Sample User ID Button
        ttk.Button(main_frame, text="Add Sample User ID", 
                  command=self.add_sample_user_id).grid(row=3, column=2, padx=(10, 0))
        
        # Session ID Input (Optional)
        ttk.Label(main_frame, text="Session ID (Optional):").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.session_id_var = tk.StringVar()
        self.session_id_entry = ttk.Entry(main_frame, textvariable=self.session_id_var, width=60)
        self.session_id_entry.grid(row=4, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        
        # Generate Session ID Button
        ttk.Button(main_frame, text="Generate Session ID", 
                  command=self.generate_session_id).grid(row=4, column=2, padx=(10, 0))
        
        # Options Frame
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding="10")
        options_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        options_frame.columnconfigure(1, weight=1)
        
        # Force Refresh Checkbox
        self.force_refresh_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Force Refresh", 
                       variable=self.force_refresh_var).grid(row=0, column=0, sticky=tk.W)
        
        # Block Images Checkbox
        self.block_images_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Block Images", 
                       variable=self.block_images_var).grid(row=1, column=0, sticky=tk.W)
        
        # Target Language Input
        ttk.Label(options_frame, text="Target Language:").grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
        self.target_language_var = tk.StringVar(value="en")
        target_language_combo = ttk.Combobox(options_frame, textvariable=self.target_language_var, 
                                            values=["en", "es", "fr", "de", "it", "pt", "ja", "ko", "zh"], 
                                            width=10, state="readonly")
        target_language_combo.grid(row=2, column=1, sticky=tk.W, padx=(20, 0), pady=(10, 0))
        
        # Priority Selection
        ttk.Label(options_frame, text="Priority:").grid(row=2, column=1, sticky=tk.W, padx=(200, 0), pady=(10, 0))
        self.priority_var = tk.StringVar(value="normal")
        priority_combo = ttk.Combobox(options_frame, textvariable=self.priority_var, 
                                     values=["low", "normal", "high", "urgent"], 
                                     width=10, state="readonly")
        priority_combo.grid(row=2, column=2, sticky=tk.W, pady=(10, 0))
        
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
        action_frame.grid(row=7, column=0, columnspan=3, pady=10)
        
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
        status_label.grid(row=8, column=0, columnspan=3, pady=(10, 5))
        
        # Product ID Display Frame
        product_id_frame = ttk.LabelFrame(main_frame, text="Supabase Product ID", padding="10")
        product_id_frame.grid(row=9, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        product_id_frame.columnconfigure(1, weight=1)
        
        # Product ID Label
        ttk.Label(product_id_frame, text="Product ID:").grid(row=0, column=0, sticky=tk.W)
        self.product_id_var = tk.StringVar(value="Not available yet")
        product_id_label = ttk.Label(product_id_frame, textvariable=self.product_id_var, 
                                    font=("Consolas", 9), foreground="blue")
        product_id_label.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))
        
        # Copy Product ID Button
        self.copy_product_id_button = ttk.Button(product_id_frame, text="Copy ID", 
                                               command=self.copy_product_id, state=tk.DISABLED)
        self.copy_product_id_button.grid(row=0, column=2, padx=(10, 0))
        
        # Results Frame
        results_frame = ttk.LabelFrame(main_frame, text="Results", padding="10")
        results_frame.grid(row=10, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Results Text Area
        self.results_text = scrolledtext.ScrolledText(results_frame, height=15, width=80, 
                                                     font=("Consolas", 9))
        self.results_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Video Generation Frame
        video_frame = ttk.LabelFrame(main_frame, text="Video Generation Testing", padding="10")
        video_frame.grid(row=11, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        video_frame.columnconfigure(1, weight=1)
        
        # Scene ID Input
        ttk.Label(video_frame, text="Scene ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.scene_id_var = tk.StringVar()
        self.scene_id_entry = ttk.Entry(video_frame, textvariable=self.scene_id_var, width=60)
        self.scene_id_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        
        # Add Sample Scene ID Button
        ttk.Button(video_frame, text="Add Sample Scene ID", 
                  command=self.add_sample_scene_id).grid(row=0, column=2, padx=(10, 0))
        
        # Video Generation Button
        self.generate_video_button = ttk.Button(video_frame, text="Generate Video", 
                                              command=self.generate_video, style="Accent.TButton")
        self.generate_video_button.grid(row=1, column=0, columnspan=3, pady=(10, 0))
        
        # Video Generation Status
        self.video_status_var = tk.StringVar(value="Ready for video generation")
        video_status_label = ttk.Label(video_frame, textvariable=self.video_status_var, 
                                     font=("Arial", 10, "bold"))
        video_status_label.grid(row=2, column=0, columnspan=3, pady=(5, 0))
        
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
    
    def add_sample_user_id(self):
        """Add a sample user ID for testing"""
        import uuid
        sample_user_id = str(uuid.uuid4())
        self.user_id_var.set(sample_user_id)
    
    def generate_session_id(self):
        """Generate a random session ID"""
        import uuid
        self.session_id_var.set(str(uuid.uuid4()))
    
    def copy_product_id(self):
        """Copy the product ID to clipboard"""
        product_id = self.product_id_var.get()
        if product_id and product_id != "Not available yet":
            self.root.clipboard_clear()
            self.root.clipboard_append(product_id)
            messagebox.showinfo("Copied", f"Product ID copied to clipboard: {product_id}")
    
    def validate_uuid(self, uuid_string):
        """Validate if a string is a valid UUID"""
        try:
            import uuid
            uuid.UUID(uuid_string)
            return True
        except ValueError:
            return False
    
    def scrape_product(self):
        """Start scraping process"""
        url = self.url_var.get().strip()
        user_id = self.user_id_var.get().strip()
        
        if not url:
            messagebox.showerror("Error", "Please enter a URL")
            return
        if not user_id:
            messagebox.showerror("Error", "User ID is required")
            return
        if not self.validate_uuid(user_id):
            messagebox.showerror("Error", "User ID must be a valid UUID format")
            return
        
        # Reset product ID display
        self.product_id_var.set("Processing...")
        self.copy_product_id_button.config(state=tk.DISABLED)
        
        # Validate URL format
        if not url.startswith(('http://', 'https://')):
            url = "https://" + url
            self.url_var.set(url)
        
        # Start scraping in background thread
        threading.Thread(target=self._scrape_product_thread, args=(url, user_id), daemon=True).start()
    
    def _scrape_product_thread(self, url, user_id):
        """Scrape product in background thread"""
        try:
            self.root.after(0, lambda: self.status_var.set("Starting scraping..."))
            self.root.after(0, lambda: self.scrape_button.config(state=tk.DISABLED))
            
            # Validate endpoint URL
            endpoint_url, error = self.validate_endpoint_url(self.endpoint_var.get())
            if error:
                raise Exception(f"Invalid endpoint URL: {error}")
            
            # Prepare request data
            request_data = {
                "url": url,
                "user_id": user_id, # Add user_id to request data
                "force_refresh": self.force_refresh_var.get(),
                "block_images": self.block_images_var.get(),
                "target_language": self.target_language_var.get(),
                "priority": self.priority_var.get()
            }
            
            # Add optional parameters
            if self.proxy_var.get().strip():
                request_data["proxy"] = self.proxy_var.get().strip()
            if self.user_agent_var.get().strip():
                request_data["user_agent"] = self.user_agent_var.get().strip()
            
            # Add session_id if available
            if self.session_id_var.get().strip():
                request_data["session_id"] = self.session_id_var.get().strip()
            
            # Make API request
            api_url = f"{endpoint_url}/scrape"
            self.root.after(0, lambda: self.status_var.set("Sending request to API..."))
            
            # Configure SSL verification based on checkbox
            verify_ssl = self.ssl_verify_var.get()
            
            response = self.session.post(api_url, json=request_data, timeout=60, verify=verify_ssl)
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
                
        except requests.exceptions.SSLError as e:
            error_msg = f"SSL Certificate Error: {str(e)}\n\nTry unchecking 'Verify SSL Certificates' for development environments."
            self.root.after(0, lambda: self.status_var.set("SSL Error"))
            self.root.after(0, lambda: self.results_text.insert(tk.END, f"Error: {error_msg}\n"))
            self.root.after(0, lambda: self.product_id_var.set("SSL Error"))
            self.root.after(0, lambda: self.copy_product_id_button.config(state=tk.DISABLED))
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection Error: {str(e)}\n\nPlease check:\n1. The API server is running\n2. The endpoint URL is correct\n3. Network connectivity"
            self.root.after(0, lambda: self.status_var.set("Connection Error"))
            self.root.after(0, lambda: self.results_text.insert(tk.END, f"Error: {error_msg}\n"))
            self.root.after(0, lambda: self.product_id_var.set("Connection Error"))
            self.root.after(0, lambda: self.copy_product_id_button.config(state=tk.DISABLED))
        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            self.root.after(0, lambda: self.status_var.set("Request failed"))
            self.root.after(0, lambda: self.results_text.insert(tk.END, f"Error: {error_msg}\n"))
            self.root.after(0, lambda: self.product_id_var.set("Request Failed"))
            self.root.after(0, lambda: self.copy_product_id_button.config(state=tk.DISABLED))
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.root.after(0, lambda: self.status_var.set("Error occurred"))
            self.root.after(0, lambda: self.results_text.insert(tk.END, f"Error: {error_msg}\n"))
            
            # Clear product ID display on error
            self.root.after(0, lambda: self.product_id_var.set("Error occurred"))
            self.root.after(0, lambda: self.copy_product_id_button.config(state=tk.DISABLED))
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
        """Poll for task status in a separate thread"""
        start_time = datetime.now()
        max_wait_time = 600  # 10 minutes (increased from 5 minutes)
        
        while self.is_polling:
            try:
                # Check if we've been waiting too long
                if (datetime.now() - start_time).seconds > max_wait_time:
                    self.root.after(0, self._handle_polling_timeout)
                    break
                
                # Validate endpoint URL
                endpoint_url, error = self.validate_endpoint_url(self.endpoint_var.get())
                if error:
                    raise Exception(f"Invalid endpoint URL: {error}")
                
                # Get task status with increased timeout
                api_url = f"{endpoint_url}/tasks/{task_id}"
                verify_ssl = self.ssl_verify_var.get()
                
                response = self.session.get(api_url, timeout=60, verify=verify_ssl)  # Increased from 30s to 60s
                response.raise_for_status()
                
                data = response.json()
                status = data.get('status')
                
                self.root.after(0, lambda: self.status_var.set(f"Task {task_id}: {status}"))
                
                if status == 'completed':
                    # Task completed successfully
                    self.root.after(0, lambda: self.status_var.set(f"Task completed - Product saved to Supabase"))
                    self.root.after(0, lambda: self._handle_scrape_response(data))
                    break
                elif status == 'failed':
                    # Task failed
                    error_msg = data.get('error', 'Unknown error occurred')
                    self.root.after(0, lambda: self.status_var.set(f"Task failed: {error_msg}"))
                    self.root.after(0, lambda: self.results_text.insert(tk.END, f"Task failed: {error_msg}\n"))
                    break
                elif status in ['pending', 'running']:
                    # Task still in progress, wait and try again
                    import time
                    time.sleep(3)  # Increased from 2s to 3s to reduce server load
                else:
                    # Unknown status
                    self.root.after(0, lambda: self.status_var.set(f"Unknown status: {status}"))
                    break
                    
            except requests.exceptions.SSLError as e:
                error_msg = f"SSL Certificate Error during polling: {str(e)}"
                self.root.after(0, lambda: self._handle_task_failure(error_msg))
                break
            except requests.exceptions.Timeout as e:
                # Handle timeout specifically - don't fail immediately
                logger.warning(f"Polling timeout for task {task_id}: {str(e)}")
                self.root.after(0, lambda: self.status_var.set(f"Task {task_id}: Polling timeout, retrying..."))
                import time
                time.sleep(5)  # Wait longer before retrying after timeout
                continue
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
        self.polling_task_id = None
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("Polling stopped")
        
        # Clear product ID display
        self.product_id_var.set("Not available yet")
        self.copy_product_id_button.config(state=tk.DISABLED)
    
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
        
        # Display Supabase product ID if available
        supabase_product_id = data.get('supabase_product_id')
        if supabase_product_id:
            self.root.after(0, lambda: self.product_id_var.set(supabase_product_id))
            self.root.after(0, lambda: self.copy_product_id_button.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.results_text.insert(tk.END, "\n" + "="*30 + "\n"))
            self.root.after(0, lambda: self.results_text.insert(tk.END, "SUPABASE PRODUCT ID\n"))
            self.root.after(0, lambda: self.results_text.insert(tk.END, "="*30 + "\n"))
            self.root.after(0, lambda: self.results_text.insert(tk.END, f"Product ID: {supabase_product_id}\n"))
            self.root.after(0, lambda: self.results_text.insert(tk.END, "Product successfully saved to Supabase database!\n"))
        else:
            self.root.after(0, lambda: self.product_id_var.set("Not available yet"))
            self.root.after(0, lambda: self.copy_product_id_button.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.results_text.insert(tk.END, "\n" + "="*30 + "\n"))
            self.root.after(0, lambda: self.results_text.insert(tk.END, "SUPABASE STATUS\n"))
            self.root.after(0, lambda: self.results_text.insert(tk.END, "="*30 + "\n"))
            self.root.after(0, lambda: self.results_text.insert(tk.END, "Product was not saved to Supabase (check logs for details)\n"))
        
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
    
    def add_sample_scene_id(self):
        """Add a sample scene ID for testing"""
        import uuid
        sample_scene_id = str(uuid.uuid4())
        self.scene_id_var.set(sample_scene_id)
    
    def generate_video(self):
        """Start video generation process"""
        scene_id = self.scene_id_var.get().strip()
        user_id = self.user_id_var.get().strip()
        
        if not scene_id:
            messagebox.showerror("Error", "Please enter a Scene ID")
            return
        if not user_id:
            messagebox.showerror("Error", "User ID is required")
            return
        if not self.validate_uuid(scene_id):
            messagebox.showerror("Error", "Scene ID must be a valid UUID format")
            return
        if not self.validate_uuid(user_id):
            messagebox.showerror("Error", "User ID must be a valid UUID format")
            return
        
        # Start video generation in background thread
        threading.Thread(target=self._generate_video_thread, args=(scene_id, user_id), daemon=True).start()
    
    def _generate_video_thread(self, scene_id, user_id):
        """Generate video in background thread"""
        try:
            self.root.after(0, lambda: self.video_status_var.set("Starting video generation..."))
            self.root.after(0, lambda: self.generate_video_button.config(state=tk.DISABLED))
            
            # Validate endpoint URL
            endpoint_url, error = self.validate_endpoint_url(self.endpoint_var.get())
            if error:
                raise Exception(f"Invalid endpoint URL: {error}")
            
            # Prepare request data
            request_data = {
                "scene_id": scene_id,
                "user_id": user_id
            }
            
            # Make API request
            api_url = f"{endpoint_url}/video/generate"
            self.root.after(0, lambda: self.video_status_var.set("Sending request to API..."))
            
            # Configure SSL verification based on checkbox
            verify_ssl = self.ssl_verify_var.get()
            
            response = self.session.post(api_url, json=request_data, timeout=60, verify=verify_ssl)
            response.raise_for_status()
            
            data = response.json()
            
            # Check if task was created successfully
            if data.get('status') == 'pending':
                task_id = data.get('task_id')
                self.root.after(0, lambda: self.video_status_var.set(f"Video generation started: {task_id}"))
                self.root.after(0, lambda: messagebox.showinfo("Success", f"Video generation task started: {task_id}"))
            else:
                self.root.after(0, lambda: self.video_status_var.set("Unexpected response"))
                self.root.after(0, lambda: messagebox.showerror("Error", f"Unexpected response: {data}"))
                
        except Exception as e:
            error_msg = f"Video generation failed: {str(e)}"
            self.root.after(0, lambda: self.video_status_var.set("Error occurred"))
            self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
        finally:
            self.root.after(0, lambda: self.generate_video_button.config(state=tk.NORMAL))
    
    def test_connection(self):
        """Test API connection"""
        threading.Thread(target=self._test_connection_thread, daemon=True).start()
    
    def _test_connection_thread(self):
        """Test connection in background thread"""
        try:
            self.root.after(0, lambda: self.status_var.set("Testing connection..."))
            
            # Validate endpoint URL
            endpoint_url, error = self.validate_endpoint_url(self.endpoint_var.get())
            if error:
                raise Exception(f"Invalid endpoint URL: {error}")
            
            api_url = f"{endpoint_url}/health"
            verify_ssl = self.ssl_verify_var.get()
            
            response = self.session.get(api_url, timeout=10, verify=verify_ssl)
            response.raise_for_status()
            
            data = response.json()
            status = data.get('status', 'unknown')
            
            if status == 'healthy':
                self.root.after(0, lambda: self.status_var.set("Connection successful"))
                self.root.after(0, lambda: messagebox.showinfo("Success", "API connection successful!"))
            else:
                self.root.after(0, lambda: self.status_var.set("API unhealthy"))
                self.root.after(0, lambda: messagebox.showwarning("Warning", f"API status: {status}"))
                
        except requests.exceptions.SSLError as e:
            error_msg = f"SSL Certificate Error: {str(e)}\n\nTry unchecking 'Verify SSL Certificates' for development environments."
            self.root.after(0, lambda: self.status_var.set("SSL Error"))
            self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection Error: {str(e)}\n\nPlease check:\n1. The API server is running\n2. The endpoint URL is correct\n3. Network connectivity"
            self.root.after(0, lambda: self.status_var.set("Connection Error"))
            self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
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