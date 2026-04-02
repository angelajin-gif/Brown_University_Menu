-- Enable required extensions on Supabase Postgres
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Core menu table
CREATE TABLE IF NOT EXISTS menu_items (
    id TEXT PRIMARY KEY,
    name_en TEXT NOT NULL,
    name_zh TEXT NOT NULL,
    description TEXT,
    calories INTEGER NOT NULL CHECK (calories >= 0),
    protein NUMERIC(8, 2) NOT NULL CHECK (protein >= 0),
    carbs NUMERIC(8, 2) NOT NULL CHECK (carbs >= 0),
    fat NUMERIC(8, 2) NOT NULL CHECK (fat >= 0),
    tags TEXT[] NOT NULL DEFAULT '{}',
    allergens TEXT[] NOT NULL DEFAULT '{}',
    hall_id TEXT NOT NULL CHECK (hall_id IN ('hall1', 'hall2')),
    meal_slot TEXT NOT NULL CHECK (meal_slot IN ('breakfast', 'lunch', 'dinner')),
    source TEXT NOT NULL DEFAULT 'local',
    external_location_id TEXT,
    external_location_name TEXT,
    station_id TEXT,
    station_name TEXT,
    service_date DATE,
    meal_name TEXT,
    menu_start TIMESTAMPTZ,
    menu_end TIMESTAMPTZ,
    item_type TEXT,
    nutrition_item_id TEXT,
    nutrition_source_url TEXT,
    nutrition_available BOOLEAN NOT NULL DEFAULT FALSE,
    nutrition_synced_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'local';
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS external_location_id TEXT;
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS external_location_name TEXT;
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS station_id TEXT;
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS station_name TEXT;
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS service_date DATE;
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS meal_name TEXT;
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS menu_start TIMESTAMPTZ;
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS menu_end TIMESTAMPTZ;
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS item_type TEXT;
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS nutrition_item_id TEXT;
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS nutrition_source_url TEXT;
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS nutrition_available BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS nutrition_synced_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_menu_items_meal_hall ON menu_items (meal_slot, hall_id);
CREATE INDEX IF NOT EXISTS idx_menu_items_service_date ON menu_items (service_date);
CREATE INDEX IF NOT EXISTS idx_menu_items_source_date ON menu_items (source, service_date);
CREATE INDEX IF NOT EXISTS idx_menu_items_tags_gin ON menu_items USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_menu_items_allergens_gin ON menu_items USING GIN (allergens);

-- Users and preference storage
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id TEXT PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    favorite_hall TEXT NOT NULL DEFAULT 'hall1' CHECK (favorite_hall IN ('hall1', 'hall2')),
    ai_auto_push BOOLEAN NOT NULL DEFAULT TRUE,
    pref_tags TEXT[] NOT NULL DEFAULT '{}',
    allergen_tags TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_notification_settings (
    user_id TEXT PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    allow_notifications BOOLEAN NOT NULL DEFAULT FALSE,
    breakfast_time TIME NOT NULL DEFAULT '07:30',
    lunch_time TIME NOT NULL DEFAULT '11:45',
    dinner_time TIME NOT NULL DEFAULT '17:30',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_favorites (
    user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    menu_item_id TEXT NOT NULL REFERENCES menu_items (id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, menu_item_id)
);

CREATE INDEX IF NOT EXISTS idx_user_favorites_user_created ON user_favorites (user_id, created_at);

-- Knowledge base chunks for RAG (private dish/nutrition docs)
-- NOTE: vector dimension is 1536 by default and should match OPENROUTER_EMBEDDING_MODEL.
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type TEXT NOT NULL CHECK (source_type IN ('menu', 'nutrition')),
    source_id TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding VECTOR(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_type, source_id)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_source ON knowledge_chunks (source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_metadata_gin ON knowledge_chunks USING GIN (metadata);

-- IVF index accelerates vector search at scale.
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_embedding
ON knowledge_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
