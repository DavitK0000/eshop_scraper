# Video Generation Service

This document describes the comprehensive video generation service that generates videos from scenes using AI-powered image and video generation via RunwayML, with intelligent resolution mapping and secure storage.

## 🚀 Overview

The video generation service provides a complete pipeline for:
1. **AI Image Generation** from text prompts and reference images using RunwayML
2. **AI Video Generation** from generated images using RunwayML's video capabilities
3. **Intelligent Resolution Mapping** between video and image generation ratios
4. **Secure Storage** with signed URLs for videos and public URLs for images
5. **Credit Management** with automatic deduction for AI operations
6. **Real-time Progress Tracking** with detailed step-by-step updates
7. **Automatic Bucket Creation** for Supabase storage

## ✨ Key Features

### 🔄 Resolution Mapping System
The service automatically maps video generation resolutions to optimal image generation ratios:

| Video Resolution | Video Ratio | Image Ratio | Description |
|------------------|-------------|-------------|-------------|
| `1280:720` | `1280:720` | `1920:1080` | 16:9 Landscape → Full HD |
| `720:1280` | `720:1280` | `1080:1920` | 9:16 Portrait → Full HD Portrait |
| `1104:832` | `1104:832` | `1168:880` | 4:3 Landscape → 4:3 HD |
| `832:1104` | `832:1104` | `1080:1440` | 3:4 Portrait → 3:4 HD |
| `960:960` | `960:960` | `1024:1024` | 1:1 Square → Full HD Square |
| `1584:672` | `1584:672` | `1920:1080` | 21:9 Ultra-wide → 16:9 |
| `1280:768` | `1280:768` | `1920:1080` | 16:9 HD+ → 16:9 |
| `768:1280` | `768:1280` | `1080:1920` | 9:16 HD → 9:16 |

### 🔐 Security Features
- **Videos**: Stored with signed URLs (1-hour expiration) for secure access
- **Images**: Stored with public URLs for easy sharing
- **Automatic bucket creation** with proper security settings
- **User isolation** ensuring users can only access their own content

### 📊 Enhanced Progress Tracking
Real-time progress updates with meaningful step descriptions:

| Step | Progress | Description |
|------|----------|-------------|
| 0 | 5% | Initializing video generation pipeline |
| 1 | 15% | Fetching scene configuration and prompts |
| 2 | 35% → 40% | Generating scene image with AI → Storing generated image |
| 3 | 70% → 75% | Creating video from generated image → Storing generated video |
| 4 | 95% | Saving results and finalizing |

## 🏗️ Architecture

### Service Components
- **VideoGenerationService**: Main orchestration service
- **RunwayML Integration**: AI image and video generation
- **Supabase Storage**: Secure content storage
- **Credit Management**: Usage tracking and deduction
- **Task Management**: Background processing and status tracking

### Data Flow
```
Scene Request → Resolution Lookup → Image Generation → Video Generation → Storage → Task Completion
     ↓              ↓                    ↓                ↓              ↓           ↓
  Scene ID    Scenario Table      RunwayML API     RunwayML API   Supabase    Database Update
```

## 📡 API Endpoints

### 1. Start Video Generation

**POST** `/api/video/generate`

Starts a video generation task with automatic resolution detection and mapping.

**Request Body:**
```json
{
  "scene_id": "uuid-of-scene",
  "user_id": "uuid-of-user"
}
```

**Response:**
```json
{
  "task_id": "generated-task-uuid",
  "status": "pending",
  "scene_id": "uuid-of-scene",
  "user_id": "uuid-of-user",
  "message": "Video generation task started",
  "created_at": "2024-01-01T00:00:00Z",
  "progress": 0.0,
  "current_step": "Initializing",
  "error_message": null
}
```

### 2. Get Task Status

**GET** `/api/video/generate/tasks/{task_id}`

Retrieves detailed task status including the generated video URL (signed URL).

**Response:**
```json
{
  "task_id": "task-uuid",
  "status": "completed",
  "scene_id": "scene-uuid",
  "user_id": "user-uuid",
  "progress": 100.0,
  "current_step": "Completed",
  "message": "Video generation completed successfully",
  "video_url": "https://xxx.supabase.co/storage/v1/object/sign/video-files/...",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:05:00Z",
  "error_message": null
}
```

