import math
import random
import time
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from monitor.models import Reading


def sample(ts, rng):
    """Mô phỏng một ngày trong phòng kính: nóng vào buổi trưa, ẩm vào đêm."""
    hour = ts.hour + ts.minute / 60
    wave = math.sin((hour - 9) / 24 * 2 * math.pi)
    temp = 28.5 + 5.5 * wave + rng.gauss(0, 0.15)
    hum = 68 - 17 * wave + rng.gauss(0, 0.5)
    d = settings.SENSOR_PROFILES[settings.SENSOR_TYPE]["decimals"]
    return round(temp, d), round(min(98, max(25, hum)), d)


class Command(BaseCommand):
    help = "Tạo số liệu mẫu 24 giờ (mỗi phút một lần đo) để chạy thử giao diện"

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Xoá số liệu cũ trước khi tạo")
        parser.add_argument("--live", action="store_true", help="Sau đó tiếp tục sinh số liệu mới mỗi 5 giây")

    def handle(self, *args, **opts):
        rng = random.Random(7)
        if opts["clear"]:
            Reading.objects.all().delete()
        now = timezone.now()
        Reading.objects.bulk_create(
            Reading(temperature=t, humidity=h, created_at=ts)
            for ts in (now - timedelta(minutes=m) for m in range(1440, -1, -1))
            for t, h in [sample(timezone.localtime(ts), rng)]
        )
        self.stdout.write(self.style.SUCCESS("Đã tạo 1441 lượt đo mẫu."))
        if opts["live"]:
            self.stdout.write("Đang sinh số liệu mới mỗi 5 giây. Nhấn Ctrl+C để dừng.")
            try:
                while True:
                    t, h = sample(timezone.localtime(), rng)
                    Reading.objects.create(temperature=t, humidity=h)
                    time.sleep(5)
            except KeyboardInterrupt:
                pass
