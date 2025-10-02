-- Migration 10: Add new resolution values to video_scenarios table
-- Add support for 1920:1080, 1080:1920, and 1440:1440 resolutions

-- Drop the existing check constraint
ALTER TABLE public.video_scenarios DROP CONSTRAINT IF EXISTS video_scenarios_resolution_check;

-- Add the new check constraint with additional resolution values
ALTER TABLE public.video_scenarios ADD CONSTRAINT video_scenarios_resolution_check CHECK (
    resolution IN (
        '1280:720',   -- 16:9 landscape
        '720:1280',   -- 9:16 portrait  
        '1104:832',   -- 4:3 landscape
        '832:1104',   -- 3:4 portrait
        '960:960',    -- 1:1 square
        '1584:672',   -- 21:9 ultra-wide
        '1280:768',   -- 16:9 landscape HD+
        '768:1280',   -- 9:16 portrait HD
        '1920:1080',  -- Full HD landscape
        '1080:1920',  -- Full HD portrait
        '1440:1440'   -- Square HD
    )
);

-- Update the comment to reflect the new resolution options
COMMENT ON COLUMN public.video_scenarios.resolution IS 'Video resolution for content generation. Supported: 1280:720, 720:1280, 1104:832, 832:1104, 960:960, 1584:672, 1280:768, 768:1280, 1920:1080, 1080:1920, 1440:1440';
