"""
Google Gemini utility functions for AI-powered image generation.
Provides easy-to-use interfaces for creating images using Google's Gemini API.
"""

import os
import base64
import mimetypes
import logging
import tempfile
import requests
import time
from typing import Dict, List, Any, Optional, Union, Tuple
from pathlib import Path
from io import BytesIO

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logging.warning("Pillow package not available. Install with: pip install Pillow")

try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logging.warning("Google Gemini package not available. Install with: pip install google-generativeai")

from app.config import settings

logger = logging.getLogger(__name__)


class GeminiManager:
    """Manages Google Gemini client and provides utility methods for AI generation."""
    
    def __init__(self):
        """Initialize Gemini client with API credentials."""
        self.client: Optional[genai.Client] = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the Gemini client with API credentials."""
        if not GEMINI_AVAILABLE:
            logger.warning("Google Gemini package not available. AI generation will be disabled.")
            return
            
        if not settings.GEMINI_ENABLED:
            logger.warning("Gemini is disabled in configuration. AI generation will be disabled.")
            return
            
        if not settings.GEMINI_API_KEY:
            logger.warning("Gemini API key not configured. AI generation will be disabled.")
            return
        
        try:
            # Initialize Gemini client
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            logger.info("Gemini client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            self.client = None
    
    def is_available(self) -> bool:
        """Check if Gemini is available and properly configured."""
        return (GEMINI_AVAILABLE and 
                settings.GEMINI_ENABLED and 
                settings.GEMINI_API_KEY and 
                self.client is not None)
    
    def is_pillow_available(self) -> bool:
        """Check if Pillow is available for image processing."""
        return PIL_AVAILABLE
    
    def _get_image_as_data_uri(self, image_path: Union[str, Path]) -> str:
        """Convert an image file to a data URI."""
        try:
            image_path = Path(image_path)
            if not image_path.exists():
                raise FileNotFoundError(f"Image file not found: {image_path}")
            
            with open(image_path, "rb") as f:
                base64_image = base64.b64encode(f.read()).decode("utf-8")
            
            # Get MIME type
            content_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
            return f"data:{content_type};base64,{base64_image}"
            
        except Exception as e:
            logger.error(f"Failed to convert image to data URI: {e}")
            raise
    
    def _download_image_from_url(self, image_url: str) -> str:
        """
        Download image from URL to a temporary file and return the file path.
        
        Args:
            image_url: URL of the image to download
            
        Returns:
            Path to the temporary file containing the downloaded image
        """
        try:
            logger.info(f"Downloading image from URL: {image_url}")
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # Check if response contains image data
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                logger.warning(f"URL does not contain image data: {content_type}")
                raise ValueError(f"URL does not contain image data: {content_type}")
            
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            temp_file.write(response.content)
            temp_file.close()
            
            logger.info(f"Successfully downloaded image to temporary file: {temp_file.name}")
            return temp_file.name
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download image from URL {image_url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error downloading image from URL {image_url}: {e}")
            raise
    
    def _get_image_bytes_from_url(self, image_url: str) -> Tuple[bytes, str]:
        """
        Download image from URL and return bytes data and MIME type.
        
        Args:
            image_url: URL of the image to download
            
        Returns:
            Tuple of (image_bytes, mime_type)
        """
        try:
            logger.info(f"Downloading image bytes from URL: {image_url}")
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # Check if response contains image data
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                logger.warning(f"URL does not contain image data: {content_type}")
                raise ValueError(f"URL does not contain image data: {content_type}")
            
            logger.info(f"Successfully downloaded image bytes from URL: {image_url}")
            return response.content, content_type
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download image bytes from URL {image_url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error downloading image bytes from URL {image_url}: {e}")
            raise
    
    def generate_image_with_prompt_and_image(
        self,
        prompt: str,
        input_image: Union[str, Path, None] = None,
        model: str = "gemini-2.5-flash-image-preview",
        output_path: str = "generated_image.png"
    ) -> Dict[str, Any]:
        """
        Generate an image using Google Gemini with a text prompt and optional input image.
        
        Args:
            prompt: Text prompt for image generation
            input_image: Optional URL to input image (will be downloaded to temp folder)
            model: Gemini model to use (default: gemini-2.5-flash-image-preview)
            output_path: Path to save the generated image
            
        Returns:
            Dictionary containing generation results and image path
        """
        if not self.is_available():
            raise RuntimeError("Gemini is not available or properly configured")
        
        if not PIL_AVAILABLE:
            raise RuntimeError("Pillow is required for image processing")
        
        temp_file_path = None
        
        try:
            logger.info(f"Starting image generation with model {model}")
            
            # Prepare contents for the API call
            contents = [prompt]
            
            # Handle input image if provided
            if input_image:
                # Download image from URL to temporary file
                temp_file_path = self._download_image_from_url(str(input_image))
                
                # Convert temporary file to data URI
                image_uri = self._get_image_as_data_uri(temp_file_path)
                contents.append(image_uri)
            
            # Generate content using Gemini
            response = self.client.models.generate_content(
                model=model,
                contents=contents,
            )
            # Process the response
            generated_text = ""
            image_saved = False
            
            for part in response.candidates[0].content.parts:
                if part.text is not None:
                    generated_text += part.text
                elif part.inline_data is not None:
                    # Save the generated image
                    image = Image.open(BytesIO(part.inline_data.data))
                    image.save(output_path)
                    image_saved = True
                    logger.info(f"Generated image saved to: {output_path}")
            
            return {
                "success": True,
                "model": model,
                "prompt": prompt,
                "generated_text": generated_text,
                "image_saved": image_saved,
                "output_path": output_path if image_saved else None,
                "status": "completed"
            }
            
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "status": "error"
            }
        finally:
            # Clean up temporary file if it was created
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                    logger.info(f"Cleaned up temporary file: {temp_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {temp_file_path}: {e}")
    
    def generate_video_with_prompt_and_image(
        self,
        prompt: str,
        image_url: str,
        model: str = "veo-3.0-generate-preview",
        file_path: Optional[str] = None,
        aspect_ratio: str = "16:9",
        number_of_videos: int = 1,
        negative_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a video using Google Gemini with a text prompt and image URL.
        
        Args:
            prompt: Text prompt for video generation
            image_url: URL of the input image
            model: Gemini model to use (default: veo-3.0-generate-preview)
            file_path: Optional path to save the generated video(s)
            aspect_ratio: Aspect ratio for the video (default: "16:9")
            number_of_videos: Number of videos to generate (default: 1)
            negative_prompt: Optional negative prompt
            
        Returns:
            Dictionary containing generation results and video paths
        """
        if not self.is_available():
            raise RuntimeError("Gemini is not available or properly configured")
        
        try:
            logger.info(f"Starting video generation with model {model}")
            
            # Get image bytes and MIME type from URL
            image_bytes, mime_type = self._get_image_bytes_from_url(image_url)
            
            # Create image object for the API
            image_obj = types.Image(image_bytes=image_bytes, mime_type=mime_type)
            
            # Create video generation operation
            operation = self.client.models.generate_videos(
                model=model,
                prompt=prompt,
                image=image_obj,
                config=types.GenerateVideosConfig(
                    aspect_ratio=aspect_ratio,
                    number_of_videos=number_of_videos,
                    negative_prompt=negative_prompt,
                ),
            )
            
            # Wait for the video(s) to be generated
            logger.info("Waiting for video generation to complete...")
            while not operation.done:
                time.sleep(3)
                operation = self.client.operations.get(operation)
                logger.info(f"Video generation status: {operation}")
            
            logger.info("Video generation completed successfully")
            
            # Process generated videos
            generated_videos = operation.result.generated_videos
            video_paths = []
            
            for n, generated_video in enumerate(generated_videos):
                # Download the video file
                self.client.files.download(file=generated_video.video)
                
                # Save video if file_path is provided
                if file_path:
                    if number_of_videos > 1:
                        # If multiple videos, add index to filename
                        base_path = Path(file_path)
                        video_filename = f"{base_path.stem}_{n}{base_path.suffix}"
                        video_path = base_path.parent / video_filename
                    else:
                        video_path = file_path
                    
                    generated_video.video.save(str(video_path))
                    video_paths.append(str(video_path))
                    logger.info(f"Video saved to: {video_path}")
                else:
                    # Just store the video object reference
                    video_paths.append(generated_video.video)
            
            return {
                "success": True,
                "model": model,
                "prompt": prompt,
                "image_url": image_url,
                "aspect_ratio": aspect_ratio,
                "number_of_videos": number_of_videos,
                "negative_prompt": negative_prompt,
                "generated_videos": generated_videos,
                "video_paths": video_paths,
                "status": "completed"
            }
            
        except Exception as e:
            logger.error(f"Video generation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "status": "error"
            }


