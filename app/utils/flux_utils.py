"""
Flux API utility functions for AI-powered image generation.
Provides easy-to-use interfaces for creating images using Black Forest Labs' Flux API.
"""

import os
import base64
import logging
import time
import requests
from typing import Dict, Any, Optional, Union, List
from pathlib import Path
from io import BytesIO

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logging.warning("Pillow package not available. Install with: pip install Pillow")

from app.config import settings

logger = logging.getLogger(__name__)


class FluxManager:
    """Manages Flux API client and provides utility methods for AI image generation."""
    
    def __init__(self):
        """Initialize Flux client with API credentials."""
        self.api_key = settings.BFL_API_KEY
        self.enabled = settings.BFL_ENABLED
        self.default_model = settings.BFL_DEFAULT_MODEL
        self.max_retries = settings.BFL_MAX_RETRIES
        self.timeout = settings.BFL_TIMEOUT
        self.polling_interval = settings.BFL_POLLING_INTERVAL
        
        if not self.api_key:
            logger.warning("Flux API key not configured. Image generation will be disabled.")
        elif not self.enabled:
            logger.warning("Flux is disabled in configuration. Image generation will be disabled.")
    
    def is_available(self) -> bool:
        """Check if Flux API is available and properly configured."""
        return (self.enabled and 
                bool(self.api_key) and 
                PIL_AVAILABLE)
    
    def is_pillow_available(self) -> bool:
        """Check if Pillow is available for image processing."""
        return PIL_AVAILABLE
    
    def get_supported_aspect_ratios(self) -> List[str]:
        """Get list of supported aspect ratios for Flux API."""
        return [
            "1:1",      # Square
            "16:9",     # Widescreen landscape
            "9:16",     # Portrait mobile
            "4:3",      # Traditional landscape
            "3:4",      # Traditional portrait
            "21:9",     # Ultra-wide
            "2:3",      # Portrait photo
            "3:2",      # Landscape photo
        ]
    
    def validate_aspect_ratio(self, aspect_ratio: str) -> bool:
        """Validate if the aspect ratio is supported."""
        return aspect_ratio in self.get_supported_aspect_ratios()
    
    def _encode_image_to_base64(self, image_path: Union[str, Path]) -> str:
        """
        Encode an image file to base64 string for API submission.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Base64 encoded string of the image
            
        Raises:
            FileNotFoundError: If image file doesn't exist
            Exception: If image encoding fails
        """
        try:
            image_path = Path(image_path)
            if not image_path.exists():
                raise FileNotFoundError(f"Image file not found: {image_path}")
            
            with open(image_path, "rb") as f:
                image_bytes = f.read()
                return base64.b64encode(image_bytes).decode("utf-8")
                
        except Exception as e:
            logger.error(f"Failed to encode image to base64: {e}")
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
                import tempfile
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
    
    def _poll_for_completion(self, request_id: str, polling_url: str) -> Dict[str, Any]:
        """
        Poll the Flux API for completion of image generation.
        
        Args:
            request_id: The request ID from the initial API call
            polling_url: The polling URL from the initial API call
            
        Returns:
            Dictionary containing the final result or error
            
        Raises:
            Exception: If polling fails or times out
        """
        start_time = time.time()
        
        while True:
            # Check timeout
            if time.time() - start_time > self.timeout:
                raise Exception(f"Image generation timed out after {self.timeout} seconds")
            
            try:
                logger.debug(f"Polling for completion: {request_id}")
                
                result = requests.get(
                    polling_url,
                    headers={
                        'accept': 'application/json',
                        'x-key': self.api_key,
                    },
                    params={'id': request_id},
                    timeout=30
                )
                result.raise_for_status()
                result_data = result.json()
                
                logger.debug(f"Polling result: {result_data}")
                
                if result_data['status'] == 'Ready':
                    logger.info(f"Image generation completed successfully: {result_data['result']['sample']}")
                    return result_data
                elif result_data['status'] in ['Error', 'Failed', 'Request Moderated', 'Content Moderated']:
                    if result_data['status'] in ['Request Moderated', 'Content Moderated']:
                        error_msg = f"Image generation failed due to content moderation: {result_data['status']}"
                        logger.warning(error_msg)
                    else:
                        error_msg = f"Image generation failed: {result_data}"
                        logger.error(error_msg)
                    raise Exception(error_msg)
                else:
                    # Still processing, wait and continue
                    logger.debug(f"Image generation in progress: {result_data['status']}")
                    time.sleep(self.polling_interval)
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error during polling: {e}")
                raise Exception(f"Polling failed: {e}")
            except Exception as e:
                logger.error(f"Unexpected error during polling: {e}")
                raise
    
    def _generate_image_core(
        self,
        prompt: str,
        input_image: Union[str, Path, None] = None,
        model: Optional[str] = None,
        output_path: str = "generated_image.png",
        aspect_ratio: str = "16:9"
    ) -> Dict[str, Any]:
        """
        Core image generation logic without retry mechanism.
        
        Args:
            prompt: Text prompt for image generation
            input_image: Optional URL or path to input image
            model: Flux model to use (default: flux-kontext-pro)
            output_path: Path to save the generated image
            aspect_ratio: Aspect ratio for the generated image (default: "16:9")
            
        Returns:
            Dictionary containing generation results and image path
            
        Raises:
            Exception: If image generation fails
        """
        if not self.is_available():
            raise RuntimeError("Flux API is not available or properly configured")
        
        if not PIL_AVAILABLE:
            raise RuntimeError("Pillow is required for image processing")
        
        if model is None:
            model = self.default_model
        
        # Validate aspect ratio
        if not self.validate_aspect_ratio(aspect_ratio):
            logger.warning(f"Unsupported aspect ratio '{aspect_ratio}'. Supported ratios: {self.get_supported_aspect_ratios()}")
            logger.info(f"Using aspect ratio '{aspect_ratio}' anyway - API may handle it or return an error")
        
        temp_file_path = None
        
        try:
            logger.info(f"Starting image generation with Flux model: {model}")
            logger.info(f"Prompt: {prompt}")
            logger.info(f"Aspect ratio: {aspect_ratio}")
            
            # Prepare the request payload
            payload = {
                'prompt': prompt,
                'aspect_ratio': aspect_ratio,
                'safety_tolerance': 6
            }
            
            # Handle input image if provided
            if input_image:
                try:
                    if str(input_image).startswith(('http://', 'https://')):
                        # Download image from URL
                        temp_file_path = self._download_image_from_url(str(input_image))
                        image_path = temp_file_path
                    else:
                        # Use local file path
                        image_path = str(input_image)
                    
                    # Encode image to base64
                    img_str = self._encode_image_to_base64(image_path)
                    payload['input_image'] = img_str
                    logger.info(f"Successfully loaded input image: {input_image}")
                    
                except Exception as download_error:
                    logger.error(f"Failed to process input image {input_image}: {download_error}")
                    raise download_error
            
            # Make the initial API request
            logger.info("Submitting image generation request to Flux API...")
            response = requests.post(
                'https://api.bfl.ai/v1/flux-kontext-max',
                headers={
                    'accept': 'application/json',
                    'x-key': self.api_key,
                    'Content-Type': 'application/json',
                },
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            request_data = response.json()
            logger.info(f"Request submitted successfully: {request_data}")
            
            request_id = request_data["id"]
            polling_url = request_data["polling_url"]
            
            # Poll for completion
            logger.info("Waiting for image generation to complete...")
            result = self._poll_for_completion(request_id, polling_url)
            
            # Download and save the generated image
            if 'result' in result and 'sample' in result['result']:
                image_url = result['result']['sample']
                logger.info(f"Downloading generated image from: {image_url}")
                
                # Download the generated image
                img_response = requests.get(image_url, timeout=30)
                img_response.raise_for_status()
                
                # Save the image
                with open(output_path, 'wb') as f:
                    f.write(img_response.content)
                
                logger.info(f"Generated image saved to: {output_path}")
                
                return {
                    "success": True,
                    "model": model,
                    "prompt": prompt,
                    "input_image": str(input_image) if input_image else None,
                    "aspect_ratio": aspect_ratio,
                    "image_saved": True,
                    "output_path": output_path,
                    "image_url": image_url,
                    "request_id": request_id,
                    "status": "completed"
                }
            else:
                raise Exception("No image result found in API response")
            
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "model": model,
                "prompt": prompt,
                "input_image": str(input_image) if input_image else None,
                "aspect_ratio": aspect_ratio,
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

    def generate_image_with_prompt_and_image(
        self,
        prompt: str,
        input_image: Union[str, Path, None] = None,
        model: Optional[str] = None,
        output_path: str = "generated_image.png",
        aspect_ratio: str = "16:9"
    ) -> Dict[str, Any]:
        """
        Generate an image using Flux API with retry logic.
        
        Args:
            prompt: Text prompt for image generation
            input_image: Optional URL or path to input image
            model: Flux model to use (default: flux-kontext-pro)
            output_path: Path to save the generated image
            aspect_ratio: Aspect ratio for the generated image (default: "16:9")
            
        Returns:
            Dictionary containing generation results and image path
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Image generation attempt {attempt + 1}/{self.max_retries}")
                
                result = self._generate_image_core(
                    prompt=prompt,
                    input_image=input_image,
                    model=model,
                    output_path=output_path,
                    aspect_ratio=aspect_ratio
                )
                
                # If we get here, generation was successful
                if attempt > 0:
                    logger.info(f"Image generation succeeded on attempt {attempt + 1}")
                return result
                
            except Exception as e:
                last_exception = e
                logger.warning(f"Image generation attempt {attempt + 1} failed: {e}")
                
                # Don't retry for certain types of errors
                if self._should_not_retry(e):
                    logger.error(f"Non-retryable error encountered: {e}")
                    break
                
                # If this was the last attempt, don't wait
                if attempt < self.max_retries - 1:
                    wait_time = min(2 ** attempt, 30)  # Exponential backoff, max 30 seconds
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
        
        # All retries failed
        logger.error(f"Image generation failed after {self.max_retries} attempts")
        return {
            "success": False,
            "error": f"Failed after {self.max_retries} attempts. Last error: {str(last_exception)}",
            "model": model,
            "prompt": prompt,
            "input_image": str(input_image) if input_image else None,
            "aspect_ratio": aspect_ratio,
            "status": "error",
            "attempts": self.max_retries
        }
    
    def _should_not_retry(self, exception: Exception) -> bool:
        """
        Determine if an exception should not trigger a retry.
        
        Args:
            exception: The exception that occurred
            
        Returns:
            True if the exception should not trigger a retry
        """
        error_message = str(exception).lower()
        
        # Don't retry for configuration errors
        if "not available" in error_message or "not configured" in error_message:
            return True
        
        # Don't retry for content moderation errors
        if "moderated" in error_message:
            return True
        
        # Don't retry for invalid input errors
        if "invalid" in error_message and ("prompt" in error_message or "aspect" in error_message):
            return True
        
        # Don't retry for authentication errors
        if "unauthorized" in error_message or "forbidden" in error_message:
            return True
        
        return False


# Global instance for easy access
flux_manager = FluxManager()


# Convenience function for easy usage
def generate_image_with_prompt_and_image(
    prompt: str,
    input_image: Union[str, Path, None] = None,
    model: Optional[str] = None,
    output_path: str = "generated_image.png",
    aspect_ratio: str = "16:9"
) -> Dict[str, Any]:
    """Convenience function to generate image with prompt and optional input image."""
    return flux_manager.generate_image_with_prompt_and_image(
        prompt, input_image, model, output_path, aspect_ratio
    )


def is_flux_available() -> bool:
    """Check if Flux API is available and configured."""
    return flux_manager.is_available()


def is_pillow_available() -> bool:
    """Check if Pillow is available for image processing."""
    return flux_manager.is_pillow_available()


def get_flux_status() -> Dict[str, Any]:
    """Get Flux API service status and configuration."""
    return {
        "available": flux_manager.is_available(),
        "enabled": settings.BFL_ENABLED,
        "configured": bool(settings.BFL_API_KEY),
        "pillow_available": flux_manager.is_pillow_available(),
        "model": settings.BFL_DEFAULT_MODEL,
        "timeout": settings.BFL_TIMEOUT,
        "polling_interval": settings.BFL_POLLING_INTERVAL,
        "supported_aspect_ratios": flux_manager.get_supported_aspect_ratios()
    }
