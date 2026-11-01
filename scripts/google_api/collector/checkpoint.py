"""checkpoint：每個 unit 的狀態，用來續跑（設計 §5.2）。

每完成一個 unit 就原子寫入一次；中斷時最多損失正在跑的那一個 unit。
檔案損壞時改名備份並停止，不自動重建（自動重建可能重抓整個回補，耗費配額）。
"""
import json
import os
from pathlib import Path

from .errors import ConfigError
from .runlog import utc_stamp
from .storage import write_json_atomic

OK = "ok"
EMPTY = "empty"
FAILED = "failed"
UNSUPPORTED = "unsupported"
NO_DATA = "no_data"
TRUNCATED = "truncated"
REGRESSION = "regression_to_empty"
# API 明確表示「這段期間沒有可用的報表資料」（例如 AdSense PAGE_URL 只保留最近一段時間）。
# 視為已定案：backfill／update 不重抓，只有 refetch 才重試。不算失敗、不計入斷路器。
UNAVAILABLE = "unavailable"
STATUSES = {OK, EMPTY, FAILED, UNSUPPORTED, NO_DATA, TRUNCATED, REGRESSION, UNAVAILABLE}

# 定案（is_final）後不必再抓的狀態。truncated 也算：同一天再抓還是會截斷，只有 refetch 才重跑。
DONE_WHEN_FINAL = {OK, EMPTY, UNSUPPORTED, NO_DATA, TRUNCATED, UNAVAILABLE}


def unit_id(source, dataset, scope_id, start, end):
    return f"{source}/{dataset}/{scope_id}/{start}_{end}"


class Checkpoints:
    def __init__(self, path):
        self.path = Path(path)
        self.units = {}
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            units = data.get("units")
            if not isinstance(units, dict):
                raise ValueError("缺少 units")
            self.units = units
        except (ValueError, OSError) as exc:
            backup = self.path.with_name(self.path.name + ".corrupt-" + utc_stamp().replace(":", ""))
            try:
                os.replace(self.path, backup)
            except OSError:
                pass
            raise ConfigError(f"checkpoints.json 損壞，已備份為 {backup.name}。不會自動重建；"
                              "請檢查後再執行（必要時用 refetch 指定範圍重抓）。") from None

    def save(self):
        write_json_atomic(self.path, {"version": 1, "units": self.units})

    def get(self, uid):
        return self.units.get(uid)

    def set(self, uid, status, **fields):
        if status not in STATUSES:
            raise ValueError(status)
        rec = {"status": status, "fetched_at": utc_stamp()}
        rec.update(fields)
        self.units[uid] = rec
        self.save()
        return rec

    @staticmethod
    def is_done(rec):
        """backfill／update 是否可以跳過這個 unit。refetch 不呼叫這個函式。"""
        if not rec:
            return False
        return rec.get("status") in DONE_WHEN_FINAL and bool(rec.get("is_final"))

    def with_prefix(self, prefix):
        return {k: v for k, v in self.units.items() if k.startswith(prefix)}

    def last_done_end(self, prefix):
        """這個資料集最後一個「完成」unit 的結束日期（ISO 字串），沒有就回傳 None。"""
        best = None
        for k, v in self.with_prefix(prefix).items():
            if v.get("status") in (OK, EMPTY, TRUNCATED):
                end = k.rsplit("_", 1)[-1]
                if best is None or end > best:
                    best = end
        return best

    def pending(self, prefix):
        """失敗、暫定、regression 的 unit id（update 要重跑）。"""
        out = []
        for k, v in self.with_prefix(prefix).items():
            if v.get("status") in (FAILED, REGRESSION) or not v.get("is_final"):
                if v.get("status") not in (UNSUPPORTED, NO_DATA, UNAVAILABLE):
                    out.append(k)
        return sorted(out)
