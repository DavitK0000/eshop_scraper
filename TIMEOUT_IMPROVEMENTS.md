# Timeout Improvements for Video Generation Service

## Overview
This document outlines the timeout improvements made to prevent `WriteTimeout` errors in the video generation service.

## Changes Made

### 1. Video Generation Service (`app/services/video_generation_service.py`)

#### Added Timeout Constants
```python
# Timeout configurations
HTTP_TIMEOUT = 300  # 5 minutes for HTTP operations
DOWNLOAD_TIMEOUT = 600  # 10 minutes for file downloads
UPLOAD_TIMEOUT = 900  # 15 minutes for file uploads
MAX_RETRIES = 3  # Maximum retry attempts for failed operations
RETRY_DELAY = 5  # Seconds to wait between retries
```

#### Updated HTTP Client Timeouts
- **Image Downloads**: Increased from default to 10 minutes (`DOWNLOAD_TIMEOUT`)
- **Video Downloads**: Increased from default to 10 minutes (`DOWNLOAD_TIMEOUT`)

#### Added Retry Logic
- Both `_store_image_in_supabase()` and `_store_video_in_supabase()` methods now include retry logic
- Up to 3 retry attempts with 5-second delays between attempts
- Better error handling and logging for timeout scenarios

### 2. Video Service (`app/services/video_service.py`)

#### Added Timeout Constant
```python
# Timeout configuration
VIDEO_DOWNLOAD_TIMEOUT = 600  # 10 minutes for video downloads
```

#### Updated HTTP Client Timeout
- Video downloads now use a 10-minute timeout instead of the default system timeout

### 3. Supabase Utils (`app/utils/supabase_utils.py`)

#### Increased Client Timeouts
```python
options=ClientOptions(
    postgrest_client_timeout=300,  # 5 minutes for database operations (was 10s)
    storage_client_timeout=900,    # 15 minutes for storage operations (was 10s)
    schema="public",
)
```

## Recommended Environment Variables

Create a `.env` file with these increased timeout values:

```bash
# Scraping Settings
DEFAULT_TIMEOUT=120

# Playwright Settings
PLAYWRIGHT_TIMEOUT=60000

# Browser Operation Timeouts
BROWSER_SCROLL_TIMEOUT=10000
BROWSER_SCROLL_WAIT_TIMEOUT=5000
BROWSER_CLEANUP_TIMEOUT=20000
BROWSER_PAGE_FETCH_TIMEOUT=300000

# MongoDB Configuration
MONGODB_SERVER_SELECTION_TIMEOUT=10000
MONGODB_CONNECT_TIMEOUT=60000
MONGODB_SOCKET_TIMEOUT=120000

# RunwayML Settings
RUNWAYML_TIMEOUT=900
```

## Key Benefits

1. **Prevents WriteTimeout Errors**: Increased timeouts prevent the `httpcore.WriteTimeout` errors
2. **Better Reliability**: Retry logic handles temporary network issues gracefully
3. **Consistent Timeouts**: All HTTP operations now use appropriate timeout values
4. **Improved Logging**: Better error messages and retry attempt tracking
5. **Scalable Configuration**: Timeout values can be easily adjusted via environment variables

## Monitoring and Debugging

### Log Messages to Watch For
- `"Attempt X failed for image/video storage: {error}. Retrying in Y seconds..."`
- `"Failed to store image/video in Supabase after X attempts: {error}"`

### Common Timeout Scenarios
1. **Large File Downloads**: Videos and high-resolution images may take longer than expected
2. **Network Congestion**: Slow network conditions during file transfers
3. **Storage Service Delays**: Supabase storage operations may be slow during peak usage

## Best Practices

1. **Monitor Logs**: Watch for retry attempts and timeout warnings
2. **Adjust Timeouts**: Increase timeout values if you continue to see timeout errors
3. **Network Quality**: Ensure stable network connection for large file operations
4. **File Sizes**: Consider file size limits and adjust timeouts accordingly

## Troubleshooting

### If Timeouts Persist
1. Check network connectivity and stability
2. Verify Supabase service status
3. Consider increasing timeout values further
4. Monitor system resources (CPU, memory, network bandwidth)

### Performance Optimization
1. Use appropriate image/video resolutions
2. Consider implementing progressive downloads for very large files
3. Monitor and optimize network usage patterns