### 3. Get All Tasks

**GET** `/api/video/generate/tasks`

Retrieves all video generation tasks for the authenticated user.

## 🗄️ Database Schema

### Required Tables

#### `video_scenes`
```sql
CREATE TABLE video_scenes (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    scenario_id UUID NOT NULL,
    image_prompt TEXT,
    visual_prompt TEXT,
    product_reference_image_url TEXT,
    duration INTEGER DEFAULT 5,
    image_url TEXT,
    generated_video_url TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### `video_scenarios`
```sql
CREATE TABLE video_scenarios (
    id UUID PRIMARY KEY,
    resolution TEXT NOT NULL, -- e.g., "1280:720", "720:1280"
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Resolution Lookup Flow
1. Get `scenario_id` from `video_scenes` table
2. Query `video_scenarios` table for `resolution` field
3. Apply resolution mapping for optimal image/video generation

## 💾 Storage Configuration

### Automatic Bucket Creation
The service automatically creates required storage buckets if they don't exist:

#### `generated-content` Bucket
- **Purpose**: Store generated images
- **Access**: Public (for easy sharing)
- **Path**: `generated_images/{user_id}/{uuid}.png`
- **Content-Type**: `image/png`

#### `video-files` Bucket
- **Purpose**: Store generated videos
- **Access**: Private (secure access via signed URLs)
- **Path**: `video-files/{user_id}/{uuid}.mp4`
- **Content-Type**: `video/mp4`
- **Security**: Signed URLs with 1-hour expiration

### URL Structure
- **Images**: `https://xxx.supabase.co/storage/v1/object/public/generated-content/...`
- **Videos**: `https://xxx.supabase.co/storage/v1/object/sign/video-files/...?token=...`

## 💳 Credit System

### Credit Requirements
- **Image Generation**: `generate_image` action credits
- **Video Generation**: `generate_scene` action credits

### Credit Deduction
- Credits are checked before generation
- Deduction occurs only after successful generation
- Automatic credit validation prevents abuse

## 🔧 Configuration

### Environment Variables
```bash
# RunwayML Configuration
RUNWAYML_ENABLED=true
RUNWAYML_API_SECRET=your_runwayml_api_secret

# Supabase Configuration
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# Storage Configuration
STORAGE_BUCKET_IMAGES=generated-content
STORAGE_BUCKET_VIDEOS=video-files
```

### Service Initialization
```python
from app.services.video_generation_service import video_generation_service

# Start video generation
result = video_generation_service.start_video_generation_task(
    scene_id="scene-uuid",
    user_id="user-uuid"
)

# Check status
status = video_generation_service.get_task_status(result['task_id'])
```

## 📱 Usage Examples

### Python Client
```python
import requests
import time

# Start generation
response = requests.post("http://localhost:8000/api/video/generate", json={
    "scene_id": "scene-uuid",
    "user_id": "user-uuid"
})
task_id = response.json()['task_id']

# Poll for completion
while True:
    status_response = requests.get(f"http://localhost:8000/api/video/generate/tasks/{task_id}")
    status_data = status_response.json()
    
    print(f"Status: {status_data['status']}, Progress: {status_data['progress']}%")
    print(f"Step: {status_data['current_step']}")
    
    if status_data['status'] in ['completed', 'failed']:
        if status_data['status'] == 'completed':
            print(f"Video URL: {status_data['video_url']}")
        else:
            print(f"Error: {status_data['error_message']}")
        break
    
    time.sleep(5)
```

### cURL Commands
```bash
# Start generation
curl -X POST "http://localhost:8000/api/video/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "scene_id": "123e4567-e89b-12d3-a456-426614174000",
    "user_id": "987fcdeb-51a2-43d1-9f12-345678901234"
  }'

# Check status
curl "http://localhost:8000/api/video/generate/tasks/{task_id}"

# Monitor progress
while true; do
  response=$(curl -s "http://localhost:8000/api/video/generate/tasks/{task_id}")
  status=$(echo $response | jq -r '.status')
  progress=$(echo $response | jq -r '.progress')
  step=$(echo $response | jq -r '.current_step')
  echo "Status: $status, Progress: $progress%, Step: $step"
  
  if [ "$status" = "completed" ] || [ "$status" = "failed" ]; then
    if [ "$status" = "completed" ]; then
      video_url=$(echo $response | jq -r '.video_url')
      echo "Video URL: $video_url"
    else
      error=$(echo $response | jq -r '.error_message')
      echo "Error: $error"
    fi
    break
  fi
  
  sleep 5
done
```

## 🚨 Error Handling

### Common Error Scenarios
1. **Scene Not Found**: Verify scene_id exists in database
2. **Insufficient Credits**: Check user's credit balance
3. **Resolution Not Found**: Ensure scenario has resolution field
4. **Storage Bucket Issues**: Service auto-creates buckets
5. **RunwayML API Errors**: Check API key and service status

### Error Response Format
```json
{
  "error": "Error description",
  "details": "Additional error information",
  "code": "ERROR_CODE",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## 🔍 Troubleshooting

### Debug Logging
Enable detailed logging for troubleshooting:
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Service logs include:
# - Resolution mapping details
# - RunwayML API responses
# - Storage operations
# - Progress updates
# - Error details
```

### Common Issues & Solutions

#### 1. "Bucket not found" Error
- **Cause**: Storage bucket doesn't exist
- **Solution**: Service automatically creates buckets
- **Check**: Verify Supabase permissions

#### 2. "Resolution not found" Error
- **Cause**: Missing resolution in video_scenarios table
- **Solution**: Add resolution field to scenario
- **Default**: Falls back to "720:1280" (portrait)

#### 3. "Insufficient credits" Error
- **Cause**: User doesn't have enough credits
- **Solution**: Check credit balance and recharge
- **Action**: Credits are checked before generation

#### 4. "RunwayML API error" Error
- **Cause**: API key invalid or service unavailable
- **Solution**: Verify RUNWAYML_API_SECRET
- **Check**: RunwayML service status

## 🧪 Testing

### Test Script
```bash
# Run comprehensive tests
python -m pytest tests/test_video_generation.py -v

# Test specific components
python -m pytest tests/test_video_generation.py::test_resolution_mapping -v
python -m pytest tests/test_video_generation.py::test_signed_urls -v
```

### Manual Testing
```python
# Test resolution mapping
from app.services.video_generation_service import VideoGenerationService
service = VideoGenerationService()

# Test different resolutions
mapping = service._get_resolution_mapping("1280:720")
print(mapping)  # Should return video_ratio and image_ratio

# Test scenario resolution lookup
resolution = service._get_scenario_resolution("scene-uuid")
print(resolution)  # Should return resolution from database
```

## 📈 Performance & Monitoring

### Metrics to Monitor
- **Generation Time**: Image and video generation duration
- **Success Rate**: Percentage of successful generations
- **Error Rates**: Common failure patterns
- **Storage Usage**: Bucket size and growth
- **Credit Consumption**: Usage patterns and trends

### Log Analysis
```bash
# Monitor generation progress
tail -f logs/app.log | grep "Video generation"

# Check error patterns
grep "ERROR" logs/app.log | grep "video_generation"

# Monitor storage operations
grep "Stored.*Supabase" logs/app.log
```

## 🔮 Future Enhancements

### Planned Features
- **Batch Processing**: Generate multiple scenes simultaneously
- **Quality Presets**: Different quality levels for different use cases
- **Caching System**: Cache frequently used prompts and results
- **Webhook Support**: Real-time notifications on completion
- **Analytics Dashboard**: Generation statistics and insights

### Integration Opportunities
- **CDN Integration**: Automatic CDN distribution
- **Video Editing**: Post-generation editing capabilities
- **Format Conversion**: Multiple output formats
- **Compression**: Automatic video optimization

## 📞 Support & Documentation

### Getting Help
1. **Check Logs**: Detailed error information in application logs
2. **Verify Configuration**: Environment variables and database setup
3. **Test Components**: Use provided test scripts
4. **Monitor Progress**: Real-time status updates via API

### Additional Resources
- **API Documentation**: Swagger/OpenAPI specs
- **Code Examples**: GitHub repository with samples
- **Troubleshooting Guide**: Common issues and solutions
- **Performance Tips**: Optimization recommendations

---

**Last Updated**: January 2025  
**Version**: 2.0.0  
**Service**: Video Generation Service  
**Status**: Production Ready ✅
