
import asyncio
import sys
import os
from pathlib import Path

# Setup paths
sys.path.append(str(Path(os.getcwd()) / "src"))
sys.path.append(str(Path(os.getcwd()) / "src" / "modules" / "collector" / "backend"))

from services.collector_service import collect_one_url, CollectConfig

async def fast_bootstrap():
    # Danh sách URL mẫu tiêu biểu cho mỗi nhóm
    sample_urls = [
        {"url": "https://winemart.vn/ruou-vang-chateau-ducluzeau/", "source": "winemart.vn"},
        {"url": "https://winemart.vn/ruou-vang-f-negroamaro-del-salento/", "source": "winemart.vn"},
        {"url": "https://www.kidsplaza.vn/sua-meiji-so-0-800g-noi-dia-nhat.html", "source": "kidsplaza.vn"},
        {"url": "https://www.kidsplaza.vn/sua-bot-enfamil-a-neuropro-so-1-400g.html", "source": "kidsplaza.vn"},
        {"url": "https://thuoclachinhhang.com/san-pham/thuoc-la-xach-tay-nhap-khau-raison-ice-pres-han-quoc/", "source": "thuoclachinhhang.com"}
    ]
    
    cfg = CollectConfig(max_products_per_domain=10)
    print("🚀 Bắt đầu thu thập nhanh (Bỏ qua Discovery)...")
    
    for item in sample_urls:
        url = item["url"]
        source = item["source"]
        print(f"--- Collecting: {url} ---")
        try:
            res = await collect_one_url(url, cfg=cfg, source=source)
            print(f"✅ Đã nạp thành công: {url} -> status: {res.get('status')}")
        except Exception as e:
            print(f"⚠️ Lỗi {url}: {e}")

if __name__ == "__main__":
    asyncio.run(fast_bootstrap())
