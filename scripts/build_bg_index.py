#!/usr/bin/env python3
"""產生 backgrounds/index.html —— 活動背卡一覽。

資料來自 trade-list/data/backgrounds.local.json（交易清單用的同一份），
所以背卡編輯器（bg-editor.html）改過的東西，重跑這支就會反映到這一頁。

    python scripts/build_bg_index.py

表格是機器產生的，但這一頁真正的價值在 PROSE 區塊的文字 ——
  資料整理過程的說明、以及對背卡的實際判斷。那些要人來寫，
  只有表格的話這一頁沒有存在的必要。
"""
import json, os, re, html, collections

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TL = os.path.join(HERE, "trade-list")
OUT_DIR = os.path.join(HERE, "backgrounds")
OUT = os.path.join(OUT_DIR, "index.html")

# 這一頁在 /backgrounds/，圖片都在 /trade-list/assets/ 底下
ASSET_PREFIX = "../trade-list/"

e = html.escape


def load():
    with open(os.path.join(TL, "data", "backgrounds.local.json"), encoding="utf-8") as f:
        bgs = json.load(f)
    with open(os.path.join(TL, "data", "pokemon.local.json"), encoding="utf-8") as f:
        mons = json.load(f)
    return bgs, mons


def sprite(mons, dex, shiny):
    """找這隻寶可夢的「一般型態」圖示。

    優先順序：form/costume 都沒有的 → 沒有 costume 的第一個。
    後者是給蒼響那種「預設就有 form 代碼」的寶可夢用的（HERO_OF_MANY_BATTLES），
    不留這層 fallback 的話牠們會整隻抓不到圖。
    """
    ent = mons.get(str(dex))
    if not ent:
        return None, None
    want = bool(shiny)
    plain = [v for v in ent["variants"]
             if bool(v.get("shiny")) == want and not v.get("costume")]
    if not plain:
        return ent.get("zh"), None
    best = next((v for v in plain if not v.get("form") and not v.get("gender")), plain[0])
    return ent.get("zh"), best.get("url")


def display_name(bg):
    """背卡名稱。有 6 張的 name 是空字串（來源資料就沒有），從檔名反推。

    "Location Background NPB 2026 Hanshin Tigers.png" → "NPB 2026 Hanshin Tigers"
    "Special Background MightAndMastery.png"          → "Might And Mastery"
    """
    name = (bg.get("name") or "").strip()
    if name:
        return name
    n = re.sub(r"\.(png|jpe?g|webp)$", "", bg["image_name"], flags=re.I)
    n = re.sub(r"^(Location|Special)\s+Background\s*", "", n, flags=re.I)
    n = re.sub(r"^GO\s+", "", n)
    n = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", n)      # MightAndMastery → Might And Mastery
    return re.sub(r"[_\s]+", " ", n).strip() or bg["image_name"]


def card_html(bg, mons):
    """一張背卡：背景圖 + 上面看得到的寶可夢（含有沒有異色）。"""
    rows = []
    shiny_n = 0
    for p in bg["pokemon"]:
        zh, url = sprite(mons, p["dex"], False)
        if not zh:
            continue
        tags = []
        if p.get("shiny"):
            shiny_n += 1
            tags.append('<span class="tag tag-shiny">異色</span>')
        if p.get("dynamax"):
            tags.append('<span class="tag">極巨化</span>')
        if p.get("gmax"):
            tags.append('<span class="tag">超極巨化</span>')
        if p.get("shadow"):
            tags.append('<span class="tag">暗影</span>')
        img = (f'<img src="{e(ASSET_PREFIX + url)}" alt="{e(zh)}" width="48" height="48" loading="lazy" decoding="async">'
               if url else '<span class="noimg">—</span>')
        rows.append(f'<li>{img}<span class="mon-name">{e(zh)}</span>'
                    f'<span class="tags">{"".join(tags)}</span></li>')

    # 隊伍主題那幾張有 120 隻以上,全部攤開會把整個 grid 列撐到六千多 px。
    # 收進 <details> 而不是砍掉 —— 內容留在 HTML 裡,搜尋引擎和頁內搜尋都還讀得到。
    SHOW = 8
    if len(rows) > SHOW:
        head, tail = rows[:SHOW], rows[SHOW:]
        mon_html = (f'<ul class="mons">{"".join(head)}</ul>'
                    f'<details class="more"><summary>還有 {len(tail)} 隻</summary>'
                    f'<ul class="mons">{"".join(tail)}</ul></details>')
    else:
        mon_html = f'<ul class="mons">{"".join(rows)}</ul>' 

    kind = "特殊背卡" if bg["type"] == "special" else "地區背卡"
    title = display_name(bg)
    # 搜尋用的字串:名稱 + 全部寶可夢中文名,一次比對就好
    hay = " ".join([title, kind] + re.findall(r'class="mon-name">([^<]+)<', "".join(rows)))
    return f'''      <article class="bgcard" data-kind="{bg['type']}" data-noshiny="{1 if shiny_n < len(rows) else 0}" data-q="{e(hay.lower())}">
        <div class="bgshot">
          <img src="{e(ASSET_PREFIX + bg['image_url'])}" alt="{e(title)}背卡" loading="lazy" decoding="async">
        </div>
        <div class="bgbody">
          <h3>{e(title)}</h3>
          <p class="meta"><span class="kind kind-{bg['type']}">{kind}</span>
             共 {len(rows)} 隻{f'・{len(rows) - shiny_n} 隻尚無異色' if shiny_n < len(rows) else ''}</p>
          {mon_html}
        </div>
      </article>'''


