"""
Detector Scanner — Sử dụng Gemini AI để khám phá cấu trúc URL và sơ đồ trang web.
"""
from __future__ import annotations

import json
import logging
from typing import Dict, Any, List
from shared.services.site_analyzer import SiteAnalyzer
from shared.config import settings
import google.generativeai as genai
import os

logger = logging.getLogger("detector.scanner")

class IntelligenceScanner:
    """Khám phá thông minh cấu trúc Website bằng AI."""

    def __init__(self, api_key: str = None, model: str = None):
        self.analyzer = SiteAnalyzer()
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model or settings.GEMINI_MODEL
        
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
        else:
            self.model = None

    def scan(self, url: str) -> Dict[str, Any]:
        """Thực hiện quét chẩn đoán + AI mapping."""
        # 1. Chẩn đoán kỹ thuật
        diagnosis = self.analyzer.diagnose(url)
        
        # 2. Khám phá cấu trúc bằng AI (nếu có thể truy cập trực tiếp)
        site_map = {
            "categories": [],
            "product_url_pattern": None,
            "navigation_menu": []
        }

        if diagnosis["crawlability"]["strategy_recommended"] != "mhtml" and self.model:
            try:
                resp = self.analyzer.session.get(url, timeout=10)
                site_map = self._ai_discover_structure(url, resp.text)
            except Exception as e:
                logger.warning(f"AI discovery failed: {e}")

        return {
            "diagnosis": diagnosis,
            "site_map": site_map,
            "conclusion": self._wrap_conclusion(diagnosis)
        }

    def _ai_discover_structure(self, url: str, html: str) -> Dict:
        """Sử dụng cơ chế lọc link thông minh trước khi gửi AI."""
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        
        soup = BeautifulSoup(html, "lxml")
        links_info = []
        
        # Chỉ lấy các link có text hoặc nằm trong cấu trúc menu/nav
        for a in soup.find_all("a", href=True):
            href = a.get("href")
            text = a.get_text(strip=True)
            # Bỏ qua các link rác (javascript:, #, tel:, mailto:)
            if any(href.startswith(p) for p in ["#", "javascript", "tel", "mailto"]):
                continue
            
            full_url = urljoin(url, href)
            if len(text) > 2:
                links_info.append(f"Title: {text} | URL: {full_url}")

        # Lấy Unique links để tiết kiệm token
        unique_links = list(set(links_info))[:250] # 250 links là đủ để AI hiểu
        links_text = "\n".join(unique_links)

        prompt = f"""
        Phân tích danh sách các đường dẫn từ website: {url}
        Hãy trích xuất cấu trúc trang web JSON:
        1. "categories": Danh sách các URL trang danh mục sản phẩm (vd: /danh-muc/ vang-phap, /c/sua-bot).
        2. "product_url_pattern": Quy luật URL của trang chi tiết sản phẩm.
        3. "navigation_menu": Các menu điều hướng chính.

        Danh sách Links:
        {links_text}

        Trả về JSON thuần túy (không markdown):
        {{
            "categories": [],
            "product_url_pattern": "",
            "navigation_menu": [{{ "label": "", "url": "" }}]
        }}
        """
        try:
            # Tắt bộ lọc an toàn để AI không chặn nội dung rượu/bia khi phân tích kỹ thuật
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            
            response = self.model.generate_content(prompt, safety_settings=safety_settings)
            text = response.text.strip()
            
            import re
            json_match = re.search(r"(\{.*\})", text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            
            text_cleaned = text.replace("```json", "").replace("```", "").strip()
            return json.loads(text_cleaned)
        except Exception as e:
            logger.warning(f"AI Smart Discovery failed: {e}")
            return {"categories": [], "product_url_pattern": None, "navigation_menu": []}

    def _wrap_conclusion(self, diagnosis: Dict) -> str:
        strat = diagnosis["crawlability"]["strategy_recommended"]
        if strat == "mhtml":
            return "Trang web này được bảo vệ rất kỹ. KHÔNG THỂ thu thập tự động. Cần dùng Web Collector (MHTML)."
        elif strat == "headless":
            return "Trang web sử dụng cơ chế render động. Cần dùng Playwright để thu thập."
        elif strat == "api":
            return "Trang web cực kỳ 'thoáng', có thể thu thập qua API với tốc độ cao."
        else:
            return "Trang web có thể thu thập tự động một cách dễ dàng bằng HTML Scraper."

    def close(self):
        self.analyzer.close()
