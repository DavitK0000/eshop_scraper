"""
RunwayML utility functions for AI-powered video generation.
Provides easy-to-use interfaces for creating videos using RunwayML's API.
Note: Image generation has been moved to Flux API (flux_utils.py).
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
    
    async def generate_video_from_image(
        self,
        prompt_image: Union[str, Path],
        prompt_text: str = "Generate a video",
        model: str = None,
        ratio: str = None,
        duration: int = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a video from an image using RunwayML's image-to-video model.
        
        Args:
            prompt_image: Path to image file or image URL
            prompt_text: Text prompt for video generation
            model: Model to use (default: gen4_turbo)
            ratio: Video aspect ratio (default: 1280:720)
            duration: Video duration in seconds (default: 5)
            **kwargs: Additional parameters for video generation
            
        Returns:
            Dictionary containing task results and video URL
        """
        if not self.is_available():
            raise RuntimeError("RunwayML is not available or properly configured")
        
        # Set defaults
        model = model or settings.RUNWAYML_DEFAULT_MODEL
        ratio = ratio or settings.RUNWAYML_DEFAULT_RATIO
        duration = duration or settings.RUNWAYML_DEFAULT_DURATION
        
        try:
            # Convert image to data URI if it's a local file
            image_uri = self._get_image_from_url_or_path(prompt_image)
            
            logger.info(f"Starting video generation with model {model}")
            
            # Create video generation task
            task = self.client.image_to_video.create(
                model=model,
                prompt_image=image_uri,
                prompt_text=prompt_text,
                ratio=ratio,
                duration=duration,
                **kwargs
            )
            
            # Wait for task completion
            result = task.wait_for_task_output()
            
            logger.info("Video generation completed successfully")
            
            return {
                "success": True,
                "model": model,
                "prompt_text": prompt_text,
                "ratio": ratio,
                "duration": duration,
                "output": result.output,
                "task_id": result.id,
                "status": "completed"
            }
            
        except TaskFailedError as e:
            logger.error(f"Video generation failed: {e}")
            return {
                "success": False,
                "error": "Video generation failed",
                "task_details": e.task_details,
                "status": "failed"
            }
        except Exception as e:
            logger.error(f"Unexpected error during video generation: {e}")
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
            "image_to_video": ["gen4_turbo"],
            "default_models": {
                "video": "gen4_turbo"
            }
        }
    
    def get_supported_ratios(self) -> List[str]:
        """Get supported aspect ratios."""
        return [
            "1280:720",   # 16:9 landscape
            "1920:1080",  # 16:9 HD
            "1080:1920",  # 9:16 portrait
            "720:1280",   # 9:16 mobile
            "1024:1024",  # 1:1 square
            "1920:1920"   # 1:1 high-res square
        ]
    
    def get_supported_durations(self) -> List[int]:
        """Get supported video durations in seconds."""
        return [5, 10]


# Global instance for easy access
runwayml_manager = RunwayMLManager()


# Convenience functions for easy usage
async def generate_video_from_image(
    prompt_image: Union[str, Path],
    prompt_text: str = "Generate a video",
    **kwargs
) -> Dict[str, Any]:
    """Convenience function to generate video from image."""
    return await runwayml_manager.generate_video_from_image(
        prompt_image, prompt_text, **kwargs
    )




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
        "supported_durations": runwayml_manager.get_supported_durations() if runwayml_manager.is_available() else None
    }
