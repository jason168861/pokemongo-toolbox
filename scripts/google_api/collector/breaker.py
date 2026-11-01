"""斷路器：同一個來源連續 N 個 unit 最終因 QuotaRate 或 Transient 失敗 → 停止該來源。

- 任何 unit 成功（含 empty）就歸零。
- Permission、BadRequest 等資料集層級的錯誤不計入，也不歸零。
"""
from .errors import BREAKER_COUNTED


class CircuitBreaker:
    def __init__(self, threshold=3):
        self.threshold = max(1, int(threshold))
        self.consecutive = 0
        self.last_category = None
        self.last_status = None

    def record_success(self):
        self.consecutive = 0

    def record_failure(self, category, status=None):
        if category in BREAKER_COUNTED:
            self.consecutive += 1
            self.last_category = category
            self.last_status = status

    @property
    def open(self):
        return self.consecutive >= self.threshold
