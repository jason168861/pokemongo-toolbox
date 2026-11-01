"""錯誤分類。

分類函式 classify() 是純函式：輸入 HTTP 狀態碼、reason 清單、訊息，輸出類別。
from_exception() 把各種函式庫的例外轉成 ApiError / AuthRequired。
"""
import json
import socket

# 類別
AUTH = "auth"
PERMISSION = "permission"
QUOTA_RATE = "quota_rate"
QUOTA_DAILY = "quota_daily"
TRANSIENT = "transient"
BAD_REQUEST = "bad_request"
NOT_FOUND = "not_found"
UNKNOWN = "unknown"

RETRYABLE = {QUOTA_RATE, TRANSIENT}
BREAKER_COUNTED = {QUOTA_RATE, TRANSIENT}

_DAILY_REASONS = {"dailylimitexceeded", "quotaexceeded", "dailylimitexceededunreg"}
_RATE_REASONS = {"ratelimitexceeded", "userratelimitexceeded", "ratelimitexceededunreg",
                 "resource_exhausted", "rate_limit_exceeded"}


class CollectorError(Exception):
    """所有自訂錯誤的基底。"""
    exit_code = 1


class ConfigError(CollectorError):
    """設定或路徑檢查失敗（exit code 2）。"""
    exit_code = 2


class AuthRequired(CollectorError):
    """需要使用者重新授權（exit code 3）。不得自動開瀏覽器。"""
    exit_code = 3

    def __init__(self, message="授權失效或缺少 token，請使用者重新執行：python scripts/google_api/collect.py auth"):
        super().__init__(message)


class StopRun(CollectorError):
    """配額、斷路器、--max-requests／--max-minutes 造成的停止，可續跑（exit code 4）。"""
    exit_code = 4


class LockBusy(CollectorError):
    exit_code = 5


class QueryInDimension(CollectorError):
    """頁面維度出現 query string、分享 id 或疑似訓練家代碼。資料集要停止，不收下資料。

    message 只描述「哪個維度、命中哪條規則、幾列」，不包含命中的值。
    hits：{規則名稱: 列數}，給 manifest 的 known_limits 用。
    """

    def __init__(self, message, hits=None, dimension=None):
        super().__init__(message)
        self.hits = dict(hits or {})
        self.dimension = dimension

    def limit_note(self):
        rules = "、".join(f"{k}（{v} 列）" for k, v in sorted(self.hits.items())) or "未知規則"
        return (f"頁面維度守門停止：{self.dimension or '頁面維度'} 命中 {rules}。"
                "digits12 可能是含長數字的合法網址（例如追蹤參數）造成的誤報，請人工判斷；raw 保留在資料目錄。")


class DuplicateKeyError(CollectorError):
    pass


class ApiError(CollectorError):
    def __init__(self, category, status=None, reasons=None, message="", retry_after=None):
        super().__init__(message or category)
        self.category = category
        self.status = status
        self.reasons = list(reasons or [])
        self.message = message
        self.retry_after = retry_after

    def __str__(self):
        return f"[{self.category}] HTTP {self.status} {','.join(self.reasons)} {self.message}".strip()


def classify(status, reasons=(), message=""):
    reasons_l = {str(r).lower() for r in reasons if r}
    msg_l = (message or "").lower()
    if status == 401:
        return AUTH
    if status in (403, 429):
        if reasons_l & _DAILY_REASONS or "per day" in msg_l or "perday" in msg_l:
            return QUOTA_DAILY
        if status == 429 or reasons_l & _RATE_REASONS:
            return QUOTA_RATE
        return PERMISSION
    if status == 400:
        return BAD_REQUEST
    if status == 404:
        return NOT_FOUND
    if status is not None and 500 <= status <= 599:
        return TRANSIENT
    return UNKNOWN


def _reasons_from_content(content):
    """從錯誤回應的 JSON 取出 reason／status。非 JSON（例如 HTML 錯誤頁）回傳空清單。"""
    if isinstance(content, bytes):
        try:
            content = content.decode("utf-8", "replace")
        except Exception:
            return [], ""
    if not isinstance(content, str) or not content.strip():
        return [], ""
    try:
        data = json.loads(content)
    except ValueError:
        return [], content[:500]
    err = data.get("error") if isinstance(data, dict) else None
    if not isinstance(err, dict):
        return [], ""
    reasons = []
    for e in err.get("errors") or []:
        if isinstance(e, dict) and e.get("reason"):
            reasons.append(e["reason"])
    for d in err.get("details") or []:
        if isinstance(d, dict) and d.get("reason"):
            reasons.append(d["reason"])
    if err.get("status"):
        reasons.append(err["status"])
    return reasons, str(err.get("message") or "")


def _retry_after(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def from_exception(exc):
    """把例外轉成 ApiError 或 AuthRequired。無法辨識的例外原樣回傳。"""
    if isinstance(exc, (ApiError, AuthRequired, CollectorError)):
        return exc

    # google-auth：refresh 失敗（含 invalid_grant）
    try:
        from google.auth.exceptions import RefreshError  # type: ignore
        if isinstance(exc, RefreshError):
            return AuthRequired()
    except ImportError:
        pass

    # googleapiclient HttpError
    try:
        from googleapiclient.errors import HttpError  # type: ignore
        if isinstance(exc, HttpError):
            status = getattr(getattr(exc, "resp", None), "status", None)
            try:
                status = int(status) if status is not None else None
            except (TypeError, ValueError):
                status = None
            reasons, message = _reasons_from_content(getattr(exc, "content", b""))
            for d in getattr(exc, "error_details", None) or []:
                if isinstance(d, dict) and d.get("reason"):
                    reasons.append(d["reason"])
            resp = getattr(exc, "resp", None)
            ra = None
            if resp is not None and hasattr(resp, "get"):
                ra = _retry_after(resp.get("retry-after"))
            cat = classify(status, reasons, message)
            if cat == AUTH:
                return AuthRequired()
            return ApiError(cat, status, reasons, message, ra)
    except ImportError:
        pass

    # urllib（PSI、CrUX）
    import urllib.error
    if isinstance(exc, urllib.error.HTTPError):
        body = getattr(exc, "_collector_body", None)
        reasons, message = _reasons_from_content(body or b"")
        ra = _retry_after(exc.headers.get("Retry-After") if exc.headers else None)
        cat = classify(exc.code, reasons, message)
        if cat == AUTH:
            return AuthRequired()
        return ApiError(cat, exc.code, reasons, message, ra)
    if isinstance(exc, urllib.error.URLError):
        return ApiError(TRANSIENT, None, [], "連線錯誤")

    if isinstance(exc, (socket.timeout, TimeoutError, ConnectionError)):
        return ApiError(TRANSIENT, None, [], type(exc).__name__)

    try:
        import httplib2  # type: ignore
        if isinstance(exc, httplib2.ServerNotFoundError):
            return ApiError(TRANSIENT, None, [], "ServerNotFoundError")
        if isinstance(exc, httplib2.HttpLib2Error):
            return ApiError(TRANSIENT, None, [], type(exc).__name__)
    except ImportError:
        pass

    return exc
