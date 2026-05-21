-- Migration: extend legacy products schema to match current pipeline expectations
-- Safe to run multiple times.

ALTER TABLE IF EXISTS products
    ADD COLUMN IF NOT EXISTS url_hash CHAR(32),
    ADD COLUMN IF NOT EXISTS price_numeric DECIMAL(12,2),
    ADD COLUMN IF NOT EXISTS currency VARCHAR(10) DEFAULT 'VND',
    ADD COLUMN IF NOT EXISTS brand VARCHAR(100),
    ADD COLUMN IF NOT EXISTS category VARCHAR(255),
    ADD COLUMN IF NOT EXISTS image_url TEXT,
    ADD COLUMN IF NOT EXISTS source_site VARCHAR(100),
    ADD COLUMN IF NOT EXISTS raw_data JSONB;

-- Backfill best-effort from legacy columns
UPDATE products
SET price_numeric = COALESCE(price_numeric, price),
    source_site  = COALESCE(source_site, source)
WHERE price_numeric IS NULL OR source_site IS NULL;

-- Add constraint/indexes used by pipeline (create only if missing)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'products_url_hash_key'
    ) THEN
        -- Allow NULLs for existing rows; enforce uniqueness where present
        ALTER TABLE products ADD CONSTRAINT products_url_hash_key UNIQUE (url_hash);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_products_source_site ON products(source_site);

