#!/usr/bin/env python3
"""產生 backgrounds/index.html —— 活動背卡一覽。

資料來自 trade-list/data/backgrounds.local.json（交易清單用的同一份），
所以背卡編輯器（bg-editor.html）改過的東西，重跑這支就會反映到這一頁。

    python scripts/build_bg_index.py

順便把首頁 index.html 裡 <span data-bg-count> 標記的背卡張數同步成同一個數字。

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
    # 型態/造型的中文標籤。站上本來就有一份（主站的圖鑑清單），沿用它，
    # 才不會在頁面上出現 ALOLA、WCS_2026 這種原始代碼。
    labels = {}
    with open(os.path.join(HERE, "data", "pokedex_manifest.json"), encoding="utf-8") as f:
        for mon in json.load(f)["pokemon"]:
            for v in mon["variants"]:
                if not v.get("label"):
                    continue
                if v.get("form"):
                    labels.setdefault((mon["dex"], "f", v["form"]), v["label"])
                if v.get("costume"):
                    labels.setdefault((mon["dex"], "c", v["costume"]), v["label"])
    # 背卡別名（aliases.json 的 kind=bg）。交易清單的搜尋本來就吃這份，
    # 這一頁不讀的話，同樣打「舊金山」在那邊找得到、在這邊卻是 0 筆。
    alias = {}
    ap = os.path.join(TL, "data", "aliases.json")
    if os.path.exists(ap):
        with open(ap, encoding="utf-8") as f:
            for ent in json.load(f).get("entries", []):
                if ent.get("kind") != "bg":
                    continue
                for t in ent.get("targets", []):
                    alias[t] = alias.get(t, "") + " " + " ".join(ent.get("terms", []))
    return bgs, mons, labels, alias


def sprite(mons, p):
    """依這一筆條目的 form / costume 找對應的圖。

    ⚠ 以前一律抓基本型，結果阿羅拉椰蛋樹畫成關都的、同一張卡上兩隻不同造型的
    皮卡丘長得一模一樣 —— 看起來像資料錯了，其實是這裡沒把 form/costume 傳進來。

    一覽頁一律顯示一般色（異色用旁邊的標籤表示），所以只找 shiny=False 的變體。
    對不到就退回基本型：寧可圖不夠精準，也不要整隻消失。
    """
    ent = mons.get(str(p["dex"]))
    if not ent:
        return None, None
    # 來源自帶的圖（wiki 原圖或人工指定的 sprite）最優先
    if p.get("sprite"):
        return ent.get("zh"), p["sprite"]
    form = p.get("form") or None
    costume = p.get("costume") or None
    ok = lambda v: not v.get("shiny")
    exact = [v for v in ent["variants"] if ok(v)
             and (v.get("form") or None) == form and (v.get("costume") or None) == costume]
    if not exact and costume:          # 只對到造型（form 是同義欄位時常兩邊都填）
        exact = [v for v in ent["variants"] if ok(v) and (v.get("costume") or None) == costume]
    if not exact and form:             # 只對到型態
        exact = [v for v in ent["variants"] if ok(v) and (v.get("form") or None) == form]
    if not exact:                      # 都對不到 → 基本型
        exact = [v for v in ent["variants"] if ok(v) and not v.get("costume")]
    if not exact:
        return ent.get("zh"), None
    best = next((v for v in exact if not v.get("gender")), exact[0])
    return ent.get("zh"), best.get("url")


def variant_label(labels, p):
    """型態/造型的中文標籤。manifest 沒收錄的（新造型）就把代碼整理一下當標籤，
    有標總比讓兩隻皮卡丘看起來一模一樣好。"""
    for kind, key in (("c", p.get("costume")), ("f", p.get("form"))):
        if not key:
            continue
        lab = labels.get((p["dex"], kind, key))
        if lab:
            return lab
        return key.replace("_", " ")   # 保留原本大小寫：PXP/WCS 是縮寫，.title() 會變成 Pxp
    return ""


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


def small(url, sub, dst):
    """原圖換成 fetch_assets.py 產生的縮圖（webp）。背卡原圖 512px PNG 平均 150KB，
    263 張全載是 40MB；縮圖只有幾 KB。沒有縮圖就用原圖。"""
    if not url:
        return None
    if url.startswith(sub):
        name = os.path.splitext(os.path.basename(url))[0] + ".webp"
        if os.path.exists(os.path.join(TL, dst, name)):
            return dst + "/" + name
    return url


def bg_img(bg, size="bgexp"):
    return small(bg.get("image_url"), "assets/bg/", "assets/" + size)


STRIP = 6   # 卡片上直接露出的寶可夢頭像數


def card_html(bg, mons, labels, alias):
    """一張背卡：背景圖、名稱、頭像列；完整寶可夢清單收在 <details>。
    有 JS 時點卡片會改用對話框顯示同一份清單（filter.js），沒有 JS 時 <details> 照樣能展開。"""
    rows, faces, names = [], [], []
    shiny_n = 0
    for p in bg["pokemon"]:
        zh, url = sprite(mons, p)
        if not zh:
            continue
        # 同一張卡上可能有同一隻的多個造型（皮卡丘 PXP_2026 / WCS_2026），
        # 不標出來的話會變成兩筆看起來一模一樣的東西
        vlab = variant_label(labels, p)
        disp = f"{zh}（{vlab}）" if vlab else zh
        names.append(disp)
        tags = []
        if p.get("shiny"):
            shiny_n += 1
            tags.append('<span class="tag tag-shiny">異色</span>')
        else:
            tags.append('<span class="tag tag-none">尚無異色</span>')
        if p.get("dynamax"):
            tags.append('<span class="tag">極巨化</span>')
        if p.get("gmax"):
            tags.append('<span class="tag">超極巨化</span>')
        if p.get("shadow"):
            tags.append('<span class="tag">暗影</span>')
        src = small(url, "assets/img/", "assets/thumb")
        img = (f'<img src="{e(ASSET_PREFIX + src)}" alt="{e(disp)}" width="56" height="56" loading="lazy" decoding="async">'
               if src else '<span class="noimg">—</span>')
        rows.append(f'<li>{img}<span class="mon-name">{e(disp)}</span>'
                    f'<span class="tags">{"".join(tags)}</span></li>')
        if len(faces) < STRIP:
            faces.append(f'<span class="av" title="{e(disp)}"><img src="{e(ASSET_PREFIX + src)}" alt="" width="40" height="40" loading="lazy" decoding="async"></span>'
                         if src else '<span class="noimg">—</span>')

    n = len(rows)
    extra = f'<span class="plus">+{n - STRIP}</span>' if n > STRIP else ""
    kind = "特殊背卡" if bg["type"] == "special" else "地區背卡"
    title = display_name(bg)
    noshiny = n - shiny_n
    src = bg_img(bg)
    shot = (f'<img src="{e(ASSET_PREFIX + src)}" alt="{e(title)}背卡" width="384" height="384" loading="lazy" decoding="async">'
            if src else "")
    # 搜尋用的字串:名稱 + 全部寶可夢中文名,一次比對就好
    hay = " ".join([title, kind, alias.get(bg["image_name"], "")] + names)
    return f'''      <article class="bgcard" data-kind="{bg['type']}" data-noshiny="{1 if noshiny else 0}" data-q="{e(hay.lower())}">
        <div class="bgshot">{shot}<span class="kind kind-{bg['type']}">{kind}</span></div>
        <div class="bgbody">
          <h3>{e(title)}</h3>
          <p class="meta">{n} 隻寶可夢{f'<span class="ns">・{noshiny} 隻尚無異色</span>' if noshiny else ''}</p>
          <p class="who">{e("、".join(names))}</p>
          <div class="strip" aria-hidden="true">{"".join(faces)}{extra}</div>
          <details class="more"><summary>全部 {n} 隻</summary><ul class="mons">{"".join(rows)}</ul></details>
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
PROSE_LEDE = """
      <p class="lede">在 Pokémon GO 的特定活動或特定地點抓到的寶可夢，卡片背景會帶有專屬圖案，
      玩家習慣叫它「背卡」。背景會跟著這隻寶可夢一起保留，交換之後也還在 ——
      所以對收藏的人來說，同一隻寶可夢配上不同背卡，是完全不同的東西。</p>
