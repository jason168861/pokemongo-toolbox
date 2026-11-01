"""命令列介面（設計 §8）。

exit code：0 成功／1 部分失敗／2 設定或路徑檢查失敗／3 需要重新授權／4 配額、斷路器或上限停止（可續跑）／5 執行鎖被占用
"""
import argparse
import json
import os
import traceback
from pathlib import Path

from . import errors as E
from .dates import default_end, to_date
from .engine import Context, FOLDERS, SourceStop
from .errors import AuthRequired, CollectorError, ConfigError, LockBusy, StopRun
from .paths import (check_cred_dir, check_data_dir, default_git_runner, describe_ignore_rules,
                    resolve_cred_dir, resolve_data_dir)
from .ratelimit import RateLimiter
from .runlog import RunLock, RunLog, configure_logging, emit_console, error_text
from .settings import load_settings, load_url_list
from .transport import Budget, Transport

SCRIPT_DIR = Path(__file__).resolve().parent.parent
OAUTH_SOURCES = ("adsense", "gsc", "ga4")
ALL_SOURCES = OAUTH_SOURCES
FAILURE_EVENTS = ("unit_failed", "probe_failed", "psi_failed", "crux_failed")


class NullRunLog(RunLog):
    """--dry-run 用：不寫任何檔案。"""

    def __init__(self, command):
        self.path = None
        self.command = command
        self.run_id = "dry-run"
        self.counts = {}

    def emit_event(self, event, level="info", **fields):
        self.counts[event] = self.counts.get(event, 0) + 1
        return {}


class CountingRunLog(RunLog):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.counts = {}

    def emit_event(self, event, level="info", **fields):
        self.counts[event] = self.counts.get(event, 0) + 1
        return super().emit_event(event, level=level, **fields)


# ------------------------------------------------------------------ 參數

def build_parser():
    p = argparse.ArgumentParser(prog="collect.py", description="PogoKit Google API Data Collector（唯讀）")
    p.add_argument("--data-dir")
    p.add_argument("--cred-dir")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--max-requests", type=int)
    p.add_argument("--max-minutes", type=float)
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--force-unlock", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("auth", help="使用者親自執行：開瀏覽器授權（三個 readonly scope）")
    c = sub.add_parser("check", help="檢查設定、路徑、憑證檔與 token（不印內容）")
    c.add_argument("--online", action="store_true")
    c.add_argument("--scan-raw-for-key", action="store_true",
                   help="掃描資料目錄所有檔案（含 .gz）是否含本 Collector 的 API key／client_secret；只輸出檔案數")

    def src_args(sp, multi=True):
        sp.add_argument("--source", help="adsense,gsc,ga4（逗號分隔，預設全部）" if multi else "")
        sp.add_argument("--dataset", help="資料集名稱（逗號分隔）")
        sp.add_argument("--gsc-site")
        sp.add_argument("--ga4-property")
        sp.add_argument("--gsc-qpm", type=int)

    for name in ("discover", "probe", "snapshot"):
        src_args(sub.add_parser(name))
    for name in ("backfill", "update", "refetch"):
        sp = sub.add_parser(name)
        src_args(sp)
        sp.add_argument("--start")
        sp.add_argument("--end")
        if name == "update":
            sp.add_argument("--refetch-days", type=int)
        if name == "refetch":
            sp.add_argument("--accept-empty", action="store_true",
                            help="允許「之前有資料、這次 0 列」時清除舊資料")
    s = sub.add_parser("status")
    s.add_argument("--json", action="store_true")
    s.add_argument("--rebuild", action="store_true")
    cp_ = sub.add_parser("compact")
    cp_.add_argument("--source", required=True)
    cp_.add_argument("--dataset", required=True)
    ps = sub.add_parser("psi")
    ps.add_argument("--urls")
    ps.add_argument("--strategy")
    ps.add_argument("--runs", type=int)
    ps.add_argument("--max-tests", type=int)
    cr = sub.add_parser("crux")
    cr.add_argument("--urls")
    cr.add_argument("--no-history", action="store_true")
    iu = sub.add_parser("inspect-urls")
    iu.add_argument("--urls", required=True)
    iu.add_argument("--max", type=int)
    return p


def _split(value):
    return [v.strip() for v in value.split(",") if v.strip()] if value else None


