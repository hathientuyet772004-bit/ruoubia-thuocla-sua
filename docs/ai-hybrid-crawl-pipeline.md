# AI Hybrid Crawl Pipeline cho website khó crawl

Tài liệu này mô tả kiến trúc đề xuất cho một pipeline AI chạy song song với crawler hiện tại để xử lý các website khó crawl bằng cơ chế tự động, không cần người can thiệp ở vòng lặp chính.

## Mục tiêu

- Xử lý các website khó crawl bằng pipeline thông thường.
- Dùng Gemini làm lớp trích xuất, chuẩn hóa và tự kiểm định dữ liệu.
- Không hardcode schema Silver.
- Cho phép fallback hoặc augmentation khi crawler thường thất bại.
- Mở rộng được cho nhiều website, nhiều ngành hàng, nhiều chiến lược thu thập.

## Pipeline đầu tiên: crawler thường

Đây là luồng mặc định cho các website có thể crawl bằng cách thông thường. Mục tiêu của pipeline này là lấy dữ liệu nhanh, rẻ, ổn định trước khi đẩy sang AI pipeline.

### Luồng xử lý

`Source Registry -> URL Discovery -> HTTP Fetch -> HTML Parse -> Rule Extract -> Normalize -> Validate -> Silver Write`

### Vai trò từng bước

- **Source Registry**: xác định domain, category, policy, và trạng thái source.
- **URL Discovery**: tìm URL danh mục, trang sản phẩm, trang cửa hàng, hoặc trang tin có cấu trúc dữ liệu.
- **HTTP Fetch**: lấy HTML tĩnh nếu site cho phép.
- **HTML Parse**: phân tích DOM và selector theo rule có sẵn.
- **Rule Extract**: áp dụng extraction rules đã lưu trong Atlas/config.
- **Normalize**: chuẩn hóa kiểu dữ liệu, tên, giá, địa chỉ, URL.
- **Validate**: kiểm tra đủ field, đủ số lượng, và loại bỏ dữ liệu lỗi.
- **Silver Write**: ghi record hợp lệ vào Silver layer.

### Khi nào pipeline này đủ dùng

- Site không cần login.
- Site không chống bot mạnh.
- HTML có cấu trúc rõ.
- Listing/detail/store có thể trích xuất bằng selector ổn định.
- Dữ liệu thu được đã đủ chất lượng để ghi thẳng Silver.

### Khi nào pipeline này phải nhường cho AI pipeline

- HTTP fetch thất bại hoặc bị chặn.
- HTML tải về rỗng hoặc thiếu dữ liệu.
- Layout render bằng JavaScript.
- Dữ liệu nằm sau thao tác người dùng.
- Có shadow DOM, iframe, lazy loading, infinite scroll.
- Rule selector không còn ổn định.

## Các trường hợp cần pipeline AI

Pipeline AI phù hợp khi website có một hoặc nhiều đặc điểm sau:

- Có login hoặc session.
- Có CAPTCHA hoặc anti-bot.
- Nội dung render động bằng JavaScript.
- Infinite scroll hoặc load more.
- Dữ liệu nằm ở API ẩn.
- Shadow DOM, iframe, lazy loading.
- Nội dung chỉ xuất hiện sau thao tác người dùng.
- Nội dung thay đổi theo khu vực, user-agent, cookie, locale.
- Website thương mại điện tử có layout phức tạp, nhiều lớp DOM, nhiều trạng thái hiển thị.

## Kiến trúc tổng quan

Luồng đề xuất:

`Source Registry -> Acquisition Planner -> Fetch/Capture Workers -> AI Extraction Workers -> Validation/Normalization -> Silver Writer`

### 1. Source Registry

Lưu metadata nguồn:

- domain
- loại website
- category
- rule version
- capability profile
- source config
- auth/session policy
- region/user-agent policy
- retry policy
- AI enabled flag

### 2. Acquisition Planner

Thành phần này quyết định nguồn nào đi theo luồng nào:

- crawler HTTP thường
- browser capture
- AI fallback
- hybrid augmentation
- human review queue nếu cần

Planner không tự trích xuất dữ liệu. Nhiệm vụ của nó là chọn chiến lược và budget.

### 3. Fetch/Capture Workers

Các worker này chịu trách nhiệm thu evidence:

- HTML
- DOM snapshot
- screenshot
- network hints
- metadata trang
- URL thật
- trạng thái session

Nếu site động hoặc có anti-bot, worker có thể dùng browser automation thay vì fetch HTML tĩnh.

### 4. AI Extraction Workers

Gemini đọc bundle evidence và sinh structured JSON.

Nhiệm vụ:

- nhận diện page type
- trích xuất semantic fields
- mapping field sang contract hiện có
- phát hiện dữ liệu thiếu
- chuẩn hóa output theo JSON contract
- sinh confidence và evidence notes

### 5. Validation / Normalization

Không ghi thẳng vào Silver.

Phải kiểm tra:

- output có phải JSON hợp lệ không
- field bắt buộc có đủ không
- URL có thật không
- price có hợp lệ không
- product/store name có sạch không
- item có trùng không
- confidence có đạt ngưỡng không

Sau đó mới normalize:

- chuẩn hóa tên
- chuẩn hóa giá
- chuẩn hóa địa chỉ
- chuẩn hóa store/product mapping
- chuẩn hóa type/unit/category

### 6. Silver Writer

Silver không hardcode schema trong code.

Silver writer phải đọc schema từ:

- Atlas/configuration
- rule catalog
- metadata của source
- mapping rules hiện có