# Global instance for easy access
gemini_manager = GeminiManager()


# Convenience function for easy usage
def generate_image_with_prompt_and_image(
    prompt: str,
    input_image: Union[str, Path, None] = None,
    model: str = "gemini-2.5-flash-image-preview",
    output_path: str = "generated_image.png"
) -> Dict[str, Any]:
    """Convenience function to generate image with prompt and optional input image URL."""
    return gemini_manager.generate_image_with_prompt_and_image(
        prompt, input_image, model, output_path
    )


def generate_video_with_prompt_and_image(
    prompt: str,
    image_url: str,
    model: str = "veo-3.0-generate-preview",
    file_path: Optional[str] = None,
    aspect_ratio: str = "16:9",
    number_of_videos: int = 1,
    negative_prompt: Optional[str] = None
) -> Dict[str, Any]:
    """Convenience function to generate video with prompt and image URL."""
    return gemini_manager.generate_video_with_prompt_and_image(
        prompt, image_url, model, file_path, aspect_ratio, number_of_videos, negative_prompt
    )


def is_gemini_available() -> bool:
    """Check if Gemini is available and configured."""
    return gemini_manager.is_available()


def is_pillow_available() -> bool:
    """Check if Pillow is available for image processing."""
    return gemini_manager.is_pillow_available()


def get_gemini_status() -> Dict[str, Any]:
    """Get Gemini service status and configuration."""
    return {
        "available": gemini_manager.is_available(),
        "enabled": settings.GEMINI_ENABLED,
        "configured": bool(settings.GEMINI_API_KEY),
        "package_available": GEMINI_AVAILABLE,
        "pillow_available": gemini_manager.is_pillow_available()
    }