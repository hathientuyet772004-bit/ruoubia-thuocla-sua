from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


TARGET_KEYS = ("listing", "product_detail", "stores")


def seed_structures(structures_dir: Path) -> list[dict[str, Any]]:
    rows = []
    if not structures_dir.exists():
        return rows
    for path in structures_dir.glob("*.json"):
        try:
            with open(path, "r", encoding="utf-8") as file:
                structure = json.load(file)
        except (OSError, json.JSONDecodeError):
            continue
        structure.setdefault("domain", path.stem)
        rows.append(structure)
    return rows


def targets_for(structure: dict[str, Any]) -> list[str]:
    return [key for key in TARGET_KEYS if target_fields(structure, key)]


def field_count(structure: dict[str, Any]) -> int:
    return sum(len(target_fields(structure, key)) for key in TARGET_KEYS)


def target_fields(structure: dict[str, Any], target: str) -> list[dict[str, Any]]:
    target_data = structure.get(target, {})
    return target_data.get("fields", []) if isinstance(target_data, dict) else []


def rule_summaries(
    rows: list[dict[str, Any]],
    raw_artifacts: Callable[[str, int], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rules = []
    for row in rows:
        structure = row.get("structure", {})
        domain = row.get("domain") or structure.get("domain")
        if not domain:
            continue
        rules.append({
            "domain": domain,
            "targets": targets_for(structure),
            "field_count": field_count(structure),
            "updated_at": row.get("updated_at"),
            "version": row.get("version"),
            "raw_artifact_count": len(raw_artifacts(domain, 80)),
            "has_raw_page": bool(raw_artifacts(domain, 1)),
        })
    return rules
