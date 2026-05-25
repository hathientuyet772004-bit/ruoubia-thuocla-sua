from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from pymongo import DESCENDING

from apps.admin_center.backend import dependencies as deps
from apps.admin_center.backend import extraction_service, extraction_writer, source_service
from apps.admin_center.backend.mongo_store import now_utc
from apps.admin_center.backend.schemas import GeminiExtractionAnalyzeSchema, PipelineSchema

PIPELINE_TEMPLATES = [
    {
        "template_id": "crawler-first",
        "name": "Crawler thường",
        "mode": "crawler",
        "description": "Ưu tiên HTTP crawl, parser và selector hiện có trước khi dùng AI.",
        "schema_mode": "guided",
        "page_budget": 200,
        "max_depth": 2,
        "target_hints": ["product_listing", "product_detail", "store_listing"],
        "notes": "Dùng cho nguồn HTML tĩnh hoặc nguồn đã có rule ổn định.",
    },
    {
        "template_id": "hybrid-ai",
        "name": "Hybrid AI",
        "mode": "hybrid",
        "description": "Crawler thường chạy trước, Gemini chỉ bù cho trang động hoặc selector yếu.",
        "schema_mode": "auto",
        "page_budget": 150,
        "max_depth": 3,
        "target_hints": ["product_listing", "product_detail", "store_listing", "store_detail"],
        "notes": "Phù hợp nguồn thương mại điện tử có layout thay đổi và store fields.",
    },
    {
        "template_id": "ai-fallback",
        "name": "AI fallback",
        "mode": "ai",
        "description": "Giảm phụ thuộc vào selector, dùng Gemini khi crawler thường không đủ dữ liệu.",
        "schema_mode": "auto",
        "page_budget": 80,
        "max_depth": 1,
        "target_hints": ["product_detail", "store_detail"],
        "notes": "Dùng cho site động, iframe, lazy load hoặc HTML không ổn định.",
    },
]


def list_pipeline_templates() -> list[dict[str, Any]]:
    return PIPELINE_TEMPLATES


def list_pipelines() -> list[dict[str, Any]]:
    db = deps.mongo_store.get_db()
    if db is None:
        return []
    pipeline_docs = list(db.admin_pipelines.find({}, {"_id": False}).sort([("updated_at", DESCENDING)]))
    runs = list(db.admin_pipeline_runs.find({}, {"_id": False}).sort([("created_at", DESCENDING)]).limit(500))
    latest_runs: dict[str, dict[str, Any]] = {}
    run_counts: dict[str, int] = {}
    for run in runs:
        pipeline_id = run.get("pipeline_id")
        if not pipeline_id:
            continue
        run_counts[pipeline_id] = run_counts.get(pipeline_id, 0) + 1
        latest_runs.setdefault(pipeline_id, run)
    return [_pipeline_view(doc, latest_runs.get(doc.get("pipeline_id")), run_counts.get(doc.get("pipeline_id"), 0)) for doc in pipeline_docs]


def get_pipeline(pipeline_id: str) -> dict[str, Any] | None:
    db = deps.mongo_store.get_db()
    if db is None:
        return None
    doc = db.admin_pipelines.find_one({"pipeline_id": pipeline_id}, {"_id": False})
    if doc is None:
        return None
    latest_run = db.admin_pipeline_runs.find_one({"pipeline_id": pipeline_id}, {"_id": False}, sort=[("created_at", DESCENDING)])
    run_count = db.admin_pipeline_runs.count_documents({"pipeline_id": pipeline_id})
    return _pipeline_view(doc, latest_run, run_count)


def create_pipeline(payload: PipelineSchema) -> dict[str, Any] | None:
    db = deps.mongo_store.get_db()
    if db is None:
        return None
    doc = _pipeline_doc(payload.model_dump())
    db.admin_pipelines.insert_one(doc)
    return _pipeline_view(doc, None, 0)


