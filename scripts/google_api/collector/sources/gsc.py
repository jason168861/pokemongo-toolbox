"""Search Console API（searchconsole v1，設計 §3.2）。"""
from urllib.parse import urlparse

from .. import checkpoint as cp
from .. import errors as E
from ..dates import backfill_floor, days_between, iso, provisional_from, refetch_start, to_date
from ..engine import Dataset, SourceStop, UnitResult, make_breaker, run_units, units_for_mode
from ..errors import ApiError, QueryInDimension
from ..manifest import dataset_key
from ..quality import GSC_QUALITY_HEADER, URL_RULES, gsc_quality_row, guard_dimension, median
from ..runlog import error_text
from ..storage import DatasetFiles, read_csv
from . import inventory_get, inventory_set, probe_get, probe_set, write_snapshot

SOURCE = "gsc"
TZ = "America/Los_Angeles"
ROW_LIMIT = 25000
DAILY_CAP = 50000
METRICS = ["clicks", "impressions", "ctr", "position"]
NO_QUERY_TYPES = {"discover", "googleNews"}

GROUPS = [
    # (後綴, 維度（不含 date）, 切段, 檔案)
    ("date", [], "range", "monthly"),
    ("date_country", ["country"], "month", "monthly"),
    ("date_device", ["device"], "month", "monthly"),
    ("date_page", ["page"], "day", "daily"),
    ("date_query", ["query"], "day", "daily"),
    ("date_page_query", ["page", "query"], "day", "daily"),
    ("date_query_country", ["query", "country"], "day", "daily"),
]

LIMITS = ["匿名查詢不會出現在 query 維度，query 清單不完整（落差見 gsc_quality）",
          "每日每種搜尋類型最多 50,000 列",
          "日期是美國太平洋時間",
          "依 page 彙總與依資源彙總的口徑不同，不可互相加總比對"]


def site_host(scope_id):
    s = str(scope_id or "")
    if s.lower().startswith("sc-domain:"):
        return s[len("sc-domain:"):].strip().lower().rstrip(".")
    return (urlparse(s).hostname or "").lower().rstrip(".")


def site_matches(scope_id, domain):
    host = site_host(scope_id)
    domain = domain.lower()
    return host == domain or host.endswith("." + domain)


def dataset_for(search_type, suffix, dims, chunk, layout):
    opts = {"search_type": search_type}
    if "page" in dims:
        opts["url_guard"] = "page"
    return Dataset(source=SOURCE, name=f"gsc_{search_type}_{suffix}", dims=["date"] + dims, dim_cols=list(dims),
                   metrics=list(METRICS), chunk=chunk, layout=layout, extra_cols=["search_type"],
                   options=opts, known_limits=list(LIMITS))


def datasets_for_type(search_type, settings):
    qc_types = set((settings.get("gsc") or {}).get("query_country_types") or ["web"])
    out = []
    for suffix, dims, chunk, layout in GROUPS:
        if "query" in dims and search_type in NO_QUERY_TYPES:
            continue
        if suffix == "date_query_country" and search_type not in qc_types:
            continue
        out.append(dataset_for(search_type, suffix, dims, chunk, layout))
    return out