Silver writer chỉ ghi khi:

- contract hợp lệ
- validation pass
- confidence đủ
- version đúng

## Pipeline song song

Hệ thống nên có 2 pipeline chạy song song:

### Pipeline A: crawler thường

- fetch HTML
- parse DOM
- extract
- validate
- write Silver

### Pipeline B: AI pipeline

- capture raw evidence
- Gemini extraction
- validation
- normalization
- write Silver

AI pipeline trở thành fallback khi crawler thường không đủ dữ liệu, hoặc trở thành augmentation pipeline khi crawler lấy được một phần dữ liệu.

## Fallback strategy

Fallback theo thứ tự đề xuất:

1. Crawler HTTP thường
2. Browser capture
3. AI extraction trên HTML/DOM/screenshot
4. AI augmentation trên dữ liệu thiếu
5. Retry với chiến lược khác
6. Đẩy vào review queue nếu vẫn không đạt

## Schema discovery strategy

Silver schema không nên hardcode.

Thay vào đó:

- đọc mapping hiện có trong Atlas/config
- infer field candidates từ rule catalog
- lấy mẫu output trước đó để đo field stability
- cho Gemini đề xuất mapping candidate
- validator quyết định accept/reject

Điều này giúp hệ thống mở rộng cho nhiều website mà không phải sửa code Silver mỗi lần.

## Gemini prompt strategy

Prompt nên chia thành 3 lớp:

### 1. Planner prompt

Quyết định:

- trang nào nên mở tiếp
- evidence nào cần thu thêm
- nguồn nào cần browser capture
- có thể dùng fallback hay không

### 2. Extractor prompt

Đọc evidence và sinh JSON.

Yêu cầu:

- JSON only
- không hallucinate
- chỉ dùng evidence thật
- có confidence
- có notes

### 3. Validator prompt

Đánh giá output:

- đủ quota chưa
- có duplicate không
- có field thiếu không
- có URL/price/store hợp lệ không
- có cần retry không

## Với website khó crawl

### Login / session

- dùng session hợp lệ nếu source cho phép
- lưu policy riêng cho source
- không xem đây là luồng mặc định

### CAPTCHA / anti-bot

- ưu tiên browser capture hợp lệ
- backoff và rate limiting
- không thiết kế hệ thống phụ thuộc vào bypass

### JS render / infinite scroll / shadow DOM / iframe

- browser capture worker phải lấy DOM snapshot sau render
- screenshot chỉ đóng vai trò evidence bổ trợ
- nếu cần, capture network để suy ra endpoint hợp lệ

### Region / user-agent

- source profile phải khai báo region, locale, UA, cookies
- AI chỉ đọc evidence theo profile đó

## Retry flow

Retry nên theo hai lớp:

### Technical retry

- timeout
- 5xx
- lỗi network
- parse lỗi tạm thời

### Semantic retry

- thiếu item
- thiếu field bắt buộc
- confidence thấp
- duplicate quá nhiều
- query quá hẹp

AI có thể tự broadening query, tự đổi strategy hoặc tự chuyển sang browser capture nếu chưa đủ dữ liệu.

## Caching

Nên cache theo:

- source
- URL
- content hash
- screenshot hash
- prompt hash
- model version
- schema version

Cache giúp:

- giảm chi phí Gemini
- giảm latency
- tránh xử lý lại cùng một evidence

## Cost optimization

- chỉ gọi Gemini cho source khó hoặc khi crawler thất bại
- dùng model nhỏ trước, model mạnh sau
- giới hạn token theo source/day
- cache output theo hash
- batch xử lý cùng loại evidence

## Observability

Nên log và trace:

- source id
- domain
- stage timing
- evidence hash
- prompt version
- model version
- token usage
- validation score
- retry count
- final decision

Mục tiêu là biết chính xác:

- stage nào chậm
- stage nào fail
- source nào tốn chi phí cao
- output nào phải retry nhiều

## Audit log

Mỗi extraction cần lưu:

- input metadata
- prompt version
- model version
- raw output hash
- validation result
- normalization result
- writer decision
- override/retry history

Audit log giúp truy vết khi có sai lệch dữ liệu.

## Versioning

Nên version:

- source config
- schema contract
- prompt template
- transform rules
- validation rules
- output format

Không nên dùng một schema cứng cho mọi nguồn.

## Ưu điểm

- xử lý được site khó crawl
- mở rộng cho nhiều nguồn
- giảm phụ thuộc vào rule thủ công
- có thể tự động fallback
- phù hợp kiến trúc event-driven

## Hạn chế

- chi phí AI cao hơn crawler thường
- latency tăng
- cần governance chặt
- vẫn có rủi ro hallucination nếu validation yếu
- login/CAPTCHA không nên kỳ vọng xử lý 100% tự động

## Tác động lên hệ thống hiện tại

Hệ thống hiện tại đã có các thành phần phù hợp để mở rộng:

- source registry
- raw artifact store
- rule registry
- Mongo-backed product/store views
- Gemini extraction hook

Phần còn thiếu là:

- acquisition planner riêng
- browser capture worker
- queue tách biệt cho AI pipeline
- schema registry cho Silver
- validation/normalization layer độc lập

## Kết luận

Thiết kế phù hợp nhất là **hybrid, modular, event-driven**:

- crawler thường xử lý nguồn dễ
- AI pipeline xử lý nguồn khó
- validation quyết định có ghi Silver hay không
- schema Silver lấy từ cấu hình, không hardcode

Đây là cách duy trì khả năng mở rộng mà vẫn kiểm soát được chất lượng dữ liệu.
