import json
from datetime import timedelta

from django.conf import settings
import logging

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import exports
from .advice import build_advice
from .forecasting import get_forecaster
from .models import Reading

logger = logging.getLogger(__name__)
ALLOWED_RANGES = (60, 180, 360, 1440)
OFFLINE_AFTER = timedelta(minutes=3)
HORIZON, STEP = 60, 10


def api_export(request):
    """Tải số liệu của N phút gần nhất: /api/export/?minutes=60&format=csv|json"""
    try:
        minutes = int(request.GET.get("minutes", 60))
    except ValueError:
        minutes = 60
    if minutes not in ALLOWED_RANGES:
        minutes = 60
    end = timezone.now()
    start = end - timedelta(minutes=minutes)
    rows = exports.fetch(start, end)
    name = exports.base_name(start, end)
    if request.GET.get("format") == "json":
        body, ctype, ext = exports.json_text(rows, start, end), "application/json", "json"
    else:
        body, ctype, ext = "\ufeff" + exports.csv_text(rows), "text/csv", "csv"  # BOM cho Excel
    resp = HttpResponse(body, content_type=f"{ctype}; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{name}.{ext}"'
    return resp


def dashboard(request):
    return render(request, "monitor/dashboard.html", {
        "location": settings.LOCATION_NAME,
        "ranges": [(60, "1 giờ"), (180, "3 giờ"), (360, "6 giờ"), (1440, "24 giờ")],
    })


def _downsample(readings, minutes, max_points=150):
    """Gộp trung bình theo khoảng thời gian để biểu đồ không quá dày."""
    bucket = max(1, -(-minutes // max_points)) * 60  # giây
    buckets = {}
    for r in readings:
        buckets.setdefault(int(r.created_at.timestamp() // bucket), []).append(r)
    out = []
    for key in sorted(buckets):
        rs = buckets[key]
        out.append({
            "t": int(sum(r.created_at.timestamp() for r in rs) / len(rs) * 1000),
            "temperature": round(sum(r.temperature for r in rs) / len(rs), 2),
            "humidity": round(sum(r.humidity for r in rs) / len(rs), 2),
        })
    return out


def api_dashboard(request):
    try:
        minutes = int(request.GET.get("minutes", 180))
    except ValueError:
        minutes = 180
    if minutes not in ALLOWED_RANGES:
        minutes = 180

    now = timezone.now()
    forecaster = get_forecaster()

    latest = Reading.objects.first()
    history = list(Reading.objects.filter(created_at__gte=now - timedelta(minutes=minutes)).order_by("created_at"))
    recent = [r for r in history if r.created_at >= now - timedelta(minutes=forecaster.lookback_minutes)]
    if len(recent) < len(history) and minutes < forecaster.lookback_minutes:
        recent = history
    if not recent and latest:
        recent = list(Reading.objects.filter(
            created_at__gte=latest.created_at - timedelta(minutes=forecaster.lookback_minutes)
        ).order_by("created_at"))

    online = bool(latest and now - latest.created_at <= OFFLINE_AFTER)
    forecast = forecaster.predict(recent, HORIZON, STEP) if recent and online else []

    return JsonResponse({
        "now": int(now.timestamp() * 1000),
        "online": online,
        "decimals": settings.SENSOR_PROFILES[settings.SENSOR_TYPE]["decimals"],
        "location": settings.LOCATION_NAME,
        "latest": latest and {
            "t": int(latest.created_at.timestamp() * 1000),
            "temperature": round(latest.temperature, 1),
            "humidity": round(latest.humidity, 1),
            "device": latest.device,
        },
        "history": _downsample(history, minutes),
        "forecast": {
            "model": forecaster.name,
            "horizon": HORIZON,
            "points": [p.as_dict() for p in forecast],
        },
        "advice": build_advice(latest if online else None, forecast) if online or not latest else [{
            "level": "warn", "title": "Mất kết nối cảm biến",
            "detail": "Đã hơn 3 phút chưa nhận số liệu mới nên chưa thể dự báo. Kiểm tra nguồn và Wi-Fi của ESP32."}],
    })


@csrf_exempt
@require_POST
def api_ingest(request):
    """ESP32 gửi: POST JSON {"temperature": 28.5, "humidity": 71.2, "device": "esp32-01"}"""
    if request.headers.get("X-API-Key") != settings.INGEST_API_KEY:
        return JsonResponse({"error": "Sai khoá API"}, status=401)
    try:
        data = json.loads(request.body)
        temp, hum = float(data["temperature"]), float(data["humidity"])
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"error": "Cần JSON có temperature và humidity (số)"}, status=400)
    if not (-40 <= temp <= 85 and 0 <= hum <= 100):
        return JsonResponse({"error": "Giá trị ngoài khoảng hợp lệ"}, status=400)
    r = Reading.objects.create(device=str(data.get("device", "esp32-01"))[:40], temperature=temp, humidity=hum)
    try:
        exports.export_previous_hour()
    except Exception:  # xuất file lỗi không được làm hỏng việc nhận số liệu
        logger.exception("Không xuất được file giờ trước")
    return JsonResponse({"id": r.id}, status=201)
