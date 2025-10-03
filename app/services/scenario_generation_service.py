"""
Scenario Generation Service for creating AI-powered video scenarios.
Handles OpenAI API calls for scenario generation and Google Vertex AI for image generation.
"""

import threading
import time
import json
import logging
import os
import uuid
import openai
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from pathlib import Path
from app.models import (
    ScenarioGenerationRequest, ScenarioGenerationResponse, GeneratedScenario,
    Scene, AudioScript, DetectedDemographics, TaskStatus
)

from app.utils.vertex_utils import generate_image_with_recontext_and_upscale, vertex_manager
from app.utils.task_management import (
    create_task, start_task, update_task_progress,
    complete_task, fail_task, TaskType, TaskStatus as TMStatus
)
from app.utils.credit_utils import can_perform_action, deduct_credits
from app.utils.supabase_utils import supabase_manager
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class ScenarioGenerationService:
    """Service for generating AI-powered video scenarios"""

    def __init__(self):
        self.openai_client = None
        self._initialize_openai()

    def _initialize_openai(self):
        """Initialize OpenAI client"""
        try:
            if not settings.OPENAI_API_KEY:
                logger.warning("OpenAI API key not configured")
                return

            self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("OpenAI client initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            self.openai_client = None

    def start_scenario_generation_task(self, request: ScenarioGenerationRequest) -> Dict[str, Any]:
        """Start a scenario generation task"""
        try:
            if not self.openai_client:
                raise Exception("OpenAI client not initialized")

            task_id = create_task(
                TaskType.SCENARIO_GENERATION,
                user_id=request.user_id,
                product_id=request.product_id
            )

            if not task_id:
                raise Exception("Failed to create scenario generation task")

            start_task(task_id)

            # Start background processing in a separate thread with asyncio
            import asyncio

            def run_async_task():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(
                        self._process_scenario_generation_task(task_id, request))
                finally:
                    loop.close()

            thread = threading.Thread(
                target=run_async_task,
                daemon=True,
                name=f"scenario_generation_{task_id}"
            )
            thread.start()

            logger.info(
                f"Started scenario generation thread for task {task_id}")

            return {
                "task_id": task_id,
                "status": "pending",
                "message": "Scenario generation task started"
            }

        except Exception as e:
            logger.error(f"Failed to start scenario generation task: {e}")
            raise

    async def _process_scenario_generation_task(self, task_id: str, request: ScenarioGenerationRequest):
        """Process the scenario generation task in the background thread"""
        thread_name = threading.current_thread().name
        logger.info(
            f"[{thread_name}] Starting scenario generation task {task_id}")

        try:
            # Update task status to running
            update_task_progress(
                task_id, 0, "Starting scenario generation", 20.0)

            # Check if user has enough credits
            if not can_perform_action(request.user_id, "generate_scenario"):
                raise Exception("Insufficient credits for scenario generation")

            update_task_progress(task_id, 20, "Generating AI scenario", 60.0)

            # Step 1: Generate scenario using OpenAI
            scenario = await self._generate_scenario_with_openai(request)
            if not scenario:
                raise Exception("Failed to generate scenario with OpenAI")

            update_task_progress(
                task_id, 60, "Generating thumbnail image", 90.0)

            # Step 2: Generate thumbnail image using Vertex AI
            thumbnail_url = await self._generate_thumbnail_image(request, scenario)
            if not thumbnail_url:
                logger.warning(
                    "Failed to generate thumbnail image, continuing without it")

            # Set the thumbnail URL in the scenario object
            scenario.thumbnail_url = thumbnail_url

            update_task_progress(task_id, 90, "Finalizing scenario", 100.0)

            # Step 3: Complete the task with generated scenario and thumbnail
            complete_task(task_id, {
                "scenario": scenario.dict(),
                "thumbnail_url": thumbnail_url  # Pass thumbnail URL in response
            })

            logger.info(
                f"[{thread_name}] Scenario generation task {task_id} completed successfully")

        except Exception as e:
            logger.error(
                f"[{thread_name}] Scenario generation task {task_id} failed: {e}")
            fail_task(task_id, str(e))

    async def _get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Fetch product data from database"""
        try:
            if not supabase_manager.is_connected():
                supabase_manager.ensure_connection()

            result = supabase_manager.client.table(
                'products').select('*').eq('id', product_id).execute()

            if result.data and len(result.data) > 0:
                product = result.data[0]

                # Extract image analysis from the images JSONB field instead of querying non-existent table
                image_analysis = []
                images_data = product.get('images', {})
                if isinstance(images_data, dict):
                    for image_url, analysis_data in images_data.items():
                        if isinstance(analysis_data, dict):
                            image_analysis.append({
                                "imageUrl": image_url,
                                "description": analysis_data.get('description', ''),
                                "details": analysis_data.get('details', {})
                            })

                return {
                    "title": product.get('title', ''),
                    "description": product.get('description', ''),
                    "price": product.get('price', 0),
                    "currency": product.get('currency', 'USD'),
                    "specifications": product.get('specifications', {}),
                    "rating": product.get('rating'),
                    "review_count": product.get('review_count'),
                    "image_analysis": image_analysis
                }

            return None

        except Exception as e:
            logger.error(f"Failed to fetch product data: {e}")
            return None

    async def _generate_scenario_with_openai(self, request: ScenarioGenerationRequest) -> Optional[GeneratedScenario]:
        """Generate scenario using OpenAI API"""
        try:
            system_message = await self._build_system_message(request)
            user_message = await self._build_user_message(request)

            logger.info("Sending request to OpenAI...")
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                functions=[self._get_scenario_generation_function()],
                function_call={"name": "generate_single_scenario"}
            )

            logger.info("OpenAI response received")
            logger.info(f"Response choices: {len(response.choices)}")

            if not response.choices:
                raise Exception("No choices in OpenAI response")

            function_call = response.choices[0].message.function_call
            if not function_call:
                raise Exception("No function call in OpenAI response")

            try:
                result = json.loads(function_call.arguments)
            except json.JSONDecodeError as e:
                logger.error(
                    f"Failed to parse function call arguments as JSON: {e}")
                logger.error(f"Raw arguments: {function_call.arguments}")
                raise Exception(
                    f"Invalid JSON in function call arguments: {e}")

            generated_scenario = result.get('scenario')

            if not generated_scenario:
                raise Exception("No scenario generated")

            if not isinstance(generated_scenario, dict):
                logger.warning(
                    f"AI returned unexpected format: {type(generated_scenario)}. Attempting to create fallback scenario...")
                # Try to create a basic scenario from the response
                if isinstance(generated_scenario, str):
                    # If it's a string, try to parse it as JSON
                    try:
                        generated_scenario = json.loads(generated_scenario)
                    except json.JSONDecodeError:
                        logger.error("Failed to parse string response as JSON")
                        raise Exception(
                            f"AI returned string instead of structured scenario: {generated_scenario}")
                else:
                    raise Exception(
                        f"Expected scenario to be a dictionary, got {type(generated_scenario)}: {generated_scenario}")

            # Validate that we have the required fields
            required_fields = ['title', 'description', 'scenes',
                'audioScript', 'detectedDemographics', 'thumbnailPrompt']
            missing_fields = [
                field for field in required_fields if field not in generated_scenario]
            if missing_fields:
                logger.warning(
                    f"Missing required fields: {missing_fields}. Creating fallback values...")
                # Create fallback values for missing fields
                if 'title' not in generated_scenario:
                    generated_scenario['title'] = 'Generated Video Scenario'
                if 'description' not in generated_scenario:
                    generated_scenario['description'] = 'AI-generated video scenario'
                if 'scenes' not in generated_scenario:
                    generated_scenario['scenes'] = []
                if 'audioScript' not in generated_scenario:
                    generated_scenario['audioScript'] = {
                        'hook': '', 'main': '', 'cta': '', 'hashtags': []}
                if 'detectedDemographics' not in generated_scenario:
                    generated_scenario['detectedDemographics'] = {
                        'targetGender': 'unisex',
                        'ageGroup': 'all-ages',
                        'productType': 'general',
                        'demographicContext': 'gender-neutral characters/models throughout'
                    }
                if 'thumbnailPrompt' not in generated_scenario:
                    generated_scenario['thumbnailPrompt'] = 'Create an eye-catching thumbnail for this video content'

            return await self._transform_openai_response(generated_scenario, request)

        except Exception as e:
            logger.error(
                f"Failed to generate scenario with OpenAI: {e}", exc_info=True)
            return None

    async def _build_system_message(self, request: ScenarioGenerationRequest) -> str:
        """Build system message for OpenAI"""
        expected_scene_count = request.video_length // 8
        product_data = await self._get_product_by_id(request.product_id)
        available_images = product_data.get(
            'image_analysis', []) if product_data else []

        image_selection_instructions = ""
        if available_images:
            image_selection_instructions = f"""
IMAGE SELECTION REQUIREMENTS:
- You have {len(available_images)} product images available
- For each scene, analyze the scene content and choose the most appropriate product image
- Use selectedImageIndex (0-based) to specify which product image to use
- Consider:
  * Hook scenes: Use most attention-grabbing product image
  * Problem scenes: Use image that shows the problem or need
  * Solution scenes: Use image that best showcases the product
  * Demonstration scenes: Use image that shows product in use
  * Benefits scenes: Use image that highlights key features
  * CTA scenes: Use most compelling product image
- Ensure image selection enhances the narrative flow and visual consistency"""

        environment_context = f"- Environment: \"{request.environment}\"" if request.environment else ""

        return f"""You are an expert TikTok video director. Create a single engaging, viral-worthy scenario that drives conversions.

CRITICAL - FIXED PARAMETERS (DO NOT MODIFY):
- Style: "{request.style}"
- Mood: "{request.mood}"  
- Video Length: {request.video_length} seconds
- Target Language: "{request.target_language}" 
{environment_context if environment_context else ""}

DEMOGRAPHIC DETECTION REQUIREMENTS:
- You MUST analyze the product information and automatically detect the target demographics
- Return the detectedDemographics object with targetGender, ageGroup, productType, and demographicContext
- Use this analysis to maintain CONSISTENT character types throughout ALL scenes
- If product targets men (e.g., men's shoes), use ONLY male characters/models in ALL scenes
- If product targets women (e.g., women's makeup), use ONLY female characters/models in ALL scenes
- If product targets children, use ONLY child/young characters in ALL scenes
- If product targets seniors, use ONLY mature/elderly characters in ALL scenes
- NEVER mix different character demographics within the same scenario

{image_selection_instructions}

 REQUIREMENTS:
 1. Generate EXACTLY 1 scenario with {expected_scene_count} scenes, each exactly 8 seconds
 2. Each scene needs TWO prompts:
    - imagePrompt: Detailed, descriptive prompt for first frame following Google Vertex Image generation best practices
    - visualPrompt: Video prompt following Veo3 best practices with these required elements:
      * Subject: The object, person, animal, or scenery in the video
      * Context: The background or context where the subject is placed
      * Action: What the subject is doing (walking, running, turning head, etc.)
      * Style: Film style keywords (horror film, film noir, cartoon style render, etc.)
      * Camera motion: What the camera is doing (aerial view, eye-level, top-down shot, low-angle shot)
      * Composition: How the shot is framed (wide shot, close-up, extreme close-up)
      * Ambiance: Color and light contribution (blue tones, night, warm tones)
 3. PROMPT ENHANCEMENT REQUIREMENTS:
    - Include camera proximity/position descriptions (e.g., "close-up shot", "wide angle", "medium shot", "overhead view", "low angle", "eye level")
    - Specify lighting conditions (e.g., "soft natural lighting", "dramatic shadows", "studio lighting", "golden hour", "backlit", "side lighting")
    - Include camera settings and effects (e.g., "shallow depth of field", "motion blur", "soft focus", "sharp focus", "cinematic bokeh", "slow motion")
    - Wrap ALL text content that appears in images/videos with double quotes ("") or single quotes ('')
    - Example: "Close-up shot with soft natural lighting, shallow depth of field, featuring text overlay 'Amazing Product'"
 4. Generate a compelling thumbnailPrompt for the video thumbnail that:
    - Captures the essence of the video content and product
    - Is optimized for social media (eye-catching, high contrast)
    - Includes style and mood elements from the video
    - Targets the detected demographic audience
    - Follows Vertex AI image generation best practices
    - Includes camera positioning, lighting, and text wrapping requirements
 5. Content must be family-friendly, professional, and pass content moderation
 6. Maintain consistent characters, settings, and visual style throughout
 7. Base content on actual product capabilities - no unrealistic scenarios
 8. Generate content suitable for TikTok vertical format (9:16)
 9. Audio script timing: Hook (20-25%), Main (50-60%), CTA (15-20%) of total duration
 10. LANGUAGE REQUIREMENTS:
    - Generate ALL audio script content (hook, main, cta, hashtags) in target language: "{request.target_language}"
    - Generate ALL text content that appears in images/videos in target language: "{request.target_language}"
    - This includes any text overlays, captions, product names, descriptions, or visual text elements
    - Ensure all visual prompts specify text content in the target language
    - Make sure image prompts include text elements in the target language when relevant
    - Wrap all text content with quotes as specified in prompt enhancement requirements
 """
    
    async def _build_user_message(self, request: ScenarioGenerationRequest) -> str:
        """Build user message for OpenAI"""
        product_data = await self._get_product_by_id(request.product_id)
        available_images = product_data.get('image_analysis', []) if product_data else []
        
        image_details = ""
        if available_images:
            image_details = f"\nAVAILABLE PRODUCT IMAGES ({len(available_images)} total):\n"
            for i, img in enumerate(available_images):
                image_details += f"- Image {i}: {img.get('imageUrl', 'N/A')}\n"
                if img.get('description'):
                    image_details += f"  Description: {img.get('description', '')}\n"
                if img.get('details'):
                    details = img.get('details', {})
                    if details.get('objects'):
                        image_details += f"  Objects: {', '.join(details.get('objects', []))}\n"
                    if details.get('colors'):
                        image_details += f"  Colors: {', '.join(details.get('colors', []))}\n"
                    if details.get('style'):
                        image_details += f"  Style: {details.get('style', '')}\n"
                    if details.get('mood'):
                        image_details += f"  Mood: {details.get('mood', '')}\n"
                image_details += "\n"
        
        return f"""Here's the product information:
- Title: {product_data.get('title', 'N/A') if product_data else 'N/A'}
- Description: {product_data.get('description', 'N/A') if product_data else 'N/A'}
- Price: {product_data.get('price', 'N/A') if product_data else 'N/A'} {product_data.get('currency', 'USD') if product_data else 'USD'}
- Specifications: {product_data.get('specifications', {}) if product_data else {}}
- Rating: {product_data.get('rating', 'N/A') if product_data else 'N/A'}
- Review Count: {product_data.get('review_count', 'N/A') if product_data else 'N/A'}{image_details}

IMPORTANT: Generate content using EXACTLY these parameters:
- Style: "{request.style}"
- Mood: "{request.mood}"  
- Video Length: {request.video_length} seconds
- Target Language: "{request.target_language}"
- Environment: "{request.environment if request.environment else ""}"

CRITICAL DEMOGRAPHIC CONSISTENCY:
- Analyze the product information and available images to detect target demographics
- Maintain EXACTLY the same character type throughout ALL scenes
- If men's product → ONLY male characters in ALL scenes
- If women's product → ONLY female characters in ALL scenes
- If children's product → ONLY child characters in ALL scenes
- NEVER mix different character types within the same scenario

IMAGE SELECTION STRATEGY:
- Analyze each scene's purpose and content
- Choose the most appropriate product image (selectedImageIndex) for each scene
- Ensure the selected image enhances the scene's narrative and visual impact
- Consider the image's content, style, and mood when making selections

Ensure all content is family-friendly, professional, and passes content moderation checks."""
    
    def _get_scenario_generation_function(self) -> Dict[str, Any]:
        """Get OpenAI function definition for scenario generation"""
        return {
            "name": "generate_single_scenario",
            "description": "Generate a single TikTok video scenario with the specified style and mood.",
            "parameters": {
                "type": "object",
                "required": ["scenario"],
                "properties": {
                    "scenario": {
                        "type": "object",
                        "required": ["title", "description", "scenes", "audioScript", "detectedDemographics", "thumbnailPrompt"],
                        "properties": {
                            "scenarioId": {"type": "string"},
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "thumbnailPrompt": {"type": "string", "description": "Detailed prompt for generating an eye-catching thumbnail image that represents the video content"},
                            "detectedDemographics": {
                                "type": "object",
                                "required": ["targetGender", "ageGroup", "productType", "demographicContext"],
                                "properties": {
                                    "targetGender": {"type": "string"},
                                    "ageGroup": {"type": "string"},
                                    "productType": {"type": "string"},
                                    "demographicContext": {"type": "string"}
                                }
                            },
                            "scenes": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["sceneId", "description", "duration", "imagePrompt", "visualPrompt", "imageReasoning", "selectedImageIndex"],
                                    "properties": {
                                        "sceneId": {"type": "string"},
                                        "description": {"type": "string"},
                                        "duration": {"type": "integer"},
                                        "imagePrompt": {"type": "string"},
                                        "visualPrompt": {"type": "string"},
                                        "imageReasoning": {"type": "string"},
                                        "selectedImageIndex": {"type": "integer", "description": "Index of the product image to use as reference (0-based, based on available product images)"}
                                    }
                                }
                            },
                            "audioScript": {
                                "type": "object",
                                "required": ["hook", "main", "cta", "hashtags"],
                                "properties": {
                                    "hook": {"type": "string"},
                                    "main": {"type": "string"},
                                    "cta": {"type": "string"},
                                    "hashtags": {"type": "array", "items": {"type": "string"}}
                                }
                            }
                        }
                    }
                }
            }
        }
    
    async def _transform_openai_response(self, openai_scenario: Dict[str, Any], request: ScenarioGenerationRequest) -> GeneratedScenario:
        """Transform OpenAI response to our GeneratedScenario model"""
        try:            
            # Ensure we have a dictionary
            if not isinstance(openai_scenario, dict):
                raise Exception(f"Expected openai_scenario to be a dictionary, got {type(openai_scenario)}: {openai_scenario}")
            
            # Get product data to access available images
            product_data = await self._get_product_by_id(request.product_id)
            available_images = product_data.get('image_analysis', []) if product_data else []
            logger.info(f"Found {len(available_images)} available images")
            
            scenes = []
            scenes_data = openai_scenario.get('scenes', [])
            if not isinstance(scenes_data, list):
                logger.warning(f"Expected scenes to be a list, got {type(scenes_data)}. Creating empty scenes list.")
                scenes_data = []
            
            for i, scene_data in enumerate(scenes_data):
                if not isinstance(scene_data, dict):
                    logger.warning(f"Scene {i} is not a dictionary: {type(scene_data)}. Skipping.")
                    continue
                                    
                # Use AI's selected image index to get the appropriate product image
                selected_image_index = scene_data.get('selectedImageIndex', 0)
                product_reference_image_url = ""
                
                if available_images and len(available_images) > 0:
                    # Ensure the index is within bounds
                    if 0 <= selected_image_index < len(available_images):
                        product_reference_image_url = available_images[selected_image_index].get('imageUrl', '')
                        logger.info(f"Selected image {selected_image_index}: {product_reference_image_url}")
                    else:
                        # Fallback to first image if index is out of bounds
                        product_reference_image_url = available_images[0].get('imageUrl', '')
                        logger.warning(f"AI selected image index {selected_image_index} is out of bounds, using first image")
                else:
                    logger.warning("No available images found for product")
                
                # Create scene with fallback values for missing fields
                scene = Scene(
                    scene_id=scene_data.get('sceneId', f"scene-{i}"),
                    scene_number=i+1,
                    description=scene_data.get('description', f'Scene {i+1}'),
                    duration=scene_data.get('duration', 8),
                    image_prompt=scene_data.get('imagePrompt', f'Generate image for scene {i+1}'),
                    visual_prompt=scene_data.get('visualPrompt', f'Video content for scene {i+1}'),
                    product_reference_image_url=product_reference_image_url,  # Use AI-selected image
                    image_reasoning=scene_data.get('imageReasoning', f'Selected image {selected_image_index} for scene {i+1}'),
                    generated_image_url=None  # Will be populated after image generation
                )
                scenes.append(scene)
                logger.info(f"Created scene: {scene.scene_number}")
            
            # If no scenes were created, create a default scene
            if not scenes:
                logger.warning("No valid scenes found, creating default scene")
                default_image_url = available_images[0].get('imageUrl', '') if available_images else ""
                default_scene = Scene(
                    scene_id="scene-default",
                    scene_number=1,
                    description="Default scene for video",
                    duration=8,
                    image_prompt="Generate a compelling product image",
                    visual_prompt="Show the product in an engaging way",
                    product_reference_image_url=default_image_url,
                    image_reasoning="Using first available product image",
                    generated_image_url=None
                )
                scenes.append(default_scene)
                logger.info("Created default scene")
            
            # Validate and create audio script with fallbacks
            audio_script_data = openai_scenario.get('audioScript', {})
            if not isinstance(audio_script_data, dict):
                logger.warning(f"Expected audioScript to be a dictionary, got {type(audio_script_data)}. Creating default.")
                audio_script_data = {}
            
            audio_script = AudioScript(
                hook=audio_script_data.get('hook', 'Welcome to our amazing product!'),
                main=audio_script_data.get('main', 'This product will solve all your problems.'),
                cta=audio_script_data.get('cta', 'Get yours today!'),
                hashtags=audio_script_data.get('hashtags', ['#product', '#amazing', '#musthave'])
            )
            
            # Validate and create demographics with fallbacks
            demographics_data = openai_scenario.get('detectedDemographics', {})
            if not isinstance(demographics_data, dict):
                logger.warning(f"Expected detectedDemographics to be a dictionary, got {type(demographics_data)}. Creating default.")
                demographics_data = {}
            
            demographics = DetectedDemographics(
                target_gender=demographics_data.get('targetGender', 'unisex'),
                age_group=demographics_data.get('ageGroup', 'all-ages'),
                product_type=demographics_data.get('productType', 'general'),
                demographic_context=demographics_data.get('demographicContext', 'gender-neutral characters/models throughout')
            )
            
            generated_scenario = GeneratedScenario(
                 title=openai_scenario.get('title', 'Generated Scenario'),
                 description=openai_scenario.get('description', ''),
                 detected_demographics=demographics,
                 scenes=scenes,
                 audio_script=audio_script,
                 total_duration=request.video_length,
                 style=request.style,
                 mood=request.mood,
                 resolution=request.resolution,
                 environment=request.environment,
                 thumbnail_prompt=openai_scenario.get('thumbnailPrompt', 'Create an eye-catching thumbnail for this video content'),
                 thumbnail_url=None  # Will be populated after thumbnail generation
             )
            
            logger.info(f"Successfully created GeneratedScenario with {len(scenes)} scenes")
            return generated_scenario
            
        except Exception as e:
            logger.error(f"Failed to transform OpenAI response: {e}", exc_info=True)
            raise

    async def _generate_thumbnail_image(self, request: ScenarioGenerationRequest, scenario: GeneratedScenario) -> Optional[str]:
        """Generate thumbnail image for the scenario using Google Vertex AI"""
        try:
            if not vertex_manager.is_available():
                logger.warning("Vertex AI not available, skipping thumbnail generation")
                return None
            
            # Use the AI-generated thumbnail prompt from the scenario
            thumbnail_prompt = scenario.thumbnail_prompt
            if not thumbnail_prompt:
                logger.warning("No thumbnail prompt found in scenario, using fallback")
                thumbnail_prompt = f"Create an eye-catching thumbnail for a video about {scenario.title}"
            
            # Enhance the prompt with style and mood
            enhanced_prompt = self._enhance_image_prompt(thumbnail_prompt, request.style, request.mood)
            
            # Use the first available product image as reference if available
            reference_image_url = None
            if scenario.scenes and len(scenario.scenes) > 0:
                first_scene = scenario.scenes[0]
                if first_scene.product_reference_image_url:
                    reference_image_url = first_scene.product_reference_image_url
                    logger.info(f"Using product reference image for thumbnail: {reference_image_url}")
            
            logger.info("Calling Vertex AI for thumbnail generation...")
            
            # Generate unique filename using UUID and save in temp directory
            thumbnail_uuid = uuid.uuid4()
            temp_dir = self._get_temp_dir()
            temp_thumbnail_path = str(temp_dir / f"temp_thumbnail_{thumbnail_uuid}.png")
            
            # Generate image using Vertex AI recontext and upscale
            result = generate_image_with_recontext_and_upscale(
                prompt=enhanced_prompt,
                product_image_url=reference_image_url or "",
                target_width=1920,
                target_height=1080,
                output_path=temp_thumbnail_path
            )
            
            logger.info(f"Vertex AI thumbnail result: {result}")
            
            if result and result.get('success'):
                if result.get('image_saved') and result.get('image_path'):
                    # Upload the generated image to Supabase and return the URL
                    try:
                        
                        # Read the generated image file using the correct path
                        image_path = result['image_path']
                        with open(image_path, 'rb') as f:
                            image_data = f.read()
                        
                        # Generate unique filename using the same UUID
                        filename = f"thumbnails/{thumbnail_uuid}.png"
                        
                        # Upload to Supabase storage
                        if supabase_manager.is_connected():
                            # Upload to generated-content bucket
                            try:
                                supabase_manager.client.storage.from_('generated-content').upload(
                                    path=filename,
                                    file=image_data,
                                    file_options={'content-type': 'image/png'}
                                )
                                
                                # Get public URL
                                public_url = supabase_manager.client.storage.from_('generated-content').get_public_url(filename)
                                
                                # Clean up local file
                                os.unlink(image_path)
                                
                                logger.info(f"Successfully generated and uploaded thumbnail: {public_url}")
                                return public_url
                                
                            except Exception as upload_error:
                                logger.error(f"Failed to upload thumbnail to Supabase: {upload_error}")
                                # Clean up local file
                                if os.path.exists(image_path):
                                    os.unlink(image_path)
                        else:
                            logger.error("Supabase not connected, cannot upload thumbnail")
                            # Clean up local file
                            if os.path.exists(image_path):
                                os.unlink(image_path)
                    except Exception as upload_error:
                        logger.error(f"Failed to process generated thumbnail: {upload_error}")
                        # Clean up local file
                        if os.path.exists(image_path):
                            os.unlink(image_path)
                else:
                    logger.warning("Thumbnail generation succeeded but image was not saved locally")
            else:
                error_msg = result.get('error', 'Unknown error') if result else 'No result returned'
                logger.warning(f"Thumbnail generation failed: {error_msg}")
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to generate thumbnail image: {e}", exc_info=True)
            return None
    
    
    def _enhance_image_prompt(self, base_prompt: str, style: str, mood: str) -> str:
        """Enhance image prompt with style and mood specific details"""
        style_enhancements = {
            'trendy-influencer-vlog': 'modern aesthetic, clean lines, soft natural lighting, warm tones',
            'cinematic-storytelling': 'dramatic lighting, deep shadows, cinematic color grading, professional film look',
            'product-showcase': 'studio lighting, clean background, professional product photography, sharp details',
            'lifestyle-content': 'natural lighting, warm atmosphere, comfortable setting, relatable environment',
            'educational-tutorial': 'clear composition, well-lit subject, professional setup, clean background',
            'behind-the-scenes': 'candid lighting, natural atmosphere, documentary style, authentic feel',
            'fashion-beauty': 'fashion photography aesthetic, professional makeup lighting, editorial style',
            'food-cooking': 'appetizing lighting, warm food photography, professional kitchen setup',
            'fitness-wellness': 'energetic lighting, motivational atmosphere, gym or outdoor setting',
            'tech-review': 'modern tech aesthetic, clean lines, professional setup, tech-focused lighting'
        }
        
        mood_enhancements = {
            'energetic': 'dynamic composition, vibrant colors, high energy lighting, bold contrast',
            'calm': 'soft lighting, muted colors, peaceful atmosphere, gentle composition',
            'professional': 'business-like setting, formal composition, corporate aesthetic, polished appearance',
            'fun': 'playful lighting, bright colors, cheerful atmosphere, engaging composition',
            'luxury': 'premium lighting, sophisticated composition, high-end aesthetic, elegant atmosphere',
            'casual': 'relaxed lighting, comfortable setting, informal composition, everyday atmosphere',
            'dramatic': 'theatrical lighting, strong shadows, intense atmosphere, powerful composition',
            'minimalist': 'clean lines, simple composition, uncluttered background, essential elements only',
            'vintage': 'retro aesthetic, classic composition, nostalgic lighting, period-appropriate styling',
            'futuristic': 'modern tech aesthetic, sleek lines, contemporary lighting, cutting-edge composition'
        }
        
        # Camera positioning and technical enhancements
        camera_enhancements = {
            'trendy-influencer-vlog': 'medium shot, eye level, shallow depth of field, cinematic bokeh',
            'cinematic-storytelling': 'wide angle establishing shot, low angle, deep focus, motion blur',
            'product-showcase': 'close-up shot, overhead view, sharp focus, studio lighting setup',
            'lifestyle-content': 'medium shot, natural eye level, soft focus, handheld camera feel',
            'educational-tutorial': 'medium shot, eye level, clear focus, stable composition',
            'behind-the-scenes': 'handheld camera, natural angles, documentary style, authentic framing',
            'fashion-beauty': 'close-up shot, professional angles, soft focus, editorial lighting',
            'food-cooking': 'overhead view, close-up details, warm lighting, appetizing composition',
            'fitness-wellness': 'dynamic angles, medium shot, energetic framing, motivational composition',
            'tech-review': 'medium shot, clean angles, sharp focus, modern composition'
        }
        
        # Lighting enhancements based on style and mood
        lighting_enhancements = {
            'energetic': 'bright natural lighting, high contrast, dynamic shadows',
            'calm': 'soft diffused lighting, gentle shadows, warm tones',
            'professional': 'even studio lighting, minimal shadows, clean illumination',
            'fun': 'bright colorful lighting, playful shadows, vibrant atmosphere',
            'luxury': 'premium lighting, sophisticated shadows, elegant illumination',
            'casual': 'natural ambient lighting, comfortable shadows, relaxed atmosphere',
            'dramatic': 'theatrical lighting, strong shadows, dramatic contrast',
            'minimalist': 'clean lighting, minimal shadows, simple illumination',
            'vintage': 'warm nostalgic lighting, classic shadows, period-appropriate atmosphere',
            'futuristic': 'modern LED lighting, sleek shadows, contemporary illumination'
        }
        
        style_enhancement = style_enhancements.get(style, style_enhancements['trendy-influencer-vlog'])
        mood_enhancement = mood_enhancements.get(mood, mood_enhancements['energetic'])
        camera_enhancement = camera_enhancements.get(style, camera_enhancements['trendy-influencer-vlog'])
        lighting_enhancement = lighting_enhancements.get(mood, lighting_enhancements['energetic'])
        
        base_enhancement = "professional lighting, sharp focus, high quality, perfect composition, studio lighting, commercial grade"
        
        return f"{base_prompt}. {base_enhancement}, {style_enhancement}, {mood_enhancement}, {camera_enhancement}, {lighting_enhancement}."
    
    def _get_temp_dir(self) -> Path:
        """Get or create the temp directory for temporary files."""
        project_root = Path(__file__).parent.parent.parent
        temp_dir = project_root / "temp"
        temp_dir.mkdir(exist_ok=True)
        return temp_dir

# Global service instance
scenario_generation_service = ScenarioGenerationService()