# ---------------------------------------------------------------------------
# 頁面文字。這裡才是這一頁的價值所在,底下的表格只是佐證。
#
# 待補（寫在這裡，不要寫成 HTML 註解 —— 那會出現在檢視原始碼裡）：
#   PROSE_TOP   開頭再加一段實際判斷:哪幾張背卡難拿、哪些很常見、
#               交換時大家最在意哪幾張、哪些背卡的異色值得追。
#   PROSE_NOTES 補上實際遇過的錯誤案例,或某張背卡為什麼特別難確認。
# ---------------------------------------------------------------------------
PROSE_TOP = """
      <p class="lede">在 Pokémon GO 的特定活動或特定地點抓到的寶可夢，卡片背景會帶有專屬圖案，
      玩家習慣叫它「背卡」。背景會跟著這隻寶可夢一起保留，交換之後也還在 ——
      所以對收藏的人來說，同一隻寶可夢配上不同背卡，是完全不同的東西。</p>

      <p>這一頁整理了目前已知的 <strong>{total} 張背卡</strong>（{loc} 張地區背卡、{spe} 張特殊背卡），
      以及每張背卡上會出現哪些寶可夢、其中哪些有異色。
      資料跟<a href="../trade-list/">交易清單產生器</a>共用同一份，
      在這裡看到的組合都可以直接拿去做成交換清單圖片。</p>

"""

PROSE_NOTES = """
      <h2>這份清單是怎麼整理出來的</h2>

      <p>背卡沒有官方公開的完整列表，這份資料是從社群維基彙整後、再逐張人工核對過的。
      過程中修掉了幾類原始資料本來就有的問題，也是為什麼這份清單跟直接抄來的不一樣：</p>

      <ul class="notes">
        <li><strong>進化型漏列。</strong>原始資料常常只寫初階進化。但異色與背卡在進化後會保留，
            所以初階有異色背卡的話，牠的進化型也應該列得出來。這批是照進化鏈補回去的。</li>
        <li><strong>重複的背卡。</strong>資料來自兩個來源，同一張背卡會出現兩次、名稱還不一樣。
            這些用圖片比對找出來後合併掉了。</li>
        <li><strong>裝扮寶可夢的異色圖用錯。</strong>有些造型寶可夢的異色沿用了一般版的圖，
            這類逐一改成正確的圖檔。</li>
        <li><strong>不能交換的寶可夢。</strong>照遊戲資料裡的可交換旗標過濾掉，
            列出來卻換不到只會浪費時間。</li>
      </ul>

      <p class="caveat">即使如此，這份清單還是可能有漏或有錯 —— 背卡會隨活動不斷新增，
      而且部分舊活動的資料本來就不完整。發現問題歡迎告訴我。</p>

"""


