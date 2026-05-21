# 🌐 Tổng quan Công cụ Web Collector

**Web Collector** là một trạm thu thập dữ liệu chuyên nghiệp, được thiết kế riêng để xây dựng bộ dữ liệu (dataset) thông minh bằng cách lưu trữ nguyên trạng các trang web đích.

---

## 🚀 Các tính năng cốt lõi

### 1. Đóng gói Nội dung (MHTML)

Thay vì chỉ tải file `.html` đơn thuần (dễ mất định dạng/hình ảnh), công cụ hỗ trợ lưu trữ dưới định dạng **.mhtml**.

- **Ưu điểm:** Đóng gói toàn bộ mã nguồn, hình ảnh, CSS và JavaScript vào một file duy nhất.
- **Lợi ích:** Dữ liệu thu thập luôn được bảo toàn nguyên trạng để phục vụ cho việc parse sau này.

### 2. Chế độ Trình duyệt Tương tác (Interactive Mode)

Hệ thống tích hợp tính năng khởi chạy trình duyệt thực tế (Playwright/Chrome) giúp:

- **Vượt rào cản bot:** Vượt qua các cơ chế chống bot của Tiki, Shopee, Lazada.
- **Tương tác linh hoạt:** Cho phép đăng nhập, giải CAPTCHA hoặc cuộn trang để tải thêm dữ liệu trước khi "Hút".
- **Nút "Hút dữ liệu":** Kích hoạt lưu trang ngay lập tức khi người dùng xác nhận thông tin sản phẩm chuẩn.

### 3. Quản lý Dữ liệu Thông minh

- **Deduplication:** Tự động kiểm tra trùng lặp dựa trên `URL Hash` để tránh tải lại cùng một trang nhiều lần.
- **Dashboard:** Theo dõi trực quan số lượng yêu cầu, thời gian tải và tổng dung lượng dữ liệu đã thu thập.
- **Lịch sử thu thập:** Sidebar quản lý danh sách file, cho phép tìm kiếm và xem lại nhanh chóng.

### 4. Giao diện Hiện đại

- **Thiết kế Glassmorphism:** Mang lại trải nghiệm cao cấp, chuyên nghiệp.
- **Thông báo Toast:** Cập nhật trạng thái thực tế của quá trình thu thập (Success/Error/Pending).

---

## 📝 Ghi chú Phát triển (Development Notes)

- [ ] **Xử lý Tên:** Tên sản phẩm trên sàn TMĐT thường chứa nhiều thông tin rác (giảm giá, mã giảm giá) -> Cần Clean Logic mạnh.
- [ ] **Mapping:** Tiến hành ánh xạ (mapping) tên sản phẩm về danh mục chuẩn.
- [ ] **Storage Infrastructure:** Đang hoàn thiện tích hợp hoàn toàn với **MinIO Lakehouse** để lưu trữ file thô dung lượng lớn.

---
*Phục vụ dự án: Dataset Rượu bia - Thuốc lá - Sữa.*
