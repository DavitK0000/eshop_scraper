"""
Merging Service for Finalizing Shorts

This module provides functionality for:
- Merging generated video scenes into final videos
- Merging audio with videos
- Embedding subtitles into videos
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
import json
import shutil
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
    """Service for finalizing shorts by merging videos, audio, and generating thumbnails."""

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

            logger.info(
                f"Started finalize short task {task_id} for short {short_id}")

            return {
                "task_id": task_id,
                "status": "pending",
                "message": "Finalization task started",
                "created_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(
                f"Failed to start finalize short task: {e}", exc_info=True)
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
            update_task_progress(
                task_id, 0.1, "Fetching video scenes and audio data")

            # Step 1: Fetch video scenes, product info, and audio data
            scenes_data = self._fetch_video_scenes(short_id)
            if not scenes_data:
                raise Exception("No video scenes found for this short")

            product_info = self._fetch_product_info(short_id)
            if not product_info:
                raise Exception("Product information not found")

            # Fetch audio data
            audio_data = self._fetch_audio_data(short_id)

            update_task_progress(task_id, 0.2, "Generating thumbnail")

            # Step 2: Generate thumbnail
            thumbnail_url = self._generate_thumbnail(
                user_id, product_info, task_id, short_id)
            if not thumbnail_url:
                raise Exception("Failed to generate thumbnail")

            # Update shorts table with thumbnail
            self._update_shorts_thumbnail(short_id, thumbnail_url)

            update_task_progress(task_id, 0.4, "Downloading videos and audio")

            # Step 3: Download videos and audio
            video_files = self._download_videos(scenes_data, user_id)
            if not video_files:
                raise Exception("Failed to download videos")

            audio_file = None
            if audio_data and audio_data.get('generated_audio_url'):
                audio_file = self._download_audio(
                    audio_data['generated_audio_url'], task_id)

            update_task_progress(task_id, 0.6, "Merging videos and audio")

            # Step 4: Merge videos
            merged_video_path = self._merge_videos(video_files, task_id)
            if not merged_video_path:
                raise Exception("Failed to merge videos")

            # Step 5: Merge audio if available
            if audio_file:
                merged_video_path = self._merge_audio_with_video(
                    merged_video_path, audio_file, task_id
                )

            # Step 6: Add subtitles if available
            if audio_data and audio_data.get('subtitles'):
                try:
                    merged_video_path = self._embed_subtitles(
                        merged_video_path, audio_data['subtitles'], task_id
                    )
                except Exception as subtitle_error:
                    logger.warning(
                        f"Failed to embed subtitles, continuing without them: {subtitle_error}")
                    # Continue with the video without subtitles

            update_task_progress(task_id, 0.7, "Processing final video")

            # Step 7: Add watermark if free plan
            final_video_path = self._add_watermark_if_needed(
                merged_video_path, user_id, task_id
            )

            # Step 8: Upscale if requested
            if upscale:
                update_task_progress(task_id, 0.8, "Upscaling video")
                final_video_path = self._upscale_video(
                    final_video_path, user_id, task_id, short_id
                )

            update_task_progress(task_id, 0.9, "Uploading final video")

            # Step 9: Upload final video
            final_video_url = self._upload_final_video(
                final_video_path, short_id, task_id)
            if not final_video_url:
                raise Exception("Failed to upload final video")

            # Update shorts table with final video URL
            self._update_shorts_final_video(short_id, final_video_url)

            # Clean up temporary files
            temp_files = video_files + [merged_video_path, final_video_path]
            if audio_file:
                temp_files.append(audio_file)
            
            # Also clean up any subtitle temporary directories
            if audio_data and audio_data.get('subtitles'):
                try:
                    # Find and clean up subtitle temp directories
                    self._cleanup_subtitle_temp_dirs()
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup subtitle temp directories: {cleanup_error}")
            
            self._cleanup_temp_files(temp_files)

            # Complete task
            complete_task(task_id, {
                "thumbnail_url": thumbnail_url,
                "final_video_url": final_video_url,
                "short_id": short_id
            })

            logger.info(
                f"Successfully completed finalize short task {task_id}")

        except Exception as e:
            logger.error(
                f"Failed to finalize short {short_id}: {e}", exc_info=True)
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
                raise Exception(
                    f"No completed video scenes found for scenario {scenario_id}")

            # Sort by scene number
            scenes = sorted(scenes_result.data,
                            key=lambda x: x['scene_number'])

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

    def _fetch_audio_data(self, short_id: str) -> Optional[Dict[str, Any]]:
        """Fetch audio data from audio_info table."""
        try:
            if not supabase_manager.is_connected():
                logger.warning(
                    "Supabase connection not available, skipping audio fetch")
                return None

            # Get audio info for the short
            audio_result = supabase_manager.client.table('audio_info').select(
                'generated_audio_url, subtitles, status'
            ).eq('short_id', short_id).eq('status', 'completed').execute()

            if not audio_result.data:
                logger.info(f"No completed audio found for short {short_id}")
                return None

            audio_data = audio_result.data[0]

            # Check if we have the required fields
            if not audio_data.get('generated_audio_url'):
                logger.info(
                    f"No generated audio URL found for short {short_id}")
                return None

            logger.info(f"Found audio data for short {short_id}")
            return audio_data

        except Exception as e:
            logger.error(f"Failed to fetch audio data: {e}")
            # Don't fail the entire process if audio fetch fails
            return None

    def _generate_thumbnail(self, user_id: str, product_info: Dict[str, Any], task_id: str, short_id: str) -> str:
        """Generate thumbnail using RunwayML."""
        try:
            # Check credits for image generation
            credit_check = credit_manager.can_perform_action(
                user_id, "generate_image")
            if credit_check.get("error"):
                raise Exception(
                    f"Credit check failed: {credit_check['error']}")

            if not credit_check.get("can_perform", False):
                raise Exception(
                    f"Insufficient credits for image generation: {credit_check.get('reason', 'Unknown')}")

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
                raise Exception(
                    f"Image generation failed: {result.get('error', 'Unknown error')}")

            # Get the generated image URL
            image_url = result.get('output')
            if not image_url:
                raise Exception("No image URL returned from RunwayML")

            # Handle case where output might be a list of URLs
            if isinstance(image_url, list):
                if len(image_url) > 0:
                    image_url = image_url[0]  # Take the first URL
                else:
                    raise Exception("No image URLs returned from RunwayML")

            # Ensure image_url is a string
            if not isinstance(image_url, str):
                raise Exception(f"Invalid image URL format: {type(image_url)}")
            # Upload directly from URL to Supabase storage without saving to filesystem
            thumbnail_url = self._upload_thumbnail_from_url(
                image_url, user_id, task_id)

            # Deduct credits
            credit_manager.deduct_credits(
                user_id=user_id,
                action_name="generate_image",
                reference_id=short_id,  # Use short_id instead of task_id
                reference_type="video_merge",  # Use video_merge instead of thumbnail_generation
                description="Generated thumbnail for short video"
            )

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

            # Validate Supabase connection and bucket
            if not supabase_manager.is_connected():
                raise Exception("Supabase connection not available")

            # Validate Supabase client
            if not hasattr(supabase_manager, 'client') or not supabase_manager.client:
                raise Exception("Supabase client not available")

            if not hasattr(supabase_manager.client, 'storage'):
                raise Exception("Supabase storage not available")

            # Check if storage bucket exists and is accessible
            try:
                buckets = supabase_manager.client.storage.list_buckets()
                bucket_names = [bucket.name for bucket in buckets]

                if 'generated-content' not in bucket_names:
                    raise Exception(
                        "Storage bucket 'generated-content' not found")

            except Exception as bucket_error:
                logger.error(
                    f"Failed to check storage buckets: {bucket_error}")
                raise Exception(f"Storage bucket check failed: {bucket_error}")

            # Download image data directly from URL and upload to Supabase
            with httpx.Client(timeout=DOWNLOAD_TIMEOUT) as client:
                response = client.get(image_url)
                response.raise_for_status()

                # Validate image content
                if len(response.content) == 0:
                    raise Exception("Downloaded image content is empty")

                # Validate content size (reasonable limits)
                if len(response.content) > 10 * 1024 * 1024:  # 10MB limit
                    raise Exception(
                        f"Image file too large: {len(response.content)} bytes")

                # Upload the image data directly to Supabase storage
                try:
                    result = supabase_manager.client.storage.from_('generated-content').upload(
                        path=filename,
                        file=response.content,  # Use the response content directly
                        file_options={"content-type": "image/png"}
                    )
                except json.JSONDecodeError as json_error:
                    logger.error(
                        f"Supabase upload failed with JSON decode error: {json_error}")
                    raise Exception(
                        f"Supabase upload failed with JSON decode error: {json_error}")
                except Exception as upload_error:
                    logger.error(
                        f"Supabase upload failed with error: {upload_error}")
                    raise Exception(f"Supabase upload failed: {upload_error}")

            # Check for upload errors
            if hasattr(result, 'error') and result.error:
                raise Exception(f"Failed to upload thumbnail: {result.error}")

            # Validate upload result
            if not result:
                raise Exception("Upload result is empty or None")

            # Get public URL
            try:
                thumbnail_url = supabase_manager.client.storage.from_(
                    'generated-content').get_public_url(filename)
            except Exception as url_error:
                logger.error(f"Failed to generate public URL: {url_error}")
                raise Exception(f"Public URL generation failed: {url_error}")

            if not thumbnail_url:
                raise Exception("Generated thumbnail URL is empty")

            return thumbnail_url

        except Exception as e:
            logger.error(f"Failed to upload thumbnail from URL: {e}")

            # Try fallback method: save to temp file first
            try:
                return self._upload_thumbnail_fallback(image_url, user_id, task_id)
            except Exception as fallback_error:
                logger.error(
                    f"Fallback upload method also failed: {fallback_error}")
                raise Exception(
                    f"Both upload methods failed. Original: {e}, Fallback: {fallback_error}")

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
            thumbnail_url = supabase_manager.client.storage.from_(
                'generated-content').get_public_url(filename)

            return thumbnail_url

        except Exception as e:
            logger.error(f"Failed to upload thumbnail: {e}")
            raise

    def _upload_thumbnail_fallback(self, image_url: str, user_id: str, task_id: str) -> str:
        """Fallback method: download image to temp file first, then upload."""
        try:
            # Download image to temporary file
            temp_path = self._download_image(image_url, task_id)

            # Validate downloaded file
            if not os.path.exists(temp_path):
                raise Exception(f"Downloaded file not found at {temp_path}")

            file_size = os.path.getsize(temp_path)
            if file_size == 0:
                raise Exception(f"Downloaded file is empty (0 bytes)")

            # Upload using the existing method
            thumbnail_url = self._upload_thumbnail(temp_path, user_id, task_id)

            # Clean up temp file
            try:
                os.remove(temp_path)
            except Exception as cleanup_error:
                logger.warning(
                    f"Failed to cleanup temporary file {temp_path}: {cleanup_error}")

            return thumbnail_url

        except Exception as e:
            logger.error(f"Fallback upload method failed: {e}")
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
                raise Exception(
                    f"Failed to update shorts thumbnail: {result.error}")

            logger.info(f"Updated shorts {short_id} with thumbnail URL")

        except Exception as e:
            logger.error(f"Failed to update shorts thumbnail: {e}")
            raise

    def _download_audio(self, audio_url: str, task_id: str) -> str:
        """Download audio file from URL."""
        try:
            # Create temporary file for audio
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_path = temp_file.name

            # Check if this is a Supabase storage URL and convert to signed URL if needed
            download_url = self._get_signed_audio_url(audio_url)

            # Download audio
            with httpx.Client(timeout=DOWNLOAD_TIMEOUT) as client:
                response = client.get(download_url)
                response.raise_for_status()

                with open(temp_path, 'wb') as f:
                    f.write(response.content)

            logger.info(f"Downloaded audio to {temp_path}")
            return temp_path

        except Exception as e:
            logger.error(f"Failed to download audio: {e}")
            raise

    def _get_signed_audio_url(self, audio_url: str) -> str:
        """Convert Supabase storage URL to signed URL for private files."""
        try:
            # Check if it's a Supabase storage URL
            if '/storage/v1/object/public/' in audio_url:
                # Extract bucket and path from the URL
                parts = audio_url.split('/storage/v1/object/public/')
                if len(parts) == 2:
                    bucket_path = parts[1]
                    bucket_name, file_path = bucket_path.split('/', 1)

                    # Create signed URL with 1 hour expiration
                    signed_url_response = supabase_manager.client.storage.from_(bucket_name).create_signed_url(
                        file_path, 3600
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
                                logger.warning(
                                    f"Could not find signed URL in response: {signed_url_response}")
                                return audio_url  # Fallback to original URL
                    elif isinstance(signed_url_response, str):
                        signed_url = signed_url_response
                    else:
                        signed_url = str(signed_url_response)

                    logger.info(
                        f"Created signed URL for audio file in bucket {bucket_name}")
                    return signed_url

            # Also check for URLs that might be direct Supabase URLs without the public pattern
            elif 'supabase.co' in audio_url and '/storage/' in audio_url:
                # Try to extract bucket and path from various URL formats
                try:
                    # Handle URLs like: https://project.supabase.co/storage/v1/object/public/bucket/path
                    # or: https://project.supabase.co/storage/v1/object/bucket/path
                    if '/storage/v1/object/' in audio_url:
                        parts = audio_url.split('/storage/v1/object/')
                        if len(parts) == 2:
                            bucket_path = parts[1]
                            # Remove 'public/' prefix if present
                            if bucket_path.startswith('public/'):
                                # Remove 'public/' prefix
                                bucket_path = bucket_path[7:]

                            bucket_name, file_path = bucket_path.split('/', 1)

                            # Create signed URL with 1 hour expiration
                            signed_url_response = supabase_manager.client.storage.from_(bucket_name).create_signed_url(
                                file_path, 3600
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
                                        logger.warning(
                                            f"Could not find signed URL in response: {signed_url_response}")
                                        return audio_url  # Fallback to original URL
                            elif isinstance(signed_url_response, str):
                                signed_url = signed_url_response
                            else:
                                signed_url = str(signed_url_response)

                            logger.info(
                                f"Created signed URL for audio file in bucket {bucket_name}")
                            return signed_url
                except Exception as parse_error:
                    logger.warning(
                        f"Failed to parse Supabase URL format: {parse_error}")

            # If not a Supabase storage URL or parsing failed, return original
            return audio_url

        except Exception as e:
            logger.warning(
                f"Failed to create signed URL for audio: {e}, using original URL")
            return audio_url

    def _handle_expired_url(self, url: str, user_id: str) -> str:
        """
        Handle expired signed URLs by converting them to public URLs or regenerating signed URLs.
        
        Args:
            url: The potentially expired URL
            user_id: The user ID for regenerating URLs if needed
            
        Returns:
            A working URL for the video
        """
        try:
            # Check if this is a Supabase signed URL
            if 'supabase.co' in url and 'token=' in url:
                logger.info(f"Detected potentially expired Supabase signed URL for user {user_id}, regenerating signed URL for private storage")
                logger.debug(f"Original URL: {url}")
                
                # Extract the file path from the signed URL
                # URL format: https://.../storage/v1/object/sign/bucket/path?token=...
                if '/storage/v1/object/sign/' in url:
                    # Extract bucket and path from signed URL
                    parts = url.split('/storage/v1/object/sign/')
                    if len(parts) > 1:
                        bucket_path = parts[1].split('?')[0]  # Remove query parameters
                        bucket_parts = bucket_path.split('/', 1)
                        if len(bucket_parts) > 1:
                            bucket_name = bucket_parts[0]
                            file_path = bucket_parts[1]
                            
                            # For private storage, directly regenerate signed URL instead of trying public URL
                            try:
                                if not supabase_manager.is_connected():
                                    raise Exception("Supabase connection not available")
                                
                                # Regenerate signed URL for private storage
                                signed_url_response = supabase_manager.client.storage.from_(bucket_name).create_signed_url(
                                    file_path, 3600  # 1 hour expiration
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
                                
                                logger.info(f"Successfully regenerated signed URL for private storage: {signed_url}")
                                logger.debug(f"Regenerated URL for bucket '{bucket_name}', file path '{file_path}'")
                                return signed_url
                                
                            except Exception as regen_error:
                                logger.error(f"Failed to regenerate signed URL for private storage: {regen_error}")
                                # Try to provide more specific error information
                                if "permission" in str(regen_error).lower():
                                    raise Exception(f"Permission denied when regenerating signed URL for private storage: {regen_error}")
                                elif "bucket" in str(regen_error).lower():
                                    raise Exception(f"Storage bucket access issue when regenerating signed URL: {regen_error}")
                                else:
                                    raise Exception(f"Could not regenerate signed URL for private storage: {regen_error}")
                
                # If we can't parse the URL or convert it, return the original
                logger.warning(f"Could not parse or convert expired URL for user {user_id}, returning original: {url}")
                return url
            else:
                # Not a Supabase signed URL, return as-is
                return url
                
        except Exception as e:
            logger.error(f"Error handling expired URL {url}: {e}")
            # Return original URL if we can't handle it
            return url

    def _download_videos(self, scenes_data: List[Dict[str, Any]], user_id: str) -> List[str]:
        """Download all video files from scenes."""
        try:
            video_files = []

            for scene in scenes_data:
                video_url = scene.get('generated_video_url')
                if not video_url:
                    continue

                # Handle potentially expired URLs
                working_url = self._handle_expired_url(video_url, user_id)
                
                # Create temporary file
                with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                    temp_path = temp_file.name

                # Download video with retry logic
                download_success = False
                for attempt in range(MAX_RETRIES):
                    try:
                        with httpx.Client(timeout=DOWNLOAD_TIMEOUT) as client:
                            response = client.get(working_url)
                            response.raise_for_status()

                            with open(temp_path, 'wb') as f:
                                f.write(response.content)

                        download_success = True
                        break
                        
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 400 and 'supabase.co' in working_url:
                            logger.warning(f"Attempt {attempt + 1}: Got 400 error for Supabase URL, trying to refresh: {e}")
                            # Try to refresh the URL
                            working_url = self._handle_expired_url(video_url, user_id)
                            if working_url == video_url:  # No change, break to avoid infinite loop
                                break
                        else:
                            logger.error(f"HTTP error downloading video: {e}")
                            break
                    except Exception as e:
                        logger.error(f"Attempt {attempt + 1} failed: {e}")
                        if attempt < MAX_RETRIES - 1:
                            import time
                            time.sleep(RETRY_DELAY)
                        else:
                            raise

                if not download_success:
                    raise Exception(f"Failed to download video after {MAX_RETRIES} attempts")

                video_files.append(temp_path)
                logger.info(
                    f"Downloaded video for scene {scene['id']} to {temp_path}")

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

            logger.info(
                f"Successfully merged {len(video_files)} videos to {merged_video_path}")
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
                logger.info(
                    f"User {user_id} is on {user_plan} plan, no watermark needed")
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
            credit_check = credit_manager.can_perform_action(
                user_id, "upscale_video")
            if credit_check.get("error"):
                raise Exception(
                    f"Credit check failed: {credit_check['error']}")

            if not credit_check.get("can_perform", False):
                raise Exception(
                    f"Insufficient credits for upscaling: {credit_check.get('reason', 'Unknown')}")

            # Calculate required credits (5 per second)
            required_credits = duration * 5

            # Check if user has enough credits
            user_credits = credit_manager.check_user_credits(user_id)
            if user_credits.get("credits_remaining", 0) < required_credits:
                raise Exception(
                    f"Insufficient credits for upscaling. Required: {required_credits}, Available: {user_credits.get('credits_remaining', 0)}")

            # Upscale video using RunwayML
            if not runwayml_manager.is_available():
                raise Exception("RunwayML is not available for upscaling")

            # Use RunwayML for video upscaling (synchronous)
            upscale_result = runwayml_manager.upscale_video_sync(
                video_path=video_path,
                target_resolution="1920:1080"
            )

            if not upscale_result.get("success", False):
                raise Exception(
                    f"RunwayML upscaling failed: {upscale_result.get('error', 'Unknown error')}")

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

            logger.info(
                f"Successfully downloaded upscaled video to {upscaled_video_path}")
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
                logger.warning(
                    f"Could not get video duration, defaulting to 30 seconds: {result.stderr}")
                return 30

        except Exception as e:
            logger.warning(
                f"Failed to get video duration: {e}, defaulting to 30 seconds")
            return 30

    def _merge_audio_with_video(self, video_path: str, audio_path: str, task_id: str) -> str:
        """Merge audio with video using FFmpeg."""
        try:
            # Create temporary directory for merged video
            temp_dir = tempfile.mkdtemp()
            merged_path = os.path.join(temp_dir, "video_with_audio.mp4")

            # Merge audio with video using FFmpeg
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'copy',  # Copy video codec
                '-c:a', 'aac',   # Convert audio to AAC
                '-longest',       # Use the longer duration between video and audio
                merged_path
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )

            if result.returncode != 0:
                raise Exception(f"FFmpeg audio merge failed: {result.stderr}")

            if not os.path.exists(merged_path):
                raise Exception("Audio-merged video file was not created")

            logger.info(f"Successfully merged audio with video")
            return merged_path

        except Exception as e:
            logger.error(f"Failed to merge audio with video: {e}")
            raise

    def _embed_subtitles(self, video_path: str, subtitles: List[Dict[str, Any]], task_id: str) -> str:
        """Embed subtitles into video using FFmpeg with SRT format."""
        try:
            # Create temporary directory at the same level as the app directory
            app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            temp_dir = os.path.join(app_dir, "temp_subtitles")
            
            # Create the temp directory if it doesn't exist
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            
            subtitled_path = os.path.join(temp_dir, "video_with_subtitles.mp4")

            # Create SRT file from subtitles data
            srt_path = os.path.join(temp_dir, "subtitles.srt")
            self._create_srt_file(subtitles, srt_path)

            # Convert Windows path to proper format for FFmpeg
            # Use forward slashes for FFmpeg on Windows - it handles them better
            escaped_srt_path = srt_path.replace('\\', '/').replace(':', '\\:')
            
            # Get appropriate font for the language
            font_name = self._get_subtitle_font()
            
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', f"subtitles='{escaped_srt_path}':force_style='FontSize=16,Bold=1,FontName={font_name},PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=1,Shadow=1,BackColour=&H000000&'",
                '-c:a', 'copy',  # Copy audio codec
                subtitled_path
            ]

            # Log the command for debugging
            logger.info(f"FFmpeg command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )

            if result.returncode != 0:
                raise Exception(f"FFmpeg subtitle embedding failed: {result.stderr}")

            if not os.path.exists(subtitled_path):
                raise Exception("Subtitled video file was not created")
            
            logger.info(f"Successfully embedded subtitles into video")

            # Don't clean up temporary directory here - let the caller handle cleanup
            # This ensures the file exists when the upload method tries to access it
            logger.debug(f"Subtitle embedding completed, file available at: {subtitled_path}")

            return subtitled_path

        except Exception as e:
            logger.error(f"Failed to embed subtitles: {e}")
            # Clean up temporary files
            try:
                if 'temp_dir' in locals() and os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
            except Exception as cleanup_error:
                logger.warning(
                    f"Failed to clean up temporary directory: {cleanup_error}")
            raise

    def _get_subtitle_font(self) -> str:
        """Get appropriate font for subtitles based on system."""
        try:
            # Common fonts that work well across different systems
            common_fonts = [
                'Arial',
                'Helvetica',
                'DejaVu Sans',
                'Liberation Sans',
                'FreeSans',
                'Verdana'
            ]
            
            # For Windows, Arial is usually available
            if os.name == 'nt':  # Windows
                return 'Arial'
            else:
                # For Unix-like systems, try to find a common font
                return 'DejaVu Sans'
                
        except Exception as e:
            logger.warning(f"Could not determine subtitle font, using default: {e}")
            return 'Arial'

    def _create_srt_file(self, subtitles: List[Dict[str, Any]], srt_path: str):
        """Create SRT file from subtitles data."""
        try:
            with open(srt_path, 'w', encoding='utf-8') as f:
                for i, subtitle in enumerate(subtitles, 1):
                    start_time = subtitle.get('start_time', 0)
                    end_time = subtitle.get('end_time', 0)
                    text = subtitle.get('text', '')

                    # Convert seconds to SRT time format (HH:MM:SS,mmm)
                    start_srt = self._seconds_to_srt_time(start_time)
                    end_srt = self._seconds_to_srt_time(end_time)

                    f.write(f"{i}\n")
                    f.write(f"{start_srt} --> {end_srt}\n")
                    f.write(f"{text}\n\n")

            logger.info(f"Created SRT file at {srt_path}")

        except Exception as e:
            logger.error(f"Failed to create SRT file: {e}")
            raise
        

    def _seconds_to_srt_time(self, seconds: float) -> str:
        """Convert seconds to SRT time format (HH:MM:SS,mmm)."""
        try:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            milliseconds = int((seconds % 1) * 1000)

            return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

        except Exception as e:
            logger.error(f"Failed to convert seconds to SRT time: {e}")
            return "00:00:00,000"

    def _upload_final_video(self, video_path: str, short_id: str, task_id: str) -> str:
        """Upload final video to Supabase storage."""
        try:
            if not supabase_manager.is_connected():
                raise Exception("Supabase connection not available")

            # Validate that the video file exists before attempting upload
            if not os.path.exists(video_path):
                raise Exception(f"Video file not found at path: {video_path}")
            
            # Check file size to ensure it's not empty
            file_size = os.path.getsize(video_path)
            if file_size == 0:
                raise Exception(f"Video file is empty (0 bytes) at path: {video_path}")
            
            logger.info(f"Uploading video file: {video_path} (size: {file_size} bytes)")

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
                raise Exception(
                    f"Failed to upload final video: {result.error}")

            # Get public URL
            final_video_url = supabase_manager.client.storage.from_(
                'generated-content').get_public_url(filename)

            logger.info(
                f"Successfully uploaded final video to {final_video_url}")
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
                raise Exception(
                    f"Failed to update shorts final video: {result.error}")

            logger.info(
                f"Updated shorts {short_id} with final video URL and completed status")

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
                        logger.debug(
                            f"Cleaned up empty directory: {parent_dir}")

        except Exception as e:
            logger.warning(f"Failed to cleanup some temporary files: {e}")

    def _cleanup_subtitle_temp_dirs(self):
        """Clean up subtitle temporary directories that may have been created."""
        try:
            # Clean up the subtitle temp directory at the same level as the app directory
            app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            temp_dir = os.path.join(app_dir, "temp_subtitles")
            
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.debug(f"Cleaned up subtitle temp directory: {temp_dir}")
                    
        except Exception as e:
            logger.warning(f"Failed to cleanup subtitle temp directory: {e}")

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

            logger.info(
                f"Cleaned up {len(completed_tasks)} completed finalization tasks")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def test_supabase_connection(self) -> Dict[str, Any]:
        """Test Supabase connection and storage access."""
        try:
            logger.info("Testing Supabase connection...")

            if not supabase_manager.is_connected():
                return {"success": False, "error": "Supabase not connected"}

            # Test basic connection
            try:
                # Test a simple query
                result = supabase_manager.client.table(
                    'shorts').select('id').limit(1).execute()
                logger.info("Basic Supabase connection test passed")
            except Exception as e:
                logger.error(f"Basic connection test failed: {e}")
                return {"success": False, "error": f"Basic connection failed: {e}"}

            # Test storage access
            try:
                buckets = supabase_manager.client.storage.list_buckets()
                bucket_names = [bucket.name for bucket in buckets]
                logger.info(f"Available storage buckets: {bucket_names}")

                if 'generated-content' not in bucket_names:
                    return {"success": False, "error": "Storage bucket 'generated-content' not found"}

                logger.info("Storage access test passed")

            except Exception as e:
                logger.error(f"Storage access test failed: {e}")
                return {"success": False, "error": f"Storage access failed: {e}"}

            return {"success": True, "message": "All tests passed"}

        except Exception as e:
            logger.error(f"Supabase connection test failed: {e}")
            return {"success": False, "error": str(e)}


# Global instance
merging_service = MergingService()
