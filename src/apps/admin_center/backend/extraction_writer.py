from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from apps.admin_center.backend import dependencies as deps
from apps.admin_center.backend.mongo_store import now_utc


PRODUCT_NAME_FIELDS = ("product_name", "name", "title")
PRICE_FIELDS = ("price", "price_numeric", "sale_price")
OLD_PRICE_FIELDS = ("old_price", "original_price", "list_price")
PRODUCT_URL_FIELDS = ("product_url", "url", "href")
IMAGE_FIELDS = ("image_url", "image", "thumbnail")
STORE_NAME_FIELDS = ("store_name", "branch_name", "name")
STORE_ADDRESS_FIELDS = ("store_address", "address")
STORE_PHONE_FIELDS = ("store_phone", "phone")
STORE_URL_FIELDS = ("store_url", "url", "href")


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def clean_price(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    text = clean_text(value)
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return None
    try:
        return float(digits)
    except ValueError:
        return None


def stable_id(*parts: Any) -> str:
    raw = "|".join(clean_text(part) for part in parts if clean_text(part))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def first_value(row: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return value
    return None


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
    if value is None:
        return None
    value = clean_text(value)
    transform = field.get("transform")
    name = field.get("name")
    if attr in {"href", "src"} or name in PRODUCT_URL_FIELDS + IMAGE_FIELDS + STORE_URL_FIELDS:
        value = urljoin(base_url or "", value)
    if transform == "clean_price" or name in PRICE_FIELDS + OLD_PRICE_FIELDS:
        return clean_price(value)
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
        scopes = [soup]

    rows = []
    for scope in scopes:
        row = {}
        for field in fields:
            if not isinstance(field, dict):
                continue
            name = clean_text(field.get("name"))
            if not name:
                continue
            row[name] = extract_field(scope, field, base_url)
        if any(value not in (None, "") for value in row.values()):
            rows.append(row)
    return rows


def product_payload(row: dict[str, Any], *, domain: str, url: str | None, raw_page_id: str | None, source_id: str | None = None) -> dict[str, Any] | None:
    name = clean_text(first_value(row, PRODUCT_NAME_FIELDS))
    product_url = clean_text(first_value(row, PRODUCT_URL_FIELDS)) or url
    price = first_value(row, PRICE_FIELDS)
    if not name and not product_url:
        return None
    product_id = stable_id(domain, product_url or name)
    return {
        "product_id": product_id,
        "product_name": name or product_url,
        "canonical_name": name or product_url,
        "product_url": product_url,
        "image_url": first_value(row, IMAGE_FIELDS),
        "price_numeric": clean_price(price),
        "price": clean_price(price) or price,
        "old_price": clean_price(first_value(row, OLD_PRICE_FIELDS)),
        "currency": row.get("currency") or "VND",
        "brand": row.get("brand"),
        "category": row.get("category") or row.get("normalized_category") or "Khac",
        "domain": domain,
        "source_id": source_id,
        "raw_page_id": raw_page_id,
        "raw_data": row,
        "updated_at": now_utc(),
    }


def offer_payload(product: dict[str, Any]) -> dict[str, Any] | None:
    price = product.get("price_numeric")
    if not product.get("product_id") or not price:
        return None
    return {
        "offer_id": stable_id(product.get("product_id"), price, datetime.now().strftime("%Y-%m-%d")),
        "product_id": product["product_id"],
        "product_name": product.get("product_name"),
        "product_url": product.get("product_url"),
        "price_numeric": price,
        "currency": product.get("currency") or "VND",
        "domain": product.get("domain"),
        "source_id": product.get("source_id"),
        "raw_page_id": product.get("raw_page_id"),
        "updated_at": now_utc(),
    }


def store_payload(row: dict[str, Any], *, domain: str, url: str | None, raw_page_id: str | None, source_id: str | None = None) -> dict[str, Any] | None:
    name = clean_text(first_value(row, STORE_NAME_FIELDS))
    address = clean_text(first_value(row, STORE_ADDRESS_FIELDS))
    store_url = clean_text(first_value(row, STORE_URL_FIELDS)) or url
    if not any([name, address, store_url]):
        return None
    store_id = stable_id(domain, store_url or name, address)
    return {
        "store_id": store_id,
        "store_name": name or store_url,
        "store_address": address,
        "store_phone": clean_text(first_value(row, STORE_PHONE_FIELDS)),
        "store_url": store_url,
        "domain": domain,
        "source_id": source_id,
        "raw_page_id": raw_page_id,
        "raw_data": row,
        "updated_at": now_utc(),
    }


def write_extraction(raw_page: dict[str, Any], html: str, structure: dict[str, Any], source_id: str | None = None) -> dict[str, Any]:
    db = deps.mongo_store.get_db()
    if db is None or not html or not structure:
        return {"products": 0, "offers": 0, "stores": 0, "warnings": ["writer skipped: missing db, html, or structure"]}

    domain = raw_page.get("domain") or structure.get("domain") or "unknown"
    url = raw_page.get("url")
    raw_page_id = raw_page.get("id") or raw_page.get("raw_page_id")
    product_rows = []
    for target in ("listing", "product_detail"):
        section = structure.get(target) if isinstance(structure.get(target), dict) else {}
        product_rows.extend(extract_rows(html, section, url))

    store_rows = extract_rows(html, structure.get("stores") or {}, url)
    products_written = 0
    offers_written = 0
    stores_written = 0
    warnings = []

    for row in product_rows:
        payload = product_payload(row, domain=domain, url=url, raw_page_id=raw_page_id, source_id=source_id)
        if not payload:
            continue
        db.sc_products.update_one(
            {"product_id": payload["product_id"]},
            {"$set": payload, "$setOnInsert": {"created_at": now_utc()}},
            upsert=True,
        )
        products_written += 1
        offer = offer_payload(payload)
        if offer:
            db.sc_offers.update_one(
                {"offer_id": offer["offer_id"]},
                {"$set": offer, "$setOnInsert": {"created_at": now_utc()}},
                upsert=True,
            )
            offers_written += 1

    for row in store_rows:
        payload = store_payload(row, domain=domain, url=url, raw_page_id=raw_page_id, source_id=source_id)
        if not payload:
            continue
        db.sc_stores.update_one(
            {"store_id": payload["store_id"]},
            {"$set": payload, "$setOnInsert": {"created_at": now_utc()}},
            upsert=True,
        )
        stores_written += 1

    if not products_written and product_rows:
        warnings.append("product rows were extracted but did not include name or URL")
    if not stores_written and store_rows:
        warnings.append("store rows were extracted but did not include name, address, or URL")
    return {
        "products": products_written,
        "offers": offers_written,
        "stores": stores_written,
        "warnings": warnings,
    }
