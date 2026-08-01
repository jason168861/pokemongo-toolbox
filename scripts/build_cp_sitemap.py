#!/usr/bin/env python3
"""為 CP 查詢器產生「每隻寶可夢一個網址」的 sitemap（sitemap-cp.xml）與靜態索引頁。

讓 Google 能收錄 ?tab=cp-checker-app&mon=<名稱> 這種深連結，
使用者搜「皮卡丘 iv100 cp」就有機會搜到並直接開到該寶可夢的查詢結果。

來源：data/precomputed_pokemon_cp.js 裡的 POKEMON_CP_DATA（名稱清單）。
輸出：sitemap-cp.xml（repo 根目錄）、data/sitemap_cp_lastmod.json（lastmod 狀態）、
      cp-list/index.html（靜態索引頁）。
在 CI（deploy.yml）中執行；本機也可手動跑。

為什麼還要一個靜態索引頁
--------------------------
Search Console 對這些 ?mon= 網址一律回報「參照網頁：未偵測到任何參照網頁」，
而且把它們判成樞紐頁 ?tab=cp-checker-app 的重複網頁。原因是這 1079 個網址
在 Google 眼中是孤立的：站內唯一有這些連結的地方是樞紐頁，但那些 <a> 全部
由 JS 產生，而樞紐頁轉譯後有 959KB —— Google 得先完整轉譯近 1MB 才看得到。
一個沒有任何連結指向、又長得像 ?參數= 變體的網址，Google 的預設行為就是
把它併回基礎網址。

所以這裡另外產生一頁純靜態 HTML 的清單：不需要執行 JS、不需要吞 959KB，
Googlebot 抓下來就直接看到 1079 個 <a>。網址與編碼跟 sitemap 用同一套
（quote()），三邊（sitemap／canonical／站內連結）才會完全一致。

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
import html
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
INDEX_DIR = os.path.join(ROOT, "cp-list")
INDEX_OUT = os.path.join(INDEX_DIR, "index.html")

# 指紋只看「會出現在該網址頁面上的」欄位：基礎數值變了 CP 表整張會變、
# 改名會換掉標題與內文、換圖會換掉卡片圖。其他欄位（例如 gm 代號）變動
# 不影響使用者看到的內容，不該觸發 lastmod。
FP_FIELDS = ("id", "name", "imageUrl", "cp15", "cp20", "cp25", "atk", "def", "sta", "alt")

# 頁面樣板／SEO 邏輯的版本，一併算進指紋。
#
# 上面的欄位指紋擋得住「資料沒變卻天天改 lastmod」，但擋過頭了：當程式改動讓
# 「同一份資料算出來的頁面」變了（canonical、標題、描述的產生方式），資料欄位
# 一個都不會動，lastmod 就停在改動之前 —— 等於對 Google 宣稱「這 1079 頁自那天
# 起沒變過」，可是我們正需要它重新檢索、重新評估已收錄狀態。
#
# 這種時候把版本號 +1，讓全部網址重新標記一次日期（之後又會恢復穩定）。
# 只有「輸出真的變了」才可以動它 —— 拿它來催檢索就變成謊報，會回到原本
# 「Google 停止信任 lastmod」的老問題。
#
# v2 (2026-08-01)：canonical / og:url / 標題 / 描述改成在 <head> 用同步腳本設定。
#   在此之前這些值要等 main.js（module + 300KB 資料檔 + Firebase）載完才會修正，
#   Googlebot 的轉譯預算內常常只看到寫死指向首頁的 canonical，整批網址因而被判為
#   重複網頁或「頁面會重新導向」。頁面輸出確實變了，值得讓 Google 重看一次。
TEMPLATE_VERSION = "2"


def load_entries():
    """回傳 [(名稱, 內容指紋, 圖鑑編號)]，名稱去重且保持原順序。"""
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
        raw = "\x1f".join([TEMPLATE_VERSION] + [str(p.get(f, "")) for f in FP_FIELDS])
        try:
            dex = int(p.get("id") or 0)
        except (TypeError, ValueError):
            dex = 0
        out.append((n, hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16], dex))
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
    seeded = {n: {"fp": fp, "lastmod": old[n]} for n, fp, _ in entries if n in old}
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


PAGE_CSS = """
:root { color-scheme: light dark; --fg:#1c1e21; --bg:#fff; --muted:#606770;
        --line:#dfe3e8; --link:#1877f2; --card:#f7f8fa; }
@media (prefers-color-scheme: dark) {
  :root { --fg:#e4e6eb; --bg:#18191a; --muted:#b0b3b8; --line:#3a3b3c;
          --link:#6aa9ff; --card:#242526; }
}
* { box-sizing: border-box; }
body { margin:0; padding:24px 16px 48px; background:var(--bg); color:var(--fg);
       font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC",
                   "Microsoft JhengHei",sans-serif; line-height:1.6; }
.wrap { max-width:1080px; margin:0 auto; }
.crumb { margin:0 0 8px; font-size:14px; }
a { color:var(--link); text-decoration:none; }
a:hover { text-decoration:underline; }
h1 { font-size:26px; margin:0 0 12px; }
h2 { font-size:19px; margin:32px 0 12px; padding-bottom:6px;
     border-bottom:1px solid var(--line); scroll-margin-top:16px; }
.lead { color:var(--muted); margin:0 0 20px; }
.jump { display:flex; flex-wrap:wrap; gap:8px; margin:0 0 8px; padding:12px;
        background:var(--card); border:1px solid var(--line); border-radius:8px; }
.jump a { font-size:14px; padding:2px 8px; border-radius:4px; white-space:nowrap; }
ul.mons { list-style:none; margin:0; padding:0;
          display:grid; gap:4px 16px;
          grid-template-columns:repeat(auto-fill,minmax(190px,1fr)); }
ul.mons li { font-size:15px; overflow-wrap:anywhere; }
ul.mons .dex { color:var(--muted); font-variant-numeric:tabular-nums;
               font-size:13px; margin-right:4px; }
footer { margin-top:48px; padding-top:16px; border-top:1px solid var(--line);
         color:var(--muted); font-size:13px; }
"""


def build_index_page(entries):
    """產生 cp-list/index.html：1079 個 ?mon= 深連結的純靜態清單。

    給 Googlebot 一條不必執行 JS、也不必轉譯樞紐頁那 959KB 就能發現這些
    網址的路徑（理由見檔頭）。網址一律用 quote()，與 sitemap-cp.xml 完全一致。
    """
    groups = {}          # 每 100 號一組，(起,迄) → [(編號, 名稱)]
    for name, _fp, dex in entries:
        lo = ((dex - 1) // 100) * 100 + 1 if dex > 0 else 0
        groups.setdefault(lo, []).append((dex, name))

    def esc(s):
        return html.escape(str(s), quote=True)

    order = sorted(groups)
    heads = []
    for lo in order:
        label = f"#{lo:03d}–#{lo + 99:03d}" if lo else "其他形態"
        heads.append((lo, label))

    out = ['<!DOCTYPE html>', '<html lang="zh-Hant">', '<head>',
           '<meta charset="UTF-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
           f'<title>全部寶可夢 IV100 CP 速查索引（共 {len(entries)} 隻）｜Pokémon Go 工具箱</title>',
           '<meta name="description" content="Pokémon GO 全部寶可夢的 IV100 CP 速查索引，'
           f'共 {len(entries)} 隻（含各地區形態）。點任一隻可查看該寶可夢在 Lv1～50 每個等級的 '
           'CP 上下限，以及 15、20、25 等的滿 IV CP。">',
           '<meta name="robots" content="index, follow">',
           f'<link rel="canonical" href="{SITE}cp-list/">',
           f'<style>{PAGE_CSS}</style>', '</head>', '<body>', '<div class="wrap">',
           '<p class="crumb"><a href="../">← 回 Pokémon Go 工具箱</a></p>',
           '<h1>全部寶可夢 IV100 CP 速查索引</h1>',
           f'<p class="lead">共 {len(entries)} 隻（含阿羅拉、伽勒爾等各地區形態）。'
           '點任一隻可查看牠在 Lv1～50 每個等級的 CP 上下限（100% IV / 0% IV），'
           '以及田野調查（Lv15）、團體戰（Lv20／25）的滿 IV CP。</p>',
           '<nav class="jump">'
           + ''.join(f'<a href="#dex-{lo}">{esc(label)}</a>' for lo, label in heads)
           + '</nav>', '<main>']

    for lo, label in heads:
        out.append(f'<section><h2 id="dex-{lo}">{esc(label)}</h2><ul class="mons">')
        for dex, name in groups[lo]:
            # 相對網址：從 /cp-list/ 往上一層就是站台根目錄，任何環境都指得對。
            href = '../?tab=cp-checker-app&amp;mon=' + quote(name)
            num = f'<span class="dex">#{dex:03d}</span>' if dex > 0 else ''
            out.append(f'<li>{num}<a href="{href}">{esc(name)}</a></li>')
        out.append('</ul></section>')

    out += ['</main>', '<footer>',
            '<p>CP 數值由各寶可夢的基礎數值與各等級 CP 倍率計算，'
            '資料來源為 Pokémon GO GAME_MASTER。</p>',
            '<p>This website is an unofficial fan-made tool, is not officially affiliated '
            'with Pokémon GO. Pokémon and its trademarks are &copy;1995-2025 Nintendo, '
            'Creatures, and GAME FREAK.</p>',
            '</footer>', '</div>', '</body>', '</html>', '']

    os.makedirs(INDEX_DIR, exist_ok=True)
    open(INDEX_OUT, "w", encoding="utf-8").write("\n".join(out))
    return len(entries), len(heads)


def main():
    entries = load_entries()
    old = load_state(entries)
    today = date.today().isoformat()

    state = {}
    added = updated = kept = 0
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for name, fp, _dex in entries:
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

    n_links, n_groups = build_index_page(entries)

    removed = [n for n in old if n not in state]
    print(f"已產生 {INDEX_OUT}，{n_links} 個站內連結、分 {n_groups} 組")
    print(f"已產生 {OUT}，共 {len(entries)} 個寶可夢網址")
    print(f"  lastmod：新增 {added}、內容有變 {updated}、沿用舊日期 {kept}"
          + (f"、已移除 {len(removed)}" if removed else ""))
    if updated:
        changed = [n for n, fp, _ in entries
                   if isinstance(old.get(n), dict) and old[n].get("fp") != fp]
        print("  內容有變動的：" + "、".join(changed[:20])
              + (" …" if len(changed) > 20 else ""))


if __name__ == "__main__":
    main()
