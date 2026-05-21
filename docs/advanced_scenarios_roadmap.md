# ROADMAP KIẾN TRÚC & KỊCH BẢN THU THẬP DỮ LIỆU NÂNG CAO

*(Dự án: Nền tảng Dữ liệu Marketplace Rượu - Bia - Thuốc lá - Sữa)*

Tài liệu này không chỉ định nghĩa 17 kịch bản (Scenarios) mà còn cung cấp **Phương án kỹ thuật (Technical Solutions)** và **Luồng xử lý (Workflow)** cho từng trường hợp.

---

## PHẦN 1: CÁC KỊCH BẢN THU THẬP NỀN TẢNG (CORE SCRAPING)

### 1. Kịch bản Trang web tĩnh (Happy Path)

* **Đặc điểm:** HTML thuần, không chống bot, load nhanh.
* **Phương án giải quyết:** Sử dụng thư viện HTTP client nhẹ + Parser truyền thống. Không tốn chi phí render JS.
* **Luồng xử lý:** `httpx` (lấy HTML) ➡️ `BeautifulSoup` / `lxml` (bóc tách qua XPATH/CSS) ➡️ Cache vào MinIO.

### 2. Kịch bản Trang web động (SPA/JS Rendering)

* **Đặc điểm:** Nội dung render bằng React/Vue/Angular (Lazy load, cuộn mới tải).
* **Phương án giải quyết:** Phải dùng Headless Browser giả lập thao tác người xem.
* **Luồng xử lý:** Khởi tạo `Playwright` ➡️ Chạy script Auto-scroll xuống cuối trang ➡️ `page.wait_for_selector` để đảm bảo dữ liệu đã tải ➡️ Chụp DOM xuất ra MHTML.

### 3. Website đổi giao diện (UI Drift)

* **Đặc điểm:** Website thực hiện A/B test hoặc thiết kế lại (Redesign), làm gãy CSS Selectors cũ. Cào về mảng rỗng.
* **Phương án giải quyết:** Xây dựng cơ chế AI Fallback và Tự sửa lỗi (Self-healing).
* **Luồng xử lý:**
  1. ETL báo lỗi (0 products extracted).
  2. Kích hoạt `AI Smart Extract` (GEMINI): Đưa HTML rút gọn cho prompt yêu cầu JSON.
  3. Phân tích viên (`FailureAnalyzer`) dán nhãn lại class mới và tự cập nhật vào Database bảng quy tắc (`baseline_selectors`).

### 4. Yêu cầu đăng nhập (Session-based)

* **Đặc điểm:** Các cổng sỉ/B2B (wholesale portal) bắt buộc đăng nhập mới xem được giá và mã SKU đầy đủ.
* **Phương án giải quyết:** Quản lý vòng đời Cookie/Session tập trung.
* **Luồng xử lý:** Trạng thái Auth được Airflow thiết lập trước định kỳ ➡️ Playwright chèn credentials vào form đăng nhập ➡️ Trích xuất `authorization token` hoặc `cookie` ➡️ Lưu vào Redis ➡️ Tái sử dụng cookie cho các job công nhân quét hàng loạt.

---

## PHẦN 2: VƯỢT RÀO CẢN VÀ CHỐNG CHẶN (ANTI-BOT & NETWORK)

### 5. Chống Bot Mạnh (Cloudflare / WAF)

* **Đặc điểm:** Website chặn request lạ, trả về mã 403 Forbidden hoặc treo mãi mãi.
* **Phương án giải quyết:** Mô phỏng IP nhà người dùng và đánh lừa thuật toán Fingerprint của WAF.
* **Luồng xử lý:** Sử dụng Residential Proxy (proxy khu dân cư) ➡️ Gắn `playwright-stealth` (xóa biến `webdriver`, fake Canvas/WebGL) ➡️ Trích xuất mượt mà.

### 6. Rate Limit / Soft Ban (Shadow Banning)

