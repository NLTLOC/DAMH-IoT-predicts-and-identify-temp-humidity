"""
Lớp dự báo.

Giao diện chỉ làm việc với `BaseForecaster.predict()`. Khi bạn chọn xong mô hình AI,
chỉ cần viết thêm một lớp kế thừa BaseForecaster rồi đổi FORECASTER_CLASS trong settings.py.
"""
from dataclasses import dataclass, asdict
import statistics

from django.conf import settings
from django.utils.module_loading import import_string


@dataclass
class ForecastPoint:
    minutes_ahead: int
    temperature: float
    humidity: float
    temp_low: float
    temp_high: float
    hum_low: float
    hum_high: float

    def as_dict(self):
        return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in asdict(self).items()}


class BaseForecaster:
    name = "Chưa đặt tên"
    # Số phút dữ liệu gần nhất mà mô hình cần để dự báo
    lookback_minutes = 60

    def predict(self, readings, horizon=60, step=10):
        """
        readings: list các Reading, sắp xếp CŨ -> MỚI, trong `lookback_minutes` phút gần nhất.
        Trả về list[ForecastPoint] cho các mốc step, 2*step, ... horizon (phút).
        """
        raise NotImplementedError


class TrendForecaster(BaseForecaster):
    """Mô hình tạm: ngoại suy xu hướng tuyến tính có giảm dần. Dùng để dựng giao diện, sẽ thay bằng AI."""

    name = "Xu hướng tuyến tính (tạm thời)"
    lookback_minutes = 30
    damping = 0.6

    def predict(self, readings, horizon=60, step=10):
        if not readings:
            return []
        last_ts = readings[-1].created_at
        xs = [(r.created_at - last_ts).total_seconds() / 60 for r in readings]
        profile = settings.SENSOR_PROFILES[settings.SENSOR_TYPE]
        t_fit = self._fit(xs, [r.temperature for r in readings])
        h_fit = self._fit(xs, [r.humidity for r in readings])

        points = []
        for m in range(step, horizon + 1, step):
            t, t_sd = self._at(t_fit, m, min_sd=profile["temp_sd"])
            h, h_sd = self._at(h_fit, m, min_sd=profile["hum_sd"])
            h, h_lo, h_hi = (min(100, max(0, v)) for v in (h, h - h_sd, h + h_sd))
            points.append(ForecastPoint(m, t, h, t - t_sd, t + t_sd, h_lo, h_hi))
        return points

    def _fit(self, xs, ys):
        n = len(xs)
        if n < 3 or max(xs) - min(xs) < 1e-6:
            return {"a": ys[-1], "b": 0.0, "sd": 0.0}
        mx, my = statistics.fmean(xs), statistics.fmean(ys)
        sxx = sum((x - mx) ** 2 for x in xs)
        b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
        a = my - b * mx  # giá trị khớp tại thời điểm đo cuối (x = 0)
        sd = statistics.pstdev([y - (a + b * x) for x, y in zip(xs, ys)])
        return {"a": a, "b": b, "sd": sd}

    def _at(self, fit, m, min_sd):
        value = fit["a"] + fit["b"] * m * self.damping
        sd = max(fit["sd"], min_sd) * (1 + m / 20)
        return value, sd


def get_forecaster():
    return import_string(settings.FORECASTER_CLASS)()
