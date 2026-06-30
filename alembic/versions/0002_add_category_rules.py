"""Add category_rules config table for DB-driven category normalization

Revision ID: 0002_category_rules
Revises: 0001_initial
Create Date: 2026-06-30
"""
from alembic import op

revision = "0002_category_rules"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

SEED_ROWS = [
    ("Rượu",    ["ruou","rượu","vodka","whisky","whiskey","wine","soju","cognac","rum","gin","tequila","brandy","liqueur"]),
    ("Bia",     ["bia","beer","lager","ale","stout"]),
    ("Thuốc lá", ["thuoc la","thuốc lá","cigarette","cigar","tobacco"]),
    ("Sữa",    ["sua","sữa","milk","vinamilk","th true milk","moc chau milk","dutch lady"]),
]


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS category_rules (
            id SERIAL PRIMARY KEY,
            category TEXT NOT NULL,
            keywords TEXT[] NOT NULL,
            priority INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_category_rules_active ON category_rules(is_active, priority DESC)")

    for i, (category, keywords) in enumerate(SEED_ROWS):
        kw_literal = "ARRAY[" + ",".join(f"'{k}'" for k in keywords) + "]"
        op.execute(f"""
            INSERT INTO category_rules (category, keywords, priority, is_active)
            VALUES ('{category}', {kw_literal}, {len(SEED_ROWS) - i}, TRUE)
            ON CONFLICT DO NOTHING
        """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS category_rules CASCADE")
