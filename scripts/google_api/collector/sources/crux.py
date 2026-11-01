"""CrUX API ＋ History API（設計 §3.6）。

404 代表「沒有資料」：寫一列 status=no_data，指標留空，絕不寫成 0。
資料是 28 天滾動平均；History 各期互相重疊，不能當成每日或每週的獨立數據。
"""
import math

from .. import errors as E
from ..errors import ApiError
from ..runlog import error_text, utc_stamp
from ..storage import SnapshotTable, slug
from ..transport import http_json

SOURCE = "crux"
URL_CURRENT = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"
URL_HISTORY = "https://chromeuxreport.googleapis.com/v1/records:queryHistoryRecord"

CURRENT_HEADER = ["target", "target_type", "form_factor", "metric", "status", "p75",
                  "good_density", "ni_density", "poor_density",
                  "collection_first_date", "collection_last_date", "url_normalization", "fetched_at"]
HISTORY_HEADER = ["target", "target_type", "form_factor", "metric", "status",
                  "period_first_date", "period_last_date", "p75", "p75_missing",
                  "good_density", "ni_density", "poor_density", "fetched_at"]
NOTE = "28 天滾動平均；History 各期互相重疊，不能當成每日或每週的獨立數據。"


def _date(d):
    if not d:
        return ""
    return f"{int(d['year']):04d}-{int(d['month']):02d}-{int(d['day']):02d}"


def _num(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f):
        return None
    return v


def body_for(target, target_type, form_factor, history_periods=None):
    body = {target_type: target}
    if form_factor:
        body["formFactor"] = form_factor
    if history_periods:
        body["collectionPeriodCount"] = history_periods
    return body


def parse_current(resp, base):
    rec = resp.get("record") or {}
    period = rec.get("collectionPeriod") or {}
    norm = resp.get("urlNormalizationDetails") or {}
    rows = []
    for metric, data in sorted((rec.get("metrics") or {}).items()):
        hist = data.get("histogram") or []
        dens = [h.get("density") for h in hist] + [None, None, None]
        rows.append(dict(base, metric=metric, status="ok",
                         p75=_num((data.get("percentiles") or {}).get("p75")),
                         good_density=dens[0], ni_density=dens[1], poor_density=dens[2],
                         collection_first_date=_date(period.get("firstDate")),
                         collection_last_date=_date(period.get("lastDate")),
                         url_normalization=norm.get("normalizedUrl") or ""))
    return rows


def parse_history(resp, base):
    rec = resp.get("record") or {}
    periods = rec.get("collectionPeriods") or []
    rows = []
    for metric, data in sorted((rec.get("metrics") or {}).items()):
        p75s = ((data.get("percentilesTimeseries") or {}).get("p75s")) or []
        hts = data.get("histogramTimeseries") or []
        for i, period in enumerate(periods):
            p75 = _num(p75s[i]) if i < len(p75s) else None
            dens = []
            for h in hts[:3]:
                ds = h.get("densities") or []
                dens.append(_num(ds[i]) if i < len(ds) else None)
            dens += [None, None, None]
            rows.append(dict(base, metric=metric, status="ok",
                             period_first_date=_date(period.get("firstDate")),
                             period_last_date=_date(period.get("lastDate")),
                             p75=p75, p75_missing="true" if p75 is None else "false",
                             good_density=dens[0], ni_density=dens[1], poor_density=dens[2]))
    return rows


def stale_no_data(new_rows):
    """這次有資料的 (target, form_factor, metric)：刪掉同組合的舊 no_data 列。

    no_data 列的 metric 是空字串（代表該 target × form_factor 整組沒有資料），
    只要同一個 target × form_factor 這次拿到任何指標，就一併刪除。
    """
    triples = {(r["target"], r["form_factor"], r.get("metric", "")) for r in new_rows if r.get("status") == "ok"}
    pairs = {(t, f) for t, f, _ in triples}

    def drop(old):
        if old.get("status") != "no_data":
            return False
        key = (old.get("target"), old.get("form_factor"))
        return (key + (old.get("metric") or "",)) in triples or (not old.get("metric") and key in pairs)
    return drop


def run_crux(ctx, urls, *, origin, form_factors, history_periods, api_key, key_mode="header",
             with_history=True, http=http_json):
    targets = [(origin, "origin")] + [(u, "url") for u in urls]
    endpoints = [("current", URL_CURRENT)] + ([("history", URL_HISTORY)] if with_history else [])
    if ctx.dry_run:
        ctx.planned["crux"] = len(targets) * len(form_factors) * len(endpoints)
        return {}
    transport = ctx.transport(SOURCE)
    timeout = (ctx.settings.get("timeout_seconds") or {}).get("crux", 30)
    fetched_at = utc_stamp()
    out = {"current": [], "history": []}
    counts = {"ok": 0, "no_data": 0, "failed": 0}
    for target, ttype in targets:
        for ff in form_factors:
            ff_name = ff or "ALL_FORM_FACTORS"
            for kind, url in endpoints:
                body = body_for(target, ttype, ff, history_periods if kind == "history" else None)
                base = {"target": target, "target_type": ttype, "form_factor": ff_name, "fetched_at": fetched_at}
                try:
                    status, resp = transport.call(lambda: http("POST", url, api_key=api_key, key_mode=key_mode,
                                                               body=body, timeout=timeout))
                except ApiError as exc:
                    if exc.category == E.NOT_FOUND:
                        nd = dict(base, metric="", status="no_data")
                        if kind == "history":
                            nd["p75_missing"] = "true"
                        out[kind].append(nd)
                        counts["no_data"] += 1
                        ctx.event("crux_no_data", source=SOURCE, target=target, form_factor=ff_name, endpoint=kind)
                        continue
                    counts["failed"] += 1
                    ctx.event("crux_failed", "error", source=SOURCE, target=target, form_factor=ff_name,
                              endpoint=kind, error_class=exc.category, message=error_text(exc))
                    continue
                ctx.save_raw(SOURCE, [fetched_at[:7]], [kind, slug(target, 60), ff_name],
                             {"api": f"chromeuxreport.v1.{kind}", "request": body, "http_status": status,
                              "response": resp})
                rows = parse_current(resp, base) if kind == "current" else parse_history(resp, base)
                out[kind].extend(rows)
                counts["ok"] += 1
    csv_dir = ctx.source_dir(SOURCE) / "csv"
    SnapshotTable(csv_dir / "crux_current.csv", CURRENT_HEADER,
                  ["target", "form_factor", "metric", "collection_last_date", "status"]
                  ).upsert(out["current"], drop=stale_no_data(out["current"]))
    if with_history:
        SnapshotTable(csv_dir / "crux_history.csv", HISTORY_HEADER,
                      ["target", "form_factor", "metric", "period_first_date", "period_last_date", "status"]
                      ).upsert(out["history"], drop=stale_no_data(out["history"]))
    ctx.manifest.data.setdefault("datasets", {})["crux/crux/" + origin] = {
        "status": "ok" if not counts["failed"] else "partial", "counts": counts,
        "last_success_at": fetched_at, "known_limits": [NOTE]}
    ctx.manifest.save()
    return out
