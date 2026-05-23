from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from bs4 import BeautifulSoup
from fastapi import HTTPException
from pydantic import BaseModel


def model_dump(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def safe_rule_domain(domain: str) -> str:
    safe_domain = domain.strip().lower()
    if not re.fullmatch(r"[a-z0-9.-]+", safe_domain):
        raise HTTPException(status_code=400, detail="Invalid rule domain")
    return safe_domain


def json_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def field_preview(html: str | None, fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not html:
        return [{**field, "matches": 0, "sample": None} for field in fields]

    soup = BeautifulSoup(html, "lxml")
    preview = []
    for field in fields:
        selector = field.get("selector") or ""
        elements = []
        if selector:
            try:
                elements = soup.select(selector)
            except Exception:
                elements = []
        sample = None
        if elements:
            attr = field.get("attr")
            sample = elements[0].get(attr) if attr else elements[0].get_text(" ", strip=True)
        preview.append({
            **field,
            "matches": len(elements),
            "sample": str(sample)[:240] if sample else None,
        })
    return preview


def normalize_product_name(value: str) -> str:
    normalized = re.sub(r"[^\w]+", " ", value.lower(), flags=re.UNICODE)
    return " ".join(normalized.split())


def dedup_candidate_id(left: dict[str, Any], right: dict[str, Any]) -> str:
    key = "|".join(sorted([
        f"{left.get('source')}:{left.get('url') or left.get('name')}",
        f"{right.get('source')}:{right.get('url') or right.get('name')}",
    ]))
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def source_group(category: str | None) -> str:
    cat = (category or "").lower()
    if any(k in cat for k in ["ruou", "rượu", "bia", "vang"]):
        return "Rượu bia"
    if any(k in cat for k in ["thuoc la", "thuốc lá", "xì gà", "cigar", "cigarette"]):
        return "Thuốc lá"
    if any(k in cat for k in ["sua", "sữa"]):
        return "Sữa"
    return "Khác"
