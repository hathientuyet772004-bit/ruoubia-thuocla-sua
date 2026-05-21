"""
Router: Proxy endpoints
GET /proxy       → JSON {html, status, engine}
GET /view-proxy  → HTMLResponse (browsable proxy với link rewriting)
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from shared.services import fetch_html, rewrite_links_for_proxy, inject_proxy_script

router = APIRouter(tags=["proxy"])


@router.get("/proxy")
async def proxy_url(url: str):
    """Fetch trang qua Playwright, trả về JSON chứa HTML."""
    try:
        html = await fetch_html(url)
        return {"html": html, "status": 200, "engine": "playwright"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/view-proxy")
async def view_proxy(url: str, request: Request):
    """
    Browsable proxy: fetch trang, viết lại links để điều hướng qua proxy,
    trả về HTMLResponse có thể nhúng trực tiếp vào iframe.
    """
    proxy_base = str(request.base_url).rstrip("/") + "/api/view-proxy?url="
    try:
        html = await fetch_html(url)
        html = rewrite_links_for_proxy(html, url, proxy_base)
        html = inject_proxy_script(html, url)
        return HTMLResponse(
            content=html,
            headers={"X-Frame-Options": "ALLOWALL", "Content-Security-Policy": ""},
        )
    except Exception as e:
        return HTMLResponse(content=f"<html><body><h1>Error: {e}</h1></body></html>")
