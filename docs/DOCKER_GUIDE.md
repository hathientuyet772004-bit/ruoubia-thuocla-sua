# 🐳 Hướng dẫn Docker - Hệ thống Thu thập Dữ liệu

Tài liệu này hướng dẫn cách triển khai hệ thống thông qua Docker để đảm bảo tính nhất quán giữa nội bộ và môi trường production.

---

## 📋 Điều kiện tiên quyết

- **Docker Desktop** đã được cài đặt ([Tải về](https://www.docker.com/products/docker-desktop))
- **RAM tối thiểu 4GB** và **Dung lượng đĩa trống 5GB**
- File `.env` chứa các biến môi trường cần thiết (GEMINI_API_KEY, DB config, v.v.)

---

## ⚡ Khởi động nhanh

### 1. Sử dụng script tự động (Khuyên dùng)

- **Windows:** Chạy file `scripts/docker-run.bat`
- **Linux/macOS:** Chạy `scripts/docker-run.sh`

### 2. Chạy thủ công bằng lệnh

```bash
# Xây dựng các images (không sử dụng cache để đảm bảo cập nhật mới nhất)
docker-compose build --no-cache

# Khởi chạy toàn bộ dịch vụ ở chế độ chạy ngầm
docker-compose up -d

# Kiểm tra trạng thái các container
docker-compose ps
```

---

## 📍 Các địa chỉ truy cập (URLs)

| Dịch vụ | URL | Mục đích |
| :--- | :--- | :--- |
| **Frontend UI** | [http://localhost](http://localhost) | Giao diện quản lý chính (Nginx proxy) |
| **Backend API** | [http://localhost/api](http://localhost/api) | Các đầu cuối API FastAPI |
| **MinIO Console** | [http://localhost:9001](http://localhost:9001) | Quản lý File thô (MHTML/HTML) |
| **Airflow UI** | [http://localhost:8085](http://localhost:8085) | Quản trị quy trình tự động (DAGs) |

---

## 📂 Cấu trúc Docker trong Dự án

Hạ tầng Docker hiện được tổ chức lại trong thư mục `infra/`:

- **Dockerfiles:** Nằm tại `infra/docker/`
  - `Dockerfile.backend`: Build cho Python service.
  - `Dockerfile.frontend`: Build cho ứng dụng React.
  - `Dockerfile.airflow`: Tùy chỉnh môi trường Airflow.
- **Config:** `infra/nginx.conf` và các script khởi tạo DB trong `infra/docker/`.

---

## 🛠️ Xử lý sự cố thường gặp (Troubleshooting)

### ❌ Lỗi "Port 80 is already in use"

Cửa sổ IIS hoặc các phần mềm khác có thể đang chiếm cổng 80.

- **Giải quyết:** Vào `docker-compose.yml`, đổi phần ports của service `nginx`:

  ```yaml
  ports:
    - "8080:80"
  ```

- Sau đó truy cập tại: `http://localhost:8080`

### ❌ Lỗi "Chromium is not available"

Hệ thống sử dụng Playwright để crawl. Nếu container backend lỗi Chromium:

- **Giải quyết:** Thử rebuild lại image backend:

  ```bash
  docker-compose build --no-cache backend
  ```

### ❌ Lỗi kết nối Database (Postgres)

- Kiểm tra logs: `docker-compose logs db`
- Đảm bảo volume `postgres_data` không bị hỏng.

---

## 🧹 Dọn dẹp hệ thống

```bash
# Dừng và xóa các container nhưng giữ lại dữ liệu
docker-compose down

# Xóa toàn bộ container và volume (⚠️ Dữ liệu DB/Storage sẽ bị mất!)
docker-compose down -v

# Dọn dẹp các images không sử dụng để giải phóng đĩa
docker image prune -a
```

---
*Cập nhật lần cuối: 2026-04-26 dựa trên cấu trúc dự án mới.*
