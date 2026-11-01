"""遮蔽：所有對外輸出都要經過 redact()（由 runlog 的出口函式呼叫）。

兩層：
1. 已知祕密值：載入憑證時用 register_secret() 登記，輸出中出現就換成 ***。
2. 規則式：處理還沒登記、但格式可辨識的值（API key、OAuth token、JWT、網址參數、JSON 欄位）。

替換結果是冪等的：對已遮蔽的字串再跑一次，結果不變。
"""
import re
import threading
from urllib.parse import quote

MASK = "***"
_MIN_SECRET_LEN = 8

_lock = threading.Lock()
_known = set()

_QUERY_KEYS = r"key|api_key|apikey|access_token|refresh_token|client_secret|token|id_token|code"
_JSON_KEYS = r"refresh_token|access_token|client_secret|token|id_token|api_key|code"

PATTERNS = [
    # Google API key
    (re.compile(r"AIza[0-9A-Za-z_\-]{35}"), MASK),
    # OAuth access token
    (re.compile(r"ya29\.[0-9A-Za-z_\-\.]+"), MASK),
    # OAuth refresh token
    (re.compile(r"1//[0-9A-Za-z_\-]{20,}"), MASK),
    # OAuth client secret
    (re.compile(r"GOCSPX-[0-9A-Za-z_\-]+"), MASK),
    # JWT（id_token 等）
    (re.compile(r"eyJ[0-9A-Za-z_\-]+\.[0-9A-Za-z_\-]+\.[0-9A-Za-z_\-]+"), MASK),
    # Authorization: Bearer xxx
    (re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s\"',;]+"), r"\1" + MASK),
    (re.compile(r"(?i)(\bbearer\s+)[0-9A-Za-z_\-\.~+/]{20,}=*"), r"\1" + MASK),
    # 網址參數 ?key=xxx&token=yyy
    (re.compile(r"(?i)([?&](?:" + _QUERY_KEYS + r")=)[^&\s\"'#]+"), r"\1" + MASK),
    # JSON 欄位 "refresh_token": "xxx"
    (re.compile(r'(?i)("(?:' + _JSON_KEYS + r')"\s*:\s*")[^"]*(")'), r"\1" + MASK + r"\2"),
]


def register_secret(value):
    """登記一個祕密值。太短的值（< 8 字元）不登記，避免把一般文字誤遮。"""
    if not isinstance(value, str):
        return
    value = value.strip()
    if len(value) < _MIN_SECRET_LEN:
        return
    with _lock:
        _known.add(value)
        encoded = quote(value, safe="")
        if encoded != value:
            _known.add(encoded)


def clear_registered():
    """只給測試用。"""
    with _lock:
        _known.clear()


def redact(text):
    """把字串中的祕密值換成 ***。非字串會先轉成字串。"""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    if not text:
        return text
    with _lock:
        known = sorted(_known, key=len, reverse=True)
    for secret in known:
        if secret in text:
            text = text.replace(secret, MASK)
    for pattern, repl in PATTERNS:
        text = pattern.sub(repl, text)
    return text


def redact_obj(obj):
    """遞迴遮蔽 dict / list / tuple 中的所有字串（含 dict 的鍵）。

    給 emit_event 用：先遮蔽每個值再序列化，所以輸出一定是合法 JSON
    （如果先序列化再遮蔽，Bearer 之類的規則可能吃掉引號）。
    """
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {redact(str(k)): redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact_obj(v) for v in obj]
    if isinstance(obj, (int, float, bool)) or obj is None:
        return obj
    return redact(str(obj))
