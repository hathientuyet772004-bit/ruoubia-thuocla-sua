import json
import logging
import hashlib
import os
import re
import time
from pathlib import Path
from bs4 import BeautifulSoup
from typing import Dict, Any

import google.generativeai as genai

logger = logging.getLogger("collector.ai_selector")

class AISelectorGenerator:
    """
    Sử dụng Gemini Flash để tự động phát hiện CSS Selectors từ mã nguồn HTML.
    Giúp Robot tự thích nghi với giao diện của bất kỳ website nào.
    """

    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash"):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for AISelectorGenerator")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.max_retries = int(os.getenv("GEMINI_MAX_RETRIES", "2"))
        self.prompt_version = os.getenv("GEMINI_PROMPT_VERSION", "2026-04-27.1")

        root_dir = Path(__file__).resolve().parents[3]
        self.cache_dir = Path(os.getenv("AI_SELECTOR_CACHE_DIR", str(root_dir / "outputs" / "ai_selector_cache")))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, *, url: str, html_sample: str) -> str:
        h = hashlib.sha256()
        h.update(self.prompt_version.encode("utf-8"))
        h.update(b"\0")
        h.update(url.encode("utf-8"))
        h.update(b"\0")
        h.update(html_sample[:2000].encode("utf-8", errors="ignore"))
        return h.hexdigest()

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _read_cache(self, key: str) -> Dict[str, Any] | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _write_cache(self, key: str, data: Dict[str, Any]) -> None:
        path = self._cache_path(key)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _clean_json(self, text: str) -> str:
        t = (text or "").strip()
        if t.startswith("```"):
            t = t.split("```", 1)[1]
            if t.startswith("json"):
                t = t[4:]
            t = t.strip()
        if t.endswith("```"):
            t = t[:-3].strip()
        return t

    def _parse_json(self, raw: str) -> Dict[str, Any]:
        cleaned = self._clean_json(raw)
        # Try the full text first
        try:
            obj = json.loads(cleaned)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            pass
        # Fallback: best-effort extract first JSON object
        m = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(1))
                return obj if isinstance(obj, dict) else {}
            except Exception:
                return {}
        return {}

    def _validate(self, data: Dict[str, Any]) -> bool:
        # Soft validation: accept partial, but require core keys to exist.
        required = {"item_container", "name_selector", "price_selector"}
        return required.issubset(set(data.keys()))

    def generate(self, url: str, html: str) -> Dict[str, Any]:
        """Phân tích HTML và trả về bộ quy luật trích xuất."""
        logger.info(f"🧠 [AI Selector] Đang phân tích cấu trúc trang: {url}")
        
        # Làm sạch HTML trước khi gửi AI để tiết kiệm token và tăng độ chính xác
        clean_html = self._prepare_html_sample(html)
        cache_key = self._cache_key(url=url, html_sample=clean_html)
        cached = self._read_cache(cache_key)
        if cached and self._validate(cached):
            logger.info("✅ [AI Selector] Cache hit")
            return cached

        prompt = f"""
        Bạn là chuyên gia trích xuất dữ liệu Web (Web Scraping Expert).
        Hãy phân tích HTML của trang web sau và tìm các CSS Selectors để thu thập danh sách sản phẩm.
        URL: {url}

        Yêu cầu trả về JSON thuần túy (không markdown, không giải thích) với cấu trúc:
        {{
            "item_container": "Selector bao quanh 1 ô sản phẩm (ví dụ: div.product-item)",
            "name_selector": "Selector lấy tên sản phẩm (tính từ item_container)",
            "price_selector": "Selector lấy giá sản phẩm",
            "image_selector": "Selector lấy ảnh sản phẩm (thẻ img)",
            "link_selector": "Selector lấy đường dẫn sản phẩm (thẻ a)",
            "pagination_next_selector": "Selector cho nút 'Trang sau' (nếu có)"
        }}

        HTML mẫu (đã được rút gọn):
        {clean_html}
        """

        # Tắt safety filters để tránh bị chặn khi phân tích trang rượu bia
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

        last_err = ""
        for attempt in range(1, self.max_retries + 2):
            try:
                t0 = time.perf_counter()
                response = self.model.generate_content(prompt, safety_settings=safety_settings)
                elapsed = round(time.perf_counter() - t0, 2)
                text = (response.text or "").strip()
                logger.info("⏱️  [AI Selector] latency=%ss chars=%s", elapsed, len(text))

                data = self._parse_json(text)
                if not self._validate(data):
                    last_err = "invalid/partial json"
                    continue

                try:
                    self._write_cache(cache_key, data)
                except Exception:
                    pass
                return data

            except Exception as e:
                last_err = str(e)
                continue

        logger.error("❌ AI Selector Generation failed after retries: %s", last_err)
        return {}

    def _prepare_html_sample(self, html: str) -> str:
        """Loại bỏ các phần rác và chỉ giữ lại cấu trúc quan trọng."""
        soup = BeautifulSoup(html, "lxml")
        
        # Xóa các thành phần không liên quan đến sản phẩm
        for tag in soup(["script", "style", "footer", "nav", "svg", "path", "iframe"]):
            tag.decompose()
            
        # Lấy một đoạn HTML đủ lớn (khoảng 30k ký tự) tập trung vào phần body
        body = soup.find("body")
        if body:
            content = body.prettify()
            return content[:30000]
        return html[:20000]

if __name__ == "__main__":
    # Script test nhanh
    import requests
    from shared.config import settings

    api_key = settings.GEMINI_API_KEY
    generator = AISelectorGenerator(api_key)
    
    test_url = "https://ruoutot.net/danh-muc/vang-phap"
    print(f"🕵️ Thử nghiệm lấy Selector cho: {test_url}")
    
    resp = requests.get(test_url, timeout=15)
    selectors = generator.generate(test_url, resp.text)
    
    print("\n✅ Bộ Selector AI đề xuất:")
    print(json.dumps(selectors, indent=2, ensure_ascii=False))