def settings_overrides(args):
    ov = {"gsc": {}, "ga4": {}, "psi": {}, "refetch": {}, "rate_per_minute": {}}
    if getattr(args, "gsc_site", None):
        ov["gsc"]["site"] = args.gsc_site
    if getattr(args, "ga4_property", None):
        ov["ga4"]["property"] = args.ga4_property
    if getattr(args, "gsc_qpm", None):
        ov["rate_per_minute"]["gsc"] = args.gsc_qpm
    if getattr(args, "refetch_days", None):
        srcs = _split(getattr(args, "source", None))
        if not srcs or len(srcs) != 1:
            raise ConfigError("--refetch-days 必須搭配單一的 --source。")
        key = "adsense_min_days" if srcs[0] == "adsense" else f"{srcs[0]}_days"
        ov["refetch"][key] = args.refetch_days
    for k in ("runs", "max_tests"):
        if getattr(args, k, None):
            ov["psi"][k] = getattr(args, k)
    if getattr(args, "strategy", None):
        ov["psi"]["strategies"] = _split(args.strategy)
    return ov


# ------------------------------------------------------------------ 建立執行環境

def make_service_factory(cred_dir, timeout):
    state = {"creds": None}

    def factory(api, version):
        if state["creds"] is None:
            from .credentials import load_oauth_credentials
            state["creds"] = load_oauth_credentials(cred_dir)
        import google_auth_httplib2  # type: ignore
        import httplib2  # type: ignore
        from googleapiclient.discovery import build  # type: ignore
        http = google_auth_httplib2.AuthorizedHttp(state["creds"], http=httplib2.Http(timeout=timeout))
        return build(api, version, http=http, cache_discovery=False, static_discovery=True)
    return factory


def make_transports(settings, budget, runlog):
    rates = settings.get("rate_per_minute") or {}
    retry = settings.get("retry") or {}
    out = {}
    for src in ("adsense", "gsc", "ga4", "psi", "crux"):
        def on_retry(err, attempt, delay, src=src):
            runlog.emit_event("retry", "warn", source=src, error_class=err.category,
                              http_status=err.status, attempt=attempt, delay_s=round(delay, 1))
        out[src] = Transport(src, RateLimiter(rates.get(src, 30)), budget,
                             max_retries=retry.get("max_retries", 5),
                             max_total_seconds=retry.get("max_total_seconds", 300), on_retry=on_retry)
    return out


def source_objects(ctx, names):
    from .sources.adsense import AdSenseSource
    from .sources.ga4 import Ga4Source
    from .sources.gsc import GscSource
    classes = {"adsense": AdSenseSource, "gsc": GscSource, "ga4": Ga4Source}
    return [(n, classes[n](ctx)) for n in names]


def all_dataset_defs(settings):
    from .sources import adsense, ga4, gsc
    out = {}
    for ds in adsense.DATASETS + ga4.DATASETS:
        out[ds.name] = ds
    for st in (settings.get("gsc") or {}).get("search_types") or []:
        for ds in gsc.datasets_for_type(st, settings):
            out[ds.name] = ds
    return out


# ------------------------------------------------------------------ 指令

def cmd_auth(args):
    from .credentials import run_auth_flow
    cred_dir = resolve_cred_dir(args.cred_dir)
    try:
        data_dir = resolve_data_dir(args.data_dir, os.environ, SCRIPT_DIR)
    except ConfigError:
        data_dir = None
    check_cred_dir(cred_dir, data_dir)
    emit_console("即將開啟瀏覽器進行授權（只申請 adsense.readonly、webmasters.readonly、analytics.readonly）。")
    run_auth_flow(cred_dir)
    emit_console("授權完成，token 已存到憑證資料夾。")
    return 0


def scan_files_for_secrets(data_dir, secrets):
    """掃描 data_dir 底下所有檔案（.gz 先解壓）是否含有各祕密值。

    secrets：{標籤: 值}。回傳 ({標籤: 含有該值的檔案數}, 掃描的檔案數, 無法讀取的檔案數)。
    只回傳數量；不回傳、不輸出任何值或片段。也比對 URL 編碼後的形式（key 出現在網址參數時）。
    """
    import gzip
    from urllib.parse import quote
    needles = {}
    for label, value in secrets.items():
        if not value:
            continue
        forms = {value.encode("utf-8"), quote(value, safe="").encode("utf-8")}
        needles[label] = forms
    counts = {label: 0 for label in needles}
    scanned = unreadable = 0
    data_dir = Path(data_dir)
    if not data_dir.exists():
        return counts, 0, 0
    for p in data_dir.rglob("*"):
        if not p.is_file():
            continue
        try:
            if p.name.endswith(".gz"):
                with gzip.open(p, "rb") as f:
                    blob = f.read()
            else:
                blob = p.read_bytes()
        except (OSError, EOFError):
            unreadable += 1
            continue
        scanned += 1
        for label, forms in needles.items():
            if any(form in blob for form in forms):
                counts[label] += 1
    return counts, scanned, unreadable


