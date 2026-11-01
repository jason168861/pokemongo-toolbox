"""AdSense Management API v2（設計 §3.1）。"""
from .. import checkpoint as cp
from .. import errors as E
from ..dates import add_months, backfill_floor, iso, month_start, provisional_from, refetch_start, split_half, to_date
from ..engine import Dataset, UnitResult, make_breaker, run_units, units_for_mode
from ..errors import ApiError
from ..manifest import dataset_key
from ..quality import URL_RULES, guard_dimension
from . import inventory_get, inventory_set, paginate, probe_dataset, probe_get, probe_set, write_snapshot

SOURCE = "adsense"
API = "adsense.v2.accounts.reports.generate"

FULL_METRICS = ["ESTIMATED_EARNINGS", "PAGE_VIEWS", "PAGE_VIEWS_RPM", "PAGE_VIEWS_CTR", "IMPRESSIONS",
                "IMPRESSIONS_RPM", "IMPRESSIONS_CTR", "CLICKS", "COST_PER_CLICK", "AD_REQUESTS",
                "MATCHED_AD_REQUESTS", "AD_REQUESTS_COVERAGE", "ACTIVE_VIEW_VIEWABILITY",
                "ACTIVE_VIEW_MEASURABILITY"]
CORE_METRICS = ["ESTIMATED_EARNINGS", "PAGE_VIEWS", "IMPRESSIONS", "CLICKS", "AD_REQUESTS"]
MIN_METRICS = ["ESTIMATED_EARNINGS", "IMPRESSIONS", "CLICKS"]
METRIC_FALLBACKS = [FULL_METRICS, CORE_METRICS, MIN_METRICS]

PAGE_URL_LIMIT = ("無法透過 API 取得網頁層級收益（PAGE_URL 不支援）；替代來源：GA4 ad 指標（若已連結）或網址管道。")


def _ds(name, dims, chunk="month", **kw):
    dim_cols = [d.lower() for d in dims]
    return Dataset(source=SOURCE, name=name, dims=["DATE"] + dims, dim_cols=dim_cols, metrics=list(FULL_METRICS),
                   chunk=chunk, layout="monthly", currency=True,
                   known_limits=["預估收益在月結與無效流量調整後可能修正（重抓本月＋上月，至少 35 天）",
                                 "日期是帳戶時區的日曆日"], **kw)


ACCOUNT_DATASETS = [
    _ds("adsense_date", [], chunk="year"),
    _ds("adsense_date_country", ["COUNTRY_CODE"]),
    _ds("adsense_date_platform", ["PLATFORM_TYPE_CODE"]),
    _ds("adsense_date_adunit", ["AD_UNIT_ID", "AD_UNIT_NAME"]),
    _ds("adsense_date_adformat", ["AD_FORMAT_CODE"]),
    _ds("adsense_date_placement", ["AD_PLACEMENT_CODE"]),
    _ds("adsense_date_urlchannel", ["URL_CHANNEL_ID", "URL_CHANNEL_NAME"]),
    _ds("adsense_date_pageurl", ["PAGE_URL"], options={"url_guard": "PAGE_URL"}),
    _ds("adsense_date_domain", ["DOMAIN_NAME"]),
]

# 「只含本站」版本：帳戶底下有多個網站，以 DOMAIN_NAME 篩選（網域取自 adsense.site_domain 設定）
SITE_SUFFIX = "_site"
SITE_BASES = ("adsense_date", "adsense_date_country", "adsense_date_platform", "adsense_date_adunit",
              "adsense_date_adformat", "adsense_date_placement")


def _site_version(base):
    return Dataset(source=SOURCE, name=base.name + SITE_SUFFIX, dims=list(base.dims), dim_cols=list(base.dim_cols),
                   metrics=list(base.metrics), chunk=base.chunk, layout=base.layout, currency=True,
                   known_limits=list(base.known_limits), options={"site_filter": True})


DATASETS = []
for _base in ACCOUNT_DATASETS:
    DATASETS.append(_base)
    if _base.name in SITE_BASES:
        DATASETS.append(_site_version(_base))
del _base

