-- Migration: Remove RunwayML references and upscaling functionality
-- Date: 2024-12-19
-- Description: 
-- 1. Remove upscale_video credit action
-- 2. Update generate_image description to reflect Vertex AI and Flux API
-- 3. Remove any upscale_video related plan configurations

-- Update the generate_image action description
UPDATE public.credit_actions 
SET 
    description = 'Generate AI images for video scenes using Vertex AI and Flux API',
    updated_at = NOW()
WHERE action_name = 'generate_image';

-- Remove upscale_video credit action
DELETE FROM public.credit_actions 
WHERE action_name = 'upscale_video';

-- Remove upscale_video plan configurations
DELETE FROM public.plan_credit_configs 
WHERE action_id IN (
    SELECT id FROM public.credit_actions WHERE action_name = 'upscale_video'
);

-- Remove any upscale_video related user credits (if they exist)
DELETE FROM public.user_credits 
WHERE action_id IN (
    SELECT id FROM public.credit_actions WHERE action_name = 'upscale_video'
);

-- Remove any upscale_video related credit transactions (if they exist)
DELETE FROM public.credit_transactions 
WHERE action_id IN (
    SELECT id FROM public.credit_actions WHERE action_name = 'upscale_video'
);

-- Clean up any orphaned records (safety measure)
-- This will remove any plan_credit_configs that reference non-existent actions
DELETE FROM public.plan_credit_configs 
WHERE action_id NOT IN (
    SELECT id FROM public.credit_actions
);

-- Clean up any orphaned user_credits
DELETE FROM public.user_credits 
WHERE action_id NOT IN (
    SELECT id FROM public.credit_actions
);

-- Clean up any orphaned credit_transactions
DELETE FROM public.credit_transactions 
WHERE action_id NOT IN (
    SELECT id FROM public.credit_actions
);

-- Add comment to track this migration
COMMENT ON TABLE public.credit_actions IS 'Credit actions table - Updated 2024-12-19: Removed upscale_video action and updated generate_image description for Vertex AI/Flux API';
