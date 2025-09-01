# Image Analysis API Documentation

## Overview

The Image Analysis API provides endpoints for analyzing product images using OpenAI's Vision API. This service can analyze multiple images simultaneously (up to 4 at once) and provides detailed visual analysis including object detection, color analysis, style identification, and video generation suggestions.

**Smart Task Management**: If all images for a product are already analyzed, the API returns an immediate response without creating unnecessary tasks. This prevents duplicate work and improves efficiency.

## Features

- **Batch Processing**: Analyze up to 4 images simultaneously for efficiency
- **Retry Logic**: Automatic retry mechanism for failed image analyses
- **Comprehensive Analysis**: Detailed visual analysis including objects, colors, style, mood, and use cases
- **Video Generation Support**: Analysis results optimized for video generation workflows
- **Progress Tracking**: Real-time progress updates and task status monitoring
- **Database Integration**: Results automatically saved to the products table
- **Asynchronous Processing**: Tasks run in background threads for non-blocking operation

## API Endpoints

### 1. Start Image Analysis

**POST** `/api/v1/image/analyze`

Starts an image analysis task for a product based on its product_id. If all images are already analyzed, returns an immediate response without creating a task.

#### Request Body

```json
{
  "product_id": "uuid-of-the-product",
  "user_id": "uuid-of-the-user"
}
```

#### Response - New Task Created

```json
{
  "task_id": "task-uuid-123",
  "status": "pending",
  "product_id": "uuid-of-the-product",
  "user_id": "uuid-of-the-user",
  "message": "Image analysis task started",
  "created_at": "2024-01-01T00:00:00Z",
  "progress": 0.0,
  "current_step": "Task started",
  "error_message": null,
  "total_images": 3,
  "analyzed_images": 0,
  "failed_images": 0,
  "analyzedData": null,
  "completed_at": null
}
```

#### Response - All Images Already Analyzed

```json
{
  "task_id": "",
  "status": "completed",
  "product_id": "uuid-of-the-product",
  "user_id": "uuid-of-the-user",
  "message": "All images already analyzed",
  "created_at": "2024-01-01T00:00:00Z",
  "progress": 100.0,
  "current_step": "Already completed",
  "error_message": null,
  "total_images": 3,
  "analyzed_images": 3,
  "failed_images": 0,
  "analyzedData": null,
  "completed_at": "2024-01-01T00:00:00Z"
}
```

### 2. Get Task Status

**GET** `/api/v1/image/analyze/tasks/{task_id}`

Retrieves the current status and progress of an image analysis task. Note: Analysis results are not included in task responses - they are stored directly in the database.

#### Response

```json
{
  "task_id": "task-uuid-123",
  "status": "completed",
  "product_id": "uuid-of-the-product",
  "user_id": "uuid-of-the-user",
  "message": "Image analysis completed. 3 analyzed, 0 failed.",
  "created_at": "2024-01-01T00:00:00Z",
  "progress": 100.0,
  "current_step": "Completed",
  "error_message": null,
  "total_images": 3,
  "analyzed_images": 3,
  "failed_images": 0,
  "analyzedData": null,
  "completed_at": "2024-01-01T00:05:00Z"
}
```

### 3. Cancel Task

**DELETE** `/api/v1/image/analyze/tasks/{task_id}`

Cancels a running image analysis task.

#### Response

```json
{
  "message": "Image analysis task task-uuid-123 cancelled successfully"
}
```

### 4. Cleanup Tasks

**DELETE** `/api/v1/image/analyze/tasks`

Cleans up old completed/failed image analysis tasks.

#### Response

```json
{
  "message": "Image analysis task cleanup completed",
  "deleted_tasks_count": 15
}
```

## Analysis Results Structure

### ImageAnalysisResult Fields

| Field | Type | Description |
|-------|------|-------------|
| `image_url` | string | URL of the analyzed image |
| `description` | string | Comprehensive description of the image content |
| `details` | object | Structured analysis details |
| `error` | string | Error message if analysis failed |
| `analyzed_at` | datetime | Timestamp when analysis was completed |
| `objects` | array | List of detected objects in the image |
| `colors` | array | List of prominent colors |
| `style` | string | Visual style (modern, vintage, minimalist, etc.) |
| `mood` | string | Emotional mood conveyed by the image |
| `text` | array | Any text, logos, or branding visible |
| `productFeatures` | array | Visual features of products shown |
| `videoScenarios` | array | Suggested video scenarios for this image |
| `targetAudience` | string | Target audience for this type of image |
| `useCases` | array | Potential use cases and contexts |

### Analysis Details

The service analyzes images for:

