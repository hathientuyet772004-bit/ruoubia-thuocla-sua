from __future__ import annotations

import hashlib
import statistics
import re
from typing import Any
from urllib.parse import urlparse

from apps.admin_center.backend import extraction_writer


REQUIRED_FIELDS = {
    "listing": {"product_name", "product_url", "price"},
    "product_detail": {"product_name", "price"},
}
STORE_FIELDS = {"store_name", "store_address", "store_url", "store_phone"}
OPTIONAL_QUALITY_FIELDS = {"brand", "store_name", "store_url", "store_address", "store_phone"}
MIN_LISTING_SAMPLES = 2
MIN_DETAIL_SAMPLES = 3
MIN_PROMOTION_SCORE = 0.72
RULE_GENERATION_VERSION = "gemini-evidence-v2"
PRICE_RULES = {
    "Sữa": {"unit_min": 3_000, "unit_max": 2_500_000},
    "Bia": {"unit_min": 8_000, "unit_max": 5_000_000},
    "Rượu": {"unit_min": 20_000, "unit_max": 500_000_000},
    "Thuốc lá": {"unit_min": 10_000, "unit_max": 10_000_000},
    "Khác": {"unit_min": 100, "unit_max": 10_000_000_000},
}


def validation_content_hash(samples: list[tuple[dict[str, Any], str]]) -> str:
    """Fingerprint the validation evidence so unchanged pages reuse AI work."""
    digest = hashlib.sha256()
    digest.update(RULE_GENERATION_VERSION.encode("utf-8"))
    digest.update(b"\0")
    for artifact, html in samples:
        digest.update(str(artifact.get("url") or "").encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(artifact.get("page_type") or "").encode("utf-8"))
        digest.update(b"\0")
        digest.update(" ".join((html or "").split()).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:24]