def cmd_scan_raw_for_key(data_dir, cred_dir):
    """F2：確認資料目錄裡出現的 AIza… 字串不是本 Collector 自己的 key。只輸出數量。"""
    from .credentials import API_KEY_FILE, CLIENT_SECRET_FILE
    secrets = {}
    key_path = Path(cred_dir) / API_KEY_FILE
    if key_path.exists():
        secrets["api_key"] = key_path.read_text(encoding="utf-8").strip()
    sec_path = Path(cred_dir) / CLIENT_SECRET_FILE
    if sec_path.exists():
        try:
            with open(sec_path, "r", encoding="utf-8") as f:
                doc = json.load(f)
            for section in ("installed", "web"):
                if isinstance(doc.get(section), dict) and doc[section].get("client_secret"):
                    secrets["client_secret"] = doc[section]["client_secret"]
        except (OSError, ValueError):
            emit_console("client_secret.json 無法解析，略過。", err=True)
    from .redact import register_secret
    for v in secrets.values():
        register_secret(v)          # 萬一有任何輸出，也一定被遮蔽
    counts, scanned, unreadable = scan_files_for_secrets(data_dir, secrets)
    emit_console(f"掃描資料目錄的檔案數：{scanned}（無法讀取 {unreadable}）")
    labels = {"api_key": "含有本 Collector API key 的檔案數", "client_secret": "含有本 Collector client_secret 的檔案數"}
    for label, text in labels.items():
        if label in counts:
            emit_console(f"{text}：{counts[label]}")
        else:
            emit_console(f"{text}：（找不到對應的憑證檔，未掃描）")
    return 1 if any(counts.values()) else 0


def count_partials(data_dir):
    """raw 寫入中斷時留下的 .partial 檔數量（check 指令顯示用）。"""
    data_dir = Path(data_dir)
    if not data_dir.exists():
        return 0
    return sum(1 for p in data_dir.rglob("*.partial") if p.is_file())


