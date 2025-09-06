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
    
    def _download_image_from_url(self, image_url: str, max_retries: int = 3) -> str:
        """
        Download image from URL to a temporary file and return the file path.
        Handles 403 Forbidden errors with different strategies and retries.
        
        Args:
            image_url: URL of the image to download
            max_retries: Maximum number of retry attempts
            
        Returns:
            Path to the temporary file containing the downloaded image
            
        Raises:
            Exception: If all download attempts fail
        """
        headers_list = [
            # Standard browser headers
            {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            },
            # Mobile browser headers
            {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            },
            # Simple headers
            {
                'User-Agent': 'Mozilla/5.0 (compatible; ImageDownloader/1.0)',
                'Accept': '*/*',
            }
        ]
        
        last_exception = None
        
        for attempt in range(max_retries):
            headers = headers_list[attempt % len(headers_list)]
            
            try:
                logger.info(f"Downloading image from URL (attempt {attempt + 1}/{max_retries}): {image_url}")
                logger.debug(f"Using headers: {headers}")
                
                response = requests.get(image_url, headers=headers, timeout=30, allow_redirects=True)
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
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 403:
                    logger.warning(f"403 Forbidden error on attempt {attempt + 1}: {e}")
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying with different headers...")
                        time.sleep(1)  # Brief delay before retry
                        continue
                else:
                    logger.error(f"HTTP error downloading image from URL {image_url}: {e}")
                    raise
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error downloading image from URL {image_url} (attempt {attempt + 1}): {e}")
                last_exception = e
                if attempt < max_retries - 1:
                    time.sleep(1)  # Brief delay before retry
                    continue
            except Exception as e:
                logger.error(f"Unexpected error downloading image from URL {image_url} (attempt {attempt + 1}): {e}")
                last_exception = e
                if attempt < max_retries - 1:
                    time.sleep(1)  # Brief delay before retry
                    continue
        
        # If all attempts failed, raise the last exception
        logger.error(f"Failed to download image from URL {image_url} after {max_retries} attempts")
        raise last_exception or Exception(f"Failed to download image from URL {image_url} after {max_retries} attempts")
    
    def _get_image_bytes_from_url(self, image_url: str, max_retries: int = 3) -> Tuple[bytes, str]:
        """
        Download image from URL and return bytes data and MIME type.
        Handles 403 Forbidden errors with different strategies and retries.
        
        Args:
            image_url: URL of the image to download
            max_retries: Maximum number of retry attempts
            
        Returns:
            Tuple of (image_bytes, mime_type)
            
        Raises:
            Exception: If all download attempts fail
        """
        headers_list = [
            # Standard browser headers
            {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            },
            # Mobile browser headers
            {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            },
            # Simple headers
            {
                'User-Agent': 'Mozilla/5.0 (compatible; ImageDownloader/1.0)',
                'Accept': '*/*',
            }
        ]
        
        last_exception = None
        
        for attempt in range(max_retries):
            headers = headers_list[attempt % len(headers_list)]
            
            try:
                logger.info(f"Downloading image bytes from URL (attempt {attempt + 1}/{max_retries}): {image_url}")
                logger.debug(f"Using headers: {headers}")
                
                response = requests.get(image_url, headers=headers, timeout=30, allow_redirects=True)
                response.raise_for_status()
                
                # Check if response contains image data
                content_type = response.headers.get('content-type', '')
                if not content_type.startswith('image/'):
                    logger.warning(f"URL does not contain image data: {content_type}")
                    raise ValueError(f"URL does not contain image data: {content_type}")
                
                logger.info(f"Successfully downloaded image bytes from URL: {image_url}")
                return response.content, content_type
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 403:
                    logger.warning(f"403 Forbidden error on attempt {attempt + 1}: {e}")
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying with different headers...")
                        time.sleep(1)  # Brief delay before retry
                        continue
                else:
                    logger.error(f"HTTP error downloading image bytes from URL {image_url}: {e}")
                    raise
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error downloading image bytes from URL {image_url} (attempt {attempt + 1}): {e}")
                last_exception = e
                if attempt < max_retries - 1:
                    time.sleep(1)  # Brief delay before retry
                    continue
            except Exception as e:
                logger.error(f"Unexpected error downloading image bytes from URL {image_url} (attempt {attempt + 1}): {e}")
                last_exception = e
                if attempt < max_retries - 1:
                    time.sleep(1)  # Brief delay before retry
                    continue
        
        # If all attempts failed, raise the last exception
        logger.error(f"Failed to download image bytes from URL {image_url} after {max_retries} attempts")
        raise last_exception or Exception(f"Failed to download image bytes from URL {image_url} after {max_retries} attempts")
    
    def _compress_image(self, image_path: str, quality: int = 85, max_size_mb: float = 5.0) -> str:
        """
        Compress an image file to reduce file size while maintaining dimensions.
        
        Args:
            image_path: Path to the input image file
            quality: JPEG quality (1-100, default: 85)
            max_size_mb: Maximum file size in MB (default: 5.0)
            
        Returns:
            Path to the compressed image file (may be the same as input if already small enough)
        """
        try:
            if not PIL_AVAILABLE:
                logger.warning("Pillow not available, skipping image compression")
                return image_path
            
            # Check current file size
            current_size_mb = os.path.getsize(image_path) / (1024 * 1024)
            logger.info(f"Original image size: {current_size_mb:.2f} MB")
            
            # If already small enough, return original path
            if current_size_mb <= max_size_mb:
                logger.info(f"Image size ({current_size_mb:.2f} MB) is already within limit ({max_size_mb} MB)")
                return image_path
            
            # Open the image
            with Image.open(image_path) as img:
                # Convert to RGB if necessary (JPEG doesn't support RGBA)
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Create white background for transparent images
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Create compressed version
                compressed_path = image_path.replace('.', '_compressed.')
                
                # Try different quality levels until we get under the size limit
                current_quality = quality
                while current_quality > 10 and os.path.getsize(image_path) / (1024 * 1024) > max_size_mb:
                    img.save(compressed_path, 'JPEG', quality=current_quality, optimize=True)
                    
                    compressed_size_mb = os.path.getsize(compressed_path) / (1024 * 1024)
                    logger.info(f"Compressed with quality {current_quality}: {compressed_size_mb:.2f} MB")
                    
                    if compressed_size_mb <= max_size_mb:
                        break
                    
                    current_quality -= 10
                
                # Replace original with compressed version
                if os.path.exists(compressed_path):
                    os.replace(compressed_path, image_path)
                    final_size_mb = os.path.getsize(image_path) / (1024 * 1024)
                    logger.info(f"Image compressed successfully: {current_size_mb:.2f} MB -> {final_size_mb:.2f} MB")
                else:
                    logger.warning("Compression failed, using original image")
            
            return image_path
            
        except Exception as e:
            logger.error(f"Failed to compress image {image_path}: {e}")
            return image_path
    
    
    
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
                    # Split aspect_ratio and compare width/height to set 16:9 or 9:16
                    # aspect_ratio = (
                    #     "9:16"
                    #     if (aspect_ratio and ":" in aspect_ratio and int(aspect_ratio.split(":")[0]) < int(aspect_ratio.split(":")[1]))
                    #     else "16:9"
                    # ),
                    aspect_ratio="16:9",
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