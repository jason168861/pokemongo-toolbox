"""GA4 Data API ＋ Admin API（設計 §3.3）。

隱私：一般資料集只用 pagePath、landingPage（不含 query string）。
含 query 的維度只允許用在 ga4_date_home_query，而且必須帶 pagePath EXACT "/" 的 filter。
"""
import json
from urllib.parse import urlparse

from .. import checkpoint as cp
from .. import errors as E
from ..dates import backfill_floor, iso, provisional_from, refetch_start, to_date
from ..engine import Dataset, SourceStop, UnitResult, make_breaker, run_units, units_for_mode
from ..errors import ApiError, ConfigError
from ..manifest import dataset_key
from ..quality import (GA4_PATH_RULES, check_drop_stop, check_home_paths, dropped_daily_stats, ga4_other_stats,
                       guard_dimension, split_rows)
from ..runlog import utc_stamp
from ..storage import SnapshotTable
from . import inventory_get, inventory_set, paginate, probe_dataset, probe_get, probe_set

SOURCE = "ga4"
PAGE_LIMIT = 100000

FORBIDDEN_DIMENSIONS = {"pagePathPlusQueryString", "landingPagePlusQueryString", "pageLocation",
                        "pageReferrer", "fullPageUrl"}
HOME_FILTER = {"filter": {"fieldName": "pagePath", "stringFilter": {"matchType": "EXACT", "value": "/"}}}
HOME_DATASET = "ga4_date_home_query"

TRAFFIC = ["totalUsers", "activeUsers", "newUsers", "sessions", "engagedSessions", "engagementRate",
           "screenPageViews", "userEngagementDuration", "averageSessionDuration", "eventCount"]
PAGE = ["screenPageViews", "activeUsers", "userEngagementDuration", "eventCount"]
LANDING = ["sessions", "engagedSessions", "engagementRate", "totalUsers", "newUsers"]
SOURCE_M = ["sessions", "engagedSessions", "engagementRate", "totalUsers"]
EVENT = ["eventCount", "totalUsers"]
ADS = ["totalAdRevenue", "publisherAdImpressions", "publisherAdClicks"]
CROSS = ["sessions", "engagedSessions", "screenPageViews", "userEngagementDuration", "eventCount"]

LIMITS = ["totalUsers、activeUsers、newUsers、engagementRate、averageSessionDuration 跨日或跨維度加總沒有意義",
          "session 範圍維度（landingPage、sessionSourceMedium）與 event 範圍維度（pagePath）的使用者數不可互相比對或加總",
          "低流量列可能被歸入 (other)；可能受門檻（thresholding）影響，見 ga4_quality",
          "日期是 property 時區的日曆日"]


def _ds(name, dims, metrics, **kw):
    return Dataset(source=SOURCE, name=name, dims=["date"] + dims, dim_cols=list(dims), metrics=list(metrics),
                   chunk="month", layout="monthly", known_limits=list(LIMITS), **kw)


DATASETS = [
    _ds("ga4_date", [], TRAFFIC),
    _ds("ga4_date_country", ["country"], TRAFFIC),
    _ds("ga4_date_tech", ["deviceCategory", "operatingSystem", "browser"], TRAFFIC),
    _ds("ga4_date_page", ["pagePath"], PAGE, options={"path_guard": "pagePath"}),
    _ds(HOME_DATASET, ["pagePathPlusQueryString"], PAGE, options={"dimension_filter": HOME_FILTER, "home_query": True}),
    _ds("ga4_date_landing", ["landingPage"], LANDING, options={"path_guard": "landingPage"}),
    _ds("ga4_date_sourcemedium", ["sessionSourceMedium"], SOURCE_M),
    _ds("ga4_date_event", ["eventName"], EVENT),
    _ds("ga4_date_ads", ["pagePath"], ADS, currency=True, options={"path_guard": "pagePath", "optional": True}),
    # 交叉資料集（分析用）：各地區／裝置用了哪些頁面（工具），以及 SPA 是否重複計算 page_view。
    # 只放可跨維度加總的指標，不放 totalUsers／activeUsers／newUsers 這類使用者數。
    _ds("ga4_date_country_page", ["country", "pagePath"], CROSS, options={"path_guard": "pagePath"}),
    _ds("ga4_date_device_page", ["deviceCategory", "pagePath"], CROSS, options={"path_guard": "pagePath"}),
]

