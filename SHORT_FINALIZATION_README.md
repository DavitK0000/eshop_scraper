# Short Finalization API

This document describes the new API endpoints for finalizing short videos by merging generated scenes, generating thumbnails, and optionally upscaling the final video.

## Overview

The short finalization process combines multiple video scenes into a single final video, generates a professional thumbnail, and optionally upscales the video quality. This is the final step in the video creation pipeline.

## API Endpoints

### 1. Start Short Finalization

**POST** `/shorts/finalize`

Starts the finalization process for a short video.

#### Request Body

```json
{
  "user_id": "uuid-string",
  "short_id": "uuid-string", 
  "upscale": false
}
```

#### Parameters

- `user_id` (required): The UUID of the user requesting the finalization
- `short_id` (required): The UUID of the short to finalize
- `upscale` (optional): Whether to upscale the final video (default: false)

#### Response

```json
{
  "task_id": "uuid-string",
  "status": "pending",
  "short_id": "uuid-string",
  "user_id": "uuid-string",
  "message": "Finalization task started",
  "created_at": "2024-01-01T00:00:00",
  "progress": 0.0,
  "current_step": "Initializing"
}
```

### 2. Get Finalization Task Status

**GET** `/shorts/finalize/tasks/{task_id}`

Retrieves the current status of a finalization task.

#### Response

```json
{
  "task_id": "uuid-string",
  "status": "completed",
  "short_id": "uuid-string",
  "user_id": "uuid-string",
  "message": "Finalization completed successfully",
  "created_at": "2024-01-01T00:00:00",
  "progress": 100.0,
  "current_step": "Finalizing results",
  "thumbnail_url": "https://example.com/thumbnail.png",
  "final_video_url": "https://example.com/final-video.mp4",
  "completed_at": "2024-01-01T00:05:00"
}
```

### 3. Cancel Finalization Task

**DELETE** `/shorts/finalize/tasks/{task_id}`

Cancels a running finalization task.

#### Response

```json
{
  "message": "Short finalization task {task_id} cancelled successfully"
}
```

### 4. Cleanup Finalization Tasks

**DELETE** `/shorts/finalize/tasks`

Cleans up old completed/failed finalization tasks.

#### Response

```json
{
  "message": "Short finalization task cleanup completed"
}
```

## Finalization Process

The finalization process follows these steps:

1. **Fetch Video Scenes**: Retrieves all completed video scenes for the short
2. **Generate Thumbnail**: Creates a professional thumbnail using RunwayML AI
3. **Download Videos**: Downloads all scene videos to temporary storage
4. **Merge Videos**: Combines videos using FFmpeg in the correct order
5. **Add Watermark**: Adds watermark for free plan users
6. **Upscale (Optional)**: Upscales video if requested
7. **Upload Final Video**: Stores the final video in Supabase storage
8. **Update Database**: Updates the shorts table with final URLs

## Credit Requirements

- **Thumbnail Generation**: 2 credits (uses `generate_image` action)
- **Video Upscaling**: 5 credits per second of video duration (uses `upscale_video` action)

## Plan Restrictions

- **Free Plan**: Automatically adds "PromoNexAI" watermark to final videos
- **Paid Plans**: No watermark added
- **Upscaling**: Available on Professional and Enterprise plans only

## Storage Structure

- **Thumbnails**: Stored in `thumbnail_images/{user_id}/{uuid}.png`
- **Final Videos**: Stored in `final_videos/{short_id}/{uuid}.mp4`

## Database Updates

The finalization process updates the following fields in the `shorts` table:

- `thumbnail_url`: URL of the generated thumbnail
- `video_url`: URL of the final merged video
- `status`: Set to 'completed'
- `updated_at`: Timestamp of completion

## Error Handling

The service includes comprehensive error handling:

- Credit validation before starting operations
- File download/upload retry logic
- Temporary file cleanup
- Detailed error logging
- Graceful fallbacks for non-critical operations

## Polling Pattern

Like other API endpoints, this uses a polling pattern:

1. Call `/shorts/finalize` to start the process
2. Receive a `task_id`
3. Poll `/shorts/finalize/tasks/{task_id}` to check progress
4. Continue polling until `status` is "completed" or "failed"

## Example Usage

### Start Finalization

```bash
curl -X POST "http://localhost:8000/shorts/finalize" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "short_id": "987fcdeb-51a2-43d1-9f12-345678901234",
    "upscale": true
  }'
```

### Check Status

```bash
curl "http://localhost:8000/shorts/finalize/tasks/{task_id}"
```

### Cancel Task

```bash
curl -X DELETE "http://localhost:8000/shorts/finalize/tasks/{task_id}"
```

## Dependencies

- **FFmpeg**: Required for video merging and watermarking
- **RunwayML**: Required for AI-powered thumbnail generation and upscaling
- **Supabase**: Required for database operations and file storage
- **httpx**: Required for HTTP operations (downloading files)

## Configuration

Ensure the following environment variables are set:

- `RUNWAYML_ENABLED`: Set to `true` to enable AI features
- `RUNWAYML_API_SECRET`: Your RunwayML API key
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_ANON_KEY`: Your Supabase anonymous key

## Troubleshooting

### Common Issues

1. **FFmpeg not found**: Install FFmpeg and ensure it's in your PATH
2. **Insufficient credits**: Check user's credit balance and plan
3. **Storage errors**: Verify Supabase storage bucket permissions
4. **RunwayML errors**: Check API key and service availability

### Logs

Check the application logs for detailed error information:

- `logs/app.log`: General application logs
- `logs/errors.log`: Error-specific logs
- `logs/debug.log`: Debug information (if enabled)

## Security Notes

- API key authentication is supported but disabled in development
- User ID validation ensures users can only finalize their own shorts
- Credit checks prevent abuse of AI generation features
- File uploads are validated and sanitized
