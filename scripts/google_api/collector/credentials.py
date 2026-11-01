"""憑證：client_secret／token／API key（設計 §7.1）。

- 只讀取 cred dir（預設 %LOCALAPPDATA%\\PogoKit\\google\\）；不複製憑證到任何地方。
- token 的 scope 必須恰好是三個 readonly scope，多或少都拒絕。
- refresh 失敗（含 invalid_grant）一律 AuthRequired，不會自動開瀏覽器。
- 每次取得新的 access token 都重新登記為已知祕密值。
"""
import json
import os
from pathlib import Path

from .errors import AuthRequired, ConfigError
from .redact import register_secret
from .storage import write_json_atomic

SCOPES = (
    "https://www.googleapis.com/auth/adsense.readonly",
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
)
CLIENT_SECRET_FILE = "client_secret.json"
TOKEN_FILE = "token.json"
API_KEY_FILE = "api_key.txt"


def _normalize_scopes(scopes):
    if scopes is None:
        return None
    if isinstance(scopes, str):
        scopes = scopes.split()
    return {str(s).strip() for s in scopes if str(s).strip()}


def check_scopes(scopes):
    got = _normalize_scopes(scopes)
    if got is None or got != set(SCOPES):
        raise AuthRequired("token 的授權範圍不是預期的三個 readonly scope（多出或缺少）。"
                           "請使用者重新執行：python scripts/google_api/collect.py auth")


def _register_client_secrets(data):
    """只登記 client_secret。client_id 是公開資訊（會出現在授權網址裡），遮掉會讓授權網址失效。"""
    for section in ("installed", "web"):
        sec = data.get(section) if isinstance(data, dict) else None
        if isinstance(sec, dict):
            register_secret(sec.get("client_secret"))
    if isinstance(data, dict):
        register_secret(data.get("client_secret"))


def _is_scope_change_error(exc):
    """oauthlib 在使用者取消勾選某個 scope 時丟的錯誤（Warning: Scope has changed ...）。"""
    name = type(exc).__name__
    text = str(exc).lower()
    return (name == "Warning" and "scope" in text) or ("scope has changed" in text)


def load_api_key(cred_dir):
    path = Path(cred_dir) / API_KEY_FILE
    if not path.exists():
        raise ConfigError(f"找不到 API key 檔案（只列路徑，不讀內容）：{path}")
    key = path.read_text(encoding="utf-8").strip()
    if not key:
        raise ConfigError(f"API key 檔案是空的：{path}")
    register_secret(key)
    return key


def _save_token(token_path, creds):
    data = json.loads(creds.to_json())
    register_secret(data.get("token"))
    register_secret(data.get("refresh_token"))
    write_json_atomic(token_path, data)


def _install_refresh_hook(creds, token_path):
    """包住 creds.refresh：refresh 失敗 → AuthRequired；成功 → 登記新 token、檢查 scope、存檔。"""
    original = creds.refresh

    def refresh(request):
        try:
            original(request)
        except Exception as exc:  # noqa: BLE001
            try:
                from google.auth.exceptions import RefreshError  # type: ignore
            except ImportError:
                RefreshError = ()  # type: ignore
            if RefreshError and isinstance(exc, RefreshError):
                raise AuthRequired() from None
            raise
        register_secret(getattr(creds, "token", None))
        granted = getattr(creds, "granted_scopes", None)
        if granted:
            check_scopes(granted)
        _save_token(token_path, creds)

    creds.refresh = refresh
    return creds


def load_oauth_credentials(cred_dir, *, credentials_cls=None, request_factory=None, refresh_now=True):
    token_path = Path(cred_dir) / TOKEN_FILE
    if not token_path.exists():
        raise AuthRequired(f"找不到 token（{token_path}）。請使用者執行：python scripts/google_api/collect.py auth")
    try:
        with open(token_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (ValueError, OSError):
        raise AuthRequired("token.json 無法讀取。請使用者重新執行 auth。") from None
    _register_client_secrets(data)
    register_secret(data.get("token"))
    register_secret(data.get("refresh_token"))
    check_scopes(data.get("scopes"))
    if not data.get("refresh_token"):
        raise AuthRequired("token.json 沒有 refresh_token。請使用者重新執行 auth。")

    if credentials_cls is None:
        from google.oauth2.credentials import Credentials as credentials_cls  # type: ignore
    creds = credentials_cls.from_authorized_user_info(data, list(SCOPES))
    _install_refresh_hook(creds, token_path)
    if refresh_now and not getattr(creds, "valid", False):
        if request_factory is None:
            def request_factory():
                import google_auth_httplib2  # type: ignore
                import httplib2  # type: ignore
                return google_auth_httplib2.Request(httplib2.Http(timeout=60))
        creds.refresh(request_factory())
    return creds


def run_auth_flow(cred_dir, *, flow_cls=None):
    """使用者親自執行的授權。唯一會開瀏覽器的地方。"""
    cred_dir = Path(cred_dir)
    secret_path = cred_dir / CLIENT_SECRET_FILE
    if not secret_path.exists():
        raise ConfigError(f"找不到 OAuth 用戶端檔案（只列路徑）：{secret_path}")
    with open(secret_path, "r", encoding="utf-8") as f:
        _register_client_secrets(json.load(f))
    if flow_cls is None:
        from google_auth_oauthlib.flow import InstalledAppFlow as flow_cls  # type: ignore
    flow = flow_cls.from_client_secrets_file(str(secret_path), scopes=list(SCOPES))
    try:
        creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    except Exception as exc:  # noqa: BLE001
        if _is_scope_change_error(exc):
            raise AuthRequired("授權時沒有勾選全部權限。請重新執行 auth，並勾選全部三個權限"
                               "（AdSense、Search Console、Analytics，皆為唯讀）後再試一次。") from None
        raise
    register_secret(getattr(creds, "token", None))
    if not getattr(creds, "refresh_token", None):
        raise AuthRequired("沒有取得 refresh token，未寫入 token.json。請到 Google 帳戶的「第三方應用程式存取權」"
                           "移除本應用程式後，重新執行 auth。")
    register_secret(creds.refresh_token)
    check_scopes(getattr(creds, "granted_scopes", None) or getattr(creds, "scopes", None))
    os.makedirs(cred_dir, exist_ok=True)
    _save_token(cred_dir / TOKEN_FILE, creds)
    return creds
