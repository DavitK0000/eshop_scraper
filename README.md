# E-commerce Scraper API

A high-performance Python-based backend service that exposes an API endpoint to extract live product information from various e-commerce websites. Built with FastAPI and Playwright for handling JavaScript-heavy sites.

## Features

- **FastAPI Backend**: Lightweight, high-performance REST API
- **Playwright Integration**: Handles JavaScript-heavy sites like Amazon, eBay, JD.com
- **Asynchronous Processing**: Non-blocking scraping operations
- **Caching System**: Redis-based caching with configurable TTL
- **Proxy Rotation**: Support for rotating proxies to bypass restrictions
- **User Agent Rotation**: Automatic user agent rotation
- **Retry Logic**: Configurable retry mechanism with exponential backoff
- **Error Handling**: Comprehensive error handling and logging
- **Task Management**: Track scraping task status and progress
- **GUI Testing Tool**: Built-in GUI application for testing the API

## Supported Platforms

- Amazon (multiple regions)
- eBay (multiple regions)
- JD.com
- Generic scraper for unsupported domains

## Prerequisites

- Python 3.8+
- Redis server
- Windows Server (as specified)

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd eshop-scraper
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright browsers**
   ```bash
   playwright install
   ```

5. **Setup Redis**
   - Install Redis on your Windows server
   - Start Redis service
   - Default configuration: `localhost:6379`

6. **Environment Configuration**
   ```bash
   # Copy the example environment file
   copy env_example.txt .env
   
   # Edit .env with your settings
   notepad .env
   ```

## Configuration

The application can be configured using environment variables. See `env_example.txt` for all available options:

### Key Settings

- `REDIS_URL`: Redis connection string
- `CACHE_TTL`: Cache time-to-live in seconds (default: 3600)
- `MAX_RETRIES`: Maximum retry attempts for failed scrapes (default: 3)
- `PROXY_LIST`: Comma-separated list of proxy servers
- `ROTATE_PROXIES`: Enable/disable proxy rotation
- `ROTATE_USER_AGENTS`: Enable/disable user agent rotation

## Usage

### Starting the API Server

