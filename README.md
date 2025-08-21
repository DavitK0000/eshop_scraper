# E-commerce Scraper API

A high-performance API for scraping product information from e-commerce websites with intelligent platform detection.

## Architecture

The system has been simplified and restructured for better separation of concerns:

### Core Components

1. **Browser Manager** (`app/browser_manager.py`)
   - Handles browser setup and page fetching
   - Uses Chrome only for consistency
   - Manages image/video blocking
   - Handles proxy and user agent configuration

2. **Extractors** (`app/extractors/`)
   - `BaseExtractor`: Abstract base class for all extractors
   - `GenericExtractor`: Handles unsupported platforms using common selectors
   - `AmazonExtractor`: Amazon-specific extraction logic
   - Platform-specific extractors can be easily added

3. **Extractor Factory** (`app/extractors/factory.py`)
   - Creates appropriate extractor based on platform detection
   - Maps platform names to extractor classes

4. **Scraping Service** (`app/services/scraping_service.py`)
   - Orchestrates the scraping process
   - Handles platform detection
   - Manages task lifecycle
   - Integrates browser manager and extractors

5. **AI Generation Utilities** (`app/utils/runwayml_utils.py`)
   - RunwayML integration for AI-powered content generation
   - Image-to-video generation using gen4_turbo model
   - Text-to-image generation with reference support
   - Styled image generation with style transfer
   - Async support for better performance

### How It Works

1. **Browser Setup**: Browser manager sets up Chrome with image blocking
2. **Page Fetching**: Browser manager fetches HTML content from the URL
3. **Platform Detection**: Scraping service detects the e-commerce platform
4. **Extractor Selection**: Factory creates the appropriate extractor
5. **Data Extraction**: Extractor parses HTML and extracts product information

## API Endpoints

### Core Endpoints

- `POST /api/v1/scrape` - Start a scraping task
- `GET /api/v1/tasks/{task_id}` - Get task status and results
- `GET /api/v1/tasks` - List all active tasks
- `GET /api/v1/health` - Health check
- `GET /api/v1/test` - Simple test page

### Removed Endpoints

The following endpoints have been removed to simplify the system:
- Video processing endpoints
- Security statistics endpoints
- Cache management endpoints
- In-memory cache status endpoints

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start the server:
```bash
python -m app.main
```

Or use the provided batch file:
```bash
start_server.bat
```

## Usage

### API Usage

```bash
# Start scraping
curl -X POST "http://localhost:8000/api/v1/scrape" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.amazon.com/dp/B08N5WRWNW",
    "force_refresh": false,
    "block_images": true
  }'

# Check task status
curl "http://localhost:8000/api/v1/tasks/{task_id}"
```

### GUI Testing

Run the simplified GUI test:
```bash
python gui_test.py
```

The GUI includes:
- URL input with sample URLs
- Basic options (force refresh, block images, proxy, user agent)
- Real-time status updates
- Results display

## Supported Platforms

Currently supported platforms:
- **Amazon** - Full support with ASIN extraction, ratings, reviews
- **Generic** - Common selectors for unsupported platforms

Platforms can be easily added by:
1. Creating a new extractor class in `app/extractors/`
2. Adding it to the factory mapping in `app/extractors/factory.py`
3. Adding platform detection patterns in `app/services/scraping_service.py`

## Configuration

Key configuration options in `app/config.py`:

### Server Settings
- `HOST` and `PORT` - Server configuration
- `LOG_LEVEL` - Logging level

### Browser Settings
- `ROTATE_PROXIES` - Enable proxy rotation
- `ROTATE_USER_AGENTS` - Enable user agent rotation
- `PLAYWRIGHT_HEADLESS` - Run browser in headless mode

### Timeout Settings
- `BROWSER_NETWORK_IDLE_TIMEOUT` - Time to wait for network idle (default: 5000ms)
- `BROWSER_DOM_LOAD_TIMEOUT` - Time to wait for DOM content (default: 10000ms)
- `BROWSER_ADDITIONAL_WAIT` - Additional wait time for content (default: 2000ms)
- `BROWSER_MAX_RETRIES` - Maximum retry attempts for failed requests (default: 2)

