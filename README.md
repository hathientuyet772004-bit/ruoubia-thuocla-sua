# Admin Center

Hệ thống mặc định chỉ chạy Admin Center để quản trị nguồn dữ liệu, quy tắc trích xuất, raw artifacts cục bộ, dữ liệu sản phẩm và hàng đợi rà soát trùng lặp.

## Runtime

Stack Docker mặc định gồm:

- `backend`: FastAPI Admin Center API.
- `frontend`: React Admin Center.
- `nginx`: cùng origin cho frontend và `/api`.

MongoDB Atlas lưu nguồn dữ liệu, sản phẩm, lịch sử giá từ offers, task/raw page và workflow state của Admin Center. Raw page lớn có thể được lưu trong GridFS và tham chiếu bằng `gridfs_file_id` trong `sc_raw_pages`.

Runtime mặc định của Admin Center chỉ cần MongoDB Atlas và ba container web trong Compose.

Admin Center dùng login backend và cookie session `HttpOnly` cho thao tác quản trị. Đặt `ADMIN_PASSWORD` và `ADMIN_SESSION_SECRET` trong `.env` trước khi dùng ngoài môi trường dev.

## Chạy bằng Docker

```bash
cp .env.example .env
docker compose up --build
```

Mở `http://localhost`.

- `/api/health` chỉ kiểm tra process API đang sống.
- `/api/ready` kiểm tra MongoDB Atlas và index cần cho Admin Center.

## Dữ liệu Admin Center

- `sources` lưu nguồn dữ liệu quản trị.
- `sc_products` và `sc_offers` cấp dữ liệu sản phẩm, giá và xu hướng.
- `sc_crawl_tasks` và `sc_raw_pages` cấp lượt chạy và raw artifacts; raw content có thể nằm trực tiếp trong document hoặc GridFS.
- `admin_dedup_candidates` và `admin_rule_events` lưu trạng thái rà soát trong Admin Center.
- `admin_extraction_rules` lưu selector rules; các JSON trong `backend/structures` chỉ seed rule ban đầu khi collection còn trống.
- `store/raw` và `store/outputs` có thể cấp file local cho selector preview hoặc dữ liệu nhập tay trong môi trường phát triển.
