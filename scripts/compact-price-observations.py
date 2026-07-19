from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from apps.admin_center.backend.pg_store import AdminPgStore, now_utc  # noqa: E402


def compact(retention_days: int = 90, dry_run: bool = False) -> dict[str, int]:
    store = AdminPgStore()
    db = store.get_db()
    if db is None:
        raise SystemExit("PostgreSQL is unavailable")

    cutoff = now_utc() - timedelta(days=max(1, retention_days))
    old_rows = list(db.sc_price_observations.find({"observed_at": {"$lt": cutoff}}, {"_id": False}))
    buckets: dict[tuple[str, str], list[dict]] = {}
    for row in old_rows:
        product_id = row.get("product_id")
        observed_at = row.get("observed_at")
        if not product_id or not observed_at:
            continue
        day = observed_at.strftime("%Y-%m-%d")
        buckets.setdefault((product_id, day), []).append(row)

    if dry_run:
        return {"observations": len(old_rows), "daily_buckets": len(buckets), "deleted": 0}

    for (product_id, day), rows in buckets.items():
        prices = [float(row.get("price_numeric") or 0) for row in rows if float(row.get("price_numeric") or 0) > 0]
        if not prices:
            continue
        latest = max(rows, key=lambda row: row.get("observed_at"))
        db.sc_price_daily.update_one(
            {"product_id": product_id, "date": day},
            {
                "$set": {
                    "product_id": product_id,
                    "date": day,
                    "domain": latest.get("domain"),
                    "source_id": latest.get("source_id"),
                    "currency": latest.get("currency") or "VND",
                    "min_price": min(prices),
                    "max_price": max(prices),
                    "avg_price": round(sum(prices) / len(prices), 2),
                    "latest_price": latest.get("price_numeric"),
                    "observation_count": len(prices),
                    "updated_at": now_utc(),
                },
                "$setOnInsert": {"created_at": now_utc()},
            },
            upsert=True,
        )
    result = db.sc_price_observations.delete_many({"observed_at": {"$lt": cutoff}})
    return {"observations": len(old_rows), "daily_buckets": len(buckets), "deleted": result.deleted_count}


def main() -> None:
    parser = argparse.ArgumentParser(description="Compact old price observations into daily aggregates.")
    parser.add_argument("--retention-days", type=int, default=90)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(compact(retention_days=args.retention_days, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
