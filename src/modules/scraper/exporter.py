"""Phase 3 — DataExporter: saves scrape results to CSV, Excel, and JSON."""
from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import pandas as pd
    import openpyxl  # noqa: F401 — ensure engine is available

    _HAS_PANDAS = True
except ImportError:
    _HAS_PANDAS = False


class DataExporter:
    """Export a scrape-result dict to CSV / Excel / JSON."""

    def export_to_db(self, db_session):
        """Lưu dữ liệu vào database thông qua SQLAlchemy ORM."""
        from collector.models_orm import Product
        products = self._product_rows()
        for prod in products:
            # Map dict fields to Product ORM
            db_product = Product(
                name=prod.get("name"),
                price=prod.get("price"),
                description=prod.get("description"),
                url=prod.get("url"),
                source=self.site_name
            )
            db_session.add(db_product)
        db_session.commit()
        print(f"  ✅ Đã lưu {len(products)} sản phẩm vào database.")

    def __init__(self, data: dict, output_dir: Path):
        self.data = data
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        raw_site = data.get("source_site", "unknown")
        self.site_name = raw_site.replace(".", "_").replace("-", "_")
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._prefix = f"{self.site_name}_{self.timestamp}"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _to_dict(self, obj) -> dict:
        return asdict(obj) if not isinstance(obj, dict) else obj

    def _product_rows(self) -> list[dict]:
        return [self._to_dict(p) for p in self.data.get("products", [])]

    def _branch_rows(self) -> list[dict]:
        return [self._to_dict(b) for b in self.data.get("branches", [])]

    # ── CSV ───────────────────────────────────────────────────────────────────

    def to_csv(self) -> list[Path]:
        saved: list[Path] = []

        products = self._product_rows()
        if products:
            path = self.output_dir / f"{self._prefix}_products.csv"
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(products[0].keys()))
                writer.writeheader()
                writer.writerows(products)
            print(f"  ✅ CSV: {path}")
            saved.append(path)

        branches = self._branch_rows()
        if branches:
            path = self.output_dir / f"{self._prefix}_branches.csv"
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(branches[0].keys()))
                writer.writeheader()
                writer.writerows(branches)
            print(f"  ✅ CSV: {path}")
            saved.append(path)

        return saved

    # ── Excel ─────────────────────────────────────────────────────────────────

    def to_excel(self) -> Optional[Path]:
        if not _HAS_PANDAS:
            print("  ⚠️  pandas/openpyxl not installed — skipping Excel export.")
            return None

        path = self.output_dir / f"{self._prefix}.xlsx"
        products = self._product_rows()
        branches = self._branch_rows()
        cp = self.data.get("company_profile")

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            if products:
                pd.DataFrame(products).to_excel(
                    writer, sheet_name="Sản phẩm", index=False
                )
            if branches:
                pd.DataFrame(branches).to_excel(
                    writer, sheet_name="Chi nhánh", index=False
                )
            if cp:
                pd.DataFrame([self._to_dict(cp)]).to_excel(
                    writer, sheet_name="Công ty", index=False
                )
            stats = {
                "Chỉ số": [
                    "Tổng sản phẩm",
                    "Tổng chi nhánh",
                    "Trang đã crawl",
                    "Thời gian",
                ],
                "Giá trị": [
                    self.data.get("total_products", 0),
                    self.data.get("total_branches", 0),
                    self.data.get("pages_scraped", 0),
                    datetime.now().strftime("%d/%m/%Y %H:%M"),
                ],
            }
            pd.DataFrame(stats).to_excel(
                writer, sheet_name="Thống kê", index=False
            )

        print(f"  ✅ Excel: {path}")
        return path

    # ── JSON ──────────────────────────────────────────────────────────────────

    def to_json(self) -> Path:
        path = self.output_dir / f"{self._prefix}.json"
        cp = self.data.get("company_profile")

        export = {
            "metadata": {
                "site": self.site_name,
                "scraped_at": datetime.now().isoformat(),
                "total_products": self.data.get("total_products", 0),
                "total_branches": self.data.get("total_branches", 0),
                "pages_scraped": self.data.get("pages_scraped", 0),
            },
            "products": self._product_rows(),
            "branches": self._branch_rows(),
            "company_profile": self._to_dict(cp) if cp else {},
        }

        with open(path, "w", encoding="utf-8") as fh:
            json.dump(export, fh, ensure_ascii=False, indent=2)

        print(f"  ✅ JSON: {path}")
        return path
