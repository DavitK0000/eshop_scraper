# RunwayML Utility Functions

This module provides easy-to-use utility functions for AI-powered image and video generation using [RunwayML's API](https://docs.dev.runwayml.com/guides/using-the-api/).

## Features

- 🎬 **Image-to-Video Generation**: Convert static images into dynamic videos
- 🎨 **Text-to-Image Generation**: Create images from text descriptions
- 🎭 **Styled Image Generation**: Generate images with reference images and style transfer
- 🔧 **Easy Configuration**: Simple environment variable setup
- 📱 **Flexible Input**: Support for both local files and URLs
- ⚡ **Async Support**: Built-in async/await support for better performance

## Installation

1. **Install the required package:**
   ```bash
   pip install runwayml
   ```

2. **Set up environment variables:**
   ```bash
   # Copy the example environment file
   cp env_example.txt .env
   
   # Edit .env and add your RunwayML API credentials
   RUNWAYML_API_SECRET=your_runwayml_api_secret_here
   RUNWAYML_ENABLED=True
   ```

## Configuration

Add these environment variables to your `.env` file:

```bash
# RunwayML Settings
RUNWAYML_API_SECRET=your_runwayml_api_secret_here
RUNWAYML_API_VERSION=2024-11-06
RUNWAYML_ENABLED=True
RUNWAYML_DEFAULT_MODEL=gen4_turbo
RUNWAYML_DEFAULT_RATIO=1280:720
RUNWAYML_DEFAULT_DURATION=5
RUNWAYML_MAX_RETRIES=3
RUNWAYML_TIMEOUT=300
```

### Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `RUNWAYML_API_SECRET` | - | Your RunwayML API secret key |
| `RUNWAYML_API_VERSION` | `2024-11-06` | API version to use |
| `RUNWAYML_ENABLED` | `False` | Enable/disable RunwayML functionality |
| `RUNWAYML_DEFAULT_MODEL` | `gen4_turbo` | Default model for video generation |
| `RUNWAYML_DEFAULT_RATIO` | `1280:720` | Default aspect ratio |
| `RUNWAYML_DEFAULT_DURATION` | `5` | Default video duration in seconds |
| `RUNWAYML_MAX_RETRIES` | `3` | Maximum retry attempts |
| `RUNWAYML_TIMEOUT` | `300` | Timeout in seconds (5 minutes) |

## Usage

### Basic Import

```python
from app.utils.runwayml_utils import (
    generate_video_from_image,
    generate_image_from_text,
    generate_image_with_reference_style,
    is_runwayml_available,
    get_runwayml_status
)
```

### 1. Generate Video from Image

```python
import asyncio
from app.utils.runwayml_utils import generate_video_from_image

async def create_video():
    result = await generate_video_from_image(
        prompt_image="path/to/image.jpg",  # Local file or URL
        prompt_text="Create a dynamic video with smooth motion",
        duration=5,
        ratio="1280:720"
    )
    
    if result["success"]:
        print(f"Video generated: {result['output']}")
    else:
        print(f"Failed: {result['error']}")

# Run the async function
asyncio.run(create_video())
```

### 2. Generate Image from Text

```python
import asyncio
from app.utils.runwayml_utils import generate_image_from_text

async def create_image():
    result = await generate_image_from_text(
        prompt_text="A beautiful sunset over a mountain landscape, digital art style",
        ratio="1920:1080"
    )
    
    if result["success"]:
        print(f"Image generated: {result['output']}")
    else:
        print(f"Failed: {result['error']}")

# Run the async function
asyncio.run(create_image())
```

### 3. Generate Styled Image with Reference

```python
import asyncio
from app.utils.runwayml_utils import generate_image_with_reference_style

async def create_styled_image():
    result = await generate_image_with_reference_style(
        prompt_text="@reference in the style of @style",
        reference_image="path/to/reference.jpg",
        style_image="path/to/style.jpg",
        ratio="1024:1024"
    )
    
    if result["success"]:
        print(f"Styled image generated: {result['output']}")
    else:
        print(f"Failed: {result['error']}")

# Run the async function
asyncio.run(create_styled_image())
```

### 4. Check Service Status

```python
from app.utils.runwayml_utils import is_runwayml_available, get_runwayml_status

# Check if RunwayML is available
if is_runwayml_available():
    print("✅ RunwayML is ready to use!")
else:
    print("❌ RunwayML is not available")

# Get detailed status
status = get_runwayml_status()
print(f"Available models: {status['models']}")
print(f"Supported ratios: {status['supported_ratios']}")
```

## Supported Models

### Video Generation
- **gen4_turbo**: High-quality video generation from images

### Image Generation
- **gen4_image**: Advanced text-to-image generation with reference support

## Supported Aspect Ratios

- `1280:720` - 16:9 landscape
- `1920:1080` - 16:9 HD
- `1080:1920` - 9:16 portrait
- `720:1280` - 9:16 mobile
- `1024:1024` - 1:1 square
- `1920:1920` - 1:1 high-res square

## Supported Video Durations

3, 4, 5, 6, 7, 8, 9, 10 seconds

## Input Formats

### Images
- **Local files**: Any image format (PNG, JPG, JPEG, etc.)
- **URLs**: Direct links to images
- **Data URIs**: Base64 encoded images

### Text Prompts
- Natural language descriptions
- Style specifications
- Reference mentions using `@tag` syntax

## Error Handling

The utility functions return structured responses with success/error information:

```python
result = await generate_video_from_image(...)

if result["success"]:
    # Success case
    video_url = result["output"]
    model_used = result["model"]
else:
    # Error case
    error_message = result["error"]
    if "task_details" in result:
        task_details = result["task_details"]
```

## Examples

### Product Marketing Video

```python
async def create_product_video():
    result = await generate_video_from_image(
        prompt_image="product_photo.jpg",
        prompt_text="Show the product rotating slowly with elegant lighting",
        duration=8,
        ratio="1920:1080"
    )
    return result
```

### Brand Style Image

```python
async def create_brand_image():
    result = await generate_image_with_reference_style(
        prompt_text="@product in our brand's minimalist style",
        reference_image="product.jpg",
        style_image="brand_style.jpg",
        ratio="1024:1024"
    )
    return result
```

### Social Media Content

```python
async def create_social_content():
    result = await generate_image_from_text(
        prompt_text="Modern tech workspace with clean design, suitable for social media",
        ratio="1080:1920"  # Instagram story format
    )
    return result
```

## Troubleshooting

### Common Issues

1. **"RunwayML is not available"**
   - Check if `RUNWAYML_ENABLED=True` in your `.env`
   - Verify `RUNWAYML_API_SECRET` is set correctly
   - Ensure the `runwayml` package is installed

2. **"Video generation failed"**
   - Check your API quota and billing status
   - Verify the input image format and size
   - Ensure the prompt text follows RunwayML guidelines

3. **"Image file not found"**
   - Verify the file path exists
   - Check file permissions
   - Use absolute paths if needed

### Debug Mode

Enable debug logging to see detailed information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## API Limits and Pricing

- Check [RunwayML's pricing page](https://runwayml.com/pricing) for current rates
- Monitor your API usage through the RunwayML dashboard
- Implement rate limiting if needed for production use

## Security Considerations

- Never commit API secrets to version control
- Use environment variables for sensitive configuration
- Implement proper access controls in production
- Monitor API usage for unusual activity

## Support

- [RunwayML API Documentation](https://docs.dev.runwayml.com/)
- [RunwayML Community](https://community.runwayml.com/)
- [API Status Page](https://status.runwayml.com/)

## License

This utility module is part of the eshop-scraper project. Please refer to the main project license for usage terms.