# dropped_rows_by_rule 加在最後一欄：舊檔沒有這一欄的列會是空值，不影響既有欄位
QUALITY_HEADER = ["dataset", "scope_id", "unit_start", "unit_end", "rows", "other_rows", "other_share",
                  "data_loss_from_other_row", "subject_to_thresholding", "sampling", "fetched_at",
                  "dropped_rows_by_rule"]


def validate_dataset(ds):
    """含 query 的維度只允許出現在首頁資料集，而且必須帶 EXACT "/" 的 filter。"""
    bad = [d for d in ds.dims if d in FORBIDDEN_DIMENSIONS]
    if not bad:
        return
    if ds.name == HOME_DATASET and ds.options.get("dimension_filter") == HOME_FILTER:
        return
    raise ConfigError(f"資料集 {ds.name} 使用了禁止的維度 {bad}（可能含分享 id），拒絕執行。")


ADS_NO_DATA_NOTE = ("GA4 端沒有廣告收益資料（推論：GA4 未連結 AdSense），廣告收益請看 AdSense 資料；"
                    "不排入回補，重新執行 probe 才會再檢查")


# 首頁資料集逐列排除只套用這兩條規則（Reviewer 條件 B-a）
HOME_DROP_RULES = ("digits12", "share_id_param")
# 被排除列要另外記錄合計的指標（不記維度值）
DROP_SUM_METRICS = ("screenPageViews", "eventCount", "userEngagementDuration")
DROPPED_DAILY_HEADER = ["dataset", "scope_id", "date", "total_rows", "dropped_rows",
                        "screenPageViews", "eventCount", "userEngagementDuration", "fetched_at"]

HOME_DROP_NOTE = ("ga4_date_home_query 是首頁 query 流量的下限估計，不是完整的首頁 query 流量：首頁 query 中命中 s=（分享 id）或 12 位以上連續數字（疑似訓練家代碼、社群分享追蹤參數）的列"
                  "已逐列排除、不寫入 CSV，所以首頁 query 的流量會略為低估；排除數量見 dropped_rows_by_rule（只記規則與列數），"
                  "每天被排除列的 screenPageViews／eventCount／userEngagementDuration 合計見 ga4_quality_dropped_daily.csv。"
                  "單日排除 > 20 列，或排除 ≥ 3 列且 > 當日總列數 1% 時整個資料集停止（門檻見 ga4.home_drop_stop）。"
                  "raw 保留原樣在資料目錄")


def dropped_totals(checkpoints, prefix):
    """彙總各 unit 的 dropped_rows_by_rule（由 checkpoint 重算，不靠累加）。"""
    totals = {}
    for rec in checkpoints.with_prefix(prefix).values():
        for rule, n in (rec.get("dropped_rows_by_rule") or {}).items():
            totals[rule] = totals.get(rule, 0) + int(n)
    return totals


def probe_status(pr):
    """舊版 probe 紀錄（status=supported 但 probe_rows=0）也視為 no_data，不必重新 probe。"""
    status = pr.get("status")
    if status == "supported" and pr.get("probe_rows") == 0:
        return "no_data"
    return status


def history_limits(prop):
    """property 建立日之前沒有資料：寫進 known_limits，避免把之前的空白誤讀成「沒有流量」。"""
    created = (prop.get("create_time") or "")[:10]
    if not created:
        return []
    return [f"這個 property 建立於 {created}，GA4 歷史只從這一天開始；之前的流量不在 GA4 內"
            "（可能在其他 property 或舊網域，需另外確認）"]


def host_matches(uri, domain):
    host = (urlparse(uri or "").hostname or "").lower().rstrip(".")
    domain = domain.lower()
    return host == domain or host.endswith("." + domain)


