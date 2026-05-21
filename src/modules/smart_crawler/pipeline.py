"""
AdaptiveCrawler Pipeline — Điều phối toàn bộ quy trình crawl và extract.

Flow:
  URL → Analyze → Strategy
    ├── Direct (API/HTML) → Template Crawler (CSS Selectors + AI Fallback)
    └── MHTML → Decoder → AI Extraction
"""
from __future__ import annotations

import logging
import time
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse

from .domain_analyzer import DomainAnalyzer
from .structure_generator import StructureGenerator
from .template_crawler import TemplateCrawler, CrawledProduct
from .db_manager import DatabaseManager
from .mhtml_processor import MHTMLProcessor
from .headless_crawler import HeadlessCrawler
from .validator import CrawlerValidator
from .url_classifier import URLClassifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("smart_crawler.pipeline")

class AdaptiveCrawler:
    """Hệ thống crawl thích nghi: Tự hiểu website, chọn chiến lược và tối ưu AI."""

    def __init__(self):
        self.db = DatabaseManager()
        self.analyzer = DomainAnalyzer()
        self.generator = StructureGenerator()
        self.validator = CrawlerValidator(self.generator)
        self.classifier = URLClassifier(self.generator)

    def run(self, url: str, max_pages: int = 20, force_analyze: bool = False) -> Dict[str, Any]:
        """Thực hiện full pipeline cho một URL/Domain."""
        domain_name = urlparse(url).netloc
        logger.info(f"🚀 BẮT ĐẦU PIPELINE: {url}")

        # 1. Phân tích Domain Intelligence
        domain_info = self._get_or_analyze_domain(url, force_analyze)
        strategy = domain_info["strategy"]
        
        # 2. Xử lý theo Strategy
        if strategy == "mhtml":
            logger.warning(f"  [STRATEGY] {domain_name} bị chặn anti-bot.")
            logger.info("  💡 FLOW: Dùng Collector thủ công lưu .mhtml sau đó chạy 'process_mhtml'")
            return {"status": "manual_collection_required", "domain_info": domain_info}

        # 3. Lấy/Tạo Structure (Selectors)
        structure = self._get_or_generate_structure(url, domain_info)
        if not structure:
            logger.error("  ❌ Không thể xác định cấu trúc trang. Hủy bỏ.")
            return {"status": "failed_structure_analysis"}

        # 4. Khởi tạo Crawler phù hợp
        if strategy == "headless":
            logger.info("  🎭 Sử dụng Headless Crawler (Playwright)")
            crawler = HeadlessCrawler(
                base_url=url,
                structure=structure,
                generator=self.generator
            )
        else:
            crawler = TemplateCrawler(
                base_url=url,
                structure=structure,
                generator=self.generator
            )

        # 5. Bắt đầu Crawl Session
        session_id = self.db.start_session(domain_name, strategy, url)
        logger.info(f"  🆔 Session ID: {session_id}")

        all_products: List[CrawledProduct] = []
        try:
            # 5.1 Crawl Listing Pages
            # Thử lấy các listing URLs từ structure (do LLM phát hiện) hoặc dùng chính URL đầu vào
            listing_urls = structure.get("listing_urls", [])
            if not listing_urls:
                listing_urls = [url]
            else:
                # Chuẩn hóa URLs
                listing_urls = [crawler._normalize_url(u) for u in listing_urls]

            # 5.1 Step 2: Thu thập pool URL thô
            product_urls_pool = set()
            for l_url in listing_urls:
                found_urls = crawler.crawl_listing(l_url, max_pages=max_pages)
                product_urls_pool.update(found_urls)

            # 5.2 Step 3: Phân loại URL (3 tầng)
            product_urls = self.classifier.classify_urls(domain_name, list(product_urls_pool))
            
            if not product_urls:
                logger.warning("  ⚠️ Không phân loại được product URL nào. Dùng danh sách thô.")
                product_urls = list(product_urls_pool)

            logger.info(f"  🎯 Tổng cộng tìm thấy {len(product_urls)} sản phẩm sau phân loại")

            # 5.2 Crawl Product Detail Pages
            for i, p_url in enumerate(product_urls):
                logger.info(f"  [{i+1}/{len(product_urls)}] Crawling: {p_url}")
                p_data = crawler.crawl_product(p_url)
                
                if p_data:
                    all_products.append(p_data)
                    # Log page success
                    self.db.log_page(session_id, {
                        "page_url": p_url,
                        "page_type": "product_detail",
                        "products_found": 1,
                        "used_fallback": p_data.extraction_method == "llm_fallback"
                    })
                
                # Batch save mỗi 10 products
                if len(all_products) >= 10:
                    self._save_products_batch(session_id, domain_name, all_products[-10:], strategy)

            # Lưu số còn lại
            if len(all_products) % 10 != 0:
                self._save_products_batch(session_id, domain_name, all_products[-(len(all_products) % 10):], strategy)

            # 6. Hoàn thành Session
            stats = crawler.stats
            self.db.update_session_stats(session_id, {
                "total_pages": stats["pages_crawled"],
                "total_products": len(all_products),
                "fallback_count": stats["fallback_count"],
                "success_rate": stats["success_rate"],
                "status": "completed",
                "error_message": None
            })

            logger.info(f"✅ PIPELINE HOÀN THÀNH: {len(all_products)} sản phẩm được lưu.")
            return {"status": "success", "total_products": len(all_products), "session_id": session_id}

        except Exception as e:
            logger.error(f"❌ Pipeline error: {e}")
            self.db.update_session_stats(session_id, {
                "total_pages": 0,
                "total_products": len(all_products),
                "fallback_count": 0,
                "success_rate": 0,
                "status": "failed",
                "error_message": str(e)
            })
            return {"status": "failed", "error": str(e)}

    # ── MHTML Workflow ────────────────────────────────────────────────────────

    def process_mhtml(self, mhtml_path: str, domain_url: str) -> bool:
        """Quy trình ETL cho file MHTML (Dùng sau khi collector thu thập file)."""
        domain_name = urlparse(domain_url).netloc
        processor = MHTMLProcessor()
        
        # 1. Decode & Clean
        html = processor.decode_file(mhtml_path)
        if not html:
            return False
        
        clean_html = processor.clean_html(html)

        # 2. Get structure (nếu chưa có)
        domain_info = {"domain": domain_name, "strategy": "mhtml"}
        structure = self._get_or_generate_structure(domain_url, domain_info, html_sample=clean_html)
        if not structure:
            return False

        # 3. Extract using Hybrid method
        # Dùng TemplateCrawler nhưng đưa soup local vào thay vì fetch URL
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        
        crawler = TemplateCrawler(base_url=domain_url, structure=structure, generator=self.generator)
        session_id = self.db.start_session(domain_name, "mhtml", "local_file")

        # Giả định đây là trang product litsing trong MHTML
        fields_cfg = {f["name"]: f for f in structure.get("listing", {}).get("fields", [])}
        listing_cfg = structure.get("listing", {})
        
        urls = crawler._extract_listing_urls(soup, listing_cfg, fields_cfg)
        logger.info(f"  Found {len(urls)} products in MHTML")

        # Ở strategy MHTML, thường chúng ta extract data trực tiếp từ listing 
        # vì không thể click vào URL Detail được dễ dàng (trừ khi có nhiều file MHTML)
        # Tạm thời extract dữ liệu listing
        
        products = []
        for i, item in enumerate(crawler._get_items(soup, listing_cfg)):
            # Tương tự logic _parse_products_from_page trong SmartScraper cũ
            p_name = crawler._extract_field(item, fields_cfg.get("product_name", {}))
            if not p_name: continue
            
            p_data = {
                "product_name": p_name,
                "price": crawler._extract_field(item, fields_cfg.get("price", {})),
                "product_url": crawler._normalize_url(crawler._extract_field(item, fields_cfg.get("product_url", {}))),
                "image_url": crawler._normalize_url(crawler._extract_field(item, fields_cfg.get("image_url", {}))),
                "domain": domain_name,
                "session_id": session_id,
                "source_strategy": "mhtml"
            }
            # Clean numeric price
            import re
            nums = re.sub(r"[^\d]", "", p_data["price"])
            p_data["price_numeric"] = float(nums) if nums else 0.0
            
            products.append(p_data)

        if products:
            self.db.save_products(products)
            self.db.update_session_stats(session_id, {
                "total_pages": 1,
                "total_products": len(products),
                "fallback_count": 0,
                "success_rate": 1.0,
                "status": "completed",
                "error_message": None
            })
            logger.info(f"✅ Đã extract {len(products)} sản phẩm từ MHTML.")
            return True
        
        return False

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_or_analyze_domain(self, url: str, force: bool) -> Dict[str, Any]:
        domain_name = urlparse(url).netloc
        if not force:
            existing = self.db.get_domain_info(domain_name)
            if existing:
                logger.info(f"  [DB] Đã tìm thấy thông tin domain: {existing['strategy'].upper()}")
                return existing

        info = self.analyzer.analyze(url)
        self.db.upsert_domain(info)
        return info

    def _get_or_generate_structure(self, url: str, domain_info: Dict[str, Any], html_sample: str = None) -> Optional[Dict[str, Any]]:
        domain_name = domain_info["domain"]
        
        # 1. Thử lấy từ DB
        existing = self.db.get_active_structure(domain_name)
        if existing:
            logger.info("  [DB] Sử dụng structure đã lưu.")
            return existing

        # 2. Nếu không có, generate mới
        if not html_sample:
            # Fetch sample
            import requests
            try:
                resp = requests.get(url, timeout=15, headers=self.analyzer._session.headers)
                html_sample = resp.text
            except:
                logger.error("  ❌ Không thể lấy sample HTML để phân tích structure.")
                return None

        structure = self.generator.generate_structure(domain_name, html_sample)
        
        # 3. Step 6: Self-validation loop
        if structure:
            logger.info(f"  🔍 Bắt đầu vòng lặp self-validation cho {domain_name}...")
            # Lấy 1 vài URL mẫu từ listing_urls hoặc dùng chính URL sample
            sample_urls = structure.get("listing_urls", [])[:2]
            if not sample_urls:
                sample_urls = [url]
            
            validated_structure = self.validator.validate_structure(domain_name, structure, sample_urls)
            if validated_structure:
                structure = validated_structure
                self.db.save_structure(domain_name, structure)
        
        return structure

    def _check_drift(self, domain: str, results: List[CrawledProduct]) -> None:
        """Step 9: Kiểm tra drift (tỷ lệ null_price > 10%)."""
        if not results: return
        
        null_prices = sum(1 for p in results if not p.price_numeric)
        drift_rate = null_prices / len(results)
        
        if drift_rate > 0.1:
            logger.warning(f"  🚨 DRIFT DETECTED: {domain} (Rate: {drift_rate:.1%}). Invaliding cache...")
            # TODO: Add invalidate_structure method in DB manager
            # self.db.invalidate_structure(domain)

    def _save_products_batch(self, session_id: str, domain: str, products: List[CrawledProduct], strategy: str):
        data = []
        for p in products:
            d = p.to_dict()
            d["session_id"] = session_id
            d["domain"] = domain
            d["source_strategy"] = strategy
            data.append(d)
        
        self.db.save_products(data)

    def close(self):
        self.db.close()
        self.analyzer.close()
