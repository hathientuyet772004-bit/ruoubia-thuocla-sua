from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from apps.admin_center.backend import dependencies as deps
from apps.admin_center.backend.cache import product_cache


NOISE_WORDS = {
    "ruou", "bia", "sua", "thuoc", "la", "chai", "lon", "hop", "qua", "gift", "box",
    "chinh", "hang", "nhap", "khau", "cao", "cap", "khuyen", "mai", "sale", "new",
}
PACK_RE = re.compile(r"\b(?:thung|hop|pack|case)\s*(\d+)|\b(\d+)\s*(?:lon|chai|hop|goi)\b", re.IGNORECASE)
VOLUME_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(ml|l|lit|liter|cl)\b", re.IGNORECASE)
ABV_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:%|\bdo\b|\bđộ\b)", re.IGNORECASE)


@dataclass(frozen=True)
class CanonicalCandidate:
    product_id: str
    product_name: str
    category: str
    brand: str
    normalized_name: str
    name_core: str
    canonical_key: str
    volume_ml: int | None
    abv_percent: float | None
    pack_size: int | None


def normalize_text(value: Any) -> str:
    text = " ".join(str(value or "").lower().split())
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d")
    text = re.sub(r"[^a-z0-9.%\s]+", " ", text)
    return " ".join(text.split())


def extract_volume_ml(*values: Any) -> int | None:
    text = normalize_text(" ".join(str(value or "") for value in values))
    match = VOLUME_RE.search(text)
    if not match:
        return None
    amount = float(match.group(1).replace(",", "."))
    unit = match.group(2).lower()
    if unit in {"l", "lit", "liter"}:
        return int(amount * 1000)
    if unit == "cl":
        return int(amount * 10)
    return int(amount)


def extract_abv_percent(*values: Any) -> float | None:
    text = normalize_text(" ".join(str(value or "") for value in values))
    match = ABV_RE.search(text)
    return float(match.group(1).replace(",", ".")) if match else None


def extract_pack_size(*values: Any) -> int | None:
    text = normalize_text(" ".join(str(value or "") for value in values))
    match = PACK_RE.search(text)
    if not match:
        return None
    return int(next(group for group in match.groups() if group))


def name_core(value: Any, brand: Any = "") -> str:
    text = normalize_text(value)
    brand_text = normalize_text(brand)
    if brand_text:
        text = re.sub(rf"\b{re.escape(brand_text)}\b", " ", text)
    text = VOLUME_RE.sub(" ", text)
    text = ABV_RE.sub(" ", text)
    text = PACK_RE.sub(" ", text)
    tokens = [token for token in text.split() if token not in NOISE_WORDS]
    return " ".join(tokens)


def stable_id(*parts: Any) -> str:
    raw = "|".join(str(part or "") for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def candidate_from_row(row: dict[str, Any]) -> CanonicalCandidate:
    raw = row.get("raw_data") if isinstance(row.get("raw_data"), dict) else {}
    product_name = str(row.get("product_name") or row.get("canonical_name") or "")
    category = normalize_text(row.get("normalized_category") or row.get("category") or "")
    brand = normalize_text(row.get("brand") or raw.get("brand") or "")
    volume_ml = extract_volume_ml(product_name, raw.get("volume"), raw.get("volume_ml"))
    abv_percent = extract_abv_percent(product_name, raw.get("percentage"), raw.get("abv_percent"))
    pack_size = extract_pack_size(product_name, raw.get("pack_size"))
    core = name_core(product_name, brand)
    normalized_name = normalize_text(product_name)
    key_parts = [
        category or "khac",
        brand or "unknown-brand",
        core,
        f"{volume_ml}ml" if volume_ml else "",
        f"{abv_percent:g}pct" if abv_percent else "",
        f"pack{pack_size}" if pack_size else "",
    ]
    canonical_key = "|".join(part for part in key_parts if part)
    return CanonicalCandidate(
        product_id=str(row.get("product_id") or ""),
        product_name=product_name,
        category=category,
        brand=brand,
        normalized_name=normalized_name,
        name_core=core,
        canonical_key=canonical_key,
        volume_ml=volume_ml,
        abv_percent=abv_percent,
        pack_size=pack_size,
    )


def match_score(left: CanonicalCandidate, right: CanonicalCandidate) -> float:
    if left.category and right.category and left.category != right.category:
        return 0.0
    if left.volume_ml and right.volume_ml and left.volume_ml != right.volume_ml:
        return 0.0
    if left.abv_percent and right.abv_percent and abs(left.abv_percent - right.abv_percent) > 0.25:
        return 0.0
    if left.pack_size and right.pack_size and left.pack_size != right.pack_size:
        return 0.0

    name_similarity = SequenceMatcher(None, left.name_core or left.normalized_name, right.name_core or right.normalized_name).ratio()
    score = name_similarity * 0.6
    score += 0.15 if left.brand and left.brand == right.brand else 0.0
    score += 0.1 if left.volume_ml and left.volume_ml == right.volume_ml else 0.0
    score += 0.05 if left.abv_percent and right.abv_percent and abs(left.abv_percent - right.abv_percent) <= 0.25 else 0.0
    score += 0.05 if left.pack_size and left.pack_size == right.pack_size else 0.0
    score += 0.05 if left.category and left.category == right.category else 0.0
    return round(min(score, 1.0), 3)


class UnionFind:
    def __init__(self, values: list[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left != root_right:
            self.parent[max(root_left, root_right)] = min(root_left, root_right)


def canonicalize_products(limit: int = 5000, min_score: float = 0.88) -> dict[str, Any]:
    rows = deps.data_store.list_products_for_canonicalization(limit=max(1, int(limit)))
    candidates = [candidate_from_row(row) for row in rows if row.get("product_id")]
    by_id = {item.product_id: item for item in candidates}
    uf = UnionFind(list(by_id))
    match_count = 0

    for index, left in enumerate(candidates):
        for right in candidates[index + 1:]:
            if left.canonical_key == right.canonical_key:
                uf.union(left.product_id, right.product_id)
                match_count += 1
                continue
            score = match_score(left, right)
            if score >= min_score:
                uf.union(left.product_id, right.product_id)
                match_count += 1

    groups: dict[str, list[CanonicalCandidate]] = {}
    for item in candidates:
        groups.setdefault(uf.find(item.product_id), []).append(item)

    updates = []
    for members in groups.values():
        representative = sorted(members, key=lambda item: (item.canonical_key, item.product_id))[0]
        canonical_product_id = f"cp_{stable_id(representative.canonical_key)}"
        for item in members:
            score = 1.0 if item.product_id == representative.product_id else max(
                match_score(item, representative),
                1.0 if item.canonical_key == representative.canonical_key else 0.0,
            )
            updates.append({
                "product_id": item.product_id,
                "canonical_product_id": canonical_product_id,
                "canonical_key": item.canonical_key,
                "canonical_match_score": score,
            })

    result = deps.data_store.update_product_canonicalization(updates)
    product_cache.clear()
    return {
        "status": "completed",
        "products_scanned": len(candidates),
        "canonical_groups": len(groups),
        "candidate_matches": match_count,
        **result,
    }