class Ga4Source:
    key = SOURCE

    def __init__(self, ctx):
        self.ctx = ctx
        self.transport = ctx.transport(SOURCE)
        self.breaker = make_breaker(ctx.settings)
        self.quota_stop_reason = None
        for ds in DATASETS:
            validate_dataset(ds)

    @property
    def admin(self):
        return self.ctx.service("analyticsadmin", "v1beta")

    @property
    def data(self):
        return self.ctx.service("analyticsdata", "v1beta")

    # ---------------------------------------------------------- discover
    def discover(self, force=False):
        inv = inventory_get(self.ctx, SOURCE)
        if self.ctx.dry_run:
            return self.ctx.require_inventory(inv, SOURCE)
        if inv and not force:
            return inv
        pages = []
        summaries = paginate(self.transport, lambda t: self.admin.accountSummaries().list(pageSize=200, pageToken=t)
                             if t else self.admin.accountSummaries().list(pageSize=200),
                             "accountSummaries", on_page=lambda i, r: pages.append(r))
        props = []
        for s in summaries:
            for p in s.get("propertySummaries") or []:
                name = p.get("property")
                req = self.admin.properties().get(name=name)
                detail = self.transport.call(lambda: req.execute(num_retries=0))
                pages.append(detail)
                streams = paginate(self.transport, lambda t, n=name: self.admin.properties().dataStreams().list(parent=n, pageToken=t)
                                   if t else self.admin.properties().dataStreams().list(parent=n),
                                   "dataStreams", on_page=lambda i, r: pages.append(r))
                webs = [st.get("webStreamData") or {} for st in streams]
                uris = [w.get("defaultUri") for w in webs if w.get("defaultUri")]
                # 評估 ID（G-XXXX）不是祕密；寫進 inventory 讓人核對網站上的 tag 對應到哪個 property。
                # 程式碼與 README 不寫死任何評估 ID。
                mids = [w.get("measurementId") for w in webs if w.get("measurementId")]
                props.append({"scope_id": name, "time_zone": detail.get("timeZone"),
                              "currency": detail.get("currencyCode"),
                              "create_time": detail.get("createTime"), "web_uris": uris,
                              "measurement_ids": mids})
        for i, r in enumerate(pages):
            self.ctx.save_raw(SOURCE, ["discover"], ["admin", f"p{i}"],
                              {"api": "analyticsadmin.v1beta", "request": {}, "response": r})
        return inventory_set(self.ctx, SOURCE, {"properties": props})

    def select_properties(self, inv):
        cfg = self.ctx.settings.get("ga4") or {}
        wanted = cfg.get("property")
        domain = cfg.get("site_domain") or "pogokit.com"
        props = inv.get("properties", [])
        if wanted:
            chosen = [p for p in props if p["scope_id"] == wanted]
            if not chosen:
                raise ConfigError("--ga4-property 指定的 property 不存在或沒有權限。")
        else:
            chosen = [p for p in props if any(host_matches(u, domain) for u in p.get("web_uris") or [])]
        skipped = [{"scope_id": p["scope_id"], "reason": f"網頁串流網址不是 {domain}" if not wanted else "未指定"}
                   for p in props if p not in chosen]
        self.ctx.manifest.set_skipped(SOURCE, skipped)
        self.ctx.manifest.save()
        if not chosen:
            raise SourceStop(f"找不到網頁串流網址是 {domain} 的 GA4 property；請用 --ga4-property 指定。"
                             "（不會改成收集所有 property）")
        return chosen

    # ---------------------------------------------------------- 查詢
    def _check_quota(self, resp):
        q = resp.get("propertyQuota") or {}
        stop = (self.ctx.settings.get("ga4") or {}).get("quota_stop") or {}
        checks = (("tokensPerHour", "tokens_per_hour_remaining"),
                  ("tokensPerDay", "tokens_per_day_remaining"),
                  ("tokensPerProjectPerHour", "tokens_per_project_per_hour_remaining"))
        for field, cfg_key in checks:
            remaining = (q.get(field) or {}).get("remaining")
            if remaining is not None and cfg_key in stop and int(remaining) < int(stop[cfg_key]):
                self.quota_stop_reason = f"GA4 {field} 剩餘 {remaining}，低於停損門檻 {stop[cfg_key]}"
        return q

    def _body(self, ds, metrics, start, end, offset=0, limit=PAGE_LIMIT):
        body = {"dateRanges": [{"startDate": iso(start), "endDate": iso(end)}],
                "dimensions": [{"name": d} for d in ds.dims],
                "metrics": [{"name": m} for m in metrics],
                "limit": limit, "offset": offset, "returnPropertyQuota": True, "keepEmptyRows": False}
        if ds.options.get("dimension_filter"):
            body["dimensionFilter"] = ds.options["dimension_filter"]
        return body

    def _run_report(self, prop, ds, metrics, start, end, unit_id):
        if self.quota_stop_reason:
            raise SourceStop(self.quota_stop_reason + "；已停止 GA4 並保留進度。")
        rows, pages, offset, meta_info = [], 0, 0, {}
        while True:
            body = self._body(ds, metrics, start, end, offset)
            req = self.data.properties().runReport(property=prop, body=body)
            resp = self.transport.call(lambda: req.execute(num_retries=0))
            self.ctx.save_raw(SOURCE, [ds.name, iso(start)[:7]], [ds.name, f"{iso(start)}_{iso(end)}", f"p{pages}"],
                              {"api": "analyticsdata.v1beta.runReport", "request": body,
                               "unit_id": unit_id, "response": resp})
            pages += 1
            q = self._check_quota(resp)
            # quota 用量：tokensPerDay.consumed 是「這次請求」消耗的 token（remaining 是整體剩餘）
            consumed = (q.get("tokensPerDay") or {}).get("consumed")
            if consumed is not None:
                meta_info["tokens_consumed"] = meta_info.get("tokens_consumed", 0) + int(consumed)
            for field, out_key in (("tokensPerDay", "tokens_per_day_remaining"),
                                   ("tokensPerHour", "tokens_per_hour_remaining")):
                rem = (q.get(field) or {}).get("remaining")
                if rem is not None:
                    meta_info[out_key] = int(rem)
            md = resp.get("metadata") or {}
            meta_info["data_loss_from_other_row"] = md.get("dataLossFromOtherRow", False) or meta_info.get("data_loss_from_other_row", False)
            meta_info["subject_to_thresholding"] = md.get("subjectToThresholding", False) or meta_info.get("subject_to_thresholding", False)
            if md.get("samplingMetadatas"):
                meta_info["sampling"] = md["samplingMetadatas"]
            if md.get("currencyCode"):
                meta_info["currency"] = md["currencyCode"]
            dim_names = [h.get("name") for h in resp.get("dimensionHeaders") or []]
            met_names = [h.get("name") for h in resp.get("metricHeaders") or []]
            got = resp.get("rows") or []
            for r in got:
                dv = [v.get("value") for v in r.get("dimensionValues") or []]
                mv = [v.get("value") for v in r.get("metricValues") or []]
                vals = dict(zip(dim_names, dv))
                out = {"date": iso(to_date(vals.get("date")))}
                for d in ds.dim_cols:
                    out[d] = vals.get(d, "")
                mvals = dict(zip(met_names, mv))
                for m in ds.metrics:
                    out[m] = mvals.get(m, "")
                rows.append(out)
            total = int(resp.get("rowCount") or 0)
            offset += len(got)
            if not got or offset >= total:
                break
        rows, dropped, daily = self._guard(ds, rows)
        if dropped:
            meta_info["dropped_rows_by_rule"] = dropped
            meta_info["dropped_daily"] = daily
        return rows, pages, meta_info

    def _guard(self, ds, rows):
        """回傳 (要寫入的列, {規則: 排除列數})。

        - 首頁資料集：路徑不是 "/" → 整個停止（filter 失效）；命中 s= 或 digits12 的列逐列排除，
          資料集繼續（例：社群分享連結夾帶的長數字追蹤參數、有人在 CP 查詢欄輸入長數字）。
        - pagePath／landingPage 資料集：命中就整個停止（本來就不該出現 query）。
        """
        dropped, daily = {}, []
        if ds.options.get("home_query"):
            check_home_paths(ds.name, [r.get("pagePathPlusQueryString") for r in rows])
            kept, removed, dropped = split_rows(rows, "pagePathPlusQueryString", HOME_DROP_RULES)
            if removed:
                daily = dropped_daily_stats(rows, removed, DROP_SUM_METRICS)
                stop = (self.ctx.settings.get("ga4") or {}).get("home_drop_stop") or {}
                check_drop_stop(ds.name, daily, float(stop.get("max_ratio", 0.01)), int(stop.get("max_rows", 20)),
                                int(stop.get("min_rows_for_ratio", 3)))
            rows = kept
        if ds.options.get("path_guard"):
            col = ds.options["path_guard"]
            guard_dimension(ds.name, col, [r.get(col) for r in rows], GA4_PATH_RULES)
        return rows, dropped, daily

    def probe(self, prop, ds, force=False):
        key = dataset_key(SOURCE, ds.name, prop)
        rec = probe_get(self.ctx, key)
        if rec and not force:
            return rec
        body = {"dimensions": [{"name": d} for d in ds.dims], "metrics": [{"name": m} for m in ds.metrics],
                "compatibilityFilter": "COMPATIBLE"}
        if ds.options.get("dimension_filter"):
            body["dimensionFilter"] = ds.options["dimension_filter"]
        req = self.data.properties().checkCompatibility(property=prop, body=body)
        try:
            resp = self.transport.call(lambda: req.execute(num_retries=0))
        except ApiError as exc:
            if exc.category == E.BAD_REQUEST:
                return probe_set(self.ctx, key, status="unsupported", metrics=[], reason=exc.message[:200])
            raise
        self.ctx.save_raw(SOURCE, ["probe"], [ds.name, "checkCompatibility"],
                          {"api": "analyticsdata.v1beta.checkCompatibility", "request": body, "response": resp})
        ok_dims = {(c.get("dimensionMetadata") or {}).get("apiName") for c in resp.get("dimensionCompatibilities") or []}
        ok_mets = [(c.get("metricMetadata") or {}).get("apiName") for c in resp.get("metricCompatibilities") or []]
        metrics = [m for m in ds.metrics if m in ok_mets]
        if not set(ds.dims) <= ok_dims or not metrics:
            return probe_set(self.ctx, key, status="unsupported", metrics=metrics,
                             rejected=[m for m in ds.metrics if m not in metrics])
        end = self.ctx.end
        start = end.fromordinal(end.toordinal() - int(self.ctx.settings.get("probe_days", 7)) + 1)
        try:
            rows, _, _ = self._run_report(prop, ds, metrics, start, end, "probe")
        except ApiError as exc:
            if exc.category == E.BAD_REQUEST:
                return probe_set(self.ctx, key, status="unsupported", metrics=[], reason=exc.message[:200])
            raise
        # 試查 0 列 → no_data：backfill 跳過，只有重新 probe 才會再檢查（例如 ga4_date_ads）
        return probe_set(self.ctx, key, status="supported" if rows else "no_data", metrics=metrics,
                         rejected=[m for m in ds.metrics if m not in metrics], probe_rows=len(rows))

    def fetch(self, prop, ds, metrics, unit, quality, dropped_tbl=None):
        rows, pages, info = self._run_report(prop, ds, metrics, unit.start, unit.end, unit.id)
        if dropped_tbl is not None and ds.options.get("home_query"):
            # 每天被排除列的合計（不含維度值）；同一 unit 重抓時整段替換，不會累加
            s, e = iso(unit.start), iso(unit.end)
            dropped_tbl.upsert(
                [dict({"dataset": ds.name, "scope_id": prop, "fetched_at": utc_stamp()}, **rec)
                 for rec in info.get("dropped_daily") or []],
                drop=lambda r, n=ds.name, p=prop: (r.get("dataset") == n and r.get("scope_id") == p
                                                   and s <= (r.get("date") or "") <= e))
        other_rows, share = ga4_other_stats(rows, ds.dim_cols, metrics[0] if metrics else "")
        quality.upsert([{"dataset": ds.name, "scope_id": prop, "unit_start": iso(unit.start),
                         "unit_end": iso(unit.end), "rows": len(rows), "other_rows": other_rows,
                         "other_share": share, "data_loss_from_other_row": info.get("data_loss_from_other_row"),
                         "subject_to_thresholding": info.get("subject_to_thresholding"),
                         "sampling": info.get("sampling") or "", "fetched_at": "",
                         "dropped_rows_by_rule": json.dumps(info["dropped_rows_by_rule"], sort_keys=True)
                         if info.get("dropped_rows_by_rule") else ""}])
        if info.get("dropped_rows_by_rule"):
            # 只記規則與列數，不記命中的值
            self.ctx.event("rows_dropped", "warn", source=SOURCE, dataset=ds.name, unit=unit.id,
                           dropped_rows_by_rule=info["dropped_rows_by_rule"])
        return UnitResult(rows=rows, status=cp.OK, pages=pages,
                          info={k: v for k, v in info.items() if k in ("data_loss_from_other_row",
                                                                       "subject_to_thresholding",
                                                                       "dropped_rows_by_rule")})

    # ---------------------------------------------------------- 執行
    def run(self, mode, start=None, end=None, datasets=None):
        inv = self.discover()
        props = self.select_properties(inv)
        cfg = self.ctx.settings.get("refetch", {})
        end = to_date(end) if end else self.ctx.end
        prov = provisional_from(SOURCE, end, cfg)
        quality = SnapshotTable(self.ctx.source_dir(SOURCE) / "csv" / "ga4_quality.csv", QUALITY_HEADER,
                                ["dataset", "scope_id", "unit_start", "unit_end"])
        dropped_tbl = SnapshotTable(self.ctx.source_dir(SOURCE) / "csv" / "ga4_quality_dropped_daily.csv",
                                    DROPPED_DAILY_HEADER, ["dataset", "scope_id", "date"])
        for p in props:
            prop = p["scope_id"]
            floor = backfill_floor(SOURCE, end, (p.get("create_time") or "")[:10] or None)
            for ds in DATASETS:
                if datasets and ds.name not in datasets:
                    continue
                key = dataset_key(SOURCE, ds.name, prop)
                pr = probe_dataset(self, prop, ds, key)
                if pr is None:
                    continue
                status = probe_status(pr)
                if status != "supported":
                    limits = list(ds.known_limits) + history_limits(p)
                    if status == "no_data":
                        limits.append(ADS_NO_DATA_NOTE if ds.name == "ga4_date_ads" else
                                      "試查期間 0 列，不排入回補；重新執行 probe 才會再檢查")
                    rec = self.ctx.manifest.update_dataset(key, checkpoints=self.ctx.checkpoints,
                                                           meta={"known_limits": limits},
                                                           extra={"probe": status,
                                                                  "probe_rows": pr.get("probe_rows")})
                    if status == "no_data":
                        rec["status"] = "no_data"
                        self.ctx.manifest.save()
                    continue
                metrics = pr.get("metrics") or ds.metrics
                units = units_for_mode(self.ctx, SOURCE, ds, prop, mode, floor, start=start, end=end,
                                       refetch_from=refetch_start(SOURCE, end, cfg))
                limits = list(ds.known_limits) + history_limits(p)
                if ds.options.get("home_query"):
                    limits.append(HOME_DROP_NOTE)
                meta = {"time_zone": p.get("time_zone"), "currency": p.get("currency"),
                        "known_limits": limits, "dimensions": ds.dims, "metrics_available": metrics}
                run_units(self.ctx, SOURCE, ds, prop, units,
                          fetch=lambda u, ds=ds, metrics=metrics: self.fetch(prop, ds, metrics, u, quality, dropped_tbl),
                          breaker=self.breaker, provisional_from=prov, mode=mode, tz=p.get("time_zone") or "",
                          currency=p.get("currency"), meta=meta)
                extra = {"provisional_from": iso(prov), "refetch_window_days": cfg.get("ga4_days", 7)}
                if ds.options.get("home_query"):
                    extra["dropped_rows_by_rule"] = dropped_totals(self.ctx.checkpoints, key + "/")
                    gap = self.home_query_gap(prop)
                    if gap:
                        extra["known_limits"] = limits + [gap["note"]]
                        extra["home_query_first_date"] = gap["home_first"]
                self.ctx.manifest.update_dataset(key, checkpoints=self.ctx.checkpoints, extra=extra)

    def home_query_gap(self, prop):
        """首頁 query 第一個有列的日期，晚於 property 有資料的第一天（以 ga4_date 為準）時，回傳說明。

        日期都取自資料，不寫死。原因【未知】（API 端行為），不是 Collector 的錯誤。
        """
        from ..storage import DatasetFiles
        by_name = {ds.name: ds for ds in DATASETS}
        home, base = by_name[HOME_DATASET], by_name["ga4_date"]
        hs = DatasetFiles(self.ctx.source_dir(SOURCE), home.name, home.layout, home.header,
                          home.key_fields).stats(prop)
        bs = DatasetFiles(self.ctx.source_dir(SOURCE), base.name, base.layout, base.header,
                          base.key_fields).stats(prop)
        home_first, prop_first = hs["first_date_with_rows"], bs["first_date_with_rows"]
        if not home_first or not prop_first or home_first <= prop_first:
            return None
        day_before = iso(to_date(home_first).fromordinal(to_date(home_first).toordinal() - 1))
        note = (f"首頁 query 資料自 {home_first} 起；{prop_first}～{day_before} API 回傳 0 列"
                "（重抓後仍相同即屬 API 端行為），原因【未知】，不是 Collector 的錯誤；"
                "這段期間不要拿 ga4_date_home_query 和 ga4_date_page 對帳")
        return {"note": note, "home_first": home_first, "property_first": prop_first}
