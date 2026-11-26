# Giao diện theo dõi nhiệt độ và độ ẩm (Django)

## Chạy thử
```bash
pip install -r monitor/requirements.txt
python manage.py migrate
python manage.py seed_demo --clear --live   # số liệu mẫu 24 giờ, rồi sinh thêm mỗi 5 giây
python manage.py runserver                   # mở http://127.0.0.1:8000
```
(Chạy `seed_demo --live` ở một terminal, `runserver` ở terminal khác.)

## Chạy Django và AI bằng Docker
```bash
docker compose up --build
```
Django chạy ở `http://localhost:8000`; FastAPI chạy ở `http://localhost:8001`.
SQLite được giữ trong `db.sqlite3` ở thư mục gốc.

## Gắn ESP32
POST JSON tới `/api/ingest/` với header `X-API-Key` (đổi trong `config/settings.py` hoặc biến môi trường `INGEST_API_KEY`):
```json
{"temperature": 28.5, "humidity": 71.2, "device": "esp32-01"}
```

## Gắn AI sau này
Django gọi dịch vụ FastAPI tại `/forecast` (địa chỉ cấu hình bằng `AI_SERVICE_URL`).
Chạy cả hai dịch vụ bằng `docker compose up --build`; FastAPI trả về sáu dự báo theo giờ.

Khi triển khai, đặt `DJANGO_SECRET_KEY`, `INGEST_API_KEY` và `DJANGO_ALLOWED_HOSTS`
trong môi trường hoặc file `.env`. Các giá trị mặc định trong Compose chỉ dành cho phát triển.
