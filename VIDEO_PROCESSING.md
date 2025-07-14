# Video Processing API

This document describes the video processing functionality added to the eShop scraper API.

## Overview

The video processing API allows you to:
- Merge multiple videos from URLs in sequence (videos should be 1920x1080)
- Add audio from base64 encoded data
- Embed subtitles directly into the video (optional)
- Return the final video as base64 encoded data

## Prerequisites

### FFmpeg Installation

The video processing requires FFmpeg to be installed on your system:

**Windows:**
1. Download FFmpeg from https://ffmpeg.org/download.html
2. Extract to a folder (e.g., `C:\ffmpeg`)
3. Add the `bin` folder to your system PATH
4. Verify installation: `ffmpeg -version`

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

## API Endpoints

### 1. Process Video

**POST** `/video/process`

Start a video processing task.

**Request Body:**
```json
{
  "video_urls": [
    "https://example.com/video1.mp4",
    "https://example.com/video2.mp4"
  ],
  "audio_data": "base64_encoded_audio_data",
  "subtitle_text": "Your subtitle text here",
  "output_resolution": "1920x1080"
}
```

**Note:** `subtitle_text` is optional. If not provided or set to `null`, the video will be processed without subtitles.

**Response:**
```json
{
  "task_id": "uuid-string",
  "status": "pending",
  "video_data": null,
  "error": null,
  "created_at": "2024-01-01T12:00:00",
  "completed_at": null
}
```

### 2. Get Task Status

**GET** `/video/tasks/{task_id}`

Check the status of a video processing task.

**Response:**
```json
{
  "task_id": "uuid-string",
  "status": "completed",
  "video_data": "base64_encoded_video_data",
  "error": null,
  "created_at": "2024-01-01T12:00:00",
  "completed_at": "2024-01-01T12:05:00"
}
```

### 3. Get All Tasks

**GET** `/video/tasks`

Get all video processing tasks.

**Response:**
```json
[
  {
    "task_id": "uuid-string",
    "status": "completed",
    "video_data": "base64_encoded_video_data",
    "error": null,
    "created_at": "2024-01-01T12:00:00",
    "completed_at": "2024-01-01T12:05:00"
  }
]
```

## Task Status Values

- `pending`: Task is queued for processing
- `running`: Task is currently being processed
- `completed`: Task completed successfully
- `failed`: Task failed with an error

## Usage Example

### Python Client

```python
import asyncio
import httpx
import base64

async def process_video():
    async with httpx.AsyncClient() as client:
        # Start processing
        response = await client.post(
            "http://localhost:8000/video/process",
            json={
                "video_urls": [
                    "https://example.com/video1.mp4",
                    "https://example.com/video2.mp4"
                ],
                "audio_data": "base64_audio_data_here",
                "subtitle_text": "Sample subtitle",
                "output_resolution": "1920x1080"
            }
        )
        
        result = response.json()
        task_id = result["task_id"]
        
        # Poll for completion
        while True:
            status_response = await client.get(f"http://localhost:8000/video/tasks/{task_id}")
            task_status = status_response.json()
            
            if task_status["status"] == "completed":
                video_data = task_status["video_data"]
                # Save video
                with open("output.mp4", "wb") as f:
                    f.write(base64.b64decode(video_data))
                break
            elif task_status["status"] == "failed":
                print(f"Error: {task_status['error']}")
                break
            
            await asyncio.sleep(2)

# Run the example
asyncio.run(process_video())
```

### cURL Example

```bash
# Start video processing with subtitles
curl -X POST "http://localhost:8000/video/process" \
  -H "Content-Type: application/json" \
  -d '{
    "video_urls": ["https://example.com/video1.mp4"],
    "audio_data": "base64_audio_data",
    "subtitle_text": "Sample subtitle",
    "output_resolution": "1920x1080"
  }'

# Start video processing without subtitles
curl -X POST "http://localhost:8000/video/process" \
  -H "Content-Type: application/json" \
  -d '{
    "video_urls": ["https://example.com/video1.mp4"],
    "audio_data": "base64_audio_data",
    "subtitle_text": null,
    "output_resolution": "1920x1080"
  }'

# Check status
curl "http://localhost:8000/video/tasks/{task_id}"
```

## Processing Steps

1. **Download Videos**: All video URLs are downloaded to temporary files
2. **Process Audio**: Base64 audio data is decoded and saved
3. **Create Subtitles** (if provided): Subtitle text is converted to SRT format
4. **Merge Videos**: Videos are concatenated in order using FFmpeg
5. **Add Audio & Subtitles**: 
   - If subtitles provided: Audio is mixed and subtitles are burned into the video
   - If no subtitles: Only audio is added to the video
6. **Encode**: Final video is encoded to base64

## Error Handling

Common errors and solutions:

- **FFmpeg not found**: Install FFmpeg and ensure it's in your PATH
- **Invalid video URLs**: Ensure all video URLs are accessible
- **Invalid audio data**: Ensure audio data is properly base64 encoded
- **Memory issues**: Large videos may require more system memory

## Performance Considerations

- Video processing is CPU and memory intensive
- Large videos may take significant time to process
- Consider implementing queue management for production use
- Temporary files are automatically cleaned up after processing

## Security Notes

- Video URLs should be from trusted sources
- Base64 data can be large; consider implementing size limits
- The API currently has security validation disabled for development 