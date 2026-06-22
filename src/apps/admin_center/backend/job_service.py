from __future__ import annotations

import json
import os
from datetime import datetime

from apps.admin_center.backend import dependencies as deps
from apps.admin_center.backend.settings import settings


def list_jobs(limit: int = 50) -> list[dict]:
    mongo_jobs = deps.mongo_store.read_or_default(
        "job list",
        lambda: deps.mongo_store.jobs(limit),
        [],
    )
    if mongo_jobs:
        return mongo_jobs
    if not settings.ADMIN_PRODUCT_LOCAL_FALLBACK_ENABLED:
        return []

    jobs = []
    raw_dir = deps.project_root / "store" / "raw"
    output_dir = deps.project_root / "store" / "outputs"

    if not raw_dir.exists():
        return []

    output_files = [path.name for path in output_dir.glob("*.json")] if output_dir.exists() else []
    for meta_file in raw_dir.glob("**/*.meta.json"):
        try:
            with open(meta_file, "r", encoding="utf-8") as handle:
                meta = json.load(handle)
        except Exception:
            continue

        filename = meta_file.name.replace(".meta.json", "")
        source = meta.get("domain", meta_file.parent.name)
        is_completed = any(filename in output_file for output_file in output_files)
        status = "Completed" if is_completed else "Pending"
        if (meta_file.parent / f"{filename}.error").exists():
            status = "Failed"
        jobs.append({
            "id": filename,
            "filename": filename,
            "source": source,
            "status": status,
            "timestamp": datetime.fromtimestamp(os.path.getmtime(meta_file)).isoformat(),
        })

    jobs.sort(key=lambda row: row["timestamp"], reverse=True)
    return jobs[:limit]


def job_logs(job_id: str) -> dict:
    mongo_log = deps.mongo_store.job_log(job_id)
    if mongo_log:
        return mongo_log

    raw_dir = deps.project_root / "store" / "raw"
    output_dir = deps.project_root / "store" / "outputs"
    logs = {"job_id": job_id, "events": [], "metadata": {}, "error": None, "output_summary": None}

    meta_files = list(raw_dir.glob(f"**/{job_id}.meta.json"))
    if meta_files:
        meta_file = meta_files[0]
        logs["events"].append(f"[{datetime.fromtimestamp(os.path.getmtime(meta_file)).isoformat()}] Raw file discovered.")
        try:
            with open(meta_file, "r", encoding="utf-8") as handle:
                logs["metadata"] = json.load(handle)
        except Exception:
            pass

        error_file = meta_file.parent / f"{job_id}.error"
        if error_file.exists():
            with open(error_file, "r", encoding="utf-8") as handle:
                logs["error"] = handle.read()
            logs["events"].append(f"[{datetime.fromtimestamp(os.path.getmtime(error_file)).isoformat()}] Processing failed.")

    output_files = list(output_dir.glob(f"{job_id}*.json"))
    if output_files:
        output_file = output_files[0]
        logs["events"].append(f"[{datetime.fromtimestamp(os.path.getmtime(output_file)).isoformat()}] Extraction completed.")
        try:
            with open(output_file, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            logs["output_summary"] = {"product_count": len(data.get("products", [])), "source": data.get("source_site")}
        except Exception:
            pass

    if not logs["events"]:
        return {"error": "Job not found"}
    return logs
