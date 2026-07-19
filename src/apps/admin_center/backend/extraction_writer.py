from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from apps.admin_center.backend import dependencies as deps
from apps.admin_center.backend.pg_store import now_utc


URL_RE = re.compile(r"^https?://", re.IGNORECASE)
PRODUCT_NAME_FIELDS = ("product_name", "name", "title")
PRICE_FIELDS = ("price", "price_numeric", "sale_price")
OLD_PRICE_FIELDS = ("old_price", "original_price", "list_price")
PRODUCT_URL_FIELDS = ("product_url", "url", "href")
IMAGE_FIELDS = ("image_url", "image", "thumbnail")
STORE_NAME_FIELDS = ("store_name", "branch_name", "name")
STORE_ADDRESS_FIELDS = ("store_address", "address")
STORE_PHONE_FIELDS = ("store_phone", "phone")
STORE_URL_FIELDS = ("store_url", "url", "href")
PHONE_RE = re.compile(r"(?:\+?84|0)(?:[\s.\-]?\d){8,10}")


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def clean_price(value: Any) -> float | None:
    if isinstance(value, (Decimal, int, float)):
        return float(value)
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"\d[\d.,\s]*", text)
    digits = re.sub(r"[^\d]", "", match.group(0) if match else text)
    if not digits:
        return None
    try:
        return float(digits)
    except ValueError:
        return None


def is_url_like(value: Any) -> bool:
    return bool(URL_RE.match(clean_text(value)))


