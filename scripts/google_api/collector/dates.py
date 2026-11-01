"""日期工具：切段、對半切、重抓視窗、回補下限。全部是純函式。

日期一律用 datetime.date；對外（API、CSV、unit id）用 ISO 字串 YYYY-MM-DD。
「今天」以 UTC 計算，終點是 UTC 今天 − 1 天（設計 §3.4）。
"""
import datetime as _dt


def to_date(value):
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    s = str(value).strip()
    if len(s) == 8 and s.isdigit():          # GA4 的 YYYYMMDD
        return _dt.date(int(s[:4]), int(s[4:6]), int(s[6:]))
    return _dt.date.fromisoformat(s[:10])


def iso(d):
    return to_date(d).isoformat()


def utc_today(now=None):
    now = now or _dt.datetime.now(_dt.timezone.utc)
    return now.astimezone(_dt.timezone.utc).date()


def default_end(now=None):
    return utc_today(now) - _dt.timedelta(days=1)


def days_between(start, end):
    start, end = to_date(start), to_date(end)
    out = []
    d = start
    while d <= end:
        out.append(d)
        d += _dt.timedelta(days=1)
    return out


def month_start(d):
    d = to_date(d)
    return d.replace(day=1)


def month_end(d):
    d = to_date(d)
    nxt = (d.replace(day=28) + _dt.timedelta(days=4)).replace(day=1)
    return nxt - _dt.timedelta(days=1)


def add_months(d, n):
    """加減月份；日期超過該月天數時取月底（例如 3/31 − 1 個月 = 2/28 或 2/29）。"""
    d = to_date(d)
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    last = month_end(_dt.date(y, m, 1)).day
    return _dt.date(y, m, min(d.day, last))


def add_years(d, n):
    return add_months(d, 12 * n)


def month_chunks(start, end):
    start, end = to_date(start), to_date(end)
    if start > end:
        return []
    out = []
    s = start
    while s <= end:
        e = min(month_end(s), end)
        out.append((s, e))
        s = e + _dt.timedelta(days=1)
    return out


def year_chunks(start, end):
    start, end = to_date(start), to_date(end)
    if start > end:
        return []
    out = []
    s = start
    while s <= end:
        e = min(_dt.date(s.year, 12, 31), end)
        out.append((s, e))
        s = e + _dt.timedelta(days=1)
    return out


def day_units(start, end):
    return [(d, d) for d in days_between(start, end)]


def chunks(kind, start, end):
    if kind == "day":
        return day_units(start, end)
    if kind == "month":
        return month_chunks(start, end)
    if kind == "year":
        return year_chunks(start, end)
    if kind == "range":
        start, end = to_date(start), to_date(end)
        return [(start, end)] if start <= end else []
    raise ValueError(f"未知的切段方式：{kind}")


def split_half(start, end):
    """對半切；單日回傳 None。"""
    start, end = to_date(start), to_date(end)
    if start >= end:
        return None
    n = (end - start).days
    mid = start + _dt.timedelta(days=n // 2)
    return (start, mid), (mid + _dt.timedelta(days=1), end)


def month_key(d):
    return to_date(d).strftime("%Y-%m")


def refetch_start(source, end, cfg):
    """各來源的重抓視窗起點（設計 §5.2）。cfg 是 settings['refetch']。"""
    end = to_date(end)
    if source == "adsense":
        min_days = int(cfg.get("adsense_min_days", 35))
        prev_month_start = month_start(add_months(month_start(end), -1))
        by_days = end - _dt.timedelta(days=min_days - 1)
        return min(prev_month_start, by_days)
    days = int(cfg.get(source + "_days", 10 if source == "gsc" else 7))
    return end - _dt.timedelta(days=max(1, days) - 1)


def backfill_floor(source, end, created=None):
    """回補下限：GSC 16 個月；AdSense 3 年且不早於帳戶建立日；GA4 不早於 property 建立日與 2015-08-14。"""
    end = to_date(end)
    if source == "gsc":
        return add_months(end, -16) + _dt.timedelta(days=1)
    if source == "adsense":
        floor = add_years(end, -3) + _dt.timedelta(days=1)
        if created:
            floor = max(floor, to_date(created))
        return floor
    if source == "ga4":
        floor = _dt.date(2015, 8, 14)
        if created:
            floor = max(floor, to_date(created))
        return floor
    raise ValueError(source)


def provisional_from(source, end, cfg, first_incomplete=None):
    """從哪一天開始算暫定資料（is_final=false）。"""
    end = to_date(end)
    if source == "gsc":
        min_days = int(cfg.get("gsc_provisional_min_days", 4))
        by_days = end - _dt.timedelta(days=min_days - 1)
        if first_incomplete:
            return min(to_date(first_incomplete), by_days)
        return by_days
    if source == "ga4":
        days = int(cfg.get("ga4_provisional_days", 3))
        return end - _dt.timedelta(days=days - 1)
    if source == "adsense":
        return month_start(add_months(month_start(end), -1))
    raise ValueError(source)