1. **Visual Content**: Objects, scenes, people, activities
2. **Visual Elements**: Colors, lighting, composition, layout
3. **Style & Mood**: Aesthetic tone, emotional atmosphere
4. **Product Features**: Visual characteristics and attributes
5. **Video Generation**: Suggested scenarios and use cases
6. **Target Audience**: Who the image would appeal to

## Accessing Analysis Results

### Analysis Results Storage

Analysis results are **not included** in task responses to keep them lightweight and efficient. Instead, results are automatically stored in the database and can be accessed directly.

### Getting Analysis Results

To retrieve the analysis results for a product, query the `products` table directly:

```sql
-- Get product with image analysis results
SELECT id, title, images 
FROM products 
WHERE product_id = 'your-product-id';
```

### Analysis Results Structure

The `images` field contains a JSONB object with analysis results:

```json
{
  "https://example.com/image1.jpg": {
    "description": "A modern smartphone with a sleek design...",
    "details": {
      "objects": ["smartphone", "background"],
      "colors": ["black", "white", "silver"],
      "style": "modern",
      "mood": "professional",
      "text": ["Brand Logo"],
      "productFeatures": ["wireless", "portable", "smart"],
      "videoScenarios": ["unboxing", "review", "demonstration"],
      "targetAudience": "professional",
      "useCases": ["home", "office", "travel"]
    },
    "analyzed_at": "2024-01-01T00:05:00Z"
  },
  "https://example.com/image2.jpg": {
    "error": "Failed to analyze image",
    "analyzed_at": "2024-01-01T00:05:00Z"
  }
}
```

### Python Example - Retrieving Results

```python
import requests
from app.utils.supabase_utils import supabase_manager

def get_image_analysis_results(product_id: str):
    """Get image analysis results for a product"""
    try:
        # Query the products table
        result = supabase_manager.client.table('products').select(
            'id, title, images'
        ).eq('product_id', product_id).execute()
        
        if result.data:
            product = result.data[0]
            images = product.get('images', {})
            
            # Process analysis results
            for image_url, analysis in images.items():
                if 'error' not in analysis:
                    print(f"Image: {image_url}")
                    print(f"Description: {analysis.get('description')}")
                    print(f"Style: {analysis.get('details', {}).get('style')}")
                    print(f"Objects: {analysis.get('details', {}).get('objects')}")
                    print("---")
                else:
                    print(f"Image {image_url} failed: {analysis.get('error')}")
                    
    except Exception as e:
        print(f"Error retrieving results: {e}")
```

## Database Schema

### Products Table Images Field

The analysis results are stored in the `products.images` field as a JSONB object:

```sql
-- Structure of the images field
{
  "https://example.com/image1.jpg": {
    "description": "Image description...",
    "details": {
      "objects": ["object1", "object2"],
      "colors": ["#FF0000", "#00FF00"],
      "style": "modern",
      "mood": "professional",
      "text": ["Brand Name"],
      "productFeatures": ["wireless", "portable"],
      "videoScenarios": ["unboxing", "review"],
      "targetAudience": "professional",
      "useCases": ["home", "office"]
    },
    "analyzed_at": "2024-01-01T00:00:00Z"
  },
  "https://example.com/image2.jpg": {
    "error": "Failed to analyze image",
    "analyzed_at": "2024-01-01T00:00:00Z"
  }
}
```

## Task Lifecycle

### Task States

1. **PENDING**: Task created and queued
2. **RUNNING**: Analysis in progress
3. **COMPLETED**: Analysis completed successfully
4. **FAILED**: Analysis failed with error

### Progress Tracking

- **0-10%**: Fetching product images
- **10-20%**: Identifying unanalyzed images
- **20-90%**: Analyzing images (progress based on completion)
- **90-100%**: Updating database and finalizing

## Error Handling

### Retry Logic

- **Max Retries**: 3 attempts per image
- **Retry Delay**: Exponential backoff (2s, 4s, 6s)
- **Failure Handling**: Failed images are marked with error details

### Common Errors

- **Content Filter**: Image blocked by OpenAI content filters
- **Invalid Image**: Unsupported or corrupted image format
- **Rate Limit**: OpenAI API rate limit exceeded
- **Network Issues**: Connection or timeout problems

## Configuration

### Environment Variables

```bash
# Required
OPENAI_API_KEY=your_openai_api_key_here

# Optional
OPENAI_MODEL=gpt-4o-mini  # Default: gpt-4o-mini
MAX_CONCURRENT_ANALYSES=4  # Default: 4
MAX_RETRIES=3              # Default: 3
RETRY_DELAY=2              # Default: 2 seconds
```