# 只做本站版本的交叉資料集（分析用；沒有帳戶層級版本）
SITE_ONLY_DATASETS = [
    # INTERSTITIAL 等格式的曝光來自自動廣告還是手動單元
    _site_version(_ds("adsense_date_adformat_placement", ["AD_FORMAT_CODE", "AD_PLACEMENT_CODE"])),
    # 平台（桌機／手機）差異是否和國家組成有關
    _site_version(_ds("adsense_date_country_platform", ["COUNTRY_CODE", "PLATFORM_TYPE_CODE"])),
]
DATASETS.extend(SITE_ONLY_DATASETS)


def site_domain(settings):
    return ((settings.get("adsense") or {}).get("site_domain")
            or (settings.get("ga4") or {}).get("site_domain") or "pogokit.com").lower()


# 只認這句完整訊息（區分大小寫），而且只用在 adsense_date_pageurl（Reviewer 條件 A-a）
UNAVAILABLE_MARK = "No reporting data is available for the requested date range"
UNAVAILABLE_DATASETS = {"adsense_date_pageurl"}


def is_retention_unavailable(exc):
    """400 而且訊息含上面那句完整訊息：推論是 API 的保留期限，不是錯誤。其他 400 照常記 failed。"""
    return (getattr(exc, "category", None) == E.BAD_REQUEST
            and UNAVAILABLE_MARK in (getattr(exc, "message", "") or ""))


def availability_info(checkpoints, prefix):
    """有 unavailable 的 unit 時，算出可取得的最早月份與 API 訊息（前 200 字，已遮蔽）。"""
    from ..redact import redact
    unavailable, available = [], []
    message = ""
    for uid, rec in sorted(checkpoints.with_prefix(prefix).items()):
        start = uid.rsplit("/", 1)[-1].split("_")[0]
        if rec.get("status") == cp.UNAVAILABLE:
            unavailable.append(start)
            message = message or rec.get("api_message") or ""
        elif rec.get("status") in (cp.OK, cp.EMPTY, cp.TRUNCATED):
            available.append(start)
    if not unavailable:
        return None
    from ..runlog import utc_stamp
    earliest = min(available)[:7] if available else None
    first_unavailable = min(unavailable)[:7]
    latest_unavailable = max(unavailable)[:7]
    msg = redact(message)[:200]
    observed = utc_stamp()[:10]
    # 邊界會隨時間移動，所以寫成「截至某日的實測」，不寫成永久結論（Reviewer 條件 A-b、A-c）
    note = (f"截至 {observed} 的實測：{first_unavailable}～{latest_unavailable} 的請求回 400「沒有可用的報表資料」，"
            f"目前可取得的最早月份是 {earliest or '（尚無成功的 unit）'}。這是 400 的實測邊界【推論：API 的保留期限】，"
            f"不是 API 保證，邊界會隨時間往後移。{len(unavailable)} 個 unit 標為 unavailable，backfill／update 不重抓，"
            f"refetch 才會重試；本月與上月照常在 update 時重抓。API 原始訊息：{msg}")
    return {"note": note, "extra": {"earliest_available_month": earliest,
                                    "first_unavailable_month": first_unavailable,
                                    "latest_unavailable_month": latest_unavailable,
                                    "unavailable_boundary_observed_at": observed,
                                    "unavailable_boundary_note": "400 的實測邊界【推論】，不是 API 保證",
                                    "unavailable_message": msg}}


# 這兩個資料集本身就能區分網域／網址，不加「帳戶層級」說明（*_site 版本也不加）
SITE_SPECIFIC_DATASETS = {"adsense_date_domain", "adsense_date_pageurl"}
MULTISITE_PREFIX = "帳戶層級資料"


def site_note(site, name):
    if site["mode"] == "dimension":
        how = ("API 不接受 filters=DOMAIN_NAME==…，改用退路：維度加上 DOMAIN_NAME 下載後只保留該網域"
               "（精確比對；ratio 類指標是逐列值，不受影響）")
    else:
        how = f"以 filters=DOMAIN_NAME=={site['domain']} 在 API 端篩選"
    base = name[:-len(SITE_SUFFIX)]
    if base in SITE_BASES:
        return f"只含 {site['domain']} 的資料（{how}）；對應的帳戶層級版本是 {base}"
    return f"只含 {site['domain']} 的資料（{how}）；只做本站版本，沒有對應的帳戶層級版本"


