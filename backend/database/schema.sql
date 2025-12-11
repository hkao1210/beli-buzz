-- =============================================================================
-- Belly-Buzz Database Schema for Supabase
-- =============================================================================
-- Run this in the Supabase SQL Editor to set up your database.
-- Requires pgvector extension.

-- Enable pgvector extension for semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- RESTAURANTS TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS restaurants (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    
    -- Core Identity
    name TEXT NOT NULL,
    slug TEXT UNIQUE,
    
    -- Location (from Google Places API)
    address TEXT NOT NULL DEFAULT '',
    neighborhood TEXT,
    city TEXT NOT NULL DEFAULT 'Toronto',
    latitude DOUBLE PRECISION NOT NULL DEFAULT 0,
    longitude DOUBLE PRECISION NOT NULL DEFAULT 0,
    
    -- Google Places Data
    google_place_id TEXT UNIQUE,
    google_maps_url TEXT,
    google_rating DOUBLE PRECISION,
    google_reviews_count INTEGER DEFAULT 0,
    
    -- Pricing
    price_tier INTEGER NOT NULL DEFAULT 2 CHECK (price_tier BETWEEN 1 AND 4),
    
    -- Photo
    photo_url TEXT,
    
    -- AI-Extracted Data
    cuisine_tags TEXT[] DEFAULT '{}',
    vibe TEXT,
    recommended_dishes TEXT[] DEFAULT '{}',
    
    -- Scores (calculated from social data)
    buzz_score DOUBLE PRECISION DEFAULT 0,
    sentiment_score DOUBLE PRECISION DEFAULT 0,
    viral_score DOUBLE PRECISION DEFAULT 0,
    pro_score DOUBLE PRECISION DEFAULT 0,
    
    -- Engagement
    total_mentions INTEGER DEFAULT 0,
    user_likes INTEGER DEFAULT 0,
    user_saves INTEGER DEFAULT 0,
    
    -- Metadata
    is_new BOOLEAN DEFAULT false,
    is_trending BOOLEAN DEFAULT false,
    hours JSONB,
    
    -- Source Tracking
    sources TEXT[] DEFAULT '{}',
    source_urls TEXT[] DEFAULT '{}',
    
    -- Vector Embedding (384 dimensions for all-MiniLM-L6-v2)
    embedding vector(384),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_scraped_at TIMESTAMPTZ
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_restaurants_city ON restaurants(city);
CREATE INDEX IF NOT EXISTS idx_restaurants_neighborhood ON restaurants(neighborhood);
CREATE INDEX IF NOT EXISTS idx_restaurants_price_tier ON restaurants(price_tier);
CREATE INDEX IF NOT EXISTS idx_restaurants_buzz_score ON restaurants(buzz_score DESC);
CREATE INDEX IF NOT EXISTS idx_restaurants_sentiment_score ON restaurants(sentiment_score DESC);
CREATE INDEX IF NOT EXISTS idx_restaurants_google_place_id ON restaurants(google_place_id);
CREATE INDEX IF NOT EXISTS idx_restaurants_cuisine_tags ON restaurants USING GIN(cuisine_tags);
CREATE INDEX IF NOT EXISTS idx_restaurants_slug ON restaurants(slug);

-- Vector similarity index for semantic search (IVFFlat for better performance)
CREATE INDEX IF NOT EXISTS idx_restaurants_embedding ON restaurants 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- =============================================================================
-- SOCIAL MENTIONS TABLE
-- =============================================================================
-- Stores individual mentions from Reddit, blogs, etc.
CREATE TABLE IF NOT EXISTS social_mentions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    
    -- Link to restaurant
    restaurant_id UUID REFERENCES restaurants(id) ON DELETE CASCADE,
    restaurant_name TEXT NOT NULL,  -- Store name in case restaurant not yet created
    
    -- Source Info
    source_type TEXT NOT NULL,  -- 'reddit', 'eater', 'blogto', 'toronto_life', etc.
    source_url TEXT NOT NULL UNIQUE,
    source_id TEXT,  -- Reddit post ID, etc.
    
    -- Content
    title TEXT,
    raw_text TEXT NOT NULL,
    
    -- Reddit-specific
    subreddit TEXT,
    reddit_score INTEGER DEFAULT 0,
    reddit_num_comments INTEGER DEFAULT 0,
    author TEXT,
    
    -- AI-Extracted
    sentiment_score DOUBLE PRECISION,
    sentiment_label TEXT,  -- 'positive', 'negative', 'neutral'
    aspects JSONB,  -- {"food": 0.9, "service": 0.7, "ambiance": 0.8}
    dishes_mentioned TEXT[] DEFAULT '{}',
    price_mentioned TEXT,
    vibe_extracted TEXT,
    
    -- Engagement metrics (at time of scrape)
    engagement_score DOUBLE PRECISION DEFAULT 0,
    
    -- Timestamps
    posted_at TIMESTAMPTZ,
    scraped_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mentions_restaurant_id ON social_mentions(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_mentions_source_type ON social_mentions(source_type);
CREATE INDEX IF NOT EXISTS idx_mentions_subreddit ON social_mentions(subreddit);
CREATE INDEX IF NOT EXISTS idx_mentions_posted_at ON social_mentions(posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_mentions_sentiment_score ON social_mentions(sentiment_score DESC);

-- =============================================================================
-- TRENDING SEARCHES TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS trending_searches (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    query TEXT NOT NULL,
    search_count INTEGER DEFAULT 1,
    city TEXT DEFAULT 'Toronto',
    last_searched_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trending_city ON trending_searches(city);
CREATE INDEX IF NOT EXISTS idx_trending_count ON trending_searches(search_count DESC);

-- =============================================================================
-- FUNCTIONS
-- =============================================================================

-- Function: Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for restaurants
DROP TRIGGER IF EXISTS update_restaurants_updated_at ON restaurants;
CREATE TRIGGER update_restaurants_updated_at
    BEFORE UPDATE ON restaurants
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- VECTOR SEARCH FUNCTION
-- =============================================================================
-- Search restaurants by semantic similarity
CREATE OR REPLACE FUNCTION search_restaurants(
    query_embedding vector(384),
    match_count INT DEFAULT 20,
    price_min INT DEFAULT NULL,
    price_max INT DEFAULT NULL,
    filter_city TEXT DEFAULT 'Toronto',
    filter_neighborhood TEXT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    name TEXT,
    slug TEXT,
    address TEXT,
    neighborhood TEXT,
    city TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    google_place_id TEXT,
    google_maps_url TEXT,
    price_tier INTEGER,
    rating DOUBLE PRECISION,
    photo_url TEXT,
    cuisine_tags TEXT[],
    vibe TEXT,
    recommended_dishes TEXT[],
    buzz_score DOUBLE PRECISION,
    sentiment_score DOUBLE PRECISION,
    viral_score DOUBLE PRECISION,
    total_mentions INTEGER,
    sources TEXT[],
    similarity DOUBLE PRECISION
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        r.id,
        r.name,
        r.slug,
        r.address,
        r.neighborhood,
        r.city,
        r.latitude,
        r.longitude,
        r.google_place_id,
        r.google_maps_url,
        r.price_tier,
        r.google_rating as rating,
        r.photo_url,
        r.cuisine_tags,
        r.vibe,
        r.recommended_dishes,
        r.buzz_score,
        r.sentiment_score,
        r.viral_score,
        r.total_mentions,
        r.sources,
        1 - (r.embedding <=> query_embedding) as similarity
    FROM restaurants r
    WHERE 
        r.embedding IS NOT NULL
        AND (filter_city IS NULL OR r.city = filter_city)
        AND (filter_neighborhood IS NULL OR r.neighborhood = filter_neighborhood)
        AND (price_min IS NULL OR r.price_tier >= price_min)
        AND (price_max IS NULL OR r.price_tier <= price_max)
    ORDER BY r.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- =============================================================================
-- HELPER FUNCTION: Get Trending Restaurants
-- =============================================================================
CREATE OR REPLACE FUNCTION get_trending_restaurants(
    filter_city TEXT DEFAULT 'Toronto',
    match_count INT DEFAULT 20
)
RETURNS TABLE (
    id UUID,
    name TEXT,
    slug TEXT,
    address TEXT,
    neighborhood TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    price_tier INTEGER,
    rating DOUBLE PRECISION,
    cuisine_tags TEXT[],
    vibe TEXT,
    recommended_dishes TEXT[],
    buzz_score DOUBLE PRECISION,
    sentiment_score DOUBLE PRECISION,
    total_mentions INTEGER,
    sources TEXT[],
    photo_url TEXT,
    google_maps_url TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        r.id,
        r.name,
        r.slug,
        r.address,
        r.neighborhood,
        r.latitude,
        r.longitude,
        r.price_tier,
        r.google_rating as rating,
        r.cuisine_tags,
        r.vibe,
        r.recommended_dishes,
        r.buzz_score,
        r.sentiment_score,
        r.total_mentions,
        r.sources,
        r.photo_url,
        r.google_maps_url
    FROM restaurants r
    WHERE r.city = filter_city
    ORDER BY r.buzz_score DESC, r.total_mentions DESC
    LIMIT match_count;
END;
$$;

-- =============================================================================
-- ROW LEVEL SECURITY (Optional, enable if needed)
-- =============================================================================
-- ALTER TABLE restaurants ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE social_mentions ENABLE ROW LEVEL SECURITY;

-- Allow public read access
-- CREATE POLICY "Public read access" ON restaurants FOR SELECT USING (true);
-- CREATE POLICY "Public read access" ON social_mentions FOR SELECT USING (true);

