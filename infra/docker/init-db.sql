-- Khởi tạo database schema cho Collector Tool - Tối ưu hóa cho Batch Processing

-- Thêm extension pgcrypto để hỗ trợ hàm băm MD5 nếu cần (tùy chọn)
-- CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. Bảng lưu trữ thông tin sản phẩm
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    url_hash CHAR(32) UNIQUE NOT NULL, -- Mã băm MD5 của URL để Deduplication
    name VARCHAR(500) NOT NULL,
    price_numeric DECIMAL(12,2),
    currency VARCHAR(10) DEFAULT 'VND',
    brand VARCHAR(100),
    category VARCHAR(255),
    description TEXT,
    url TEXT,
    image_url TEXT,
    source_site VARCHAR(100) NOT NULL,
    raw_data JSONB, -- Lưu trữ dữ liệu gốc dạng JSON để đối chiếu
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Bảng lưu trữ thông tin cửa hàng/chi nhánh (Địa chỉ)
CREATE TABLE IF NOT EXISTS branches (
    id SERIAL PRIMARY KEY,
    branch_name VARCHAR(255) NOT NULL,
    address TEXT,
    phone VARCHAR(50),
    email VARCHAR(100),
    district VARCHAR(100),
    city VARCHAR(100),
    branch_url TEXT,
    source_site VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Bảng theo dõi các file được lưu trong MinIO và trạng thái xử lý Batch
CREATE TABLE IF NOT EXISTS scraped_files (
    id SERIAL PRIMARY KEY,
    url_hash CHAR(32) UNIQUE NOT NULL,
    url TEXT NOT NULL,
    minio_path TEXT NOT NULL, -- Đường dẫn đến file .mhtml trong MinIO
    source VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- pending, processing, completed, failed
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

-- 4. Bảng theo dõi phiên thu thập (Scrape Sessions)
CREATE TABLE IF NOT EXISTS scrape_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) UNIQUE NOT NULL,
    source VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'running',
    total_items INTEGER DEFAULT 0,
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    error_message TEXT
);

-- Tạo Index để tăng tốc độ truy vấn
CREATE INDEX IF NOT EXISTS idx_products_source ON products(source_site);
CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
CREATE INDEX IF NOT EXISTS idx_branches_city ON branches(city);
CREATE INDEX IF NOT EXISTS idx_scraped_files_status ON scraped_files(status);
CREATE INDEX IF NOT EXISTS idx_scrape_sessions_source ON scrape_sessions(source);

-- ============================================================================
-- Orchestration tables (Monthly automation backbone)
-- ============================================================================

-- 1) Domain registry + cadence
CREATE TABLE IF NOT EXISTS domains (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) UNIQUE NOT NULL,      -- e.g. "winemart.vn"
    base_url TEXT NOT NULL,                   -- e.g. "https://winemart.vn"
    strategy VARCHAR(50) DEFAULT 'auto',      -- auto|api|html|playwright|mhtml|manual
    cadence VARCHAR(50) DEFAULT 'monthly',    -- monthly|weekly|daily|custom
    enabled BOOLEAN DEFAULT TRUE,

    health_score NUMERIC(5,2) DEFAULT 1.00,   -- 0..1 (or any scoring you choose)
    blocked_reason TEXT,
    prompt_version VARCHAR(64),

    last_discover_at TIMESTAMP,
    last_collect_at  TIMESTAMP,
    last_extract_at  TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_domains_enabled ON domains(enabled);
CREATE INDEX IF NOT EXISTS idx_domains_cadence ON domains(cadence);

-- 2) Monthly runs
CREATE TABLE IF NOT EXISTS crawl_runs (
    id SERIAL PRIMARY KEY,
    run_key VARCHAR(64) UNIQUE NOT NULL,      -- e.g. "monthly_202604"
    cadence VARCHAR(50) NOT NULL DEFAULT 'monthly',
    status VARCHAR(20) DEFAULT 'running',     -- running|done|failed
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    meta JSONB
);

CREATE INDEX IF NOT EXISTS idx_crawl_runs_status ON crawl_runs(status);
CREATE INDEX IF NOT EXISTS idx_crawl_runs_cadence ON crawl_runs(cadence);

-- 3) Tasks per run/domain
CREATE TABLE IF NOT EXISTS crawl_tasks (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES crawl_runs(id) ON DELETE CASCADE,
    domain_id INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
    task_type VARCHAR(20) NOT NULL,           -- discover|collect|extract|dq
    target_url TEXT,
    status VARCHAR(20) DEFAULT 'pending',     -- pending|running|done|failed|skipped
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 2,
    scheduled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    error_message TEXT,
    meta JSONB
);

CREATE INDEX IF NOT EXISTS idx_crawl_tasks_run ON crawl_tasks(run_id);
CREATE INDEX IF NOT EXISTS idx_crawl_tasks_domain ON crawl_tasks(domain_id);
CREATE INDEX IF NOT EXISTS idx_crawl_tasks_status ON crawl_tasks(status);

-- 4) Extract run summary (optional but useful for audit)
CREATE TABLE IF NOT EXISTS extract_runs (
    id SERIAL PRIMARY KEY,
    run_id INTEGER REFERENCES crawl_runs(id) ON DELETE SET NULL,
    domain_id INTEGER REFERENCES domains(id) ON DELETE SET NULL,
    status VARCHAR(20) DEFAULT 'running',     -- running|done|failed
    files_total INTEGER DEFAULT 0,
    files_ok INTEGER DEFAULT 0,
    files_failed INTEGER DEFAULT 0,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    meta JSONB
);

CREATE INDEX IF NOT EXISTS idx_extract_runs_status ON extract_runs(status);

-- 5) Data quality results (placeholder)
CREATE TABLE IF NOT EXISTS dq_results (
    id SERIAL PRIMARY KEY,
    run_id INTEGER REFERENCES crawl_runs(id) ON DELETE SET NULL,
    domain_id INTEGER REFERENCES domains(id) ON DELETE SET NULL,
    metric VARCHAR(100) NOT NULL,
    value NUMERIC,
    passed BOOLEAN,
    details JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trigger tự động cập nhật updated_at (Tùy chọn - chỉ dành cho Postgres)
-- CREATE OR REPLACE FUNCTION update_modified_column()
-- RETURNS TRIGGER AS $$
-- BEGIN
--     NEW.updated_at = now();
--     RETURN NEW;
-- END;
-- $$ language 'plpgsql';

-- CREATE TRIGGER update_products_modtime
--     BEFORE UPDATE ON products
--     FOR EACH ROW
--     EXECUTE PROCEDURE update_modified_column();