* **Đặc điểm:** Trả kết quả rất chậm, thiếu dữ liệu random (có lúc đủ, có lúc trống), hoặc báo lỗi 429 Too Many Requests.
* **Phương án giải quyết:** Hệ thống phải biết cách tự hãm tốc độ và điều hòa số lượng luồng (Adaptive Crawl Engine).
* **Luồng xử lý:** Bộ giám sát tỷ lệ lỗi (Airflow Metrics) thấy % HTTP 429 tăng ➡️ Tự động điều chỉnh `concurrency` từ 10 xuống 2 ➡️ Giảm tốc (cooldown scheduling) ➡️ Retry with Jitter (thử lại với độ trễ ngẫu nhiên từ 1-5s).

### 7. API Hidden Discovery (Trích xuất API Ngầm)

* **Đặc điểm:** Giao diện rất rối nhưng ứng dụng ở Front-end lại gọi một API trả về chuỗi JSON cực kỳ sạch đẹp.
* **Phương án giải quyết:** Bắt trộm (Intercept) lệnh mạng thay vì cào HTML. Đây là cách hiệu quả số 1.
* **Luồng xử lý:** Playwright kích hoạt lắng nghe event mạng (`page.on('response')`) ➡️ Filter các request dạng XHR/Fetch đi qua URL `/api/products` ➡️ Parse trực tiếp JSON ra DB bỏ qua bước duyệt DOM.

### 8. CAPTCHA Challenge

* **Đặc điểm:** Hiện reCAPTCHA, Cloudflare Turnstile, hoặc kéo thanh trượt (slider).
* **Phương án giải quyết:** Chuyển hướng cho dịch vụ của bên thứ 3 giải quyết.
* **Luồng xử lý:** Phát hiện khung iframe Captcha ➡️ Cắt URL/SiteKey gửi qua API `2Captcha` / `Anti-captcha` ➡️ Đợi 10-20s nhận token giải mã ➡️ Inject token vào thẻ input ẩn ➡️ Submit form.

---

## PHẦN 3: KIỂM SOÁT LUỒNG DỮ LIỆU & CHIẾN LƯỢC QUÉT (DATA FLOW)

### 9. Pagination Phức tạp (Infinite Scroll & API Cursor)

* **Đặc điểm:** Dữ liệu nhiều trang nhưng bị ẩn dưới dạng token-based pagination hoặc graphql cursor. Job hay chết khi chạy tới nửa chừng.
* **Phương án giải quyết:** Quản lý vòng lặp dựa trên Cursor, lưu State Statefulness.
* **Luồng xử lý:**
  1. Extract tham số `next_page_token` từ file JSON trả về.
  2. Gắn token này vào request tiếp theo.
  3. Cứ 10 trang lưu `checkpoint` vào Redis. Nếu job fail ở trang 48, Cron restart sẽ đọc Redis và chạy tiếp từ trang 49, tiết kiệm tài nguyên.

### 10. Multi-location Pricing (Giá theo khu vực)

* **Đặc điểm:** GrabMart, WinMart hiển thị giá khác nhau dựa trên IP hoặc định vị cửa hàng, phân vùng user.
* **Phương án giải quyết:** Giả lập tọa độ GPS cho browser hoặc ép Cookie địa chỉ.
* **Luồng xử lý:** Định nghĩa mảng địa điểm mục tiêu (HCM, HN, Đà Nẵng) ➡️ Playwright set `geolocation` ➡️ Inject tọa độ (Vĩ độ/Kinh độ) ➡️ Capture MHTML từng version một bằng Tag `[HCM]`, `[HN]`.

### 11. Flash Sale / Real-time Monitoring

* **Đặc điểm:** Cần theo dõi sự thay đổi theo từng phút (chiến dịch đêm khuya, livestream commerce).
* **Phương án giải quyết:** Streaming pipeline thay vì Batch Pipeline.
* **Luồng xử lý:** Khởi chạy worker vòng lặp bất tận qua top sản phẩm ➡️ Cào liên tục ➡️ So sánh Hash của block giá. Chỉ khi giá thay đổi (Delta detected) mới bắn event qua Kafka / Redis PubSub để hệ thống ghi lại DB, nếu giá giữ nguyên thì ném bỏ data để tránh rác.

---

## PHẦN 4: TRÍ TUỆ NHÂN TẠO & CHUẨN HÓA (AI DEDUPLICATION)

### 12. Kịch bản Rác Dữ liệu & Giá Ảo