def update_pipeline(pipeline_id: str, payload: PipelineSchema) -> dict[str, Any] | None:
    db = deps.mongo_store.get_db()
    if db is None:
        return None
    current = db.admin_pipelines.find_one({"pipeline_id": pipeline_id}, {"_id": False})
    if current is None:
        return None
    doc = _pipeline_doc(payload.model_dump(), current=current)
    db.admin_pipelines.update_one({"pipeline_id": pipeline_id}, {"$set": doc})
    latest_run = db.admin_pipeline_runs.find_one({"pipeline_id": pipeline_id}, {"_id": False}, sort=[("created_at", DESCENDING)])
    run_count = db.admin_pipeline_runs.count_documents({"pipeline_id": pipeline_id})
    return _pipeline_view(doc, latest_run, run_count)


def delete_pipeline(pipeline_id: str) -> bool:
    db = deps.mongo_store.get_db()
    if db is None:
        return False
    result = db.admin_pipelines.delete_one({"pipeline_id": pipeline_id})
    return bool(result.deleted_count)


def list_pipeline_runs(limit: int = 50, pipeline_id: str | None = None) -> list[dict[str, Any]]:
    db = deps.mongo_store.get_db()
    if db is None:
        return []
    query: dict[str, Any] = {}
    if pipeline_id:
        query["pipeline_id"] = pipeline_id
    runs = list(db.admin_pipeline_runs.find(query, {"_id": False}).sort([("created_at", DESCENDING)]).limit(limit))
    pipeline_names = {
        doc.get("pipeline_id"): doc.get("name")
        for doc in db.admin_pipelines.find({}, {"_id": False, "pipeline_id": True, "name": True})
    }
    return [_run_view(run, pipeline_names.get(run.get("pipeline_id"))) for run in runs]


def source_pipeline_id(source_id: str) -> str:
    return f"source-{source_id}"


def ensure_source_pipeline(source_id: str) -> dict[str, Any]:
    db = deps.mongo_store.get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB Atlas is unavailable")
    source = next((row for row in deps.mongo_store.list_sources() if str(row.get("id")) == str(source_id)), None)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    pipeline_id = source_pipeline_id(source_id)
    current = db.admin_pipelines.find_one({"pipeline_id": pipeline_id}, {"_id": False})
    created_at = (current or {}).get("created_at") or now_utc()
    doc = {
        "pipeline_id": pipeline_id,
        "name": f"Thu thập {source.get('name') or source_id}",
        "description": "Pipeline ngầm được tạo từ trang nguồn.",
        "mode": "hybrid",
        "source_ids": [source_id],
        "entry_urls": [source.get("url")] if source.get("url") else [],
        "search_queries": [],
        "target_hints": ["product_listing", "product_detail", "store_listing"],
        "schema_mode": "auto",
        "schedule_type": "manual",
        "cron": None,
        "page_budget": 100,
        "max_depth": 2,
        "region": "VN",
        "user_agent": None,
        "enabled": True,
        "notes": "Managed by source collection action.",
        "managed_by": "source",
        "source_id": source_id,
        "created_at": created_at,
        "updated_at": now_utc(),
    }
    db.admin_pipelines.update_one(
        {"pipeline_id": pipeline_id},
        {"$set": {key: value for key, value in doc.items() if key != "created_at"}, "$setOnInsert": {"created_at": created_at}},
        upsert=True,
    )
    latest_run = db.admin_pipeline_runs.find_one({"pipeline_id": pipeline_id}, {"_id": False}, sort=[("created_at", DESCENDING)])
    run_count = db.admin_pipeline_runs.count_documents({"pipeline_id": pipeline_id})
    return _pipeline_view(doc, latest_run, run_count)


def list_source_runs(source_id: str, limit: int = 20) -> list[dict[str, Any]]:
    db = deps.mongo_store.get_db()
    if db is None:
        return []
    pipeline_id = source_pipeline_id(source_id)
    runs = list(db.admin_pipeline_runs.find({"pipeline_id": pipeline_id}, {"_id": False}).sort([("created_at", DESCENDING)]).limit(limit))
    return [_run_view(run, run.get("pipeline_name")) for run in runs]


