from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from apps.admin_center.backend.settings import settings

GEMINI_ALLOWED_TRANSFORMS = {
    "text_content",
    "clean_price",
    "extract_percentage",
    "extract_volume_ml",
    "check_for_sold_out_indicator",
    "extract_rating_from_html_attributes_or_classes",
    "extract_review_count_from_html_attributes_or_classes",
}


def _safe_html_excerpt(html: str, limit: int = 24000) -> str:
    text = " ".join(html.split())
    return text[:limit]


def _normalize_model_name(model: str) -> str:
    value = model.strip()
    if "/models/" in value:
        value = value.split("/models/", 1)[1]
    if value.startswith("models/"):
        value = value.split("models/", 1)[1]
    return value


def _target_schema(target: str) -> dict[str, Any]:
    if target == "listing":
        return {
            "container_selector": "",
            "item_selector": "",
            "pagination": {
                "type": "none",
                "next_button_selector": None,
                "page_param": None,
                "url_pattern": None,
                "max_pages": None,
            },
            "fields": [],
        }
    if target == "stores":
        return {
            "container_selector": "",
            "item_selector": "",
            "fields": [],
        }
    return {"fields": []}


def build_gemini_prompt(*, domain: str, html: str, url: str | None = None, page_type: str | None = None, target_hint: str | None = None) -> str:
    excerpt = _safe_html_excerpt(html)
    payload = {
        "domain": domain,
        "url": url,
        "page_type": page_type,
        "target_hint": target_hint or "auto",
        "known_targets": ["listing", "product_detail", "stores"],
        "notes": [
            "Return JSON only. No markdown. No code fences.",
            "Do not invent selectors that are not supported by the HTML.",
            "Prefer stable selectors with tag, class, id, attribute, or semantic structure.",
            "If the page supports multiple targets, include each target you can justify from the HTML.",
            "If a target cannot be justified, leave its object empty instead of hallucinating selectors.",
            "Use the same output shape as the Admin Center rule files.",
        ],
        "allowed_transforms": sorted(GEMINI_ALLOWED_TRANSFORMS),
        "output_shape": {
            "domain": domain,
            "page_type": page_type or "unknown",
            "listing": _target_schema("listing"),
            "product_detail": _target_schema("product_detail"),
            "stores": _target_schema("stores"),
            "notes": "short notes only",
        },
        "html_excerpt": excerpt,
    }
    return (
        "You are an extraction engineer. Read the HTML excerpt and produce a deterministic rule draft for the site.\n"
        "The result must be a single JSON object matching this schema:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
        "Rules:\n"
        "- Use only evidence in the HTML excerpt.\n"
        "- For listing pages, return selectors for container, item, pagination, and fields.\n"
        "- For product detail pages, return product_detail fields.\n"
        "- For store or branch pages, return stores selectors and fields.\n"
        "- Fields should use names already common in the Admin Center such as product_name, price, old_price, image_url, product_url, store_name, store_address, store_phone, store_url.\n"
        "- Each field object must use: name, selector, attr, required, transform.\n"
        "- Keep selectors concise and stable.\n"
        "- If unsure, prefer a narrower selector and mention the uncertainty in notes.\n"
        "- Output JSON only."
    )


