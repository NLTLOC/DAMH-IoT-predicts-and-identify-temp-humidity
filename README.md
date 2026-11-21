# Giao diện theo dõi nhiệt độ và độ ẩm (Django)

## Chạy thử
```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo --clear --live   # số liệu mẫu 24 giờ, rồi sinh thêm mỗi 5 giây
python manage.py runserver                   # mở http://127.0.0.1:8000
```
(Chạy `seed_demo --live` ở một terminal, `runserver` ở terminal khác.)

## Gắn ESP32
POST JSON tới `/api/ingest/` với header `X-API-Key` (đổi trong `config/settings.py` hoặc biến môi trường `INGEST_API_KEY`):
```json
{"temperature": 28.5, "humidity": 71.2, "device": "esp32-01"}
```

## Gắn AI sau này
Viết lớp kế thừa `BaseForecaster` trong `monitor/forecasting.py` (hàm `predict`), rồi đổi `FORECASTER_CLASS` trong `config/settings.py`.
Giao diện, biểu đồ và bảng dự báo không cần sửa.
