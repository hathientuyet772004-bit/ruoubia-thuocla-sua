import os
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

try:
    from google import genai as genai_new
except ImportError:
    genai_new = None

try:
    import google.generativeai as genai_old
except ImportError:
    genai_old = None


load_dotenv()

api_key = os.getenv("GEMINI_API_KEY", "").strip()
if not api_key:
    raise ValueError("Missing GEMINI_API_KEY. Please set it in .env")

model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite").strip()
if not model_name:
    raise ValueError("Missing GEMINI_MODEL. Please set it in .env")

html_path = Path("htmls/ruoutot.html")
if not html_path.exists():
    raise FileNotFoundError(f"HTML file not found: {html_path}")

html_content = html_path.read_text(encoding="utf-8", errors="ignore")

prompt = f"""
You are an expert web scraping engineer.
Analyze the following HTML and return ONLY valid JSON describing a robust crawl extraction structure for BOTH branches and all products.

Requirements:
1) Output must be strict JSON only (no markdown, no comments).
2) JSON root keys exactly:
   - source_file
   - page_type
    - crawl_targets
   - notes
3) crawl_targets must be an array containing at least 3 entities:
    - products
    - branches
    - company_profile
4) Each crawl_targets item must have keys:
    - entity
    - description
    - container_selector
    - item_selector
    - pagination
    - fields
5) fields must be an array of objects with keys:
   - name
   - selector
   - attr
   - required
   - transform
6) products must include fields:
   product_name, brand, category, alcohol_percent, volume_ml, price, old_price,
    stock_status, rating, review_count, image_url, product_url
7) branches must include fields:
    branch_name, branch_url, address, phone, email
8) Use CSS selectors when possible.
9) If a field is not found, still include it with selector="" and required=false.
10) Prefer these selectors if present in HTML:
    - product cards: .product_inner
    - branch links in footer: #fcl-chi_nhanh_toan_quoc a.footer-content__link
    - branch cards in news: .tintuc_detailds
    - company profile block: #fcl-security_1

Return one single JSON object.

HTML:
{html_content}
"""

print(f"Using Gemini model: {model_name}")


def clean_json_text(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("```", 1)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return text

try:
    if genai_new is not None:
        client = genai_new.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        output_text = response.text
    elif genai_old is not None:
        genai_old.configure(api_key=api_key)
        model = genai_old.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        output_text = response.text
    else:
        raise ImportError(
            "No Gemini SDK found. Install one of: pip install google-genai OR pip install google-generativeai"
        )

    json_text = clean_json_text(output_text)
    data = json.loads(json_text)

    out_path = Path("htmls/winemart.html")
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"\nSaved JSON structure to: {out_path}")
except Exception as exc:
    print(f"Gemini API error: {exc}")
    sys.exit(1)