def cmd_check(args, settings):
    from .credentials import API_KEY_FILE, CLIENT_SECRET_FILE, TOKEN_FILE, check_scopes
    data_dir = resolve_data_dir(args.data_dir, os.environ, SCRIPT_DIR)
    emit_console(f"資料目錄：{data_dir}")
    info = check_data_dir(data_dir, create=False)
    emit_console("  git 忽略檢查：通過" + ("（不在任何 git 工作樹內）" if info["outside_repo"] else ""))
    if data_dir.exists():
        rules = describe_ignore_rules(data_dir)
        if not rules.get("outside_repo"):
            emit_console(f"  根目錄規則命中：{'是' if rules['root_rule_hit'] else '否'}"
                         f"（{rules.get('root_rule_source') or '—'}）")
            emit_console(f"  內層 .gitignore 正確：{'是' if rules['inner_rule_hit'] else '否'}")
            if not rules["root_rule_hit"]:
                emit_console("  警告：根目錄 .gitignore 沒有忽略資料目錄，目前只靠內層 .gitignore 保護。", err=True)
        partials = count_partials(data_dir)
        emit_console(f"  未完成的 raw 暫存檔（*.partial）：{partials} 個"
                     + ("（寫入中斷留下的，可人工檢查後刪除）" if partials else ""))
    cred_dir = resolve_cred_dir(args.cred_dir)
    check_cred_dir(cred_dir, data_dir)
    if getattr(args, "scan_raw_for_key", False):
        return cmd_scan_raw_for_key(data_dir, cred_dir)
    emit_console(f"憑證資料夾：{cred_dir}")
    for name in (CLIENT_SECRET_FILE, API_KEY_FILE, TOKEN_FILE):
        emit_console(f"  {name}：{'存在' if (cred_dir / name).exists() else '不存在'}")
    token_path = cred_dir / TOKEN_FILE
    if token_path.exists():
        try:
            with open(token_path, "r", encoding="utf-8") as f:
                tok = json.load(f)
            check_scopes(tok.get("scopes"))
            emit_console("  token scope：恰好三個 readonly scope（通過）")
            emit_console(f"  refresh_token：{'有' if tok.get('refresh_token') else '沒有（需要重新 auth）'}")
        except AuthRequired as exc:
            emit_console(f"  token scope：不通過（{exc}）", err=True)
        except ValueError:
            emit_console("  token.json 無法解析", err=True)
    try:
        from importlib.metadata import version
        for pkg in ("google-api-python-client", "google-auth", "google-auth-oauthlib", "google-auth-httplib2", "httplib2"):
            try:
                emit_console(f"套件 {pkg}：{version(pkg)}")
            except Exception:
                emit_console(f"套件 {pkg}：未安裝", err=True)
    except ImportError:
        pass
    try:
        from googleapiclient import discovery_cache  # type: ignore
        for api, ver in (("adsense", "v2"), ("searchconsole", "v1"), ("analyticsdata", "v1beta"),
                         ("analyticsadmin", "v1beta")):
            doc = discovery_cache.get_static_doc(api, ver)
            emit_console(f"內建 discovery 文件 {api} {ver}：{'有' if doc else '沒有（需改用 static_discovery=False）'}")
    except Exception:
        emit_console("無法檢查內建 discovery 文件（googleapiclient 未安裝？）", err=True)
    if args.online:
        factory = make_service_factory(cred_dir, (settings.get("timeout_seconds") or {}).get("google_api", 60))
        ok = True
        for label, fn in (("AdSense accounts.list", lambda: factory("adsense", "v2").accounts().list(pageSize=1).execute()),
                          ("Search Console sites.list", lambda: factory("searchconsole", "v1").sites().list().execute()),
                          ("GA4 accountSummaries.list", lambda: factory("analyticsadmin", "v1beta").accountSummaries().list(pageSize=1).execute())):
            try:
                fn()
                emit_console(f"線上檢查 {label}：通過")
            except Exception as exc:  # noqa: BLE001
                ok = False
                err = E.from_exception(exc)
                if isinstance(err, AuthRequired):
                    raise err
                emit_console(f"線上檢查 {label}：失敗（{error_text(exc)}）", err=True)
        emit_console("提醒：請在 Google Cloud Console 確認 (1) API key 只限 PageSpeed Insights API 與 Chrome UX Report API；"
                     "(2) 專案沒有綁定帳單。程式無法用現有權限查詢這兩點。")
        return 0 if ok else 1
    return 0


def cmd_status(args, data_dir, settings):
    from .checkpoint import Checkpoints
    from .manifest import Manifest
    from .storage import DatasetFiles
    manifest = Manifest(data_dir / "manifest.json")
    if args.rebuild:
        cps = Checkpoints(data_dir / "state" / "checkpoints.json")
        defs = all_dataset_defs(settings)
        keys = set()
        for uid in cps.units:
            parts = uid.split("/", 2)
            if len(parts) < 3:
                continue
            src, ds_name, rest = parts
            scope = rest.rsplit("/", 1)[0]
            keys.add((src, ds_name, scope))
        for src, ds_name, scope in sorted(keys):
            ds = defs.get(ds_name)
            files = DatasetFiles(data_dir / FOLDERS[src], ds_name, ds.layout, ds.header, ds.key_fields) if ds else None
            manifest.update_dataset(f"{src}/{ds_name}/{scope}", checkpoints=cps, files=files, scope_id=scope)
        emit_console(f"已從 checkpoints 與 CSV 重建 manifest（{len(keys)} 個資料集）。")
    if args.json:
        emit_console(json.dumps(manifest.data, ensure_ascii=False, indent=2))
        return 0
    for key, rec in sorted(manifest.data.get("datasets", {}).items()):
        cov = rec.get("coverage") or {}
        units = rec.get("units") or {}
        emit_console(f"{key}  [{rec.get('status')}]  {cov.get('first_date_with_rows') or '—'} ~ "
                     f"{cov.get('last_date_with_rows') or '—'}  列數 {rec.get('row_count', '—')}  "
                     f"失敗 {units.get('failed', 0)}  regression {units.get('regression_to_empty', 0)}"
                     + (f"  停止原因：{rec['stopped_reason']}" if rec.get("stopped_reason") else ""))
    return 0


