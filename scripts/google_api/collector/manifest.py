"""manifest.json：各資料集現況（設計 §2.4）。

row_count 與 coverage 每次都從 CSV 重算，不靠累加，所以重跑不會越算越多。
"""
from pathlib import Path

from . import checkpoint as cp
from .runlog import utc_stamp
from .storage import read_json, write_json_atomic

COLLECTOR_VERSION = "0.1.0"


def dataset_key(source, dataset, scope_id):
    return f"{source}/{dataset}/{scope_id}"


def unit_stats(checkpoints, prefix):
    stats = {"ok": 0, "empty_final": 0, "empty_provisional": 0, "failed": 0, "unsupported": 0,
             "no_data": 0, "truncated": 0, "provisional": 0, "regression_to_empty": 0, "unavailable": 0}
    failed, regression = [], []
    for uid, rec in sorted(checkpoints.with_prefix(prefix).items()):
        st = rec.get("status")
        final = bool(rec.get("is_final"))
        if st == cp.EMPTY:
            stats["empty_final" if final else "empty_provisional"] += 1
        elif st in stats:
            stats[st] += 1
        if not final and st not in (cp.UNSUPPORTED, cp.NO_DATA, cp.UNAVAILABLE):
            stats["provisional"] += 1
        if st == cp.FAILED:
            failed.append(uid.rsplit("/", 1)[-1])
        if st == cp.REGRESSION:
            regression.append(uid.rsplit("/", 1)[-1])
    return stats, failed, regression


def truncated_dates(checkpoints, prefix):
    """AdSense 截斷是在父 unit 上以 truncated_dates 記錄（不另記子 unit）。這裡彙總成一份清單。"""
    out = []
    for uid, rec in sorted(checkpoints.with_prefix(prefix).items()):
        if rec.get("status") == cp.TRUNCATED:
            out.extend(rec.get("truncated_dates") or [])
    return sorted(set(out))


def overall_status(stats, stopped=False):
    if stopped:
        return "stopped"
    total = sum(v for k, v in stats.items() if k != "provisional")
    if total == 0:
        return "not_started"
    if stats["unsupported"] and total == stats["unsupported"]:
        return "unsupported"
    if stats["no_data"] and total == stats["no_data"]:
        return "no_data"
    if stats.get("unavailable") and total == stats["unavailable"]:
        return "unavailable"
    if stats["failed"] or stats["regression_to_empty"]:
        done = stats["ok"] + stats["empty_final"] + stats["empty_provisional"] + stats["truncated"]
        return "partial" if done else "failed"
    return "ok"


class Manifest:
    def __init__(self, path):
        self.path = Path(path)
        self.data = read_json(self.path, default=None) or {}
        self.data.setdefault("datasets", {})
        self.data.setdefault("skipped_scopes", {})

    def save(self):
        self.data["generated_at"] = utc_stamp()
        self.data["collector_version"] = COLLECTOR_VERSION
        write_json_atomic(self.path, self.data)

    def get(self, key):
        return self.data["datasets"].get(key)

    def set_skipped(self, source, items):
        """items：[{scope_id, reason}]"""
        self.data["skipped_scopes"][source] = items

    def update_dataset(self, key, *, checkpoints, files=None, scope_id=None, meta=None,
                       stopped_reason=None, extra=None, success=False):
        rec = dict(self.data["datasets"].get(key) or {})
        prefix = key + "/"
        stats, failed, regression = unit_stats(checkpoints, prefix)
        rec["units"] = stats
        rec["failed_units"] = failed
        rec["regression_units"] = regression
        tdates = truncated_dates(checkpoints, prefix)
        if tdates or stats["truncated"]:
            rec["truncated_dates"] = tdates
        if files is not None and scope_id is not None:
            s = files.stats(scope_id)
            rec["row_count"] = s["row_count"]
            cov = dict(rec.get("coverage") or {})
            cov["first_date_with_rows"] = s["first_date_with_rows"]
            cov["last_date_with_rows"] = s["last_date_with_rows"]
            rec["coverage"] = cov
        if meta:
            for k in ("time_zone", "currency", "known_limits", "dimensions", "metrics_available"):
                if k in meta:
                    rec[k] = meta[k]
        if extra:
            for k, v in extra.items():
                if k == "coverage":
                    cov = dict(rec.get("coverage") or {})
                    cov.update(v)
                    rec["coverage"] = cov
                else:
                    rec[k] = v
        if stopped_reason:
            rec["stopped_reason"] = stopped_reason
        elif "stopped_reason" in rec and success:
            rec.pop("stopped_reason", None)
            rec.pop("guard_hits", None)
        rec["status"] = overall_status(stats, stopped=bool(stopped_reason))
        if success:
            rec["last_success_at"] = utc_stamp()
        self.data["datasets"][key] = rec
        self.save()
        return rec
