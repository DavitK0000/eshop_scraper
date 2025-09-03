-- Add environment field to video_scenarios table
-- This field will store the environment context for video scenarios

-- Add the environment column to video_scenarios table
ALTER TABLE IF EXISTS public.video_scenarios 
    ADD COLUMN IF NOT EXISTS environment TEXT;

-- Add comment to document the new field
COMMENT ON COLUMN public.video_scenarios.environment IS 'Environment context for the video scenario (e.g., indoor, outdoor, studio, home, office, etc.)';

-- Create index for better query performance on environment field
CREATE INDEX IF NOT EXISTS idx_video_scenarios_environment ON public.video_scenarios(environment) WHERE environment IS NOT NULL;
