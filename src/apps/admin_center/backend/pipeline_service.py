from __future__ import annotations

import uuid
from typing import Any, Callable

from fastapi import HTTPException
from pymongo import DESCENDING

from apps.admin_center.backend import dependencies as deps
from apps.admin_center.backend import extraction_quality
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
        "description": "Pipeline ngầm được tạo từ trang nguồn, dùng Gemini để học rule rồi áp dụng writer.",
        "mode": "hybrid",
        "source_ids": [source_id],
        "entry_urls": [source.get("url")] if source.get("url") else [],
        "search_queries": [],
        "target_hints": ["product_listing", "product_detail", "store_listing"],
        "schema_mode": "auto",
        "schedule_type": "manual",
        "cron": None,
        "page_budget": 24,
        "writer_page_limit": 6,
        "max_depth": 2,
        "retry_attempts": 3,
        "retry_backoff_seconds": 1.5,
        "browser_fallback": False,
        "region": "VN",
        "user_agent": None,
        "enabled": True,
        "notes": "Managed by source collection action. Gemini drafts extraction rules; validated rules are saved and reused by writer.",
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
    run_id = str(uuid.uuid4())
    if not deps.mongo_store.acquire_pipeline_lease(pipeline_id, run_id):
        raise HTTPException(status_code=409, detail="Pipeline is already running")
    try:
        return _run_pipeline_body(pipeline_id, run_id)
    finally:
        deps.mongo_store.release_pipeline_lease(pipeline_id, run_id)


def run_collection_pipeline(
    pipeline_id: str,
    capture: Callable[[dict[str, Any]], Any],
) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    if not deps.mongo_store.acquire_pipeline_lease(pipeline_id, run_id, lease_seconds=3600):
        raise HTTPException(status_code=409, detail="Pipeline is already running")
    try:
        db = deps.mongo_store.get_db()
        if db is None:
            raise HTTPException(status_code=503, detail="MongoDB Atlas is unavailable")
        pipeline = db.admin_pipelines.find_one({"pipeline_id": pipeline_id}, {"_id": False})
        if pipeline is None:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        capture(pipeline)
        return _run_pipeline_body(pipeline_id, run_id)
    finally:
        deps.mongo_store.release_pipeline_lease(pipeline_id, run_id)


