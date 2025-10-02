import base64
from google.cloud import aiplatform
from google import genai
from google.genai import types
from google.genai.types import EditImageConfig, GenerateImagesConfig, RecontextImageConfig
from google.oauth2 import service_account
from google.genai.types import RecontextImageSource, ProductImage, Image, RawReferenceImage, MaskReferenceImage, MaskReferenceConfig
from PIL import Image as PILImage, ImageOps
from io import BytesIO
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

def create_centered_image_with_black_background(source_image:Image, target_width=1920, target_height=1080):
    """
    Create an image with the source image centered and black background.
    
    Args:
        source_image_path: Path to the source image
        target_width: Desired width of the output image
        target_height: Desired height of the output image
    
    Returns:
        PIL Image object
    """
    # Load the source image from bytes
    source_img = PILImage.open(BytesIO(source_image.image_bytes))
    
    # Create a black background image
    background = PILImage.new('RGB', (target_width, target_height), (0, 0, 0))
    
    # Calculate position to center the source image
    x = (target_width - source_img.width) // 2
    y = (target_height - source_img.height) // 2
    
    # Paste the source image onto the black background
    background.paste(source_img, (x, y))
    
    return background

def create_mask_image_with_black_area(source_image:Image, target_width=1920, target_height=1080):
    """
    Create an image with black area where the source image was positioned.
    
    Args:
        source_image_path: Path to the source image
        target_width: Desired width of the output image
        target_height: Desired height of the output image
    
    Returns:
        PIL Image object
    """
    # Load the source image to get its dimensions
    source_img = PILImage.open(BytesIO(source_image.image_bytes))
    
    # Create a white background image
    background = PILImage.new('RGB', (target_width, target_height), (255, 255, 255))
    
    # Calculate position where the source image would be centered
    x = (target_width - source_img.width) // 2
    y = (target_height - source_img.height) // 2
    
    # Create a black rectangle where the source image would be
    black_area = PILImage.new('RGB', (source_img.width, source_img.height), (0, 0, 0))
    
    # Paste the black area onto the white background
    background.paste(black_area, (x, y))
    
    return background

# Load service account
credentials = service_account.Credentials.from_service_account_file(
    "promo-nex-ai-vertex-ai-key.json"
)

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str("promo-nex-ai-vertex-ai-key.json")
os.environ['GOOGLE_CLOUD_PROJECT'] = 'promo-nex-ai-466218'
project_root = Path(__file__).parent
key_file_path = project_root / "promo-nex-ai-vertex-ai-key.json"

client = genai.Client(
    vertexai=True,
    http_options=types.HttpOptions(api_version='v1'),
    credentials=service_account.Credentials.from_service_account_file(
        str(key_file_path),
        scopes=['https://www.googleapis.com/auth/cloud-platform']
    )
)

source_image = Image(image_bytes=open("temp1.png", "rb").read(), mime_type="image/png")

# Generate the recontext image
print("Generating recontext image...")
image = client.models.recontext_image(
    model="imagen-product-recontext-preview-06-30",
    source=RecontextImageSource(
        prompt="A beautiful young woman wearing the jacket",
        product_images=[
            ProductImage(product_image=source_image)
        ],
    ),
    config=RecontextImageConfig()
)

recontext_image = image.generated_images[0].image

# # Set desired dimensions
TARGET_WIDTH = 1920
TARGET_HEIGHT = 1080

# Create the two required images
print("Creating centered image with black background...")
centered_image = create_centered_image_with_black_background(recontext_image, TARGET_WIDTH, TARGET_HEIGHT)
print(f"Created centered image: {centered_image.size}")

print("Creating mask image with black area...")
mask_image = create_mask_image_with_black_area(recontext_image, TARGET_WIDTH, TARGET_HEIGHT)
print(f"Created mask image: {mask_image.size}")

# Convert PIL images to bytes
centered_image_bytes = BytesIO()
centered_image.save(centered_image_bytes, format='PNG')
centered_image_bytes = centered_image_bytes.getvalue()

mask_image_bytes = BytesIO()
mask_image.save(mask_image_bytes, format='PNG')
mask_image_bytes = mask_image_bytes.getvalue()

raw_ref = RawReferenceImage(
    reference_image=Image(image_bytes=centered_image_bytes, mime_type="image/png"),
    reference_id=0,
)
mask_ref = MaskReferenceImage(
    reference_id=1,
    reference_image=Image(image_bytes=mask_image_bytes, mime_type="image/png"),
    config=MaskReferenceConfig(
        mask_mode="MASK_MODE_USER_PROVIDED",
        mask_dilation=0.03,
    ),
)

image = client.models.edit_image(
    model="imagen-3.0-capability-001",
    prompt="A beautiful young woman wearing the jacket",
    reference_images=[raw_ref, mask_ref],
    config=EditImageConfig(
        edit_mode="EDIT_MODE_OUTPAINT",
    ),
)

# Save the final upscaled image
image.generated_images[0].image.save("upscaled_output.png")
print("Saved upscaled_output.png")

# print("All images generated successfully!")
# print(f"Centered image: {TARGET_WIDTH}x{TARGET_HEIGHT} with source image centered on black background")
# print(f"Mask image: {TARGET_WIDTH}x{TARGET_HEIGHT} with black area where source image was")
# print(f"Recontext image: 1024x1024 (needs upscaling)")
