# Save Scenario Service

## Overview

The Save Scenario Service is a new service that handles saving AI-generated scenarios to the database and generating images for all scenes (except the first one which is already generated). This service follows the same pattern as other services in the codebase, using task management and threading for background processing.

## API Endpoints

### POST `/scenario/save`
- **Purpose**: Save a generated scenario and generate images for scenes
- **Request Body**: `SaveScenarioRequest` containing `short_id`, `user_id`, and `scenario` JSON string
- **Response**: `SaveScenarioResponse` with task ID for polling
- **Authentication**: Optional API key via Bearer token

### GET `/scenario/save/tasks/{task_id}`
- **Purpose**: Get the status of a save scenario task
- **Response**: Current task status, progress, and completion details

### DELETE `/scenario/save/tasks/{task_id}`
- **Purpose**: Cancel a running save scenario task
- **Response**: Confirmation message

## How It Works

### 1. Task Creation
- Creates a new task in the task management system with type `SAVE_SCENARIO`
- No credit check is performed at this stage
- Returns immediately with a task ID for polling

### 2. Background Processing
The service runs in a background thread and performs the following steps:

#### Step 1: Save Scenario (5-25%)
- Saves the scenario object to the `video_scenarios` table
- Extracts metadata including narrative style, target audience, demographics, etc.

#### Step 2: Save Scenes (25-65%)
- Saves all scenes to the `video_scenes` table
- Each scene includes image prompts, visual prompts, and product reference images
- Scenes are numbered sequentially

#### Step 3: Generate Images (65-90%)
- **Skips the first scene** (already generated)
- **Bulk credit check**: Verifies user has enough credits for ALL image generations upfront
- For each remaining scene:
  - Generates image using RunwayML based on `image_prompt`
  - Downloads temporary image from RunwayML
  - Uploads image to Supabase storage (`generated-content/scenes/`)
  - Deducts credits for each successful image generation
  - Updates the scene with the permanent Supabase image URL
- **Credit Model**: `scene_count * generate_image` (e.g., 5 scenes = 5 * 2 = 10 credits)
- **Image Storage**: All generated images are permanently stored in Supabase storage

#### Step 4: Finalization (90-100%)
- Updates task completion status
- Stores final results including scenario ID and scene count

### 3. Credit Management
- **No credits required** for the `save_scenario` action itself
- **Bulk credit verification**: Checks if user has enough credits for ALL image generations before starting
- Credits are deducted individually for each image generation using the existing `generate_image` action
- If a user doesn't have enough credits for all images, the entire image generation step is skipped
- Credit deduction happens only after successful image generation and upload to Supabase
- **Efficient processing**: No wasted time starting generation for users with insufficient credits

## Database Schema

### video_scenarios Table
- `short_id`: Reference to the short video
- `title`, `description`: Scenario details
- `script`: Combined audio script
- `scene_count`: Number of scenes
- `estimated_duration`: Total duration in seconds
- `metadata`: JSON containing narrative style, demographics, hashtags, etc.

### video_scenes Table
- `scenario_id`: Reference to the scenario
- `scene_number`: Sequential scene number
- `image_prompt`: AI prompt for image generation
- `visual_prompt`: Safe video prompt
- `product_reference_image_url`: Reference image from product
- `image_url`: Generated AI image URL from Supabase storage (populated after generation)
- `status`: Scene status (pending → completed)

## Error Handling

- **Database failures**: Task marked as failed
- **Image generation failures**: Individual scenes skipped, task continues
- **Credit failures**: Scenes skipped, task continues with available credits
- **RunwayML unavailability**: Image generation skipped, task completes successfully

## Usage Example

```python
from app.services.save_scenario_service import save_scenario_service
from app.models import SaveScenarioRequest
import json

# Example scenario data (this would come from your scenario generation service)
scenario_data = {
    "scenario_id": "scenario_123",
    "title": "Product Showcase Video",
    "description": "A dynamic showcase of the product features",
    "detected_demographics": {
        "target_gender": "unisex",
        "age_group": "adults",
        "product_type": "electronics",
        "demographic_context": "Tech-savvy adults interested in innovation"
    },
    "scenes": [
        {
            "scene_id": "scene_1",
            "scene_number": 1,
            "description": "Product introduction",
            "duration": 5,
            "image_prompt": "Modern smartphone on dark background with dramatic lighting",
            "visual_prompt": "Camera slowly zooms in on smartphone",
            "product_reference_image_url": "https://example.com/product.jpg",
            "image_reasoning": "Highlights the main product clearly"
        }
    ],
    "audio_script": {
        "hook": "Discover the future of technology",
        "main": "This revolutionary smartphone combines cutting-edge features with elegant design",
        "cta": "Get yours today and experience the difference",
        "hashtags": ["#TechInnovation", "#Smartphone", "#FutureTech"]
    },
    "total_duration": 15,
    "style": "modern-minimalist",
    "mood": "professional",
    "resolution": "1080:1920"
}

# Convert scenario to JSON string
scenario_json = json.dumps(scenario_data)

# Create the request
request = SaveScenarioRequest(
    short_id="short_456",
    user_id="user_789",
    scenario=scenario_json
)

# Start the save scenario task
response = save_scenario_service.start_save_scenario_task(request)

# Get task ID for polling
task_id = response["task_id"]

# Poll for completion
# GET /scenario/save/tasks/{task_id}
```

## Task Management

The service integrates with the existing task management system:
- **Task Type**: `SAVE_SCENARIO`
- **Progress Tracking**: Real-time progress updates with descriptive messages
- **Status Management**: Pending → Running → Completed/Failed
- **Metadata Storage**: Scenario details, scene counts, completion results

## Dependencies

- **Supabase**: Database operations and image storage
- **RunwayML**: AI image generation
- **Task Management**: Task lifecycle management
- **Credit System**: Credit checking and deduction for image generation
- **Requests**: HTTP operations for downloading temporary images

## Image Generation & Storage Process

### 1. RunwayML Generation
- Uses `scene.image_prompt` for AI image generation
- References `scene.product_reference_image_url` for style consistency
- Returns temporary URL to generated image

### 2. Supabase Storage
- Downloads temporary image from RunwayML
- Uploads to `generated-content/scenes/` bucket
- Generates unique filename with scene type and UUID
- Returns permanent public URL for database storage

### 3. Database Update
- Updates `video_scenes.image_url` field with Supabase URL
- Sets scene status to "completed"
- Ensures permanent image storage and accessibility

## Notes

- The first scene is always skipped for image generation (assumed to be already generated)
- Image generation is optional - if RunwayML is unavailable, the task still completes successfully
- Credit deduction is per-image, not per-scenario
- The service is designed to be resilient to individual failures

