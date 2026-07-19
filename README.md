# Admin Center

Hệ thống mặc định chạy Admin Center để quản trị nguồn dữ liệu, pipeline thu thập, quy tắc trích xuất, raw artifacts, dữ liệu sản phẩm, giá bán và batch dữ liệu do AI sinh. Các màn `AI duyệt` và `Rà soát trùng lặp` đang được ẩn khỏi giao diện vì hiện chưa dùng trong luồng vận hành chính.

## Runtime

Stack Docker mặc định gồm:

- `backend`: FastAPI Admin Center API.
- `frontend`: React Admin Center.
- `nginx`: cùng origin cho frontend và `/api`.
- `postgres`: PostgreSQL lưu dữ liệu vận hành.

PostgreSQL lưu nguồn dữ liệu, sản phẩm, lịch sử giá từ offers, task/raw page và workflow state của Admin Center. Raw page content được lưu trong `sc_raw_pages.content`, đồng thời worker vẫn ghi bản sao cục bộ vào `store/raw` để debug.

Runtime mặc định của Admin Center chạy bằng PostgreSQL và ba container web trong Compose.

Admin Center đang chạy theo mô hình nội bộ: không hiển thị trang đăng nhập và không yêu cầu cookie session cho API quản trị.
Khi `ENV=production`, backend kiểm tra `DATABASE_URL`/`PG_URL` và CORS để tránh chạy bằng placeholder.

## Cấu hình môi trường

- Dev local không cần Nginx: chạy frontend ở `3000` và backend ở `8000`.
- Docker local dùng Nginx làm entrypoint duy nhất, mặc định publish `HOST_HTTP_PORT=80`.
- Production dùng `docker-compose.prod.yml` để publish thêm `HOST_HTTPS_PORT=443` sau khi SSL đã cấu hình trong `infra/nginx.conf`.
- Backend và frontend chỉ dùng port nội bộ trong Docker network: backend `BACKEND_PORT=8080`, frontend `FRONTEND_PORT=3000`.
- Worker mặc định không tự chạy pipeline `manual` (`WORKER_RUN_MANUAL_PIPELINES=false`) để tránh ghi raw pages lặp lại vào PostgreSQL.

Kiểm tra file env trước khi chạy:

```bash
python scripts/validate-env.py --env-file .env
```

Với production, script sẽ chặn cấu hình thiếu PostgreSQL connection string và CORS placeholder. Nếu bật lại `ADMIN_AUTH_ENABLED=true`, script cũng chặn password/secret mặc định.

## Setup Trên Máy Tính

Yêu cầu cài sẵn:

- Docker Desktop, bật Linux containers.
- Git.
- Python 3.11 trở lên nếu muốn chạy test/script local.
- Node.js 18 trở lên nếu muốn build frontend ngoài Docker.

Clone hoặc mở thư mục dự án:

```bash
cd D:\datasets\ruoubia-thuocla-sua
```

Tạo file môi trường:

```bash
copy .env.example .env
```

Nếu máy đã dùng port PostgreSQL `5432`, đổi port host trong `.env`:

```env
HOST_POSTGRES_PORT=15432
```

Nếu port web `80` đã bận, đổi:

```env
HOST_HTTP_PORT=8088
```

Nếu dùng Gemini để sinh rule hoặc tạo dữ liệu, điền:

```env
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash
```

Lưu ý Gemini free tier có giới hạn quota. Khi gặp lỗi `429 quota exceeded`, đợi hết thời gian retry hoặc dùng key/billing có quota cao hơn.

Kiểm tra env:

```bash
python scripts\validate-env.py --env-file .env
```

## Chạy Bằng Docker

```bash
docker compose up --build
```

Mở `http://localhost` nếu dùng `HOST_HTTP_PORT=80`. Nếu đổi port, mở `http://localhost:<HOST_HTTP_PORT>`.