def run_pipeline(pipeline_id: str) -> dict[str, Any]:
    db = deps.mongo_store.get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB Atlas is unavailable")
    pipeline = db.admin_pipelines.find_one({"pipeline_id": pipeline_id}, {"_id": False})
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    run_id = str(uuid.uuid4())
    started_at = now_utc()
    run_doc: dict[str, Any] = {
        "run_id": run_id,
        "pipeline_id": pipeline_id,
        "pipeline_name": pipeline.get("name"),
        "mode": pipeline.get("mode", "hybrid"),
        "status": "running",
        "summary": {
            "source_count": len(pipeline.get("source_ids", [])),
            "processed_sources": 0,
            "raw_artifacts": 0,
            "ai_attempts": 0,
            "ai_accepted": 0,
            "warnings": [],
            "results": [],
        },
        "created_at": started_at,
        "updated_at": started_at,
    }
    db.admin_pipeline_runs.insert_one(run_doc)

    summary = run_doc["summary"]
    failed_sources = 0
    source_ids = list(dict.fromkeys(pipeline.get("source_ids") or []))
    for source_id in source_ids:
        result: dict[str, Any] = {"source_id": source_id, "status": "pending"}
        try:
            discovery = source_service.source_discovery(source_id)
            result["domain"] = discovery.get("domain")
            result["raw_artifact_count"] = len(discovery.get("raw_artifacts") or [])
            result["rule_targets"] = discovery.get("rule", {}).get("targets", [])
            summary["raw_artifacts"] += result["raw_artifact_count"]
            summary["processed_sources"] += 1

            should_analyze = pipeline.get("mode") in {"hybrid", "ai"} and result["raw_artifact_count"]
            writer_structure = None
            rule = deps.mongo_store.rule_structure(discovery.get("domain") or "")
            if rule and isinstance(rule.get("structure"), dict):
                writer_structure = rule["structure"]
            if should_analyze:
                artifact = (discovery.get("raw_artifacts") or [None])[0]
                if artifact and artifact.get("id"):
                    summary["ai_attempts"] += 1
                    analysis = extraction_service.analyze_with_gemini(GeminiExtractionAnalyzeSchema(
                        domain=discovery.get("domain") or "",
                        raw_artifact_id=artifact["id"],
                        target_hint=(pipeline.get("target_hints") or ["auto"])[0],
                    ))
                    validation = analysis.get("validation") or {}
                    result["ai"] = {
                        "model": analysis.get("model"),
                        "accepted": bool(validation.get("accepted")),
                        "target_count": len(validation.get("targets") or {}),
                    }
                    if validation.get("accepted"):
                        summary["ai_accepted"] += 1
                        if not writer_structure:
                            writer_structure = analysis.get("draft")
                else:
                    summary["warnings"].append(f"{source_id}: không tìm được trang thô hợp lệ.")
            elif pipeline.get("mode") == "crawler" and not result["raw_artifact_count"]:
                summary["warnings"].append(f"{source_id}: chưa có raw artifact để crawl thường.")

            if writer_structure and result["raw_artifact_count"]:
                artifact = (discovery.get("raw_artifacts") or [None])[0]
                raw_page, html = deps.raw_artifact_html((artifact or {}).get("id"), discovery.get("domain"))
                writer_result = extraction_writer.write_extraction(raw_page or {}, html or "", writer_structure, source_id)
                result["writer"] = writer_result
                summary["products_written"] = summary.get("products_written", 0) + writer_result.get("products", 0)
                summary["offers_written"] = summary.get("offers_written", 0) + writer_result.get("offers", 0)
                summary["stores_written"] = summary.get("stores_written", 0) + writer_result.get("stores", 0)
                summary["warnings"].extend(writer_result.get("warnings") or [])
            result["status"] = "completed"
        except HTTPException as exc:
            failed_sources += 1
            result["status"] = "failed"
            result["error"] = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            summary["warnings"].append(f"{source_id}: {result['error']}")
        except Exception as exc:  # pragma: no cover - defensive guard for runtime orchestration
            failed_sources += 1
            result["status"] = "failed"
            result["error"] = str(exc)
            summary["warnings"].append(f"{source_id}: {exc}")
        summary["results"].append(result)

    finished_at = now_utc()
    status = "failed" if source_ids and failed_sources == len(source_ids) else "completed"
    db.admin_pipeline_runs.update_one(
        {"run_id": run_id},
        {"$set": {"status": status, "summary": summary, "updated_at": finished_at, "finished_at": finished_at}},
    )
    db.admin_pipelines.update_one(
        {"pipeline_id": pipeline_id},
        {"$set": {"last_run_id": run_id, "last_run_status": status, "last_run_at": finished_at, "updated_at": finished_at}},
    )
    return {
        "run_id": run_id,
        "pipeline_id": pipeline_id,
        "status": status,
        "summary": summary,
        "created_at": started_at,
        "finished_at": finished_at,
    }


