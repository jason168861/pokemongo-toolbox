"""共用執行引擎：unit 規劃、跳過已完成、抓取、寫 CSV、checkpoint、斷路器、manifest。

各來源（sources/*.py）只負責「怎麼查 API、怎麼把回應轉成列」。
"""
import datetime as _dt
from dataclasses import dataclass, field
from pathlib import Path

from . import checkpoint as cp
from . import errors as E
from .breaker import CircuitBreaker
from .checkpoint import Checkpoints
from .dates import chunks, days_between, iso, to_date
from .errors import ApiError, AuthRequired, DuplicateKeyError, QueryInDimension, StopRun
from .manifest import dataset_key
from .redact import redact
from .runlog import emit_console, error_text, utc_stamp
from .storage import DatasetFiles, raw_stamp, read_json, slug, write_json_atomic, write_raw

FOLDERS = {"adsense": "adsense", "gsc": "search_console", "ga4": "ga4", "psi": "pagespeed", "crux": "crux"}


class SourceStop(StopRun):
    """停止單一來源（每日配額、斷路器、GA4 token 停損）；其他來源繼續，整體 exit code 4。"""


@dataclass
class Dataset:
    source: str
    name: str
    dims: list               # API 維度名稱
    dim_cols: list           # CSV 欄位名稱（與 dims 對應；不含 date）
    metrics: list            # 候選指標（CSV 欄位固定是這一整組）
    chunk: str               # day / month / year / range
    layout: str              # daily / monthly
    currency: bool = False
    extra_cols: list = field(default_factory=list)   # 例如 GSC 的 search_type
    options: dict = field(default_factory=dict)
    known_limits: list = field(default_factory=list)
    definition_version: int = 1

    @property
    def header(self):
        cols = ["date", "scope_id"] + list(self.extra_cols) + list(self.dim_cols) + list(self.metric_cols) + ["tz"]
        if self.currency:
            cols.append("currency")
        cols += ["is_final", "fetched_at"]
        return cols

    @property
    def metric_cols(self):
        return [m for m in self.metrics]

    @property
    def key_fields(self):
        return ["date", "scope_id"] + list(self.extra_cols) + list(self.dim_cols)


@dataclass
class Unit:
    source: str
    dataset: str
    scope_id: str
    start: _dt.date
    end: _dt.date

    @property
    def id(self):
        return cp.unit_id(self.source, self.dataset, self.scope_id, iso(self.start), iso(self.end))

    @property
    def dates(self):
        return days_between(self.start, self.end)


@dataclass
class UnitResult:
    rows: list
    status: str = cp.OK          # ok / truncated / unsupported / no_data（empty 由列數決定）
    pages: int = 0
    info: dict = field(default_factory=dict)


class Context:
    """一次執行的共用狀態。測試可以直接建立，注入假的 service 與 transport。"""

    def __init__(self, *, data_dir, settings, runlog, end, budget, transports,
                 service_factory=None, api_key_loader=None, dry_run=False, accept_empty=False,
                 now=None):
        self.data_dir = Path(data_dir)
        self.settings = settings
        self.runlog = runlog
        self.end = to_date(end)
        self.budget = budget
        self.transports = transports
        self.service_factory = service_factory
        self.api_key_loader = api_key_loader
        self.dry_run = dry_run
        self.accept_empty = accept_empty
        self.now = now
        self.checkpoints = Checkpoints(self.state_path("checkpoints.json"))
        from .manifest import Manifest
        self.manifest = Manifest(self.data_dir / "manifest.json")
        self._services = {}
        self.planned = {}          # dry-run 統計：dataset_key → unit 數
        self.stopped_sources = {}  # source → 原因
        if dry_run:
            # --dry-run：不寫任何檔案
            self.manifest.save = lambda: None
            self.checkpoints.save = lambda: None

    def state_path(self, name):
        return self.data_dir / "state" / name

    def source_dir(self, source):
        return self.data_dir / FOLDERS[source]

    def transport(self, source):
        return self.transports[source]

    def service(self, api, version):
        key = (api, version)
        if key not in self._services:
            if self.service_factory is None:
                raise E.ConfigError("沒有可用的 API client（未授權？）")
            self._services[key] = self.service_factory(api, version)
        return self._services[key]

    # ---- state 檔
    def read_state(self, name, default):
        return read_json(self.state_path(name), default=default)

    def write_state(self, name, obj):
        if self.dry_run:
            return
        write_json_atomic(self.state_path(name), obj)

    def require_inventory(self, inv, source):
        """--dry-run 不發請求，所以必須先執行過 discover。"""
        if inv:
            return inv
        raise E.ConfigError(f"--dry-run 需要先執行過 discover（{source} 還沒有 inventory）。")

    # ---- raw
    def save_raw(self, source, subdir_parts, name_parts, payload):
        if self.dry_run:
            return None
        stamp = raw_stamp()
        base = self.source_dir(source) / "raw"
        for p in subdir_parts:
            base = base / slug(p, 80)
        fname = "__".join(slug(p, 80) for p in name_parts) + f"__{stamp}.json.gz"
        doc = {"api": payload.get("api"), "request": payload.get("request"),
               "fetched_at": utc_stamp(), "run_id": self.runlog.run_id,
               "unit_id": payload.get("unit_id"), "http_status": payload.get("http_status", 200),
               "response": payload.get("response")}
        return write_raw(base / fname, doc)

    def event(self, event, level="info", **fields):
        return self.runlog.emit_event(event, level=level, **fields)


