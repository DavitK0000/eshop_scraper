# Scenario Generation API

This document describes the new Scenario Generation API endpoint that creates AI-powered video scenarios for products.

## Overview

The Scenario Generation API generates complete video scenarios including:
- Multiple scenes with detailed descriptions
- Image prompts for RunwayML image generation
- Video prompts for video generation
- Audio scripts with proper timing
- Demographic detection for character consistency
- Preview image generation for the first scene

## Endpoints

### 1. Generate Scenario

**POST** `/scenario/generate`

Starts a scenario generation task asynchronously.

#### Request Body

```json
{
  "short_id": "optional-existing-short-id",
  "product_id": "required-product-id",
  "user_id": "required-user-id",
  "style": "trendy-influencer-vlog",
  "mood": "energetic",
  "video_length": 30,
  "resolution": "720:1280",
  "target_language": "en-US"
}
```

#### Parameters

- **short_id** (optional): ID of existing short to update
- **product_id** (required): ID of product to generate scenario for
- **user_id** (required): ID of user requesting the scenario
- **style** (required): Video style (e.g., "trendy-influencer-vlog", "cinematic-storytelling")
- **mood** (required): Video mood (e.g., "energetic", "calm", "professional")
- **video_length** (required): Video duration in seconds (15, 20, 30, 45, or 60)
- **resolution** (required): Video resolution (e.g., "720:1280", "1280:720")
- **target_language** (required): Target language for content (e.g., "en-US", "es-ES")

#### Response

```json
{
  "task_id": "generated-task-id",
  "status": "pending",
  "short_id": "",
  "user_id": "user-id",
  "message": "Scenario generation task started",
  "created_at": "2024-01-01T00:00:00Z",
  "progress": 0.0,
  "current_step": "Starting scenario generation",
  "error_message": null,
  "scenario": null,
  "completed_at": null
}
```

### 2. Get Task Status

**GET** `/scenario/generate/tasks/{task_id}`

Get the current status of a scenario generation task.

#### Response

```json
{
  "task_id": "task-id",
  "status": "completed",
  "short_id": "generated-short-id",
  "user_id": "user-id",
  "message": "Scenario generation completed",
  "created_at": "2024-01-01T00:00:00Z",
  "progress": 100.0,
  "current_step": "Scenario generation completed",
  "error_message": null,
  "scenario": {
    "scenario_id": "scenario-123",
    "title": "Generated Scenario",
    "description": "Scenario description",
    "narrative_style": "Storytelling approach",
    "target_audience": "General audience",
    "detected_demographics": {
      "target_gender": "unisex",
      "age_group": "all-ages",
      "product_type": "general",
      "demographic_context": "Gender-neutral characters/models throughout"
    },
    "scenes": [
      {
        "scene_id": "scene-1",
        "description": "Scene description",
        "duration": 5,
        "image_prompt": "Detailed image prompt for RunwayML",
        "visual_prompt": "Safe video prompt",
        "image_url": "Reference image URL",
        "image_reasoning": "Why this image was chosen",
        "generated_image_url": "Generated preview image URL"
      }
    ],
    "audio_script": {
      "hook": "Attention-grabbing opening",
      "main": "Main content about product benefits",
      "cta": "Call-to-action",
      "hashtags": ["#fyp", "#viral", "#trending"]
    }
  },
  "completed_at": "2024-01-01T00:01:00Z"
}
```

### 3. Cancel Task

**DELETE** `/scenario/generate/tasks/{task_id}`

Cancel a running scenario generation task.

#### Response

```json
{
  "message": "Scenario generation task task-id cancelled successfully"
}
```

## Features

### AI-Powered Generation
- Uses OpenAI GPT-4o-mini for scenario generation
- Automatically detects product demographics
- Maintains character consistency throughout scenes
- Generates family-friendly, professional content

### Image Generation
- Generates preview image for first scene using RunwayML
- Maps video resolutions to optimal image generation ratios
- Enhances prompts with style and mood specific details
- Uses product images as reference for better results

### Scene Structure
- Each scene is exactly 5 seconds
- Proper narrative flow and timing
- Audio script timing: Hook (20-25%), Main (50-60%), CTA (15-20%)

### Credit System
- Requires "generate_scenario" action credits
- Single credit deduction per scenario
- Credit validation before task starts

## Usage Examples

### Python Client

```python
import requests

# Start scenario generation
response = requests.post("http://localhost:8000/scenario/generate", json={
    "product_id": "product-123",
    "user_id": "user-456",
    "style": "trendy-influencer-vlog",
    "mood": "energetic",
    "video_length": 30,
    "resolution": "720:1280",
    "target_language": "en-US"
})

task_id = response.json()["task_id"]

# Poll for completion
while True:
    status_response = requests.get(f"http://localhost:8000/scenario/generate/tasks/{task_id}")
    status_data = status_response.json()
    
    if status_data["status"] in ["completed", "failed"]:
        if status_data["status"] == "completed":
            scenario = status_data["scenario"]
            print(f"Scenario generated: {scenario['title']}")
            print(f"Preview image: {scenario['scenes'][0]['generated_image_url']}")
        else:
            print(f"Task failed: {status_data['error_message']}")
        break
    
    time.sleep(2)
```

### cURL

```bash
# Start scenario generation
curl -X POST "http://localhost:8000/scenario/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "product-123",
    "user_id": "user-456",
    "style": "trendy-influencer-vlog",
    "mood": "energetic",
    "video_length": 30,
    "resolution": "720:1280",
    "target_language": "en-US"
  }'

# Check status
curl "http://localhost:8000/scenario/generate/tasks/{task_id}"

# Cancel task
curl -X DELETE "http://localhost:8000/scenario/generate/tasks/{task_id}"
```

## Error Handling

The API returns appropriate HTTP status codes:

- **200**: Success
- **400**: Bad request (missing required fields, invalid video length)
- **401**: Authentication required
- **402**: Insufficient credits
- **404**: Task not found
- **500**: Internal server error

## Configuration

Make sure the following environment variables are set:

- `OPENAI_API_KEY`: OpenAI API key for scenario generation
- `RUNWAYML_ENABLED`: Enable RunwayML image generation
- `RUNWAYML_API_SECRET`: RunwayML API secret for image generation

## Notes

- Tasks run asynchronously using threading and asyncio
- Progress updates are available during execution
- Preview image is generated only for the first scene
- All content is generated in the specified target language
- Character demographics are automatically detected and maintained consistently
