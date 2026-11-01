"""每個來源一個限速器：以「每分鐘最多 N 次」換算成請求之間的最小間隔。

時鐘與 sleep 可以注入，方便測試。
"""
import time


class RateLimiter:
    def __init__(self, per_minute, clock=time.monotonic, sleep=time.sleep):
        if per_minute <= 0:
            raise ValueError("per_minute 必須大於 0")
        self.per_minute = per_minute
        self.interval = 60.0 / per_minute
        self._clock = clock
        self._sleep = sleep
        self._next = None
        self.acquired = 0

    def acquire(self):
        now = self._clock()
        if self._next is not None and self._next > now:
            self._sleep(self._next - now)
            now = self._next
        self._next = now + self.interval
        self.acquired += 1
