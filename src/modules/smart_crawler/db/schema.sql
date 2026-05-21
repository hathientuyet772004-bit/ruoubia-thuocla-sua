-- ==============================================================================
-- SMART CRAWLER & MARKETPLACE ANALYTICS SCHEMA
-- Version: 2.0.0
-- Description: Centralized Schema for Smart Crawling, Lakehouse ETL, and AI Extraction
-- ==============================================================================

-- Bật extension để sinh UUID tự động
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── 1. DOMAINS (Infrastructure Metadata) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS domains (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain VARCHAR(255) UNIQUE NOT NULL,
    category VARCHAR(100), -- ruou-bia, thuoc-la, sua

    strategy VARCHAR(50) DEFAULT 'DIRECT', -- DIRECT / MHTML
    is_blocked BOOLEAN DEFAULT FALSE,
    has_api BOOLEAN DEFAULT FALSE,

    last_crawled_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ── 2. STRUCTURES (LLM Extraction Templates Cache) ──────────────────────────
CREATE TABLE IF NOT EXISTS structures (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain_id UUID REFERENCES domains(id) ON DELETE CASCADE,

    structure_json JSONB NOT NULL,
    version INT DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ── 3. PRODUCTS (Global Entity - Unique Products) ───────────────────────────
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Chúng ta có thể trỏ tới domain gốc nơi product này được tìm thấy lần đầu
    domain_id UUID REFERENCES domains(id) ON DELETE SET NULL,
    source_url TEXT UNIQUE NOT NULL, -- URL gốc để định danh duy nhất

    name TEXT NOT NULL,
    image_url TEXT,
    brand TEXT,
    category TEXT,
    
    rating FLOAT DEFAULT 0,
    
    -- Dữ liệu thô từ lần extract cuối cùng để re-process
    raw_data JSONB,

    -- Trust metrics
    confidence_score FLOAT DEFAULT 1.0,
    validation_status VARCHAR(50) DEFAULT 'valid', -- valid, needs_review, invalid

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ── 4. STORES (Sellers/Marketplaces) ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS stores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain_id UUID REFERENCES domains(id) ON DELETE CASCADE,

    store_name TEXT NOT NULL, -- Ví dụ: "Tiki Trading", "Shop Rượu Ngoại"
    store_url TEXT,
    
    rating FLOAT DEFAULT 0,
    review_count INT DEFAULT 0,
    
    location TEXT,
    is_official BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(domain_id, store_name) -- Tránh duplicate store trên cùng 1 domain
);

-- ── 5. PRODUCT_OFFERS (The Marketplace "Offer") ───────────────────────────
CREATE TABLE IF NOT EXISTS product_offers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    store_id UUID REFERENCES stores(id) ON DELETE CASCADE,

    price NUMERIC(15, 2) NOT NULL,
    original_price NUMERIC(15, 2),
    currency VARCHAR(10) DEFAULT 'VND',

    stock_status VARCHAR(50) DEFAULT 'in_stock', -- in_stock, out_of_stock, unknown
    product_url TEXT NOT NULL, -- Link trực tiếp đến trang bán của shop này

    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(product_id, store_id) -- Mỗi store chỉ có 1 giá hiện tại cho 1 product
);

-- ── 6. PRICE_HISTORY (Time-series Tracking) ──────────────────────────────────
CREATE TABLE IF NOT EXISTS price_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_offer_id UUID REFERENCES product_offers(id) ON DELETE CASCADE,

    price NUMERIC(15, 2) NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ── 7. RAW_FILES (Lakehouse Management) ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    category VARCHAR(100),
    domain VARCHAR(255),

    file_path TEXT UNIQUE NOT NULL, -- Path trong MinIO
    file_type VARCHAR(20), -- html, mhtml

    is_decoded BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) DEFAULT 'PENDING', -- PENDING, PROCESSED, FAILED
    error_message TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ── 8. CRAWL_JOBS (Execution Tracking) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS crawl_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain_id UUID REFERENCES domains(id) ON DELETE CASCADE,
    
    strategy VARCHAR(50),
    total_pages INT DEFAULT 0,
    processed_pages INT DEFAULT 0,
    
    success_count INT DEFAULT 0,
    failed_count INT DEFAULT 0,
    fallback_count INT DEFAULT 0, -- Số lần phải dùng LLM fallback

    status VARCHAR(50) DEFAULT 'RUNNING', -- RUNNING, COMPLETED, FAILED
    
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP WITH TIME ZONE
);

-- ── 9. LAKEHOUSE_JOBS (ETL Execution) ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS lakehouse_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    category VARCHAR(100),
    domain VARCHAR(255),

    total_files INT DEFAULT 0,
    processed_files INT DEFAULT 0,
    success_count INT DEFAULT 0,
    failed_count INT DEFAULT 0,

    status VARCHAR(50) NOT NULL,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ── 10. EXTRACTION_LOGS (Traceability & Debug) ──────────────────────────────
CREATE TABLE IF NOT EXISTS extraction_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain_id UUID REFERENCES domains(id),
    product_url TEXT,

    used_structure BOOLEAN DEFAULT FALSE,
    used_fallback BOOLEAN DEFAULT FALSE, -- Bằng TRUE nếu dùng LLM fallback
    
    execution_time_ms INT,
    error_message TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ── 11. DOMAIN_STATS (Analytical Snapshots) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS domain_stats (
    domain_id UUID PRIMARY KEY REFERENCES domains(id) ON DELETE CASCADE,

    total_products INT DEFAULT 0,
    success_rate FLOAT DEFAULT 0,
    fallback_rate FLOAT DEFAULT 0,

    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- INDEXING STRATEGY
-- ==============================================================================

-- 1. Tối ưu tìm kiếm Product & Domain
CREATE INDEX IF NOT EXISTS idx_products_domain ON products(domain_id);
CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);

-- 2. Tối ưu Marketplace Queries (Hàng đầu cho bài toán Marketplace)
CREATE INDEX IF NOT EXISTS idx_offers_product ON product_offers(product_id);
CREATE INDEX IF NOT EXISTS idx_offers_store ON product_offers(store_id);
CREATE INDEX IF NOT EXISTS idx_offers_price ON product_offers(price);

-- 3. Tối ưu Lakehouse ETL
CREATE INDEX IF NOT EXISTS idx_raw_files_status_domain ON raw_files(status, domain);

-- 4. Tối ưu Debugging
CREATE INDEX IF NOT EXISTS idx_logs_domain ON extraction_logs(domain_id, created_at DESC);

-- 5. GIN Index cho raw_data JSONB (Cho phép tìm kiếm nội dung bên trong thô)
CREATE INDEX IF NOT EXISTS idx_products_raw_data ON products USING GIN (raw_data);

-- ==============================================================================
-- AUDIT TRIGGER (Auto-update updated_at)
-- ==============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plrcpgsql';

-- Disable triggers by default for performance if needed, but good for data integrity
-- CREATE TRIGGER update_products_updated_at BEFORE UPDATE ON products FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
