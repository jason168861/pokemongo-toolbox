"""完整性計算與資料守門（設計 §6、§3.3）。"""
import re

from .errors import QueryInDimension

RULES = {
    "question_mark": re.compile(r"\?"),
    "share_id_param": re.compile(r"(?:^|[?&;/])s="),
    "digits12": re.compile(r"\d{12,}"),
}

# GA4 的 pagePath / landingPage：不該有任何 query（設計 U19 護欄）
GA4_PATH_RULES = ("question_mark", "share_id_param", "digits12")
# GSC page、AdSense PAGE_URL、GA4 首頁 query：?tab= / ?mon= 是正常的，只攔分享 id 與疑似訓練家代碼
URL_RULES = ("share_id_param", "digits12")

HOME_QUERY_RE = re.compile(r"^/(\?.*)?$")


def scan_values(values, rules):
    """回傳 {rule: 命中列數}。不回傳命中的值。"""
    hits = {}
    for v in values:
        if v is None:
            continue
        s = str(v)
        for name in rules:
            if RULES[name].search(s):
                hits[name] = hits.get(name, 0) + 1
    return hits


def guard_dimension(dataset, dim_name, values, rules):
    """命中任何規則就丟 QueryInDimension。訊息只含維度名稱、規則與列數。"""
    hits = scan_values(values, rules)
    if hits:
        detail = ", ".join(f"{k}={v}" for k, v in sorted(hits.items()))
        raise QueryInDimension(f"{dataset} 的 {dim_name} 維度出現不該有的內容（{detail} 列）；資料集已停止，未寫入 CSV。",
                               hits=hits, dimension=dim_name)


def check_home_paths(dataset, values):
    """首頁資料集：路徑不是 "/" 代表 filter 失效，整個資料集停止（不是逐列排除）。"""
    bad = sum(1 for v in values if v is not None and not HOME_QUERY_RE.match(str(v)))
    if bad:
        raise QueryInDimension(f"{dataset} 出現路徑不是 \"/\" 的列（{bad} 列）；資料集已停止，未寫入 CSV。",
                               hits={"path_not_root": bad}, dimension="pagePathPlusQueryString")


def split_rows(rows, col, rules):
    """逐列分開命中規則的列。回傳 (保留的列, 排除的列, {規則: 排除列數})。

    一列命中多條規則時，每條規則各計一次（列只排除一次）。
    排除的列只給呼叫端算合計用，不可寫進 log／manifest／CSV。
    """
    kept, removed, counts = [], [], {}
    for r in rows:
        v = r.get(col)
        hit = [name for name in rules if v is not None and RULES[name].search(str(v))]
        if hit:
            for name in hit:
                counts[name] = counts.get(name, 0) + 1
            removed.append(r)
        else:
            kept.append(r)
    return kept, removed, counts


def filter_rows(rows, col, rules):
    """逐列排除命中規則的列。回傳 (保留的列, {規則: 排除列數})。不回傳命中的值。"""
    kept, _, counts = split_rows(rows, col, rules)
    return kept, counts


def dropped_daily_stats(all_rows, removed, metrics):
    """每天：總列數、排除列數、排除列的指標合計（不含維度值）。"""
    total = {}
    for r in all_rows:
        total[r.get("date")] = total.get(r.get("date"), 0) + 1
    out = {}
    for r in removed:
        d = r.get("date")
        rec = out.setdefault(d, {"date": d, "total_rows": total.get(d, 0), "dropped_rows": 0,
                                 **{m: 0.0 for m in metrics}})
        rec["dropped_rows"] += 1
        for m in metrics:
            try:
                rec[m] += float(r.get(m) or 0)
            except (TypeError, ValueError):
                pass
    return [out[k] for k in sorted(out)]


def check_drop_stop(dataset, daily, max_ratio, max_rows, min_rows_for_ratio=0):
    """停損：任何一天
    - 排除列數 > max_rows → 停；或
    - 排除列數 ≥ min_rows_for_ratio，而且 > 該日總列數 × max_ratio → 停。
    min_rows_for_ratio 讓偶發的 1–2 列不會因為當天總列數少而觸發比例停損。
    """
    for rec in daily:
        n, total = rec["dropped_rows"], rec["total_rows"] or 0
        ratio = n / total if total else 1.0
        if n > max_rows or (n >= min_rows_for_ratio and ratio > max_ratio):
            raise QueryInDimension(
                f"{dataset} 在 {rec['date']} 排除了 {n} 列（該日共 {total} 列，比例 {ratio:.2%}），"
                f"超過停損門檻（> {max_rows} 列，或 ≥ {min_rows_for_ratio} 列且 > {max_ratio:.2%}）；"
                "資料集已停止，未寫入 CSV。",
                hits={"drop_stop": n}, dimension="pagePathPlusQueryString")


def guard_home_query(dataset, values):
    """舊版行為（命中就停止）。目前 GA4 首頁資料集改用 check_home_paths + filter_rows。"""
    check_home_paths(dataset, values)
    guard_dimension(dataset, "pagePathPlusQueryString", values, URL_RULES)


def ratio_gap(total, part):
    """1 − part/total；total 為 0 或缺值時回傳 None（不是 0）。"""
    try:
        total = float(total)
        part = float(part)
    except (TypeError, ValueError):
        return None
    if total <= 0:
        return None
    return round(1.0 - part / total, 6)


def gsc_quality_row(date, scope_id, search_type, totals, query_sums, page_sums, hit_cap, aggregation):
    return {
        "date": date, "scope_id": scope_id, "search_type": search_type,
        "total_clicks": totals.get("clicks"), "total_impressions": totals.get("impressions"),
        "query_sum_clicks": query_sums.get("clicks"), "query_sum_impressions": query_sums.get("impressions"),
        "click_gap_ratio": ratio_gap(totals.get("clicks"), query_sums.get("clicks")),
        "impression_gap_ratio": ratio_gap(totals.get("impressions"), query_sums.get("impressions")),
        "page_sum_clicks": page_sums.get("clicks"), "page_sum_impressions": page_sums.get("impressions"),
        "query_hit_daily_cap": "true" if hit_cap else "false",
        "page_aggregation_type": aggregation or "",
    }


GSC_QUALITY_HEADER = ["date", "scope_id", "search_type", "total_clicks", "total_impressions",
                      "query_sum_clicks", "query_sum_impressions", "click_gap_ratio", "impression_gap_ratio",
                      "page_sum_clicks", "page_sum_impressions", "query_hit_daily_cap", "page_aggregation_type"]


def ga4_other_stats(rows, dim_names, metric_name):
    """rows：已正規化的 dict。回傳 (other 列數, other 占該指標的比例或 None)。"""
    other_rows = 0
    other_sum = 0.0
    total = 0.0
    for r in rows:
        try:
            v = float(r.get(metric_name) or 0)
        except ValueError:
            v = 0.0
        total += v
        if any(r.get(d) == "(other)" for d in dim_names):
            other_rows += 1
            other_sum += v
    share = round(other_sum / total, 6) if total > 0 else None
    return other_rows, share


def median(values):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    n = len(vals)
    mid = n // 2
    return vals[mid] if n % 2 else (vals[mid - 1] + vals[mid]) / 2
