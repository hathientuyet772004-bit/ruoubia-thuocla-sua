from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from apps.admin_center.backend.mongo_store import AdminMongoStore, now_utc  # noqa: E402


def migrate(dry_run: bool = False) -> dict[str, int]:
    store = AdminMongoStore()
    db = store.get_db()
    if db is None:
        raise SystemExit("MongoDB Atlas is unavailable")

    query = {
        "$or": [
            {"store_id": {"$exists": True}},
            {"raw_data.store_id": {"$exists": True}},
            {"store_address": "Online"},
            {"data_origin": {"$exists": False}},
            {"field_sources": {"$exists": False}},
            {"address_status": {"$exists": False}},
        ]
    }
    matched = db.sc_products.count_documents(query)
    if dry_run:
        return {"matched": matched, "updated": 0}

    result = db.sc_products.update_many(
        query,
        {
            "$set": {
                "data_origin": "legacy",
                "field_sources": {},
                "address_status": "NOT_APPLICABLE",
                "store_channel": "online",
                "schema_migrated_at": now_utc(),
            },
            "$unset": {
                "store_id": "",
                "raw_data.store_id": "",
            },
        },
    )
    db.sc_products.update_many(
        {"store_address": "Online"},
        {"$unset": {"store_address": ""}, "$set": {"address_status": "NOT_APPLICABLE", "store_channel": "online"}},
    )
    db.sc_offers.update_many({"store_id": {"$exists": True}}, {"$unset": {"store_id": ""}})
    return {"matched": matched, "updated": result.modified_count}


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill product schema after store/provenance migration.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(migrate(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
