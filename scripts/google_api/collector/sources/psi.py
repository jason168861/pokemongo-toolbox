"""PageSpeed Insights API（設計 §3.5）。

注意：Lighthouse 會真的載入頁面並執行站上的 JS（Firebase 瀏覽計數、GA4、AdSense 廣告請求），
所以每次執行有總測試數上限（--max-tests），預設只跑 1 次。
"""
import urllib.parse

from ..errors import ApiError, ConfigError
from ..quality import median
from ..runlog import error_text, utc_stamp
from ..storage import SnapshotTable, slug
from ..transport import http_json

SOURCE = "psi"
ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

RUN_HEADER = ["url", "final_url", "strategy", "batch", "run_index", "fetch_time", "lighthouse_version", "status",
              "perf_score", "a11y_score", "bp_score", "seo_score",
              "lcp_ms", "cls", "fcp_ms", "tbt_ms", "si_ms", "ttfb_ms",
              "inp_field_p75", "has_field_data", "field_overall_category", "origin_fallback",
              "run_warnings", "runtime_error"]
SUMMARY_HEADER = ["url", "strategy", "batch", "runs_ok", "perf_score", "lcp_ms", "cls", "fcp_ms", "tbt_ms",
                  "si_ms", "ttfb_ms"]

AUDITS = {"lcp_ms": "largest-contentful-paint", "cls": "cumulative-layout-shift",
          "fcp_ms": "first-contentful-paint", "tbt_ms": "total-blocking-time",
          "si_ms": "speed-index", "ttfb_ms": "server-response-time"}
CATS = {"perf_score": "performance", "a11y_score": "accessibility", "bp_score": "best-practices",
        "seo_score": "seo"}


def build_url(page_url, strategy, categories):
    params = [("url", page_url), ("strategy", strategy)] + [("category", c) for c in categories]
    return ENDPOINT + "?" + urllib.parse.urlencode(params)


def parse_result(resp):
    """回傳一列（不含 url/strategy/batch/run_index）。runtimeError → status lh_error，不寫分數。"""
    lh = resp.get("lighthouseResult") or {}
    row = {"final_url": lh.get("finalDisplayedUrl") or lh.get("finalUrl") or resp.get("id"),
           "fetch_time": lh.get("fetchTime") or resp.get("analysisUTCTimestamp"),
           "lighthouse_version": lh.get("lighthouseVersion"),
           "run_warnings": " | ".join(lh.get("runWarnings") or [])}
    rt = lh.get("runtimeError")
    if rt and rt.get("code") not in (None, "NO_ERROR"):
        row["status"] = "lh_error"
        row["runtime_error"] = f"{rt.get('code')}: {rt.get('message', '')}"[:300]
    else:
        row["status"] = "ok"
        cats = lh.get("categories") or {}
        for col, cid in CATS.items():
            row[col] = (cats.get(cid) or {}).get("score")
        audits = lh.get("audits") or {}
        for col, aid in AUDITS.items():
            row[col] = (audits.get(aid) or {}).get("numericValue")
    le = resp.get("loadingExperience") or {}
    metrics = le.get("metrics") or {}
    row["has_field_data"] = "true" if metrics else "false"
    row["field_overall_category"] = le.get("overall_category") or ""
    row["origin_fallback"] = "true" if le.get("origin_fallback") else "false"
    inp = metrics.get("INTERACTION_TO_NEXT_PAINT") or {}
    row["inp_field_p75"] = inp.get("percentile")
    return row


def summarize(rows):
    groups = {}
    for r in rows:
        if r.get("status") != "ok":
            continue
        groups.setdefault((r["url"], r["strategy"], r["batch"]), []).append(r)
    out = []
    for (url, strategy, batch), rs in sorted(groups.items()):
        rec = {"url": url, "strategy": strategy, "batch": batch, "runs_ok": len(rs)}
        for col in ("perf_score", "lcp_ms", "cls", "fcp_ms", "tbt_ms", "si_ms", "ttfb_ms"):
            vals = []
            for r in rs:
                try:
                    vals.append(float(r.get(col)))
                except (TypeError, ValueError):
                    pass
            rec[col] = median(vals)
        out.append(rec)
    return out


def run_psi(ctx, urls, *, strategies, runs, max_tests, api_key, key_mode="header", categories=None,
            http=http_json):
    categories = categories or ["performance"]
    total = len(urls) * len(strategies) * runs
    if total > max_tests:
        raise ConfigError(f"PSI 總測試數 {len(urls)} 網址 × {len(strategies)} 策略 × {runs} 次 = {total}，"
                          f"超過上限 --max-tests {max_tests}。請減少網址或次數。")
    if ctx.dry_run:
        ctx.planned["psi"] = total
        return []
    transport = ctx.transport(SOURCE)
    timeout = (ctx.settings.get("timeout_seconds") or {}).get("psi", 120)
    batch = utc_stamp()
    rows = []
    for u in urls:
        for strategy in strategies:
            for i in range(runs):
                req_url = build_url(u, strategy, categories)
                base = {"url": u, "strategy": strategy, "batch": batch, "run_index": i + 1}
                try:
                    status, resp = transport.call(lambda: http("GET", req_url, api_key=api_key,
                                                               key_mode=key_mode, timeout=timeout))
                except ApiError as exc:
                    row = dict(base, status="http_error", runtime_error=error_text(exc)[:300], fetch_time=utc_stamp())
                    rows.append(row)
                    ctx.event("psi_failed", "error", source=SOURCE, url=u, strategy=strategy,
                              error_class=exc.category, message=error_text(exc))
                    continue
                ctx.save_raw(SOURCE, [batch[:7]], [strategy, slug(u, 60), f"r{i + 1}"],
                             {"api": "pagespeedonline.v5.runPagespeed",
                              "request": {"url": u, "strategy": strategy, "category": categories},
                              "http_status": status, "response": resp})
                row = dict(base)
                row.update(parse_result(resp))
                rows.append(row)
                ctx.event("psi_done", source=SOURCE, url=u, strategy=strategy, status=row["status"])
    out_dir = ctx.source_dir(SOURCE) / "csv"
    SnapshotTable(out_dir / "psi_runs.csv", RUN_HEADER, ["url", "strategy", "fetch_time", "run_index"]).upsert(rows)
    SnapshotTable(out_dir / "psi_summary.csv", SUMMARY_HEADER, ["url", "strategy", "batch"]).upsert(summarize(rows))
    return rows
