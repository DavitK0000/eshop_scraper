# Session Feature Implementation

This document describes the session feature implementation for task management in the e-shop scraper system.

## Overview

The session feature provides tracking and management of task sessions in MongoDB. Each session is associated with a `short_id`, `task_type`, and `task_id`, allowing for better task lifecycle management and cleanup.

## Features Implemented

### 1. Session Model (`app/models.py`)
- Added `SessionInfo` Pydantic model for session data structure
- Includes fields: `short_id`, `task_type`, `task_id`, `created_at`, `updated_at`, `user_id`, `status`

### 2. Session Service (`app/services/session_service.py`)
- **SessionManager**: MongoDB connection and operation management
- **SessionService**: High-level session management operations
- **Key Methods**:
  - `create_session()`: Create a new session for a task
  - `update_session_status()`: Update session status
  - `remove_session()`: Remove a session
  - `get_session()`: Get session by task ID
  - `get_sessions_by_short_id()`: Get all sessions for a short ID
  - `cleanup_old_sessions()`: Clean up old completed/failed sessions

### 3. Task Management Integration (`app/utils/task_management.py`)
- **Session Creation**: Automatically creates sessions when tasks are created (if `short_id` is provided, except for scraping tasks)
- **Session Cleanup**: Automatically removes sessions when tasks complete, fail, or are cancelled (except for scraping and scenario-generation tasks)
- **Exception Handling**: 
  - Scraping tasks are excluded from session management entirely
  - Scenario-generation tasks are NOT automatically cleaned up (special handling)

### 4. Special Scenario Generation Handling (`app/services/save_scenario_service.py`)
- **Delayed Cleanup**: Scenario-generation task sessions are only removed when `save_scenario_service` is triggered
- **Batch Cleanup**: Finds and removes all scenario-generation sessions for a given `short_id`

### 5. Scheduler Integration (`app/services/scheduler_service.py`)
- **Automatic Cleanup**: Sessions are cleaned up along with old tasks
- **Configurable**: Sessions older than 7 days are automatically removed

### 6. API Endpoints (`app/api/routes.py`)
- `GET /sessions/{short_id}`: Get all sessions for a short ID
- `GET /sessions/task/{task_id}`: Get session information for a specific task
- `DELETE /sessions/task/{task_id}`: Manually remove a session

### 7. Application Integration (`app/main.py`)
- **Startup**: Session service is initialized on application startup
- **Shutdown**: Session service is properly cleaned up on application shutdown

## Session Lifecycle

### Normal Tasks (Non-Scenario Generation, Non-Scraping)
1. **Task Creation**: Session is created when task is created with `short_id` (except scraping tasks)
2. **Task Execution**: Session remains active during task execution
3. **Task Completion/Failure/Cancellation**: Session is automatically removed

**Note**: Video generation tasks now properly create sessions as they include `short_id` in their metadata.

### Scraping Tasks
1. **Task Creation**: No session is created for scraping tasks
2. **Task Execution**: No session tracking
3. **Task Completion/Failure/Cancellation**: No session cleanup needed

### Scenario Generation Tasks
1. **Task Creation**: Session is created when scenario generation task is created
2. **Task Execution**: Session remains active during task execution
3. **Task Completion**: Session is NOT removed (special case)
4. **Save Scenario Triggered**: Session is removed when `save_scenario_service` processes the scenario

## Database Schema

### MongoDB Collection: `sessions`
```json
{
  "_id": ObjectId,
  "short_id": "string",
  "task_type": "string",
  "task_id": "string",
  "created_at": "ISO datetime",
  "updated_at": "ISO datetime",
  "user_id": "string (optional)",
  "status": "string (active, completed, failed)"
}
```

### Indexes
- `task_id` (unique)
- `short_id`
- `task_type`
- `status`
- `created_at`
- `user_id`

## Configuration

The session service uses the same MongoDB configuration as the task management system:
- `MONGODB_URI`: MongoDB connection string
- `MONGODB_DATABASE`: Database name
- `MONGODB_POOL_SIZE`: Connection pool size
- `MONGODB_MAX_POOL_SIZE`: Maximum pool size
- `MONGODB_SERVER_SELECTION_TIMEOUT`: Server selection timeout
- `MONGODB_CONNECT_TIMEOUT`: Connection timeout
- `MONGODB_SOCKET_TIMEOUT`: Socket timeout

