import csv
import json
import time
import sys
from pathlib import Path

# Add src/ to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.detector.analyzer import SiteAnalyzer

def batch_scan(csv_path: str, output_path: str):
    analyzer = SiteAnalyzer()
    results = []
    
    print(f"🚀 Bắt đầu quét hàng loạt từ file: {csv_path}")
    
    if not Path(csv_path).exists():
        print(f"❌ File {csv_path} không tồn tại!")
        return

    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Tên Website")
            url = row.get("URL")
            
            if not url or name is None: continue
            
            print(f"🕵️ [{row.get('STT')}] Chẩn đoán: {name}...")
            try:
                diag = analyzer.diagnose(url)
                
                # Lưu kết quả rút gọn
                results.append({
                    "STT": row.get("STT"),
                    "Tên": name,
                    "URL": url,
                    "Score": diag["crawlability"]["score"],
                    "Strategy": diag["crawlability"]["strategy_recommended"].upper(),
                    "Anti-bot": diag["protection"]["anti_bot"],
                    "JS": diag["technology"]["js_required"],
                    "Note": diag["crawlability"]["notes"]
                })
            except Exception as e:
                print(f"❌ Lỗi trang {url}: {e}")
            
            # Nghỉ ngắn giữa các request để an toàn
            time.sleep(0.3)

    # 1. Xuất file JSON chi tiết
    with open(f"{output_path}.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # 2. Xuất bảng Markdown để xem nhanh
    markdown = "# 📊 Báo cáo Khả năng Thu thập Dữ liệu (Batch Scan)\n\n"
    markdown += f"Thời gian thực hiện: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    markdown += "| STT | Website | Score | Strategy | Anti-bot | JS | Note |\n"
    markdown += "|:---|:---|:---:|:---:|:---:|:---:|:---|\n"
    for r in results:
        status_icon = "🛑" if r["Score"] < 50 else ("⚠️" if r["Score"] < 80 else "✅")
        markdown += f"| {r['STT']} | **{r['Tên']}** | {status_icon} {r['Score']} | `{r['Strategy']}` | {r['Anti-bot']} | {r['JS']} | {r['Note']} |\n"

    with open(f"{output_path}.md", "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"\n✅ Đã hoàn thành! Báo cáo tại: {output_path}.md")
    analyzer.close()

if __name__ == "__main__":
    # Fix paths for execution
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
    csv_file = PROJECT_ROOT / "src" / "core" / "urls.csv"
    output_dir = PROJECT_ROOT / "outputs"
    output_dir.mkdir(exist_ok=True)
    output_base = output_dir / "batch_scan_report"
    
    batch_scan(str(csv_file), str(output_base))
