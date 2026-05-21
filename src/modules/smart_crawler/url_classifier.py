"""
URLClassifier — Phân loại URL (Step 3) theo 3 tầng để giảm thiểu rác và xác định đúng trang sản phẩm.
"""
from __future__ import annotations

import re
import logging
from typing import List, Dict, Any, Optional
from .structure_generator import StructureGenerator

logger = logging.getLogger("smart_crawler.url_classifier")

class URLClassifier:
    """
    Tier 1: Regex filter (loại bỏ 80% rác như /blog, /news, /contact...)
    Tier 2: Gemini sample (Gửi 20 URL cho Gemini để nhận diện pattern)
    Tier 3: Pattern application (Phân loại toàn bộ dựa trên pattern đã học)
    """

    def __init__(self, generator: StructureGenerator):
        self.generator = generator
        self.patterns = {} # domain -> pattern regex

    def classify_urls(self, domain: str, urls: List[str]) -> List[str]:
        """Trả về danh sách URLs được xác định là Product Detail Pages."""
        # 1. Tier 1: Regex Filter
        filtered_urls = self._tier1_regex_filter(urls)
        if not filtered_urls:
            return []

        # 2. Tier 2 & 3: LLM Pattern Recognition
        if domain not in self.patterns:
            logger.info(f"  🧠 Tier 2: Learning URL patterns for {domain}...")
            self.patterns[domain] = self._tier2_learn_pattern(domain, filtered_urls[:30])

        pattern = self.patterns[domain]
        if not pattern:
            return filtered_urls # Fallback: return everything filtered if pattern learning fails

        # Tier 3: Apply pattern
        product_urls = [u for u in filtered_urls if re.search(pattern, u)]
        logger.info(f"  ✅ Tier 3: Classified {len(product_urls)}/{len(urls)} as product pages.")
        return product_urls

    def _tier1_regex_filter(self, urls: List[str]) -> List[str]:
        """Loại bỏ các URLs chắc chắn không phải sản phẩm."""
        junk_patterns = [
            r"/blog/", r"/news/", r"/tin-tuc/", r"/huong-dan/", 
            r"/chinh-sach/", r"/contact", r"/about", r"/gioi-thieu",
            r"\.jpg$", r"\.png$", r"\.pdf$", r"\.zip$"
        ]
        results = []
        for u in urls:
            is_junk = any(re.search(p, u, re.IGNORECASE) for p in junk_patterns)
            if not is_junk:
                results.append(u)
        return results

    def _tier2_learn_pattern(self, domain: str, sample_urls: List[str]) -> Optional[str]:
        """Dùng Gemini để tìm ra Regex Pattern cho product page."""
        # Mock logic: Nếu là BHX
        if "bachhoaxanh.com" in domain:
            return r"/product/" # Dummy
        
        prompt = f"""
        Analyze these URLs from the domain "{domain}" and identify which ones are likely PRODUCT DETAIL pages (not category, not news).
        URLs:
        {chr(10).join(sample_urls)}
        
        Return ONLY a simple regex pattern that matches the product detail URLs. 
        Example: /product/[0-9]+
        """
        # Trả về pattern đơn giản hoặc gọi LLM
        # TODO: Link with StructureGenerator's Gemini caller
        return None 
