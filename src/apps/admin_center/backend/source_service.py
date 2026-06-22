from __future__ import annotations

import csv
import io
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from apps.admin_center.backend import dependencies as deps
from apps.admin_center.backend.cache import source_cache
from apps.admin_center.backend.rule_catalog import targets_for
from apps.admin_center.backend.services import source_group

SOURCE_IMPORT_COLUMNS = ["name", "url", "type", "category", "note"]
LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def list_sources() -> list[dict]:
    """Return source rows with a short cache because the registry is read often."""
    return source_cache.get_or_set(("sources",), _list_sources_uncached)


def clear_source_cache() -> None:
    """Invalidate source reads after create/update/delete/import mutations."""
    source_cache.clear()


def _list_sources_uncached() -> list[dict]:
    sources = deps.mongo_store.read_or_default(
        "source list",
        deps.mongo_store.list_sources,
        [],
    )
    domains = [source.get("domain") or urlparse(source.get("url") or "").netloc for source in sources]
    # Batch the raw-page lookup instead of calling Mongo once per source.
    saved_domains = deps.mongo_store.read_or_default(
        "source raw-page domains",
        lambda: deps.mongo_store.raw_page_domains(domains),
        set(),
    )
    product_counts = deps.mongo_store.read_or_default(
        "source product counts",
        lambda: deps.mongo_store.source_product_counts(domains),
        {},
    )
    # Keep local development behavior: raw files on disk also count as saved data.
    for root in deps.raw_dirs():
        saved_domains.update(path.name for path in root.iterdir() if path.is_dir())
    result = []
    for source, domain in zip(sources, domains):
        # Treat example.com and www.example.com as the same source for raw artifacts.
        aliases = {domain, domain.removeprefix("www.")}
        if not domain.startswith("www."):
            aliases.add(f"www.{domain}")
        product_count = sum((product_counts.get(alias) or {}).get("products", 0) for alias in aliases)
        quarantine_count = sum((product_counts.get(alias) or {}).get("quarantined", 0) for alias in aliases)
        has_raw_data = bool(aliases & saved_domains)
        domain = source.get("domain") or urlparse(source.get("url") or "").netloc
        result.append({
            "id": source["id"],
            "name": source.get("name"),
            "url": source.get("url"),
            "type": source.get("type"),
            "category": source.get("category"),
            "group": source_group(source.get("category")),
            "note": source.get("note"),
            "store_scope": source.get("store_scope") or "site",
            "store_name": source.get("store_name"),
            "store_url": source.get("store_url"),
            "store_address": source.get("store_address"),
            "store_phone": source.get("store_phone"),
            "store_channel": source.get("store_channel"),
            "auto_promote_rules": source.get("auto_promote_rules", True),
            "quality_gate_enabled": source.get("quality_gate_enabled", True),
            "important": source.get("important", False),
            "has_raw_data": has_raw_data,
            "product_count": product_count,
            "quarantine_count": quarantine_count,
            "saved_locally": has_raw_data,
        })
    return result


def source_template_csv() -> str:
    return sources_to_csv([{
        "name": "Example Store",
        "url": "https://example.com",
        "type": "E-commerce",
        "category": "Rượu bia",
        "note": "Ghi chú tùy chọn",
    }])


def sources_to_csv(sources: list[dict]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=SOURCE_IMPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for source in sources:
        writer.writerow({
            "name": source.get("name") or "",
            "url": source.get("url") or "",
            "type": source.get("type") or "",
            "category": source.get("category") or "",
            "note": source.get("note") or "",
        })
    return output.getvalue()


def local_timestamp() -> str:
    return datetime.now(LOCAL_TZ).strftime("%Y%m%d-%H%M%S")


def parse_sources_csv(raw_csv: str) -> list[dict]:
    """Validate source import CSV before writing anything to MongoDB."""
    reader = csv.DictReader(io.StringIO(raw_csv))
    missing = [column for column in SOURCE_IMPORT_COLUMNS[:4] if column not in (reader.fieldnames or [])]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing CSV columns: {', '.join(missing)}")

    rows = []
    for index, row in enumerate(reader, start=2):
        source = {column: (row.get(column) or "").strip() for column in SOURCE_IMPORT_COLUMNS}
        if not any(source.values()):
            continue
        if not source["name"] or not source["url"] or not source["type"] or not source["category"]:
            raise HTTPException(status_code=400, detail=f"Row {index} must include name, url, type, category")
        rows.append(source)
    if not rows:
        raise HTTPException(status_code=400, detail="CSV file does not contain source rows")
    return rows


def import_sources_csv(raw_csv: str) -> dict:
    rows = parse_sources_csv(raw_csv)
    created = []
    failed = []
    for index, row in enumerate(rows, start=1):
        result = deps.mongo_store.create_source(row)
        if result:
            created.append(result)
        else:
            failed.append({"row": index, "name": row.get("name"), "url": row.get("url")})
    return {
        "imported": len(created),
        "failed": len(failed),
        "total": len(rows),
        "sources": created,
        "errors": failed,
    }


def source_discovery(source_id: str) -> dict:
    source = next((row for row in deps.mongo_store.list_sources() if str(row.get("id")) == str(source_id)), None)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    domain = source.get("domain") or urlparse(source.get("url") or "").netloc
    aliases = [domain, domain.removeprefix("www.")]
    if not domain.startswith("www."):
        aliases.append(f"www.{domain}")
    artifacts_by_id = {}
    for alias in dict.fromkeys(aliases):
        for artifact in deps.raw_artifacts(alias, limit=12):
            artifact_id = artifact.get("id") or artifact.get("raw_page_id")
            if artifact_id:
                artifacts_by_id[str(artifact_id)] = artifact
    artifacts = sorted(
        artifacts_by_id.values(),
        key=lambda item: str(item.get("updated_at") or item.get("captured_at") or ""),
        reverse=True,
    )[:12]
    rule = deps.mongo_store.rule_structure(domain)
    structure = rule.get("structure") if rule else None
    targets = targets_for(structure) if isinstance(structure, dict) else []
    return {
        "source": source,
        "domain": domain,
        "raw_artifacts": artifacts,
        "rule": {
            "configured": bool(rule),
            "version": rule.get("version") if rule else None,
            "targets": targets,
        },
        "summary": {
            "raw_artifact_count": len(artifacts),
            "has_recent_raw": bool(artifacts),
            "has_rule": bool(rule),
        },
    }
