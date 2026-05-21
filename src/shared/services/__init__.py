from .browser_service import fetch_html, fetch_mhtml, BrowserManager, ProxyPatcher

# Wrappers cho Proxy (được dùng trong routers/proxy.py)
rewrite_links_for_proxy = ProxyPatcher.rewrite_links
inject_proxy_script = ProxyPatcher.inject_script

from .minio_service import upload_mhtml, make_url_hash, upload_processed_json, download_mhtml
from .redis_service import is_url_seen, mark_url_seen, mark_urls_seen_bulk
from .url_service import get_domain, normalize_url, classify_url, get_month_key, format_load_time, safe_filename
from .discovery_service import DiscoveryService, CollectConfig
from .site_analyzer import SiteAnalyzer
