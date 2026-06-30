"""Initial schema — create all 17 existing tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-30
"""
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS sources (
            id SERIAL PRIMARY KEY,
            name TEXT,
            url TEXT NOT NULL UNIQUE,
            type TEXT,
            category TEXT,
            note TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS sc_raw_pages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            task_id TEXT,
            source_id INTEGER REFERENCES sources(id) ON DELETE SET NULL,
            url TEXT,
            filename TEXT,
            path TEXT,
            page_type TEXT,
            domain TEXT,
            content_length INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS sc_crawl_tasks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_id INTEGER REFERENCES sources(id) ON DELETE SET NULL,
            status TEXT DEFAULT 'Pending',
            mode TEXT,
            filename TEXT,
            source TEXT,
            summary JSONB DEFAULT '{}',
            error TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS sc_products (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT,
            brand TEXT,
            category TEXT,
            price TEXT,
            price_numeric NUMERIC,
            price_status TEXT DEFAULT 'MISSING',
            currency TEXT DEFAULT 'VND',
            url TEXT,
            source TEXT,
            source_site TEXT,
            store_name TEXT,
            store_address TEXT,
            store_url TEXT,
            store_channel TEXT,
            address_status TEXT,
            domain TEXT,
            rating NUMERIC,
            data JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS sc_offers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            product_id UUID REFERENCES sc_products(id) ON DELETE CASCADE,
            source_id INTEGER REFERENCES sources(id) ON DELETE SET NULL,
            price NUMERIC,
            currency TEXT DEFAULT 'VND',
            url TEXT,
            raw_page_id UUID,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS sc_price_observations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            product_id UUID REFERENCES sc_products(id) ON DELETE CASCADE,
            price NUMERIC,
            currency TEXT DEFAULT 'VND',
            source TEXT,
            observed_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS sc_generation_prompts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_id INTEGER REFERENCES sources(id) ON DELETE SET NULL,
            prompt TEXT,
            model TEXT,
            result JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_extraction_rules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            domain TEXT NOT NULL UNIQUE,
            target TEXT DEFAULT 'product_detail',
            targets TEXT[] DEFAULT '{}',
            fields JSONB DEFAULT '[]',
            version INTEGER DEFAULT 1,
            quality_score NUMERIC DEFAULT 0,
            source TEXT DEFAULT 'manual',
            raw_page_id UUID,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_extraction_rule_versions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            domain TEXT NOT NULL,
            version INTEGER NOT NULL,
            target TEXT,
            fields JSONB DEFAULT '[]',
            quality_score NUMERIC DEFAULT 0,
            source TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_extraction_rule_candidates (
            candidate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            domain TEXT NOT NULL,
            model TEXT,
            fields JSONB DEFAULT '[]',
            quality JSONB DEFAULT '{}',
            status TEXT DEFAULT 'pending',
            raw_page_id UUID,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_rule_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            domain TEXT NOT NULL,
            event_type TEXT,
            data JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_rule_generation_attempts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            domain TEXT NOT NULL,
            model TEXT,
            status TEXT,
            error TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_ai_review_candidates (
            review_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            entity_type TEXT,
            source TEXT,
            source_site TEXT,
            raw_page_url TEXT,
            payload JSONB DEFAULT '{}',
            confidence NUMERIC DEFAULT 0,
            reason TEXT,
            status TEXT DEFAULT 'needs_review',
            published_at TIMESTAMPTZ,
            raw_page_id UUID,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_dedup_candidates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            left_id UUID,
            right_id UUID,
            left_data JSONB DEFAULT '{}',
            right_data JSONB DEFAULT '{}',
            confidence NUMERIC DEFAULT 0,
            reasons TEXT[] DEFAULT '{}',
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_pipelines (
            pipeline_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            enabled BOOLEAN DEFAULT TRUE,
            cron TEXT,
            status TEXT DEFAULT 'idle',
            data JSONB DEFAULT '{}',
            last_run_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_pipeline_runs (
            run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            pipeline_id UUID REFERENCES admin_pipelines(pipeline_id) ON DELETE CASCADE,
            status TEXT DEFAULT 'pending',
            data JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_pipeline_worker_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            pipeline_id UUID,
            run_id UUID,
            event TEXT,
            data JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_sources_url ON sources(url)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sc_products_domain ON sc_products(domain)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sc_products_source ON sc_products(source)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sc_products_category ON sc_products(category)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sc_crawl_tasks_status ON sc_crawl_tasks(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_admin_extraction_rules_domain ON admin_extraction_rules(domain)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_admin_ai_review_candidates_status ON admin_ai_review_candidates(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_admin_dedup_candidates_status ON admin_dedup_candidates(status)")


def downgrade() -> None:
    tables = [
        "admin_pipeline_worker_events",
        "admin_pipeline_runs",
        "admin_pipelines",
        "admin_dedup_candidates",
        "admin_ai_review_candidates",
        "admin_rule_generation_attempts",
        "admin_rule_events",
        "admin_extraction_rule_candidates",
        "admin_extraction_rule_versions",
        "admin_extraction_rules",
        "sc_generation_prompts",
        "sc_price_observations",
        "sc_offers",
        "sc_products",
        "sc_crawl_tasks",
        "sc_raw_pages",
        "sources",
    ]
    for t in tables:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