### Environment Variables

Create a `.env` file with these settings:

```env
# Browser Manager Timeout Settings
BROWSER_NETWORK_IDLE_TIMEOUT=5000
BROWSER_DOM_LOAD_TIMEOUT=10000
BROWSER_ADDITIONAL_WAIT=2000
BROWSER_MAX_RETRIES=2

# Logging Settings
LOG_LEVEL=INFO
LOG_TO_FILE=True
LOG_FILE_MAX_SIZE=10485760
LOG_FILE_BACKUP_COUNT=5

# Other settings...
HOST=0.0.0.0
PORT=8000
ROTATE_PROXIES=True
ROTATE_USER_AGENTS=True
PLAYWRIGHT_HEADLESS=True
```

### Logging System

The application uses a comprehensive logging system that writes to both console and files:

- **Console Output**: Less verbose, shows INFO level and above
- **File Logs**: 
  - `logs/app.log` - All logs with detailed formatting
  - `logs/errors.log` - Error-level logs only
  - `logs/security.log` - Security-related events

Log files are automatically rotated when they reach the configured size limit.

**Log Levels:**
- `DEBUG` - Detailed debugging information
- `INFO` - General application information
- `WARNING` - Warning messages
- `ERROR` - Error messages
- `CRITICAL` - Critical errors

## AI Generation with RunwayML

The application includes powerful AI generation utilities powered by [RunwayML](https://runwayml.com/) for creating dynamic content from your scraped product data.

### Features

- 🎬 **Image-to-Video**: Convert product photos into engaging marketing videos
- 🎨 **Text-to-Image**: Generate product mockups and lifestyle images
- 🎭 **Style Transfer**: Apply brand styles to product images
- ⚡ **Async Processing**: Non-blocking generation for better performance

### Quick Start

1. **Install the package:**
   ```bash
   pip install runwayml
   ```

2. **Configure your API key:**
   ```bash
   # Add to your .env file
   RUNWAYML_API_SECRET=your_api_key_here
   RUNWAYML_ENABLED=True
   ```

3. **Generate content:**
   ```python
   from app.utils.runwayml_utils import generate_video_from_image
   
   # Create a product video
   result = await generate_video_from_image(
       prompt_image="product.jpg",
       prompt_text="Show the product rotating with elegant lighting",
       duration=5
   )
   ```

### Use Cases

- **Product Marketing**: Create dynamic videos from static product images
- **Social Media**: Generate branded content in various aspect ratios
- **Brand Consistency**: Apply consistent styling across product catalogs
- **Content Creation**: Generate images for product descriptions and marketing

For detailed usage instructions, see [RUNWAYML_README.md](RUNWAYML_README.md).

## Development

### Adding a New Platform

1. Create extractor class:
```python
from app.extractors.base import BaseExtractor

class NewPlatformExtractor(BaseExtractor):
    def extract_title(self):
        # Platform-specific title extraction
        pass
    
    def extract_price(self):
        # Platform-specific price extraction
        pass
    
    # ... other methods
```

2. Add to factory:
```python
_platform_extractors = {
    'amazon': AmazonExtractor,
    'newplatform': NewPlatformExtractor,
}
```

3. Add platform detection patterns in `ScrapingService`

## Troubleshooting

### Common Issues

1. **Browser not starting**: Ensure Chrome is installed and accessible
2. **Platform not detected**: Check if platform patterns are correctly configured
3. **Extraction fails**: Verify CSS selectors in the platform extractor
4. **Timeout errors**: 
   - Increase `BROWSER_NETWORK_IDLE_TIMEOUT` for slow-loading sites
   - Increase `BROWSER_DOM_LOAD_TIMEOUT` for complex pages
   - Increase `BROWSER_MAX_RETRIES` for unreliable connections
   - Check network connectivity and proxy settings

### Logs

Check logs for detailed error information:

```bash
# View all logs
tail -f logs/app.log

# View only errors
tail -f logs/errors.log

# View security events
tail -f logs/security.log
```

## License

This project is licensed under the MIT License. 