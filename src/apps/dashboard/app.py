import streamlit as st
import pandas as pd
from shared.config import settings
from sqlalchemy import create_engine, text

st.set_page_config(
    page_title="Collector Dashboard",
    page_icon="🕸️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for premium look
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    .stMetric {
        background-color: #1a1c24;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #30363d;
    }
    .confidence-high { color: #23d38a; }
    .confidence-med { color: #f1c40f; }
    .confidence-low { color: #e74c3c; }
    </style>
    """, unsafe_allow_html=True)


@st.cache_resource
def get_engine():
    return create_engine(settings.database_url, pool_pre_ping=True)


def _scalar(sql: str, **params):
    engine = get_engine()
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar()


def get_stats():
    try:
        total_products = _scalar("SELECT COUNT(*) FROM products") or 0
        pending = _scalar("SELECT COUNT(*) FROM scraped_files WHERE status='pending'") or 0
        processing = _scalar("SELECT COUNT(*) FROM scraped_files WHERE status='processing'") or 0
        completed = _scalar("SELECT COUNT(*) FROM scraped_files WHERE status='completed'") or 0
        failed = _scalar("SELECT COUNT(*) FROM scraped_files WHERE status='failed'") or 0
        sources = _scalar("SELECT COUNT(DISTINCT source_site) FROM products") or 0
    except Exception as e:
        return None, str(e)

    return {
        "total_products": int(total_products),
        "total_sources": int(sources),
        "files_pending": int(pending),
        "files_processing": int(processing),
        "files_completed": int(completed),
        "files_failed": int(failed),
    }, None


def list_products(limit=100, source_site: str | None = None):
    engine = get_engine()
    base = """
        SELECT
            name,
            price_numeric,
            currency,
            source_site,
            url,
            updated_at
        FROM products
    """
    params = {"limit": int(limit)}
    if source_site and source_site != "all":
        base += " WHERE source_site = :source_site"
        params["source_site"] = source_site
    base += " ORDER BY updated_at DESC NULLS LAST LIMIT :limit"

    try:
        with engine.connect() as conn:
            return pd.read_sql_query(text(base), conn, params=params)
    except Exception:
        return pd.DataFrame()


def list_sources(limit=100):
    engine = get_engine()
    sql = """
        SELECT source_site, COUNT(*) AS product_count
        FROM products
        GROUP BY source_site
        ORDER BY product_count DESC
        LIMIT :limit
    """
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(text(sql), conn, params={"limit": int(limit)})
        return ["all"] + df["source_site"].tolist()
    except Exception:
        return ["all"]

def main():
    st.title("🕸️ Collector Dashboard")
    st.markdown("---")

    stats, err = get_stats()
    if err:
        st.error(f"Không kết nối/đọc được DB: {err}")
        st.info("Kiểm tra `POSTGRES_*` trong `.env`, hoặc chạy `docker compose up -d db`.")
        return

    # Rest of the dashboard...
    if stats:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Products", stats['total_products'])
        with col2:
            st.metric("Sources", stats['total_sources'])
        with col3:
            st.metric("Files Pending", stats['files_pending'])
        with col4:
            st.metric("Files Failed", stats['files_failed'])

    st.sidebar.header("Control Panel")
    selected_source = st.sidebar.selectbox("Filter Source", list_sources())
    limit = st.sidebar.number_input("Rows", min_value=10, max_value=500, value=100, step=10)

    st.subheader(f"Recent Products ({selected_source})")
    df = list_products(limit=limit, source_site=selected_source)
    
    if not df.empty:
        st.dataframe(
            df,
            column_config={
                "url": st.column_config.LinkColumn("Product Link"),
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No products found for the selected filter.")

    st.sidebar.markdown("---")
    st.sidebar.subheader("System Notes")
    st.sidebar.info("Dashboard này bám theo schema Collector hiện tại (products, scraped_files).")

if __name__ == "__main__":
    main()