## Usage Examples

### Creating a Task with Session
```python
from app.utils.task_management import create_task, TaskType, TaskPriority

# This will automatically create a session if short_id is provided (except for scraping tasks)
task_id = create_task(
    TaskType.IMAGE_ANALYSIS,  # Non-scraping task
    user_id="user123",
    short_id="short_456",  # This triggers session creation
    product_id="product_123",
    priority=TaskPriority.NORMAL
)

# Scraping tasks do NOT create sessions
scraping_task_id = create_task(
    TaskType.SCRAPING,
    url="https://example.com",
    user_id="user123",
    short_id="short_456",  # This will NOT trigger session creation
    priority=TaskPriority.NORMAL
)
```

### Getting Session Information
```python
from app.services.session_service import session_service

# Get session by task ID
session = session_service.get_session(task_id)

# Get all sessions for a short ID
sessions = session_service.get_sessions_by_short_id("short_456")
```

### Manual Session Cleanup
```python
# Remove a specific session
session_service.remove_session(task_id)

# Clean up old sessions (7+ days old)
deleted_count = session_service.cleanup_old_sessions(7)
```

## API Usage

### Session Response Structure

All session API endpoints return session objects with the following structure:

```json
{
  "short_id": "string",           // Short ID associated with the session
  "task_type": "string",          // Type of task (see task types below)
  "task_id": "string",            // Unique task identifier
  "user_id": "string",            // User ID (optional)
  "status": "string",             // Session status (active, completed, failed)
  "created_at": "ISO datetime",   // When the session was created
  "updated_at": "ISO datetime"    // When the session was last updated
}
```

### Supported Task Types

The `task_type` field can have the following values:
- `image_analysis` - Image analysis tasks
- `scenario_generation` - Scenario generation tasks  
- `video_generation` - Video generation tasks
- `finalize_short` - Short finalization tasks
- `save_scenario` - Save scenario tasks
- `content_analysis` - Content analysis tasks
- `data_extraction` - Data extraction tasks

**Note:** Scraping tasks (`scraping`) are excluded from session management and will not appear in session responses.

### Get Sessions for a Short ID
```bash
GET /api/v1/sessions/short_456
```

Response:
```json
{
  "short_id": "short_456",
  "sessions": [
    {
      "short_id": "short_456",
      "task_type": "image_analysis",
      "task_id": "task_789",
      "user_id": "user123",
      "status": "active",
      "created_at": "2024-01-01T12:00:00Z",
      "updated_at": "2024-01-01T12:00:00Z"
    }
  ],
  "total_sessions": 1,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**Note:** The `task_type` field indicates the type of task associated with the session. See the supported task types section above for details.

### Get Session by Task ID
```bash
GET /api/v1/sessions/task/task_789
```

Response:
```json
{
  "short_id": "short_456",
  "task_type": "image_analysis",
  "task_id": "task_789",
  "user_id": "user123",
  "status": "active",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z"
}
```

**Note:** The `task_type` field indicates the type of task associated with this session. See the supported task types section above for details.

### Remove Session
```bash
DELETE /api/v1/sessions/task/task_789
```

## Testing

A test script is provided (`test_session_feature.py`) that tests:
- Session creation and retrieval
- Session cleanup
- Task integration with sessions
- Scenario generation session behavior

Run the test:
```bash
python test_session_feature.py
```

## Error Handling

- **MongoDB Unavailable**: Session operations gracefully degrade when MongoDB is not available
- **Connection Issues**: Automatic reconnection attempts with proper error logging
- **Invalid Data**: Proper validation and error responses for invalid session data

## Performance Considerations

- **Indexes**: Proper indexing for fast lookups by `task_id`, `short_id`, and other fields
- **Connection Pooling**: Reuses MongoDB connection pool for efficient database operations
- **Batch Operations**: Efficient batch cleanup of old sessions
- **Fallback Handling**: Graceful degradation when MongoDB is unavailable

## Monitoring and Logging

- **Comprehensive Logging**: All session operations are logged with appropriate levels
- **Error Tracking**: Detailed error logging for troubleshooting
- **Performance Metrics**: Session creation, update, and cleanup operations are tracked

## Future Enhancements

Potential future improvements could include:
- Session analytics and reporting
- Session-based rate limiting
- Session state persistence across application restarts
- Advanced session filtering and search capabilities
- Session-based user activity tracking
