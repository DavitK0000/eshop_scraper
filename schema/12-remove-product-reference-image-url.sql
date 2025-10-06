-- Migration to remove product_reference_image_url column from video_scenes table
-- This migration removes the product_reference_image_url field and related index

-- Drop the index first
DROP INDEX IF EXISTS idx_video_scenes_product_reference_image_url;

-- Remove the column
ALTER TABLE public.video_scenes DROP COLUMN IF EXISTS product_reference_image_url;

-- Add comment to document the change
COMMENT ON TABLE public.video_scenes IS 'Video scenes table - product_reference_image_url column removed in migration 12';
