"""
MHTMLProcessor — Decode .mhtml files và tiền xử lý HTML.

Logic:
  - Parse .mhtml (multipart/related)
  - Trích xuất main HTML part
  - Detect encoding
  - Clean HTML (loại bỏ scripts, styles, unnecessary tags)
"""
from __future__ import annotations

import email
import logging
import chardet
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger("smart_crawler.mhtml_processor")

class MHTMLProcessor:
    """Xử lý decode và chuẩn hóa file .mhtml thành HTML sạch."""

    @staticmethod
    def decode_file(mhtml_path: str | Path) -> Optional[str]:
        """Decode file mhtml và trả về nội dung HTML chính."""
        path = Path(mhtml_path)
        if not path.exists():
            logger.error(f"File not found: {mhtml_path}")
            return None

        try:
            with open(path, 'rb') as f:
                msg = email.message_from_binary_file(f)

            # MHTML là một email-like format (multipart/related)
            # Chúng ta cần tìm phần có content-type là text/html
            html_content = None

            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/html":
                        payload = part.get_payload(decode=True)
                        if payload:
                            html_content = MHTMLProcessor._decode_payload(payload)
                            break
            else:
                # Không phải multipart, thử lấy payload trực tiếp
                html_content = MHTMLProcessor._decode_payload(msg.get_payload(decode=True))

            if html_content:
                logger.info(f"✅ Decoded MHTML: {path.name} ({len(html_content)} chars)")
                return html_content

        except Exception as e:
            logger.error(f"❌ Failed to decode MHTML {path.name}: {e}")

        return None

    @staticmethod
    def _decode_payload(payload: bytes) -> str:
        """Tự động phát hiện encoding và decode bytes."""
        if not payload:
            return ""
        
        # Thử UTF-8 trước
        try:
            return payload.decode('utf-8')
        except UnicodeDecodeError:
            pass

        # Dùng chardet để phát hiện encoding
        detection = chardet.detect(payload)
        encoding = detection.get('encoding') or 'utf-8'
        try:
            return payload.decode(encoding, errors='ignore')
        except:
            return payload.decode('latin-1', errors='ignore')

    @staticmethod
    def clean_html(html: str) -> str:
        """Làm sạch HTML để giảm tokens cho LLM và tăng hiệu quả selector."""
        if not html:
            return ""
        
        soup = BeautifulSoup(html, "lxml")
        
        # Xóa các tag không cần thiết cho extraction
        tags_to_remove = [
            "script", "style", "noscript", "iframe", "svg", 
            "header", "footer", "nav", "aside", "link", "meta"
        ]
        for tag in soup.find_all(tags_to_remove):
            tag.decompose()

        # Giữ lại các thuộc tính quan trọng, xóa các thuộc tính rác
        important_attrs = ["id", "class", "href", "src", "data-src", "data-lazy", "value"]
        for tag in soup.find_all(True):
            attrs = dict(tag.attrs)
            tag.attrs = {k: v for k, v in attrs.items() if k.lower() in important_attrs}

        # Trả về string (thu gọn whitespace)
        cleaned = soup.prettify()
        # Regex để thu gọn whitespace thừa
        import re
        cleaned = re.sub(r'\n\s*\n', '\n', cleaned)
        return cleaned