def pipeline_overview() -> dict[str, Any]:
    db = deps.mongo_store.get_db()
    if db is None:
        return {"total": 0, "enabled": 0, "runs": 0, "running": 0}
    total = db.admin_pipelines.count_documents({})
    enabled = db.admin_pipelines.count_documents({"enabled": True})
    runs = db.admin_pipeline_runs.count_documents({})
    running = db.admin_pipeline_runs.count_documents({"status": "running"})
    return {"total": total, "enabled": enabled, "runs": runs, "running": running}


def _pipeline_doc(payload: dict[str, Any], current: dict[str, Any] | None = None) -> dict[str, Any]:
    created_at = current.get("created_at") if current else now_utc()
    pipeline_id = current.get("pipeline_id") if current else str(uuid.uuid4())
    return {
        "pipeline_id": pipeline_id,
        "name": payload.get("name"),
        "description": payload.get("description"),
        "mode": payload.get("mode", "hybrid"),
        "source_ids": list(dict.fromkeys(payload.get("source_ids") or [])),
        "entry_urls": [value for value in payload.get("entry_urls") or [] if value],
        "search_queries": [value for value in payload.get("search_queries") or [] if value],
        "target_hints": [value for value in payload.get("target_hints") or [] if value],
        "schema_mode": payload.get("schema_mode", "auto"),
        "schedule_type": payload.get("schedule_type", "manual"),
        "cron": payload.get("cron"),
        "page_budget": int(payload.get("page_budget") or 0) or 100,
        "max_depth": int(payload.get("max_depth") or 0) or 2,
        "region": payload.get("region") or "VN",
        "user_agent": payload.get("user_agent"),
        "enabled": bool(payload.get("enabled", True)),
        "notes": payload.get("notes"),
        "created_at": created_at,
        "updated_at": now_utc(),
    }


def _pipeline_view(doc: dict[str, Any], latest_run: dict[str, Any] | None, run_count: int) -> dict[str, Any]:
    return {
        "id": doc.get("pipeline_id"),
        "pipeline_id": doc.get("pipeline_id"),
        "name": doc.get("name"),
        "description": doc.get("description"),
        "mode": doc.get("mode", "hybrid"),
        "source_ids": doc.get("source_ids") or [],
        "entry_urls": doc.get("entry_urls") or [],
        "search_queries": doc.get("search_queries") or [],
        "target_hints": doc.get("target_hints") or [],
        "schema_mode": doc.get("schema_mode", "auto"),
        "schedule_type": doc.get("schedule_type", "manual"),
        "cron": doc.get("cron"),
        "page_budget": doc.get("page_budget", 100),
        "max_depth": doc.get("max_depth", 2),
        "region": doc.get("region") or "VN",
        "user_agent": doc.get("user_agent"),
        "enabled": bool(doc.get("enabled", True)),
        "notes": doc.get("notes"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
        "run_count": run_count,
        "source_count": len(doc.get("source_ids") or []),
        "last_run_id": doc.get("last_run_id") or (latest_run or {}).get("run_id"),
        "last_run_status": doc.get("last_run_status") or (latest_run or {}).get("status"),
        "last_run_at": doc.get("last_run_at") or (latest_run or {}).get("created_at"),
    }


def _run_view(doc: dict[str, Any], pipeline_name: str | None) -> dict[str, Any]:
    return {
        "id": doc.get("run_id"),
        "run_id": doc.get("run_id"),
        "pipeline_id": doc.get("pipeline_id"),
        "pipeline_name": pipeline_name or doc.get("pipeline_name"),
        "mode": doc.get("mode", "hybrid"),
        "status": doc.get("status", "queued"),
        "summary": doc.get("summary") or {},
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
        "finished_at": doc.get("finished_at"),
    }