def domain_periods(files, scope_id):
    """從 adsense_date_domain 的 CSV 算出各網域有資料的期間（最早、最晚日期）。全部取自資料，不寫死網域。"""
    from ..storage import read_csv
    periods = {}
    for path in files.all_files():
        _, rows = read_csv(path)
        for r in rows:
            if r.get("scope_id") != scope_id or not r.get("domain_name"):
                continue
            p = periods.setdefault(r["domain_name"], [r["date"], r["date"]])
            p[0] = min(p[0], r["date"])
            p[1] = max(p[1], r["date"])
    return [{"domain": k, "first_date": v[0], "last_date": v[1]} for k, v in sorted(periods.items())]


def multisite_note(periods, site=None, ds_name=None):
    """帳戶層級資料的說明。網域與日期都取自 adsense_date_domain 的資料。

    有 *_site 版本的資料集：指向 *_site；沒有的（例如 urlchannel）：請以 adsense_date_domain 篩選。
    """
    detail = "；".join(f"{p['domain']} {p['first_date']}～{p['last_date']}" for p in periods)
    mine = [p for p in periods if site and p["domain"].lower() == site]
    others = [p for p in periods if not (site and p["domain"].lower() == site)]
    if mine and others:
        head = f"{MULTISITE_PREFIX}，{mine[0]['first_date']} 前含其他網站"
    elif others:
        head = f"{MULTISITE_PREFIX}，含其他網站"
    else:
        head = f"{MULTISITE_PREFIX}，目前只看到本站"
    tail = (f"分析本站請用 {ds_name}{SITE_SUFFIX} 版本" if ds_name and ds_name in SITE_BASES
            else "分析本站時，請以 adsense_date_domain 的 domain_name 篩選，或注意各網域有資料的期間")
    return f"{head}（依 adsense_date_domain，各網域有資料的期間：{detail or '尚無資料'}）；{tail}"


def _date_params(start, end):
    s, e = to_date(start), to_date(end)
    return {"startDate_year": s.year, "startDate_month": s.month, "startDate_day": s.day,
            "endDate_year": e.year, "endDate_month": e.month, "endDate_day": e.day}


