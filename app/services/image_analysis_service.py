"""
Image Analysis Service for analyzing product images using OpenAI Vision API.
Handles multiple images simultaneously with retry logic and progress tracking.
"""

import asyncio
import concurrent.futures
import json
import logging
import threading
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import openai
from app.config import settings
from app.utils.supabase_utils import supabase_manager
from app.utils.task_management import (
    create_task, start_task, update_task_progress, 
    complete_task, fail_task, TaskType, TaskStatus
)
from app.logging_config import get_logger

logger = get_logger(__name__)


class ImageAnalysisService:
    """Service for analyzing product images using OpenAI Vision API"""
    
    def __init__(self):
        self.max_concurrent_analyses = 4  # Process 4 images simultaneously
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        
    def start_image_analysis_task(
        self,
        product_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Start an image analysis task for a product
        
        Args:
            product_id: Product ID to analyze images for
            user_id: User ID associated with the task
            
        Returns:
            Dict with task_id and initial status
        """
        try:
            # Create task in task management system
            task_id = create_task(
                TaskType.IMAGE_ANALYSIS,
                user_id=user_id,
                product_id=product_id
            )
            
            if not task_id:
                raise Exception("Failed to create image analysis task")
            
            # Start the task
            start_task(task_id)
            
            # Start background processing in a separate thread
            thread = threading.Thread(
                target=self._process_image_analysis_task,
                args=(task_id, product_id, user_id),
                daemon=True,  # Make thread daemon so it doesn't block app shutdown
                name=f"image_analysis_{task_id}"
            )
            thread.start()
            
            logger.info(f"Started image analysis thread for task {task_id}")
            
            return {
                "task_id": task_id,
                "status": "pending",
                "message": "Image analysis task started"
            }
            
        except Exception as e:
            logger.error(f"Failed to start image analysis task: {e}")
            raise
    
    def _process_image_analysis_task(self, task_id: str, product_id: str, user_id: str):
        """Process the image analysis task in the background thread"""
        thread_name = threading.current_thread().name
        logger.info(f"[{thread_name}] Starting image analysis task {task_id} for product_id {product_id}")
        
        try:
            # Update task status to running
            update_task_progress(task_id, 0, "Fetching product images", 10.0)
            
            # Get product images from database
            product_data = self._get_product_by_id(product_id)
            if not product_data:
                logger.error(f"[{thread_name}] Product not found for product_id: {product_id}")
                fail_task(task_id, f"Product not found for product_id: {product_id}")
                return
            
            images = product_data.get('images', {})
            if not images:
                logger.error(f"[{thread_name}] No images found for product with product_id: {product_id}")
                fail_task(task_id, "No images found for this product")
                return
            
            # Find unanalyzed images
            unanalyzed_images = self._get_unanalyzed_images(images)
            if not unanalyzed_images:
                # All images already analyzed - complete task with special message
                logger.info(f"[{thread_name}] All images already analyzed for product_id {product_id}")
                complete_task(task_id, {
                    "message": "All images already analyzed",
                    "total_images": len(images),
                    "analyzed_images": len(images),
                    "failed_images": 0
                })
                return
            
            total_images = len(unanalyzed_images)
            logger.info(f"[{thread_name}] Found {total_images} unanalyzed images for product_id {product_id}")
            update_task_progress(task_id, 1, f"Found {total_images} images to analyze", 20.0)
            
            # Analyze images with concurrent processing
            results = self._analyze_images_concurrently(task_id, unanalyzed_images, total_images)
            
            # Update product with analysis results
            self._update_product_images(product_id, results)
            
            # Calculate final statistics
            analyzed_count = len([r for r in results if not r.get('error')])
            failed_count = len([r for r in results if r.get('error')])
            
            logger.info(f"[{thread_name}] Image analysis completed for task {task_id}: {analyzed_count} analyzed, {failed_count} failed")
            
            # Complete the task (without analyzedData in response)
            complete_task(task_id, {
                "total_images": total_images,
                "analyzed_images": analyzed_count,
                "failed_images": failed_count,
                "message": f"Image analysis completed. {analyzed_count} analyzed, {failed_count} failed."
            })
            
        except Exception as e:
            logger.error(f"[{thread_name}] Error in image analysis task {task_id}: {e}", exc_info=True)
            fail_task(task_id, str(e))
        finally:
            logger.info(f"[{thread_name}] Image analysis thread {task_id} finished")
    
    def _get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get product data from database using product_id"""
        try:
            if not supabase_manager.is_connected():
                raise Exception("Supabase connection not available")
            
            result = supabase_manager.client.table('products').select(
                'id, title, images'
            ).eq('id', product_id).execute()
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Failed to get product by product_id {product_id}: {e}")
            return None
    
    def _get_unanalyzed_images(self, images: Dict[str, Any]) -> List[str]:
        """Get list of image URLs that haven't been analyzed yet"""
        unanalyzed = []
        for image_url, analysis_data in images.items():
            # Check if image has been analyzed (has analysis data)
            if not analysis_data or (isinstance(analysis_data, dict) and not analysis_data):
                unanalyzed.append(image_url)
        return unanalyzed
    
    def _analyze_images_concurrently(
        self, 
        task_id: str, 
        image_urls: List[str], 
        total_images: int
    ) -> List[Dict[str, Any]]:
        """Analyze multiple images concurrently with progress tracking"""
        results = []
        analyzed_count = 0
        
        # Process images in batches of max_concurrent_analyses
        for i in range(0, len(image_urls), self.max_concurrent_analyses):
            batch = image_urls[i:i + self.max_concurrent_analyses]
            
            # Analyze batch concurrently
            batch_results = self._analyze_image_batch(batch)
            results.extend(batch_results)
            
            # Update progress
            analyzed_count += len(batch)
            progress = 20.0 + (analyzed_count / total_images) * 70.0  # 20-90% range
            update_task_progress(
                task_id, 
                2, 
                f"Analyzed {analyzed_count}/{total_images} images", 
                progress
            )
        
        return results
    
    def _analyze_image_batch(self, image_urls: List[str]) -> List[Dict[str, Any]]:
        """Analyze a batch of images concurrently"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrent_analyses) as executor:
            # Submit all images for analysis
            future_to_url = {
                executor.submit(self._analyze_single_image, url): url 
                for url in image_urls
            }
            
            results = []
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to analyze image {url}: {e}")
                    results.append({
                        "image_url": url,
                        "description": "",
                        "details": None,
                        "error": str(e),
                        "analyzed_at": datetime.now().isoformat()
                    })
        
        return results
    
    def _analyze_single_image(self, image_url: str) -> Dict[str, Any]:
        """Analyze a single image using OpenAI Vision API with retry logic"""
        for attempt in range(self.max_retries):
            try:
                return self._call_openai_vision_api(image_url)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    # Last attempt failed
                    raise e
                
                logger.warning(f"Attempt {attempt + 1} failed for {image_url}: {e}")
                import time
                time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
        
        # Should never reach here
        raise Exception("All retry attempts failed")
    
    def _call_openai_vision_api(self, image_url: str) -> Dict[str, Any]:
        """Call OpenAI Vision API to analyze an image"""
        if not settings.OPENAI_API_KEY:
            raise Exception("OpenAI API key not configured")
        
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Function schema for structured image analysis
        image_analysis_function = {
            "name": "analyze_image",
            "description": "Analyze an image and extract structured information about its visual content, style, and potential use cases for video generation",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "A comprehensive description of what the image visually shows and represents"
                    },
                    "objects": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of main objects, items, or products visible in the image"
                    },
                    "colors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of prominent colors visible in the image"
                    },
                    "style": {
                        "type": "string",
                        "description": "The visual style of the image (e.g., modern, vintage, minimalist, luxury, etc.)"
                    },
                    "mood": {
                        "type": "string",
                        "description": "The emotional mood or atmosphere conveyed by the image"
                    },
                    "text": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Any text, logos, or branding visible in the image"
                    },
                    "productFeatures": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Visual features or characteristics of products shown in the image"
                    },
                    "videoScenarios": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Potential video scenarios that could be created based on this image"
                    },
                    "targetAudience": {
                        "type": "string",
                        "description": "The target audience that this image would appeal to"
                    },
                    "useCases": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Potential use cases or contexts where this type of image would be relevant"
                    }
                },
                "required": ["description"]
            }
        }
        
        default_prompt = """Analyze this image and describe what it visually shows and represents. Focus on the visual content and elements that can be used for video generation:

1. VISUAL CONTENT DESCRIPTION:
   - What objects, items, or products are visible in the image
   - The overall scene, setting, or environment shown
   - Any people, actions, or activities depicted
   - Visual composition and layout of elements

2. VISUAL ELEMENTS:
   - Colors, lighting, and visual style
   - Background and foreground elements
   - Any props, accessories, or contextual items
   - Text, logos, or branding visible in the image

3. VISUAL MOOD & STYLE:
   - The overall aesthetic and visual tone
   - Emotional atmosphere conveyed by the image
   - Visual style (modern, vintage, minimalist, etc.)
   - Color scheme and visual appeal

4. VISUAL DETAILS:
   - Specific visual features or characteristics
   - Quality and clarity of visual elements
   - Any notable visual patterns or textures
   - Elements that stand out or are emphasized

5. VISUAL CONTEXT:
   - What the image represents or suggests
   - Visual storytelling elements
   - Context clues about usage or purpose
   - Visual hierarchy and focal points

Provide a clear, descriptive analysis of what the image visually contains and represents. Focus on the visual elements that can inform video generation scenarios, without making assumptions about product details that would come from text descriptions."""
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert visual analyst specializing in image content analysis for video generation. Analyze images to extract detailed visual information that can be used to create video scenarios. Focus on describing what the image visually shows, represents, and contains. Provide clear, descriptive analysis of visual elements, composition, style, and context that can inform video generation without making assumptions about product details that would come from text descriptions."
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": default_prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url,
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                functions=[image_analysis_function],
                function_call={"name": "analyze_image"},
                max_tokens=800,
                temperature=0.3
            )
            
            function_call = response.choices[0].message.function_call
            content = response.choices[0].message.content
            
            if function_call and function_call.name == "analyze_image":
                try:
                    function_args = json.loads(function_call.arguments)
                    description = function_args.get("description") or content or 'No description generated'
                    
                    # Extract details from function call arguments
                    details = {}
                    
                    if function_args.get("objects"): details["objects"] = function_args["objects"]
                    if function_args.get("colors"): details["colors"] = function_args["colors"]
                    if function_args.get("style"): details["style"] = function_args["style"]
                    if function_args.get("mood"): details["mood"] = function_args["mood"]
                    if function_args.get("text"): details["text"] = function_args["text"]
                    if function_args.get("productFeatures"): details["productFeatures"] = function_args["productFeatures"]
                    if function_args.get("videoScenarios"): details["videoScenarios"] = function_args["videoScenarios"]
                    if function_args.get("targetAudience"): details["targetAudience"] = function_args["targetAudience"]
                    if function_args.get("useCases"): details["useCases"] = function_args["useCases"]
                    
                    return {
                        "image_url": image_url,
                        "description": description,
                        "details": details if details else None,
                        "error": None,
                        "analyzed_at": datetime.now().isoformat(),
                        "objects": function_args.get('objects'),
                        "colors": function_args.get('colors'),
                        "style": function_args.get('style'),
                        "mood": function_args.get('mood'),
                        "text": function_args.get('text'),
                        "productFeatures": function_args.get('productFeatures'),
                        "videoScenarios": function_args.get('videoScenarios'),
                        "targetAudience": function_args.get('targetAudience'),
                        "useCases": function_args.get('useCases')
                    }
                    
                except Exception as parse_error:
                    logger.error(f'Error parsing function call arguments for {image_url}: {parse_error}')
                    # Fallback to content if function call parsing fails
                    return {
                        "image_url": image_url,
                        "description": content or 'No description generated',
                        "details": None,
                        "error": None,
                        "analyzed_at": datetime.now().isoformat()
                    }
            else:
                # Fallback if no function call is made
                description = content or 'No description generated'
                details = self._extract_details_from_description(description)
                
                return {
                    "image_url": image_url,
                    "description": description,
                    "details": details,
                    "error": None,
                    "analyzed_at": datetime.now().isoformat(),
                    "objects": details.get('objects') if details else None,
                    "colors": details.get('colors') if details else None,
                    "style": details.get('style') if details else None,
                    "mood": details.get('mood') if details else None,
                    "text": details.get('text') if details else None,
                    "productFeatures": details.get('productFeatures') if details else None,
                    "videoScenarios": details.get('videoScenarios') if details else None,
                    "targetAudience": details.get('targetAudience') if details else None,
                    "useCases": details.get('useCases') if details else None
                }
                
        except Exception as error:
            logger.error(f'OpenAI API error for {image_url}: {error}')
            
            if isinstance(error, Exception):
                # Handle specific OpenAI errors
                if 'content_filter' in str(error):
                    raise Exception('Image analysis was blocked by content filters')
                if 'invalid_image' in str(error):
                    raise Exception('Invalid or unsupported image format')
                if 'rate_limit' in str(error):
                    raise Exception('Rate limit exceeded. Please try again later.')
            
            raise Exception('Failed to analyze image. Please try again.')
    
    def _extract_details_from_description(self, description: str) -> Optional[Dict[str, Any]]:
        """Helper function to extract structured details from the description (fallback)"""
        details = {}
        
        # Extract objects (simple heuristic - look for common object words)
        object_keywords = ['person', 'people', 'car', 'building', 'tree', 'chair', 'table', 'phone', 'laptop', 'book', 'food', 'animal', 'dog', 'cat', 'bird', 'product', 'item', 'device', 'tool', 'accessory']
        objects = [keyword for keyword in object_keywords if keyword in description.lower()]
        if objects:
            details["objects"] = objects
        
        # Extract colors
        color_keywords = ['red', 'blue', 'green', 'yellow', 'black', 'white', 'gray', 'grey', 'brown', 'purple', 'pink', 'orange', 'gold', 'silver', 'rose', 'navy', 'teal']
        colors = [color for color in color_keywords if color in description.lower()]
        if colors:
            details["colors"] = colors
        
        # Extract style/mood keywords
        style_keywords = ['modern', 'vintage', 'minimalist', 'bright', 'dark', 'warm', 'cool', 'professional', 'casual', 'elegant', 'rustic', 'luxury', 'premium', 'sporty', 'classic', 'trendy']
        styles = [style for style in style_keywords if style in description.lower()]
        if styles:
            details["style"] = styles[0]  # Take the first matching style
        
        # Extract mood keywords
        mood_keywords = ['happy', 'sad', 'serene', 'energetic', 'peaceful', 'dramatic', 'mysterious', 'cheerful', 'melancholy', 'exciting', 'relaxing', 'confident', 'playful', 'sophisticated']
        moods = [mood for mood in mood_keywords if mood in description.lower()]
        if moods:
            details["mood"] = moods[0]  # Take the first matching mood
        
        # Extract product features
        feature_keywords = ['wireless', 'portable', 'waterproof', 'durable', 'lightweight', 'compact', 'smart', 'automatic', 'digital', 'bluetooth', 'usb', 'battery', 'rechargeable', 'adjustable', 'foldable']
        features = [feature for feature in feature_keywords if feature in description.lower()]
        if features:
            details["productFeatures"] = features
        
        # Extract video scenario suggestions
        scenario_keywords = ['demonstration', 'comparison', 'before after', 'lifestyle', 'unboxing', 'review', 'tutorial', 'showcase', 'testimonial', 'transformation']
        scenarios = [scenario for scenario in scenario_keywords if scenario in description.lower()]
        if scenarios:
            details["videoScenarios"] = scenarios
        
        # Extract target audience hints
        audience_keywords = ['professional', 'student', 'parent', 'fitness', 'traveler', 'gamer', 'chef', 'artist', 'business', 'teen', 'adult', 'senior']
        audiences = [audience for audience in audience_keywords if audience in description.lower()]
        if audiences:
            details["targetAudience"] = audiences[0]  # Take the first matching audience
        
        # Extract use cases
        use_case_keywords = ['home', 'office', 'gym', 'travel', 'kitchen', 'bathroom', 'bedroom', 'outdoor', 'indoor', 'work', 'leisure', 'cooking', 'cleaning', 'entertainment']
        use_cases = [use_case for use_case in use_case_keywords if use_case in description.lower()]
        if use_cases:
            details["useCases"] = use_cases
        
        return details if details else None
    
    def _update_product_images(self, product_id: str, analysis_results: List[Dict[str, Any]]):
        """Update the product's images field with analysis results"""
        try:
            if not supabase_manager.is_connected():
                raise Exception("Supabase connection not available")
            
            # Get current product data
            product_data = self._get_product_by_id(product_id)
            if not product_data:
                raise Exception("Product not found")
            
            current_images = product_data.get('images', {})
            
            # Update with new analysis results
            for result in analysis_results:
                image_url = result['image_url']
                if not result.get('error'):
                    # Successful analysis
                    current_images[image_url] = {
                        "description": result['description'],
                        "details": result.get('details'),
                        "analyzed_at": result['analyzed_at']
                    }
                else:
                    # Failed analysis - mark as failed
                    current_images[image_url] = {
                        "error": result['error'],
                        "analyzed_at": result['analyzed_at']
                    }
            
            # Update the product in database
            supabase_manager.client.table('products').update({
                "images": current_images
            }).eq('id', product_id).execute()
            
            logger.info(f"Updated product images for product_id {product_id}")
            
        except Exception as e:
            logger.error(f"Failed to update product images for product_id {product_id}: {e}")
            raise


# Global instance
image_analysis_service = ImageAnalysisService()
