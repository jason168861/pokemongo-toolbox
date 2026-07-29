#!/usr/bin/env python3
"""為 CP 查詢器產生「每隻寶可夢一個網址」的 sitemap（sitemap-cp.xml）。

讓 Google 能收錄 ?tab=cp-checker-app&mon=<名稱> 這種深連結，
使用者搜「皮卡丘 iv100 cp」就有機會搜到並直接開到該寶可夢的查詢結果。

來源：data/precomputed_pokemon_cp.js 裡的 POKEMON_CP_DATA（名稱清單）。
輸出：sitemap-cp.xml（repo 根目錄）、data/sitemap_cp_lastmod.json（lastmod 狀態）。
在 CI（deploy.yml）中執行；本機也可手動跑。

<lastmod> 為什麼要記狀態
---------------------------
CI 每 8 小時跑一次。如果每次都把全部 1000+ 筆的 <lastmod> 寫成當天，
就等於每天對 Google 宣稱「這一千頁都更新了」，但實際上內容一個字都沒動。
Google 對這種 sitemap 會停止信任 lastmod、降低重新檢索的優先度——
剛好會拖慢我們最需要的「重新評估已收錄狀態」。

所以這裡替每個網址算一個內容指紋（會影響頁面顯示的欄位），存在
data/sitemap_cp_lastmod.json；指紋沒變就沿用上次的 lastmod，只有真的
變動（Niantic 調數值、改名、換圖）才更新成今天。

狀態檔放在 data/ 底下是刻意的：deploy.yml 的回寫步驟只 `git add data/`，
放在別的地方下一輪 checkout 就讀不到，等於沒記。
"""
import ast
import hashlib
import json
import os
from datetime import date
from urllib.parse import quote
from xml.sax.saxutils import escape

SITE = "https://jason168861.github.io/pokemongo-toolbox/"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "precomputed_pokemon_cp.js")
OUT = os.path.join(ROOT, "sitemap-cp.xml")
STATE = os.path.join(ROOT, "data", "sitemap_cp_lastmod.json")

# 指紋只看「會出現在該網址頁面上的」欄位：基礎數值變了 CP 表整張會變、
# 改名會換掉標題與內文、換圖會換掉卡片圖。其他欄位（例如 gm 代號）變動
# 不影響使用者看到的內容，不該觸發 lastmod。
FP_FIELDS = ("id", "name", "imageUrl", "cp15", "cp20", "cp25", "atk", "def", "sta", "alt")


def load_entries():
    """回傳 [(名稱, 內容指紋)]，名稱去重且保持原順序。"""
    text = open(SRC, encoding="utf-8").read()
    # 只取第一個陣列(POKEMON_CP_DATA)。檔案後面還有 CP_MULTIPLIER 陣列,
    # 用 rindex("]") 會抓到那個的結尾、把兩個陣列連同中間的 JS 一起餵進 literal_eval → 直接爆。
    arr = ast.literal_eval(text[text.index("["):text.index("];") + 1])  # 單引號字典 → Python 字面值
    out, seen = [], set()
    for p in arr:
        n = (p.get("name") or "").strip()
        if not n or n in seen:
            continue
        seen.add(n)
        raw = "\x1f".join(str(p.get(f, "")) for f in FP_FIELDS)
        out.append((n, hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]))
    return out


def seed_from_sitemap(entries):
    """狀態檔還不存在時，先沿用現有 sitemap-cp.xml 裡的 lastmod。

    不做這件事的話，導入這個機制的第一次執行會把全部網址的 lastmod 再刷成
    今天——正好又是我們想避免的「謊報一千頁都更新了」。既有網址的內容此刻
    沒有變，直接把舊日期配上目前的指紋當基線即可。
    """
    try:
        text = open(OUT, encoding="utf-8").read()
    except OSError:
        return {}
    import re
    from urllib.parse import unquote
    old = {}
    for loc, lastmod in re.findall(r"<loc>(.*?)</loc><lastmod>(.*?)</lastmod>", text):
        if "mon=" in loc:
            old[unquote(loc.split("mon=", 1)[1])] = lastmod
    seeded = {n: {"fp": fp, "lastmod": old[n]} for n, fp in entries if n in old}
    if seeded:
        print(f"  （狀態檔不存在，已從現有 sitemap-cp.xml 沿用 {len(seeded)} 筆 lastmod 當基線）")
    return seeded


def load_state(entries):
    try:
        with open(STATE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and data:
            return data
    except (OSError, ValueError):
        pass
    return seed_from_sitemap(entries)   # 第一次跑、或檔案壞掉


def main():
    entries = load_entries()
    old = load_state(entries)
    today = date.today().isoformat()

    state = {}
    added = updated = kept = 0
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for name, fp in entries:
        prev = old.get(name)
        if isinstance(prev, dict) and prev.get("fp") == fp and prev.get("lastmod"):
            lastmod = prev["lastmod"]          # 內容沒變 → 不要謊報更新
            kept += 1
        else:
            lastmod = today
            if prev:
                updated += 1
            else:
                added += 1
        state[name] = {"fp": fp, "lastmod": lastmod}
        # mon 用名稱（UTF-8 編碼）；XML 內 & 需寫成 &amp;
        loc = SITE + "?tab=cp-checker-app&mon=" + quote(name)
        lines.append("  <url><loc>" + escape(loc) + "</loc>"
                     "<lastmod>" + lastmod + "</lastmod>"
                     "<changefreq>monthly</changefreq><priority>0.5</priority></url>")
    lines.append("</urlset>\n")

    open(OUT, "w", encoding="utf-8").write("\n".join(lines))
    # sort_keys 讓每次輸出順序固定，git diff 才只會顯示真正變動的那幾筆
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")

    removed = [n for n in old if n not in state]
    print(f"已產生 {OUT}，共 {len(entries)} 個寶可夢網址")
    print(f"  lastmod：新增 {added}、內容有變 {updated}、沿用舊日期 {kept}"
          + (f"、已移除 {len(removed)}" if removed else ""))
    if updated:
        changed = [n for n, fp in entries
                   if isinstance(old.get(n), dict) and old[n].get("fp") != fp]
        print("  內容有變動的：" + "、".join(changed[:20])
              + (" …" if len(changed) > 20 else ""))


if __name__ == "__main__":
    main()
