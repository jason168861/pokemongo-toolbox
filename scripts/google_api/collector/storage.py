"""raw 寫入、CSV 日檔／月檔替換、備份、compact（設計 §2.1、§2.2、§5.3）。"""
import csv
import datetime as _dt
import gzip
import io
import json
import os
import shutil
from pathlib import Path

from .dates import month_key, to_date
from .errors import DuplicateKeyError

CSV_ENCODING = "utf-8-sig"
BACKUP_KEEP = 3


# ---------------------------------------------------------------- raw

def write_raw(path, payload):
    """寫入 gzip JSON。先寫 .partial，再用不覆蓋的方式放到最終檔名。

    目標已存在 → FileExistsError（.partial 保留，留給人查看）。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(str(path))
    tmp = Path(str(path) + ".partial")
    data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    with open(tmp, "xb") as f:
        with gzip.GzipFile(fileobj=f, mode="wb", mtime=0) as gz:
            gz.write(data)
        f.flush()
        os.fsync(f.fileno())
    place_no_overwrite(tmp, path)
    return path


def place_no_overwrite(src, dst):
    """把 src 放到 dst，dst 已存在時丟 FileExistsError（src 保留）。"""
    try:
        os.link(src, dst)
    except FileExistsError:
        raise
    except (OSError, AttributeError, NotImplementedError):
        if os.name != "nt":
            raise
        # Windows 且不支援 hard link：os.rename 在目標存在時會丟 FileExistsError，不會覆蓋
        os.rename(src, dst)
        return
    os.remove(src)


def read_raw(path):
    with gzip.open(path, "rb") as f:
        return json.loads(f.read().decode("utf-8"))


def raw_stamp(now=None):
    now = now or _dt.datetime.now(_dt.timezone.utc)
    return now.strftime("%Y%m%dT%H%M%S%fZ")


def slug(text, limit=60):
    out = []
    for ch in str(text):
        out.append(ch if ch.isalnum() or ch in "-_" else "_")
    s = "".join(out).strip("_")
    while "__" in s:
        s = s.replace("__", "_")
    return s[:limit] or "x"


# ---------------------------------------------------------------- CSV 基本

def render_csv(header, rows):
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=header, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in header})
    return buf.getvalue().encode(CSV_ENCODING)


def read_csv(path):
    path = Path(path)
    if not path.exists():
        return None, []
    with open(path, "r", encoding=CSV_ENCODING, newline="") as f:
        reader = csv.DictReader(f)
        rows = [dict(r) for r in reader]
        return list(reader.fieldnames or []), rows


def _backup(path, backup_dir, keep=BACKUP_KEEP):
    path = Path(path)
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = raw_stamp()
    dst = backup_dir / f"{path.name}.{stamp}.csv"
    shutil.copy2(path, dst)
    olds = sorted(backup_dir.glob(path.name + ".*.csv"))
    for old in olds[:-keep] if keep > 0 else olds:
        try:
            old.unlink()
        except OSError:
            pass
    return dst


def write_if_changed(path, data, backup_dir=None):
    """內容與現有檔案相同時什麼都不做；不同時先備份舊檔（只在有差異時），再原子替換。

    回傳 "unchanged" / "created" / "replaced"。
    """
    path = Path(path)
    if path.exists():
        with open(path, "rb") as f:
            if f.read() == data:
                return "unchanged"
        if backup_dir is not None:
            _backup(path, backup_dir)
        result = "replaced"
    else:
        result = "created"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".tmp")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return result


# ---------------------------------------------------------------- 資料集檔案

class DatasetFiles:
    """一個資料集在某個來源資料夾底下的 CSV 檔案配置。

    layout = "daily"：csv/<dataset>/<YYYY-MM>/<YYYY-MM-DD>.csv
    layout = "monthly"：csv/<dataset>/<YYYY-MM>.csv
    """

    def __init__(self, source_dir, dataset, layout, header, key_fields):
        if layout not in ("daily", "monthly"):
            raise ValueError(layout)
        self.source_dir = Path(source_dir)
        self.dataset = dataset
        self.layout = layout
        self.header = list(header)
        self.key_fields = list(key_fields)
        self.csv_dir = self.source_dir / "csv" / dataset
        self.backup_dir = self.source_dir / "csv_backup" / dataset

    def file_for(self, d):
        d = to_date(d)
        if self.layout == "daily":
            return self.csv_dir / month_key(d) / f"{d.isoformat()}.csv"
        return self.csv_dir / f"{month_key(d)}.csv"

    def all_files(self):
        if not self.csv_dir.exists():
            return []
        return sorted(p for p in self.csv_dir.rglob("*.csv") if p.is_file())

    def _key(self, row):
        return tuple(row.get(k, "") or "" for k in self.key_fields)

    def apply(self, scope_id, unit_dates, new_rows, accept_empty=False):
        """把一個成功 unit 的結果寫進 CSV（設計 §5.3）。

        unit_dates：這個 unit 涵蓋的全部日期（含 0 列的日期）。
        new_rows：list[dict]，每列必須有 date（ISO）與 scope_id。
        回傳 {"regression_dates": [...], "files": {path: result}}。
        """
        dates = sorted({to_date(d).isoformat() for d in unit_dates})
        rows_by_date = {}
        for r in new_rows:
            d = to_date(r["date"]).isoformat()
            if d not in dates:
                raise ValueError(f"列的日期 {d} 不在 unit 範圍內")
            r["date"] = d
            rows_by_date.setdefault(d, []).append(r)

        by_file = {}
        for d in dates:
            by_file.setdefault(self.file_for(d), []).append(d)

        regression = []
        results = {}
        for path, file_dates in sorted(by_file.items()):
            old_header, existing = read_csv(path)
            had_rows = {r.get("date") for r in existing if r.get("scope_id") == scope_id}
            protected = set()
            for d in file_dates:
                if not rows_by_date.get(d) and d in had_rows and not accept_empty:
                    protected.add(d)
            regression.extend(sorted(protected))
            replace = set(file_dates) - protected
            kept = [r for r in existing
                    if not (r.get("scope_id") == scope_id and r.get("date") in replace)]
            added = []
            for d in sorted(replace):
                added.extend(rows_by_date.get(d, []))
            combined = kept + added
            seen = set()
            for r in combined:
                k = self._key(r)
                if k in seen:
                    raise DuplicateKeyError(f"{self.dataset} 自然鍵重複：{len(self.key_fields)} 個欄位的組合出現兩次（檔案 {path.name}）")
                seen.add(k)
            combined.sort(key=self._key)
            if not combined and not path.exists():
                continue                      # 0 列而且原本沒有檔案：不建立空檔
            data = render_csv(self.header, combined)
            results[str(path)] = write_if_changed(path, data, self.backup_dir / path.parent.name
                                                  if self.layout == "daily" else self.backup_dir)
        return {"regression_dates": regression, "files": results}

    def dates_with_rows(self, scope_id, dates):
        found = set()
        for path in sorted({self.file_for(d) for d in dates}):
            _, rows = read_csv(path)
            for r in rows:
                if r.get("scope_id") == scope_id:
                    found.add(r.get("date"))
        return found

    def stats(self, scope_id):
        """row_count 與最早／最晚有列的日期（由 CSV 重算，不靠累加）。"""
        count = 0
        first = last = None
        for path in self.all_files():
            _, rows = read_csv(path)
            for r in rows:
                if r.get("scope_id") != scope_id:
                    continue
                count += 1
                d = r.get("date")
                if d:
                    first = d if first is None or d < first else first
                    last = d if last is None or d > last else last
        return {"row_count": count, "first_date_with_rows": first, "last_date_with_rows": last}

    def compact(self, out_path):
        files = self.all_files()
        rows = []
        for path in files:
            _, r = read_csv(path)
            rows.extend(r)
        rows.sort(key=lambda r: (r.get("date", ""),) + self._key(r))
        return write_if_changed(out_path, render_csv(self.header, rows))


class SnapshotTable:
    """附加型的表（PSI、CrUX）：依自然鍵 upsert，整份原子寫回。"""

    def __init__(self, path, header, key_fields, backup_dir=None):
        self.path = Path(path)
        self.header = list(header)
        self.key_fields = list(key_fields)
        self.backup_dir = backup_dir

    def upsert(self, rows, drop=None):
        """drop(existing_row) -> bool：寫入前先刪掉符合條件的舊列（例如 CrUX 有資料後刪掉同組合的 no_data 列）。"""
        _, existing = read_csv(self.path)
        index = {}
        for r in existing:
            if drop is not None and drop(r):
                continue
            index[tuple(r.get(k, "") or "" for k in self.key_fields)] = r
        for r in rows:
            norm = {k: ("" if r.get(k) is None else str(r.get(k))) for k in self.header}
            index[tuple(norm.get(k, "") for k in self.key_fields)] = norm
        merged = sorted(index.values(), key=lambda r: tuple(r.get(k, "") or "" for k in self.key_fields))
        return write_if_changed(self.path, render_csv(self.header, merged), self.backup_dir)


def write_json_atomic(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=False, default=str)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
