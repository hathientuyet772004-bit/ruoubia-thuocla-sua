# Admin Center

Hệ thống mặc định chỉ chạy Admin Center để quản trị nguồn dữ liệu, quy tắc trích xuất, raw artifacts cục bộ, dữ liệu sản phẩm và hàng đợi rà soát trùng lặp.

## Runtime

Stack Docker mặc định gồm:

- `backend`: FastAPI Admin Center API.
- `frontend`: React Admin Center.
- `nginx`: cùng origin cho frontend và `/api`.

MongoDB Atlas lưu nguồn dữ liệu, sản phẩm, lịch sử giá từ offers, task/raw page và workflow state của Admin Center. Raw page lớn có thể được lưu trong GridFS và tham chiếu bằng `gridfs_file_id` trong `sc_raw_pages`.

Runtime mặc định của Admin Center chỉ cần MongoDB Atlas và ba container web trong Compose.

Admin Center đang chạy theo mô hình nội bộ: không hiển thị trang đăng nhập và không yêu cầu cookie session cho API quản trị.
Khi `ENV=production`, backend vẫn kiểm tra MongoDB URI và CORS để tránh chạy bằng placeholder.

## Cấu hình môi trường

- Dev local không cần Nginx: chạy frontend ở `3000` và backend ở `8000`.
- Docker local dùng Nginx làm entrypoint duy nhất, mặc định publish `HOST_HTTP_PORT=80`.
- Production dùng `docker-compose.prod.yml` để publish thêm `HOST_HTTPS_PORT=443` sau khi SSL đã cấu hình trong `infra/nginx.conf`.
- Backend và frontend chỉ dùng port nội bộ trong Docker network: backend `BACKEND_PORT=8080`, frontend `FRONTEND_PORT=3000`.
- Worker mặc định không tự chạy pipeline `manual` (`WORKER_RUN_MANUAL_PIPELINES=false`) để tránh ghi raw pages lặp lại vào Atlas.

Kiểm tra file env trước khi chạy:

```bash
python scripts/validate-env.py --env-file .env
```

Với production, script sẽ chặn placeholder MongoDB URI và CORS placeholder. Nếu bật lại `ADMIN_AUTH_ENABLED=true`, script cũng chặn password/secret mặc định.

## Chạy bằng Docker

```bash
cp .env.example .env
docker compose up --build
```

Mở `http://localhost`.

- `/api/health` chỉ kiểm tra process API đang sống.
- `/api/ready` kiểm tra MongoDB Atlas và index cần cho Admin Center.
- Docker mode chỉ publish Nginx qua `HOST_HTTP_PORT` mặc định `80`; backend `8080` và frontend `3000` chỉ mở trong Docker network.
- Production chỉ publish `HOST_HTTPS_PORT` mặc định `443` qua `docker-compose.prod.yml` sau khi đã cấu hình SSL trong `infra/nginx.conf`.

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
CI cũng build Docker Compose và kiểm tra Nginx proxy tới frontend và `/api/health`; `/api/ready` vẫn là smoke local vì cần MongoDB Atlas thật.

## Dữ liệu Admin Center

- `sources` lưu nguồn dữ liệu quản trị.
- Trang nguồn hỗ trợ nhập/xuất CSV với các cột `name,url,type,category,note`; file xuất có timestamp trong tên.
- Trang sản phẩm hỗ trợ lọc theo cửa hàng/kênh bán và xuất CSV giá bán với các cột `name,price,original_price,currency,price_status,source,category,brand,store_name,store_url,store_address,store_channel,address_status,store_phone,data_origin,rule_version,extraction_method,validation_score,url,updated_at`; file xuất có timestamp trong tên.
- `sc_products` và `sc_offers` cấp dữ liệu sản phẩm, giá và xu hướng.
- `sc_crawl_tasks` và `sc_raw_pages` cấp lượt chạy và raw artifacts; raw content có thể nằm trực tiếp trong document hoặc GridFS.
- Raw artifacts được giới hạn để tránh vượt quota Atlas: mỗi response mặc định tối đa `WORKER_MAX_RESPONSE_BYTES=1000000`, mỗi vòng crawl tối đa `WORKER_MAX_PAGE_BUDGET=20`, cùng URL không crawl lại trong `WORKER_RECRAWL_MIN_HOURS=24`, raw pages cũ được dọn sau `WORKER_RAW_PAGE_RETENTION_DAYS=14`, và mỗi domain giữ tối đa `WORKER_MAX_RAW_PAGES_PER_DOMAIN=100`.
- `admin_dedup_candidates` và `admin_rule_events` lưu trạng thái rà soát trong Admin Center.
- `admin_extraction_rules` lưu selector rules; các JSON trong `backend/structures` chỉ seed rule ban đầu khi collection còn trống.
- `store/raw` và `store/outputs` có thể cấp file local cho selector preview hoặc dữ liệu nhập tay trong môi trường phát triển; UI/API sản phẩm mặc định chỉ hiển thị dữ liệu từ Atlas. Đặt `ADMIN_PRODUCT_LOCAL_FALLBACK_ENABLED=true` nếu cần bật lại fallback local khi dev.

## Gemini hỗ trợ tạo rule

- Đặt `GEMINI_API_KEY` để bật endpoint AI phân tích HTML.
- `POST /api/extraction/ai/analyze` nhận `domain`, `raw_artifact_id` hoặc `html`, gọi Gemini để sinh draft rule và tự kiểm tra bằng preview selector.
- Mặc định dùng `GEMINI_MODEL=gemini-2.5-flash`, có thể đổi sang model khác bằng env.

## Batch Gemini

- Dùng `python scripts/batch-gemini-analyze.py --domain ruoutot.net --domain maltco.vn` để chạy phân tích nhiều domain qua cùng endpoint.
- Có thể dùng `--domains-file domains.txt` và `--output results.jsonl` nếu muốn chạy hàng loạt và lưu kết quả.
- `make batch-gemini BATCH_DOMAINS="ruoutot.net maltco.vn"` là lối gọi ngắn cho cùng script.

## Secrets

File `.env` local đã được ignore và không nên commit. Nếu URI hoặc secret từng xuất hiện trong log, chat, issue hoặc CI output, hãy rotate credential đó ở MongoDB Atlas.
