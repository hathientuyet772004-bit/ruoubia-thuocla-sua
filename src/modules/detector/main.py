import argparse
import json
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.detector.scanner import IntelligenceScanner

def main():
    parser = argparse.ArgumentParser(description="Detector Module — Website Crawler Intelligence & Verification")
    parser.add_argument("--url", required=True, help="URL của website cần xác minh")
    parser.add_argument("--ai", action="store_true", help="Sử dụng AI (Gemini) để khám phá cấu trúc sâu")
    
    args = parser.parse_args()

    scanner = IntelligenceScanner()
    
    try:
        if args.ai:
            print(f"🚀 Khởi động AI Scanner cho: {args.url}...")
            result = scanner.scan(args.url)
        else:
            print(f"🔍 Đang chẩn đoán kỹ thuật cho: {args.url}...")
            result = scanner.analyzer.diagnose(args.url)

        print("\n" + "="*50)
        print("📊 KẾT QUẢ PHÂN TÍCH")
        print("="*50)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")
    finally:
        scanner.close()

if __name__ == "__main__":
    main()