def cmd_compact(args, data_dir, settings):
    from .storage import DatasetFiles
    src = args.source
    if src not in FOLDERS:
        raise ConfigError(f"未知的來源：{src}")
    ds = all_dataset_defs(settings).get(args.dataset)
    if not ds:
        raise ConfigError(f"未知的資料集：{args.dataset}")
    files = DatasetFiles(data_dir / FOLDERS[src], ds.name, ds.layout, ds.header, ds.key_fields)
    out = data_dir / FOLDERS[src] / "compact" / f"{ds.name}.csv"
    result = files.compact(out)
    emit_console(f"compact 完成：{out}（{result}）")
    return 0


def run_sources(ctx, args, mode):
    names = _split(getattr(args, "source", None)) or list(ALL_SOURCES)
    for n in names:
        if n not in OAUTH_SOURCES:
            raise ConfigError(f"未知的來源：{n}（可用：{', '.join(OAUTH_SOURCES)}）")
    datasets = set(_split(getattr(args, "dataset", None)) or []) or None
    stopped = {}
    for name, src in source_objects(ctx, names):
        try:
            if mode == "discover":
                src.discover(force=True)
            elif mode == "probe":
                inv = src.discover()
                _probe_all(ctx, name, src, inv, datasets)
            elif mode == "snapshot":
                # 只有 AdSense（清單、警告、政策問題）與 GSC（sitemaps）有快照；其他來源略過，不中斷整個指令
                if not callable(getattr(src, "snapshot", None)):
                    ctx.event("snapshot_skipped", source=name, reason="這個來源沒有快照")
                    emit_console(f"[{name}] 沒有快照，略過。")
                    continue
                src.snapshot()
            else:
                src.run(mode, start=getattr(args, "start", None), end=getattr(args, "end", None), datasets=datasets)
                if mode == "update" and callable(getattr(src, "snapshot", None)) and not ctx.dry_run:
                    src.snapshot()
        except SourceStop as exc:
            stopped[name] = str(exc)
            ctx.event("source_stopped", "error", source=name, message=str(exc))
            emit_console(f"[{name}] {exc}", err=True)
    return stopped


def _probe_all(ctx, name, src, inv, datasets):
    """probe 指令：強制重新試查（忽略 probe.json 既有結果）。"""
    from .dates import backfill_floor
    from .manifest import dataset_key
    if ctx.dry_run:
        raise ConfigError("probe 會發出請求，不能搭配 --dry-run。")
    if name == "gsc":
        for site in src.select_sites(inv):
            for st in (ctx.settings.get("gsc") or {}).get("search_types") or []:
                rec = src.type_probe(site, st, backfill_floor("gsc", ctx.end), ctx.end)
                emit_console(f"[gsc] {st}: {rec.get('status')}")
        return
    if name == "adsense":
        from .sources.adsense import DATASETS
        scopes = [a["scope_id"] for a in inv.get("accounts", [])]
    else:
        from .sources.ga4 import DATASETS
        scopes = [p["scope_id"] for p in src.select_properties(inv)]
    for scope in scopes:
        for ds in DATASETS:
            if datasets and ds.name not in datasets:
                continue
            rec = _force_probe(src, scope, ds, dataset_key(name, ds.name, scope))
            if rec:
                emit_console(f"[{name}] {ds.name}: {rec.get('status')}")


def _force_probe(src, scope, ds, key):
    from .sources import probe_dataset
    original = src.probe
    src.probe = lambda s, d: original(s, d, force=True)
    try:
        return probe_dataset(src, scope, ds, key)
    finally:
        src.probe = original


# ------------------------------------------------------------------ main

