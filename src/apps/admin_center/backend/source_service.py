from __future__ import annotations

import csv
import io
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from apps.admin_center.backend import dependencies as deps
from apps.admin_center.backend.rule_catalog import targets_for
from apps.admin_center.backend.services import source_group

SOURCE_IMPORT_COLUMNS = ["name", "url", "type", "category", "note"]
LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def list_sources() -> list[dict]:
    result = []
    for source in deps.mongo_store.list_sources():
        domain = source.get("domain") or urlparse(source.get("url") or "").netloc
        result.append({
            "id": source["id"],
            "name": source.get("name"),
            "url": source.get("url"),
            "type": source.get("type"),
            "category": source.get("category"),
            "group": source_group(source.get("category")),
            "note": source.get("note"),
            "saved_locally": bool(deps.mongo_store.raw_pages(domain, 1)),
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
    writer = csv.DictWriter(output, fieldnames=[*SOURCE_IMPORT_COLUMNS, "exported_at"], extrasaction="ignore")
    writer.writeheader()
    exported_at = datetime.now(LOCAL_TZ).isoformat()
    for source in sources:
        writer.writerow({
            "name": source.get("name") or "",
            "url": source.get("url") or "",
            "type": source.get("type") or "",
            "category": source.get("category") or "",
            "note": source.get("note") or "",
            "exported_at": exported_at,
        })
    return output.getvalue()


def local_timestamp() -> str:
    return datetime.now(LOCAL_TZ).strftime("%Y%m%d-%H%M%S")


def parse_sources_csv(raw_csv: str) -> list[dict]:
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
    artifacts = deps.raw_artifacts(domain, limit=12)
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
