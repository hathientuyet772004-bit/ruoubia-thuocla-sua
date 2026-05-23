from __future__ import annotations

import email
import logging
import quopri
from pathlib import Path

import chardet

log = logging.getLogger("admin_center.mhtml_processor")


class MHTMLProcessor:
    """Decode local MHTML fallback artifacts into HTML for selector previews."""

    @staticmethod
    def decode_file(mhtml_path: str | Path) -> str | None:
        path = Path(mhtml_path)
        if not path.exists():
            return None
        try:
            with open(path, "rb") as file:
                message = email.message_from_binary_file(file)
            html = None
            if message.is_multipart():
                for part in message.walk():
                    if part.get_content_type() == "text/html":
                        payload = part.get_payload(decode=True)
                        if payload:
                            html = MHTMLProcessor._decode_payload(payload)
                            break
            else:
                html = MHTMLProcessor._decode_payload(message.get_payload(decode=True))
            if html and "=3D" in html:
                html = MHTMLProcessor._decode_payload(quopri.decodestring(html.encode("utf-8")))
            return html
        except Exception as exc:
            log.warning("Could not decode MHTML %s: %s", path.name, exc)
            return None

    @staticmethod
    def _decode_payload(payload: bytes | None) -> str:
        if not payload:
            return ""
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError:
            encoding = chardet.detect(payload).get("encoding") or "utf-8"
            return payload.decode(encoding, errors="ignore")