def build_ai_review_prompt(*, domain: str, html: str, url: str | None = None, page_type: str | None = None, target_hint: str | None = None, max_items: int = 24) -> str:
    excerpt = _safe_html_excerpt(html)
    payload = {
        "domain": domain,
        "url": url,
        "page_type": page_type,
        "target_hint": target_hint or "auto",
        "max_items": max(1, min(int(max_items or 24), 50)),
        "notes": [
            "Return JSON only. No markdown. No code fences.",
            "Produce a review list, not extraction rules.",
            "Use only evidence in the HTML excerpt.",
            "If the page is dynamic or blocked, infer only what is visible in text/metadata.",
            "Mark every candidate with review_status='needs_review'.",
            "Prefer products and stores that an operator can verify manually.",
        ],
        "output_shape": {
            "domain": domain,
            "page_type": page_type or "unknown",
            "source_url": url,
            "items": [
                {
                    "entity_type": "product",
                    "name": "sample name",
                    "url": "https://example.com/product",
                    "price": 0,
                    "currency": "VND",
                    "store_name": "sample store",
                    "store_url": "https://example.com",
                    "address": "sample address",
                    "phone": "sample phone",
                    "image_url": "https://example.com/image.jpg",
                    "confidence": 0.5,
                    "reason": "short reason",
                    "review_status": "needs_review",
                }
            ],
            "notes": "short notes only",
        },
        "html_excerpt": excerpt,
    }
    return (
        "You are an AI data collection agent for a review queue.\n"
        "Extract a candidate list from the HTML excerpt for human review.\n"
        "The result must be a single JSON object matching this schema:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
        "Rules:\n"
        "- Use only evidence visible in the excerpt.\n"
        "- Produce candidate rows for products, stores, or both if justified.\n"
        "- Each item must include entity_type, name, url, price, currency, store_name, store_url, address, phone, image_url, confidence, reason, review_status.\n"
        "- review_status must be 'needs_review' for every item.\n"
        "- Keep confidence between 0 and 1.\n"
        "- If the page is a category/listing page, return multiple products.\n"
        "- If the page is a store/contact page, return store candidates.\n"
        "- Output JSON only."
    )


def _extract_json_text(text: str) -> str:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        if "\n" in candidate:
            candidate = candidate.split("\n", 1)[1]
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start >= 0 and end > start:
        return candidate[start : end + 1]
    return candidate


def _normalize_section(section: Any) -> dict[str, Any]:
    if not isinstance(section, dict):
        return {}
    normalized = dict(section)
    if "pagination" in normalized and not isinstance(normalized["pagination"], dict):
        normalized["pagination"] = {}
    fields = normalized.get("fields")
    if isinstance(fields, list):
        normalized["fields"] = [
            {
                "name": str(field.get("name") or ""),
                "selector": str(field.get("selector") or ""),
                "attr": field.get("attr"),
                "required": bool(field.get("required", False)),
                "transform": field.get("transform")
                if isinstance(field.get("transform"), str) and field.get("transform") in GEMINI_ALLOWED_TRANSFORMS
                else field.get("transform"),
            }
            for field in fields
            if isinstance(field, dict) and field.get("name")
        ]
    return normalized


def parse_gemini_rule(raw_text: str) -> dict[str, Any]:
    payload = json.loads(_extract_json_text(raw_text))
    if not isinstance(payload, dict):
        raise ValueError("Gemini response must be a JSON object")
    output_shape = payload.get("output_shape") if isinstance(payload.get("output_shape"), dict) else {}
    listing = payload.get("listing") if isinstance(payload.get("listing"), dict) else output_shape.get("listing")
    product_detail = (
        payload.get("product_detail")
        if isinstance(payload.get("product_detail"), dict)
        else output_shape.get("product_detail")
    )
    stores = payload.get("stores") if isinstance(payload.get("stores"), dict) else output_shape.get("stores")
    result = {
        "domain": payload.get("domain"),
        "page_type": payload.get("page_type") or "unknown",
        "listing": _normalize_section(listing),
        "product_detail": _normalize_section(product_detail),
        "stores": _normalize_section(stores),
        "notes": payload.get("notes") or "",
    }
    return result