```bash
# Development mode
python -m app.main

# Or using uvicorn directly
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:
- API: http://localhost:8000
- ReDoc: http://localhost:8000/redoc

### Using the GUI Testing Tool

```bash
python gui_test.py
```

The GUI provides:
- URL input with sample URLs
- Force refresh option
- Proxy and user agent configuration
- Real-time scraping results
- Health check and cache management

## API Endpoints

### Core Endpoints

#### `POST /api/v1/scrape`
Scrape product information from a URL.

**Request Body:**
```json
{
  "url": "https://www.amazon.com/dp/B08N5WRWNW",
  "force_refresh": false,
  "proxy": "http://proxy:8080",
  "user_agent": "Mozilla/5.0..."
}
```

#### `GET /api/v1/scrape`
Convenience endpoint for simple GET requests.

**Query Parameters:**
- `url` (required): Product URL
- `force_refresh` (optional): Bypass cache
- `proxy` (optional): Custom proxy
- `user_agent` (optional): Custom user agent

### Management Endpoints

#### `GET /api/v1/health`
Check API health status.

#### `GET /api/v1/tasks/{task_id}`
Get status of a specific scraping task.

#### `GET /api/v1/tasks`
Get all active scraping tasks.

#### `GET /api/v1/domains`
Get list of supported domains.

#### `GET /api/v1/cache/stats`
Get cache statistics.

#### `DELETE /api/v1/cache`
Clear all cached results.

#### `DELETE /api/v1/cache/{url}`
Invalidate cache for specific URL.

#### `POST /api/v1/tasks/cleanup`
Clean up old completed tasks.

## Response Format

### Successful Scrape Response
```json
{
  "task_id": "task_abc123_1234567890",
  "status": "completed",
  "url": "https://www.amazon.com/dp/B08N5WRWNW",
  "product_info": {
    "title": "Product Title",
    "price": "$99.99",
    "currency": "USD",
    "description": "Product description...",
    "images": ["https://image1.jpg", "https://image2.jpg"],
    "availability": "In Stock",
    "rating": 4.5,
    "review_count": 1234,
    "seller": "Amazon",
    "brand": "Brand Name",
    "sku": "ABC123",
    "category": "Electronics",
    "specifications": {
      "Color": "Black",
      "Weight": "1.5 lbs"
    },
    "raw_data": {
      "url": "https://www.amazon.com/dp/B08N5WRWNW",
      "html_length": 50000
    }
  },
  "error": null,
  "created_at": "2024-01-01T12:00:00",
  "completed_at": "2024-01-01T12:00:05",
  "cache_hit": false
}
```

### Error Response
```json
{
  "task_id": "task_abc123_1234567890",
  "status": "failed",
  "url": "https://invalid-url.com",
  "product_info": null,
  "error": "Invalid URL format",
  "created_at": "2024-01-01T12:00:00",
  "completed_at": "2024-01-01T12:00:01",
  "cache_hit": false
}
```

## Scraper Development

### Adding New Scrapers

1. Create a new scraper class in `app/scrapers/`:
   ```python
   from app.scrapers.base import BaseScraper
   from app.models import ProductInfo
   
   class NewSiteScraper(BaseScraper):
       async def extract_product_info(self) -> ProductInfo:
           product_info = ProductInfo()
           
           # Extract data using CSS selectors
           product_info.title = self.find_element_text('.product-title')
           product_info.price = self.extract_price('.price')
           # ... more extractions
           
           return product_info
   ```

2. Register the scraper in `app/scrapers/factory.py`:
   ```python
   _scrapers = {
       'newsite.com': NewSiteScraper,
       # ... existing scrapers
   }
   ```

### Scraper Base Class Methods

- `find_element_text(selector)`: Get text from element
- `find_element_attr(selector, attr)`: Get attribute from element
- `find_elements_attr(selector, attr)`: Get attributes from multiple elements
- `extract_price(selector)`: Extract and format price
- `extract_rating(selector)`: Extract and format rating

## Performance Considerations

### Caching
- Results are cached in Redis with configurable TTL
- Use `force_refresh=true` to bypass cache
- Cache statistics available via API

### Resource Management
- Playwright browsers are properly cleaned up after each request
- Memory usage is optimized for Windows Server environment
- Connection pooling for Redis

### Rate Limiting
- Configurable rate limiting per minute
- Exponential backoff for retries
- Proxy rotation to avoid IP blocking

## Monitoring and Logging

### Log Levels
- `INFO`: General application flow
- `WARNING`: Non-critical issues
- `ERROR`: Scraping failures and errors
- `DEBUG`: Detailed debugging information

### Health Monitoring
- `/api/v1/health` endpoint for health checks
- Redis connection status monitoring
- Task status tracking

## Troubleshooting

### Common Issues

1. **Playwright Installation**
   ```bash
   playwright install
   playwright install-deps
   ```

2. **Redis Connection**
   - Ensure Redis is running on Windows
   - Check Redis URL in configuration
   - Verify network connectivity

3. **Scraping Failures**
   - Check if site is accessible
   - Verify CSS selectors are still valid
   - Try with different proxy/user agent

4. **Memory Issues**
   - Monitor browser cleanup
   - Check for memory leaks in long-running processes
   - Adjust Playwright settings if needed

### Debug Mode
Set `DEBUG=True` in environment to enable detailed logging and auto-reload.

## Security Considerations

- Configure CORS properly for production
- Set trusted hosts in production
- Use HTTPS in production
- Implement proper authentication if needed
- Validate and sanitize all inputs

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Add tests if applicable
5. Submit a pull request

## License

[Add your license information here]

## Support

For issues and questions:
- Check the troubleshooting section
- Open an issue in the repository 