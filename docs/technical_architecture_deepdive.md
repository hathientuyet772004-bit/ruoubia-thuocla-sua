# ⚙️ Tài liệu Chi tiết Kỹ thuật: Hệ thống Lưu trữ & ETL

Tài liệu này đóng vai trò là tham chiếu kỹ thuật (Technical Deep Dive) cho đội ngũ phát triển, mô tả chi tiết cách vận hành của hệ thống Lakehouse.

---

## 1. Thành phần Hệ thống (Technology Stack)

- **Object Storage:** MinIO (Lưu trữ file .mhtml).
- **RDBMS:** PostgreSQL with PostGIS (Lưu dữ liệu cấu trúc và tọa độ).
- **In-memory Store:** Redis (Bộ lọc URL Hash, Task Queue).
- **Orchestration:** Airflow / ETL Workers (Điều phối luồng dữ liệu).

---

## 2. Chiến lược Lưu trữ MinIO (Bronze & Silver)

### Cấu trúc Folder trong Bucket `collector-data`

- `raw/`: File gốc (.mhtml).
- `processed/`: Kết quả JSON trung gian sau khi parse.
- `logs/`: Nhật ký vận hành hệ thống.

### Quy ước đặt tên (Key naming)

`raw/{domain}/{YYYY-MM-DD}/{url_hash}.mhtml`

---

## 3. Lớp Xử lý dữ liệu (ETL Pipeline)

Dự án áp dụng mô hình xử lý theo **Batch** (Hàng loạt):

1. **Extraction:** Tải file MHTML từ MinIO.
2. **AI Transformation:**
   - Sử dụng **Gemini AI** để trích xuất schema (Product Name, Brand, Price, Attributes).
   - Normalize dữ liệu tiền tệ (VND) và đơn vị tính (ml, gr, lon/thùng).
3. **Loading:**
   - Thực hiện `Upsert` vào PostgreSQL.
   - Bản ghi cũ được cập nhật giá mới nhất và ghi nhận lịch sử vào bảng `price_history`.

---

## 4. Cơ sở dữ liệu (PostgreSQL Schema)

### Bảng `scraped_files` (Quản lý trạng thái)

Lưu vết mọi file được thu thập để Worker biết cần xử lý file nào.

- `status`: `pending` | `processing` | `completed` | `failed`.

### Bảng `products` (Gold Layer)

Lưu trữ thông tin sản phẩm "sạch" cuối cùng.

- Cột `url_hash` là khóa chính duy nhất.
- Cột `raw_data` (JSONB) lưu giữ bản sao dữ liệu trích xuất để đối chiếu.

---

## 5. Xử lý Lỗi & Khả năng mở rộng (Scalability)

- **Retry Mechanism:** Tự động thử lại tối đa 3 lần nếu worker gặp lỗi mạng.
- **Idempotency:** Đảm bảo chạy lại ETL nhiều lần trên cùng dữ liệu không làm sai lệch kết quả (nhờ `url_hash`).
- **Parallelism:** Có thể triển khai nhiều instance Worker xử lý song song các Domain khác nhau trong MinIO.

---
*Cập nhật lần cuối: 2026-04-26*
