# 📝 Tài liệu Chiến lược Dữ liệu & Quy trình Thu thập (V2 - Cải tiến)

Tài liệu này tổng hợp chiến lược toàn diện về dữ liệu, hạ tầng và quy trình vận hành cho các ngành hàng: **Sữa, Rượu bia, Thuốc lá**.

---

## 🎯 1. Mục tiêu Chiến dịch & KPIs (Scalable)

- **Độ bao phủ sàn:** Shopee, Lazada, Tiki, TikTok Shop, GrabMart, WinMart, BachhoaXANH và các Web chuyên biệt.
- **Quy mô dữ liệu:** Khởi đầu 50 SKUs/sàn, lộ trình mở rộng lên >10.000 SKUs thông qua tự động hóa.
- **Chỉ số vàng (Golden Metrics):**
  - **Data Fidelity:** > 98% chính xác sau khi qua lớp xác thực AI & HITL.
  - **Crawl Success Rate:** > 90% (tỷ lệ request thành công không bị block).
  - **Price Timeliness:** Cập nhật giá mới nhất trong vòng 24h.

---

## �️ 2. Chiến lược Chống chặn (Anti-Bot & Proxy)

Để đối phó với cơ chế bảo mật của Shopee, Lazada, hệ thống áp dụng:

- **Proxy Rotation:** Sử dụng Residential Proxy để thay đổi địa chỉ IP liên tục.
- **User-Agent Shuffling:** Luân phiên tập hợp >100 dấu vân tay trình duyệt (Fingerprints) khác nhau.
- **Behavior Simulation:** Mô phỏng hành vi người dùng (cuộn trang, di chuột ngẫu nhiên, độ trễ không đồng nhất).
- **Headless Bypass:** Sử dụng `stealth` plugin trong Playwright để che dấu dấu vết automation.

---

## 🏗️ 3. Mô hình Cấu trúc Dữ liệu Chuyên sâu

### A. Core Product Schema (JSONB)

```json
{
  "product_id": "string (UUID)",
  "name": "string",
  "brand": "string",
  "barcode": "string (EAN/UPC)",
  "origin": "string",
  "is_adult_item": "boolean",
  "meta": {
    "promotion_price": "number",
    "discount_percentage": "number",
    "stock_status": "boolean",
    "rating_count": "integer"
  }
}
```

### B. Thuộc tính đặc thù (Chi tiết)

- **Rượu:** Nồng độ (% ABV), Dung tích (ml), Năm (Vintage), Tasting Notes (Aroma, Palate, Finish).
- **Bia:** Packaging (Lon/Chai), Quy cách (Lốc/Thùng), Hạn sử dụng (Exp Date).
- **Sữa:** Thành phần dinh dưỡng (DHA, Protein, Vitamin), Độ tuổi (Số 1, 2, 3), Thông tin dị ứng.

---

## 🔁 4. Quy trình Xác thực & Vòng đời Dữ liệu

### Quy trình Xác thực 3 Lớp

1. **Lớp 1 (Regex/Rules):** Kiểm tra tính hợp lệ cơ bản (giá > 0, có tên sản phẩm).
2. **Lớp 2 (Gemini AI):** Trích xuất và đối soát mã vạch, nhãn hiệu từ nội dung thô.
3. **Lớp 3 (Human-in-the-loop):** Các bản ghi có độ tin cậy < 85% sẽ được đẩy về Dashboard quản trị để kiểm tra thủ công.

### Chính sách Lưu trữ (Retention Policy)

- **Bronze (MHTML):** Lưu tại MinIO trong **30 ngày** (phục vụ đối soát), sau đó chuyển sang Archive (nén).
- **Silver (JSON Raw):** Lưu trữ trong **90 ngày**.
- **Gold (Structured Data):** Lưu trữ **vĩnh viễn** trong PostgreSQL để phân tích xu hướng và lịch sử giá.

---

## � 5. Theo dõi Biến động & Store Mapping

- **Mapping ID:** Sử dụng `url_hash` để định danh sản phẩm duy nhất trên toàn hệ thống.
- **Store-Product Link:** Một sản phẩm có thể liên kết với nhiều cửa hàng (`store_id`) với các mức giá khác nhau tại cùng một thời điểm.
- **Price Dashboard:** Tích hợp biểu đồ biến động giá (Time-series) để nhận diện các đợt tăng/giảm giá ảo.

---

## 📂 6. Phân bổ Module Hệ thống

- `src/modules/collector`: Giao diện thu thập tương tác cho người dùng.
- `src/modules/crawler`: Robot tự động chạy ngầm theo lịch trình (Airflow).
- `src/core/config`: Quản lý tập trung API Keys và cấu hình Proxy.

---
*Tài liệu phiên bản V2 - Cập nhật ngày 2026-04-26 định hướng quy mô công nghiệp.*
