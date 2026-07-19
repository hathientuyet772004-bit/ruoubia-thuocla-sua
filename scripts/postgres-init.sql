CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    name TEXT,
    url TEXT NOT NULL UNIQUE,
    base_url TEXT,
    domain TEXT,
    type TEXT,
    category TEXT,
    target_categories JSONB DEFAULT '[]'::jsonb,
    note TEXT,
    store_scope TEXT DEFAULT 'site',
    store_name TEXT,
    store_url TEXT,
    store_address TEXT,
    store_phone TEXT,
    store_channel TEXT,
    auto_promote_rules BOOLEAN DEFAULT TRUE,
    quality_gate_enabled BOOLEAN DEFAULT TRUE,
    important BOOLEAN DEFAULT FALSE,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sc_products (
    product_id TEXT PRIMARY KEY,
    product_name TEXT,
    canonical_name TEXT,
    product_url TEXT,
    image_url TEXT,
    price_numeric NUMERIC,
    price NUMERIC,
    price_status TEXT,
    old_price NUMERIC,
    currency TEXT DEFAULT 'VND',
    brand TEXT,
    category TEXT,
    normalized_category TEXT,
    store_name TEXT,
    store_url TEXT,
    store_address TEXT,
    store_channel TEXT,
    address_status TEXT,
    store_phone TEXT,
    domain TEXT,
    source_id TEXT,
    raw_page_id TEXT,
    raw_data JSONB DEFAULT '{}'::jsonb,
    data_origin TEXT,
    evidence_id TEXT,
    rule_version TEXT,
    extraction_method TEXT,
    model TEXT,
    content_hash TEXT,
    field_sources JSONB DEFAULT '{}'::jsonb,
    field_details JSONB DEFAULT '{}'::jsonb,
    validation_score NUMERIC,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sc_offers (
    offer_id TEXT PRIMARY KEY,
    seller_key TEXT,
    product_id TEXT,
    product_name TEXT,
    product_url TEXT,
    data JSONB DEFAULT '{}'::jsonb,
    price_numeric NUMERIC,
    currency TEXT DEFAULT 'VND',
    store_name TEXT,
    store_url TEXT,
    store_address TEXT,
    store_phone TEXT,
    domain TEXT,
    source_id TEXT,
    raw_page_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sc_price_observations (
    observation_id TEXT PRIMARY KEY,
    product_id TEXT,
    price_numeric NUMERIC,
    currency TEXT DEFAULT 'VND',
    domain TEXT,
    source_id TEXT,
    raw_page_id TEXT,
    rule_version TEXT,
    data_origin TEXT,
    observed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sc_raw_pages (
    raw_page_id TEXT PRIMARY KEY,
    url TEXT,
    domain TEXT,
    page_type TEXT,
    task_id TEXT,
    captured_at TIMESTAMPTZ DEFAULT NOW(),
    content_type TEXT,
    content_length INTEGER DEFAULT 0,
    status TEXT,
    minio_key TEXT,
    content TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS admin_extraction_rules (
    domain TEXT PRIMARY KEY,
    structure JSONB NOT NULL DEFAULT '{}'::jsonb,
    version TEXT,
    quality JSONB DEFAULT '{}'::jsonb,
    candidate_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS admin_extraction_rule_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain TEXT NOT NULL,
    structure JSONB DEFAULT '{}'::jsonb,
    version TEXT,
    quality JSONB DEFAULT '{}'::jsonb,
    status TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS admin_extraction_rule_candidates (
    candidate_id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    structure JSONB DEFAULT '{}'::jsonb,
    version TEXT,
    status TEXT DEFAULT 'pending',
    quality JSONB DEFAULT '{}'::jsonb,
    score NUMERIC DEFAULT 0,
    model TEXT,
    artifact_ids JSONB DEFAULT '[]'::jsonb,
    content_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS admin_rule_generation_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    model TEXT,
    status TEXT,
    error TEXT,
    retry_after TIMESTAMPTZ,
    attempt_count INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(domain, content_hash)
);

CREATE TABLE IF NOT EXISTS admin_rule_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event JSONB DEFAULT '{}'::jsonb,
    domain TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS admin_pipelines (
    pipeline_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    data JSONB DEFAULT '{}'::jsonb,
    locked_by_run_id TEXT,
    locked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS admin_pipeline_runs (
    run_id TEXT PRIMARY KEY,
    pipeline_id TEXT REFERENCES admin_pipelines(pipeline_id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',
    data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS admin_pipeline_worker_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_id TEXT,
    data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS admin_dedup_candidates (
    candidate_id TEXT PRIMARY KEY,
    confidence NUMERIC DEFAULT 0,
    reasons JSONB DEFAULT '[]'::jsonb,
    left_product JSONB DEFAULT '{}'::jsonb,
    right_product JSONB DEFAULT '{}'::jsonb,
    status TEXT DEFAULT 'pending',
    note TEXT,
    updated_by_role TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS admin_ai_review_candidates (
    review_id TEXT PRIMARY KEY,
    domain TEXT,
    entity_type TEXT,
    status TEXT DEFAULT 'needs_review',
    confidence NUMERIC,
    reason TEXT,
    payload JSONB DEFAULT '{}'::jsonb,
    note TEXT,
    updated_by_role TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sc_synthetic_products (
    synthetic_id TEXT PRIMARY KEY,
    batch_id TEXT,
    source_id TEXT,
    source_domain TEXT,
    source_name TEXT,
    payload JSONB DEFAULT '{}'::jsonb,
    data_origin TEXT,
    validation_status TEXT,
    review_status TEXT,
    validation JSONB DEFAULT '{}'::jsonb,
    model TEXT,
    prompt_hash TEXT,
    review_note TEXT,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sc_synthetic_quarantine (LIKE sc_synthetic_products INCLUDING ALL);

CREATE TABLE IF NOT EXISTS sc_product_quarantine (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain TEXT,
    source_id TEXT,
    raw_page_id TEXT,
    reason TEXT,
    payload JSONB DEFAULT '{}'::jsonb,
    metrics JSONB DEFAULT '{}'::jsonb,
    previous_metrics JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sc_generation_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key TEXT NOT NULL,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(key, version)
);

CREATE TABLE IF NOT EXISTS category_rules (
    id SERIAL PRIMARY KEY,
    category TEXT NOT NULL,
    keywords TEXT[] NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO category_rules (category, keywords, priority, is_active) VALUES
('Rượu', ARRAY['ruou','rượu','vodka','whisky','whiskey','wine','soju','cognac','rum','gin','tequila','brandy','liqueur'], 4, TRUE),
('Bia', ARRAY['bia','beer','lager','ale','stout'], 3, TRUE),
('Thuốc lá', ARRAY['thuoc la','thuốc lá','cigarette','cigar','tobacco'], 2, TRUE),
('Sữa', ARRAY['sua','sữa','milk','vinamilk','th true milk','moc chau milk','dutch lady'], 1, TRUE)
ON CONFLICT DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_sc_products_domain ON sc_products(domain);
CREATE INDEX IF NOT EXISTS idx_sc_raw_pages_domain_captured ON sc_raw_pages(domain, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_sc_raw_pages_url_captured ON sc_raw_pages(url, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_pipeline_runs_pipeline ON admin_pipeline_runs(pipeline_id, created_at DESC);

GRANT USAGE, CREATE ON SCHEMA public TO admin_center;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO admin_center;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO admin_center;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO admin_center;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO admin_center;
