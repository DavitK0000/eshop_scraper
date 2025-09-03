-- Drop the category_environments table
DROP TABLE IF EXISTS public.category_environments;

-- Add environments array to categories table
ALTER TABLE public.categories
ADD COLUMN environments TEXT[] DEFAULT '{}';

-- Add index for environments array
CREATE INDEX IF NOT EXISTS idx_categories_environments ON public.categories USING GIN (environments);

-- Add comment
COMMENT ON COLUMN public.categories.environments IS 'Array of environment names (e.g., Indoor, Outdoor, City, Mountain)';
