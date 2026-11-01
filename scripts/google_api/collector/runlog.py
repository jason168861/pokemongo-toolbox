"""唯一的輸出出口。

其他模組不得直接 print、不得直接寫 log 檔或 manifest 的錯誤欄位，一律經過這裡：
- emit_console(msg)：終端機
- RunLog.emit_event(**fields)：collection_log.jsonl
- error_text(exc)：給 manifest、checkpoint、raw 錯誤欄位用的例外文字

另外 install_stream_guards() 會把 sys.stdout / sys.stderr 換成 RedactingStream，
並攔截 warnings 與 logging，連第三方函式庫直接輸出的文字也會被遮蔽。
"""
import datetime as _dt
import json
import logging
import os
import sys
import uuid
import warnings

from .redact import redact, redact_obj

# 第三方 logger：等級固定為 WARNING，--verbose / --debug 都不會調低
THIRD_PARTY_LOGGERS = ("googleapiclient", "googleapiclient.discovery", "googleapiclient.discovery_cache",
                       "google.auth", "google.auth.transport", "google_auth_oauthlib",
                       "google_auth_httplib2", "urllib3", "oauthlib", "requests_oauthlib", "httplib2")

_ERROR_TEXT_LIMIT = 2000
_BODY_LIMIT = 500


class RedactingStream:
    """包住 stdout / stderr：緩衝到換行才輸出，避免祕密值被切在兩次 write 之間。"""

    def __init__(self, stream):
        self._stream = stream
        self._buf = ""

    def write(self, s):
        if not isinstance(s, str):
            s = str(s)
        self._buf += s
        written = len(s)
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._stream.write(redact(line) + "\n")
        # 防止沒有換行的超長輸出一直累積
        if len(self._buf) > 65536:
            self._stream.write(redact(self._buf))
            self._buf = ""
        return written

    def flush(self):
        if self._buf:
            self._stream.write(redact(self._buf))
            self._buf = ""
        try:
            self._stream.flush()
        except Exception:
            pass

    @property
    def wrapped(self):
        return self._stream

    def __getattr__(self, name):
        return getattr(self._stream, name)


class _RedactFilter(logging.Filter):
    def filter(self, record):
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        record.msg = redact(msg)
        record.args = ()
        if record.exc_text:
            record.exc_text = redact(record.exc_text)
        return True


class _RedactFormatter(logging.Formatter):
    def format(self, record):
        return redact(super().format(record))


def _showwarning(message, category, filename, lineno, file=None, line=None):
    text = warnings.formatwarning(message, category, filename, lineno, line)
    target = file or sys.stderr
    try:
        target.write(redact(text))
    except Exception:
        pass


def install_stream_guards():
    """collect.py 啟動的第一件事。重複呼叫不會重複包裝。"""
    if not isinstance(sys.stdout, RedactingStream):
        sys.stdout = RedactingStream(sys.stdout)
    if not isinstance(sys.stderr, RedactingStream):
        sys.stderr = RedactingStream(sys.stderr)
    warnings.showwarning = _showwarning
    logging.captureWarnings(True)
    configure_logging(verbose=False, debug=False)


def configure_logging(verbose=False, debug=False):
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stderr)
    handler.addFilter(_RedactFilter())
    handler.setFormatter(_RedactFormatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(logging.WARNING)
    collector_logger = logging.getLogger("collector")
    collector_logger.setLevel(logging.DEBUG if (verbose or debug) else logging.INFO)
    pin_third_party()


def pin_third_party():
    """第三方 logger 固定 WARNING；httplib2 的 debug 輸出固定關閉。"""
    for name in THIRD_PARTY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    try:
        import httplib2  # type: ignore
        httplib2.debuglevel = 0
    except ImportError:
        pass


def emit_console(msg, err=False):
    stream = sys.stderr if err else sys.stdout
    stream.write(redact(str(msg)) + "\n")
    try:
        stream.flush()
    except Exception:
        pass


def _bytes_to_text(b):
    if b is None:
        return ""
    if isinstance(b, bytes):
        return b[:_BODY_LIMIT].decode("utf-8", "replace")
    return str(b)[:_BODY_LIMIT]


def error_text(exc):
    """例外 → 已遮蔽的文字。HttpError 的 uri、content 與 urllib 的 url、body 都會一起遮蔽。"""
    parts = [type(exc).__name__]
    try:
        parts.append(str(exc))
    except Exception:
        parts.append("<無法轉成文字>")
    uri = getattr(exc, "uri", None)
    if uri:
        parts.append(f"uri={uri}")
    content = getattr(exc, "content", None)
    if content:
        parts.append(f"content={_bytes_to_text(content)}")
    url = getattr(exc, "url", None) or getattr(exc, "filename", None)
    if isinstance(url, str) and url:
        parts.append(f"url={url}")
    body = getattr(exc, "_collector_body", None)
    if body:
        parts.append(f"body={_bytes_to_text(body)}")
    reason = getattr(exc, "reason", None)
    if reason is not None and not isinstance(reason, (int, float)):
        parts.append(f"reason={reason}")
    text = " | ".join(p for p in parts if p)
    return redact(text)[:_ERROR_TEXT_LIMIT]


def utc_now():
    return _dt.datetime.now(_dt.timezone.utc)


def utc_stamp(dt=None):
    dt = dt or utc_now()
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class RunLog:
    """collection_log.jsonl：只追加、不改寫。每個值先遮蔽再序列化，輸出一定是合法 JSON。"""

    def __init__(self, path, command, run_id=None):
        self.path = path
        self.command = command
        self.run_id = run_id or utc_now().strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def emit_event(self, event, level="info", **fields):
        record = {"ts": utc_stamp(), "run_id": self.run_id, "command": self.command,
                  "level": level, "event": event}
        record.update(fields)
        safe = redact_obj(record)
        line = json.dumps(safe, ensure_ascii=False, sort_keys=False, default=str)
        with open(self.path, "a", encoding="utf-8", newline="\n") as f:
            f.write(line + "\n")
        return safe


class RunLock:
    """state/run.lock：O_CREAT|O_EXCL 建立，避免兩個程序同時寫入。"""

    def __init__(self, path):
        self.path = path
        self.held = False

    def acquire(self, command, force=False):
        from .errors import LockBusy
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if force and os.path.exists(self.path):
            os.remove(self.path)
            emit_console("警告：已依 --force-unlock 移除殘留的執行鎖。", err=True)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise LockBusy(f"執行鎖被占用：{self.path}。若確定沒有其他程序在跑，請加 --force-unlock。")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "started_at": utc_stamp(), "command": command}, f)
        self.held = True

    def release(self):
        if self.held:
            try:
                os.remove(self.path)
            except FileNotFoundError:
                pass
            self.held = False