def build():
    bgs, mons = load()
    bgs = sorted(bgs, key=lambda b: (b["type"] != "special", display_name(b).lower()))
    n_loc = sum(1 for b in bgs if b["type"] == "location")
    n_spe = len(bgs) - n_loc
    n_combo = sum(len(b["pokemon"]) for b in bgs)
    # 來源資料本身就是一份異色供應表,99% 的組合都標了異色 ——
    # 所以「有異色」沒有資訊量,「還沒有異色」的例外才是使用者真正想知道的。
    n_noshiny = sum(1 for b in bgs for p in b["pokemon"] if not p.get("shiny"))

    cards = "\n".join(card_html(b, mons) for b in bgs)
    desc = (f"Pokémon GO 活動背卡完整一覽:{len(bgs)} 張背卡（{n_loc} 張地區、{n_spe} 張特殊），"
            f"列出每張背卡會出現哪些寶可夢、哪些有異色，並可直接做成交換清單。")

    ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "Pokémon GO 活動背卡一覽",
        "description": desc,
        "inLanguage": "zh-Hant",
        "mainEntityOfPage": "https://pogokit.com/backgrounds/",
    }, ensure_ascii=False)

    page = f'''<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8866689605007086" crossorigin="anonymous"></script>
<script src="../js/zh-search.js"></script>
<script src="../js/analytics.js"></script>
<script src="../config.js"></script>
<script src="../js/pageview-counter.js" defer></script>
<link rel="icon" type="image/png" sizes="192x192" href="../img/masterball.png">
<title>Pokémon GO 活動背卡一覽 — {len(bgs)} 張背卡與異色對照｜Pokémon Go 工具箱</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="https://pogokit.com/backgrounds/">
<meta name="robots" content="index,follow">
<meta property="og:type" content="article">
<meta property="og:title" content="Pokémon GO 活動背卡一覽 — {len(bgs)} 張背卡與異色對照">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="https://pogokit.com/backgrounds/">
<script type="application/ld+json">{ld}</script>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header class="topbar">
  <a class="home" href="../">← Pokémon Go 工具箱</a>
  <a class="cta" href="../trade-list/">🔴 做交換清單</a>
</header>

<main>
  <article class="page">
    <h1>Pokémon GO 活動背卡一覽</h1>
{PROSE_TOP.format(total=len(bgs), loc=n_loc, spe=n_spe)}

    <div class="stats">
      <div><b>{len(bgs)}</b><span>張背卡</span></div>
      <div><b>{n_loc}</b><span>地區背卡</span></div>
      <div><b>{n_spe}</b><span>特殊背卡</span></div>
      <div><b>{n_combo:,}</b><span>寶可夢組合</span></div>
    </div>

    <section class="listing">
      <h2>全部背卡</h2>
      <div class="controls">
        <input id="q" type="search" placeholder="搜尋背卡名稱或寶可夢…（簡體也可以）" autocomplete="off">
        <div class="filters">
          <button class="f on" data-f="all">全部</button>
          <button class="f" data-f="special">特殊背卡</button>
          <button class="f" data-f="location">地區背卡</button>
          <button class="f" data-f="noshiny">尚無異色（{n_noshiny}）</button>
        </div>
      </div>
      <p class="count" id="count"></p>
      <div class="grid" id="grid">
{cards}
      </div>
      <p class="empty" id="empty" hidden>找不到符合的背卡。</p>
    </section>

{PROSE_NOTES}

    <section class="next">
      <h2>把想要的背卡做成交換清單</h2>
      <p>找到想收的組合之後，可以直接到<a href="../trade-list/">交易清單產生器</a>把它們挑起來，
      分成「我想要的」和「我能提供的」，一鍵匯出成一張圖片貼給對方 ——
      不用一隻一隻打字說明，對方也不會看錯。</p>
      <p><a class="bigcta" href="../trade-list/">🔴 開始製作交換清單</a></p>
    </section>
  </article>
</main>

<footer class="foot">
  <p>資料整理自社群維基並經人工核對，非官方資料，可能有誤或未即時更新。</p>
  <p>本站為非官方同人工具，與 Pokémon GO／Niantic 無隸屬關係。
     Pokémon 及其商標為 &copy;1995-2026 Nintendo, Creatures, GAME FREAK 所有。</p>
  <p><a href="../about/">關於本站</a> · <a href="../contact/">聯絡我們</a> · <a href="../privacy/">隱私權政策</a> · <a href="../disclaimer/">免責聲明</a> · <a href="../">回工具箱</a></p>
</footer>

<script src="filter.js" defer></script>
</body>
</html>
'''
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)

    print(f"已寫出 backgrounds/index.html（{os.path.getsize(OUT):,} bytes）")
    print(f"  背卡 {len(bgs)} 張:地區 {n_loc}、特殊 {n_spe}")
    print(f"  寶可夢組合 {n_combo:,} 個,其中 {n_noshiny} 個目前沒有異色")
    miss = sum(1 for b in bgs for p in b["pokemon"] if not sprite(mons, p["dex"], False)[1])
    if miss:
        print(f"  ⚠ 有 {miss} 個寶可夢找不到圖示（會顯示成 —）")
    print("  ⚠ 別忘了補 PROSE_TOP / PROSE_NOTES 裡標「請補上」的段落 —— 那才是這頁的價值")


if __name__ == "__main__":
    build()
