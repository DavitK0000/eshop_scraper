# Test Audio Endpoint

This document describes the new test audio endpoint that generates and caches test audio samples using ElevenLabs.

## Overview

The test audio endpoint allows users to get test audio samples for specific voice IDs and languages. It checks if the audio already exists in MongoDB and returns it, or generates new audio using ElevenLabs and uploads it to Supabase storage if it doesn't exist.

## Endpoint

```
POST /api/v1/test-audio
```

## Request Body

```json
{
  "voice_id": "string",
  "language": "string", 
  "user_id": "string"
}
```

### Parameters

- `voice_id` (required): ElevenLabs voice ID for audio generation
- `language` (required): Language code for the test audio
- `user_id` (required): User ID associated with the request

### Supported Languages

- `en-US` - English (United States)
- `en-CA` - English (Canada)
- `en-GB` - English (United Kingdom)
- `es` - Spanish
- `es-MX` - Spanish (Mexico)
- `pt-BR` - Portuguese (Brazil)
- `fr` - French
- `de` - German
- `nl` - Dutch

## Response

```json
{
  "voice_id": "string",
  "language": "string",
  "audio_url": "string",
  "user_id": "string",
  "created_at": "datetime",
  "is_cached": "boolean",
  "message": "string"
}
```

### Response Fields

- `voice_id`: Voice ID used for test audio
- `language`: Language code used
- `audio_url`: URL of the test audio
- `user_id`: User ID who requested the audio
- `created_at`: When the test audio was generated
- `is_cached`: Whether this was a cached result
- `message`: Status message

## Example Usage

### cURL

```bash
curl -X POST "http://localhost:8000/api/v1/test-audio" \
  -H "Content-Type: application/json" \
  -d '{
    "voice_id": "JBFqnCBsd6RMkjVDRZzb",
    "language": "en-US",
    "user_id": "user123"
  }'
```

### Python

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/test-audio",
    json={
        "voice_id": "JBFqnCBsd6RMkjVDRZzb",
        "language": "en-US", 
        "user_id": "user123"
    }
)

result = response.json()
print(f"Audio URL: {result['audio_url']}")
print(f"Cached: {result['is_cached']}")
```

### JavaScript

```javascript
const response = await fetch('http://localhost:8000/api/v1/test-audio', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    voice_id: 'JBFqnCBsd6RMkjVDRZzb',
    language: 'en-US',
    user_id: 'user123'
  })
});

const result = await response.json();
console.log('Audio URL:', result.audio_url);
console.log('Cached:', result.is_cached);
```

## Configuration

Add the following environment variables to your `.env` file:

```env
# ElevenLabs Settings
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
ELEVENLABS_ENABLED=True
ELEVENLABS_DEFAULT_MODEL=eleven_multilingual_v2
ELEVENLABS_DEFAULT_OUTPUT_FORMAT=mp3_44100_128
ELEVENLABS_MAX_RETRIES=3
ELEVENLABS_TIMEOUT=60
```

## Storage

### Supabase Storage
- **Bucket**: `test-audios` (publicly accessible)
- **File Path**: `test-audios/{voice_id}_{language}_{uuid}.mp3`
- **Content Type**: `audio/mpeg`
- **Access**: Public URLs for direct access

### MongoDB Schema

The service stores test audio information in MongoDB in the `test_audio` collection:

```json
{
  "_id": "ObjectId",
  "voice_id": "string",
  "language": "string", 
  "audio_url": "string",
  "user_id": "string",
  "type": "test_audio",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

The `audio_url` field contains the public Supabase storage URL.

## Error Handling

- **400 Bad Request**: Invalid request data
- **500 Internal Server Error**: Server error during processing

Common error scenarios:
- Unsupported language code
- Invalid voice ID
- ElevenLabs API errors
- MongoDB connection issues
- Supabase storage errors
- Bucket creation failures

## Testing

Run the test script to verify the endpoint:

```bash
python test_audio_endpoint.py
```

This will test:
- Basic functionality with valid data
- Multiple language support
- Invalid language handling
- Caching behavior

## Notes

- The service uses ElevenLabs' `eleven_multilingual_v2` model by default
- Audio is generated in MP3 format with 44.1kHz sample rate and 128kbps bitrate
- Test audio is cached in MongoDB to avoid regenerating the same voice/language combinations
- Audio files are stored in Supabase storage bucket `test-audios` with public access
- The service automatically creates the `test-audios` bucket if it doesn't exist
- The service includes appropriate test text for each supported language
- Generated audio URLs are publicly accessible Supabase storage URLs