class GscSource:
    key = SOURCE

    def __init__(self, ctx):
        self.ctx = ctx
        self.transport = ctx.transport(SOURCE)
        self.breaker = make_breaker(ctx.settings)
        self.extra_limits = []

    @property
    def svc(self):
        return self.ctx.service("searchconsole", "v1")

    # ---------------------------------------------------------- discover
    def discover(self, force=False):
        inv = inventory_get(self.ctx, SOURCE)
        if self.ctx.dry_run:
            return self.ctx.require_inventory(inv, SOURCE)
        if inv and not force:
            return inv
        req = self.svc.sites().list()
        resp = self.transport.call(lambda: req.execute(num_retries=0))
        self.ctx.save_raw(SOURCE, ["discover"], ["sites"], {"api": "searchconsole.v1.sites.list",
                                                           "request": {}, "response": resp})
        entries = [{"scope_id": e.get("siteUrl"), "permission": e.get("permissionLevel")}
                   for e in resp.get("siteEntry") or []]
        inv = inventory_set(self.ctx, SOURCE, {"sites": entries})
        return inv

    def select_sites(self, inv):
        """只選網域符合 gsc.site_domain 的資源（設計 §3.2，比照 GA4）。

        - 預設：優先 sc-domain:<網域>，沒有才用該網域的 URL-prefix 資源，只選一個。
        - --gsc-site all：該網域的所有資源（不會包含其他網域）。
        - --gsc-site <資源>：使用者明確指定（例如舊網域歷史，需使用者同意）。
        - 找不到符合的資源 → SourceStop，不會退回選其他資源（帳號底下可能有使用者的私人網站）。
        API 回傳順序沒有保證，所以不依賴順序。
        """
        cfg = self.ctx.settings.get("gsc") or {}
        wanted = cfg.get("site")
        domain = (cfg.get("site_domain") or "pogokit.com").lower()
        legacy_hint = cfg.get("legacy_path_hint")
        entries = inv.get("sites", [])
        usable = [e for e in entries if e.get("permission") != "siteUnverifiedUser"]
        matching = [e for e in usable if site_matches(e["scope_id"], domain)]
        if wanted == "all":
            chosen = matching
        elif wanted:
            chosen = [e for e in usable if e["scope_id"] == wanted]
            if not chosen:
                raise E.ConfigError("--gsc-site 指定的資源不存在或沒有權限。")
        else:
            exact = [e for e in matching if str(e["scope_id"]).lower() == f"sc-domain:{domain}"]
            others = sorted((e for e in matching if e not in exact), key=lambda e: str(e["scope_id"]))
            chosen = (exact or others)[:1]
        skipped = []
        self.extra_limits = []
        for e in entries:
            if e in chosen:
                continue
            sid = str(e["scope_id"])
            if e not in usable:
                reason = "沒有權限（siteUnverifiedUser）"
            elif e not in matching:
                reason = f"不是 {domain}"
            else:
                reason = "與已選資源重複（URL-prefix 是 sc-domain 的子集合）；可用 --gsc-site 指定"
            item = {"scope_id": sid, "reason": reason}
            if legacy_hint and legacy_hint in sid and e not in matching:
                item["note"] = "舊網域"
                self.extra_limits.append(f"可用 --gsc-site {sid} 另外收集舊網域歷史，需要使用者同意")
            skipped.append(item)
        self.ctx.manifest.set_skipped(SOURCE, skipped)
        self.ctx.manifest.save()
        if not chosen:
            raise SourceStop(f"找不到網域是 {domain} 的 Search Console 資源；請用 --gsc-site 指定。"
                             "（不會改成收集其他資源）")
        return [e["scope_id"] for e in chosen]

    # ---------------------------------------------------------- 查詢
    def _query_all(self, site, ds, start, end, unit_id):
        """分頁抓完一個 unit。回傳 (rows, pages, info)。"""
        search_type = ds.options["search_type"]
        rows, pages, start_row = [], 0, 0
        info = {}
        while True:
            body = {"startDate": iso(start), "endDate": iso(end), "dimensions": list(ds.dims),
                    "type": search_type, "dataState": "all", "rowLimit": ROW_LIMIT, "startRow": start_row}
            req = self.svc.searchanalytics().query(siteUrl=site, body=body)
            resp = self.transport.call(lambda: req.execute(num_retries=0))
            self.ctx.save_raw(SOURCE, [ds.name, iso(start)[:7]], [ds.name, f"{iso(start)}_{iso(end)}", f"p{pages}"],
                              {"api": "searchconsole.v1.searchanalytics.query", "request": body,
                               "unit_id": unit_id, "response": resp})
            pages += 1
            got = resp.get("rows") or []
            meta = resp.get("metadata") or {}
            if meta.get("firstIncompleteDate"):
                info["first_incomplete_date"] = meta["firstIncompleteDate"]
            if resp.get("responseAggregationType"):
                info["aggregation"] = resp["responseAggregationType"]
            for r in got:
                keys = r.get("keys") or []
                out = {"date": keys[0] if keys else None, "search_type": search_type}
                for col, val in zip(ds.dim_cols, keys[1:]):
                    out[col] = val
                for m in METRICS:
                    out[m] = r.get(m)
                rows.append(out)
            if len(got) < ROW_LIMIT:
                break
            start_row += len(got)
            if start_row >= DAILY_CAP:
                info["hit_daily_cap"] = True
                break
        if ds.options.get("url_guard"):
            guard_dimension(ds.name, "page", [r.get("page") for r in rows], URL_RULES)
        return rows, pages, info

    def fetch(self, site, ds, unit):
        rows, pages, info = self._query_all(site, ds, unit.start, unit.end, unit.id)
        return UnitResult(rows=rows, status=cp.OK, pages=pages, info=info)

    def type_probe(self, site, search_type, start, end):
        """用 [date] 查整段（1 次請求）判斷這個搜尋類型有沒有資料。

        - 400 → unsupported
        - 0 列，或「有列但 impressions 總和為 0」→ no_data（API 對沒有資料的類型也可能逐日回 0）
        - impressions 總和 > 0 → supported；first_date／last_date 取 impressions > 0 的日期
        """
        key = f"{SOURCE}/type/{search_type}/{site}"
        ds = dataset_for(search_type, "date", [], "range", "monthly")
        try:
            rows, pages, info = self._query_all(site, ds, start, end, "probe")
        except ApiError as exc:
            if exc.category == E.BAD_REQUEST:
                return probe_set(self.ctx, key, status="unsupported", reason=exc.message[:200])
            raise
        active = [r for r in rows if r.get("date") and _num(r.get("impressions")) > 0]
        total_impr = sum(_num(r.get("impressions")) for r in rows)
        total_clicks = sum(_num(r.get("clicks")) for r in rows)
        base = {"rows_returned": len(rows), "probe_rows": len(rows), "impressions": total_impr, "clicks": total_clicks,
                "probe_start": iso(start), "probe_end": iso(end)}
        if not active:
            reason = "API 沒有回傳任何列" if not rows else "有回傳列，但該期間 impressions 總和為 0"
            return probe_set(self.ctx, key, status="no_data", reason=reason, **base)
        dates = sorted(r["date"] for r in active)
        return probe_set(self.ctx, key, status="supported", first_date=dates[0], last_date=dates[-1], **base)

    def _record_type_skipped(self, site, search_type, pr):
        """沒有資料或不支援的搜尋類型：在 manifest 留一筆紀錄（不排入回補）。"""
        key = dataset_key(SOURCE, f"gsc_{search_type}_date", site)
        if pr.get("status") == "no_data":
            note = (f"{pr.get('probe_start', '?')}～{pr.get('probe_end', '?')} 期間 impressions 為 0"
                    f"（API 回傳 {pr.get('rows_returned', 0)} 列）；不排入回補，update 時會再確認一次")
        else:
            note = f"API 不支援這個搜尋類型：{pr.get('reason', '')}"
        rec = self.ctx.manifest.update_dataset(key, checkpoints=self.ctx.checkpoints,
                                               extra={"probe": pr.get("status"), "known_limits": [note],
                                                      "probe_checked_at": pr.get("probed_at")})
        rec["status"] = pr.get("status")
        self.ctx.manifest.save()

    # ---------------------------------------------------------- 執行
    def run(self, mode, start=None, end=None, datasets=None):
        inv = self.discover()
        sites = self.select_sites(inv)
        cfg = self.ctx.settings.get("refetch", {})
        end = to_date(end) if end else self.ctx.end
        floor = backfill_floor(SOURCE, end)
        types = (self.ctx.settings.get("gsc") or {}).get("search_types") or ["web"]
        for site in sites:
            for st in types:
                tkey = f"{SOURCE}/type/{st}/{site}"
                pr = probe_get(self.ctx, tkey)
                # 需要（重新）probe 的情況，backfill／update 都會做（每種類型 1 次請求）：
                # 沒有紀錄、上次是 no_data、或是舊版紀錄（沒有 impressions 欄位，當時只看「有沒有列」）
                legacy = pr is not None and pr.get("status") == "supported" and "impressions" not in pr
                if (pr is None or pr.get("status") == "no_data" or legacy) and mode in ("backfill", "update") \
                        and not self.ctx.dry_run:
                    try:
                        pr = self.type_probe(site, st, floor, end)
                    except ApiError as exc:
                        self.ctx.event("probe_failed", "error", source=SOURCE, dataset=f"type:{st}",
                                       error_class=exc.category, message=error_text(exc))
                        if exc.category == E.QUOTA_DAILY:
                            raise SourceStop("Search Console 每日配額用完。") from None
                        self.breaker.record_failure(exc.category, exc.status)
                        if self.breaker.open:
                            raise SourceStop("Search Console 斷路器開啟。") from None
                        continue
                    except QueryInDimension:
                        continue
                pr = pr or {"status": "supported"}
                if pr.get("status") != "supported":
                    self.ctx.event("type_skipped", source=SOURCE, search_type=st, status=pr.get("status"),
                                   reason=pr.get("reason"))
                    self._record_type_skipped(site, st, pr)
                    continue
                type_floor = to_date(pr["first_date"]) if pr.get("first_date") and mode == "backfill" else floor
                first_incomplete = None
                for ds in datasets_for_type(st, self.ctx.settings):
                    if datasets and ds.name not in datasets:
                        continue
                    info_box = {}

                    def fetch(u, ds=ds, box=info_box):
                        res = self.fetch(site, ds, u)
                        if res.info.get("first_incomplete_date"):
                            box["first_incomplete_date"] = res.info["first_incomplete_date"]
                        return res

                    prov = provisional_from(SOURCE, end, cfg, first_incomplete)
                    # 回補起點用 probe 的 first_date（第一個 impressions > 0 的日期），不是固定 16 個月
                    units = units_for_mode(self.ctx, SOURCE, ds, site, mode, type_floor,
                                           start=start, end=end, refetch_from=refetch_start(SOURCE, end, cfg))
                    meta = {"time_zone": TZ, "known_limits": list(ds.known_limits) + list(self.extra_limits),
                            "dimensions": ds.dims,
                            "metrics_available": METRICS}
                    run_units(self.ctx, SOURCE, ds, site, units, fetch=fetch, breaker=self.breaker,
                              provisional_from=prov, mode=mode, tz=TZ, meta=meta)
                    if info_box.get("first_incomplete_date"):
                        first_incomplete = info_box["first_incomplete_date"]
                    self.ctx.manifest.update_dataset(dataset_key(SOURCE, ds.name, site), checkpoints=self.ctx.checkpoints,
                                                     extra={"provisional_from": iso(provisional_from(SOURCE, end, cfg, first_incomplete)),
                                                            "refetch_window_days": cfg.get("gsc_days", 10)})
                if not self.ctx.dry_run:
                    q_start = start or (refetch_start(SOURCE, end, cfg) if mode == "update" else type_floor)
                    self.update_quality(site, st, q_start, end)

    # ---------------------------------------------------------- 完整性
    def update_quality(self, site, search_type, start, end):
        """比較 date 總量與 date×query、date×page 的加總，寫入 gsc_quality（設計 §6）。"""
        start = max(to_date(start), backfill_floor(SOURCE, end))
        start = min(start, to_date(end))
        d_total = DatasetFiles(self.ctx.source_dir(SOURCE), f"gsc_{search_type}_date", "monthly",
                               [], ["date", "scope_id", "search_type"])
        d_query = DatasetFiles(self.ctx.source_dir(SOURCE), f"gsc_{search_type}_date_query", "daily", [], [])
        d_page = DatasetFiles(self.ctx.source_dir(SOURCE), f"gsc_{search_type}_date_page", "daily", [], [])
        totals = {}
        for path in sorted({d_total.file_for(d) for d in days_between(start, end)}):
            _, rows = read_csv(path)
            for r in rows:
                if r.get("scope_id") == site:
                    totals[r["date"]] = r
        out_rows = []
        gaps = []
        for d in days_between(start, end):
            ds_iso = iso(d)
            t = totals.get(ds_iso)
            if not t:
                continue
            q = _sum_file(d_query.file_for(d), site)
            p = _sum_file(d_page.file_for(d), site)
            rec = self.ctx.checkpoints.get(f"{SOURCE}/gsc_{search_type}_date_query/{site}/{ds_iso}_{ds_iso}") or {}
            prec = self.ctx.checkpoints.get(f"{SOURCE}/gsc_{search_type}_date_page/{site}/{ds_iso}_{ds_iso}") or {}
            row = gsc_quality_row(ds_iso, site, search_type,
                                  {"clicks": t.get("clicks"), "impressions": t.get("impressions")},
                                  q, p, rec.get("hit_daily_cap"), prec.get("aggregation"))
            out_rows.append(row)
            if row["click_gap_ratio"] is not None:
                gaps.append(row["click_gap_ratio"])
        if not out_rows:
            return
        qf = DatasetFiles(self.ctx.source_dir(SOURCE), f"gsc_quality_{search_type}", "monthly",
                          GSC_QUALITY_HEADER, ["date", "scope_id", "search_type"])
        qf.apply(site, [to_date(r["date"]) for r in out_rows], out_rows, accept_empty=True)
        key = dataset_key(SOURCE, f"gsc_{search_type}_date_query", site)
        self.ctx.manifest.update_dataset(key, checkpoints=self.ctx.checkpoints,
                                         extra={"completeness": {"click_gap_ratio_median": median(gaps),
                                                                 "click_gap_ratio_max": max(gaps) if gaps else None,
                                                                 "days_measured": len(out_rows)}})

    def snapshot(self):
        inv = self.discover()
        for site in self.select_sites(inv):
            req = self.svc.sitemaps().list(siteUrl=site)
            resp = self.transport.call(lambda: req.execute(num_retries=0))
            items = resp.get("sitemap") or []
            pages = [resp]
            details = []
            for sm in items:
                r2 = self.svc.sitemaps().get(siteUrl=site, feedpath=sm.get("path"))
                d = self.transport.call(lambda: r2.execute(num_retries=0))
                pages.append(d)
                details.append(d)
            write_snapshot(self.ctx, SOURCE, "sitemaps", details or items, pages, "searchconsole.v1.sitemaps")

    def inspect_urls(self, urls, max_count):
        inv = self.discover()
        sites = self.select_sites(inv)
        if not sites:
            return 0
        site = sites[0]
        results, pages = [], []
        for u in urls[:max_count]:
            body = {"inspectionUrl": u, "siteUrl": site, "languageCode": "zh-TW"}
            req = self.svc.urlInspection().index().inspect(body=body)
            resp = self.transport.call(lambda: req.execute(num_retries=0))
            pages.append(resp)
            res = dict((resp.get("inspectionResult") or {}))
            res["inspectionUrl"] = u
            results.append(res)
        write_snapshot(self.ctx, SOURCE, "url_inspection", results, pages, "searchconsole.v1.urlInspection")
        return len(results)


def _num(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _sum_file(path, site):
    _, rows = read_csv(path)
    clicks = impressions = 0.0
    found = False
    for r in rows:
        if r.get("scope_id") != site:
            continue
        found = True
        try:
            clicks += float(r.get("clicks") or 0)
            impressions += float(r.get("impressions") or 0)
        except ValueError:
            pass
    if not found:
        return {}
    return {"clicks": clicks, "impressions": impressions}
