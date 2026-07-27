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
"""
import argparse, http.server, json, os, socket, socketserver, sys, threading, webbrowser

try:
    sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
if os.name == "nt":
    os.system("")   # 啟用 ANSI 顏色

HERE = os.path.dirname(os.path.abspath(__file__))
C = lambda s, c: f"\033[{c}m{s}\033[0m"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

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