def name_from_url(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    path = re.sub(r"[?#].*$", "", text).rstrip("/").split("/")[-1]
    path = re.sub(r"\.(html?|php|aspx?)$", "", path, flags=re.IGNORECASE)
    path = re.sub(r"[-_]+", " ", path)
    path = re.sub(r"\b(sp|sku|id|vk)\d+\b", "", path, flags=re.IGNORECASE)
    return clean_text(path).title()


def normalize_category(*values: Any) -> str:
    haystack = " ".join(clean_text(value).lower() for value in values if value)
    rules = [
        ("Rượu", ("ruou", "rượu", "vodka", "whisky", "whiskey", "wine", "soju", "cognac", "rum", "gin", "tequila", "brandy", "liqueur")),
        ("Bia", ("bia", "beer", "lager", "ale", "stout")),
        ("Thuốc lá", ("thuoc la", "thuốc lá", "cigarette", "cigar", "tobacco")),
        ("Sữa", ("sua", "sữa", "milk", "vinamilk", "th true milk", "moc chau milk", "dutch lady")),
    ]
    for label, keywords in rules:
        if any(keyword in haystack for keyword in keywords):
            return label
    return "Khác"


def normalize_store_address(value: Any) -> str:
    address = clean_text(value)
    return address or ""


def address_status(value: Any, channel: str | None = None) -> str:
    if clean_text(value):
        return "FOUND"
    if channel == "online":
        return "NOT_APPLICABLE"
    return "MISSING"


def stable_id(*parts: Any) -> str:
    raw = "|".join(clean_text(part) for part in parts if clean_text(part))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def first_value(row: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return value
    return None


def price_status(value: Any, numeric: float | None) -> str:
    text = clean_text(value).lower()
    if numeric and numeric > 0:
        return "FOUND"
    if any(token in text for token in ("liên hệ", "lien he", "call", "contact")):
        return "CONTACT"
    return "MISSING"


def resolve_url(value: Any, base_url: str | None = None) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if base_url:
        return urljoin(base_url, text)
    return text


def extract_field(scope: Any, field: dict[str, Any], base_url: str | None = None) -> Any:
    selector = field.get("selector") or ""
    if not selector:
        return None
    try:
        element = scope.select_one(selector)
    except Exception:
        return None
    if element is None:
        return None
    attr = field.get("attr")
    value = element.get(attr) if attr else element.get_text(" ", strip=True)
    if value is None and attr == "data-src":
        value = element.get("src")
    if value is None:
        return None
    value = clean_text(value)
    transform = field.get("transform")
    name = field.get("name")
    if attr in {"href", "src"} or name in PRODUCT_URL_FIELDS + IMAGE_FIELDS + STORE_URL_FIELDS:
        value = urljoin(base_url or "", value)
    if transform == "clean_price" or name in PRICE_FIELDS + OLD_PRICE_FIELDS:
        return clean_price(value)
    if transform == "extract_percentage":
        match = re.search(r"\d+(?:[.,]\d+)?\s*%", value)
        return match.group(0).replace(",", ".") if match else None
    if transform == "extract_volume_ml":
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*(ml|l|lit|liter|lít)", value, re.IGNORECASE)
        if not match:
            return None
        amount = float(match.group(1).replace(",", "."))
        unit = match.group(2).lower()
        return int(amount * 1000) if unit in {"l", "lit", "liter", "lít"} else int(amount)
    if transform == "check_for_sold_out_indicator":
        lowered = value.lower()
        if any(token in lowered for token in ("hết hàng", "sold out", "out of stock", "tạm hết")):
            return "OUT_OF_STOCK"
        if any(token in lowered for token in ("còn hàng", "in stock")):
            return "IN_STOCK"
        return None
    if transform == "extract_rating_from_html_attributes_or_classes":
        match = re.search(r"\d+(?:[.,]\d+)?", value)
        return float(match.group(0).replace(",", ".")) if match else None
    if transform == "extract_review_count_from_html_attributes_or_classes":
        match = re.search(r"\d+", value)
        return int(match.group(0)) if match else None
    return value


def extract_rows(html: str, section: dict[str, Any], base_url: str | None = None) -> list[dict[str, Any]]:
    fields = section.get("fields") if isinstance(section, dict) else []
    if not fields:
        return []
    soup = BeautifulSoup(html, "lxml")
    item_selector = section.get("item_selector") or section.get("container_selector")
    scopes = []
    if item_selector:
        try:
            scopes = soup.select(item_selector)
        except Exception:
            scopes = []
        if not scopes:
            return []
    if not scopes:
        scopes = [soup]

    rows = []
    for scope in scopes:
        row = {}
        field_sources = {}
        field_details = {}
        for field in fields:
            if not isinstance(field, dict):
                continue
            name = clean_text(field.get("name"))
            if not name:
                continue
            raw_value = None
            selector = field.get("selector") or ""
            if selector:
                try:
                    element = scope.select_one(selector)
                    if element is not None:
                        attr = field.get("attr")
                        raw_value = element.get(attr) if attr else element.get_text(" ", strip=True)
                except Exception:
                    raw_value = None
            row[name] = extract_field(scope, field, base_url)
            if row[name] not in (None, ""):
                field_sources[name] = "selector"
                field_details[name] = {
                    "source": "selector",
                    "selector": field.get("selector"),
                    "attr": field.get("attr"),
                    "transform": field.get("transform"),
                    "raw_value": clean_text(raw_value),
                    "normalized_value": row[name],
                }
        if field_sources:
            row["_field_sources"] = field_sources
            row["_field_details"] = field_details
        if any(value not in (None, "") for value in row.values()):
            rows.append(row)
    return rows


def fallback_structure(domain: str) -> dict[str, Any]:
    return {
        "domain": domain,
        "listing": {
            "item_selector": ".product_inner, .product, .product-item, .item-product, .product-box, .pro-item, .item_product",
            "fields": [
                {"name": "product_name", "selector": ".text_widget h3 a, .text_widget h3, .name, .title, .product-name, h3, h2", "required": True},
                {"name": "price", "selector": ".listed_price, .price, .product-price, .sale-price, [class*='price']", "transform": "clean_price"},
                {"name": "old_price", "selector": ".old-price, .compare-price, del, [class*='old']", "transform": "clean_price"},
                {"name": "product_url", "selector": "a", "attr": "href"},
                {"name": "image_url", "selector": "img[data-src], img", "attr": "data-src"},
            ],
        },
        "product_detail": {
            "fields": [
                {"name": "product_name", "selector": "h1, .product-title, .product-name", "required": True},
                {"name": "price", "selector": ".listed_price, .price, .product-price, .sale-price, [class*='price']", "transform": "clean_price"},
                {"name": "old_price", "selector": ".old-price, .compare-price, del, [class*='old']", "transform": "clean_price"},
            ],
        },
        "stores": {
            "item_selector": ".store, .branch, .location, [class*='store'], [class*='branch']",
            "fields": [
                {"name": "store_name", "selector": ".name, .title, h3, h2, strong", "required": True},
                {"name": "store_address", "selector": ".address, [class*='address']"},
                {"name": "store_phone", "selector": ".phone, [href^='tel:'], [class*='phone']"},
                {"name": "store_url", "selector": "a", "attr": "href"},
            ],
        },
    }


def page_extraction_target(raw_page: dict[str, Any]) -> str | None:
    page_type = clean_text(raw_page.get("page_type")).lower()
    if any(token in page_type for token in ("listing", "category", "collection", "search")):
        return "listing"
    if any(token in page_type for token in ("detail", "product_detail")):
        return "product_detail"
    path = urlparse(clean_text(raw_page.get("url"))).path.lower().rstrip("/")
    if any(token in path for token in ("/category/", "/collection/", "/danh-muc/", "/search")):
        return "listing"
    if re.search(r"/(?:products|san-pham)(?:/[^/.]+)?$", path):
        return "listing"
    if "/product/" in path or path.endswith((".html", ".htm")):
        return "product_detail"
    return None


def jsonld_rows(html: str, base_url: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    soup = BeautifulSoup(html, "lxml")
    products: list[dict[str, Any]] = []
    stores: list[dict[str, Any]] = []

    def visit(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                visit(item)
            return
        if not isinstance(node, dict):
            return
        node_type = node.get("@type")
        types = node_type if isinstance(node_type, list) else [node_type]
        normalized_types = {clean_text(item).lower() for item in types}
        if "product" in normalized_types:
            offers = node.get("offers") if isinstance(node.get("offers"), dict) else {}
            products.append({
                "product_name": node.get("name"),
                "product_url": urljoin(base_url or "", node.get("url") or ""),
                "image_url": first_value({"image": node.get("image")}, ("image",)),
                "price": offers.get("price") or node.get("price"),
                "currency": offers.get("priceCurrency"),
                "brand": (node.get("brand") or {}).get("name") if isinstance(node.get("brand"), dict) else node.get("brand"),
                "_field_sources": {
                    "product_name": "jsonld",
                    "product_url": "jsonld",
                    "image_url": "jsonld",
                    "price": "jsonld",
                    "brand": "jsonld",
                },
            })
        if normalized_types & {"localbusiness", "store", "organization"}:
            address = node.get("address")
            if isinstance(address, dict):
                address = ", ".join(clean_text(address.get(key)) for key in ("streetAddress", "addressLocality", "addressRegion") if address.get(key))
            stores.append({
                "store_name": node.get("name"),
                "store_address": address,
                "store_phone": node.get("telephone"),
                "store_url": urljoin(base_url or "", node.get("url") or ""),
                "_field_sources": {
                    "store_name": "jsonld",
                    "store_address": "jsonld",
                    "store_phone": "jsonld",
                    "store_url": "jsonld",
                },
            })
        for key in ("@graph", "itemListElement", "mainEntity", "hasOfferCatalog"):
            visit(node.get(key))

    for script in soup.select("script[type='application/ld+json']"):
        try:
            visit(json.loads(script.string or script.get_text() or "{}"))
        except json.JSONDecodeError:
            continue
    return products, stores


def _meta_content(soup: BeautifulSoup, *keys: str) -> str:
    for key in keys:
        node = soup.select_one(f"meta[property='{key}'], meta[name='{key}']")
        if node and node.get("content"):
            return clean_text(node.get("content"))
    return ""


def _labeled_value(soup: BeautifulSoup, labels: tuple[str, ...]) -> str:
    for node in soup.select("th, dt, .label, .attribute-label"):
        text = clean_text(node.get_text(" ", strip=True)).lower()
        if not any(label in text for label in labels):
            continue
        sibling = node.find_next_sibling(["td", "dd", "span", "div"])
        if sibling:
            return clean_text(sibling.get_text(" ", strip=True))
    return ""


def page_context(html: str, base_url: str | None, domain: str) -> dict[str, Any]:
    """Extract site-level fields deterministically before applying AI selectors."""
    soup = BeautifulSoup(html, "lxml")
    jsonld_products, jsonld_stores = jsonld_rows(html, base_url)
    product = next((row for row in jsonld_products if row.get("brand")), {})
    store = next(
        (
            row
            for row in jsonld_stores
            if any(row.get(key) for key in ("store_name", "store_address", "store_phone"))
        ),
        {},
    )

    brand = clean_text(product.get("brand"))
    if not brand:
        brand_node = soup.select_one("[itemprop='brand'], meta[property='product:brand'], meta[name='brand']")
        if brand_node:
            brand = clean_text(brand_node.get("content") or brand_node.get_text(" ", strip=True))
    brand = brand or _labeled_value(soup, ("thương hiệu", "brand"))

    parsed = urlparse(base_url or "")
    origin = f"{parsed.scheme}://{parsed.netloc}/" if parsed.scheme and parsed.netloc else f"https://{domain}/"
    store_url = resolve_url(store.get("store_url"), origin)
    if not store_url:
        canonical = soup.select_one("link[rel='canonical']")
        store_url = resolve_url(canonical.get("href"), origin) if canonical else None
    if store_url and urlparse(store_url).path not in {"", "/"}:
        store_url = origin

    store_name = clean_text(store.get("store_name")) or _meta_content(soup, "og:site_name", "application-name")
    if not store_name:
        title = clean_text(soup.title.get_text(" ", strip=True) if soup.title else "")
        store_name = re.split(r"\s+[|\-–]\s+", title, maxsplit=1)[0]

    phone = clean_text(store.get("store_phone"))
    if not phone:
        tel = soup.select_one("a[href^='tel:'], [itemprop='telephone']")
        phone = clean_text((tel.get("href") or "").removeprefix("tel:") if tel else "")
    if not phone:
        footer_text = clean_text((soup.select_one("footer") or soup).get_text(" ", strip=True))
        match = PHONE_RE.search(footer_text)
        phone = clean_text(match.group(0)) if match else ""

    address = clean_text(store.get("store_address"))
    if not address:
        address_node = soup.select_one("address, [itemprop='address'], .store-address, .contact-address, .address")
        address = clean_text(address_node.get_text(" ", strip=True) if address_node else "")

    return {
        "brand": brand or None,
        "store_name": store_name or domain,
        "store_url": store_url or origin,
        "store_address": normalize_store_address(address),
        "store_phone": phone,
    }


def product_payload(row: dict[str, Any], *, domain: str, url: str | None, raw_page_id: str | None, source_id: str | None = None) -> dict[str, Any] | None:
    name = clean_text(first_value(row, PRODUCT_NAME_FIELDS))
    product_url = resolve_url(first_value(row, PRODUCT_URL_FIELDS), url) or url
    if is_url_like(name):
        product_url = resolve_url(name, url) or product_url
        name = name_from_url(name)
    if not name and product_url:
        name = name_from_url(product_url)
    price = first_value(row, PRICE_FIELDS)
    price_numeric = clean_price(price)
    if not name and not product_url:
        return None
    product_id = stable_id(domain, product_url or name)
    category = row.get("category") or row.get("normalized_category")
    normalized_category = normalize_category(category, name, product_url, domain)
    store_channel = row.get("store_channel")
    store_address = normalize_store_address(row.get("store_address"))
    return {
        "product_id": product_id,
        "product_name": name,
        "canonical_name": name,
        "product_url": product_url,
        "image_url": resolve_url(first_value(row, IMAGE_FIELDS), url),
        "price_numeric": price_numeric,
        "price": price_numeric,
        "price_status": price_status(price, price_numeric),
        "old_price": clean_price(first_value(row, OLD_PRICE_FIELDS)),
        "currency": row.get("currency") or "VND",
        "brand": row.get("brand"),
        "category": normalized_category,
        "normalized_category": normalized_category,
        "store_name": row.get("store_name"),
        "store_url": row.get("store_url"),
        "store_address": store_address or None,
        "store_channel": store_channel,
        "address_status": address_status(store_address, store_channel),
        "store_phone": row.get("store_phone"),
        "domain": domain,
        "source_id": source_id,
        "raw_page_id": raw_page_id,
        "raw_data": {key: value for key, value in row.items() if key not in {"store_id", "_field_sources", "_field_details"}},
        "updated_at": now_utc(),
    }


def offer_payload(product: dict[str, Any]) -> dict[str, Any] | None:
    price = product.get("price_numeric")
    if not product.get("product_id") or not price:
        return None
    seller_key = stable_id(
        product.get("domain"),
        product.get("store_url"),
        product.get("store_name"),
        product.get("store_address"),
        product.get("store_phone"),
    )
    return {
        "offer_id": stable_id(product.get("product_id"), seller_key),
        "seller_key": seller_key,
        "product_id": product["product_id"],
        "product_name": product.get("product_name"),
        "product_url": product.get("product_url"),
        "price_numeric": price,
        "currency": product.get("currency") or "VND",
        "store_name": product.get("store_name"),
        "store_url": product.get("store_url"),
        "store_address": product.get("store_address"),
        "store_phone": product.get("store_phone"),
        "domain": product.get("domain"),
        "source_id": product.get("source_id"),
        "raw_page_id": product.get("raw_page_id"),
        "updated_at": now_utc(),
    }


def price_observation_payload(product: dict[str, Any]) -> dict[str, Any] | None:
    price = product.get("price_numeric")
    if not product.get("product_id") or not price:
        return None
    observed_at = now_utc()
    return {
        "observation_id": stable_id(
            product.get("product_id"),
            product.get("raw_page_id"),
            price,
            product.get("store_url"),
            product.get("store_name"),
        ),
        "product_id": product.get("product_id"),
        "price_numeric": price,
        "currency": product.get("currency") or "VND",
        "domain": product.get("domain"),
        "source_id": product.get("source_id"),
        "raw_page_id": product.get("raw_page_id"),
        "rule_version": product.get("rule_version"),
        "data_origin": product.get("data_origin"),
        "observed_at": observed_at,
    }


def store_payload(row: dict[str, Any], *, domain: str, url: str | None, raw_page_id: str | None, source_id: str | None = None) -> dict[str, Any] | None:
    name = clean_text(first_value(row, STORE_NAME_FIELDS))
    address = clean_text(first_value(row, STORE_ADDRESS_FIELDS))
    store_url = resolve_url(first_value(row, STORE_URL_FIELDS), url) or url
    if not any([name, address, store_url]):
        return None
    return {
        "store_name": name or store_url,
        "store_address": normalize_store_address(address) or None,
        "address_status": address_status(address, row.get("store_channel")),
        "store_channel": row.get("store_channel"),
        "store_phone": clean_text(first_value(row, STORE_PHONE_FIELDS)),
        "store_url": store_url,
        "domain": domain,
        "source_id": source_id,
        "raw_page_id": raw_page_id,
        "raw_data": row,
        "updated_at": now_utc(),
    }


def _persist_rows(
    *,
    db: Any,
    domain: str,
    url: str | None,
    raw_page_id: str | None,
    source_id: str | None,
    product_rows: list[dict[str, Any]],
    store_rows: list[dict[str, Any]],
    source_config: dict[str, Any] | None = None,
    rule_version: str | None = None,
    extraction_method: str = "rule",
    model: str | None = None,
    validation_score: float | None = None,
    content_hash: str | None = None,
    quality_gate_enabled: bool = False,
    previous_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    products_written = 0
    offers_written = 0
    warnings = []
    store_payloads = []
    persisted_products: list[dict[str, Any]] = []

    for row in store_rows:
        payload = store_payload(row, domain=domain, url=url, raw_page_id=raw_page_id, source_id=source_id)
        if not payload:
            continue
        store_payloads.append(payload)

    source_config = source_config or {}
    store_scope = str(source_config.get("store_scope") or "site").lower()
    configured_store = {
        "store_name": source_config.get("store_name"),
        "store_url": source_config.get("store_url"),
        "store_address": source_config.get("store_address"),
        "store_phone": source_config.get("store_phone"),
        "store_channel": source_config.get("store_channel"),
    }
    primary_store = configured_store if store_scope == "site" and any(configured_store.values()) else (store_payloads[0] if store_scope == "site" and store_payloads else None)

    for row in product_rows:
        enriched_row = dict(row)
        if primary_store and store_scope == "site":
            for key in ("store_name", "store_url", "store_address", "store_phone"):
                if enriched_row.get(key) in (None, ""):
                    enriched_row[key] = primary_store.get(key)
                    enriched_row.setdefault("_field_sources", {})[key] = "source_config" if configured_store.get(key) else "site_metadata"
            if enriched_row.get("store_channel") in (None, ""):
                enriched_row["store_channel"] = primary_store.get("store_channel")
        payload = product_payload(enriched_row, domain=domain, url=url, raw_page_id=raw_page_id, source_id=source_id)
        if not payload:
            continue
        payload.update({
            "data_origin": "crawled" if extraction_method == "rule" else "ai_extracted",
            "evidence_id": raw_page_id,
            "rule_version": rule_version,
            "extraction_method": extraction_method,
            "model": model,
            "content_hash": content_hash,
            "field_sources": {
                key: (enriched_row.get("_field_sources") or {}).get(key, extraction_method)
                for key, value in payload.items()
                if value not in (None, "") and key in {"product_name", "price", "brand", "product_url", "store_name", "store_url", "store_address", "store_phone"}
            },
            "field_details": {
                key: (enriched_row.get("_field_details") or {}).get(key)
                for key, value in payload.items()
                if value not in (None, "") and key in {"product_name", "price", "brand", "product_url", "store_name", "store_url", "store_address", "store_phone"}
            },
            "validation_score": validation_score,
        })
        persisted_products.append(payload)

    product_ids = [str(item.get("product_id") or "") for item in persisted_products if item.get("product_id")]
    prices = [float(item["price_numeric"]) for item in persisted_products if item.get("price_numeric")]
    complete = [
        item for item in persisted_products
        if item.get("product_name") and item.get("product_url") and item.get("price_numeric")
    ]
    metrics = {
        "valid_products": len(persisted_products),
        "required_coverage": round(len(complete) / len(persisted_products), 3) if persisted_products else 0.0,
        "brand_coverage": round(sum(1 for item in persisted_products if item.get("brand")) / len(persisted_products), 3) if persisted_products else 0.0,
        "duplicate_ratio": round(1 - (len(set(product_ids)) / len(product_ids)), 3) if product_ids else 0.0,
        "median_price": sorted(prices)[len(prices) // 2] if prices else None,
    }
    gate_reasons = quality_gate_reasons(metrics, previous_metrics)
    if quality_gate_enabled and gate_reasons:
        if persisted_products:
            db.sc_product_quarantine.insert_many([
                {
                    "domain": domain,
                    "source_id": source_id,
                    "raw_page_id": raw_page_id,
                    "reason": reason,
                    "payload": payload,
                    "metrics": metrics,
                    "previous_metrics": previous_metrics,
                    "created_at": now_utc(),
                }
                for payload in persisted_products
                for reason in gate_reasons[:1]
            ])
        warnings.extend(f"quality gate blocked write: {reason}" for reason in gate_reasons)
        return {"products": 0, "offers": 0, "stores": len(store_payloads), "warnings": warnings, "metrics": metrics, "quarantined": len(persisted_products)}

    for payload in persisted_products:
        db.sc_products.update_one(
            {"product_id": payload["product_id"]},
            {
                "$set": payload,
                "$unset": {"store_id": ""},
                "$setOnInsert": {"created_at": now_utc()},
            },
            upsert=True,
        )
        products_written += 1
        offer = offer_payload(payload)
        if offer:
            db.sc_offers.update_one(
                {"offer_id": offer["offer_id"]},
                {
                    "$set": offer,
                    "$unset": {"store_id": ""},
                    "$setOnInsert": {"created_at": now_utc()},
                },
                upsert=True,
            )
            offers_written += 1
        observation = price_observation_payload(payload)
        if observation:
            db.sc_price_observations.update_one(
                {"observation_id": observation["observation_id"]},
                {"$set": observation, "$setOnInsert": {"created_at": now_utc()}},
                upsert=True,
            )

    if not products_written and product_rows:
        warnings.append("product rows were extracted but did not include name or URL")
    if not store_payloads and store_rows:
        warnings.append("store rows were extracted but did not include name, address, or URL")
    return {
        "products": products_written,
        "offers": offers_written,
        "stores": len(store_payloads),
        "warnings": warnings,
        "metrics": metrics,
    }


def quality_gate_reasons(metrics: dict[str, Any], previous_metrics: dict[str, Any] | None) -> list[str]:
    reasons = []
    if float(metrics.get("required_coverage") or 0) < 0.65:
        reasons.append("required coverage below 65%")
    if not previous_metrics:
        return reasons
    old_count = int(previous_metrics.get("valid_products") or 0)
    new_count = int(metrics.get("valid_products") or 0)
    if old_count >= 5 and new_count < old_count * 0.3:
        reasons.append(f"product count dropped more than 70% ({old_count} -> {new_count})")
    old_price = previous_metrics.get("median_price")
    new_price = metrics.get("median_price")
    if old_price and new_price and abs(float(new_price) - float(old_price)) / float(old_price) > 0.8:
        reasons.append("median price changed more than 80%")
    return reasons


def write_extraction(
    raw_page: dict[str, Any],
    html: str,
    structure: dict[str, Any],
    source_id: str | None = None,
    *,
    source_config: dict[str, Any] | None = None,
    rule_version: str | None = None,
    extraction_method: str = "rule",
    model: str | None = None,
    validation_score: float | None = None,
    previous_metrics: dict[str, Any] | None = None,
    allowed_targets: set[str] | None = None,
    allow_generic_fallback: bool = True,
) -> dict[str, Any]:
    db = deps.data_store.get_db()
    if db is None or not html:
        return {"products": 0, "offers": 0, "stores": 0, "warnings": ["writer skipped: missing db or html"]}

    domain = raw_page.get("domain") or structure.get("domain") or "unknown"
    url = raw_page.get("url")
    raw_page_id = raw_page.get("id") or raw_page.get("raw_page_id")
    content_hash = hashlib.sha256(html.encode("utf-8", errors="ignore")).hexdigest()[:16]
    configured_targets = {
        target
        for target in ("listing", "product_detail")
        if isinstance(structure.get(target), dict) and (structure.get(target) or {}).get("fields")
    }
    permitted_targets = configured_targets if allowed_targets is None else configured_targets & set(allowed_targets)
    page_target = page_extraction_target(raw_page)
    selected_targets = {page_target} & permitted_targets if page_target else permitted_targets
    product_rows = []
    for target in ("listing", "product_detail"):
        if target not in selected_targets:
            continue
        section = structure.get(target) if isinstance(structure.get(target), dict) else {}
        product_rows.extend(extract_rows(html, section, url))

    store_rows = extract_rows(html, structure.get("stores") or {}, url)
    jsonld_product_rows, jsonld_store_rows = jsonld_rows(html, url)
    if selected_targets:
        product_rows.extend(jsonld_product_rows)
    store_rows.extend(jsonld_store_rows)
    context = page_context(html, url, domain)
    if not product_rows and allow_generic_fallback:
        fallback = fallback_structure(domain)
        if page_target != "product_detail":
            product_rows.extend(extract_rows(html, fallback["listing"], url))
        if not product_rows and page_target != "listing":
            product_rows.extend(extract_rows(html, fallback["product_detail"], url))
    if not store_rows and allow_generic_fallback:
        fallback = fallback_structure(domain)
        store_rows.extend(extract_rows(html, fallback["stores"], url))
    if not store_rows and allow_generic_fallback:
        store_rows.append({
            key: context.get(key)
            for key in ("store_name", "store_url", "store_address", "store_phone")
        })
    for row in product_rows:
        if context.get("brand") and row.get("brand") in (None, ""):
            row["brand"] = context["brand"]
            row.setdefault("_field_sources", {})["brand"] = "page_metadata"
    return _persist_rows(
        db=db,
        domain=domain,
        url=url,
        raw_page_id=raw_page_id,
        source_id=source_id,
        product_rows=product_rows,
        store_rows=store_rows,
        source_config=source_config,
        rule_version=rule_version,
        extraction_method=extraction_method,
        model=model,
        validation_score=validation_score,
        content_hash=content_hash,
        quality_gate_enabled=bool((source_config or {}).get("quality_gate_enabled", True)),
        previous_metrics=previous_metrics,
    )


def write_gemini_extraction(
    raw_page: dict[str, Any],
    records: list[dict[str, Any]],
    source_id: str | None = None,
    *,
    source_config: dict[str, Any] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    db = deps.data_store.get_db()
    if db is None or not records:
        return {"products": 0, "offers": 0, "stores": 0, "warnings": ["writer skipped: missing db or records"]}

    domain = raw_page.get("domain") or "unknown"
    url = raw_page.get("url")
    raw_page_id = raw_page.get("id") or raw_page.get("raw_page_id")
    product_rows: list[dict[str, Any]] = []
    store_rows: list[dict[str, Any]] = []
    for row in records:
        if not isinstance(row, dict):
            continue
        entity_type = clean_text(row.get("entity_type")).lower()
        if entity_type == "store":
            store_rows.append(row)
        else:
            product_rows.append(row)
    return _persist_rows(
        db=db,
        domain=domain,
        url=url,
        raw_page_id=raw_page_id,
        source_id=source_id,
        product_rows=product_rows,
        store_rows=store_rows,
        source_config=source_config,
        extraction_method="ai_extracted",
        model=model,
    )
