"""
Validator — Thực hiện Self-validation loop (Step 6) để đảm bảo CSS selectors hoạt động đúng.
"""
from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional
from .template_crawler import TemplateCrawler
from .structure_generator import StructureGenerator

logger = logging.getLogger("smart_crawler.validator")

class CrawlerValidator:
    """
    Thực hiện kiểm tra tính đúng đắn của selectors bằng cách scrape thử một vài trang.
    """

    def __init__(self, generator: StructureGenerator):
        self.generator = generator

    def validate_structure(
        self, 
        domain: str, 
        structure: dict, 
        sample_urls: List[str],
        max_retries: int = 3
    ) -> dict:
        """
        Vòng lặp validation: thử scrape -> nếu fail (rỗng name/price) -> re-prompt Gemini.
        """
        current_structure = structure
        retry_count = 0

        while retry_count < max_retries:
            logger.info(f"  🔍 Validation Loop (Thử lần {retry_count + 1})...")
            
            results = self._test_scrape(domain, current_structure, sample_urls)
            is_valid, feedback = self._evaluate_results(results)

            if is_valid:
                logger.info("  ✅ Validation PASS!")
                return current_structure
            
            logger.warning(f"  ⚠️ Validation FAIL: {feedback}")
            
            # Re-prompt Gemini với feedback
            retry_count += 1
            if retry_count < max_retries:
                logger.info(f"  🧠 Re-prompting Gemini with feedback (Attempt {retry_count})...")
                current_structure = self._relearn_structure(domain, sample_urls[0], feedback)
                if not current_structure:
                    break
        
        logger.error(f"  ❌ Validation failed after {max_retries} attempts.")
        return current_structure

    def _test_scrape(self, domain: str, structure: dict, urls: List[str]) -> List[dict]:
        """Scrape thử các URL mẫu dùng structure hiện tại."""
        crawler = TemplateCrawler(domain, structure)
        results = []
        # Chỉ lấy 1 vài URL đầu tiên làm mẫu
        for url in urls[:5]:
            try:
                # Dùng trực tiếp _extract_item hoặc run đơn giản
                product = crawler._crawl_detail_page(url)
                if product:
                    results.append(product)
            except Exception as e:
                logger.debug(f"      Scrape fail cho {url}: {e}")
        return results

    def _evaluate_results(self, results: List[dict]) -> tuple[bool, str]:
        """Đánh giá kết quả scrape mẫu."""
        if not results:
            return False, "Không tìm thấy sản phẩm nào trên các trang mẫu."

        invalid_count = 0
        missing_fields = set()

        for p in results:
            # Kiểm tra các trường bắt buộc
            if not p.get("product_name"):
                invalid_count += 1
                missing_fields.add("product_name")
            if not p.get("price") or p.get("price") == "0":
                invalid_count += 1
                missing_fields.add("price")

        if invalid_count > len(results) / 2:
            return False, f"Hơn 50% sản phẩm bị lỗi. Thiếu các trường: {', '.join(missing_fields)}"

        return True, ""

    def _relearn_structure(self, domain: str, sample_url: str, feedback: str) -> Optional[dict]:
        """Yêu cầu Gemini học lại với feedback cụ thể."""
        # TODO: Implement re-prompt logic in StructureGenerator
        # Hiện tại mock bằng cách gọi lại generate_structure với force_refresh
        try:
            # Truyền feedback vào prompt (cần update StructureGenerator)
            return self.generator.generate_structure(domain, "", force_refresh=True)
        except Exception as e:
            logger.error(f"Error during re-learning: {e}")
            return None