* **Đặc điểm:** Shop setup giá 1 VNĐ hoặc bán ốp lưng trong danh mục điện thoại.
* **Phương án giải quyết:** Chặn (Gatekeeping) bằng AI Data Quality Guard trước khi vào kho Gold.
* **Luồng xử lý:** AI nhận đầu vào, so sánh `price` với trung bình ngành hàng (Z-Score anomaly). Đánh dấu `requires_review` nếu phát hiện sai lệch > 80%.

### 13. Duplicate Product Resolution (Khử Trùng Lặp Chéo)

* **Đặc điểm:** Cùng 1 bao thuốc hoặc lon bia nhưng có tên khác nhau (Heineken 330ml thùng 24 vs Thùng 24 lon Heineken nhãn bạc).
* **Phương án giải quyết:** Gom nhóm bằng thuật toán so sánh nhúng ngực (Embeddings) và Fuzzy Matching cấu hình SKU.
* **Luồng xử lý:** Bóc tách thể tích (330ml), quy cách đóng gói (Thùng 24) ➡️ Chuyển tên thành Vector thông qua LLM Embeddings ➡️ Tính Cosine Similarity. Nếu độ giống > 95%, gán chung vào 1 `Canonical_SKU_ID` duy nhất.

### 14. Image + OCR Extraction

* **Đặc điểm:** Nồng độ rượu, thông tin tem phụ, hạn sử dụng chỉ có trên hình ảnh.
* **Phương án giải quyết:** Vision Pipeline tự động đọc chữ trên ảnh.
* **Luồng xử lý:** Crawler tải ảnh lưu vào MinIO ➡️ Gửi URL ảnh tới Google Vision API / Tesseract OCR ➡️ Lọc Regex để lấy nồng độ cồn (% Vol) và Năm sản xuất (Vintage) ➡️ Gộp (Merge) vào metadata của JSON.

### 15. Multi-language Cross-border (Hàng xách tay)

* **Đặc điểm:** Rượu ngoại xách tay viết tiếng Nhật/Pháp, barcode mã chéo.
* **Phương án giải quyết:** Chuẩn hóa dịch thuật tại Tầng Silver.
* **Luồng xử lý:** AI Normalizer phát hiện ngôn ngữ source ➡️ Dịch tên Brand sang English/Vietnamese gốc ➡️ Map với bộ từ điển Alias (VD: "サッポロ" = "Sapporo") để đảm bảo truy xuất đúng.

---

## PHẦN 5: BẢO VỆ NGƯỜI DÙNG & PHÁP CHẾ (COMPLIANCE REGTECH) - TÍNH NĂNG MŨI NHỌN

### 16. Marketplace Seller Fraud Detection (Phòng Chống Gian Lận Shop)

* **Đặc điểm:** Xuất hiện chuỗi clone shop, đánh giá ảo, giá mồi câu rẻ không tưởng.
* **Phương án giải quyết:** Máy học phân tích đồ thị (Graph Analysis) và Anomaly Detection.
* **Luồng xử lý:** Tự động giám sát tốc độ sinh ra Review/1 phút ➡️ Kiểm tra ngày thành lập shop ➡️ Áp dụng thuật toán Fraud Scoring để gán `Store_Trust_Score`. Cảnh báo Admin nếu phát hiện bất thường.

### 17. Legal / Compliance Monitoring (Giám sát Chấp hành Pháp luật)

* **Đặc điểm:** Giám sát xem website và người bán có vi phạm Luật Quảng Cáo và Luật thương mại hay không. Rất hữu ích cho **Thanh tra thị trường**.
* **Luồng xử lý bằng Compliance AI:**
  * **Sữa trẻ em:** Quét prompt `Có từ khóa khuyên dùng thay sữa mẹ dưới 24 tháng không?`
  * **Rượu bia:** Quét ảnh/text để xem có biển báo 18+ và cảnh báo không lái xe khi uống không.
  * **Thuốc lá:** Quét phát hiện hành vi kinh doanh thuốc lá điện tử lậu hoặc khuyến mãi trái quy định.
  * **Thực phẩm chức năng:** Phát hiện các từ khóa "Thần dược", "Chữa dứt điểm" vi phạm quy định y tế. Bắn Alert System PDF report để cơ quan chức năng phạt nguội.