### Service Configuration

```python
class ImageAnalysisService:
    def __init__(self):
        self.max_concurrent_analyses = 4  # Process 4 images simultaneously
        self.max_retries = 3
        self.retry_delay = 2  # seconds
```

## Usage Examples

### Python Client Example

```python
import requests
import time

# Start image analysis
response = requests.post(
    "http://localhost:8000/api/v1/image/analyze",
    json={
        "product_id": "your-product-id",
        "user_id": "your-user-id"
    }
)

response_data = response.json()

# Check if all images are already analyzed
if response_data["status"] == "completed" and response_data["task_id"] == "":
    print(f"All images already analyzed: {response_data['message']}")
    print(f"Total images: {response_data['total_images']}")
    print(f"Analyzed images: {response_data['analyzed_images']}")
    # Results are available in the database - no need to poll
else:
    # New task created - poll for completion
    task_id = response_data["task_id"]
    print(f"Task started: {task_id}")
    
    # Poll for completion
    while True:
        status_response = requests.get(
            f"http://localhost:8000/api/v1/image/analyze/tasks/{task_id}"
        )
        status_data = status_response.json()
        
        if status_data["status"] in ["completed", "failed"]:
            print(f"Task completed: {status_data['message']}")
            print(f"Total images: {status_data['total_images']}")
            print(f"Analyzed images: {status_data['analyzed_images']}")
            print(f"Failed images: {status_data['failed_images']}")
            # Note: Analysis results are stored in database, not in response
            break
        
        time.sleep(5)  # Wait 5 seconds before checking again
```

### cURL Examples

```bash
# Start analysis
curl -X POST "http://localhost:8000/api/v1/image/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "your-product-id",
    "user_id": "your-user-id"
  }'

# Check status
curl "http://localhost:8000/api/v1/image/analyze/tasks/{task_id}"

# Cancel task
curl -X DELETE "http://localhost:8000/api/v1/image/analyze/tasks/{task_id}"
```

## Performance Considerations

### Concurrent Processing

- **Batch Size**: Up to 4 images analyzed simultaneously
- **API Limits**: Respects OpenAI rate limits
- **Memory Usage**: Efficient memory management for large image sets

### Optimization Tips

1. **Batch Requests**: Group multiple images in single requests when possible
2. **Image Quality**: Use high-quality images for better analysis results
3. **Caching**: Results are stored in database for future reference
4. **Error Handling**: Implement proper retry logic in client applications

## Security

### Authentication

- **API Keys**: Optional Bearer token authentication
- **User Validation**: User ID validation for task ownership
- **Rate Limiting**: Configurable rate limits per API key

### Data Privacy

- **Image URLs**: Only image URLs are sent to OpenAI (not image data)
- **Secure Storage**: Analysis results stored securely in Supabase
- **Access Control**: User-specific data isolation

## Monitoring and Logging

### Task Monitoring

- **Progress Tracking**: Real-time progress updates
- **Status History**: Complete task lifecycle tracking
- **Error Logging**: Detailed error information for debugging

### Performance Metrics

- **Success Rate**: Percentage of successful analyses
- **Processing Time**: Average time per image
- **Concurrency**: Number of simultaneous analyses
- **Error Rates**: Failure patterns and frequencies

## Troubleshooting

### Common Issues

1. **Task Not Starting**
   - Check OpenAI API key configuration
   - Verify product_id exists in database
   - Check user permissions

2. **Analysis Failures**
   - Verify image URLs are accessible
   - Check image format compatibility
   - Review OpenAI API quotas

3. **Performance Issues**
   - Monitor concurrent analysis limits
   - Check network connectivity to OpenAI
   - Review image sizes and quality

### Debug Information

Enable debug logging to get detailed information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

### Planned Features

- **Custom Analysis Prompts**: User-defined analysis criteria
- **Batch Processing**: Support for larger image sets
- **Analysis Templates**: Predefined analysis patterns
- **Export Options**: Multiple output formats
- **Integration APIs**: Webhook notifications and callbacks

### API Versioning

- **Current Version**: v1
- **Backward Compatibility**: Maintained across minor versions
- **Deprecation Policy**: 6-month notice for breaking changes

## Support

### Documentation

- **API Reference**: Complete endpoint documentation
- **Code Examples**: Working examples in multiple languages
- **Integration Guides**: Step-by-step setup instructions

### Community

- **Issues**: GitHub issue tracking
- **Discussions**: Community forums and Q&A
- **Contributions**: Pull request guidelines and development setup

---

For additional support or questions, please refer to the main project documentation or create an issue in the project repository.
