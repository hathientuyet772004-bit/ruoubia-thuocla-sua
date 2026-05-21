"""
Detector Analyzer — Công nghệ chẩn đoán sức khỏe website và khả năng thu thập dữ liệu.
Tự động phát hiện các lớp bảo mật, anti-bot và kiến trúc frontend của trang web.
"""
from __future__ import annotations

import re
import time
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("detector.analyzer")

from shared.config import settings

_HEADERS = {
    "User-Agent": settings.PLAYWRIGHT_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_ANTI_BOT_SIGNALS = [
    r"cloudflare", r"cf-browser-verification", r"captcha", r"hcaptcha", 
    r"ddos-guard", r"just a moment", r"enable javascript", r"access denied"
]

# ── Implementation ───────────────────────────────────────────────────────────

class SiteAnalyzer:
    """Chuyên viên chẩn đoán kỹ thuật cho Website."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)

    def diagnose(self, url: str) -> Dict[str, Any]:
        """Thực hiện chẩn đoán toàn diện cho một URL."""
        domain = urlparse(url).netloc or url
        logger.info(f"🔍 Đang chẩn đoán: {domain}")

        result = {
            "url": url,
            "domain": domain,
            "is_reachable": False,
            "status_code": None,
            "protection": {
                "anti_bot": False,
                "provider": None, # Cloudflare, etc.
            },
            "technology": {
                "js_required": False,
                "framework": None, # React, Vue, etc.
                "has_api_hints": False
            },
            "crawlability": {
                "score": 0, # 0-100
                "strategy_recommended": "mhtml", # api, html, headless, mhtml
                "notes": ""
            }
        }

        try:
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            result["is_reachable"] = True
            result["status_code"] = resp.status_code
            html = resp.text
        except Exception as e:
            result["crawlability"]["notes"] = f"Lỗi kết nối: {str(e)}"
            return result

        # 1. Kiểm tra Anti-bot
        self._check_protection(resp, html, result)

        # 2. Kiểm tra Công nghệ Frontend
        self._check_technology(html, result)

        # 3. Tính toán khả năng thu thập & Đề xuất chiến lược
        self._calculate_crawlability(result)

        return result

    def _check_protection(self, resp: requests.Response, html: str, result: Dict):
        # Kiểm tra status codes đặc thù
        if resp.status_code in (403, 429, 503):
            result["protection"]["anti_bot"] = True
        
        # Kiểm tra nội dung html
        lower_html = html.lower()
        for signal in _ANTI_BOT_SIGNALS:
            if re.search(signal, lower_html):
                result["protection"]["anti_bot"] = True
                if "cloudflare" in signal:
                    result["protection"]["provider"] = "Cloudflare"
                break
        
        # Kiểm tra headers
        if "cf-ray" in resp.headers or "server" in resp.headers and "cloudflare" in resp.headers["server"].lower():
            result["protection"]["anti_bot"] = True
            result["protection"]["provider"] = "Cloudflare"

    def _check_technology(self, html: str, result: Dict):
        soup = BeautifulSoup(html, "lxml")
        
        # JS Required check
        scripts = soup.find_all("script")
        if len(scripts) > 10 and len(soup.get_text()) < 500:
            result["technology"]["js_required"] = True

        # Framework detection
        html_str = str(html)
        if "__next" in html_str: result["technology"]["framework"] = "Next.js"
        elif "nuxt" in html_str: result["technology"]["framework"] = "Nuxt.js"
        elif "data-v-" in html_str: result["technology"]["framework"] = "Vue.js"
        elif "react" in html_str.lower(): result["technology"]["framework"] = "React"

        # API Hints
        api_patterns = [r"/api/v", r"/graphql", r"\.json\?"]
        if any(re.search(p, html_str) for p in api_patterns):
            result["technology"]["has_api_hints"] = True

    def _calculate_crawlability(self, result: Dict):
        score = 100
        strategy = "html"

        if result["protection"]["anti_bot"]:
            score -= 70
            strategy = "mhtml"
            result["crawlability"]["notes"] = "Bị chặn bởi hệ thống Anti-bot mạnh."
        elif result["technology"]["js_required"]:
            score -= 30
            strategy = "headless"
            result["crawlability"]["notes"] = "Yêu cầu render JavaScript (Playwright)."
        
        if result["technology"]["has_api_hints"] and not result["protection"]["anti_bot"]:
            strategy = "api"
            score += 10
            result["crawlability"]["notes"] = "Tiềm năng có API công khai."

        result["crawlability"]["score"] = max(0, min(100, score))
        result["crawlability"]["strategy_recommended"] = strategy

    def close(self):
        self.session.close()
