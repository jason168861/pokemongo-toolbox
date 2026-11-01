"""各資料來源。共用的小工具放這裡。"""
from ..runlog import utc_stamp

PROBE_FILE = "probe.json"
INVENTORY_FILE = "inventory.json"


def probe_get(ctx, key):
    return (ctx.read_state(PROBE_FILE, {}) or {}).get(key)


def probe_set(ctx, key, **fields):
    data = ctx.read_state(PROBE_FILE, {}) or {}
    rec = {"probed_at": utc_stamp()}
    rec.update(fields)
    data[key] = rec
    ctx.write_state(PROBE_FILE, data)
    return rec


def inventory_get(ctx, source):
    return (ctx.read_state(INVENTORY_FILE, {}) or {}).get(source)


def inventory_set(ctx, source, value):
    data = ctx.read_state(INVENTORY_FILE, {}) or {}
    value = dict(value)
    value["discovered_at"] = utc_stamp()
    data[source] = value
    ctx.write_state(INVENTORY_FILE, data)
    return value


def probe_dataset(src, scope_id, ds, key):
    """執行 src.probe(scope_id, ds) 並處理錯誤。

    回傳 probe 紀錄；資料集要跳過時回傳 None（已寫入 manifest 與 log）。
    每日配額或斷路器開啟時丟 SourceStop。
    """
    from .. import errors as E
    from ..engine import SourceStop
    from ..errors import ApiError, QueryInDimension
    from ..runlog import error_text
    ctx = src.ctx
    if ctx.dry_run:
        return probe_get(ctx, key) or {"status": "supported", "metrics": list(ds.metrics)}
    try:
        return src.probe(scope_id, ds)
    except QueryInDimension as exc:
        from ..engine import guard_extra
        ctx.event("probe_failed", "warn", source=src.key, dataset=ds.name, error_class="query_in_dimension",
                  message=error_text(exc), guard_hits=dict(exc.hits))
        ctx.manifest.update_dataset(key, checkpoints=ctx.checkpoints,
                                    stopped_reason="query_in_dimension：" + str(exc),
                                    extra=guard_extra(ctx, key, {"known_limits": list(ds.known_limits)}, exc))
        return None
    except ApiError as exc:
        ctx.event("probe_failed", "error", source=src.key, dataset=ds.name, error_class=exc.category,
                  http_status=exc.status, message=error_text(exc))
        if exc.category == E.QUOTA_DAILY:
            raise SourceStop(f"{src.key} 每日配額用完，已停止該來源。") from None
        src.breaker.record_failure(exc.category, exc.status)
        ctx.manifest.update_dataset(key, checkpoints=ctx.checkpoints,
                                    stopped_reason=f"probe 失敗（{exc.category}）")
        if src.breaker.open:
            raise SourceStop(f"{src.key} 連續失敗，斷路器開啟，已停止該來源。") from None
        return None


def paginate(transport, make_request, items_key, token_param="pageToken", token_field="nextPageToken",
             on_page=None, max_pages=1000):
    """處理 nextPageToken 的清單 API。make_request(token) 回傳 googleapiclient 的 request 物件。"""
    items = []
    token = None
    for page in range(max_pages):
        req = make_request(token)
        resp = transport.call(lambda: req.execute(num_retries=0))
        if on_page:
            on_page(page, resp)
        items.extend(resp.get(items_key) or [])
        token = resp.get(token_field)
        if not token:
            break
    return items


def flatten(obj, prefix=""):
    """把巢狀 dict 攤平成 a.b.c 欄位（快照 CSV 用）；list 轉成 JSON 字串。"""
    import json
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                out.update(flatten(v, key))
            elif isinstance(v, list):
                out[key] = json.dumps(v, ensure_ascii=False)
            else:
                out[key] = v
    return out


def write_snapshot(ctx, source, kind, items, raw_pages, api_name):
    """非時間序列的清單：每次存一份 raw 與一份 CSV（以抓取時間命名，不覆蓋）。"""
    from ..storage import raw_stamp, render_csv, write_if_changed
    stamp = raw_stamp()
    for i, resp in enumerate(raw_pages):
        ctx.save_raw(source, ["snapshots", kind], [kind, f"p{i}"],
                     {"api": api_name, "request": {"kind": kind}, "response": resp})
    rows = [flatten(it) for it in items]
    header = sorted({k for r in rows for k in r.keys()}) or ["_empty"]
    path = ctx.source_dir(source) / "snapshots" / kind / f"{stamp}.csv"
    write_if_changed(path, render_csv(header, rows))
    return path, len(rows)