- `/api/health` chỉ kiểm tra process API đang sống.
- `/api/ready` kiểm tra PostgreSQL connection.
- Docker mode chỉ publish Nginx qua `HOST_HTTP_PORT` mặc định `80`; backend `8080` và frontend `3000` chỉ mở trong Docker network.
- Production chỉ publish `HOST_HTTPS_PORT` mặc định `443` qua `docker-compose.prod.yml` sau khi đã cấu hình SSL trong `infra/nginx.conf`.

Các lệnh thường dùng:

```bash
docker compose ps
docker compose logs --tail=200 backend
docker compose logs --tail=200 worker
docker compose restart backend
docker compose down
```

Khi đổi code backend/frontend:

```bash
docker compose up -d --build backend frontend nginx
```

Khi muốn rebuild toàn bộ:

```bash
docker compose up -d --build
```

## Kiểm Tra Sau Khi Chạy

```bash
curl http://localhost/api/health
curl http://localhost/api/ready
curl "http://localhost/api/products/search?limit=5&source=all&category=all"
```

Kết quả mong muốn:

- `/api/health` trả `{"status":"ok","app":"Admin Center"}`.
- `/api/ready` trả `{"status":"ready","database":"PostgreSQL"}`.
- `/api/products/search` trả danh sách JSON, hoặc `[]` nếu chưa có sản phẩm.

Kiểm tra trực tiếp PostgreSQL trong Docker:

```bash
docker compose exec postgres psql -U admin_center -d admin_center -c "SELECT COUNT(*) FROM sc_products;"
docker compose exec postgres psql -U admin_center -d admin_center -c "SELECT domain, COUNT(*) FROM sc_products GROUP BY domain ORDER BY count DESC;"
```

Nếu `.env` dùng user mặc định khác, thay `-U admin_center -d admin_center` theo `POSTGRES_USER` và `POSTGRES_DB`.

## Hướng Dẫn Sử Dụng Admin Center

### 1. Nguồn Dữ Liệu

Mở `Nguồn dữ liệu` để xem danh sách website đang quản lý.

- `Có trang thô`: nguồn đã có HTML/raw page trong PostgreSQL.
- `Sản phẩm`: số sản phẩm đã ghi vào `sc_products`.
- `Cách ly`: số dòng bị chặn ở `sc_product_quarantine`.
- Nút `Chạy`: tạo hoặc dùng pipeline của nguồn đó và chạy thu thập nền.

Sau khi bấm `Chạy`, UI sẽ tự kiểm tra lượt chạy mới và báo kết quả thật: hoàn tất, thất bại hoặc bị chặn, kèm số trang thô và số sản phẩm.

### 2. Pipeline

Mở `Pipeline` để xem các pipeline crawler.

- `Pipeline mới`: tạo pipeline thủ công cho một hoặc nhiều source.
- `Đang bật`: pipeline được worker tự quét nếu có lịch.
- `Đang chạy`: pipeline đang giữ lease chạy.

Pipeline thủ công từ nút `Chạy` trên nguồn thường có id dạng `source-<source_id>`.

### 3. Lượt Chạy

Mở `Lượt chạy` để kiểm tra kết quả từng lần crawl.

Các trạng thái hay gặp:

- `Hoàn tất`: có thể chạy xong và đã ghi sản phẩm, hoặc không có lỗi chặn.
- `Bị chặn`: có trang thô nhưng thiếu rule hợp lệ, Gemini bị quota, hoặc quality gate không cho ghi.
- `Thất bại`: không capture được trang thô, lỗi network hoặc lỗi hệ thống.

Cột `Cảnh báo` rất quan trọng:

- `Capture produced no usable raw pages`: crawler không lấy được HTML dùng được.
- `Gemini skipped ... 429`: Gemini hết quota nên không học rule mới.
- `quality gate blocked write`: rule yếu, không đủ coverage trường bắt buộc.
- `no raw artifacts are available`: nguồn chưa có trang thô để parse.

### 4. Quy Tắc Trích Xuất

Mở `Quy tắc trích xuất` để kiểm thử selector trên raw page.

Luồng cơ bản:

