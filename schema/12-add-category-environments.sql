-- Add environment types for categories
CREATE TABLE IF NOT EXISTS public.category_environments (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    category_id UUID REFERENCES public.categories(id) ON DELETE CASCADE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add unique constraint to prevent duplicate environment names per category
CREATE UNIQUE INDEX IF NOT EXISTS idx_category_environments_unique_name 
ON public.category_environments(category_id, name) 
WHERE is_active = true;

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_category_environments_category_id ON public.category_environments(category_id);
CREATE INDEX IF NOT EXISTS idx_category_environments_is_active ON public.category_environments(is_active);
CREATE INDEX IF NOT EXISTS idx_category_environments_sort_order ON public.category_environments(sort_order);

-- Add trigger for updated_at column
CREATE TRIGGER update_category_environments_updated_at 
    BEFORE UPDATE ON public.category_environments 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments
COMMENT ON TABLE public.category_environments IS 'Environment types for categories (e.g., indoor/outdoor for clothing, city/park/mountain for bikes)';
COMMENT ON COLUMN public.category_environments.category_id IS 'The category this environment belongs to';
COMMENT ON COLUMN public.category_environments.name IS 'Name of the environment (e.g., Indoor, Outdoor, City, Mountain)';
COMMENT ON COLUMN public.category_environments.description IS 'Optional description of the environment';
COMMENT ON COLUMN public.category_environments.is_active IS 'Whether this environment is active and available for use';
COMMENT ON COLUMN public.category_environments.sort_order IS 'Order in which environments should be displayed';
