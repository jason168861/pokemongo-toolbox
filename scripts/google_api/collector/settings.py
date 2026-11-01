"""讀取 config/defaults.json，再套用 CLI 覆寫。"""
import copy
import json
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def deep_merge(base, override):
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_settings(overrides=None, path=None):
    path = Path(path) if path else CONFIG_DIR / "defaults.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.pop("_comment", None)
    return deep_merge(data, overrides or {})


def load_url_list(path=None):
    path = Path(path) if path else CONFIG_DIR / "psi_urls.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    urls = data.get("urls") if isinstance(data, dict) else data
    if not isinstance(urls, list) or not all(isinstance(u, str) for u in urls):
        raise ValueError("網址清單格式錯誤：需要 {\"urls\": [\"https://...\"]}")
    return [u.strip() for u in urls if u.strip()]