1. Chọn domain.
2. Chọn raw page.
3. Chọn target như `Chi tiết sản phẩm` hoặc listing.
4. Điền selector cho các trường như `product_name`, `price`, `image_url`, `product_url`.
5. Bấm `Kiểm thử`.
6. Nếu số khớp và mẫu đúng, bấm `Lưu quy tắc`.

Rule tốt giúp writer ghi sản phẩm mà không cần gọi Gemini lại.

### 5. Duyệt Rule AI

Mở `Duyệt Rule AI` để xem rule candidate do Gemini tạo.

- `Có thể duyệt`: candidate đạt quality gate và có thể promote thành rule chính thức.
- `Đã duyệt`: rule đã được promote.
- `Đã từ chối`: candidate bị loại hoặc không đạt.

Nếu Gemini hết quota, danh sách này có thể không có candidate mới.

### 6. Sản Phẩm & Giá Bán

Mở `Sản phẩm & giá bán` để xem dữ liệu trong `sc_products`.

- Dữ liệu lấy từ endpoint `/api/products/search`.
- Có thể tìm theo tên, lọc theo nguồn hoặc cửa hàng.
- Nút `Tải CSV` xuất dữ liệu sản phẩm và giá.

Kiểm tra nhanh bằng API:

```bash
curl "http://localhost/api/products/search?limit=10&source=all&category=all"
```

### 7. Tạo Dữ Liệu

Mở `Tạo dữ liệu` để sinh batch dữ liệu bằng Gemini.

Các trường quan trọng:

- `Nguồn dữ liệu`: nguồn dùng làm ngữ cảnh.
- `Số dòng`: nên dùng `3-10` khi test để tránh quota.
- `Chế độ Synthetic`: dữ liệu mô phỏng có kiểm tra schema.
- `Chế độ Grounded synthetic`: yêu cầu có raw page evidence.
- `Lưu vào kho dữ liệu`: lưu vào `sc_synthetic_products`, không trộn trực tiếp vào `sc_products`.

Batch đã sinh nằm ở `Batch dữ liệu gần đây`. Dữ liệu synthetic và dữ liệu product thật là hai kho khác nhau:

- `sc_products`: sản phẩm/giá từ crawler, rule hoặc backfill.
- `sc_synthetic_products`: dữ liệu do Gemini sinh để tham khảo/demo.

### 8. Xem Trang Thô

Mở `Xem trang thô` hoặc bấm link raw page từ `Lượt chạy` để kiểm tra HTML crawler đã lưu.

Dùng màn này khi:

- Source có raw page nhưng không ra sản phẩm.
- Cần xem page bị chặn, thiếu nội dung, redirect, hoặc HTML động.
- Cần lấy selector cho `Quy tắc trích xuất`.

## Khi Không Thu Được Sản Phẩm

Kiểm tra theo thứ tự:

1. Vào `Nguồn dữ liệu`, xem source có `Có trang thô` không.
2. Vào `Lượt chạy`, xem cảnh báo của run mới nhất.
3. Nếu không có raw page, kiểm tra website có chặn crawler hoặc cần browser fallback không.
4. Nếu có raw page nhưng `0 sản phẩm`, kiểm tra rule trong `Quy tắc trích xuất`.
5. Nếu cảnh báo Gemini `429`, đợi quota hoặc dùng key có quota cao hơn.
6. Nếu cảnh báo `quality gate blocked write`, mở rule và kiểm thử selector để tăng coverage.
7. Kiểm tra bảng product:

```bash
docker compose exec postgres psql -U admin_center -d admin_center -c "SELECT COUNT(*) FROM sc_products;"
docker compose exec postgres psql -U admin_center -d admin_center -c "SELECT COUNT(*) FROM sc_product_quarantine;"
```

## Production Compose Và SSL

Production dùng file:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Trước khi chạy production:

- Đổi `ENV=production`.
- Đặt `DATABASE_URL` hoặc `PG_URL` thật.
- Đổi `POSTGRES_PASSWORD`, `ADMIN_PASSWORD`, `ADMIN_SESSION_SECRET`.
- Đặt `CORS_ALLOW_ORIGINS` đúng domain thật, không dùng placeholder rộng.
- Cấu hình SSL trong `infra/nginx.conf` và mount certificate theo đường dẫn production.
- Chạy `python scripts\validate-env.py --env-file .env` để bắt lỗi cấu hình.

