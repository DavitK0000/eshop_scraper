"""
RunwayML utility functions for AI-powered image and video generation.
Provides easy-to-use interfaces for creating images and videos using RunwayML's API.
"""

import os
import base64
import mimetypes
import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor

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
    
    async def generate_image_from_text(
        self,
        prompt_text: str,
        model: str = None,
        ratio: str = None,
        reference_images: List[Dict[str, str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate an image from text using RunwayML's text-to-image model.
        
        Args:
            prompt_text: Text prompt for image generation
            model: Model to use (default: gen4_image)
            ratio: Image aspect ratio (default: 1920:1080)
            reference_images: List of reference images with tags
            **kwargs: Additional parameters for image generation
            
        Returns:
            Dictionary containing task results and image URL
        """
        if not self.is_available():
            raise RuntimeError("RunwayML is not available or properly configured")
        
        # Set defaults
        model = model or "gen4_image"
        ratio = ratio or "1920:1080"
        
        try:
            logger.info(f"Starting image generation with model {model}")
            
            # Prepare reference images if provided
            processed_reference_images = None
            if reference_images:
                processed_reference_images = []
                for ref_img in reference_images:
                    processed_ref = {
                        "uri": self._get_image_from_url_or_path(ref_img["uri"]),
                        "tag": ref_img.get("tag")
                    }
                    processed_reference_images.append(processed_ref)
            
            # Create image generation task
            task_params = {
                "model": model,
                "prompt_text": prompt_text,
                "ratio": ratio,
                **kwargs
            }
            
            if processed_reference_images:
                task_params["reference_images"] = processed_reference_images
            
            task = self.client.text_to_image.create(**task_params)
            
            # Wait for task completion
            result = task.wait_for_task_output()
            
            logger.info("Image generation completed successfully")
            
            return {
                "success": True,
                "model": model,
                "prompt_text": prompt_text,
                "ratio": ratio,
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
    
    async def generate_image_with_reference_style(
        self,
        prompt_text: str,
        reference_image: Union[str, Path],
        style_image: Union[str, Path] = None,
        model: str = None,
        ratio: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate an image with a specific reference and optional style.
        
        Args:
            prompt_text: Text prompt for image generation
            reference_image: Reference image for the subject
            style_image: Optional style reference image
            model: Model to use (default: gen4_image)
            ratio: Image aspect ratio (default: 1920:1080)
            **kwargs: Additional parameters for image generation
            
        Returns:
            Dictionary containing task results and image URL
        """
        if not self.is_available():
            raise RuntimeError("RunwayML is not available or properly configured")
        
        # Set defaults
        model = model or "gen4_image"
        ratio = ratio or "1920:1080"
        
        try:
            logger.info(f"Starting styled image generation with model {model}")
            
            # Prepare reference images
            reference_images = [
                {
                    "uri": self._get_image_from_url_or_path(reference_image),
                    "tag": "reference"
                }
            ]
            
            if style_image:
                reference_images.append({
                    "uri": self._get_image_from_url_or_path(style_image)
                    # No tag for style image
                })
            
            # Create image generation task
            task = self.client.text_to_image.create(
                model=model,
                prompt_text=prompt_text,
                ratio=ratio,
                reference_images=reference_images,
                **kwargs
            )
            
            # Wait for task completion
            result = task.wait_for_task_output()
            
            logger.info("Styled image generation completed successfully")
            
            return {
                "success": True,
                "model": model,
                "prompt_text": prompt_text,
                "ratio": ratio,
                "output": result.output,
                "task_id": result.id,
                "status": "completed"
            }
            
        except TaskFailedError as e:
            logger.error(f"Styled image generation failed: {e}")
            return {
                "success": False,
                "error": "Styled image generation failed",
                "task_details": e.task_details,
                "status": "failed"
            }
        except Exception as e:
            logger.error(f"Unexpected error during styled image generation: {e}")
            return {
                "success": False,
                "error": str(e),
                "status": "error"
            }
    
    def get_available_models(self) -> Dict[str, List[str]]:
        """Get available models for different generation types."""
        return {
            "image_to_video": ["gen4_turbo"],
            "text_to_image": ["gen4_image"],
            "default_models": {
                "video": "gen4_turbo",
                "image": "gen4_image"
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


async def generate_image_from_text(
    prompt_text: str,
    **kwargs
) -> Dict[str, Any]:
    """Convenience function to generate image from text."""
    return await runwayml_manager.generate_image_from_text(
        prompt_text, **kwargs
    )


async def generate_image_with_reference_style(
    prompt_text: str,
    reference_image: Union[str, Path],
    style_image: Union[str, Path] = None,
    **kwargs
) -> Dict[str, Any]:
    """Convenience function to generate styled image with reference."""
    return await runwayml_manager.generate_image_with_reference_style(
        prompt_text, reference_image, style_image, **kwargs
    )


def is_runwayml_available() -> bool:
    """Check if RunwayML is available and configured."""
    return runwayml_manager.is_available()


def get_runwayml_status() -> Dict[str, Any]:
    """Get RunwayML service status and configuration."""
    return {
        "available": runwayml_manager.is_available(),
        "enabled": settings.RUNWAYML_ENABLED,
        "configured": bool(settings.RUNWAYML_API_SECRET),
        "package_available": RUNWAYML_AVAILABLE,
        "models": runwayml_manager.get_available_models() if runwayml_manager.is_available() else None,
        "supported_ratios": runwayml_manager.get_supported_ratios() if runwayml_manager.is_available() else None,
        "supported_durations": runwayml_manager.get_supported_durations() if runwayml_manager.is_available() else None
    }
