#!/usr/bin/env python3
"""Wine & Beer Scraper — Powered by Gemini AI

Cách dùng (từ thư mục gốc):
	python scraper/main.py https://ruoutot.net/
	python scraper/main.py https://winemart.vn/ --max-pages 10

	→ Gemini tự fetch HTML, phân tích cấu trúc, scrape toàn bộ, xuất CSV + Excel + JSON.
	→ Kết quả lưu tại data/outputs/
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

# Đảm bảo root dự án có trong path để import 'scraper'
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Paths chuẩn hóa theo cấu trúc mới
_OUTPUTS_DIR = PROJECT_ROOT / "store" / "outputs"
_CACHE_DIR = PROJECT_ROOT / "store" / "cache"
_RAW_DATA_DIR = PROJECT_ROOT / "store" / "raw"

# Create dirs
_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_url(s: str) -> bool:
	return bool(s) and (s.startswith("http://") or s.startswith("https://"))


def _safe_name(s: str) -> str:
	if _is_url(s):
		s = urlparse(s).netloc
	return re.sub(r"[^\w.-]", "_", str(s)).strip("_")[:50]


def _load_structure(path: str) -> dict:
	p = Path(path)
	if not p.exists():
		print(f"❌ Structure file not found: {p}")
		sys.exit(1)
	return json.loads(p.read_text(encoding="utf-8"))


def _export(data: dict) -> None:
	from scraper.exporter import DataExporter

	print("\n💾 Đang xuất kết quả …")
	exp = DataExporter(data, _OUTPUTS_DIR)
	exp.to_csv()
	exp.to_excel()
	exp.to_json()

	print("\n" + "=" * 60)
	print("🎉 Xong!")
	print(f"   📦 {data.get('total_products', 0)} sản phẩm")
	print(f"   🏪 {data.get('total_branches', 0)} chi nhánh")
	print(f"   📁 Kết quả: {_OUTPUTS_DIR}")
	print("=" * 60)


def _do_scrape(url: str, structure: dict, max_pages: int = 50) -> dict:
	pg: dict = {}
	for target in structure.get("crawl_targets", []):
		if target.get("entity") == "products" and target.get("pagination"):
			pg = target["pagination"] or {}
			break
	if not pg:
		pg = structure.get("pagination") or {}

	ptype: str = pg.get("type") or ""
	print(f"\n🕷️  Kiểu phân trang: {ptype or 'none'}")

	if ptype in ("infinite_scroll", "load_more"):
		from scraper.playwright_scraper import scrape_with_playwright
		data = scrape_with_playwright(url, structure)
	else:
		from scraper.scraper import SmartScraper
		data = SmartScraper(url, structure).scrape_all(max_pages=max_pages)

	_export(data)
	return data


# ── Subcommands ───────────────────────────────────────────────────────────────

def cmd_run(url: str, max_pages: int = 50, structure_path: str | None = None) -> None:
	"""Full pipeline: Gemini fetch HTML → phân tích → scrape → export."""
	print("\n" + "=" * 60)
	print("🍺 WINE & BEER SCRAPER — Powered by Gemini AI")
	print("=" * 60)

	if structure_path and Path(structure_path).exists():
		print(f"\n📂 Dùng structure có sẵn: {structure_path}")
		structure = _load_structure(structure_path)
	else:
		print("\n🧠 Bước 1: Gemini đang phân tích cấu trúc trang …")
		from scraper.analyzer import analyze_page_structure

		structure = analyze_page_structure(url=url)
		if not structure:
			print("❌ Gemini không trả về cấu trúc hợp lệ.")
			sys.exit(1)

		struct_path = _CACHE_DIR / f"{_safe_name(url)}_structure.json"
		struct_path.write_text(
			json.dumps(structure, ensure_ascii=False, indent=2), encoding="utf-8"
		)
		print(f"   ✅ Structure đã lưu: {struct_path}")

	print(f"   page_type: {structure.get('page_type', '?')}")
	_do_scrape(url, structure, max_pages=max_pages)


def cmd_analyze(url: str | None, html: str | None, out: str | None) -> None:
	"""Phase 1 only: gửi HTML cho Gemini, lưu structure JSON."""
	from scraper.analyzer import analyze_page_structure

	if url:
		structure = analyze_page_structure(url=url)
		name = _safe_name(url)
	elif html:
		structure = analyze_page_structure(html_file=html)
		name = Path(html).stem
	else:
		print("❌ Cần cung cấp URL hoặc --html")
		sys.exit(1)

	if not structure:
		print("❌ Phân tích thất bại.")
		sys.exit(1)

	dest = Path(out) if out else _CACHE_DIR / f"{name}_structure.json"
	dest.parent.mkdir(parents=True, exist_ok=True)
	dest.write_text(json.dumps(structure, ensure_ascii=False, indent=2), encoding="utf-8")
	print(f"\n✅ Structure đã lưu: {dest}")
	print(f"   page_type    : {structure.get('page_type', '?')}")
	entities = [t["entity"] for t in structure.get("crawl_targets", [])]
	print(f"   crawl_targets: {entities}")


def cmd_scrape(url: str, structure_path: str, max_pages: int = 50) -> None:
	"""Phase 2 only: scrape bằng structure JSON có sẵn."""
	structure = _load_structure(structure_path)
	print(f"\n📂 Structure loaded: {structure_path}")
	_do_scrape(url, structure, max_pages=max_pages)


def cmd_local(html: str, base_url: str | None, structure_path: str | None) -> None:
	"""Parse file HTML local, không fetch live."""
	html_file = Path(html)
	if not html_file.exists():
		print(f"❌ File not found: {html_file}")
		sys.exit(1)

	if structure_path and Path(structure_path).exists():
		structure = _load_structure(structure_path)
		print(f"📂 Using structure: {structure_path}")
	else:
		print(f"\n🧠 Analysing {html_file.name} with Gemini …")
		from scraper.analyzer import analyze_page_structure
		structure = analyze_page_structure(html_file=html_file)
		if not structure:
			print("❌ Analysis failed.")
			sys.exit(1)
		sp = _CACHE_DIR / f"{html_file.stem}_structure.json"
		sp.write_text(json.dumps(structure, ensure_ascii=False, indent=2), encoding="utf-8")
		print(f"   Structure saved: {sp}")

	resolved_url = base_url or f"https://{html_file.stem}"

	from bs4 import BeautifulSoup
	from scraper.scraper import SmartScraper

	soup = BeautifulSoup(
		html_file.read_text(encoding="utf-8", errors="ignore"), "lxml"
	)
	scraper = SmartScraper(resolved_url, structure, delay=0)
	products = scraper._parse_products_from_page(soup, 1)
	branches = scraper._parse_branches_from_page(soup)
	company = scraper._parse_company_profile_from_page(soup)

	data = {
		"products": products,
		"branches": branches,
		"company_profile": company,
		"total_products": len(products),
		"total_branches": len(branches),
		"pages_scraped": 1,
		"source_site": html_file.stem,
	}
	print(f"\n📊 Parsed: {len(products)} products, {len(branches)} branches")
	_export(data)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
	if len(sys.argv) >= 2 and _is_url(sys.argv[1]):
		p = argparse.ArgumentParser(add_help=False)
		p.add_argument("url")
		p.add_argument("--max-pages", type=int, default=50, dest="max_pages")
		p.add_argument("--structure", default=None)
		a, _ = p.parse_known_args()
		cmd_run(a.url, a.max_pages, a.structure)
		return

	parser = argparse.ArgumentParser(
		prog="scraper/main.py",
		description="🍺 Wine & Beer Scraper powered by Gemini AI",
		formatter_class=argparse.RawDescriptionHelpFormatter,
		epilog=__doc__,
	)
	sub = parser.add_subparsers(dest="command")

	# analyze
	p = sub.add_parser("analyze", help="Phân tích cấu trúc trang với Gemini, lưu JSON")
	p.add_argument("url", nargs="?", metavar="URL")
	p.add_argument("--html", metavar="FILE")
	p.add_argument("--out", metavar="FILE")

	# scrape
	p = sub.add_parser("scrape", help="Scrape bằng structure JSON có sẵn (không gọi Gemini)")
	p.add_argument("url", metavar="URL")
	p.add_argument("--structure", required=True, metavar="FILE")
	p.add_argument("--max-pages", type=int, default=50, dest="max_pages")

	# local
	p = sub.add_parser("local", help="Parse file HTML local, không fetch live")
	p.add_argument("--html", required=True, metavar="FILE")
	p.add_argument("--url", metavar="URL")
	p.add_argument("--structure", metavar="FILE")

	args = parser.parse_args()

	if args.command == "analyze":
		cmd_analyze(
			url=getattr(args, "url", None),
			html=getattr(args, "html", None),
			out=getattr(args, "out", None),
		)
	elif args.command == "scrape":
		cmd_scrape(args.url, args.structure, args.max_pages)
	elif args.command == "local":
		cmd_local(
			html=args.html,
			base_url=getattr(args, "url", None),
			structure_path=getattr(args, "structure", None),
		)
	else:
		parser.print_help()


if __name__ == "__main__":
	main()
