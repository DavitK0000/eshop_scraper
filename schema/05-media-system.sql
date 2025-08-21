-- Auto-Promo AI Media System Schema
-- Audio information and publishing information management

-- Audio information for videos
CREATE TABLE IF NOT EXISTS public.audio_info (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    short_id UUID REFERENCES public.shorts(id) ON DELETE CASCADE NOT NULL,
    audio_url TEXT,
    duration INTEGER, -- in seconds
    format TEXT,
    bitrate INTEGER,
    sample_rate INTEGER,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Publishing information for social media platforms
CREATE TABLE IF NOT EXISTS public.publishing_info (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    short_id UUID REFERENCES public.shorts(id) ON DELETE CASCADE NOT NULL,
    platform TEXT NOT NULL, -- tiktok, youtube, instagram, etc.
    platform_post_id TEXT,
    title TEXT,
    description TEXT,
    hashtags TEXT[],
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'uploading', 'published', 'failed')),
    published_at TIMESTAMP WITH TIME ZONE,
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for media system tables
CREATE INDEX IF NOT EXISTS idx_audio_info_user_id ON public.audio_info(user_id);
CREATE INDEX IF NOT EXISTS idx_audio_info_short_id ON public.audio_info(short_id);

CREATE INDEX IF NOT EXISTS idx_publishing_info_user_id ON public.publishing_info(user_id);
CREATE INDEX IF NOT EXISTS idx_publishing_info_short_id ON public.publishing_info(short_id);
CREATE INDEX IF NOT EXISTS idx_publishing_info_platform ON public.publishing_info(platform);

-- Triggers for updated_at columns
CREATE TRIGGER update_audio_info_updated_at 
    BEFORE UPDATE ON public.audio_info 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_publishing_info_updated_at 
    BEFORE UPDATE ON public.publishing_info 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column(); 