"""
RunwayML utility functions for AI-powered image and video processing.
Provides easy-to-use interfaces for image generation and video upscaling using RunwayML's API.
Features:
- Image generation with reference images using Gen-4 model
- Video upscaling using RunwayML's upscaling models
Note: Basic image generation has been moved to Flux API (flux_utils.py).
Video generation functionality has been removed from this module.
"""

import os
import base64
import mimetypes
import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor
import requests
from io import BytesIO

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logging.warning("Pillow package not available. Install with: pip install Pillow")

try:
    from runwayml import RunwayML, TaskFailedError
    RUNWAYML_AVAILABLE = True
except ImportError:
    RUNWAYML_AVAILABLE = False
    logging.warning("RunwayML package not available. Install with: pip install runwayml")

from app.config import settings

logger = logging.getLogger(__name__)


class RunwayMLManager:
    """Manages RunwayML client and provides utility methods for AI generation."""
    
    def __init__(self):
        """Initialize RunwayML client with API credentials."""
        self.client: Optional[RunwayML] = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the RunwayML client with API credentials."""
        if not RUNWAYML_AVAILABLE:
            logger.warning("RunwayML package not available. AI generation will be disabled.")
            return
            
        if not settings.RUNWAYML_ENABLED:
            logger.warning("RunwayML is disabled in configuration. AI generation will be disabled.")
            return
            
        if not settings.RUNWAYML_API_SECRET:
            logger.warning("RunwayML API secret not configured. AI generation will be disabled.")
            return
        
        try:
            # Initialize RunwayML client
            self.client = RunwayML()
            logger.info("RunwayML client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize RunwayML client: {e}")
            self.client = None
    
    def is_available(self) -> bool:
        """Check if RunwayML is available and properly configured."""
        return (RUNWAYML_AVAILABLE and 
                settings.RUNWAYML_ENABLED and 
                settings.RUNWAYML_API_SECRET and 
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
    
    def _get_image_from_url_or_path(self, image_source: Union[str, Path]) -> str:
        """Get image as data URI from either a file path or URL."""
        if isinstance(image_source, (str, Path)):
            # Check if it's a file path
            if os.path.exists(str(image_source)) or Path(image_source).exists():
                return self._get_image_as_data_uri(image_source)
            # Assume it's a URL
            return str(image_source)
        return str(image_source)
    
    def _fetch_image_from_url(self, image_url: str) -> Optional[bytes]:
        """
        Fetch image data from a URL.
        
        Args:
            image_url: URL of the image to fetch
            
        Returns:
            Image data as bytes if successful, None otherwise
        """
        try:
            logger.info(f"Fetching image from URL: {image_url}")
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # Check if response contains image data
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                logger.warning(f"URL does not contain image data: {content_type}")
                return None
                
            logger.info(f"Successfully fetched image from URL: {image_url}")
            return response.content
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch image from URL {image_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching image from URL {image_url}: {e}")
            return None
    
    def _convert_image_to_png_data_uri(self, image_data: bytes) -> str:
        """
        Convert image data to PNG format and return as data URI.
        
        Args:
            image_data: Raw image data as bytes
            
        Returns:
            PNG image as data URI
        """
        if not PIL_AVAILABLE:
            logger.error("Pillow not available, cannot convert image to PNG")
            raise RuntimeError("Pillow not available for image conversion")
            
        try:
            # Open image from bytes
            image = Image.open(BytesIO(image_data))
            
            # Convert to RGB if necessary (PNG supports RGBA, but some models prefer RGB)
            if image.mode in ('RGBA', 'LA', 'P'):
                # Create white background for transparent images
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Convert to PNG bytes
            png_buffer = BytesIO()
            image.save(png_buffer, format='PNG', optimize=True)
            png_data = png_buffer.getvalue()
            
            # Convert to base64 data URI
            base64_image = base64.b64encode(png_data).decode("utf-8")
            data_uri = f"data:image/png;base64,{base64_image}"
            
            logger.info("Successfully converted image to PNG data URI")
            return data_uri
            
        except Exception as e:
            logger.error(f"Failed to convert image to PNG: {e}")
            raise
    
    def _fetch_and_convert_image(self, image_url: str) -> Optional[str]:
        """
        Fetch image from URL and convert to PNG data URI.
        
        Args:
            image_url: URL of the image to fetch
            
        Returns:
            PNG image as data URI if successful, None otherwise
        """
        try:
            image_data = self._fetch_image_from_url(image_url)
            if image_data is None:
                return None
                
            return self._convert_image_to_png_data_uri(image_data)
            
        except Exception as e:
            logger.error(f"Failed to fetch and convert image from {image_url}: {e}")
            return None
    
    def _create_reference_image(self, image_source: Union[str, Path], tag: str = "reference") -> Dict[str, str]:
        """
        Create a reference image object for RunwayML API.
        
        Args:
            image_source: Path to image file or image URL
            tag: Tag name for the reference image (3-16 characters, alphanumeric + underscore, starts with letter)
            
        Returns:
            Dictionary with uri and tag for reference image
        """
        # Validate tag
        if not (3 <= len(tag) <= 16):
            raise ValueError("Tag must be 3-16 characters long")
        
        if not tag[0].isalpha():
            raise ValueError("Tag must start with a letter")
        
        if not all(c.isalnum() or c == '_' for c in tag):
            raise ValueError("Tag must contain only alphanumeric characters and underscores")
        
        # Convert image to data URI if it's a local file
        uri = self._get_image_from_url_or_path(image_source)
        
        return {
            "uri": uri,
            "tag": tag
        }
    
    async def generate_image_from_text(
        self,
        prompt_text: str,
        ratio: str = "1920:1080",
        model: str = "gen4_image",
        seed: Optional[int] = None,
        reference_images: Optional[List[Dict[str, str]]] = None,
        content_moderation: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate an image from text using RunwayML's text-to-image API.
        
        Args:
            prompt_text: Text prompt describing the desired image (max 1000 characters)
            ratio: Resolution ratio for the output image (default: "1920:1080")
            model: Model variant to use - "gen4_image" or "gen4_image_turbo" (default: "gen4_image")
            seed: Random seed for reproducible results (0-4294967295)
            reference_images: List of reference images with uri and tag
            content_moderation: Content moderation settings
            **kwargs: Additional parameters for image generation
            
        Returns:
            Dictionary containing task results and generated image URL
        """
        if not self.is_available():
            raise RuntimeError("RunwayML is not available or properly configured")
        
        # Validate prompt length
        if len(prompt_text) > 1000:
            raise ValueError("Prompt text must be 1000 characters or less")
        
        # Validate model
        if model not in ["gen4_image", "gen4_image_turbo"]:
            raise ValueError("Model must be 'gen4_image' or 'gen4_image_turbo'")
        
        # For gen4_image_turbo, at least one reference image is required
        if model == "gen4_image_turbo" and (not reference_images or len(reference_images) == 0):
            raise ValueError("gen4_image_turbo requires at least one reference image")
        
        try:
            logger.info(f"Starting image generation with model {model}")
            
            # Prepare request parameters
            request_params = {
                "promptText": prompt_text,
                "ratio": ratio,
                "model": model
            }
            
            # Add optional parameters
            if seed is not None:
                request_params["seed"] = seed
            
            if reference_images:
                request_params["referenceImages"] = reference_images
            
            if content_moderation:
                request_params["contentModeration"] = content_moderation
            
            # Add any additional kwargs
            request_params.update(kwargs)
            
            # Create image generation task using text-to-image endpoint
            task = self.client.text_to_image.create(**request_params)
            
            # Wait for task completion
            result = task.wait_for_task_output()
            
            logger.info("Image generation completed successfully")
            
            return {
                "success": True,
                "prompt_text": prompt_text,
                "ratio": ratio,
                "model": model,
                "seed": seed,
                "output": result.output,
                "task_id": result.id,
                "status": "completed"
            }
            
        except TaskFailedError as e:
            logger.error(f"Image generation failed: {e}")
            return {
                "success": False,
                "error": "Image generation failed",
                "task_details": e.task_details,
                "status": "failed"
            }
        except Exception as e:
            logger.error(f"Unexpected error during image generation: {e}")
            return {
                "success": False,
                "error": str(e),
                "status": "error"
            }
    
    async def upscale_video(
        self,
        video_path: Union[str, Path],
        model: str = "upscale_v1",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Upscale video using RunwayML's video upscaling model.
        
        Args:
            video_path: Path to video file
            model: Model to use for upscaling (default: upscale_v1)
            **kwargs: Additional parameters for video upscaling
            
        Returns:
            Dictionary containing task results and upscaled video URL
        """
        if not self.is_available():
            raise RuntimeError("RunwayML is not available or properly configured")
        
        try:
            # Convert video to data URI if it's a local file
            video_uri = self._get_video_from_url_or_path(video_path)
            
            logger.info(f"Starting video upscaling with model {model}")
            
            # Create video upscaling task
            task = self.client.video_upscale.create(
                model=model,
                video_uri=video_uri,
                **kwargs
            )
            
            # Wait for task completion
            result = task.wait_for_task_output()
            
            logger.info("Video upscaling completed successfully")
            
            return {
                "success": True,
                "model": model,
                "output": result.output,
                "task_id": result.id,
                "status": "completed"
            }
            
        except TaskFailedError as e:
            logger.error(f"Video upscaling failed: {e}")
            return {
                "success": False,
                "error": "Video upscaling failed",
                "task_details": e.task_details,
                "status": "failed"
            }
        except Exception as e:
            logger.error(f"Unexpected error during video upscaling: {e}")
            return {
                "success": False,
                "error": str(e),
                "status": "error"
            }

    def upscale_video_sync(
        self,
        video_path: Union[str, Path],
        model: str = "upscale_v1",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Upscale video using RunwayML's video upscaling model (synchronous version).
        
        Args:
            video_path: Path to video file
            model: Model to use for upscaling (default: upscale_v1)
            **kwargs: Additional parameters for video upscaling
            
        Returns:
            Dictionary containing task results and upscaled video URL
        """
        if not self.is_available():
            raise RuntimeError("RunwayML is not available or properly configured")
        
        try:
            # Convert video to data URI if it's a local file
            video_uri = self._get_video_from_url_or_path(video_path)
            
            logger.info(f"Starting video upscaling with model {model}")
            
            # Create video upscaling task
            task = self.client.video_upscale.create(
                model=model,
                video_uri=video_uri,
                **kwargs
            )
            
            # Wait for task completion
            result = task.wait_for_task_output()
            
            logger.info("Video upscaling completed successfully")
            
            return {
                "success": True,
                "model": model,
                "output": result.output,
                "task_id": result.id,
                "status": "completed"
            }
            
        except TaskFailedError as e:
            logger.error(f"Video upscaling failed: {e}")
            return {
                "success": False,
                "error": "Video upscaling failed",
                "task_details": e.task_details,
                "status": "failed"
            }
        except Exception as e:
            logger.error(f"Unexpected error during video upscaling: {e}")
            return {
                "success": False,
                "error": str(e),
                "status": "error"
            }

    def _get_video_from_url_or_path(self, video_source: Union[str, Path]) -> str:
        """Get video as data URI from either a file path or URL."""
        if isinstance(video_source, (str, Path)):
            # Check if it's a file path
            if os.path.exists(str(video_source)) or Path(video_source).exists():
                return self._get_video_as_data_uri(video_source)
            # Assume it's a URL
            return str(video_source)
        return str(video_source)
    
    def _get_video_as_data_uri(self, video_path: Union[str, Path]) -> str:
        """Convert a video file to a data URI."""
        try:
            video_path = Path(video_path)
            if not video_path.exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")
            
            with open(video_path, "rb") as f:
                base64_video = base64.b64encode(f.read()).decode("utf-8")
            
            # Get MIME type
            content_type = mimetypes.guess_type(str(video_path))[0] or "video/mp4"
            return f"data:{content_type};base64,{base64_video}"
            
        except Exception as e:
            logger.error(f"Failed to convert video to data URI: {e}")
            raise

    
    def get_available_models(self) -> Dict[str, List[str]]:
        """Get available models for different generation types."""
        return {
            "image_generation": ["gen4_image", "gen4_image_turbo"],
            "video_upscaling": ["upscale_v1"],
            "default_models": {
                "image": "gen4_image",
                "video_upscale": "upscale_v1"
            }
        }
    
    def get_supported_ratios(self) -> List[str]:
        """Get supported aspect ratios for image generation."""
        return [
            "1920:1080",  # 16:9 HD
            "1080:1920",  # 9:16 Portrait
            "1024:1024",  # 1:1 Square
            "1360:768",   # 16:9 Widescreen
            "1080:1080",  # 1:1 Square HD
            "1168:880",   # 4:3 Standard
            "1440:1080",  # 4:3 HD
            "1080:1440",  # 3:4 Portrait HD
            "1808:768",   # 21:9 Ultra-wide
            "2112:912",   # 21:9 Ultra-wide HD
            "1280:720",   # 16:9 HD
            "720:1280",   # 9:16 Mobile
            "720:720",    # 1:1 Square
            "960:720",    # 4:3 Standard
            "720:960",    # 3:4 Portrait
            "1680:720"    # 21:9 Ultra-wide
        ]
    
    def get_supported_resolutions(self) -> List[str]:
        """Get supported resolutions for image generation."""
        return [
            "720p",   # 1280x720
            "1080p",  # 1920x1080
            "1440p",  # 2560x1440
            "4K"      # 3840x2160
        ]


# Global instance for easy access
runwayml_manager = RunwayMLManager()


# Convenience functions for easy usage
async def generate_image_from_text(
    prompt_text: str,
    ratio: str = "1920:1080",
    model: str = "gen4_image",
    **kwargs
) -> Dict[str, Any]:
    """Convenience function to generate image from text."""
    return await runwayml_manager.generate_image_from_text(
        prompt_text, ratio, model, **kwargs
    )


def create_reference_image(
    image_source: Union[str, Path],
    tag: str = "reference"
) -> Dict[str, str]:
    """Convenience function to create reference image object."""
    return runwayml_manager._create_reference_image(image_source, tag)


async def upscale_video(
    video_path: Union[str, Path],
    **kwargs
) -> Dict[str, Any]:
    """Convenience function to upscale video."""
    return await runwayml_manager.upscale_video(
        video_path, **kwargs
    )


def upscale_video_sync(
    video_path: Union[str, Path],
    **kwargs
) -> Dict[str, Any]:
    """Convenience function to upscale video (synchronous)."""
    return runwayml_manager.upscale_video_sync(
        video_path, **kwargs
    )


def is_runwayml_available() -> bool:
    """Check if RunwayML is available and configured."""
    return runwayml_manager.is_available()


def is_pillow_available() -> bool:
    """Check if Pillow is available for image processing."""
    return runwayml_manager.is_pillow_available()


def get_runwayml_status() -> Dict[str, Any]:
    """Get RunwayML service status and configuration."""
    return {
        "available": runwayml_manager.is_available(),
        "enabled": settings.RUNWAYML_ENABLED,
        "configured": bool(settings.RUNWAYML_API_SECRET),
        "package_available": RUNWAYML_AVAILABLE,
        "pillow_available": runwayml_manager.is_pillow_available(),
        "models": runwayml_manager.get_available_models() if runwayml_manager.is_available() else None,
        "supported_ratios": runwayml_manager.get_supported_ratios() if runwayml_manager.is_available() else None,
        "supported_resolutions": runwayml_manager.get_supported_resolutions() if runwayml_manager.is_available() else None
    }
