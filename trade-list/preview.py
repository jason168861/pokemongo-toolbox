#!/usr/bin/env python3
"""本機預覽交易清單 —— 改完直接看,不用 commit / push。

    python preview.py            # 起 http://127.0.0.1:8797 並自動開瀏覽器
    python preview.py -p 9000    # 指定埠號
    python preview.py -n         # 不要自動開瀏覽器
    python preview.py --lan      # 同網段的手機也能連(印出區網網址)

跟 `python -m http.server` 的差別:
  * 一律送 no-store,改了 index.html / data/*.json 重新整理就生效(不會吃到舊快取)
  * 埠被佔用會自動往後找
  * 啟動時先檢查 data/ 與 assets/ 是否齊全,缺什麼直接講
  * 多一個 POST /__save 讓 alias-editor.html 直接寫回 data/aliases.json
    (只接受本機來的請求、只准寫白名單裡的檔、覆蓋前先備份)
"""
import argparse, http.server, json, os, shutil, socket, socketserver, sys, threading, webbrowser

try:
    sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
if os.name == "nt":
    os.system("")   # 啟用 ANSI 顏色

HERE = os.path.dirname(os.path.abspath(__file__))
C = lambda s, c: f"\033[{c}m{s}\033[0m"

# alias-editor.html 可以寫回的檔。白名單寫死,避免這支預覽伺服器變成任意寫檔的洞
SAVABLE = {"data/aliases.json"}
MAX_SAVE = 4 * 1024 * 1024


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        """POST /__save?f=data/aliases.json  —— body 就是要寫進去的檔案內容。"""
        path, _, qs = self.path.partition("?")
        if path != "/__save":
            return self._json(404, {"ok": False, "error": "not found"})
        # --lan 會綁 0.0.0.0,同網段的手機也連得到 → 寫檔只允許本機發動
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            return self._json(403, {"ok": False, "error": "只接受本機的儲存請求"})
        rel = dict(p.split("=", 1) for p in qs.split("&") if "=" in p).get("f", "")
        rel = rel.replace("%2F", "/")
        if rel not in SAVABLE:
            return self._json(403, {"ok": False, "error": f"不允許寫入 {rel!r}"})
        n = int(self.headers.get("Content-Length") or 0)
        if not 0 < n <= MAX_SAVE:
            return self._json(400, {"ok": False, "error": "內容是空的或太大"})
        raw = self.rfile.read(n)
        try:
            json.loads(raw.decode("utf-8"))          # 壞掉的 JSON 一律不寫,免得寫爛前端讀的檔
        except Exception as e:
            return self._json(400, {"ok": False, "error": f"不是合法 JSON:{e}"})
        dst = os.path.join(HERE, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):                       # 覆蓋前留一份上一版
            shutil.copyfile(dst, dst + ".bak")
        with open(dst, "wb") as f:
            f.write(raw)
        print(C(f"  ✔ 已寫入 {rel}({n:,} bytes,舊檔備份為 {rel}.bak)", "32"))
        return self._json(200, {"ok": True, "bytes": n})

    def end_headers(self):
        # 預覽用:完全不快取,存檔後重新整理就是最新的
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        super().end_headers()

    def log_message(self, fmt, *args):
        code = str(args[1]) if len(args) > 1 else ""
        if code.startswith("2") or code.startswith("3"):
            return                                   # 只在有問題時吵
        sys.stderr.write(C(f"  {self.requestline}  → {code}\n", "33"))


def check():
    """啟動前掃一遍資料:少檔案的話先講,免得對著空白頁除錯。"""
    ok = True
    for f in ("index.html", "data/pokemon.json", "data/backgrounds.json"):
        if not os.path.exists(os.path.join(HERE, f)):
            print(C(f"  ✗ 缺 {f}", "31")); ok = False
    loc = [os.path.join(HERE, "data", x) for x in ("pokemon.local.json", "backgrounds.local.json")]
    if all(os.path.exists(p) for p in loc):
        bg = json.load(open(loc[1], encoding="utf-8"))
        n_cos = sum(1 for r in bg for m in r["pokemon"] if m.get("costume") or m.get("sprite"))
        missing = {m[k] for r in bg for m in r["pokemon"] for k in ("sprite", "sprite_shiny")
                   if m.get(k) and not os.path.exists(os.path.join(HERE, m[k]))}
        print(f"  本機資料:背卡 {len(bg)} 張 / 背卡×寶可夢 "
              f"{sum(len(r['pokemon']) for r in bg)} 筆 / 其中帶造型 {n_cos} 筆")
        if missing:
            print(C(f"  ⚠ 有 {len(missing)} 張造型圖還沒下載,請跑 python fetch_assets.py", "33"))
    else:
        print(C("  ⚠ 沒有 data/*.local.json,前端會改抓遠端圖(較慢)。跑 python fetch_assets.py 可產生。", "33"))
    return ok


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80)); return s.getsockname()[0]
    except Exception:
        return None
    finally:
        s.close()


def main():
    ap = argparse.ArgumentParser(description="本機預覽交易清單")
    ap.add_argument("-p", "--port", type=int, default=8797)
    ap.add_argument("-n", "--no-open", action="store_true", help="不要自動開瀏覽器")
    ap.add_argument("--lan", action="store_true", help="綁 0.0.0.0,同網段裝置(手機)也能連")
    a = ap.parse_args()

    print("=" * 56)
    print(" 交易清單本機預覽")
    print(f"  目錄:{HERE}")
    if not check():
        print(C("\n缺檔案,先跑 python build_data.py 再跑 python fetch_assets.py。", "31")); sys.exit(1)

    host = "0.0.0.0" if a.lan else "127.0.0.1"
    socketserver.TCPServer.allow_reuse_address = True
    port = a.port
    for _ in range(20):                              # 埠被佔用就往後找
        try:
            httpd = socketserver.ThreadingTCPServer((host, port), Handler); break
        except OSError:
            port += 1
    else:
        print(C(f"找不到可用的埠({a.port}–{a.port + 19})", "31")); sys.exit(1)

    url = f"http://127.0.0.1:{port}/index.html"
    print("=" * 56)
    print(f"  {C('▶ ' + url, '1;36')}")
    if a.lan and (ip := lan_ip()):
        print(f"    區網(手機):http://{ip}:{port}/index.html")
    print(f"    別名建檔:http://127.0.0.1:{port}/alias-editor.html(可直接存回 data/aliases.json)")
    print("  改完 index.html 或 data/*.json → 直接重新整理(已關快取)")
    print(f"  {C('Ctrl+C 結束', '90')}")
    print("=" * 56)
    if not a.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
        httpd.shutdown()


if __name__ == "__main__":
    main()
