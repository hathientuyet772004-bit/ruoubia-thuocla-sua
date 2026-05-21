"""
LakehouseETL — Luồng xử lý ETL batch từ Lakehouse (MinIO).
Sử dụng chung logc extractor với Smart Crawler.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup

from .minio_lakehouse import MinIOLakehouse
from .structure_generator import StructureGenerator
from .template_crawler import TemplateCrawler, CrawledProduct
from .db_manager import DatabaseManager
from .mhtml_processor import MHTMLProcessor

logger = logging.getLogger("smart_crawler.lakehouse_etl")

class LakehouseETL:
    """Hệ thống xử lý batch dữ liệu từ Lakehouse."""

    def __init__(self):
        self.minio = MinIOLakehouse()
        self.db = DatabaseManager()
        self.generator = StructureGenerator()

    def process_domain(self, category: str, domain: str, files: List[str] = None) -> Dict[str, Any]:
        """
        Xử lý toàn bộ hoặc một nhóm file của một domain trong Lakehouse.
        """
        logger.info(f"🟣 [LAKEHOUSE] Bắt đầu xử lý: {category}/{domain}")
        
        # 1. Khởi tạo Job
        if not files:
            files = self.minio.list_files(category, domain)
        
        if not files:
            logger.warning(f"  ⚠️  Không tìm thấy file nào để xử lý.")
            return {"status": "no_files_found"}

        job_id = self._create_job(category, domain, len(files))
        
        # 2. Lấy structure (dùng file đầu tiên làm mẫu nếu chưa có structure)
        sample_html = self.minio.get_file_content(files[0])
        if not sample_html:
            self._update_job(job_id, {"status": "failed", "error_message": "Cannot load sample file"})
            return {"status": "failed"}

        # Giả sử base_url dựa trên domain
        base_url = f"https://{domain}"
        structure = self._get_or_generate_structure(domain, base_url, sample_html)
        
        if not structure:
            self._update_job(job_id, {"status": "failed", "error_message": "Structure analysis failed"})
            return {"status": "failed"}

        # 3. Khởi tạo extractor (TemplateCrawler mode)
        crawler = TemplateCrawler(base_url=base_url, structure=structure, generator=self.generator)
        
        # 4. Loop xử lý từng file
        processed_count = 0
        success_count = 0
        fallback_count = 0
        all_products = []

        for obj_name in files:
            logger.info(f"  📄 Processing {processed_count+1}/{len(files)}: {obj_name}")
            html = self.minio.get_file_content(obj_name)
            if not html:
                processed_count += 1
                continue

            # Xử lý nếu là MHTML
            if obj_name.endswith('.mhtml'):
                html = MHTMLProcessor.clean_html(MHTMLProcessor._decode_payload(html.encode('utf-8')))

            # Extract products từ HTML
            products = self._extract_from_html(html, crawler, obj_name)
            
            for p in products:
                success_count += 1
                if p.get("extraction_method") == "llm_fallback":
                    fallback_count += 1
                all_products.append(p)

            processed_count += 1
            
            # Cập nhật tiến độ mỗi 5 file
            if processed_count % 5 == 0:
                self._update_job(job_id, {
                    "processed_files": processed_count,
                    "success_count": success_count,
                    "fallback_count": fallback_count
                })
            
            # Save batch
            if len(all_products) >= 20:
                self.db.save_products(all_products)
                all_products = []

        # Lưu nốt
        if all_products:
            self.db.save_products(all_products)

        # 5. Hoàn thành Job
        final_stats = {
            "processed_files": processed_count,
            "success_count": success_count,
            "fallback_count": fallback_count,
            "status": "completed"
        }
        self._update_job(job_id, final_stats)
        
        logger.info(f"✅ [LAKEHOUSE] Xong: {success_count} products từ {processed_count} files.")
        return final_stats

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _extract_from_html(self, html: str, crawler: TemplateCrawler, source_name: str) -> List[Dict[str, Any]]:
        """Dùng logic crawler để extract từ HTML string."""
        soup = BeautifulSoup(html, "lxml")
        listing_cfg = crawler.structure.get("listing", {})
        fields_cfg = {f["name"]: f for f in listing_cfg.get("fields", [])}
        
        extracted = []
        # Thử coi đây là trang listing
        items = crawler._get_items(soup, listing_cfg)
        
        if not items:
            # Có thể là trang detail? Thử extract như 1 product
            p = crawler._extract_product(soup, {f["name"]: f for f in crawler.structure.get("product_detail", {}).get("fields", [])}, source_name, 1)
            if p.product_name:
                d = p.to_dict()
                d["source_strategy"] = "lakehouse"
                d["domain"] = crawler.domain
                extracted.append(d)
        else:
            for item in items:
                p_name = crawler._extract_field(item, fields_cfg.get("product_name", {}))
                if p_name:
                    p_url = crawler._normalize_url(crawler._extract_field(item, fields_cfg.get("product_url", {})))
                    p_data = {
                        "product_name": p_name,
                        "price": crawler._extract_field(item, fields_cfg.get("price", {})),
                        "product_url": p_url or f"{source_name}#item",
                        "image_url": crawler._normalize_url(crawler._extract_field(item, fields_cfg.get("image_url", {}))),
                        "domain": crawler.domain,
                        "source_strategy": "lakehouse",
                        "extraction_method": "selector"
                    }
                    import re
                    nums = re.sub(r"[^\d]", "", p_data["price"])
                    p_data["price_numeric"] = float(nums) if nums else 0.0
                    extracted.append(p_data)

        # Nếu hoàn toàn không có gì, fallback LLM cho cả cục HTML (nếu là product page)
        if not extracted and len(html) > 1000:
            llm_data = self.generator.extract_product_fallback(html[:8000])
            if llm_data and llm_data.get("product_name"):
                p_data = llm_data
                p_data["extraction_method"] = "llm_fallback"
                p_data["source_strategy"] = "lakehouse"
                p_data["domain"] = crawler.domain
                extracted.append(p_data)

        return extracted

    def _get_or_generate_structure(self, domain: str, url: str, html: str) -> Optional[Dict[str, Any]]:
        existing = self.db.get_active_structure(domain)
        if existing:
            return existing
        
        structure = self.generator.generate_structure(domain, html)
        if structure:
            self.db.save_structure(domain, structure)
        return structure

    def _create_job(self, category: str, domain: str, total_files: int) -> int:
        sql = """
            INSERT INTO sc_lakehouse_jobs (category, domain, total_files, status)
            VALUES (%s, %s, %s, 'running') RETURNING id
        """
        with self.db._get_conn().cursor() as cur:
            cur.execute(sql, (category, domain, total_files))
            return cur.fetchone()[0]

    def _update_job(self, job_id: int, stats: Dict[str, Any]):
        fields = ", ".join([f"{k} = %({k})s" for k in stats.keys()])
        sql = f"UPDATE sc_lakehouse_jobs SET {fields}, updated_at = NOW() WHERE id = %(id)s"
        params = {"id": job_id, **stats}
        with self.db._get_conn().cursor() as cur:
            cur.execute(sql, params)