class AdSenseSource:
    key = SOURCE

    def __init__(self, ctx):
        self.ctx = ctx
        self.transport = ctx.transport(SOURCE)
        self.breaker = make_breaker(ctx.settings)

    @property
    def svc(self):
        return self.ctx.service("adsense", "v2")

    # ---------------------------------------------------------- discover
    def discover(self, force=False):
        inv = inventory_get(self.ctx, SOURCE)
        if self.ctx.dry_run:
            return self.ctx.require_inventory(inv, SOURCE)
        if inv and not force:
            return inv
        raw_pages = []
        accounts = paginate(self.transport, lambda tok: self.svc.accounts().list(pageToken=tok, pageSize=50)
                            if tok else self.svc.accounts().list(pageSize=50),
                            "accounts", on_page=lambda i, r: raw_pages.append(r))
        details = []
        for acc in accounts:
            name = acc.get("name")
            req = self.svc.accounts().get(name=name)
            d = self.transport.call(lambda: req.execute(num_retries=0))
            raw_pages.append(d)
            details.append({"scope_id": name, "time_zone": (d.get("timeZone") or {}).get("id"),
                            "create_time": d.get("createTime"), "state": d.get("state")})
        for i, r in enumerate(raw_pages):
            self.ctx.save_raw(SOURCE, ["discover"], ["accounts", f"p{i}"],
                              {"api": "adsense.v2.accounts", "request": {}, "response": r})
        inv = inventory_set(self.ctx, SOURCE, {"accounts": details})
        return inv

    # ---------------------------------------------------------- 報表
    def _generate(self, account, ds, metrics, start, end, unit_id=None, site=None):
        """site：{"mode": "filter" | "dimension", "domain": "..."}。

        filter：帶 filters=DOMAIN_NAME==<網域>，API 端篩選。
        dimension：API 不接受 filter 時的退路，維度多加 DOMAIN_NAME，下載後在 _parse 篩選。
        """
        dims = list(ds.dims)
        extra = {}
        if site and site.get("mode") == "dimension":
            dims.append("DOMAIN_NAME")
        elif site:
            extra["filters"] = [f"DOMAIN_NAME=={site['domain']}"]
        params = dict(account=account, dateRange="CUSTOM", dimensions=dims, metrics=list(metrics),
                      reportingTimeZone="ACCOUNT_TIME_ZONE", limit=100000, **_date_params(start, end), **extra)
        req = self.svc.accounts().reports().generate(**params)
        resp = self.transport.call(lambda: req.execute(num_retries=0))
        self.ctx.save_raw(SOURCE, [ds.name, iso(start)[:7]], [ds.name, f"{iso(start)}_{iso(end)}", "p0"],
                          {"api": API, "request": {k: v for k, v in params.items() if k != "account"},
                           "unit_id": unit_id, "response": resp})
        return resp

    def _parse(self, ds, resp, site=None):
        headers = resp.get("headers") or []
        names = [h.get("name") for h in headers]
        currency = None
        for h in headers:
            if h.get("currencyCode"):
                currency = h["currencyCode"]
        rows = []
        keep_domain = site["domain"] if site and site.get("mode") == "dimension" else None
        for row in resp.get("rows") or []:
            cells = row.get("cells") or []
            vals = {names[i]: (c.get("value") if isinstance(c, dict) else None) for i, c in enumerate(cells) if i < len(names)}
            if keep_domain is not None and (vals.get("DOMAIN_NAME") or "").lower() != keep_domain:
                continue      # 退路：下載後只留本站（精確比對網域）
            out = {"date": vals.get("DATE")}
            for dim, col in zip(ds.dims[1:], ds.dim_cols):
                out[col] = vals.get(dim, "")
            for m in ds.metrics:
                out[m] = vals.get(m, "")
            rows.append(out)
        return rows, currency

    def probe(self, account, ds, force=False):
        key = dataset_key(SOURCE, ds.name, account)
        rec = probe_get(self.ctx, key)
        if rec and not force:
            return rec
        end = self.ctx.end
        start = end.fromordinal(end.toordinal() - int(self.ctx.settings.get("probe_days", 7)) + 1)
        # 本站版本：先試 API 端 filter；所有指標組合都被 400 拒絕時，退回「維度加 DOMAIN_NAME、下載後篩選」
        modes = ["filter", "dimension"] if ds.options.get("site_filter") else [None]
        domain = site_domain(self.ctx.settings)
        rejected = []
        for mode in modes:
            site = {"mode": mode, "domain": domain} if mode else None
            for metrics in METRIC_FALLBACKS:
                try:
                    resp = self._generate(account, ds, metrics, start, end, unit_id="probe", site=site)
                except ApiError as exc:
                    if exc.category == E.BAD_REQUEST:
                        rejected.append({"site_mode": mode, "metrics": metrics, "reason": exc.message[:200]})
                        continue
                    raise
                rows, currency = self._parse(ds, resp, site)
                if ds.options.get("url_guard"):
                    guard_dimension(ds.name, ds.options["url_guard"], [r.get(ds.dim_cols[0]) for r in rows], URL_RULES)
                # 只記數量，不記維度值本身
                samples = {col: len({r.get(col) for r in rows if r.get(col) not in (None, "")}) for col in ds.dim_cols}
                # 7 天試查 0 列不代表整段歷史都沒有資料，所以 AdSense 的 supported_empty 仍會回補（只是標記出來）
                status = "supported" if rows else "supported_empty"
                extra = {}
                if site:
                    extra = {"site_mode": mode, "site_domain": domain,
                             "filter_rejected": any(r["site_mode"] == "filter" for r in rejected) and mode != "filter"}
                return probe_set(self.ctx, key, status=status, metrics=metrics, currency=currency,
                                 rejected=[{"site_mode": r["site_mode"], "metrics": r["metrics"]} for r in rejected],
                                 probe_rows=len(rows), dimension_value_counts=samples, **extra)
        return probe_set(self.ctx, key, status="unsupported", metrics=[],
                         rejected=[{"site_mode": r["site_mode"], "metrics": r["metrics"]} for r in rejected])

    def _fetch_range(self, account, ds, metrics, start, end, unit_id, acc, site=None):
        resp = self._generate(account, ds, metrics, start, end, unit_id=unit_id, site=site)
        acc["pages"] += 1
        rows, currency = self._parse(ds, resp, site)
        if currency:
            acc["currency"] = currency
        try:
            matched = int(resp.get("totalMatchedRows") or len(rows))
        except (TypeError, ValueError):
            matched = len(rows)
        if matched > len(rows):
            halves = split_half(start, end)
            if halves:
                for s, e in halves:
                    self._fetch_range(account, ds, metrics, s, e, unit_id, acc, site)
                return
            acc["truncated_dates"].append(iso(start))
        acc["rows"].extend(rows)

    def fetch_unit(self, account, ds, metrics, unit, site=None):
        acc = {"rows": [], "pages": 0, "truncated_dates": [], "currency": None}
        self._fetch_range(account, ds, metrics, unit.start, unit.end, unit.id, acc, site)
        if ds.options.get("url_guard"):
            guard_dimension(ds.name, ds.options["url_guard"], [r.get(ds.dim_cols[0]) for r in acc["rows"]], URL_RULES)
        status = cp.TRUNCATED if acc["truncated_dates"] else cp.OK
        return UnitResult(rows=acc["rows"], status=status, pages=acc["pages"],
                          info={"truncated_dates": acc["truncated_dates"]} if acc["truncated_dates"] else {}), acc

    # ---------------------------------------------------------- 執行
    def run(self, mode, start=None, end=None, datasets=None):
        inv = self.discover()
        cfg = self.ctx.settings.get("refetch", {})
        end = to_date(end) if end else self.ctx.end
        prov = provisional_from(SOURCE, end, cfg)
        for acc in inv.get("accounts", []):
            account = acc["scope_id"]
            floor = backfill_floor(SOURCE, end, (acc.get("create_time") or "")[:10] or None)
            for ds in DATASETS:
                if datasets and ds.name not in datasets:
                    continue
                key = dataset_key(SOURCE, ds.name, account)
                pr = probe_dataset(self, account, ds, key)
                if pr is None:
                    continue
                limits = list(ds.known_limits)
                if pr.get("status") not in ("supported", "supported_empty"):
                    if ds.name == "adsense_date_pageurl":
                        limits.append(PAGE_URL_LIMIT)
                    self.ctx.manifest.update_dataset(key, checkpoints=self.ctx.checkpoints,
                                                     meta={"known_limits": limits, "time_zone": acc.get("time_zone")},
                                                     extra={"probe": "unsupported"})
                    continue
                metrics = pr.get("metrics") or FULL_METRICS
                units = units_for_mode(self.ctx, SOURCE, ds, account, mode, floor, start=start, end=end,
                                       refetch_from=refetch_start(SOURCE, end, cfg))
                if ds.name == "adsense_date_pageurl":
                    limits.append("PAGE_URL 可能經過 Google 正規化；已檢查分享 id（s=）與 12 位數字，命中時資料集停止")
                site = None
                site_extra = {}
                if ds.options.get("site_filter"):
                    site = {"mode": pr.get("site_mode") or "filter", "domain": site_domain(self.ctx.settings)}
                    limits.append(site_note(site, ds.name))
                    site_extra = {"site_domain": site["domain"], "site_method": site["mode"]}
                meta = {"time_zone": acc.get("time_zone"), "known_limits": limits,
                        "dimensions": ds.dims, "metrics_available": metrics}
                currency_box = {"value": pr.get("currency")}

                def fetch(u, ds=ds, metrics=metrics, account=account, box=currency_box, site=site):
                    res, acc_info = self.fetch_unit(account, ds, metrics, u, site)
                    if acc_info.get("currency"):
                        box["value"] = acc_info["currency"]
                    for r in res.rows:
                        r["currency"] = box["value"] or ""
                    return res

                run_units(self.ctx, SOURCE, ds, account, units, fetch=fetch, breaker=self.breaker,
                          provisional_from=prov, mode=mode, tz=acc.get("time_zone") or "",
                          currency=currency_box["value"], meta=meta,
                          unavailable=is_retention_unavailable if ds.name in UNAVAILABLE_DATASETS else None)
                extra = {"currency": currency_box["value"],
                         "refetch_window_days": (end - refetch_start(SOURCE, end, cfg)).days + 1,
                         "provisional_from": iso(prov), **site_extra}
                avail = availability_info(self.ctx.checkpoints, key + "/")
                if avail:
                    extra.update(avail["extra"])
                    extra["known_limits"] = limits + [avail["note"]]
                self.ctx.manifest.update_dataset(key, checkpoints=self.ctx.checkpoints, extra=extra)
            if not self.ctx.dry_run:
                # 每次執行結束都依最新的 adsense_date_domain 重算（各資料集的 meta 會覆寫 known_limits）
                self.annotate_multisite(account)

    def annotate_multisite(self, account):
        """AdSense 帳戶底下可能有多個網站：在帳戶層級資料集的 known_limits 加上各網域有資料的期間。

        網域與日期都取自 adsense_date_domain 的資料。舊的同類說明會被替換，不會越加越多。
        """
        from ..storage import DatasetFiles
        dom = [ds for ds in DATASETS if ds.name == "adsense_date_domain"][0]
        files = DatasetFiles(self.ctx.source_dir(SOURCE), dom.name, dom.layout, dom.header, dom.key_fields)
        periods = domain_periods(files, account)
        if not periods:
            return []
        site = site_domain(self.ctx.settings)
        for ds in DATASETS:
            key = dataset_key(SOURCE, ds.name, account)
            rec = self.ctx.manifest.get(key)
            if rec is None:
                continue
            if ds.name in SITE_SPECIFIC_DATASETS or ds.options.get("site_filter"):
                if ds.name == "adsense_date_domain":
                    self.ctx.manifest.update_dataset(key, checkpoints=self.ctx.checkpoints,
                                                     extra={"account_domains": periods})
                continue
            limits = [x for x in (rec.get("known_limits") or []) if not str(x).startswith(MULTISITE_PREFIX)]
            limits.append(multisite_note(periods, site, ds.name))
            self.ctx.manifest.update_dataset(key, checkpoints=self.ctx.checkpoints,
                                             extra={"known_limits": limits, "account_domains": periods})
        return periods

    def snapshot(self):
        inv = self.discover()
        for acc in inv.get("accounts", []):
            account = acc["scope_id"]
            svc = self.svc
            pages = []
            clients = paginate(self.transport, lambda t: svc.accounts().adclients().list(parent=account, pageToken=t)
                               if t else svc.accounts().adclients().list(parent=account),
                               "adClients", on_page=lambda i, r: pages.append(r))
            write_snapshot(self.ctx, SOURCE, "adclients", clients, pages, "adsense.v2.adclients.list")
            for kind, items_key, getter in (("adunits", "adUnits", lambda: svc.accounts().adclients().adunits()),
                                            ("urlchannels", "urlChannels", lambda: svc.accounts().adclients().urlchannels()),
                                            ("customchannels", "customChannels", lambda: svc.accounts().adclients().customchannels())):
                all_items, all_pages = [], []
                for c in clients:
                    parent = c.get("name")
                    items = paginate(self.transport, lambda t, p=parent, g=getter: g().list(parent=p, pageToken=t)
                                     if t else g().list(parent=p), items_key,
                                     on_page=lambda i, r: all_pages.append(r))
                    all_items.extend(items)
                write_snapshot(self.ctx, SOURCE, kind, all_items, all_pages, f"adsense.v2.{kind}.list")
            for kind, items_key, getter in (("sites", "sites", lambda: svc.accounts().sites()),
                                            ("policyissues", "policyIssues", lambda: svc.accounts().policyIssues())):
                pages = []
                items = paginate(self.transport, lambda t, g=getter: g().list(parent=account, pageToken=t)
                                 if t else g().list(parent=account), items_key,
                                 on_page=lambda i, r: pages.append(r))
                write_snapshot(self.ctx, SOURCE, kind, items, pages, f"adsense.v2.{kind}.list")
            req = svc.accounts().alerts().list(parent=account)
            resp = self.transport.call(lambda: req.execute(num_retries=0))
            write_snapshot(self.ctx, SOURCE, "alerts", resp.get("alerts") or [], [resp], "adsense.v2.alerts.list")
