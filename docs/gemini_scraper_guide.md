# 🤖 Hướng dẫn Scraper Thông minh với Gemini AI

Tài liệu này hướng dẫn cách kết hợp sức mạnh của **Gemini AI** để tự động hóa việc phân tích cấu trúc trang web và xây dựng bộ trích xuất (Scraper) linh hoạt.

---

## 📐 Kiến trúc 3 Giai đoạn

1. **Giai đoạn 1 (Analyze):** Gemini Vision/Text đọc hiểu screenshot hoặc HTML thô để xác định các CSS Selectors, cơ chế phân trang và cấu trúc dữ liệu.
2. **Giai đoạn 2 (Scrape):** Sử dụng Python (Playwright/BeautifulSoup) để thu thập dữ liệu theo các "chỉ dẫn" từ Gemini.
3. **Giai đoạn 3 (Export):** Chuẩn hóa và xuất dữ liệu ra Database hoặc file Excel/JSON.

---

## 🧠 Giai đoạn 1: Phân tích bằng Gemini AI

Sử dụng Prompt để yêu cầu Gemini trả về cấu trúc JSON chuẩn:

```python
import google.generativeai as genai
import json

def get_page_structure(html_snippet: str):
    model = genai.GenerativeModel("gemini-1.5-pro")
    prompt = f"Phân tích HTML sau và trả về JSON cấu trúc: {html_snippet}"
    response = model.generate_content(prompt)
    return json.loads(response.text)
```

---

## 🕷️ Giai đoạn 2: Trích xuất Dữ liệu (Crawler Logic)

Sử dụng lớp `SmartScraper` để xử lý đa dạng các loại trang:

### A. Phân trang truyền thống (URL Params)

Thực hiện lặp qua các trang `?page=n` theo pattern đã được Gemini xác định.

### B. Nội dung động (Infinite Scroll)

Sử dụng **Playwright** để mô phỏng hành vi cuộn chuột của người dùng:

```python
while True:
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(2000)
    # Check if more data loaded...
```

---

## 💾 Giai đoạn 3: Chuẩn hóa & Lưu trữ

### Chuẩn hóa Giá tiền (Price Normalization)

```python
def normalize_price(price_str: str) -> float:
    # Chuyển "125.000đ" -> 125000.0
    nums = re.sub(r'[^\d]', '', price_str)
    return float(nums) if nums else 0.0
```

### Xuất dữ liệu

- **Database:** Đẩy trực tiếp vào PostgreSQL Gold Layer.
- **Excel/JSON:** Dùng cho báo cáo nhanh hoặc kiểm tra thủ công.

---

## 🚨 Xử lý Case đặc biệt

| Tình huống | Giải pháp |
| :--- | :--- |
| **Dùng React/Vue** | Dùng Playwright thay cho Requests thông thường. |
| **Bị chặn IP** | Rotate User-Agent, thêm delay ngẫu nhiên, hoặc dùng Proxy. |
| **CAPTCHA** | Tích hợp dịch vụ giải CAPTCHA hoặc chuyển sang thu thập thủ công qua Web Collector. |
| **Shopify/WooCommerce** | Ưu tiên gọi API endpoint nội bộ `/collections/all.json`. |

---
*Tài liệu hướng dẫn kỹ thuật cho dự án Dataset Rượu bia - Thuốc lá - Sữa.*
