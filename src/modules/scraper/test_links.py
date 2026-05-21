import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
import pandas as pd
import xml.etree.ElementTree as ET
import gzip
from io import BytesIO
import time

# =============================
# HEADERS (ANTI-BOT FIX)
# =============================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive"
}

# =============================
# REQUEST (RETRY)
# =============================
def safe_request(url, retries=3, timeout=10):
    for i in range(retries):
        try:
            res = requests.get(url, headers=HEADERS, timeout=timeout)
            if res.status_code == 200:
                return res
        except:
            pass
        time.sleep(2)
    return None


# =============================
# BASIC FUNCTIONS
# =============================
def normalize_link(base_url, link):
    return urljoin(base_url, link)


def is_internal(domain, link):
    parsed = urlparse(link)
    return parsed.netloc == "" or parsed.netloc == domain


def is_valid_link(link):
    return not (
        link.startswith("tel:") or
        link.startswith("javascript:") or
        link.startswith("#")
    )


# =============================
# SITEMAP HELPERS
# =============================
def clean_xml(content):
    return content.lstrip()


def get_sitemap_from_robots(base_url):
    robots_url = urljoin(base_url, "/robots.txt")
    res = safe_request(robots_url)

    if res and res.status_code == 200:
        lines = res.text.split("\n")
        return [l.split(": ")[1].strip() for l in lines if "Sitemap:" in l]

    return []


def find_common_sitemaps(base_url):
    paths = [
        "/sitemap.xml",
        "/sitemap_index.xml",
        "/wp-sitemap.xml",
        "/sitemap.xml.gz",
        "/media/sitemap.xml"
    ]

    found = []
    for path in paths:
        url = urljoin(base_url, path)
        res = safe_request(url)
        if res and res.status_code == 200:
            found.append(url)

    return found


# =============================
# PARSE SITEMAP (ROBUST)
# =============================
def parse_sitemap(url):
    res = safe_request(url)

    if not res or res.status_code != 200:
        return []

    content = res.content

    # detect HTML (anti-bot)
    if b"<html" in content[:300].lower():
        print(f"  ⚠ Blocked (HTML instead of XML): {url}")
        return []

    # gzip
    if url.endswith(".gz"):
        try:
            content = gzip.GzipFile(fileobj=BytesIO(content)).read()
        except:
            return []

    content = clean_xml(content)

    urls = []

    try:
        root = ET.fromstring(content)

        namespace = ""
        if root.tag.startswith("{"):
            namespace = root.tag.split("}")[0] + "}"

        # sitemap index
        if "sitemapindex" in root.tag:
            for sitemap in root.findall(f"{namespace}sitemap"):
                loc = sitemap.find(f"{namespace}loc")
                if loc is not None:
                    urls.append(loc.text)

        # url set
        elif "urlset" in root.tag:
            for url_tag in root.findall(f"{namespace}url"):
                loc = url_tag.find(f"{namespace}loc")
                if loc is not None:
                    urls.append(loc.text)

    except Exception as e:
        print(f"  ❌ Parse error: {url} | {e}")

    return urls


# =============================
# SITEMAP PIPELINE
# =============================
def extract_sitemap_urls(base_url):
    all_sitemaps = set()

    all_sitemaps.update(find_common_sitemaps(base_url))
    all_sitemaps.update(get_sitemap_from_robots(base_url))

    all_urls = set()

    for sitemap in all_sitemaps:
        print(f"  → Parsing sitemap: {sitemap}")
        urls = parse_sitemap(sitemap)

        print(f"     ↳ Extracted: {len(urls)}")

        for u in urls:
            if u and ("sitemap" in u or u.endswith(".xml")):
                sub_urls = parse_sitemap(u)
                all_urls.update(sub_urls)
            else:
                all_urls.add(u)

    return list(all_urls), list(all_sitemaps)


# =============================
# CRAWLER (FALLBACK)
# =============================
def get_links(url):
    res = safe_request(url)
    if not res:
        return set()

    soup = BeautifulSoup(res.text, "html.parser")

    links = set()
    for a in soup.find_all("a", href=True):
        if is_valid_link(a["href"]):
            links.add(a["href"])

    return links


def crawl_site(base_url, max_depth=2, max_pages=50):
    domain = urlparse(base_url).netloc

    visited = set()
    queue = deque([(base_url, 0)])

    urls = set()

    while queue and len(visited) < max_pages:
        url, depth = queue.popleft()

        if url in visited or depth > max_depth:
            continue

        print(f"  → Crawling: {url}")
        visited.add(url)
        urls.add(url)

        links = get_links(url)

        for link in links:
            full_link = normalize_link(base_url, link)

            if is_internal(domain, full_link):
                if full_link not in visited:
                    queue.append((full_link, depth + 1))

        time.sleep(1)

    return list(urls)


# =============================
# MAIN PIPELINE
# =============================
def process_site(site):
    print("\n====================")
    print(f"Site: {site}")

    sitemap_urls, sitemap_sources = extract_sitemap_urls(site)

    if len(sitemap_sources) > 0:
        print(f"✔ Sitemap detected ({len(sitemap_sources)} sources)")
        print(f"✔ Extracted {len(sitemap_urls)} URLs")

    if sitemap_urls:
        return sitemap_urls, "sitemap"
    else:
        print("✖ No usable sitemap → fallback crawl")
        crawl_urls = crawl_site(site, max_depth=1)
        return crawl_urls, "crawl"


# =============================
# RUN
# =============================
df = pd.read_csv(r"D:\datasets\ruoubia-thuocla-sua\htmls\website.csv")
websites = list(set(df["Website"].dropna().tolist()))

all_data = []

for site in websites:
    urls, source = process_site(site)

    for u in urls:
        if u:
            all_data.append({
                "website": site,
                "url": u,
                "source": source
            })


# =============================
# SAVE
# =============================
output_df = pd.DataFrame(all_data)
output_df.to_csv("site_structure.csv", index=False)

print("\n✅ Done! Saved to site_structure.csv")