def plan_units(source, ds, scope_id, start, end):
    start, end = to_date(start), to_date(end)
    return [Unit(source, ds.name, scope_id, s, e) for s, e in chunks(ds.chunk, start, end)]


def run_units(ctx, source, ds, scope, units, *, fetch, breaker, provisional_from, mode,
              tz="", currency=None, meta=None, unavailable=None):
    """依序執行 units。回傳 (status_word, stopped_reason)。

    fetch(unit) -> UnitResult；可能丟 ApiError / AuthRequired / QueryInDimension / StopRun。
    """
    scope_id = scope
    files = DatasetFiles(ctx.source_dir(source), ds.name, ds.layout, ds.header, ds.key_fields)
    dkey = dataset_key(source, ds.name, scope_id)
    prov = to_date(provisional_from) if provisional_from else None
    stopped_reason = None
    guard = None
    did_success = False

    todo = [u for u in units if mode == "refetch" or not Checkpoints.is_done(ctx.checkpoints.get(u.id))]
    if ctx.dry_run:
        ctx.planned[dkey] = ctx.planned.get(dkey, 0) + len(todo)
        return "dry_run", None

    for u in todo:
        is_final = prov is None or u.end < prov
        try:
            res = fetch(u)
        except (AuthRequired, StopRun):
            raise
        except QueryInDimension as exc:
            ctx.checkpoints.set(u.id, cp.FAILED, is_final=is_final, error_class="query_in_dimension",
                                error=error_text(exc))
            ctx.event("unit_failed", "warn", source=source, dataset=ds.name, unit=u.id,
                      error_class="query_in_dimension", message=error_text(exc))
            stopped_reason = "query_in_dimension：" + str(exc)
            guard = exc
            break
        except ApiError as exc:
            if unavailable is not None and unavailable(exc):
                # API 明確表示這段期間沒有可用資料（保留期限）：不算失敗、不計入斷路器、不碰 CSV。
                # is_final 照一般規則：重抓視窗內（本月、上月）的 unit 不算定案，update 時照常重抓。
                ctx.checkpoints.set(u.id, cp.UNAVAILABLE, is_final=is_final, http_status=exc.status,
                                    api_message=redact(exc.message or str(exc))[:300])
                ctx.event("unit_unavailable", source=source, dataset=ds.name, unit=u.id, http_status=exc.status)
                continue
            ctx.checkpoints.set(u.id, cp.FAILED, is_final=is_final, error_class=exc.category,
                                http_status=exc.status, error=error_text(exc))
            ctx.event("unit_failed", "error", source=source, dataset=ds.name, unit=u.id,
                      error_class=exc.category, http_status=exc.status, message=error_text(exc))
            if exc.category == E.QUOTA_DAILY:
                ctx.manifest.update_dataset(dkey, checkpoints=ctx.checkpoints, files=files, scope_id=scope_id,
                                            meta=meta, stopped_reason="每日配額用完")
                raise SourceStop(f"{source} 每日配額用完，已停止該來源並保留進度。") from None
            breaker.record_failure(exc.category, exc.status)
            if exc.category == E.PERMISSION:
                stopped_reason = "permission（403）"
                break
            if breaker.open:
                ctx.event("breaker_open", "error", source=source, dataset=ds.name,
                          error_class=breaker.last_category, http_status=breaker.last_status)
                ctx.manifest.update_dataset(dkey, checkpoints=ctx.checkpoints, files=files, scope_id=scope_id,
                                            meta=meta, stopped_reason="斷路器：連續失敗")
                raise SourceStop(f"{source} 連續 {breaker.threshold} 個 unit 因 {breaker.last_category} 失敗，"
                                 "已停止該來源並保留進度。") from None
            continue

        if res.status in (cp.UNSUPPORTED, cp.NO_DATA):
            ctx.checkpoints.set(u.id, res.status, is_final=True, pages=res.pages, **_info(res))
            ctx.event("unit_done", source=source, dataset=ds.name, unit=u.id, status=res.status)
            breaker.record_success()
            continue

        fetched_at = utc_stamp()
        for r in res.rows:
            r["scope_id"] = scope_id
            r.setdefault("tz", tz)
            if ds.currency:
                r.setdefault("currency", currency or "")
            d = to_date(r["date"])
            r["is_final"] = "true" if (prov is None or d < prov) else "false"
            r["fetched_at"] = fetched_at
        try:
            applied = files.apply(scope_id, u.dates, res.rows, accept_empty=ctx.accept_empty)
        except DuplicateKeyError as exc:
            ctx.checkpoints.set(u.id, cp.FAILED, is_final=is_final, error_class="duplicate_key",
                                error=error_text(exc))
            ctx.event("unit_failed", "error", source=source, dataset=ds.name, unit=u.id,
                      error_class="duplicate_key", message=error_text(exc))
            continue
        except OSError as exc:      # 例如 Windows 上 CSV 正被 Excel 開著
            ctx.checkpoints.set(u.id, cp.FAILED, is_final=is_final, error_class="write_error",
                                error=error_text(exc))
            ctx.event("unit_failed", "error", source=source, dataset=ds.name, unit=u.id,
                      error_class="write_error", message="寫入 CSV 失敗（檔案是否被其他程式開著？）")
            continue

        if applied["regression_dates"]:
            status = cp.REGRESSION
            ctx.event("regression_to_empty", "warn", source=source, dataset=ds.name, unit=u.id,
                      dates=applied["regression_dates"],
                      message="之前有資料的日期這次是 0 列，已保留舊資料；確認後可用 refetch --accept-empty 清除。")
        elif res.status == cp.TRUNCATED:
            status = cp.TRUNCATED
        elif res.rows:
            status = cp.OK
        else:
            status = cp.EMPTY
        ctx.checkpoints.set(u.id, status, is_final=is_final, rows=len(res.rows), pages=res.pages, **_info(res))
        ctx.event("unit_done", source=source, dataset=ds.name, unit=u.id, status=status,
                  rows=len(res.rows), pages=res.pages)
        breaker.record_success()
        did_success = True

    ctx.manifest.update_dataset(dkey, checkpoints=ctx.checkpoints, files=files, scope_id=scope_id,
                                meta=meta, stopped_reason=stopped_reason, success=did_success,
                                extra=guard_extra(ctx, dkey, meta, guard))
    return ("stopped" if stopped_reason else "done"), stopped_reason


