# 🛒 Quy trình Trích xuất Dữ liệu Shopee (MHTML)

Tài liệu này hướng dẫn cách trích xuất dữ liệu sản phẩm từ file `.mhtml` được lưu từ Shopee.

---

## 🔄 Các bước thực hiện

### 1. Thu thập Trang (Capture)

- Sử dụng trình duyệt hoặc **Web Collector Tool**.
- Lưu trang dưới dạng `.mhtml` để giữ trọn vẹn CSS/hình ảnh.

### 2. Tiền xử lý File (Preprocessing)

- **Đọc file:** Mở file với encoding `utf-8`.
- **Tách HTML:** Loại bỏ header của file MHTML bằng cách tìm vị trí bắt đầu `<!DOCTYPE html>`.
- **Giải mã:** Sử dụng thư viện `quopri` để giải mã `quoted-printable` (định dạng lưu trữ mặc định của MHTML).

### 3. Trích xuất Thông tin (Parsing)

Sử dụng **BeautifulSoup4** để truy vấn các thành phần:

| Thông tin | Phương pháp trích xuất |
| :--- | :--- |
| **Tiêu đề** | Thẻ `<title>` hoặc meta `og:title`. |
| **Mô tả sơ bộ** | Thẻ meta `og:description`. |
| **Hình ảnh chính** | Thẻ meta `og:image`. |
| **Giá (Price)** | Tìm `div` có class chứa pattern `IZPeQz` hoặc `B67UQ0`. |
| **Thuộc tính** | Duyệt qua `div class='ybxj32'`, cặp Key/Value từ `h3 class='VJOnTD'`. |
| **Mô tả chi tiết** | Nội dung trong `div class='e8lZp3'`, lấy tất cả thẻ `p`. |

### 4. Lưu trữ & Kiểm tra

- **Xuất bản:** Ghi dữ liệu vào CSV/JSON hoặc đẩy trực tiếp vào PostgreSQL (Gold Layer).
- **Audit:** Kiểm tra các trường dữ liệu thiếu (null) do Shopee thay đổi cấu trúc class (Class Obfuscation).

---

## 🛠️ Lưu ý kỹ thuật
>
> [!TIP]
> Shopee thường thay đổi class ngẫu nhiên. Để tăng độ bền vững (robustness), nên ưu tiên trích xuất từ cấu trúc **Microdata/LD-JSON** (nếu có) thay vì dựa hoàn toàn vào CSS Classes.

---
*Cập nhật: 2026-04-26*