def _aggregate_writer_metrics(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    valid_products = sum(int(item.get("valid_products") or 0) for item in metrics)
    if not valid_products:
        return {
            "valid_products": 0,
            "required_coverage": 0.0,
            "brand_coverage": 0.0,
            "duplicate_ratio": 0.0,
            "median_price": None,
        }
    return {
        "valid_products": valid_products,
        "required_coverage": round(
            sum(float(item.get("required_coverage") or 0) * int(item.get("valid_products") or 0) for item in metrics)
            / valid_products,
            3,
        ),
        "brand_coverage": round(
            sum(float(item.get("brand_coverage") or 0) * int(item.get("valid_products") or 0) for item in metrics)
            / valid_products,
            3,
        ),
        "duplicate_ratio": round(
            sum(float(item.get("duplicate_ratio") or 0) * int(item.get("valid_products") or 0) for item in metrics)
            / valid_products,
            3,
        ),
        "median_price": next(
            (item.get("median_price") for item in reversed(metrics) if item.get("median_price") is not None),
            None,
        ),
    }


def _validation_samples(domain: str, artifacts: list[dict[str, Any]]) -> list[tuple[dict[str, Any], str]]:
    samples = []
    for artifact in extraction_quality.select_validation_artifacts(artifacts):
        raw_page, html = deps.raw_artifact_html((artifact or {}).get("id"), domain)
        if raw_page and html:
            samples.append((raw_page, html))
    return samples


def _run_pipeline_body(pipeline_id: str, run_id: str) -> dict[str, Any]:
    db = deps.mongo_store.get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB Atlas is unavailable")
    pipeline = db.admin_pipelines.find_one({"pipeline_id": pipeline_id}, {"_id": False})
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")

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
            "rules_saved": 0,
            "warnings": [],
            "results": [],
        },
        "created_at": started_at,
        "updated_at": started_at,
    }
    db.admin_pipeline_runs.insert_one(run_doc)

    summary = run_doc["summary"]
    failed_sources = 0
    quality_metrics_by_source = dict(pipeline.get("quality_metrics_by_source") or {})
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
            active_rule_version = None
            active_validation_score = None
            rule = deps.mongo_store.rule_structure(discovery.get("domain") or "")
            if rule and isinstance(rule.get("structure"), dict):
                writer_structure = rule["structure"]
                active_rule_version = rule.get("version")
                active_validation_score = ((rule.get("quality") or {}).get("score"))
            if should_analyze:
                validation_artifacts = extraction_quality.select_validation_artifacts(discovery.get("raw_artifacts") or [])
                artifact = (validation_artifacts or discovery.get("raw_artifacts") or [None])[0]
                if artifact and artifact.get("id"):
                    summary["ai_attempts"] += 1
                    try:
                        analysis = extraction_service.analyze_with_gemini(GeminiExtractionAnalyzeSchema(
                            domain=discovery.get("domain") or "",
                            raw_artifact_id=artifact["id"],
                            target_hint=(pipeline.get("target_hints") or ["auto"])[0],
                        ))
                        validation = analysis.get("validation") or {}
                        draft = analysis.get("draft") if isinstance(analysis.get("draft"), dict) else None
                        candidate_validation = {}
                        candidate = None
                        if draft:
                            draft = extraction_quality.enforce_contract(draft)
                            samples = _validation_samples(discovery.get("domain") or "", discovery.get("raw_artifacts") or [])
                            candidate_validation = extraction_quality.validate_candidate(draft, samples, discovery.get("domain") or "")
                            candidate = deps.mongo_store.save_rule_candidate(
                                discovery.get("domain") or "",
                                draft,
                                candidate_validation,
                                model=analysis.get("model"),
                                artifact_ids=[(sample[0] or {}).get("id") for sample in samples if (sample[0] or {}).get("id")],
                            )
                        result["ai"] = {
                            "model": analysis.get("model"),
                            "accepted": bool(candidate_validation.get("accepted")),
                            "target_count": len(validation.get("targets") or {}),
                            "candidate_id": (candidate or {}).get("candidate_id"),
                            "score": candidate_validation.get("score"),
                            "quality": candidate_validation,
                        }
                        if candidate_validation.get("accepted") and candidate:
                            summary["ai_accepted"] += 1
                            auto_promote = bool((discovery.get("source") or {}).get("auto_promote_rules", True))
                            promoted = (
                                deps.mongo_store.promote_rule_candidate(candidate["candidate_id"], (rule or {}).get("version"))
                                if auto_promote
                                else {"promoted": False, "reason": "manual_review_required", "candidate_id": candidate["candidate_id"]}
                            )
                            if promoted and promoted.get("promoted"):
                                summary["rules_saved"] += 1
                                writer_structure = promoted.get("structure") or draft
                                active_rule_version = promoted.get("version")
                                active_validation_score = candidate_validation.get("score")
                                result["ai"]["rule_saved"] = True
                                result["ai"]["rule_version"] = promoted.get("version")
                                previous_quality = (rule or {}).get("quality")
                                drift = extraction_quality.drift_warnings(candidate_validation.get("metrics"), previous_quality.get("metrics") if isinstance(previous_quality, dict) else None)
                                if drift:
                                    result["ai"]["drift_warnings"] = drift
                                    summary["warnings"].extend(f"{source_id}: {item}" for item in drift)
                            else:
                                result["ai"]["rule_saved"] = False
                                result["ai"]["promotion_result"] = promoted
                                writer_structure = writer_structure or draft
                        elif candidate_validation:
                            summary["warnings"].append(f"{source_id}: candidate rule rejected, score={candidate_validation.get('score')}")
                    except HTTPException as exc:
                        result["ai"] = {"accepted": False, "error": exc.detail}
                        summary["warnings"].append(f"{source_id}: Gemini skipped: {exc.detail}")
                else:
                    summary["warnings"].append(f"{source_id}: không tìm được trang thô hợp lệ.")
            elif pipeline.get("mode") == "crawler" and not result["raw_artifact_count"]:
                summary["warnings"].append(f"{source_id}: chưa có raw artifact để crawl thường.")

            if result["raw_artifact_count"]:
                writer_structure = writer_structure or {"domain": discovery.get("domain") or ""}
                writer_limit = max(1, min(6, int(pipeline.get("writer_page_limit") or pipeline.get("page_budget") or 6)))
                writer_result = {"products": 0, "offers": 0, "store_fields": 0, "warnings": []}
                writer_metrics = []
                for artifact in (discovery.get("raw_artifacts") or [])[:writer_limit]:
                    raw_page, html = deps.raw_artifact_html((artifact or {}).get("id"), discovery.get("domain"))
                    partial = extraction_writer.write_extraction(
                        raw_page or {},
                        html or "",
                        writer_structure,
                        source_id,
                        source_config=discovery.get("source") or {},
                        rule_version=active_rule_version,
                        extraction_method="rule",
                        validation_score=float(active_validation_score) if active_validation_score is not None else None,
                        previous_metrics=quality_metrics_by_source.get(str(source_id)),
                    )
                    writer_result["products"] += partial.get("products", 0)
                    writer_result["offers"] += partial.get("offers", 0)
                    writer_result["store_fields"] += partial.get("stores", 0)
                    writer_result["warnings"].extend(partial.get("warnings") or [])
                    if isinstance(partial.get("metrics"), dict):
                        writer_metrics.append(partial["metrics"])
                current_metrics = _aggregate_writer_metrics(writer_metrics)
                previous_metrics = quality_metrics_by_source.get(str(source_id))
                drift = extraction_quality.drift_warnings(current_metrics, previous_metrics)
                writer_result["metrics"] = current_metrics
                writer_result["drift_warnings"] = drift
                quality_metrics_by_source[str(source_id)] = current_metrics
                if drift:
                    summary["warnings"].extend(f"{source_id}: {item}" for item in drift)
                result["writer"] = writer_result
                summary["products_written"] = summary.get("products_written", 0) + writer_result.get("products", 0)
                summary["offers_written"] = summary.get("offers_written", 0) + writer_result.get("offers", 0)
                summary["store_fields_attached"] = summary.get("store_fields_attached", 0) + writer_result.get("store_fields", 0)
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
        {"$set": {
            "last_run_id": run_id,
            "last_run_status": status,
            "last_run_at": finished_at,
            "quality_metrics_by_source": quality_metrics_by_source,
            "updated_at": finished_at,
        }},
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
        "retry_attempts": max(1, int(payload.get("retry_attempts") or 0) or 3),
        "retry_backoff_seconds": float(payload.get("retry_backoff_seconds") or 0) or 1.5,
        "browser_fallback": bool(payload.get("browser_fallback", False)),
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
        "retry_attempts": doc.get("retry_attempts", 3),
        "retry_backoff_seconds": doc.get("retry_backoff_seconds", 1.5),
        "browser_fallback": bool(doc.get("browser_fallback", False)),
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