def guard_extra(ctx, dkey, meta, guard):
    """守門命中時：known_limits 加上命中的規則名稱與列數（不含命中的值），另存 guard_hits。"""
    if guard is None:
        return None
    base = list((meta or {}).get("known_limits") or (ctx.manifest.get(dkey) or {}).get("known_limits") or [])
    note = guard.limit_note()
    if note not in base:
        base.append(note)
    return {"known_limits": base, "guard_hits": dict(guard.hits)}


def _info(res):
    out = {}
    for k, v in (res.info or {}).items():
        if k in ("status", "is_final", "rows", "pages", "fetched_at"):
            continue
        out[k] = v
    return out


def units_for_mode(ctx, source_key, ds, scope_id, mode, floor, start=None, end=None, refetch_from=None):
    """依模式產生 unit 清單。

    backfill：floor..end
    update：從「最後完成日＋1」與「重抓視窗起點」較早者 ..end，外加還沒完成的舊 unit
    refetch：start..end（必填）
    """
    end = to_date(end or ctx.end)
    if mode == "refetch":
        return plan_units(source_key, ds, scope_id, start, end)
    if mode == "backfill":
        s = to_date(start) if start else to_date(floor)
        return plan_units(source_key, ds, scope_id, max(s, to_date(floor)), end)
    # update
    prefix = dataset_key(source_key, ds.name, scope_id) + "/"
    last = ctx.checkpoints.last_done_end(prefix)
    s = to_date(refetch_from)
    if last:
        s = min(s, to_date(last) + _dt.timedelta(days=1))
    s = max(s, to_date(floor))
    units = plan_units(source_key, ds, scope_id, s, end)
    known = {u.id for u in units}
    for uid in ctx.checkpoints.pending(prefix):
        rng = uid.rsplit("/", 1)[-1]
        a, b = rng.split("_")
        if uid not in known and to_date(b) < s:
            units.insert(0, Unit(source_key, ds.name, scope_id, to_date(a), to_date(b)))
    return units


def make_breaker(settings):
    return CircuitBreaker(settings.get("breaker_threshold", 3))


def say(msg):
    emit_console(msg)
