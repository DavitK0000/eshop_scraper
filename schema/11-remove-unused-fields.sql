-- Migration to remove unused fields from video generation tables
-- This migration removes fields that are no longer needed in the scenario generation system

-- Remove fields from video_scenes table
ALTER TABLE IF EXISTS public.video_scenes 
    DROP COLUMN IF EXISTS visual_elements,
    DROP COLUMN IF EXISTS camera_movement,
    DROP COLUMN IF EXISTS transition;

-- Remove fields from video_scenarios table
ALTER TABLE IF EXISTS public.video_scenarios 
    DROP COLUMN IF EXISTS target_audience,
    DROP COLUMN IF EXISTS video_description;

-- Add comment to document the changes
COMMENT ON TABLE public.video_scenes IS 'Video scenes table - removed visual_elements, camera_movement, and transition fields as they are no longer needed';
COMMENT ON TABLE public.video_scenarios IS 'Video scenarios table - removed target_audience and video_description fields as they are no longer needed';
