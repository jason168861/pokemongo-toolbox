#!/usr/bin/env python3
"""
把工具用到的所有圖片下載到本機(自我託管,不再盜連別人)。
- 寶可夢 sprite:來自 PokeMiners → assets/img/
- 背卡:來自 Fandom(帶 no-referer 繞過盜連保護,合法把自己要用的抓下來)→ assets/bg/
產出 data/pokemon.local.json / data/backgrounds.local.json(url 指向本機),前端讀這兩個。

未來更新:先跑 build_data.py 刷新來源資料,再跑本檔即可 —— sprite 已存在會跳過,背卡一律重抓(抓最新藝術圖)。
"""
import json, os, re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "assets", "img")
BGD = os.path.join(HERE, "assets", "bg")
os.makedirs(IMG, exist_ok=True); os.makedirs(BGD, exist_ok=True)

def dl(url, path, no_referer=False, force=False, tries=3):
    if os.path.exists(path) and not force and os.path.getsize(path) > 0:
        return "skip"
    # 完全不送 Referer(urllib 預設就不送)→ 繞過 Fandom 盜連保護。no_referer 參數保留給語意清楚。
    headers = {"User-Agent": "Mozilla/5.0 asset-fetch"}
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            data = urllib.request.urlopen(req, timeout=60).read()
            if len(data) < 100:  # 疑似錯誤頁
                raise IOError("too small")
            with open(path, "wb") as f: f.write(data)
            return "ok"
        except Exception as e:
            if a == tries - 1: return f"ERR {e}"

def sprite_local(url):
    return os.path.basename(url.split("?")[0])  # pm25.icon.png

def bg_local(url):
    m = re.search(r"/images/[0-9a-f/]+/([^/]+\.(?:png|jpg|jpeg|webp))/revision", url, re.I)
    name = m.group(1) if m else os.path.basename(url.split("?")[0])
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)

def main():
    pk = json.load(open(os.path.join(HERE, "data", "pokemon.json"), encoding="utf-8"))
    bg = json.load(open(os.path.join(HERE, "data", "backgrounds.json"), encoding="utf-8"))

    # 收集 sprite url
    sprite_urls = set()
    for p in pk.values():
        for v in p["variants"]: sprite_urls.add(v["url"])
        if p.get("gigantamax"):
            for k in ("normal", "shiny"):
                if p["gigantamax"].get(k): sprite_urls.add(p["gigantamax"][k])

    jobs = []  # (url, path, no_referer, force)
    for u in sprite_urls:
        jobs.append((u, os.path.join(IMG, sprite_local(u)), False, False))
    for b in bg:
        if b.get("image_url"):
            jobs.append((b["image_url"], os.path.join(BGD, bg_local(b["image_url"])), True, True))  # 背卡一律重抓

    print(f"要處理:{len(sprite_urls)} sprite + {len(bg)} 背卡 = {len(jobs)} 檔", flush=True)
    ok = skip = err = 0
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = {ex.submit(dl, u, p, nr, fo): u for (u, p, nr, fo) in jobs}
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            if r == "ok": ok += 1
            elif r == "skip": skip += 1
            else: err += 1; print("  ", r, futs[f][-40:], flush=True)
            if i % 400 == 0: print(f"  進度 {i}/{len(jobs)} (ok {ok}/skip {skip}/err {err})", flush=True)

    # 寫出 local 版 JSON(url 指向本機)
    for p in pk.values():
        for v in p["variants"]: v["url"] = "assets/img/" + sprite_local(v["url"])
        if p.get("gigantamax"):
            for k in ("normal", "shiny"):
                if p["gigantamax"].get(k): p["gigantamax"][k] = "assets/img/" + sprite_local(p["gigantamax"][k])
    for b in bg:
        if b.get("image_url"): b["image_url"] = "assets/bg/" + bg_local(b["image_url"])

    json.dump(pk, open(os.path.join(HERE, "data", "pokemon.local.json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(bg, open(os.path.join(HERE, "data", "backgrounds.local.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"\n完成:ok {ok} / 已存在跳過 {skip} / 失敗 {err}", flush=True)
    print("已寫出 data/pokemon.local.json 與 data/backgrounds.local.json", flush=True)

if __name__ == "__main__":
    main()