"""

PROSE_TOP = """
      <p class="intro">這一頁整理了目前已知的 <strong>{total} 張背卡</strong>（{loc} 張地區背卡、{spe} 張特殊背卡），
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
    bgs, mons, labels, alias = load()
    bgs = sorted(bgs, key=lambda b: (b["type"] != "special", display_name(b).lower()))
    n_loc = sum(1 for b in bgs if b["type"] == "location")
    n_spe = len(bgs) - n_loc
    n_combo = sum(len(b["pokemon"]) for b in bgs)
    # 來源資料本身就是一份異色供應表,99% 的組合都標了異色 ——
    # 所以「有異色」沒有資訊量,「還沒有異色」的例外才是使用者真正想知道的。
    n_noshiny = sum(1 for b in bgs for p in b["pokemon"] if not p.get("shiny"))

    cards = "\n".join(card_html(b, mons, labels, alias) for b in bgs)
    # 主視覺的背卡拼貼：寶可夢最多的幾張特殊背卡（活動主題，畫面最豐富），用 220px 縮圖
    pick = sorted((b for b in bgs if b["type"] == "special" and bg_img(b, "bgthumb")),
                  key=lambda b: -len(b["pokemon"]))[:6]
    mosaic = "".join(f'<img src="{e(ASSET_PREFIX + bg_img(b, "bgthumb"))}" alt="" width="220" height="220" decoding="async">'
                     for b in pick)
    desc =(f"Pokémon GO 活動背卡完整一覽:{len(bgs)} 張背卡（{n_loc} 張地區、{n_spe} 張特殊），"
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
  <a class="home" href="../"><span class="logo" aria-hidden="true">🧰</span><span>Pokémon Go 工具箱</span></a>
  <nav class="tnav" aria-label="相關工具">
    <a href="../tradable/">不可交換清單</a>
    <a href="../stardust/">星沙攻略</a>
  </nav>
  <a class="cta" href="../trade-list/">做交換清單</a>
</header>

<main>
  <article class="page">
    <section class="hero">
      <div class="hero-text">
        <p class="eyebrow">背卡圖鑑 · 持續更新</p>
        <h1>Pokémon GO 活動背卡一覽</h1>
{PROSE_LEDE}
        <div class="hero-cta">
          <a class="btn btn-light" href="#all">瀏覽全部 {len(bgs)} 張背卡</a>
          <a class="btn btn-ghost" href="../trade-list/">做成交換清單 →</a>
        </div>
      </div>
      <div class="mosaic" aria-hidden="true">{mosaic}</div>
    </section>

    <div class="stats">
      <div><b>{len(bgs)}</b><span>張背卡</span></div>
      <div><b>{n_loc}</b><span>地區背卡</span></div>
      <div><b>{n_spe}</b><span>特殊背卡</span></div>
      <div><b>{n_combo:,}</b><span>寶可夢組合</span></div>
    </div>
{PROSE_TOP.format(total=len(bgs), loc=n_loc, spe=n_spe)}

    <section class="listing" id="all">
      <div class="listing-head">
        <h2>全部背卡</h2>
        <p class="count" id="count" aria-live="polite"></p>
      </div>
      <div class="controls">
        <label class="search">
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" stroke-width="2"/><path d="m20 20-3.5-3.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
          <input id="q" type="search" placeholder="搜尋背卡名稱或寶可夢（簡體也可以）" autocomplete="off" aria-label="搜尋背卡名稱或寶可夢">
        </label>
        <div class="filters" role="group" aria-label="篩選">
          <button class="f on" data-f="all" aria-pressed="true">全部</button>
          <button class="f" data-f="special" aria-pressed="false">特殊背卡</button>
          <button class="f" data-f="location" aria-pressed="false">地區背卡</button>
          <button class="f" data-f="noshiny" aria-pressed="false">尚無異色 <span>{n_noshiny}</span></button>
        </div>
      </div>
      <div class="grid" id="grid">
{cards}
      </div>
      <p class="empty" id="empty" hidden>找不到符合的背卡。換個關鍵字，或改用簡短的寶可夢名稱試試。</p>
    </section>

    <section class="notes-sec">
{PROSE_NOTES}
    </section>

    <section class="next">
      <div>
        <h2>把想要的背卡做成交換清單</h2>
        <p>找到想收的組合之後，可以直接到<a href="../trade-list/">交易清單產生器</a>把它們挑起來，
        分成「我想要的」和「我能提供的」，一鍵匯出成一張圖片貼給對方 ——
        不用一隻一隻打字說明，對方也不會看錯。</p>
      </div>
      <p><a class="bigcta" href="../trade-list/">開始製作交換清單 →</a></p>
    </section>
  </article>
</main>

<dialog class="sheet" id="sheet" aria-labelledby="sheet-title">
  <div class="sheet-shot"><img id="sheet-img" alt="" width="384" height="384"><button class="sheet-x" type="button" aria-label="關閉">✕</button></div>
  <div class="sheet-body">
    <p class="sheet-kind" id="sheet-kind"></p>
    <h3 id="sheet-title"></h3>
    <p class="sheet-meta" id="sheet-meta"></p>
    <ul class="mons" id="sheet-list"></ul>
  </div>
  <div class="sheet-foot"><a class="bigcta" href="../trade-list/">用這張背卡做交換清單 →</a></div>
</dialog>

<footer class="foot">
  <p>資料整理自社群維基並經人工核對，非官方資料，可能有誤或未即時更新。</p>
  <p>本站為非官方同人工具，與 Pokémon GO／Niantic 無隸屬關係。
     Pokémon 及其商標為 &copy;1995-2026 Nintendo, Creatures, GAME FREAK 所有。</p>
  <p><a href="../about/">關於本站</a> · <a href="../contact/">聯絡我們</a> · <a href="../privacy/">隱私權政策</a> · <a href="../disclaimer/">免責聲明</a> · <a href="../">回工具箱</a></p>
</footer>

<script src="filter.js" defer></script>
<script src="../js/ads.js" defer></script>
</body>
</html>
'''
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)

    print(f"已寫出 backgrounds/index.html（{os.path.getsize(OUT):,} bytes）")
    print(f"  背卡 {len(bgs)} 張:地區 {n_loc}、特殊 {n_spe}")
    print(f"  寶可夢組合 {n_combo:,} 個,其中 {n_noshiny} 個目前沒有異色")
    miss = sum(1 for b in bgs for p in b["pokemon"] if not sprite(mons, p)[1])
    if miss:
        print(f"  ⚠ 有 {miss} 個寶可夢找不到圖示（會顯示成 —）")
    print("  ⚠ 別忘了補 PROSE_TOP / PROSE_NOTES 裡標「請補上」的段落 —— 那才是這頁的價值")
    sync_home_count(len(bgs))


# 首頁（index.html）的背卡卡片和介紹段落也寫了背卡張數，用 <span data-bg-count> 標記。
# 首頁是手寫的，這裡只換標記裡的數字，其他內容一律不動。
HOME = os.path.join(HERE, "index.html")
HOME_COUNT_RE = re.compile(r"(<span data-bg-count>)\d+(</span>)")


def sync_home_count(n):
    with open(HOME, encoding="utf-8", newline="") as f:
        src = f.read()
    new, hits = HOME_COUNT_RE.subn(rf"\g<1>{n}\g<2>", src)
    if not hits:
        print("  ⚠ index.html 找不到 <span data-bg-count>，首頁的背卡張數沒有同步")
        return
    if new != src:
        with open(HOME, "w", encoding="utf-8", newline="") as f:
            f.write(new)
        print(f"  已把 index.html 的背卡張數（{hits} 處）同步為 {n}")
    else:
        print(f"  index.html 的背卡張數（{hits} 處）已經是 {n}")


if __name__ == "__main__":
    build()
