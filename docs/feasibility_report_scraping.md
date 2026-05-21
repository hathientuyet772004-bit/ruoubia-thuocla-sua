# 📈 Báo cáo Khả thi: Hệ thống Thu thập Dữ liệu Quy mô lớn

Tài liệu này phân tích tính khả thi và so sánh giữa hai phương pháp: **Thu thập Tự động (Scraper/Crawler)** và **Thu thập Thủ công (Đội ngũ 20 người)**.

---

## 1. Phân tích Tốc độ & Hiệu suất

### Phương pháp A: Tự động hóa (Automation)

- **Tốc độ:** ~100-200 trang/giờ mỗi server (có delay 1.5s/request để tránh block).
- **Trình độ:** Chạy 24/7 không nghỉ.
- **Sản lượng ước tính:** ~40,000 - 80,000 trang/tháng/server.
- **Dữ liệu:** Có tính cấu trúc cao, đồng nhất.

### Phương pháp B: Thủ công (Human Team - 20 người)

- **Tốc độ:** ~10-20 trang/giờ/người.
- **Thời gian làm việc:** 4 giờ/ngày, 20 ngày/tháng.
- **Sản lượng ước tính:** ~15,000 - 25,000 trang/tháng cả đội ngũ.
- **Dữ liệu:** Linh hoạt, vượt được các CAPTCHA phức tạp.

---

## 2. So sánh Chi phí (Ước tính hàng tháng)

| Tiêu chí | Tự động hóa (1 Server) | Đội ngũ (20 người) |
| :--- | :--- | :--- |
| **Chi phí cố định** | ~5-10tr (Server/Proxy) | ~50tr (Quản lý/Thiết bị) |
| **Chi phí biến đổi** | ~3-5tr (API Gemini/LLM) | ~10-20tr (Lương/Thưởng) |
| **Tổng cộng** | **~10-20tr** | **~60-70tr** |
| **Giá thành/SP** | Rất thấp (~2-20 VNĐ) | Trung bình (~50-200 VNĐ) |

---

## 3. Đánh giá Rủi ro Pháp lý & Kỹ thuật

- **Rủi ro Bot:** Các sàn lớn (Shopee, Lazada, Tiki) có cơ chế phát hiện bot cực mạnh.
- **Giải pháp:** Sử dụng **Adaptive Scraping** (mô phỏng hành vi người dùng) kết hợp với Proxy Rotation.
- **Pháp lý:** Tuân thủ các quy định về dữ liệu công khai và bản quyền nội dung. Không thu thập thông tin cá nhân người dùng.

---

## 4. Lộ trình Triển khai Khuyến nghị (Hybrid Approach)

Chúng ta nên áp dụng mô hình **Lai (Hybrid)** để tối ưu hóa kết quả:

1. **Giai đoạn 1 (Thủ công):** Sử dụng `Web Collector Tool` để đội ngũ 20 người tập trung lưu trữ trang `.mhtml` từ các sản phẩm ngách khó tìm.
2. **Giai đoạn 2 (Bán tự động):** Chạy Worker ETL để trích xuất dữ liệu hàng loạt từ đống file MHTML đã thu thập.
3. **Giai đoạn 3 (Tự động hoàn toàn):** Triển khai `Adaptive Crawler` cho các trang có cấu trúc ổn định để thu thập dữ liệu định kỳ mỗi ngày.

---

## 5. Kết luận

Phương pháp tự động hóa giúp tiết kiệm **~70-80% chi phí** và mang lại sản lượng dữ liệu gấp **3-4 lần** so với đội ngũ thủ công. Tuy nhiên, đội ngũ thủ công đóng vai trò quan trọng trong việc xử lý các trang có rào cản kỹ thuật cao.

---
*Người lập báo cáo: Antigravity AI*