def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose, debug=args.debug)
    lock = None
    runlog = None
    code = 0
    try:
        if args.cmd == "auth":
            return cmd_auth(args)
        settings = load_settings(settings_overrides(args))
        if args.cmd == "check":
            return cmd_check(args, settings)

        data_dir = resolve_data_dir(args.data_dir, os.environ, SCRIPT_DIR)
        check_data_dir(data_dir, create=not args.dry_run)
        cred_dir = resolve_cred_dir(args.cred_dir)
        check_cred_dir(cred_dir, data_dir)
        if not args.dry_run:
            from .datadoc import DATA_README
            from .storage import write_if_changed
            write_if_changed(data_dir / "README.md", DATA_README.encode("utf-8"))

        if args.cmd == "status":
            return cmd_status(args, data_dir, settings)
        if args.cmd == "compact":
            return cmd_compact(args, data_dir, settings)

        if args.dry_run:
            runlog = NullRunLog(args.cmd)
        else:
            runlog = CountingRunLog(str(data_dir / "collection_log.jsonl"), args.cmd)
            lock = RunLock(str(data_dir / "state" / "run.lock"))
            lock.acquire(args.cmd, force=args.force_unlock)
            import sys
            runlog.emit_event("run_start", argv=list(argv if argv is not None else sys.argv[1:]))

        budget = Budget(args.max_requests, args.max_minutes)
        transports = make_transports(settings, budget, runlog)
        end = to_date(args.end) if getattr(args, "end", None) else default_end()
        timeout = (settings.get("timeout_seconds") or {}).get("google_api", 60)
        ctx = Context(data_dir=data_dir, settings=settings, runlog=runlog, end=end, budget=budget,
                      transports=transports, service_factory=make_service_factory(cred_dir, timeout),
                      dry_run=args.dry_run, accept_empty=getattr(args, "accept_empty", False))

        stopped = {}
        if args.cmd in ("discover", "probe", "snapshot", "backfill", "update", "refetch"):
            if args.cmd == "refetch" and not (args.start and args.end and args.source and args.dataset):
                raise ConfigError("refetch 需要 --source、--dataset、--start、--end。")
            stopped = run_sources(ctx, args, args.cmd)
        elif args.cmd in ("psi", "crux"):
            from .credentials import load_api_key
            api_key = None if args.dry_run else load_api_key(cred_dir)
            urls = load_url_list(args.urls)
            if args.cmd == "psi":
                from .sources.psi import run_psi
                pcfg = settings.get("psi") or {}
                run_psi(ctx, urls, strategies=pcfg.get("strategies"), runs=int(pcfg.get("runs", 1)),
                        max_tests=int(pcfg.get("max_tests", 60)), api_key=api_key,
                        key_mode=pcfg.get("key_mode", "header"), categories=pcfg.get("categories"))
            else:
                from .sources.crux import run_crux
                ccfg = settings.get("crux") or {}
                run_crux(ctx, urls, origin=ccfg.get("origin"), form_factors=ccfg.get("form_factors"),
                         history_periods=ccfg.get("history_periods", 40), api_key=api_key,
                         key_mode=ccfg.get("key_mode", "header"), with_history=not args.no_history)
        elif args.cmd == "inspect-urls":
            from .sources.gsc import GscSource
            urls = load_url_list(args.urls)
            n = GscSource(ctx).inspect_urls(urls, args.max or (settings.get("url_inspection") or {}).get("max", 50))
            emit_console(f"URL Inspection 完成：{n} 個網址。")

        if args.dry_run:
            total = sum(ctx.planned.values())
            for k, v in sorted(ctx.planned.items()):
                emit_console(f"[dry-run] {k}: {v} 個 unit／測試")
            emit_console(f"[dry-run] 合計約 {total} 次請求（不含分頁與截斷切分）；沒有發出任何請求。")
            return 0

        failures = sum(runlog.counts.get(e, 0) for e in FAILURE_EVENTS)
        if stopped:
            code = 4
        elif failures:
            code = 1
        emit_console(f"完成。請求數 {budget.requests}；失敗事件 {failures}；"
                     f"停止的來源 {', '.join(stopped) if stopped else '無'}。")
        return code
    except AuthRequired as exc:
        code = 3
        emit_console(str(exc), err=True)
        return code
    except LockBusy as exc:
        code = 5
        emit_console(str(exc), err=True)
        return code
    except ConfigError as exc:
        code = 2
        emit_console(f"設定或路徑檢查失敗：{exc}", err=True)
        return code
    except StopRun as exc:
        code = 4
        emit_console(str(exc), err=True)
        return code
    except CollectorError as exc:
        code = getattr(exc, "exit_code", 1)
        emit_console(error_text(exc), err=True)
        return code
    except KeyboardInterrupt:
        code = 4
        emit_console("已中斷；進度已保留，可以重新執行續跑。", err=True)
        return code
    except Exception as exc:  # noqa: BLE001
        code = 1
        emit_console(f"未預期的錯誤：{error_text(exc)}", err=True)
        if args.debug:
            emit_console(traceback.format_exc(), err=True)
        return code
    finally:
        if runlog is not None and not isinstance(runlog, NullRunLog):
            try:
                runlog.emit_event("run_end", exit_code=code, counts=dict(runlog.counts))
            except Exception:
                pass
        if lock is not None:
            lock.release()
