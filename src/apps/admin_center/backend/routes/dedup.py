from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from apps.admin_center.backend.dependencies import dedup_queue, mongo_store, require_mutation_session
from apps.admin_center.backend.schemas import DedupDecisionSchema

router = APIRouter(prefix="/api/dedup", tags=["dedup"])


@router.get("/candidates")
async def get_dedup_candidates(
    status: str | None = Query(default="pending"),
    limit: int = Query(default=20, ge=1, le=100),
):
    if status and status not in {"pending", "merged", "rejected", "needs_review", "all"}:
        raise HTTPException(status_code=400, detail="Invalid dedup queue status")
    rows = list(dedup_queue()["candidates"].values())
    if status and status != "all":
        rows = [row for row in rows if row.get("status") == status]
    rows.sort(key=lambda row: (row.get("status") != "pending", -row.get("confidence", 0)))
    return rows[:limit]


@router.post("/candidates/{candidate_id}/decision")
async def save_dedup_decision(
    candidate_id: str,
    payload: DedupDecisionSchema,
    role: str = Depends(require_mutation_session),
):
    if payload.status not in {"pending", "merged", "rejected", "needs_review"}:
        raise HTTPException(status_code=400, detail="Invalid dedup queue status")
    queue = dedup_queue()
    candidate = queue["candidates"].get(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Dedup candidate not found")
    if not mongo_store.update_dedup_candidate(candidate_id, payload.status, payload.note, role):
        raise HTTPException(status_code=503, detail="MongoDB Atlas could not save dedup decision")
    return {"status": "recorded", "candidate_id": candidate_id, "queue_status": payload.status}
