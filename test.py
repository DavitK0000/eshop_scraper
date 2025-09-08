from google.cloud import aiplatform
from google.oauth2 import service_account

# Load service account
credentials = service_account.Credentials.from_service_account_file(
    "promo-nex-ai-vertex-ai-key.json"
)

aiplatform.init(
    project="promo-nex-ai-466218",
    location="us-central1",
    credentials=credentials
)

model = aiplatform.ImageGenerationModel.from_pretrained("imagen-3.0")
    
result = model.predict(
    prompt="A beautiful sunset over a calm ocean",
    number_of_images=1,
    aspect_ratio="1:1",
)

# result.images[0] contains the generated image
print(result.images[0].uri)