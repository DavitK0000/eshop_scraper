# Polling API Documentation

## Overview

The scraping API now supports proper asynchronous/polling patterns. Instead of waiting for the entire scraping process to complete, the API returns immediately with a task ID that can be used to poll for completion status and results.

## API Endpoints

### 1. Start Scraping Task

**POST** `/scrape`

Starts a scraping task asynchronously and returns immediately with a task ID.

**Request Body:**
```json
{
  "url": "https://example.com/product",
  "force_refresh": false,
  "proxy": null,
  "user_agent": null,
  "block_images": true,
  "target_language": "en"
}
```

**Response:**
```json
{
  "task_id": "abc123def456",
  "status": "pending",
  "url": "https://example.com/product",
  "created_at": "2024-01-01T12:00:00Z",
  "product_info": null,
  "error": null,
  "completed_at": null,
  "cache_hit": false,
  "detected_platform": null,
  "platform_confidence": null,
  "platform_indicators": [],
  "target_language": "en"
}
```

### 2. Get Task Status

**GET** `/tasks/{task_id}`

Returns the current status of a scraping task.

**Response:**
```json
{
  "task_id": "abc123def456",
  "status": "running",
  "progress": null,
  "message": "Scraping product information",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:05Z",
  "target_language": "en"
}
```

### 3. Get Task Result

**GET** `/tasks/{task_id}/result`

Returns the complete result of a scraping task, including product information when completed.

**Response (Completed):**
```json
{
  "task_id": "abc123def456",
  "status": "completed",
  "url": "https://example.com/product",
  "product_info": {
    "title": "Product Title",
    "price": 99.99,
    "currency": "USD",
    "description": "Product description...",
    "images": ["https://example.com/image1.jpg"],
    "availability": "In Stock",
    "rating": 4.5,
    "review_count": 123,
    "seller": "Example Store",
    "brand": "Example Brand",
    "sku": "SKU123",
    "category": "Electronics",
    "specifications": {},
    "raw_data": {}
  },
  "error": null,
  "created_at": "2024-01-01T12:00:00Z",
  "completed_at": "2024-01-01T12:00:10Z",
  "cache_hit": false,
  "detected_platform": "shopify",
  "platform_confidence": 0.85,
  "platform_indicators": ["Shopify pattern found", "shopify-section class detected"],
  "target_language": "en"
}
```

**Response (Failed):**
```json
{
  "task_id": "abc123def456",
  "status": "failed",
  "url": "https://example.com/product",
  "product_info": null,
  "error": "Failed to load page: timeout",
  "created_at": "2024-01-01T12:00:00Z",
  "completed_at": "2024-01-01T12:00:05Z",
  "cache_hit": false,
  "detected_platform": null,
  "platform_confidence": null,
  "platform_indicators": [],
  "target_language": "en"
}
```

## Task Status Values

- `pending`: Task has been created but not yet started
- `running`: Task is currently being executed
- `completed`: Task completed successfully with results
- `failed`: Task failed with an error

## Client Usage Examples

### Python Example

```python
import asyncio
import aiohttp

async def scrape_with_polling():
    async with aiohttp.ClientSession() as session:
        # Start scraping task
        async with session.post("http://localhost:8000/scrape", json={
            "url": "https://example.com/product",
            "target_language": "en"
        }) as response:
            task_data = await response.json()
            task_id = task_data["task_id"]
        
        # Poll for completion
        while True:
            async with session.get(f"http://localhost:8000/tasks/{task_id}/result") as response:
                result = await response.json()
                
                if result["status"] in ["completed", "failed"]:
                    if result["status"] == "completed":
                        print(f"Product: {result['product_info']['title']}")
                        print(f"Price: {result['product_info']['price']}")
                    else:
                        print(f"Error: {result['error']}")
                    break
                
                await asyncio.sleep(2)  # Wait 2 seconds before next poll

# Run the example
asyncio.run(scrape_with_polling())
```

### JavaScript Example

```javascript
async function scrapeWithPolling() {
    // Start scraping task
    const startResponse = await fetch('http://localhost:8000/scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            url: 'https://example.com/product',
            target_language: 'en'
        })
    });
    
    const taskData = await startResponse.json();
    const taskId = taskData.task_id;
    
    // Poll for completion
    while (true) {
        const resultResponse = await fetch(`http://localhost:8000/tasks/${taskId}/result`);
        const result = await resultResponse.json();
        
        if (result.status === 'completed' || result.status === 'failed') {
            if (result.status === 'completed') {
                console.log(`Product: ${result.product_info.title}`);
                console.log(`Price: ${result.product_info.price}`);
            } else {
                console.log(`Error: ${result.error}`);
            }
            break;
        }
        
        await new Promise(resolve => setTimeout(resolve, 2000)); // Wait 2 seconds
    }
}

scrapeWithPolling();
```

## Benefits of Polling API

1. **Non-blocking**: The API returns immediately, allowing clients to handle multiple requests concurrently
2. **Progress tracking**: Clients can monitor task progress and provide user feedback
3. **Timeout handling**: Clients can implement their own timeout logic
4. **Resource management**: Better control over server resources and connection handling
5. **Scalability**: Supports high-concurrency scenarios without blocking

## Backward Compatibility

The original synchronous `scrape_product` method is still available in the scraping service for backward compatibility, but the API endpoints now use the new polling pattern by default.

## Error Handling

- **404 Not Found**: Task ID doesn't exist
- **500 Internal Server Error**: Server error during scraping
- **Timeout**: Task takes too long to complete (client-side handling)

## Best Practices

1. **Polling interval**: Use 2-5 second intervals to avoid overwhelming the server
2. **Timeout**: Implement reasonable timeouts (30-60 seconds) for scraping tasks
3. **Error handling**: Always check for failed status and handle errors gracefully
4. **Caching**: The API automatically caches successful results for better performance
5. **Concurrent requests**: The API supports multiple concurrent scraping tasks 