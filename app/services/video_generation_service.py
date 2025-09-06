"""
Video Generation Service

This module provides video generation capabilities including:
- Image generation using Flux API (Black Forest Labs)
- Video generation from images using Google Gemini
- Credit management and deduction
- Supabase storage integration
- Task management integration
"""

import os
import uuid
import threading
import tempfile
import httpx
import base64
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

from app.logging_config import get_logger
from app.utils.gemini_utils import generate_video_with_prompt_and_image
from app.utils.flux_utils import flux_manager
from app.utils.supabase_utils import supabase_manager
from app.utils.credit_utils import credit_manager
from app.utils.task_management import (
    create_task, start_task, update_task_progress,
    complete_task, fail_task, get_task_status,
    TaskType
)
from app.models import TaskStatus
from app.config import settings

logger = get_logger(__name__)

# Timeout configurations
HTTP_TIMEOUT = 300  # 5 minutes for HTTP operations
DOWNLOAD_TIMEOUT = 600  # 10 minutes for file downloads
UPLOAD_TIMEOUT = 900  # 15 minutes for file uploads
MAX_RETRIES = 3  # Maximum retry attempts for failed operations
RETRY_DELAY = 5  # Seconds to wait between retries


class VideoGenerationService:
    """Service for generating videos from scenes using AI generation."""

    def __init__(self):
        self._active_threads: Dict[str, threading.Thread] = {}

    def _get_resolution_mapping(self, video_resolution: str) -> Dict[str, str]:
        """
        Map video generation ratios to Gemini's supported aspect ratios.

        Args:
            video_resolution: Resolution from video_scenarios table (e.g., "1280:720")

        Returns:
            Dict with 'video_ratio' and 'image_ratio' keys
        """
        mapping = {
            # 16:9 landscape
            "1280:720": {"video_ratio": "16:9", "image_ratio": "16:9"},
            # 9:16 portrait
            "720:1280": {"video_ratio": "9:16", "image_ratio": "9:16"},
            # 4:3 landscape
            "1104:832": {"video_ratio": "4:3", "image_ratio": "4:3"},
            # 3:4 portrait
            "832:1104": {"video_ratio": "3:4", "image_ratio": "3:4"},
            # 1:1 square
            "960:960": {"video_ratio": "1:1", "image_ratio": "1:1"},
            # 21:9 ultra-wide -> 16:9
            "1584:672": {"video_ratio": "16:9", "image_ratio": "16:9"},
            # 16:9 landscape HD+ -> 16:9
            "1280:768": {"video_ratio": "16:9", "image_ratio": "16:9"},
            # 9:16 portrait HD -> 9:16
            "768:1280": {"video_ratio": "9:16", "image_ratio": "9:16"},
        }

        return mapping.get(video_resolution, {"video_ratio": "9:16", "image_ratio": "9:16"})

    def _get_scenario_resolution(self, scene_id: str) -> str:
        """
        Get resolution from video_scenarios table based on scenario_id from video_scenes.

        Args:
            scene_id: The UUID of the scene

        Returns:
            Resolution string (e.g., "1280:720")
        """
        try:
            if not supabase_manager.is_connected():
                raise Exception("Supabase connection not available")

            # First get the scenario_id from the scene
            scene_result = supabase_manager.client.table('video_scenes').select(
                'scenario_id').eq('id', scene_id).execute()

            if not scene_result.data:
                raise Exception(f"Scene {scene_id} not found")

            scenario_id = scene_result.data[0]['scenario_id']

            # Then get the resolution from the scenario
            scenario_result = supabase_manager.client.table('video_scenarios').select(
                'resolution').eq('id', scenario_id).execute()

            if not scenario_result.data:
                raise Exception(f"Scenario {scenario_id} not found")

            resolution = scenario_result.data[0].get('resolution', '720:1280')
            logger.info(
                f"Retrieved resolution {resolution} for scene {scene_id}")
            return resolution

        except Exception as e:
            logger.error(
                f"Failed to get scenario resolution for scene {scene_id}: {e}")
            # Return default resolution if there's an error
            return "720:1280"

    def _create_signed_video_url(self, video_url: str, expires_in: int = 3600) -> str:
        """
        Convert a Supabase storage URL to a signed URL or refresh existing signed URL.

        Args:
            video_url: The Supabase storage URL (public or signed)
            expires_in: Expiration time in seconds (default: 1 hour)

        Returns:
            Signed URL that expires after the specified time
        """
        try:
            # Check if it's already a signed URL (contains 'token=' parameter)
            if 'token=' in video_url:
                # Extract bucket and path from signed URL
                # URL format: https://xxx.supabase.co/storage/v1/object/sign/bucket-name/path/to/file?token=...
                if '/storage/v1/object/sign/' in video_url:
                    parts = video_url.split('/storage/v1/object/sign/')
                    if len(parts) == 2:
                        bucket_path = parts[1].split(
                            '?')[0]  # Remove query parameters
                        bucket_name, file_path = bucket_path.split('/', 1)

                        # Create new signed URL with fresh expiration
                        signed_url_response = supabase_manager.client.storage.from_(bucket_name).create_signed_url(
                            file_path, expires_in
                        )

                        # Extract the signed URL string from the response
                        if isinstance(signed_url_response, dict):
                            if 'signedURL' in signed_url_response:
                                signed_url = signed_url_response['signedURL']
                            elif 'signedUrl' in signed_url_response:
                                signed_url = signed_url_response['signedUrl']
                            else:
                                # Try to find any URL-like property
                                for key, value in signed_url_response.items():
                                    if isinstance(value, str) and value.startswith('http'):
                                        signed_url = value
                                        break
                                else:
                                    raise Exception(f"Could not find signed URL in response: {signed_url_response}")
                        elif isinstance(signed_url_response, str):
                            signed_url = signed_url_response
                        else:
                            signed_url = str(signed_url_response)

                        logger.info(
                            f"Refreshed signed URL for video, expires in {expires_in} seconds")
                        return signed_url

            # Check if it's a public URL
            elif '/storage/v1/object/public/' in video_url:
                parts = video_url.split('/storage/v1/object/public/')
                if len(parts) == 2:
                    bucket_path = parts[1]
                    bucket_name, file_path = bucket_path.split('/', 1)

                    # Create signed URL
                    signed_url_response = supabase_manager.client.storage.from_(bucket_name).create_signed_url(
                        file_path, expires_in
                    )

                    # Extract the signed URL string from the response
                    if isinstance(signed_url_response, dict):
                        if 'signedURL' in signed_url_response:
                            signed_url = signed_url_response['signedURL']
                        elif 'signedUrl' in signed_url_response:
                            signed_url = signed_url_response['signedUrl']
                        else:
                            # Try to find any URL-like property
                            for key, value in signed_url_response.items():
                                if isinstance(value, str) and value.startswith('http'):
                                    signed_url = value
                                    break
                            else:
                                raise Exception(f"Could not find signed URL in response: {signed_url_response}")
                    elif isinstance(signed_url_response, str):
                        signed_url = signed_url_response
                    else:
                        signed_url = str(signed_url_response)

                    logger.info(
                        f"Created signed URL for video, expires in {expires_in} seconds")
                    return signed_url

            # If we can't parse the URL, return the original
            logger.warning(
                f"Could not parse video URL for signed URL creation: {video_url}")
            return video_url

        except Exception as e:
            logger.error(f"Failed to create signed URL for video: {e}")
            # Return original URL if signing fails
            return video_url

    def start_video_generation_task(
        self,
        scene_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Start a video generation task for a specific scene.

        Args:
            scene_id: The UUID of the scene to process
            user_id: The user ID who owns the scene

        Returns:
            Dict containing task information
        """
        try:
            # Create task using task management system
            logger.info(
                f"Creating video generation task for scene {scene_id} and user {user_id}")
            task_id = create_task(
                task_type=TaskType.MEDIA_PROCESSING,
                user_id=user_id,
                scene_id=scene_id,
                task_name="Video Generation",
                description=f"Generate video for scene {scene_id}"
            )
            logger.info(f"Successfully created task {task_id}")

            # Validate task_id
            if not task_id or not isinstance(task_id, str):
                raise Exception(f"Invalid task_id returned: {task_id}")

            # Start processing in background thread
            thread = threading.Thread(
                target=self._process_video_generation_task,
                args=(task_id, scene_id, user_id),
                daemon=True
            )
            thread.start()

            # Store the thread reference
            self._active_threads[task_id] = thread

            logger.info(f"Started background thread for task {task_id}")

            logger.info(
                f"Started video generation task {task_id} for scene {scene_id}")

            return {
                'task_id': task_id,
                'status': TaskStatus.PENDING,
                'scene_id': scene_id,
                'user_id': user_id,
                'created_at': datetime.now(),
                'message': 'Video generation task started',
                'progress': 0.0,
                'current_step': 'Initializing',
                'error_message': None,
                'video_url': None,  # Will be populated with signed URL when task completes
                'image_url': None   # Will be populated when task completes
            }
        except Exception as e:
            logger.error(f"Failed to start video generation task: {e}")
            raise

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status by task ID."""
        try:
            task = get_task_status(task_id)
            if task:
                # Get the video and image URLs if task is completed
                video_url = None
                image_url = None
                if task.task_status == 'completed' and task.task_metadata:
                    video_url = task.task_metadata.get('video_url')
                    image_url = task.task_metadata.get('image_url')

                return {
                    'task_id': task.task_id,
                    'status': task.task_status,
                    'scene_id': task.task_metadata.get('scene_id'),
                    'user_id': task.user_id,
                    'progress': task.progress,
                    'message': task.task_status_message,
                    'current_step': task.current_step_name,
                    'error_message': task.error_message,
                    'created_at': task.created_at,
                    'updated_at': task.updated_at,
                    'video_url': video_url,  # Signed URL from task metadata for immediate access
                    'image_url': image_url   # Image URL from metadata
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get task status for {task_id}: {e}")
            return None

    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Get all tasks."""
        # This would need to be implemented to query all video processing tasks
        # For now, return empty dict as this method is not critical for the core functionality
        logger.warning(
            "get_all_tasks not implemented - would need to query MongoDB for all video processing tasks")
        return {}

    def _update_task(self, task_id: str, **kwargs):
        """Update task information using task management system."""
        try:
            # Convert our internal update format to task management format
            update_data = {}

            if 'status' in kwargs:
                if kwargs['status'] == TaskStatus.RUNNING:
                    start_task(task_id)
                elif kwargs['status'] == TaskStatus.COMPLETED:
                    complete_task(task_id, kwargs.get('metadata'))
                elif kwargs['status'] == TaskStatus.FAILED:
                    fail_task(task_id, kwargs.get(
                        'error_message', 'Unknown error'))

            if 'progress' in kwargs and 'current_step' in kwargs:
                # Map our step names to step numbers
                step_mapping = {
                    'initializing video generation pipeline': 0,
                    'fetching scene configuration and prompts': 1,
                    'generating scene image with ai': 2,
                    'creating video from generated image': 3,
                    'saving results and finalizing': 4
                }
                # Convert step name to lowercase for matching
                step_name_lower = kwargs['current_step'].lower()
                step_number = step_mapping.get(step_name_lower, 0)
                update_task_progress(task_id, step_number, kwargs['current_step'], kwargs['progress'])

        except Exception as e:
            logger.error(f"Failed to update task {task_id}: {e}")
    
    def _process_video_generation_task(self, task_id: str, scene_id: str, user_id: str):
        """Process the video generation task in a background thread."""
        try:
            logger.info(f"Starting video generation task {task_id} for scene {scene_id}")
            start_task(task_id)
            update_task_progress(task_id, 0, 'Initializing video generation pipeline', 5.0)
            
            # Step 1: Fetch scene data from database
            update_task_progress(task_id, 1, 'Fetching scene configuration and prompts', 15.0)
            scene_data = self._fetch_scene_data(scene_id)
            if not scene_data:
                raise Exception(f"Scene {scene_id} not found")
            
            # Step 2: Generate image if needed
            update_task_progress(task_id, 2, 'Generating scene image with AI', 45.0)
            image_url = self._generate_image_if_needed(scene_data, user_id, task_id)
            
            # Step 3: Generate video
            update_task_progress(task_id, 3, 'Creating video from generated image', 80.0)
            # Get both public URL (for database) and signed URL (for immediate access)
            public_video_url, signed_video_url = self._generate_video(scene_data, image_url, user_id, task_id)
            
            # Step 4: Update scene with generated URLs
            update_task_progress(task_id, 4, 'Saving results and finalizing', 95.0)
            # Store public URL in database for permanent access
            self._update_scene_urls(scene_id, image_url, public_video_url)
            
            # Complete the task with signed URL for immediate access
            complete_task(task_id, {
                'scene_id': scene_id,
                'image_url': image_url,
                'video_url': signed_video_url,  # Signed URL for immediate access
                'status': 'completed'
            })
            
            logger.info(f"Video generation task {task_id} completed successfully")
            
        except Exception as e:
            error_msg = f"Video generation failed: {str(e)}"
            logger.error(f"Error in video generation task {task_id}: {e}", exc_info=True)
            fail_task(task_id, error_msg)
    
    def _fetch_scene_data(self, scene_id: str) -> Optional[Dict[str, Any]]:
        """Fetch scene data from the database."""
        try:
            if not supabase_manager.is_connected():
                raise Exception("Supabase connection not available")
            
            result = supabase_manager.client.table('video_scenes').select('*').eq('id', scene_id).execute()
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Failed to fetch scene data for {scene_id}: {e}")
            raise
    
    def _generate_image_if_needed(self, scene_data: Dict[str, Any], user_id: str, task_id: str) -> str:
        """Generate image if it doesn't exist, otherwise return existing image URL."""
        # Check if image already exists
        if scene_data.get('image_url'):
            logger.info(f"Image already exists for scene {scene_data['id']}: {scene_data['image_url']}")
            return scene_data['image_url']
        
        # Get required data for image generation
        image_prompt = scene_data.get('image_prompt')
        product_reference_image_url = scene_data.get('product_reference_image_url')
        
        if not image_prompt:
            raise Exception("Image prompt is required for image generation")
        
        # Check credits before generation
        credit_check = credit_manager.can_perform_action(user_id, "generate_image")
        if credit_check.get("error") or not credit_check.get("can_perform", False):
            raise Exception(f"Insufficient credits for image generation: {credit_check.get('reason', 'Unknown error')}")
        
        # Get resolution mapping for image generation
        scene_id = scene_data['id']
        video_resolution = self._get_scenario_resolution(scene_id)
        resolution_mapping = self._get_resolution_mapping(video_resolution)
        image_ratio = resolution_mapping['image_ratio']
        
        logger.info(f"Using image ratio {image_ratio} for scene {scene_id} (video resolution: {video_resolution})")
        
        # Update progress - starting AI image generation
        update_task_progress(task_id, 2, 'Generating scene image with AI', 35.0)
        
        # Generate image using Flux API
        try:
            # Use Flux API for image generation with both text and reference image
            result = flux_manager.generate_image_with_prompt_and_image(
                prompt=image_prompt,
                input_image=product_reference_image_url if product_reference_image_url else None,
                model=settings.BFL_DEFAULT_MODEL,
                output_path=f"temp_image_{uuid.uuid4()}.png"
            )
            
            if not result or not result.get('success'):
                error_msg = result.get('error', 'Unknown error') if result else 'No result returned'
                raise Exception(f"Failed to generate image with Flux API: {error_msg}")
            
            # Check if image was saved locally
            if not result.get('image_saved') or not result.get('output_path'):
                raise Exception("Image was not saved to local storage")
            
            # Get the local image path
            local_image_path = result['output_path']
            if not os.path.exists(local_image_path):
                raise Exception(f"Generated image file not found at {local_image_path}")
            
            logger.info(f"Successfully generated image for scene {scene_data['id']}")
            
        except Exception as e:
            logger.error(f"Unexpected error during image generation: {e}")
            raise Exception(f"Failed to generate image with Flux API: {e}")
        
        # Update progress - uploading image to Supabase
        update_task_progress(task_id, 2, 'Storing generated image', 40.0)
        
        # Upload local image to Supabase
        image_url = self._store_local_image_in_supabase(local_image_path, user_id)
        
        # Update the scene with the generated image URL
        self._update_scene_image_url(scene_data['id'], image_url)
        
        # Clean up local image file
        try:
            os.unlink(local_image_path)
            logger.info(f"Cleaned up temporary image file: {local_image_path}")
        except Exception as cleanup_error:
            logger.warning(f"Failed to clean up temporary image file {local_image_path}: {cleanup_error}")
        
        # Deduct credits after successful generation
        credit_manager.deduct_credits(
            user_id=user_id,
            action_name="generate_image",
            reference_id=scene_data['id'],
            reference_type="scene",
            description=f"Generated image for scene {scene_data['id']}"
        )
        
        return image_url
    
    def _generate_video(self, scene_data: Dict[str, Any], image_url: str, user_id: str, task_id: str) -> tuple[str, str]:
        """Generate video using the image and visual prompt."""
        temp_video_path = None
        try:
            visual_prompt = scene_data.get('visual_prompt')
            duration = scene_data.get('duration', 5)  # Default 5 seconds
            
            if not visual_prompt:
                raise Exception("Visual prompt is required for video generation")
            
            # Check credits before generation
            credit_check = credit_manager.can_perform_action(user_id, "generate_scene")
            if credit_check.get("error") or not credit_check.get("can_perform", False):
                raise Exception(f"Insufficient credits for video generation: {credit_check.get('reason', 'Unknown error')}")
            
            # Get resolution mapping for video generation
            scene_id = scene_data['id']
            video_resolution = self._get_scenario_resolution(scene_id)
            resolution_mapping = self._get_resolution_mapping(video_resolution)
            video_ratio = resolution_mapping['video_ratio']
            
            logger.info(f"Using video ratio {video_ratio} for scene {scene_id} (scenario resolution: {video_resolution})")
            
            # Update progress - starting AI video generation
            update_task_progress(task_id, 3, 'Creating video from generated image', 70.0)
            
            # Create temporary file path for video
            temp_video_path = f"temp_video_{uuid.uuid4()}.mp4"
            
            # Generate video using new Gemini function
            result = generate_video_with_prompt_and_image(
                prompt=visual_prompt,
                image_url=image_url,
                model=settings.GEMINI_VIDEO_MODEL,
                file_path=temp_video_path,
                aspect_ratio=video_ratio,
                number_of_videos=1
            )
            
            if not result or not result.get('success'):
                error_msg = result.get('error', 'Unknown error') if result else 'No result returned'
                raise Exception(f"Failed to generate video with Gemini: {error_msg}")
            
            # Check if video was saved locally
            if not result.get('video_paths') or not result['video_paths']:
                raise Exception("Video was not saved to local storage")
            
            # Get the video path (should be the temp file we created)
            video_path = result['video_paths'][0]
            if not os.path.exists(video_path):
                raise Exception(f"Generated video file not found at {video_path}")
            
            # Update progress - uploading video to Supabase
            update_task_progress(task_id, 3, 'Storing generated video', 75.0)
            
            # Upload the local video file to Supabase
            public_url, signed_url = self._store_local_video_in_supabase(video_path, user_id)
            
            # Deduct credits after successful generation
            credit_manager.deduct_credits(
                user_id=user_id,
                action_name="generate_scene",
                reference_id=scene_data['id'],
                reference_type="scene",
                description=f"Generated video for scene {scene_data['id']}"
            )
            
            return public_url, signed_url
            
        except Exception as e:
            logger.error(f"Failed to generate video for scene {scene_data['id']}: {e}")
            raise
        finally:
            # Clean up temporary video file
            if temp_video_path and os.path.exists(temp_video_path):
                try:
                    os.unlink(temp_video_path)
                    logger.info(f"Cleaned up temporary video file: {temp_video_path}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to clean up temporary video file {temp_video_path}: {cleanup_error}")
    
    def _store_local_image_in_supabase(self, image_path: str, user_id: str) -> str:
        """
        Upload a local image file to Supabase storage.
        
        Args:
            image_path: Path to the local image file
            user_id: User ID for organizing files
            
        Returns:
            str: Public URL of the uploaded image
        """
        for attempt in range(MAX_RETRIES):
            try:
                # Read the local image file
                with open(image_path, 'rb') as f:
                    image_data = f.read()
                
                # Generate unique filename
                filename = f"generated_images/{user_id}/{uuid.uuid4()}.png"
                
                # Upload to Supabase storage
                if not supabase_manager.is_connected():
                    raise Exception("Supabase connection not available")
                
                # Upload to generated-content bucket (create if doesn't exist)
                try:
                    result = supabase_manager.client.storage.from_('generated-content').upload(
                        path=filename,
                        file=image_data,
                        file_options={'content-type': 'image/png'}
                    )
                except Exception as bucket_error:
                    if "Bucket not found" in str(bucket_error):
                        logger.warning("Bucket 'generated-content' not found, trying to create it...")
                        try:
                            # Try to create the bucket
                            supabase_manager.client.storage.create_bucket('generated-content', options={"public": True})
                            logger.info("Created 'generated-content' bucket")
                            # Retry upload
                            result = supabase_manager.client.storage.from_('generated-content').upload(
                                path=filename,
                                file=image_data,
                                file_options={'content-type': 'image/png'}
                            )
                        except Exception as create_error:
                            logger.error(f"Failed to create bucket 'generated-content': {create_error}")
                            raise Exception(f"Storage bucket 'generated-content' not available and could not be created: {create_error}")
                    else:
                        raise bucket_error
                
                # Get public URL
                public_url = supabase_manager.client.storage.from_('generated-content').get_public_url(filename)
                
                logger.info(f"Stored local image in Supabase: {public_url}")
                return public_url
                
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Attempt {attempt + 1} failed for local image storage: {e}. Retrying in {RETRY_DELAY} seconds...")
                    import time
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"Failed to store local image in Supabase after {MAX_RETRIES} attempts: {e}")
                    raise

    def _store_image_in_supabase(self, image_url: str, user_id: str) -> str:
        """Download image from Gemini and store it in Supabase storage. Handles both regular URLs and data URIs."""
        for attempt in range(MAX_RETRIES):
            try:
                # Check if it's a data URI
                if image_url.startswith('data:'):
                    image_data = self._extract_data_from_uri(image_url)
                else:
                    # Download image from URL
                    with httpx.Client(timeout=DOWNLOAD_TIMEOUT) as client:
                        response = client.get(image_url)
                        response.raise_for_status()
                        image_data = response.content
                
                # Generate unique filename
                filename = f"generated_images/{user_id}/{uuid.uuid4()}.png"
                
                # Upload to Supabase storage
                if not supabase_manager.is_connected():
                    raise Exception("Supabase connection not available")
                
                # Upload to generated-content bucket (create if doesn't exist)
                try:
                    result = supabase_manager.client.storage.from_('generated-content').upload(
                        path=filename,
                        file=image_data,
                        file_options={'content-type': 'image/png'}
                    )
                except Exception as bucket_error:
                    if "Bucket not found" in str(bucket_error):
                        logger.warning("Bucket 'generated-content' not found, trying to create it...")
                        try:
                            # Try to create the bucket
                            supabase_manager.client.storage.create_bucket('generated-content', options={"public": True})
                            logger.info("Created 'generated-content' bucket")
                            # Retry upload
                            result = supabase_manager.client.storage.from_('generated-content').upload(
                                path=filename,
                                file=image_data,
                                file_options={'content-type': 'image/png'}
                            )
                        except Exception as create_error:
                            logger.error(f"Failed to create bucket 'generated-content': {create_error}")
                            raise Exception(f"Storage bucket 'generated-content' not available and could not be created: {create_error}")
                    else:
                        raise bucket_error
                
                # Get public URL
                public_url = supabase_manager.client.storage.from_('generated-content').get_public_url(filename)
                
                logger.info(f"Stored image in Supabase: {public_url}")
                return public_url
                
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Attempt {attempt + 1} failed for image storage: {e}. Retrying in {RETRY_DELAY} seconds...")
                    import time
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"Failed to store image in Supabase after {MAX_RETRIES} attempts: {e}")
                    raise
    
    def _store_local_video_in_supabase(self, video_path: str, user_id: str) -> tuple[str, str]:
        """
        Upload a local video file to Supabase storage.
        
        Args:
            video_path: Path to the local video file
            user_id: User ID for organizing files
            
        Returns:
            tuple: (public_url, signed_url) - public URL for database, signed URL for immediate access
        """
        for attempt in range(MAX_RETRIES):
            try:
                # Read the local video file
                with open(video_path, 'rb') as f:
                    video_data = f.read()
                
                # Generate unique filename
                filename = f"video-files/{user_id}/{uuid.uuid4()}.mp4"
                
                # Upload to Supabase storage
                if not supabase_manager.is_connected():
                    raise Exception("Supabase connection not available")
                
                # Upload to video-files bucket (create if doesn't exist)
                try:
                    result = supabase_manager.client.storage.from_('video-files').upload(
                        path=filename,
                        file=video_data,
                        file_options={'content-type': 'video/mp4'}
                    )
                except Exception as bucket_error:
                    if "Bucket not found" in str(bucket_error):
                        logger.warning("Bucket 'video-files' not found, trying to create it...")
                        try:
                            # Try to create the bucket
                            supabase_manager.client.storage.create_bucket('video-files', options={"public": False})
                            logger.info("Created 'video-files' bucket")
                            # Retry upload
                            result = supabase_manager.client.storage.from_('video-files').upload(
                                path=filename,
                                file=video_data,
                                file_options={'content-type': 'video/mp4'}
                            )
                        except Exception as create_error:
                            logger.error(f"Failed to create bucket 'video-files': {create_error}")
                            raise Exception(f"Storage bucket 'video-files' not available and could not be created: {create_error}")
                    else:
                        raise bucket_error
                
                # Get public URL for storage in database
                public_url = supabase_manager.client.storage.from_('video-files').get_public_url(filename)
                
                # Get signed URL for immediate access
                signed_url_response = supabase_manager.client.storage.from_('video-files').create_signed_url(
                    filename, 3600  # 1 hour expiration
                )
                
                # Extract the signed URL string from the response
                if isinstance(signed_url_response, dict):
                    if 'signedURL' in signed_url_response:
                        signed_url = signed_url_response['signedURL']
                    elif 'signedUrl' in signed_url_response:
                        signed_url = signed_url_response['signedUrl']
                    else:
                        # Try to find any URL-like property
                        for key, value in signed_url_response.items():
                            if isinstance(value, str) and value.startswith('http'):
                                signed_url = value
                                logger.info(f"Found URL in property '{key}': {signed_url}")
                                break
                        else:
                            raise Exception(f"Could not find signed URL in response: {signed_url_response}")
                elif isinstance(signed_url_response, str):
                    signed_url = signed_url_response
                else:
                    # Fallback: try to get the first value if it's a different structure
                    signed_url = str(signed_url_response)
                    logger.warning(f"Unexpected signed URL response format: {signed_url_response}")
                
                logger.info(f"Stored local video in Supabase: public={public_url}, signed={signed_url}")
                return public_url, signed_url
                
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Attempt {attempt + 1} failed for local video storage: {e}. Retrying in {RETRY_DELAY} seconds...")
                    import time
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"Failed to store local video in Supabase after {MAX_RETRIES} attempts: {e}")
                    raise

    def _store_video_in_supabase(self, video_url: str, user_id: str) -> tuple[str, str]:
        """
        Download video from Gemini and store it in Supabase storage.
        Handles both regular URLs and data URIs.
        
        Returns:
            tuple: (public_url, signed_url) - public URL for database, signed URL for immediate access
        """
        for attempt in range(MAX_RETRIES):
            try:
                # Check if it's a data URI
                if video_url.startswith('data:'):
                    video_data = self._extract_data_from_uri(video_url)
                else:
                    # Download video from URL
                    with httpx.Client(timeout=DOWNLOAD_TIMEOUT) as client:
                        response = client.get(video_url)
                        response.raise_for_status()
                        video_data = response.content
                
                # Generate unique filename
                filename = f"video-files/{user_id}/{uuid.uuid4()}.mp4"
                
                # Upload to Supabase storage
                if not supabase_manager.is_connected():
                    raise Exception("Supabase connection not available")
                
                # Upload to video-files bucket (create if doesn't exist)
                try:
                    result = supabase_manager.client.storage.from_('video-files').upload(
                        path=filename,
                        file=video_data,
                        file_options={'content-type': 'video/mp4'}
                    )
                except Exception as bucket_error:
                    if "Bucket not found" in str(bucket_error):
                        logger.warning("Bucket 'video-files' not found, trying to create it...")
                        try:
                            # Try to create the bucket
                            supabase_manager.client.storage.create_bucket('video-files', options={"public": False})
                            logger.info("Created 'video-files' bucket")
                            # Retry upload
                            result = supabase_manager.client.storage.from_('video-files').upload(
                                path=filename,
                                file=video_data,
                                file_options={'content-type': 'video/mp4'}
                            )
                        except Exception as create_error:
                            logger.error(f"Failed to create bucket 'video-files': {create_error}")
                            raise Exception(f"Storage bucket 'video-files' not available and could not be created: {create_error}")
                    else:
                        raise bucket_error
                
                # Get public URL for storage in database
                public_url = supabase_manager.client.storage.from_('video-files').get_public_url(filename)
                
                # Get signed URL for immediate access
                signed_url_response = supabase_manager.client.storage.from_('video-files').create_signed_url(
                    filename, 3600  # 1 hour expiration
                )
                
                # Extract the signed URL string from the response
                if isinstance(signed_url_response, dict):
                    if 'signedURL' in signed_url_response:
                        signed_url = signed_url_response['signedURL']
                    elif 'signedUrl' in signed_url_response:
                        signed_url = signed_url_response['signedUrl']
                    else:
                        # Try to find any URL-like property
                        for key, value in signed_url_response.items():
                            if isinstance(value, str) and value.startswith('http'):
                                signed_url = value
                                logger.info(f"Found URL in property '{key}': {signed_url}")
                                break
                        else:
                            raise Exception(f"Could not find signed URL in response: {signed_url_response}")
                elif isinstance(signed_url_response, str):
                    signed_url = signed_url_response
                else:
                    # Fallback: try to get the first value if it's a different structure
                    signed_url = str(signed_url_response)
                    logger.warning(f"Unexpected signed URL response format: {signed_url_response}")
                
                logger.info(f"Stored video in Supabase: public={public_url}, signed={signed_url}")
                return public_url, signed_url
                
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Attempt {attempt + 1} failed for video storage: {e}. Retrying in {RETRY_DELAY} seconds...")
                    import time
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"Failed to store video in Supabase after {MAX_RETRIES} attempts: {e}")
                    raise
    
    def _extract_data_from_uri(self, data_uri: str) -> bytes:
        """
        Extract binary data from a data URI.
        
        Args:
            data_uri: Data URI string (e.g., "data:video/mp4;base64,AAAA...")
            
        Returns:
            Binary data as bytes
        """
        try:
            # Check if it's a valid data URI
            if not data_uri.startswith('data:'):
                raise ValueError("Invalid data URI format")
            
            # Split the data URI
            header, data = data_uri.split(',', 1)
            
            # Extract MIME type and encoding
            mime_type = header.split(';')[0].split(':')[1] if ':' in header else 'application/octet-stream'
            encoding = 'base64' if 'base64' in header else 'url'
            
            if encoding != 'base64':
                raise ValueError(f"Unsupported data URI encoding: {encoding}")
            
            # Decode base64 data
            binary_data = base64.b64decode(data)
            
            logger.info(f"Successfully extracted {len(binary_data)} bytes from data URI (MIME: {mime_type})")
            return binary_data
            
        except Exception as e:
            logger.error(f"Failed to extract data from URI: {e}")
            raise

    def _update_scene_image_url(self, scene_id: str, image_url: str):
        """Update the scene with generated image URL."""
        try:
            if not supabase_manager.is_connected():
                raise Exception("Supabase connection not available")
            
            # Update scene with image URL
            result = supabase_manager.client.table('video_scenes').update({
                'image_url': image_url,
                'updated_at': datetime.now().isoformat()
            }).eq('id', scene_id).execute()
            
            if not result.data:
                raise Exception("Failed to update scene with image URL")
            
            logger.info(f"Updated scene {scene_id} with image URL: {image_url}")
            
        except Exception as e:
            logger.error(f"Failed to update scene {scene_id} with image URL: {e}")
            raise

    def _update_scene_urls(self, scene_id: str, image_url: str, video_url: str):
        """Update the scene with generated image and video URLs."""
        try:
            if not supabase_manager.is_connected():
                raise Exception("Supabase connection not available")
            
            # Update scene with new URLs (video_url is the public URL for database storage)
            result = supabase_manager.client.table('video_scenes').update({
                'image_url': image_url,
                'generated_video_url': video_url,  # Public URL stored in database
                'status': 'completed',
                'updated_at': datetime.now().isoformat()
            }).eq('id', scene_id).execute()
            
            if not result.data:
                raise Exception("Failed to update scene with generated URLs")
            
            logger.info(f"Updated scene {scene_id} with generated URLs (public video URL stored in database)")
            
        except Exception as e:
            logger.error(f"Failed to update scene {scene_id} with generated URLs: {e}")
            raise
    
    def _run_sync(self, coro):
        """Run an async coroutine synchronously in a new event loop."""
        import asyncio
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in a running event loop, create a new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(coro)
                finally:
                    loop.close()
            else:
                # Use the existing event loop
                return loop.run_until_complete(coro)
        except RuntimeError:
            # No event loop, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
    
    def cleanup(self):
        """Clean up all active threads and resources"""
        try:
            # Wait for all active threads to complete
            for task_id, thread in self._active_threads.items():
                if thread.is_alive():
                    logger.info(f"Waiting for task {task_id} to complete...")
                    thread.join(timeout=5.0)  # Wait up to 5 seconds
            
            # Clear the threads dictionary
            self._active_threads.clear()
            
            logger.info("Video generation service cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during video generation service cleanup: {e}")


# Global instance
video_generation_service = VideoGenerationService()
