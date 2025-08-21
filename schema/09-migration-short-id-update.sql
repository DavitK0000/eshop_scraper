-- Migration script to update database schema for short_id relationships
-- This script should be run after the main schema to update existing databases

-- Step 1: Add short_id column to products table
ALTER TABLE IF EXISTS public.products 
ADD COLUMN IF NOT EXISTS short_id UUID REFERENCES public.shorts(id) ON DELETE CASCADE;

-- Step 2: Remove product_id column from shorts table (if it exists)
ALTER TABLE IF EXISTS public.shorts 
DROP COLUMN IF EXISTS product_id;

-- Step 3: Create index on short_id in products table
CREATE INDEX IF NOT EXISTS idx_products_short_id ON public.products(short_id);

-- Step 4: Drop old index on product_id in shorts table (if it exists)
DROP INDEX IF EXISTS idx_shorts_product_id;

-- Step 5: Add comment to document the new relationship
COMMENT ON COLUMN public.products.short_id IS 'Reference to the short this product belongs to. When short is deleted, related products are also deleted.';
