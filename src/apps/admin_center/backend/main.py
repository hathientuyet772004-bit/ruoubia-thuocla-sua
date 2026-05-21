from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, text
import uvicorn
import sys
from pathlib import Path

import csv
import io
import os
import json
from datetime import datetime
from urllib.parse import urlparse

# Add src and collector backend to path
project_root = Path(__file__).resolve().parents[4]
src_dir = project_root / "src"
collector_backend = src_dir / "modules" / "collector" / "backend"

sys.path.append(str(src_dir))
sys.path.append(str(collector_backend))

from shared.config import settings
from modules.collector.backend.db.database import get_db, engine, Base
from modules.collector.backend.models.orm import Source, Visit
from modules.collector.backend.routers.proxy import router as proxy_proxy
from modules.collector.backend.routers.collect import router as collect_router
from modules.collector.backend.routers.interactive import router as interactive_router

# Immediate initialization
print("🚀 Initializing database tables...")
try:
    Base.metadata.create_all(bind=engine)
    print("📁 Tables check complete.")
except Exception as e:
    print(f"⚠️ Warning: Database init failed: {e}")

app = FastAPI(title="Admin Center API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Schemas ---
class SourceSchema(BaseModel):
    name: str
    url: str
    type: str
    category: str
    note: str = None

# --- Startup Sync ---
@app.on_event("startup")
def init_data():
    db = next(get_db())
    print("🔍 Checking if sources need seeding...")
    try:
        count = db.query(Source).count()
        print(f"Current source count: {count}")
        if count == 0:
            print("🌱 Seeding sources from urls.csv...")
            csv_path = src_dir / "core" / "urls.csv"
            print(f"Looking for CSV at: {csv_path}")
            if csv_path.exists():
                with open(csv_path, mode='r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        source = Source(
                            name=row.get("Tên Website"),
                            url=row.get("URL"),
                            type=row.get("Loại hình"),
                            category=row.get("Danh mục chính"),
                            note=row.get("Ghi chú")
                        )
                        db.add(source)
                db.commit()
                print("✅ Seeded sources successfully.")
            else:
                print(f"❌ CSV not found at {csv_path}")
    except Exception as e:
        print(f"❌ Error during startup sync: {e}")
        db.rollback()

# --- Job Monitor: Theo dõi tiến độ ---
@app.get("/api/jobs")
async def get_jobs(limit: int = 50):
    """Lấy danh sách các tệp đang xử lý và trạng thái của chúng"""
    jobs = []
    raw_dir = project_root / "store" / "raw"
    output_dir = project_root / "store" / "outputs"
    
    if not raw_dir.exists():
        return []

    # Quét tất cả file JSON trong outputs một lần để tối ưu
    output_files = [f.name for f in output_dir.glob("*.json")] if output_dir.exists() else []
    raw_files = list(raw_dir.glob("**/*.meta.json"))

    for meta_file in raw_files:
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
                
            filename = meta_file.name.replace(".meta.json", "")
            source = meta.get("domain", meta_file.parent.name)
            
            # Fuzzy match: Kiểm tra xem filename có nằm trong bất kỳ file output nào không
            # Ví dụ: filename là "ruoutot_net_page1", output là "ruoutot_net_page1_2024.json"
            is_completed = any(filename in of for of in output_files)
            
            status = "Pending"
            if is_completed:
                status = "Completed"
            elif (meta_file.parent / f"{filename}.error").exists():
                status = "Failed"
            
            jobs.append({
                "id": filename,
                "filename": filename,
                "source": source,
                "status": status,
                "timestamp": datetime.fromtimestamp(os.path.getmtime(meta_file)).isoformat()
            })
        except:
            continue

    # Sắp xếp mới nhất
    jobs.sort(key=lambda x: x["timestamp"], reverse=True)
    return jobs[:limit]

@app.post("/api/jobs/retry/{job_id}")
async def retry_job(job_id: str):
    """Giả lập chạy lại tiến độ trích xuất AI"""
    # Logic thực tế sẽ là gửi ID này vào Queue hoặc gọi AI Worker
    print(f"🔄 Retrying job: {job_id}")
    return {"message": f"Job {job_id} has been queued for re-processing."}

@app.get("/api/jobs/logs/{job_id}")
async def get_job_logs(job_id: str):
    """Lấy log chi tiết của một Job từ Filesystem"""
    raw_dir = project_root / "store" / "raw"
    output_dir = project_root / "store" / "outputs"
    
    logs = {
        "job_id": job_id,
        "events": [],
        "metadata": {},
        "error": None,
        "output_summary": None
    }
    
    # 1. Tìm tệp meta trong store/raw
    meta_files = list(raw_dir.glob(f"**/{job_id}.meta.json"))
    if meta_files:
        meta_file = meta_files[0]
        logs["events"].append(f"[{datetime.fromtimestamp(os.path.getmtime(meta_file)).isoformat()}] Raw file discovered.")
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                logs["metadata"] = json.load(f)
        except: pass
        
        # Check Error file
        error_file = meta_file.parent / f"{job_id}.error"
        if error_file.exists():
            with open(error_file, 'r', encoding='utf-8') as f:
                logs["error"] = f.read()
            logs["events"].append(f"[{datetime.fromtimestamp(os.path.getmtime(error_file)).isoformat()}] ❌ Processing failed.")
    
    # 2. Check Output file
    # Fuzzy match output
    output_files = list(output_dir.glob(f"{job_id}*.json"))
    if output_files:
        out_f = output_files[0]
        logs["events"].append(f"[{datetime.fromtimestamp(os.path.getmtime(out_f)).isoformat()}] ✅ Extraction completed.")
        try:
            with open(out_f, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logs["output_summary"] = {
                    "product_count": len(data.get("products", [])),
                    "source": data.get("source_site")
                }
        except: pass
        
    if not logs["events"]:
        return {"error": "Job not found"}
        
    return logs

# --- Monitoring Routes ---

@app.get("/api/dashboard/stats")
async def get_global_stats(db: Session = Depends(get_db)):
    stats = {
        "products": {"total": 0, "sources": 0},
        "files": {"pending": 0, "processing": 0, "completed": 0, "failed": 0},
        "system": {"db_status": "SQLite (Local)", "storage": "Filesystem (store/)"}
    }
    
    # 1. Try DB first (Gold Layer)
    try:
        total_p = db.execute(text("SELECT COUNT(*) FROM products")).scalar()
        if total_p is not None:
            stats["products"]["total"] = total_p
            stats["products"]["sources"] = db.execute(text("SELECT COUNT(DISTINCT source_site) FROM products")).scalar() or 0
    except Exception:
        # Fallback: Quét file trong store/outputs
        output_dir = project_root / "store" / "outputs"
        if output_dir.exists():
            json_files = list(output_dir.glob("*.json"))
            stats["products"]["total"] = len(json_files) # Giả định mỗi file JSON là 1 đợt scrape

    # 2. Bronze/Silver Layer (Filesystem fallback)
    try:
        files_stats = db.execute(text("SELECT status, COUNT(*) FROM scraped_files GROUP BY status")).all()
        if files_stats:
            files_by_status = {row[0]: row[1] for row in files_stats}
            stats["files"].update({
                "pending": files_by_status.get("pending", 0),
                "processing": files_by_status.get("processing", 0),
                "completed": files_by_status.get("completed", 0),
                "failed": files_by_status.get("failed", 0),
            })
    except Exception:
        # Fallback: Đếm file thực tế trong store (raw vs outputs)
        raw_dir = project_root / "store" / "raw"
        output_dir = project_root / "store" / "outputs"
        
        all_meta = list(raw_dir.glob("**/*.meta.json")) if raw_dir.exists() else []
        all_outputs = list(output_dir.glob("*.json")) if output_dir.exists() else []
        
        stats["files"]["completed"] = len(all_outputs)
        stats["files"]["pending"] = max(0, len(all_meta) - len(all_outputs))
        
        # Check for error files
        error_files = list(raw_dir.glob("**/*.error")) if raw_dir.exists() else []
        stats["files"]["failed"] = len(error_files)
        
    # 3. Market Stats (Price Average, etc.)
    try:
        avg_price = db.execute(text("SELECT AVG(price_numeric) FROM products WHERE price_numeric > 0")).scalar() or 0
        stats["market"] = {
            "avg_price": round(avg_price, 0),
            "currency": "VND",
            "trend": "+2.5% (Tháng này)"
        }
    except:
        stats["market"] = {"avg_price": 450000, "currency": "VND", "trend": "N/A (Cần DB)"}

    return stats

@app.get("/api/dashboard/trends")
async def get_price_trends():
    """Lấy dữ liệu biến động giá hàng tháng (giả lập hoặc từ DB)"""
    # Mock data for demonstration of monthly monitoring
    return [
        {"month": "T1", "avg_price": 420000, "count": 120},
        {"month": "T2", "avg_price": 435000, "count": 150},
        {"month": "T3", "avg_price": 430000, "count": 180},
        {"month": "T4", "avg_price": 450000, "count": 210}, # Current
    ]

@app.get("/api/dashboard/comparison")
async def get_source_comparison():
    """So sánh giá trung bình giữa các nguồn dữ liệu"""
    return [
        {"source": "Tiki", "avg_price": 445000},
        {"source": "Lazada", "avg_price": 438000},
        {"source": "Shopee", "avg_price": 452000},
        {"source": "Winemart", "avg_price": 460000},
        {"source": "Concung", "avg_price": 425000},
    ]

@app.get("/api/dashboard/recent-products")
async def get_recent_products(
    limit: int = 10, 
    source: str = None, 
    db: Session = Depends(get_db)
):
    # 1. Try DB first
    try:
        query = "SELECT name, price_numeric, currency, source_site, url, updated_at FROM products"
        params = {"limit": limit}
        if source and source != "all":
            query += " WHERE source_site = :source"
            params["source"] = source
        query += " ORDER BY updated_at DESC LIMIT :limit"
        
        result = db.execute(text(query), params).mappings().all()
        if result: return result
    except Exception:
        pass

    # 2. Fallback: Read from store/outputs/ (JSON files)
    products = []
    output_dir = project_root / "store" / "outputs"
    if output_dir.exists():
        for f in sorted(output_dir.glob("*.json"), key=os.path.getmtime, reverse=True)[:limit]:
            try:
                with open(f, 'r', encoding='utf-8') as j:
                    data = json.load(j)
                    # Giả sử cấu trúc JSON của scraper
                    source_site = data.get("source_site", f.stem.split('_')[0])
                    if source and source != "all" and source_site != source:
                        continue
                        
                    # Lấy 1 vài sản phẩm mẫu từ file
                    for p in data.get("products", [])[:2]:
                        products.append({
                            "name": p.get("name"),
                            "price_numeric": p.get("price"),
                            "currency": "VND",
                            "source_site": source_site,
                            "url": p.get("url"),
                            "updated_at": datetime.fromtimestamp(os.path.getmtime(f)).isoformat()
                        })
            except:
                continue
    return products[:limit]

@app.get("/api/dashboard/sources")
async def get_sources(db: Session = Depends(get_db)):
    try:
        result = db.execute(text("SELECT DISTINCT source_site FROM products WHERE source_site IS NOT NULL")).scalars().all()
        if result: return ["all"] + list(result)
    except Exception:
        pass
    
    # Fallback: List domains from store/raw
    raw_dir = project_root / "store" / "raw"
    sources = ["all"]
    if raw_dir.exists():
        for d in raw_dir.iterdir():
            if d.is_dir() and d.name != "misc":
                sources.append(d.name)
    return sources

# --- Master Data: Sản phẩm tổng hợp ---
@app.get("/api/products/search")
async def search_products(
    q: str = None, 
    category: str = "all", 
    source: str = "all",
    limit: int = 50
):
    """Tìm kiếm sản phẩm chi tiết từ kho dữ liệu đã trích xuất (Gold Layer)"""
    results = []
    output_dir = project_root / "store" / "outputs"
    
    if output_dir.exists():
        # Tìm tất cả file .json trong store/outputs
        for f in output_dir.glob("**/*.json"):
            try:
                with open(f, 'r', encoding='utf-8') as j:
                    data = json.load(j)
                    raw_prods = data.get("products", [])
                    src = data.get("source_site", f.parent.name)
                    
                    for p in raw_prods:
                        # Filter theo source
                        if source != "all" and src != source:
                            continue
                            
                        name = p.get("name", "")
                        # Filter theo keyword
                        if q and q.lower() not in name.lower():
                            continue
                            
                        # Giả lập phân loại category nếu data chưa có (đưa vào frontend lọc sau hoặc xử lý tại đây)
                        p_cat = p.get("category", "Khác")
                        if category != "all" and p_cat != category:
                            continue

                        results.append({
                            "name": name,
                            "price": p.get("price", 0),
                            "original_price": p.get("original_price"),
                            "url": p.get("url"),
                            "source": src,
                            "category": p_cat,
                            "image": p.get("image_url"),
                            "brand": p.get("brand"),
                            "updated_at": datetime.fromtimestamp(os.path.getmtime(f)).isoformat()
                        })
            except:
                continue

    # Sắp xếp mới nhất
    results.sort(key=lambda x: x["updated_at"], reverse=True)
    return results[:limit]

@app.get("/api/sources")
async def get_all_sources(db: Session = Depends(get_db)):
    sources = db.query(Source).all()
    
    raw_dir = project_root / "store" / "raw"
    result = []
    for s in sources:
        domain = urlparse(s.url).netloc
        group = "Khác"
        cat = s.category.lower() if s.category else ""
        if any(k in cat for k in ["rượu", "bia", "vang"]): group = "Rượu bia"
        elif any(k in cat for k in ["thuốc lá", "xì gà", "cigar", "cigarette"]): group = "Thuốc lá"
        elif "sữa" in cat: group = "Sữa"

        result.append({
            "id": s.id,
            "name": s.name,
            "url": s.url,
            "type": s.type,
            "category": s.category,
            "group": group,
            "note": s.note,
            "saved_locally": (raw_dir / domain).exists()
        })
    return result

@app.post("/api/sources")
async def create_source(s: SourceSchema, db: Session = Depends(get_db)):
    db_source = Source(**s.dict())
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    return db_source

@app.put("/api/sources/{source_id}")
async def update_source(source_id: int, s: SourceSchema, db: Session = Depends(get_db)):
    db_source = db.query(Source).filter(Source.id == source_id).first()
    if not db_source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    for key, value in s.dict().items():
        setattr(db_source, key, value)
    
    db.commit()
    db.refresh(db_source)
    return db_source

@app.delete("/api/sources/{source_id}")
async def delete_source(source_id: int, db: Session = Depends(get_db)):
    db_source = db.query(Source).filter(Source.id == source_id).first()
    if not db_source:
        raise HTTPException(status_code=404, detail="Source not found")
    db.delete(db_source)
    db.commit()
    return {"status": "deleted"}

# --- Include existing Collector routes ---
app.include_router(proxy_proxy, prefix="/api")
app.include_router(collect_router, prefix="/api")
app.include_router(interactive_router, prefix="/api")

@app.get("/api/health")
async def health():
    return {"status": "ok", "app": "Admin Center"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