def enforce_contract(structure: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(structure)
    for target, required_names in REQUIRED_FIELDS.items():
        section = normalized.get(target)
        if not isinstance(section, dict):
            continue
        fields = []
        for field in section.get("fields") or []:
            if not isinstance(field, dict):
                continue
            item = dict(field)
            item["required"] = str(item.get("name") or "") in required_names
            fields.append(item)
        section = dict(section)
        section["fields"] = fields
        normalized[target] = section
    stores = normalized.get("stores")
    if isinstance(stores, dict):
        section = dict(stores)
        section["fields"] = [{**field, "required": False} for field in stores.get("fields") or [] if isinstance(field, dict)]
        normalized["stores"] = section
    return normalized


def classify_artifact(artifact: dict[str, Any]) -> str:
    url = str(artifact.get("url") or "").lower()
    if "listcategory" in url:
        return "unknown"
    path = urlparse(url).path.rstrip("/")
    if any(token in path for token in ("/store-locator", "/stores", "/store", "/branches", "/he-thong-cua-hang", "/cua-hang")):
        return "store_listing"
    if any(token in path for token in ("/category/", "/collection/", "/collections/", "/danh-muc/", "/search", "/brand/")):
        return "listing"
    if path.endswith((".html", ".htm")) and path.count("/") >= 3 and not any(token in path for token in ("/product/", "/san-pham/")):
        return "listing"
    page_type = str(artifact.get("page_type") or "").lower()
    if any(token in page_type for token in ("listing", "category", "collection", "search")):
        return "listing"
    if any(token in page_type for token in ("detail", "product_detail")):
        return "product_detail"

    if "/product/" in path or path.endswith((".html", ".htm")):
        return "product_detail"
    if any(token in path for token in ("/category/", "/collection/", "/danh-muc/", "/search")):
        return "listing"
    if re.search(r"/(?:products|san-pham)(?:/[^/.]+)?$", path):
        return "listing"
    return "unknown"


def select_validation_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stores = [item for item in artifacts if classify_artifact(item) == "store_listing"][:3]
    listing = [item for item in artifacts if classify_artifact(item) == "listing"][:3]
    detail = [item for item in artifacts if classify_artifact(item) == "product_detail"][:5]
    unknown = [item for item in artifacts if classify_artifact(item) == "unknown"]
    while len(listing) < MIN_LISTING_SAMPLES and unknown:
        listing.append(unknown.pop(0))
    while len(detail) < MIN_DETAIL_SAMPLES and unknown:
        detail.append(unknown.pop(0))
    return stores + listing + detail


def _valid_name(value: Any) -> bool:
    text = extraction_writer.clean_text(value)
    lowered = text.lower()
    return bool(
        3 <= len(text) <= 300
        and not extraction_writer.is_url_like(text)
        and lowered not in {"sản phẩm", "san pham", "menu", "trang chủ", "home", "breadcrumb"}
    )


def _valid_product_url(value: Any, domain: str) -> bool:
    text = extraction_writer.clean_text(value)
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    return parsed.netloc.removeprefix("www.") == domain.removeprefix("www.") and parsed.path not in {"", "/"}


def infer_volume_ml(*values: Any) -> int | None:
    text = " ".join(extraction_writer.clean_text(value).lower() for value in values if value)
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(ml|l|lit|liter|lít)", text, re.IGNORECASE)
    if not match:
        return None
    amount = float(match.group(1).replace(",", "."))
    return int(amount * 1000) if match.group(2).lower() in {"l", "lit", "liter", "lít"} else int(amount)


def infer_package_count(*values: Any) -> int:
    text = " ".join(extraction_writer.clean_text(value).lower() for value in values if value)
    patterns = [
        r"(?:thùng|hộp|lốc|pack|case)\s*(\d{1,3})",
        r"(\d{1,3})\s*(?:chai|lon|hộp|goi|gói)\b",
        r"x\s*(\d{1,3})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = int(match.group(1))
            return max(1, min(value, 500))
    return 1


def category_price_bounds(row: dict[str, Any], domain: str) -> tuple[int, int]:
    name = row.get("product_name") or row.get("name")
    category = extraction_writer.normalize_category(row.get("category"), name, row.get("product_url"), domain)
    rule = PRICE_RULES.get(category, PRICE_RULES["Khác"])
    package_count = infer_package_count(name, row.get("raw_data"))
    volume_ml = infer_volume_ml(name, row.get("volume_ml"))
    factor = package_count
    if volume_ml:
        if category in {"Rượu", "Bia"}:
            factor *= max(0.15, min(volume_ml / 750, 4))
        elif category == "Sữa":
            factor *= max(0.1, min(volume_ml / 1000, 10))
    return int(rule["unit_min"] * factor), int(rule["unit_max"] * factor)


def _row_validity(row: dict[str, Any], domain: str, target: str) -> dict[str, bool]:
    price = extraction_writer.clean_price(row.get("price"))
    old_price = extraction_writer.clean_price(row.get("old_price"))
    min_price, max_price = category_price_bounds(row, domain)
    checks = {
        "product_name": _valid_name(row.get("product_name")),
        "price": bool(price and min_price <= price <= max_price),
        "product_url": _valid_product_url(row.get("product_url"), domain),
        "old_price": old_price is None or price is None or old_price >= price,
    }
    if target == "product_detail":
        checks["product_url"] = True
    return checks


def validate_candidate(
    structure: dict[str, Any],
    samples: list[tuple[dict[str, Any], str]],
    domain: str,
) -> dict[str, Any]:
    structure = enforce_contract(structure)
    target_results: dict[str, Any] = {}
    all_rows: list[dict[str, Any]] = []
    required_passes = 0
    required_total = 0

    for target in ("listing", "product_detail"):
        section = structure.get(target)
        if not isinstance(section, dict) or not section.get("fields"):
            continue
        target_samples = [
            (artifact, html)
            for artifact, html in samples
            if classify_artifact(artifact) == target
        ]
        if not target_samples:
            target_samples = [
                (artifact, html)
                for artifact, html in samples
                if classify_artifact(artifact) == "unknown"
            ]
        sample_results = []
        target_rows: list[dict[str, Any]] = []
        for artifact, html in target_samples:
            rows = extraction_writer.extract_rows(html, section, artifact.get("url"))
            valid_rows = []
            for row in rows:
                checks = _row_validity(row, domain, target)
                if all(checks.get(name, False) for name in REQUIRED_FIELDS[target]):
                    valid_rows.append(row)
                required_passes += sum(1 for name in REQUIRED_FIELDS[target] if checks.get(name, False))
                required_total += len(REQUIRED_FIELDS[target])
            target_rows.extend(valid_rows)
            sample_results.append({
                "raw_page_id": artifact.get("id"),
                "page_type": classify_artifact(artifact),
                "row_count": len(rows),
                "valid_row_count": len(valid_rows),
                "coverage": round(len(valid_rows) / len(rows), 3) if rows else 0.0,
            })

        unique_products = {
            extraction_writer.clean_text(row.get("product_url") or row.get("product_name")).lower()
            for row in target_rows
            if row.get("product_url") or row.get("product_name")
        }
        field_coverage = {
            field: round(sum(1 for row in target_rows if row.get(field) not in (None, "")) / len(target_rows), 3)
            if target_rows else 0.0
            for field in REQUIRED_FIELDS[target] | OPTIONAL_QUALITY_FIELDS
        }
        available_samples = sum(1 for item, _ in samples if classify_artifact(item) == target)
        min_required = MIN_LISTING_SAMPLES if target == "listing" else MIN_DETAIL_SAMPLES
        min_samples = max(1, min(min_required, available_samples))
        enough_samples = len(target_samples) >= min_samples
        enough_rows = len(unique_products) >= (2 if target == "listing" else 1)
        sample_success = (
            sum(1 for item in sample_results if item["valid_row_count"] > 0) / len(sample_results)
            if sample_results else 0.0
        )
        passed = (
            enough_samples
            and enough_rows
            and sample_success >= 0.8
            and all(field_coverage[name] >= 0.8 for name in REQUIRED_FIELDS[target])
        )
        target_results[target] = {
            "passed": passed,
            "sample_count": len(target_samples),
            "minimum_samples": min_samples,
            "valid_rows": len(target_rows),
            "unique_products": len(unique_products),
            "field_coverage": field_coverage,
            "sample_success": round(sample_success, 3),
            "samples": sample_results,
        }
        all_rows.extend(target_rows)

    stores_section = structure.get("stores")
    store_rows: list[dict[str, Any]] = []
    if isinstance(stores_section, dict) and stores_section.get("fields"):
        target_samples = [
            (artifact, html)
            for artifact, html in samples
            if classify_artifact(artifact) == "store_listing"
        ]
        if not target_samples and not target_results:
            target_samples = [
                (artifact, html)
                for artifact, html in samples
                if classify_artifact(artifact) == "unknown"
            ]
        sample_results = []
        for artifact, html in target_samples:
            rows = extraction_writer.extract_rows(html, stores_section, artifact.get("url"))
            valid_rows = [
                row for row in rows
                if extraction_writer.clean_text(row.get("store_address"))
                and any(extraction_writer.clean_text(row.get(name)) for name in ("store_name", "store_url", "store_phone"))
            ]
            store_rows.extend(valid_rows)
            sample_results.append({
                "raw_page_id": artifact.get("id"),
                "page_type": classify_artifact(artifact),
                "row_count": len(rows),
                "valid_row_count": len(valid_rows),
                "coverage": round(len(valid_rows) / len(rows), 3) if rows else 0.0,
            })
        unique_stores = {
            extraction_writer.clean_text(row.get("store_address") or row.get("store_url") or row.get("store_name")).lower()
            for row in store_rows
            if row.get("store_address") or row.get("store_url") or row.get("store_name")
        }
        field_coverage = {
            field: round(sum(1 for row in store_rows if row.get(field) not in (None, "")) / len(store_rows), 3)
            if store_rows else 0.0
            for field in STORE_FIELDS
        }
        sample_success = (
            sum(1 for item in sample_results if item["valid_row_count"] > 0) / len(sample_results)
            if sample_results else 0.0
        )
        passed = bool(target_samples and unique_stores and sample_success >= 0.8 and field_coverage["store_address"] >= 0.8)
        target_results["stores"] = {
            "passed": passed,
            "sample_count": len(target_samples),
            "minimum_samples": 1,
            "valid_rows": len(store_rows),
            "unique_stores": len(unique_stores),
            "field_coverage": field_coverage,
            "sample_success": round(sample_success, 3),
            "samples": sample_results,
        }

    if store_rows and not all_rows:
        store_coverage = (target_results.get("stores") or {}).get("field_coverage") or {}
        coverage_score = float(store_coverage.get("store_address") or 0)
        diversity_score = min(1.0, len({
            extraction_writer.clean_text(row.get("store_address") or row.get("store_url") or row.get("store_name")).lower()
            for row in store_rows
        }) / 5)
        score = round(coverage_score * 0.75 + diversity_score * 0.25, 3)
        accepted = bool(target_results.get("stores", {}).get("passed") and score >= MIN_PROMOTION_SCORE)
        return {
            "accepted": accepted,
            "score": score,
            "threshold": MIN_PROMOTION_SCORE,
            "targets": target_results,
            "metrics": {
                "valid_products": 0,
                "valid_stores": len(store_rows),
                "required_coverage": round(coverage_score, 3),
                "brand_coverage": 0.0,
                "duplicate_ratio": round(1 - diversity_score, 3),
                "median_price": None,
            },
        }

    coverage_score = required_passes / required_total if required_total else 0.0
    diversity_score = min(1.0, len({
        extraction_writer.clean_text(row.get("product_url") or row.get("product_name")).lower()
        for row in all_rows
    }) / 5)
    old_price_checks = [
        _row_validity(row, domain, "listing")["old_price"]
        for row in all_rows
        if row.get("old_price") not in (None, "")
    ]
    consistency_score = sum(old_price_checks) / len(old_price_checks) if old_price_checks else 1.0
    score = round(coverage_score * 0.65 + diversity_score * 0.25 + consistency_score * 0.10, 3)
    product_targets = {key: value for key, value in target_results.items() if key in REQUIRED_FIELDS}
    accepted = bool(product_targets and all(item["passed"] for item in product_targets.values()) and score >= MIN_PROMOTION_SCORE)
    prices = [extraction_writer.clean_price(row.get("price")) for row in all_rows]
    prices = [price for price in prices if price]
    return {
        "accepted": accepted,
        "score": score,
        "threshold": MIN_PROMOTION_SCORE,
        "targets": target_results,
        "metrics": {
            "valid_products": len(all_rows),
            "required_coverage": round(coverage_score, 3),
            "brand_coverage": round(sum(1 for row in all_rows if row.get("brand")) / len(all_rows), 3) if all_rows else 0.0,
            "duplicate_ratio": round(1 - diversity_score, 3),
            "median_price": statistics.median(prices) if prices else None,
        },
    }


def validate_active_rule(
    structure: dict[str, Any],
    samples: list[tuple[dict[str, Any], str]],
    domain: str,
) -> dict[str, Any]:
    """Validate active rules only against target types present in this crawl batch."""
    available_targets = {
        classify_artifact(artifact)
        for artifact, _html in samples
        if classify_artifact(artifact) in (set(REQUIRED_FIELDS) | {"store_listing"})
    }
    if "store_listing" in available_targets:
        available_targets.remove("store_listing")
        available_targets.add("stores")
    if not available_targets:
        available_targets = {
            target
            for target in set(REQUIRED_FIELDS) | {"stores"}
            if isinstance(structure.get(target), dict) and (structure.get(target) or {}).get("fields")
        }
    filtered = dict(structure)
    for target in set(REQUIRED_FIELDS) | {"stores"}:
        if target not in available_targets:
            filtered.pop(target, None)
    return validate_candidate(filtered, samples, domain)


def drift_warnings(current: dict[str, Any] | None, previous: dict[str, Any] | None) -> list[str]:
    if not previous:
        return []
    current = current or {}
    warnings = []
    previous_count = int(previous.get("valid_products") or 0)
    current_count = int(current.get("valid_products") or 0)
    if previous_count >= 5 and current_count < previous_count * 0.5:
        warnings.append(f"product count dropped from {previous_count} to {current_count}")
    for field in ("required_coverage", "brand_coverage"):
        old = float(previous.get(field) or 0)
        new = float(current.get(field) or 0)
        if old >= 0.5 and new < old - 0.3:
            warnings.append(f"{field} dropped from {old:.2f} to {new:.2f}")
    old_price = previous.get("median_price")
    new_price = current.get("median_price")
    if old_price and new_price and abs(new_price - old_price) / old_price > 0.6:
        warnings.append("median price changed by more than 60%")
    if float(current.get("duplicate_ratio") or 0) > 0.5:
        warnings.append("duplicate ratio exceeded 50%")
    return warnings
