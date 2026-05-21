# 🛡️ Chiến lược Khử trùng lặp Dữ liệu (Deduplication)

Tài liệu này chi tiết phương pháp kết hợp **URL Hashing** và **Unique Constraints** để đảm bảo tính toàn vẹn và hiệu năng của kho dữ liệu.

---

## 1. Tại sao cần URL Hashing?

Việc sử dụng trực tiếp chuỗi URL để kiểm tra trùng lặp gặp các hạn chế:

- **Độ dài không cố định:** URL sàn TMĐT thường rất dài (>500 ký tự), gây chậm Index.
- **Tham số rác:** UTM tags, session IDs làm sai lệch kết quả kiểm tra trùng.
- **Hiệu năng:** So sánh string dài tốn tài nguyên RAM và CPU hơn so với chuỗi hash cố định.

---

## 2. Giải pháp Kỹ thuật

### A. Chuẩn hóa URL (Normalization)

Trước khi băm, URL được đưa về dạng chuẩn (Canonical URL):

1. Chuyển về **lowercase**.
2. Loại bỏ các tham số query không cần thiết (vd: `sp_atk`, `utm_source`).
3. Loại bỏ dấu `/` cuối cùng.

### B. Thuật toán băm (MD5)

- **Định dạng:** Trả về chuỗi 32 ký tự Hex.
- **Lý do chọn MD5:** Tốc độ cực nhanh, dung lượng lưu trữ cố định (`CHAR(32)`), xác suất trùng mã (collision) cực thấp cho quy mô hàng chục triệu URL.

---

## 3. Cấu trúc Database & Logic

### Schema SQL (PostgreSQL)

```sql
-- Cột url_hash là khóa duy nhất giúp chặn trùng lặp ở tầng DB
ALTER TABLE products ADD COLUMN url_hash CHAR(32) UNIQUE NOT NULL;

-- Index bổ trợ để truy vấn theo nguồn nhanh hơn
CREATE INDEX idx_products_source_site ON products(source_site);
```

### Logic Python (MD5 Helper)

```python
import hashlib

def get_url_hash(url: str) -> str:
    # 1. Chuẩn hóa
    clean_url = url.strip().lower().split('?')[0].rstrip('/')
    # 2. Băm MD5
    return hashlib.md5(clean_url.encode('utf-8')).hexdigest()
```

---

## 4. Tích hợp Hệ thống (Pipeline)

Hệ thống kiểm tra trùng lặp tại 2 thời điểm:

1. **Lúc thu thập (Collector):** Sử dụng **Redis SET** để check nhanh URL Hash. Nếu đã tồn tại -> Bỏ qua không crawl.
2. **Lúc lưu trữ (Gold Layer):** Sử dụng `INSERT ... ON CONFLICT (url_hash) DO UPDATE`.
    - Nếu URL mới: Tạo bản ghi sản phẩm.
    - Nếu URL đã có: Chỉ cập nhật giá và thời gian `updated_at`.

---

## 5. Kết quả đạt được

- **Tốc độ:** Kiểm tra trùng lặp đạt độ phức tạp $O(1)$.
- **Dung lượng:** Giảm thiểu 100% dữ liệu sản phẩm bị lặp lại trong database.
- **Tin cậy:** Đảm bảo mỗi sản phẩm chỉ có duy nhất một bản ghi định danh trên mỗi sàn.

---
*Cập nhật: 2026-04-26*
