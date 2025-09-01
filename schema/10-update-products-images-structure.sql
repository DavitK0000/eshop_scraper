-- Migration 10: Update Products Table Images Structure
-- Changes the images column from text[] (array of URLs) to JSONB (object with image URLs as keys and analysis data as values)
-- Date: 2024

-- Step 1: Change the images column type from text[] to JSONB
-- First, add a temporary JSONB column
ALTER TABLE public.products ADD COLUMN images_new JSONB DEFAULT '{}'::jsonb;

-- Step 1b: Convert existing array data to JSONB object format
UPDATE public.products 
SET images_new = (
    SELECT jsonb_object_agg(url, '{}'::jsonb)
    FROM unnest(images) AS url
)
WHERE images IS NOT NULL AND array_length(images, 1) > 0;

-- Step 1c: Drop the old column and rename the new one
ALTER TABLE public.products DROP COLUMN images;
ALTER TABLE public.products RENAME COLUMN images_new TO images;

-- Step 2: Set the default value to empty object
ALTER TABLE public.products 
ALTER COLUMN images SET DEFAULT '{}'::jsonb;

-- Step 3: Update the comment on the images column to reflect the new structure
COMMENT ON COLUMN public.products.images IS 'Object where keys are image URLs and values are image analysis data (empty object {} if no analysis)';

-- Step 4: Create a GIN index on the images column for better JSON query performance
-- This will help with queries that search within the image analysis data
CREATE INDEX IF NOT EXISTS idx_products_images_gin ON public.products USING GIN (images);

-- Migration completed successfully
-- The images column has been converted from text[] to JSONB with object structure:
-- {
--   "https://example.com/image1.jpg": {
--     "dominant_colors": ["#FF0000", "#00FF00"],
--     "objects_detected": ["product", "background"],
--     "confidence_score": 0.95,
--     "analysis_timestamp": "2024-01-01T00:00:00Z"
--   },
--   "https://example.com/image2.jpg": {},
--   "https://example.com/image3.jpg": {
--     "dominant_colors": ["#0000FF"],
--     "objects_detected": ["product"]
--   }
-- }
