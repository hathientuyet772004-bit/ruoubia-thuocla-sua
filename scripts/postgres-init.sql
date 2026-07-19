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
    store_channel TEXT DEFAULT 'online',
    store_locator_url TEXT,
    auto_promote_rules BOOLEAN DEFAULT TRUE,
    quality_gate_enabled BOOLEAN DEFAULT TRUE,
    important BOOLEAN DEFAULT FALSE,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sc_store_locations (
    store_location_id TEXT PRIMARY KEY,
    source_id TEXT,
    domain TEXT,
    store_name TEXT,
    store_address TEXT,
    address_status TEXT,
    store_channel TEXT,
    store_phone TEXT,
    store_url TEXT,
    raw_page_id TEXT,
    raw_data JSONB DEFAULT '{}'::jsonb,
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
    canonical_product_id TEXT,
    canonical_key TEXT,
    canonical_match_score NUMERIC,
    canonicalized_at TIMESTAMPTZ,
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
    canonical_product_id TEXT,
    canonical_key TEXT,
    canonicalized_at TIMESTAMPTZ,
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
CREATE INDEX IF NOT EXISTS idx_sc_products_canonical ON sc_products(canonical_product_id);
CREATE INDEX IF NOT EXISTS idx_sc_offers_canonical ON sc_offers(canonical_product_id);
CREATE INDEX IF NOT EXISTS idx_sc_raw_pages_domain_captured ON sc_raw_pages(domain, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_sc_raw_pages_url_captured ON sc_raw_pages(url, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_pipeline_runs_pipeline ON admin_pipeline_runs(pipeline_id, created_at DESC);

GRANT USAGE, CREATE ON SCHEMA public TO admin_center;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO admin_center;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO admin_center;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO admin_center;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO admin_center;

-- Seed sources
INSERT INTO sources (source_id, name, url, base_url, domain, type, category, note) VALUES
('c649c9f5-349d-4e71-ab35-5f01c4c84494', 'TH true Mart', 'https://thtruemart.vn/', 'https://thtruemart.vn/', 'thtruemart.vn', 'Brand Store', 'Sữa', 'Sữa TH True Milk'),
('e865b508-0045-48ec-9607-de1d58e383dd', 'Bách Hóa Xanh', 'https://www.bachhoaxanh.com/sua', 'https://www.bachhoaxanh.com/sua', 'www.bachhoaxanh.com', 'E-commerce', 'Sữa', ''),
('d6b8c696-a375-497d-8014-223555f0ad67', 'WinMart', 'https://winmart.vn/', 'https://winmart.vn/', 'winmart.vn', 'E-commerce', 'Sữa', ''),
('3db0a05e-f586-4e3f-85da-fab1f93414da', 'Vinamilk eShop', 'https://giacmosuaviet.com.vn/', 'https://giacmosuaviet.com.vn/', 'giacmosuaviet.com.vn', 'Brand Store', 'Sữa', 'Cửa hàng chính hãng Vinamilk'),
('2f003bce-2093-472a-8899-314ad75220f8', 'Co.op Online', 'https://cooponline.vn/', 'https://cooponline.vn/', 'cooponline.vn', 'E-commerce', 'Sữa', 'Hàng tiêu dùng & sữa'),
('8af03290-e183-4cbb-8b20-3d7869fa8601', 'Lotte Mart', 'https://www.lottemart.vn/', 'https://www.lottemart.vn/', 'www.lottemart.vn', 'E-commerce', 'Sữa', 'Siêu thị'),
('3be8fd22-ba6d-4350-982f-6cb09fdc1b6d', 'GO! Big C', 'https://go-vietnam.vn/', 'https://go-vietnam.vn/', 'go-vietnam.vn', 'E-commerce', 'Sữa', 'Siêu thị GO!'),
('ec2046f2-9056-4ff4-9e22-5e0dd930b0ba', 'MM Mega Market', 'https://online.mmvietnam.com/', 'https://online.mmvietnam.com/', 'online.mmvietnam.com', 'E-commerce', 'Sữa', 'Bán sỉ & bán lẻ'),
('f8256e16-d096-4235-b3b0-db7354e62384', 'WineMart', 'https://winemart.vn/', 'https://winemart.vn/', 'winemart.vn', 'Liquor', 'Rượu', 'Rượu vang và rượu mạnh nhập khẩu'),
('666f250a-0160-4661-98d5-7bec146c5b03', 'Rượu Ngoại', 'https://ruoungoai.net/', 'https://ruoungoai.net/', 'ruoungoai.net', 'Liquor', 'Rượu', 'Whisky Vodka Cognac Rum Gin'),
('5372905b-a42d-4307-83d9-abb18b9c2b42', 'Sành Rượu', 'https://sanhruou.com/', 'https://sanhruou.com/', 'sanhruou.com', 'Liquor', 'Rượu', 'Rượu vang và rượu ngoại'),
('41c8c009-a461-4f07-8186-eb873fdbaba3', 'WineCellar', 'https://winecellar.vn/', 'https://winecellar.vn/', 'winecellar.vn', 'Liquor', 'Rượu', 'Rượu vang cao cấp'),
('80c27105-2e0e-420b-b27c-3a4fe313d3a7', 'Rượu Sỉ', 'https://ruousi.vn/', 'https://ruousi.vn/', 'ruousi.vn', 'Liquor', 'Rượu', 'Rượu ngoại và vang'),
('92e1adc9-6aca-45ae-b013-9e94e97720b5', 'Malt & Co', 'https://maltco.vn/', 'https://maltco.vn/', 'maltco.vn', 'Liquor', 'Rượu', 'Whisky nhập khẩu'),
('416725e2-543f-4fa0-95be-c19a9b81ddb6', 'WeWine', 'https://wewine.vn/', 'https://wewine.vn/', 'wewine.vn', 'Liquor', 'Rượu', 'Rượu vang nhập khẩu'),
('3bbb82f5-d65d-4ccf-a466-ebe8123a4fd7', 'InWine', 'https://inwine.vn/', 'https://inwine.vn/', 'inwine.vn', 'Liquor', 'Rượu', 'Rượu vang'),
('17bdcffa-70d5-4346-9d5b-79b5cc1e3d89', 'Rượu Ngoại Ngon', 'https://ruoungoaingon.com/', 'https://ruoungoaingon.com/', 'ruoungoaingon.com', 'Liquor', 'Rượu', 'Whisky và spirits'),
('efd96ecf-a519-4b10-b0f3-f3f0075ecf51', 'Shop Rượu Ngoại', 'https://shop-ruoungoai.com/', 'https://shop-ruoungoai.com/', 'shop-ruoungoai.com', 'Liquor', 'Rượu', 'Rượu ngoại nhập khẩu'),
('1faecede-e22c-4523-bda7-0cca1512c225', 'Bách Hóa Xanh', 'https://www.bachhoaxanh.com/bia', 'https://www.bachhoaxanh.com/bia', 'www.bachhoaxanh.com', 'E-commerce', 'Bia', 'Bia Heineken Tiger Budweiser Sapporo'),
('ffd5c29b-feb9-427b-9b84-8ee08d1e2dc0', 'Circle K Việt Nam', 'https://www.circlek.com.vn/', 'https://www.circlek.com.vn/', 'www.circlek.com.vn', 'Convenience', 'Bia', 'Cửa hàng tiện lợi'),
('4de09195-2ffd-46f4-b050-3dbb98f57f9d', 'GS25 Việt Nam', 'https://gs25.com.vn/', 'https://gs25.com.vn/', 'gs25.com.vn', 'Convenience', 'Bia', 'Cửa hàng tiện lợi'),
('ad825e72-99ea-46ac-a28a-3f082421b77c', 'FamilyMart Việt Nam', 'https://www.familymart.vn/', 'https://www.familymart.vn/', 'www.familymart.vn', 'Convenience', 'Bia', 'Cửa hàng tiện lợi'),
('cdf9fd38-a310-4582-8f9d-24895d5e6c3d', '7-Eleven Việt Nam', 'https://7eleven.vn/', 'https://7eleven.vn/', '7eleven.vn', 'Convenience', 'Bia', 'Cửa hàng tiện lợi'),
('44c54acb-81c7-4e55-bb22-9cbeefa77e01', 'Thuốc Lá 24h', 'https://thuocla24h.vn/', 'https://thuocla24h.vn/', 'thuocla24h.vn', 'Specialty', 'Thuốc lá', 'Thuốc lá nội địa và nhập khẩu'),
('ea7b7d58-beac-400d-a652-04b005487c92', 'Thế Giới Xì Gà', 'https://thegioixiga.vn/', 'https://thegioixiga.vn/', 'thegioixiga.vn', 'Specialty', 'Thuốc lá', 'Xì gà và thuốc lá cao cấp'),
('93842236-38fc-4386-a72f-87c0c41e4268', 'Cigar PTT', 'https://cigarptt.com/', 'https://cigarptt.com/', 'cigarptt.com', 'Specialty', 'Thuốc lá', 'Xì gà Cuba và phụ kiện'),
('cd2d65b8-4176-4839-89ce-6fa3a39489e2', 'Vua Xì Gà', 'https://vuaxiga.vn/', 'https://vuaxiga.vn/', 'vuaxiga.vn', 'Specialty', 'Thuốc lá', 'Xì gà nhập khẩu'),
('2f93243d-fc11-407d-8c2c-c58b42dcac51', 'Example Site', 'https://example.com', 'https://example.com', 'example.com', 'E-commerce', 'Khác', 'Nguon test them moi va chay thu thap')
ON CONFLICT (source_id) DO NOTHING;