def parse_ai_review_candidates(raw_text: str) -> dict[str, Any]:
    payload = json.loads(_extract_json_text(raw_text))
    if not isinstance(payload, dict):
        raise ValueError("Gemini response must be a JSON object")
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    normalized_items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        entity_type = str(item.get("entity_type") or "product").strip().lower()
        if entity_type not in {"product", "store"}:
            entity_type = "product"
        normalized_items.append({
            "entity_type": entity_type,
            "name": str(item.get("name") or "").strip(),
            "url": str(item.get("url") or "").strip(),
            "price": item.get("price"),
            "currency": str(item.get("currency") or "VND").strip() or "VND",
            "store_name": str(item.get("store_name") or "").strip(),
            "store_url": str(item.get("store_url") or "").strip(),
            "address": str(item.get("address") or "").strip(),
            "phone": str(item.get("phone") or "").strip(),
            "image_url": str(item.get("image_url") or "").strip(),
            "confidence": max(0.0, min(float(item.get("confidence") or 0.0), 1.0)),
            "reason": str(item.get("reason") or "").strip(),
            "review_status": str(item.get("review_status") or "needs_review").strip() or "needs_review",
        })
    return {
        "domain": payload.get("domain"),
        "page_type": payload.get("page_type") or "unknown",
        "source_url": payload.get("source_url"),
        "notes": payload.get("notes") or "",
        "items": normalized_items,
    }


@dataclass
class GeminiExtractionResult:
    model: str
    prompt: str
    draft: dict[str, Any]
    validation: dict[str, Any]


@dataclass
class GeminiReviewResult:
    model: str
    prompt: str
    candidates: dict[str, Any]


class GeminiClient:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or getattr(settings, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
        configured_model = model or getattr(settings, "GEMINI_MODEL", "") or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        self.model = _normalize_model_name(configured_model)

    def available(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        body = json.dumps({
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 4096,
                "responseMimeType": "application/json",
            },
        }).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"Gemini API request failed: {exc.code} {exc.reason}") from exc
        except URLError as exc:
            raise RuntimeError(f"Gemini API request failed: {exc.reason}") from exc

        candidates = payload.get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini API returned no candidates")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        if not text.strip():
            raise RuntimeError("Gemini API returned empty text")
        return text


def validate_draft(html: str | None, draft: dict[str, Any]) -> dict[str, Any]:
    from apps.admin_center.backend.services import field_preview

    validation: dict[str, Any] = {"targets": {}, "accepted": False}
    if not html:
        return validation

    total_targets = 0
    accepted_targets = 0
    for target_name in ("listing", "product_detail", "stores"):
        section = draft.get(target_name) or {}
        fields = section.get("fields") if isinstance(section, dict) else []
        if not fields:
            continue
        total_targets += 1
        preview = field_preview(html, fields)
        required_fields = [row for row in preview if row.get("required")]
        passed_required = all((row.get("matches") or 0) > 0 for row in required_fields) if required_fields else False
        field_hits = sum(1 for row in preview if (row.get("matches") or 0) > 0)
        score = round(field_hits / len(preview), 2) if preview else 0.0
        if passed_required:
            accepted_targets += 1
        validation["targets"][target_name] = {
            "preview": preview,
            "required_pass": passed_required,
            "field_score": score,
        }

    validation["accepted"] = bool(total_targets and accepted_targets)
    return validation


def analyze_html(*, domain: str, html: str, url: str | None = None, page_type: str | None = None, target_hint: str | None = None) -> GeminiExtractionResult:
    client = GeminiClient()
    prompt = build_gemini_prompt(domain=domain, html=html, url=url, page_type=page_type, target_hint=target_hint)
    raw_text = client.generate(prompt)
    draft = parse_gemini_rule(raw_text)
    draft["domain"] = draft.get("domain") or domain
    validation = validate_draft(html, draft)
    validation["model"] = client.model
    validation["target_hint"] = target_hint or "auto"
    return GeminiExtractionResult(model=client.model, prompt=prompt, draft=draft, validation=validation)


def generate_review_candidates(*, domain: str, html: str, url: str | None = None, page_type: str | None = None, target_hint: str | None = None, max_items: int = 24) -> GeminiReviewResult:
    client = GeminiClient()
    prompt = build_ai_review_prompt(domain=domain, html=html, url=url, page_type=page_type, target_hint=target_hint, max_items=max_items)
    raw_text = client.generate(prompt)
    candidates = parse_ai_review_candidates(raw_text)
    candidates["domain"] = candidates.get("domain") or domain
    candidates["page_type"] = candidates.get("page_type") or (page_type or "unknown")
    return GeminiReviewResult(model=client.model, prompt=prompt, candidates=candidates)
