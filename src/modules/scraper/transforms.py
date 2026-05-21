"""Field transform functions applied after extracting raw text/attrs from HTML."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from bs4 import Tag

_SOLD_OUT_PATTERNS = [
    r"hết\s*hàng",
    r"sold[\s-]?out",
    r"out[\s-]?of[\s-]?stock",
    r"unavailable",
    r"ngừng\s*kinh\s*doanh",
    r"tạm\s*hết",
]


def apply_transform(element: "Tag", raw: str, transform: Optional[str]) -> str:
    """Apply a named transform to a raw string extracted from *element*."""
    value = (raw or "").strip()
    if not transform:
        return value

    t = transform.lower().strip()

    dispatch = {
        "text_content": lambda v: v,
        "strip_html": lambda v: v,
        "clean_price": clean_price,
        "extract_percentage": extract_percentage,
        "extract_volume_ml": extract_volume_ml,
        "check_for_sold_out_indicator": lambda v: check_sold_out(element, v),
        "extract_rating_from_html_attributes_or_classes": lambda v: extract_rating(element, v),
        "extract_review_count_from_html_attributes_or_classes": lambda v: extract_review_count(element, v),
        # These require external context; return as-is
        "extract_brand_from_product_name": lambda v: v,
        "extract_category_from_product_name": lambda v: v,
    }

    fn = dispatch.get(t)
    return fn(value) if fn else value


# ── Individual transforms ────────────────────────────────────────────────────

def clean_price(text: str) -> str:
    """Remove all non-digit characters: '125.000đ' → '125000'."""
    return re.sub(r"[^\d]", "", text)


def price_to_float(text: str) -> float:
    nums = re.sub(r"[^\d]", "", text)
    try:
        return float(nums) if nums else 0.0
    except ValueError:
        return 0.0


def extract_percentage(text: str) -> str:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*%", text)
    return (match.group(1) + "%") if match else text.strip()


def extract_volume_ml(text: str) -> str:
    match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(ml|cl|dl|l|lít|litre?s?)\b", text, re.IGNORECASE
    )
    if match:
        val_str = match.group(1).replace(",", ".")
        unit = match.group(2).lower()
        try:
            val = float(val_str)
        except ValueError:
            return text.strip()
        if unit in ("l", "lít", "litre", "litres"):
            return str(int(val * 1000)) + "ml"
        if unit == "cl":
            return str(int(val * 10)) + "ml"
        if unit == "dl":
            return str(int(val * 100)) + "ml"
        return val_str + "ml"
    return text.strip()


def check_sold_out(element: "Tag", text: str) -> str:
    combined = (str(element) + " " + text).lower()
    for pattern in _SOLD_OUT_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE):
            return "Hết hàng"
    return "Còn hàng"


def extract_rating(element: "Tag", text: str) -> str:
    for attr in ("data-rating", "data-score", "data-stars"):
        val = element.get(attr, "")  # type: ignore[union-attr]
        if val:
            return str(val)
    html = str(element)
    match = re.search(r"rating[_-]?(\d+(?:[.,]\d+)?)", html, re.IGNORECASE)
    if match:
        return match.group(1)
    stars = element.select(".star-active, .star-filled, .rating-active")  # type: ignore[union-attr]
    if stars:
        return str(len(stars))
    return text.strip()


def extract_review_count(element: "Tag", text: str) -> str:
    for attr in ("data-review-count", "data-count", "data-reviews"):
        val = element.get(attr, "")  # type: ignore[union-attr]
        if val:
            return str(val)
    match = re.search(r"(\d+)\s*(?:đánh giá|review|nhận xét)", text, re.IGNORECASE)
    if match:
        return match.group(1)
    return text.strip()
