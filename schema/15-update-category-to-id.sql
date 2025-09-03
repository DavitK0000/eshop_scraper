-- Update products table to use category_id instead of category string
-- This migration changes the category field from TEXT to UUID with foreign key reference

-- First, add the new category_id column
ALTER TABLE IF EXISTS public.products 
    ADD COLUMN IF NOT EXISTS category_id UUID REFERENCES public.categories(id) ON DELETE SET NULL;

-- Create index for the new category_id column
CREATE INDEX IF NOT EXISTS idx_products_category_id ON public.products(category_id);

-- Add comment to document the new field
COMMENT ON COLUMN public.products.category_id IS 'Foreign key reference to the categories table';

-- Note: We keep the old category column for now to allow for data migration
-- The old category column will be removed in a future migration after data is migrated
-- COMMENT ON COLUMN public.products.category IS 'DEPRECATED: Use category_id instead. This column will be removed in a future migration.';