## Kiểm thử

```bash
make test-backend
make test-frontend
make smoke-docker
```

- `make test-backend` chạy unittest cho API và route frontend smoke.
- `make test-frontend` build React app bằng Vite.
- `make smoke-docker` build stack Docker, recreate Nginx để tránh upstream DNS cũ, rồi kiểm tra `/`, `/api/health`, `/api/ready`.

GitHub Actions chạy backend tests và frontend build trên mỗi push vào `main` và pull request.
CI cũng build Docker Compose và kiểm tra Nginx proxy tới frontend và `/api/health`; smoke local kiểm tra thêm `/api/ready` với PostgreSQL thật trong Compose.

## Dữ liệu Admin Center

- `sources` lưu nguồn dữ liệu quản trị.
- Trang nguồn hỗ trợ nhập/xuất CSV với các cột `name,url,type,category,note`; file xuất có timestamp trong tên.
- Trang sản phẩm hỗ trợ lọc theo cửa hàng/kênh bán và xuất CSV giá bán với các cột `name,price,original_price,currency,price_status,source,category,brand,store_name,store_url,store_address,store_channel,address_status,store_phone,data_origin,rule_version,extraction_method,validation_score,url,updated_at`; file xuất có timestamp trong tên.
- `sc_products` và `sc_offers` cấp dữ liệu sản phẩm, giá và xu hướng.
- `sc_crawl_tasks` và `sc_raw_pages` cấp lượt chạy và raw artifacts; raw content nằm trong PostgreSQL và bản sao local `store/raw`.
- Raw artifacts được giới hạn để tránh phình storage: mỗi response mặc định tối đa `WORKER_MAX_RESPONSE_BYTES=1000000`, mỗi vòng crawl tối đa `WORKER_MAX_PAGE_BUDGET=20`, cùng URL không crawl lại trong `WORKER_RECRAWL_MIN_HOURS=24`, raw pages cũ được dọn sau `WORKER_RAW_PAGE_RETENTION_DAYS=14`, và mỗi domain giữ tối đa `WORKER_MAX_RAW_PAGES_PER_DOMAIN=100`.
- `admin_dedup_candidates` và `admin_rule_events` lưu trạng thái rà soát trong Admin Center.
- `admin_extraction_rules` lưu selector rules; các JSON trong `backend/structures` chỉ seed rule ban đầu khi collection còn trống.
- `store/raw` và `store/outputs` có thể cấp file local cho selector preview hoặc dữ liệu nhập tay trong môi trường phát triển; UI/API sản phẩm mặc định chỉ hiển thị dữ liệu từ PostgreSQL. Đặt `ADMIN_PRODUCT_LOCAL_FALLBACK_ENABLED=true` nếu cần bật lại fallback local khi dev.

## Gemini hỗ trợ tạo rule

- Đặt `GEMINI_API_KEY` để bật endpoint AI phân tích HTML.
- `POST /api/extraction/ai/analyze` nhận `domain`, `raw_artifact_id` hoặc `html`, gọi Gemini để sinh draft rule và tự kiểm tra bằng preview selector.
- Mặc định dùng `GEMINI_MODEL=gemini-2.5-flash`, có thể đổi sang model khác bằng env.

## Batch Gemini

- Dùng `python scripts/batch-gemini-analyze.py --domain ruoutot.net --domain maltco.vn` để chạy phân tích nhiều domain qua cùng endpoint.
- Có thể dùng `--domains-file domains.txt` và `--output results.jsonl` nếu muốn chạy hàng loạt và lưu kết quả.
- `make batch-gemini BATCH_DOMAINS="ruoutot.net maltco.vn"` là lối gọi ngắn cho cùng script.

## Secrets

File `.env` local đã được ignore và không nên commit. Nếu database URI hoặc secret từng xuất hiện trong log, chat, issue hoặc CI output, hãy rotate credential đó ở hệ quản trị tương ứng.
