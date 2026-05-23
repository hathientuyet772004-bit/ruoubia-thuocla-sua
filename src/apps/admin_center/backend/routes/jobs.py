from __future__ import annotations

import json
import os
from datetime import datetime

from fastapi import APIRouter, Depends

from apps.admin_center.backend.dependencies import mongo_store, project_root, require_admin_session

router = APIRouter(prefix="/api/jobs", tags=["jobs"], dependencies=[Depends(require_admin_session)])


@router.get("")
async def get_jobs(limit: int = 50):
    mongo_jobs = mongo_store.jobs(limit)
    if mongo_jobs:
        return mongo_jobs

    jobs = []
    raw_dir = project_root / "store" / "raw"
    output_dir = project_root / "store" / "outputs"

    if not raw_dir.exists():
        return []

    output_files = [path.name for path in output_dir.glob("*.json")] if output_dir.exists() else []
    raw_files = list(raw_dir.glob("**/*.meta.json"))
    for meta_file in raw_files:
        try:
            with open(meta_file, "r", encoding="utf-8") as handle:
                meta = json.load(handle)

            filename = meta_file.name.replace(".meta.json", "")
            source = meta.get("domain", meta_file.parent.name)
            is_completed = any(filename in output_file for output_file in output_files)
            status = "Completed" if is_completed else "Pending"
            if (meta_file.parent / f"{filename}.error").exists():
                status = "Failed"
            timestamp = datetime.fromtimestamp(os.path.getmtime(meta_file)).isoformat()

            jobs.append({
                "id": filename,
                "filename": filename,
                "source": source,
                "status": status,
                "timestamp": timestamp,
            })
        except Exception:
            continue

    jobs.sort(key=lambda row: row["timestamp"], reverse=True)
    return jobs[:limit]


@router.get("/logs/{job_id}")
async def get_job_logs(job_id: str):
    mongo_log = mongo_store.job_log(job_id)
    if mongo_log:
        return mongo_log

    raw_dir = project_root / "store" / "raw"
    output_dir = project_root / "store" / "outputs"

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
