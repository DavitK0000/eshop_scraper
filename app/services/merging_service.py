"""
Merging Service for Finalizing Shorts

This module provides functionality for:
- Merging generated video scenes into final videos
- Generating thumbnails using RunwayML
- Upscaling videos using RunwayML
- Adding watermarks for free plan users
- Managing the finalization process with task management
"""

import os
import uuid
import threading
import tempfile
import httpx
import subprocess
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

from app.logging_config import get_logger
from app.utils.runwayml_utils import runwayml_manager
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


class MergingService:
    """Service for finalizing shorts by merging videos and generating thumbnails."""

    def __init__(self):
        self._active_threads: Dict[str, threading.Thread] = {}

    def start_finalize_short_task(
        self,
        user_id: str,
        short_id: str,
        upscale: bool = False
    ) -> Dict[str, Any]:
        """
        Start the finalization process for a short video.
        
        Args:
            user_id: The user's UUID
            short_id: The short's UUID
            upscale: Whether to upscale the final video
            
        Returns:
            Dict containing task information
        """
        try:
            # Create task
            task_metadata = {
                "user_id": user_id,
                "short_id": short_id,
                "upscale": upscale,
                "task_type": "finalize_short"
            }
            
            task_id = create_task(
                task_type=TaskType.FINALIZE_SHORT,
                task_metadata=task_metadata,
                user_id=user_id
            )
            
            # Start task in background thread
            thread = threading.Thread(
                target=self._finalize_short_worker,
                args=(task_id, user_id, short_id, upscale),
                daemon=True
            )
            
            self._active_threads[task_id] = thread
            thread.start()
            
            logger.info(f"Started finalize short task {task_id} for short {short_id}")
            
            return {
                "task_id": task_id,
                "status": "pending",
                "message": "Finalization task started",
                "created_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to start finalize short task: {e}", exc_info=True)
            raise

    def _finalize_short_worker(
        self,
        task_id: str,
        user_id: str,
        short_id: str,
        upscale: bool
    ):
        """Background worker for finalizing shorts."""
        try:
            # Start task
            start_task(task_id)
            update_task_progress(task_id, 0.1, "Fetching video scenes")
            
            # Step 1: Fetch video scenes and product info
            scenes_data = self._fetch_video_scenes(short_id)
            if not scenes_data:
                raise Exception("No video scenes found for this short")
            
            product_info = self._fetch_product_info(short_id)
            if not product_info:
                raise Exception("Product information not found")
            
            update_task_progress(task_id, 0.2, "Generating thumbnail")
            
            # Step 2: Generate thumbnail
            thumbnail_url = self._generate_thumbnail(user_id, product_info, task_id)
            if not thumbnail_url:
                raise Exception("Failed to generate thumbnail")
            
            # Update shorts table with thumbnail
            self._update_shorts_thumbnail(short_id, thumbnail_url)
            
            update_task_progress(task_id, 0.4, "Downloading videos")
            
            # Step 3: Download videos
            video_files = self._download_videos(scenes_data, task_id)
            if not video_files:
                raise Exception("Failed to download videos")
            
            update_task_progress(task_id, 0.6, "Merging videos")
            
            # Step 4: Merge videos
            merged_video_path = self._merge_videos(video_files, task_id)
            if not merged_video_path:
                raise Exception("Failed to merge videos")
            
            update_task_progress(task_id, 0.7, "Processing final video")
            
            # Step 5: Add watermark if free plan
            final_video_path = self._add_watermark_if_needed(
                merged_video_path, user_id, task_id
            )
            
            # Step 6: Upscale if requested
            if upscale:
                update_task_progress(task_id, 0.8, "Upscaling video")
                final_video_path = self._upscale_video(
                    final_video_path, user_id, task_id, short_id
                )
            
            update_task_progress(task_id, 0.9, "Uploading final video")
            
            # Step 7: Upload final video
            final_video_url = self._upload_final_video(final_video_path, short_id, task_id)
            if not final_video_url:
                raise Exception("Failed to upload final video")
            
            # Update shorts table with final video URL
            self._update_shorts_final_video(short_id, final_video_url)
            
            # Clean up temporary files
            self._cleanup_temp_files(video_files + [merged_video_path, final_video_path])
            
            # Complete task
            complete_task(task_id, {
                "thumbnail_url": thumbnail_url,
                "final_video_url": final_video_url,  # Use final_video_url to match the field name
                "short_id": short_id
            })
            
            logger.info(f"Successfully completed finalize short task {task_id}")
            
        except Exception as e:
            logger.error(f"Failed to finalize short {short_id}: {e}", exc_info=True)
            fail_task(task_id, str(e))
        finally:
            # Remove thread reference
            if task_id in self._active_threads:
                del self._active_threads[task_id]

    def _fetch_video_scenes(self, short_id: str) -> List[Dict[str, Any]]:
        """Fetch all video scenes for a short."""
        try:
            if not supabase_manager.is_connected():
                raise Exception("Supabase connection not available")
            
            # Get scenario_id from video_scenarios table
            scenario_result = supabase_manager.client.table('video_scenarios').select(
                'id'
            ).eq('short_id', short_id).execute()
            
            if not scenario_result.data:
                raise Exception(f"No scenario found for short {short_id}")
            
            scenario_id = scenario_result.data[0]['id']
            
            # Get all scenes with generated videos (only columns that exist in video_scenes table)
            scenes_result = supabase_manager.client.table('video_scenes').select(
                'id, scene_number, generated_video_url, duration'
            ).eq('scenario_id', scenario_id).eq('status', 'completed').not_.is_('generated_video_url', 'null').execute()
            
            if not scenes_result.data:
                raise Exception(f"No completed video scenes found for scenario {scenario_id}")
            
            # Sort by scene number
            scenes = sorted(scenes_result.data, key=lambda x: x['scene_number'])
            
            logger.info(f"Found {len(scenes)} video scenes for short {short_id}")
            return scenes
            
        except Exception as e:
            logger.error(f"Failed to fetch video scenes: {e}")
            raise

    def _fetch_product_info(self, short_id: str) -> Dict[str, Any]:
        """Fetch product information for thumbnail generation."""
        try:
            if not supabase_manager.is_connected():
                raise Exception("Supabase connection not available")
            
            # Get product info from products table using short_id
            product_result = supabase_manager.client.table('products').select(
                'title, description, images'
            ).eq('short_id', short_id).execute()
            
            if product_result.data:
                product_data = product_result.data[0]
                return {
                    "title": product_data.get('title'),
                    "description": product_data.get('description'),
                    "images": product_data.get('images', [])
                }
            
            # Fallback to shorts data if no product found
            short_result = supabase_manager.client.table('shorts').select(
                'title, description'
            ).eq('id', short_id).execute()
            
            if short_result.data:
                short_data = short_result.data[0]
                return {
                    "title": short_data.get('title', 'Product Video'),
                    "description": short_data.get('description', 'Product showcase video'),
                    "images": []
                }
            
            return {
                "title": "Product Video",
                "description": "Product showcase video",
                "images": []
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch product info: {e}")
            raise

    def _generate_thumbnail(self, user_id: str, product_info: Dict[str, Any], task_id: str) -> str:
        """Generate thumbnail using RunwayML."""
        try:
            # Check credits for image generation
            credit_check = credit_manager.can_perform_action(user_id, "generate_image")
            if credit_check.get("error"):
                raise Exception(f"Credit check failed: {credit_check['error']}")
            
            if not credit_check.get("can_perform", False):
                raise Exception(f"Insufficient credits for image generation: {credit_check.get('reason', 'Unknown')}")
            
            # Generate thumbnail prompt
            title = product_info.get('title', 'Product')
            description = product_info.get('description', '')
            
            prompt = f"Create a professional product thumbnail for: {title}"
            if description:
                prompt += f". Description: {description}"
            prompt += ". Style: Modern, clean, professional, suitable for social media, high contrast, eye-catching"
            
            # Generate image using RunwayML
            if not runwayml_manager.is_available():
                raise Exception("RunwayML is not available")
            
            # Run the async method in a sync context
            import asyncio
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    runwayml_manager.generate_image_from_text(
                        prompt_text=prompt,
                        ratio="1920:1080"  # 16:9 ratio for thumbnails
                    )
                )
            finally:
                loop.close()
            
            if not result.get('success'):
                raise Exception(f"Image generation failed: {result.get('error', 'Unknown error')}")
            
            # Get the generated image URL
            image_url = result.get('output')
            if not image_url:
                raise Exception("No image URL returned from RunwayML")
            
            logger.info(f"RunwayML returned image URL: {image_url} (type: {type(image_url)})")
            
            # Handle case where output might be a list of URLs
            if isinstance(image_url, list):
                if len(image_url) > 0:
                    image_url = image_url[0]  # Take the first URL
                    logger.info(f"Extracted first URL from list: {image_url}")
                else:
                    raise Exception("No image URLs returned from RunwayML")
            
            # Ensure image_url is a string
            if not isinstance(image_url, str):
                raise Exception(f"Invalid image URL format: {type(image_url)}")
                
            logger.info(f"Uploading image directly from: {image_url}")
            # Upload directly from URL to Supabase storage without saving to filesystem
            thumbnail_url = self._upload_thumbnail_from_url(image_url, user_id, task_id)
            
            # Deduct credits
            credit_manager.deduct_credits(
                user_id=user_id,
                action_name="generate_image",
                reference_id=short_id,  # Use short_id instead of task_id
                reference_type="video_merge",  # Use video_merge instead of thumbnail_generation
                description="Generated thumbnail for short video"
            )
            
            logger.info(f"Successfully generated thumbnail for user {user_id}")
            return thumbnail_url
            
        except Exception as e:
            logger.error(f"Failed to generate thumbnail: {e}")
            raise

    def _download_image(self, image_url: str, task_id: str) -> str:
        """Download generated image to temporary file."""
        try:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Download image
            with httpx.Client(timeout=DOWNLOAD_TIMEOUT) as client:
                response = client.get(image_url)
                response.raise_for_status()
                
                with open(temp_path, 'wb') as f:
                    f.write(response.content)
            
            logger.info(f"Downloaded image to {temp_path}")
            return temp_path
            
        except Exception as e:
            logger.error(f"Failed to download image: {e}")
            raise

    def _upload_thumbnail_from_url(self, image_url: str, user_id: str, task_id: str) -> str:
        """Upload thumbnail directly from URL to Supabase storage without saving to filesystem."""
        try:
            if not supabase_manager.is_connected():
                raise Exception("Supabase connection not available")
            
            # Create storage path
            filename = f"thumbnail_images/{user_id}/{uuid.uuid4()}.png"
            
            # Download image data directly from URL and upload to Supabase
            with httpx.Client(timeout=DOWNLOAD_TIMEOUT) as client:
                response = client.get(image_url)
                response.raise_for_status()
                
                # Upload the image data directly to Supabase storage
                result = supabase_manager.client.storage.from_('generated-content').upload(
                    path=filename,
                    file=response.content,  # Use the response content directly
                    file_options={"content-type": "image/png"}
                )
            
            # Check for upload errors
            if hasattr(result, 'error') and result.error:
                raise Exception(f"Failed to upload thumbnail: {result.error}")
            
            # Get public URL
            thumbnail_url = supabase_manager.client.storage.from_('generated-content').get_public_url(filename)
            
            logger.info(f"Successfully uploaded thumbnail to {thumbnail_url}")
            return thumbnail_url
            
        except Exception as e:
            logger.error(f"Failed to upload thumbnail from URL: {e}")
            raise

    def _upload_thumbnail(self, thumbnail_path: str, user_id: str, task_id: str) -> str:
        """Upload thumbnail from local file to Supabase storage."""
        try:
            if not supabase_manager.is_connected():
                raise Exception("Supabase connection not available")
            
            # Create storage path
            filename = f"thumbnail_images/{user_id}/{uuid.uuid4()}.png"
            
            # Upload to Supabase storage
            with open(thumbnail_path, 'rb') as f:
                result = supabase_manager.client.storage.from_('generated-content').upload(
                    path=filename,
                    file=f,
                    file_options={"content-type": "image/png"}
                )
            
            # Check for upload errors
            if hasattr(result, 'error') and result.error:
                raise Exception(f"Failed to upload thumbnail: {result.error}")
            
            # Get public URL
            thumbnail_url = supabase_manager.client.storage.from_('generated-content').get_public_url(filename)
            
            logger.info(f"Successfully uploaded thumbnail to {thumbnail_url}")
            return thumbnail_url
            
        except Exception as e:
            logger.error(f"Failed to upload thumbnail: {e}")
            raise

    def _update_shorts_thumbnail(self, short_id: str, thumbnail_url: str):
        """Update shorts table with thumbnail URL."""
        try:
            if not supabase_manager.is_connected():
                raise Exception("Supabase connection not available")
            
            result = supabase_manager.client.table('shorts').update({
                'thumbnail_url': thumbnail_url,
                'updated_at': datetime.utcnow().isoformat()
            }).eq('id', short_id).execute()
            
            # Check for update errors
            if hasattr(result, 'error') and result.error:
                raise Exception(f"Failed to update shorts thumbnail: {result.error}")
            
            logger.info(f"Updated shorts {short_id} with thumbnail URL")
            
        except Exception as e:
            logger.error(f"Failed to update shorts thumbnail: {e}")
            raise

    def _download_videos(self, scenes_data: List[Dict[str, Any]], task_id: str) -> List[str]:
        """Download all video files from scenes."""
        try:
            video_files = []
            
            for scene in scenes_data:
                video_url = scene.get('generated_video_url')
                if not video_url:
                    continue
                
                # Create temporary file
                with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                    temp_path = temp_file.name
                
                # Download video
                with httpx.Client(timeout=DOWNLOAD_TIMEOUT) as client:
                    response = client.get(video_url)
                    response.raise_for_status()
                    
                    with open(temp_path, 'wb') as f:
                        f.write(response.content)
                
                video_files.append(temp_path)
                logger.info(f"Downloaded video for scene {scene['id']} to {temp_path}")
            
            if not video_files:
                raise Exception("No videos were downloaded successfully")
            
            logger.info(f"Successfully downloaded {len(video_files)} videos")
            return video_files
            
        except Exception as e:
            logger.error(f"Failed to download videos: {e}")
            raise

    def _merge_videos(self, video_files: List[str], task_id: str) -> str:
        """Merge videos using FFmpeg."""
        try:
            if len(video_files) == 1:
                return video_files[0]
            
            # Create temporary directory for merged video
            temp_dir = tempfile.mkdtemp()
            merged_video_path = os.path.join(temp_dir, "merged.mp4")
            
            # Create file list for FFmpeg
            file_list_path = os.path.join(temp_dir, "file_list.txt")
            with open(file_list_path, 'w') as f:
                for video_file in video_files:
                    f.write(f"file '{video_file}'\n")
            
            # Merge videos using FFmpeg concat demuxer
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', file_list_path,
                '-c', 'copy',
                merged_video_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode != 0:
                raise Exception(f"FFmpeg failed: {result.stderr}")
            
            if not os.path.exists(merged_video_path):
                raise Exception("Merged video file was not created")
            
            logger.info(f"Successfully merged {len(video_files)} videos to {merged_video_path}")
            return merged_video_path
            
        except Exception as e:
            logger.error(f"Failed to merge videos: {e}")
            raise

    def _add_watermark_if_needed(self, video_path: str, user_id: str, task_id: str) -> str:
        """Add watermark if user is on free plan."""
        try:
            # Check user's plan
            user_plan = self._get_user_plan(user_id)
            
            if user_plan == "free":
                logger.info(f"Adding watermark for free plan user {user_id}")
                return self._add_watermark_to_video(video_path, task_id)
            else:
                logger.info(f"User {user_id} is on {user_plan} plan, no watermark needed")
                return video_path
                
        except Exception as e:
            logger.error(f"Failed to check user plan or add watermark: {e}")
            # Continue without watermark if there's an error
            return video_path

    def _get_user_plan(self, user_id: str) -> str:
        """Get user's subscription plan."""
        try:
            if not supabase_manager.is_connected():
                return "free"  # Default to free if can't check
            
            # Get user's subscription info
            result = supabase_manager.client.rpc(
                'get_user_credits',
                {'user_uuid': user_id}
            ).execute()
            
            if result.data:
                plan_name = result.data[0].get('plan_name', 'free')
                return plan_name if plan_name != 'no_plan' else 'free'
            
            return "free"
            
        except Exception as e:
            logger.error(f"Failed to get user plan: {e}")
            return "free"

    def _add_watermark_to_video(self, video_path: str, task_id: str) -> str:
        """Add watermark to video using FFmpeg."""
        try:
            # Create temporary directory for watermarked video
            temp_dir = tempfile.mkdtemp()
            watermarked_video_path = os.path.join(temp_dir, "watermarked.mp4")
            
            # Add watermark using FFmpeg
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', 'drawtext=text=\'PromoNexAI\':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2:box=1:boxcolor=black@0.5',
                '-c:a', 'copy',
                watermarked_video_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode != 0:
                raise Exception(f"FFmpeg watermark failed: {result.stderr}")
            
            if not os.path.exists(watermarked_video_path):
                raise Exception("Watermarked video file was not created")
            
            logger.info(f"Successfully added watermark to video")
            return watermarked_video_path
            
        except Exception as e:
            logger.error(f"Failed to add watermark: {e}")
            raise

    def _upscale_video(self, video_path: str, user_id: str, task_id: str, short_id: str) -> str:
        """Upscale video using RunwayML."""
        try:
            # Get video duration for credit calculation
            duration = self._get_video_duration(video_path)
            
            # Check credits for upscaling
            credit_check = credit_manager.can_perform_action(user_id, "upscale_video")
            if credit_check.get("error"):
                raise Exception(f"Credit check failed: {credit_check['error']}")
            
            if not credit_check.get("can_perform", False):
                raise Exception(f"Insufficient credits for upscaling: {credit_check.get('reason', 'Unknown')}")
            
            # Calculate required credits (5 per second)
            required_credits = duration * 5
            
            # Check if user has enough credits
            user_credits = credit_manager.check_user_credits(user_id)
            if user_credits.get("credits_remaining", 0) < required_credits:
                raise Exception(f"Insufficient credits for upscaling. Required: {required_credits}, Available: {user_credits.get('credits_remaining', 0)}")
            
            # Upscale video using RunwayML
            if not runwayml_manager.is_available():
                raise Exception("RunwayML is not available for upscaling")
            
            # Use RunwayML for video upscaling (synchronous)
            upscale_result = runwayml_manager.upscale_video_sync(
                video_path=video_path,
                target_resolution="1920:1080"
            )
            
            if not upscale_result.get("success", False):
                raise Exception(f"RunwayML upscaling failed: {upscale_result.get('error', 'Unknown error')}")
            
            # Download the upscaled video
            upscaled_video_path = self._download_upscaled_video(
                upscale_result["output"], 
                task_id
            )
            
            # Deduct credits
            credit_manager.deduct_credits(
                user_id=user_id,
                action_name="upscale_video",
                reference_id=short_id,  # Use short_id instead of task_id
                reference_type="video_merge",  # Use video_merge instead of video_upscaling
                description=f"Upscaled video for {duration} seconds"
            )
            
            logger.info(f"Successfully upscaled video for user {user_id}")
            return upscaled_video_path
            
        except Exception as e:
            logger.error(f"Failed to upscale video: {e}")
            raise

    def _download_upscaled_video(self, video_url: str, task_id: str) -> str:
        """Download upscaled video from RunwayML URL."""
        try:
            # Create temporary directory for upscaled video
            temp_dir = tempfile.mkdtemp()
            upscaled_video_path = os.path.join(temp_dir, "upscaled.mp4")
            
            # Download the upscaled video (synchronous)
            with httpx.Client(timeout=DOWNLOAD_TIMEOUT) as client:
                response = client.get(video_url)
                response.raise_for_status()
                
                # Save the video to local file
                with open(upscaled_video_path, 'wb') as f:
                    f.write(response.content)
            
            if not os.path.exists(upscaled_video_path):
                raise Exception("Upscaled video file was not downloaded")
            
            logger.info(f"Successfully downloaded upscaled video to {upscaled_video_path}")
            return upscaled_video_path
            
        except Exception as e:
            logger.error(f"Failed to download upscaled video: {e}")
            raise

    def _get_video_duration(self, video_path: str) -> int:
        """Get video duration in seconds using FFmpeg."""
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                video_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                duration = float(result.stdout.strip())
                return int(duration)
            else:
                logger.warning(f"Could not get video duration, defaulting to 30 seconds: {result.stderr}")
                return 30
                
        except Exception as e:
            logger.warning(f"Failed to get video duration: {e}, defaulting to 30 seconds")
            return 30



    def _upload_final_video(self, video_path: str, short_id: str, task_id: str) -> str:
        """Upload final video to Supabase storage."""
        try:
            if not supabase_manager.is_connected():
                raise Exception("Supabase connection not available")
            
            # Create storage path
            filename = f"final_videos/{short_id}/{uuid.uuid4()}.mp4"
            
            # Upload to Supabase storage
            with open(video_path, 'rb') as f:
                result = supabase_manager.client.storage.from_('generated-content').upload(
                    path=filename,
                    file=f,
                    file_options={"content-type": "video/mp4"}
                )
            
            # Check for upload errors
            if hasattr(result, 'error') and result.error:
                raise Exception(f"Failed to upload final video: {result.error}")
            
            # Get public URL
            final_video_url = supabase_manager.client.storage.from_('generated-content').get_public_url(filename)
            
            logger.info(f"Successfully uploaded final video to {final_video_url}")
            return final_video_url
            
        except Exception as e:
            logger.error(f"Failed to upload final video: {e}")
            raise

    def _update_shorts_final_video(self, short_id: str, final_video_url: str):
        """Update shorts table with final video URL."""
        try:
            if not supabase_manager.is_connected():
                raise Exception("Supabase connection not available")
            
            result = supabase_manager.client.table('shorts').update({
                'final_video_url': final_video_url,  # Using correct final_video_url field
                'status': 'completed',
                'updated_at': datetime.utcnow().isoformat()
            }).eq('id', short_id).execute()
            
            # Check for update errors
            if hasattr(result, 'error') and result.error:
                raise Exception(f"Failed to update shorts final video: {result.error}")
            
            logger.info(f"Updated shorts {short_id} with final video URL and completed status")
            
        except Exception as e:
            logger.error(f"Failed to update shorts final video: {e}")
            raise

    def _cleanup_temp_files(self, file_paths: List[str]):
        """Clean up temporary files."""
        try:
            for file_path in file_paths:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.debug(f"Cleaned up temporary file: {file_path}")
                    
                    # Also remove parent directory if empty
                    parent_dir = os.path.dirname(file_path)
                    if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                        os.rmdir(parent_dir)
                        logger.debug(f"Cleaned up empty directory: {parent_dir}")
                        
        except Exception as e:
            logger.warning(f"Failed to cleanup some temporary files: {e}")

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a finalization task."""
        try:
            return get_task_status(task_id)
        except Exception as e:
            logger.error(f"Failed to get task status for {task_id}: {e}")
            return None

    def cleanup(self):
        """Clean up completed tasks and threads."""
        try:
            # Clean up completed threads
            completed_tasks = []
            for task_id, thread in self._active_threads.items():
                if not thread.is_alive():
                    completed_tasks.append(task_id)
            
            for task_id in completed_tasks:
                del self._active_threads[task_id]
            
            logger.info(f"Cleaned up {len(completed_tasks)} completed finalization tasks")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Global instance
merging_service = MergingService()
