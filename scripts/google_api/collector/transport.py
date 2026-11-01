"""請求執行：限速、重試（指數退避＋jitter）、錯誤分類、整體預算（設計 §4）。"""
import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request

from . import errors as E
from .errors import ApiError, AuthRequired, ConfigError, StopRun

# API key 只能送到這兩個 API（設計 §3.5）
KEY_HOST_WHITELIST = (
    ("www.googleapis.com", "/pagespeedonline/"),
    ("pagespeedonline.googleapis.com", "/"),
    ("chromeuxreport.googleapis.com", "/"),
)


class Budget:
    """--max-requests／--max-minutes：到上限就在 unit 之間停下（StopRun，exit code 4）。"""

    def __init__(self, max_requests=None, max_minutes=None, clock=time.monotonic):
        self.max_requests = max_requests
        self.deadline = clock() + max_minutes * 60 if max_minutes else None
        self._clock = clock
        self.requests = 0

    def check(self):
        if self.max_requests is not None and self.requests >= self.max_requests:
            raise StopRun(f"已達 --max-requests {self.max_requests}，停止並保留進度。")
        if self.deadline is not None and self._clock() >= self.deadline:
            raise StopRun("已達 --max-minutes 時間上限，停止並保留進度。")

    def count(self):
        self.requests += 1


class Transport:
    def __init__(self, source, limiter, budget, *, max_retries=5, max_total_seconds=300,
                 sleep=time.sleep, rand=random.uniform, clock=time.monotonic, on_retry=None):
        self.source = source
        self.limiter = limiter
        self.budget = budget
        self.max_retries = max_retries
        self.max_total = max_total_seconds
        self._sleep = sleep
        self._rand = rand
        self._clock = clock
        self.on_retry = on_retry
        self.requests = 0

    def backoff(self, attempt, retry_after=None):
        delay = min(64.0, 2.0 ** attempt) * self._rand(0.5, 1.0)
        if retry_after:
            delay = max(delay, float(retry_after))
        return delay

    def call(self, fn):
        """fn() 執行一次請求並回傳結果。失敗時丟 ApiError／AuthRequired。"""
        attempt = 0
        start = self._clock()
        while True:
            self.budget.check()
            self.limiter.acquire()
            self.budget.count()
            self.requests += 1
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001 — 一律分類
                err = E.from_exception(exc)
                if isinstance(err, AuthRequired):
                    raise err from None
                if not isinstance(err, ApiError):
                    raise
                if err.category in E.RETRYABLE and attempt < self.max_retries:
                    delay = self.backoff(attempt, err.retry_after)
                    if self._clock() - start + delay > self.max_total:
                        raise err from None
                    if self.on_retry:
                        self.on_retry(err, attempt + 1, delay)
                    self._sleep(delay)
                    attempt += 1
                    continue
                raise err from None


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """遇到 3xx 一律拋錯、不跟隨：避免 X-Goog-Api-Key 被帶到其他主機。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ApiError(E.UNKNOWN, code, ["redirect"],
                       f"API 回應重新導向（HTTP {code}），為避免 API key 被帶到其他主機，拒絕跟隨。")


def no_redirect_opener():
    return urllib.request.build_opener(NoRedirectHandler)


def check_key_host(url):
    p = urllib.parse.urlparse(url)
    if p.scheme != "https":
        raise ConfigError("API key 只能用 https 傳送。")
    for host, path_prefix in KEY_HOST_WHITELIST:
        if p.hostname == host and p.path.startswith(path_prefix):
            return True
    raise ConfigError(f"拒絕把 API key 送到白名單以外的主機：{p.hostname}")


def http_json(method, url, *, api_key, key_mode="header", body=None, timeout=60, opener=None):
    """PSI／CrUX 用：送出請求並回傳 (status, json)。

    key_mode="header"：用 X-Goog-Api-Key（預設，網址不帶金鑰）。
    key_mode="query"：加 key= 參數（U7 若 header 不被接受才用；遮蔽器會處理網址中的 key=）。
    HTTPError 會讀出 body 存到 exc._collector_body，方便分類與（遮蔽後）記錄。
    """
    check_key_host(url)
    headers = {"Accept": "application/json"}
    if key_mode == "header":
        headers["X-Goog-Api-Key"] = api_key
    else:
        sep = "&" if "?" in url else "?"
        url = url + sep + urllib.parse.urlencode({"key": api_key})
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    # 不用 urllib.request.urlopen：預設會自動跟隨重新導向，可能把 key header 帶到別的主機
    open_fn = opener or no_redirect_opener().open
    try:
        with open_fn(req, timeout=timeout) as resp:
            raw = resp.read()
            status = getattr(resp, "status", 200)
    except urllib.error.HTTPError as exc:
        try:
            exc._collector_body = exc.read()
        except Exception:
            exc._collector_body = b""
        raise
    try:
        return status, json.loads(raw.decode("utf-8"))
    except ValueError:
        raise ApiError(E.TRANSIENT, status, [], "回應不是 JSON") from None
