#!/usr/bin/env python3
"""產生 PvP 三個聯盟的排名 Top 100 靜態頁：
    /pvp-ranker/great-league/   超級聯盟（CP 1500）
    /pvp-ranker/ultra-league/   高級聯盟（CP 2500）
    /pvp-ranker/master-league/  大師聯盟（無上限）

資料：data/pokemon_data_and_rankings.js（CI 由 generate_pokemon_data.py 從 pvpoketw 更新）
      的 POKEMON_RANKINGS_*、POKEDEX；圖片用 trade-list/assets/thumb/。

    python scripts/build_pvp_league.py

CI 每次排程都會跑（在 generate_pokemon_data.py / refresh_cp_data.py 之後）。
跑完三個聯盟後會接著跑 build_pvp_cups.py（盃賽排名頁與 /pvp-ranker/cups/ 賽程總覽），CI 不必另外加步驟。
頁面上的「資料更新」日期 = 這個聯盟 Top 100 內容最後一次改變的日期（台灣時間），
狀態存在 data/pvp_league_state.json；排名沒變就不改日期，也不會產生無意義的 commit。
同時更新 sitemap.xml 裡這三個網址的 <lastmod>（只改日期，不動其他內容）。

為什麼要有這頁：/pvp-ranker/ 是「輸入 IV 查排名」的互動工具，但搜尋「超級聯盟排名」的人要的是
一張看得到的強度榜。這頁是靜態榜單（Google 讀得到每一隻），每隻都連回工具（?p=<id> 直接帶入）。
"""
import json, os, re, html, hashlib, datetime, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pvpoke_credit import credit_html  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "data", "pvp_league_state.json")
SITEMAP = os.path.join(ROOT, "sitemap.xml")
BASE = "https://pogokit.com/pvp-ranker/"
TOP = 100
TW = datetime.timezone(datetime.timedelta(hours=8))
e = lambda s: html.escape(str(s), quote=True)

FAQ_SCORE = ("這份排名的分數怎麼來的？", "分數來自 PvPoke 的對戰模擬：讓每隻寶可夢用推薦招式，和整個聯盟的常見對手以各種護盾數對打，"
             "綜合勝率與表現算成 0～100 的分數。分數越高，代表在目前環境越全面，但實戰仍要看隊伍搭配與對手。")
FAQ_ELITE = ("「限定」招式是什麼意思？", "標「限定」的是限定招式：平常進化或用招式學習器學不到，只能在社群日等特定活動，或用厲害招式學習器學到。如果你的寶可夢沒有這個招式，強度會比排名低。")
FAQ_UPDATE = ("排名多久更新？", "本站每天會多次檢查 PvPoke 的最新排名，前 100 名有變動就自動重新產生這頁，頁首的「資料更新」就是最近一次變動的日期。"
              "賽季更換或招式平衡調整後，排名通常會明顯變動。")

LEAGUES = [
    {"slug": "great-league", "cp": 1500, "name": "超級聯盟", "short": "超級", "eyebrow": "GO 對戰聯盟 · CP 1500",
     "lede": "超級聯盟限制 CP 1500，比的不是誰 CP 高，而是屬性、招式和耐久的組合，很多中低階的寶可夢反而是主力。",
     "faq": [
         ("超級聯盟是什麼？", "Pokémon GO 對戰聯盟（GO Battle League）中，寶可夢 CP 上限 1500 的聯盟。因為 CP 被限制，"
          "強度看的是屬性、招式與耐久的組合，而不是單純的高 CP，很多中低階的寶可夢反而是主力。"),
         FAQ_SCORE, FAQ_ELITE,
         ("為什麼 PvP 要找低攻擊的 IV？", "CP 公式裡攻擊的權重最高。在 1500 的上限內，攻擊 IV 低、防禦與 HP 高的個體可以升到更高等級，"
          "總能力值（統計值乘積）反而更大。想知道你手上那隻的 IV 排第幾，可以用 PvP IV 排名工具查。"),
         FAQ_UPDATE]},
    {"slug": "ultra-league", "cp": 2500, "name": "高級聯盟", "short": "高級", "eyebrow": "GO 對戰聯盟 · CP 2500",
     "lede": "高級聯盟限制 CP 2500，是很多耐久型寶可夢與部分傳說寶可夢的舞台；不少寶可夢要用 XL 糖果升到 40 級以上才能接近上限。",
     "faq": [
         ("高級聯盟是什麼？", "Pokémon GO 對戰聯盟（GO Battle League）中，寶可夢 CP 上限 2500 的聯盟。比超級聯盟多了一些傳說寶可夢與高耐久的寶可夢，"
          "但同樣有 CP 上限，所以屬性、招式和耐久的搭配仍然比單純的高 CP 重要。"),
         FAQ_SCORE, FAQ_ELITE,
         ("高級聯盟要什麼樣的 IV？", "跟超級聯盟一樣，攻擊 IV 低、防禦與 HP 高的個體可以升到更高等級，總能力值更大。"
          "不過很多寶可夢就算 15/15/15 升到 50 級也碰不到 2500，這種情況三圍全滿就是最好。PvP IV 排名工具會直接算出你那隻排第幾。"),
         ("要準備多少 XL 糖果？", "超過 40 級要用 XL 糖果。高級聯盟裡不少寶可夢要升到 45～50 級才接近 CP 2500，需要的 XL 糖果很多；"
          "在 PvP IV 排名工具輸入 IV，就能看到牠要升到幾級、CP 多少。"),
         FAQ_UPDATE]},
    {"slug": "master-league", "cp": 10000, "name": "大師聯盟", "short": "大師", "eyebrow": "GO 對戰聯盟 · 無 CP 上限",
     "lede": "大師聯盟沒有 CP 上限，主角是傳說、幻之寶可夢與高種族值的寶可夢；能養多高就多高，IV 越高越好。",
     "faq": [
         ("大師聯盟是什麼？", "Pokémon GO 對戰聯盟（GO Battle League）中沒有 CP 上限的聯盟。因為不限 CP，"
          "種族值高的傳說、幻之寶可夢與大型寶可夢是主力，通常要升到 50 級（或最佳夥伴 51 級）才有競爭力。"),
         FAQ_SCORE, FAQ_ELITE,
         ("大師聯盟要什麼樣的 IV？", "沒有 CP 上限，所以攻擊、防禦、HP 都是越高越好，15/15/15 是最理想的。"
          "IV 差一兩點影響不大，但要升到 50 級需要大量 XL 糖果，是大師聯盟最大的門檻。"),
         FAQ_UPDATE]},
]


def league_url(lg):
    return BASE + lg["slug"] + "/"


def today_tw():
    return datetime.datetime.now(TW).date().isoformat()


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state):
    with open(STATE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def fingerprint(ranks):
    """只看頁面上會顯示的內容：名字、分數（一位小數）、招式與 ★、總收錄數。"""
    keys = ("name", "fastMove", "chargedMove1", "chargedMove2", "isEliteFast", "isEliteCharged1", "isEliteCharged2")
    rows = [[r.get(k) for k in keys] + [round(r["score"], 1)] for r in ranks[:TOP]]
    raw = json.dumps([len(ranks), rows], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def update_sitemap(dates):
    """把 sitemap.xml 裡各聯盟網址的 <lastmod> 改成資料更新日期；保留原本的換行字元。"""
    if not os.path.exists(SITEMAP):
        return
    with open(SITEMAP, encoding="utf-8", newline="") as f:
        xml = f.read()
    new = xml
    for url, d in dates.items():
        pat = re.compile(r"(<loc>" + re.escape(url) + r"</loc>\s*<lastmod>)[0-9-]+(</lastmod>)")
        new = pat.sub(lambda m: m.group(1) + d + m.group(2), new)
    if new != xml:
        with open(SITEMAP, "w", encoding="utf-8", newline="") as f:
            f.write(new)


TYPE_COLOR = {   # 屬性色（取自遊戲常見配色，調暗一點讓白字讀得清楚）
    "一般": "#8a8a6e", "火": "#e2662a", "水": "#3d7fe0", "草": "#4fa83d", "電": "#d4a90f", "冰": "#4cb5c4",
    "格鬥": "#b8352c", "毒": "#9a4aa8", "地面": "#c79b45", "飛行": "#7f8fe0", "超能力": "#e2557d", "蟲": "#8a9a1c",
    "岩石": "#a8923c", "幽靈": "#6550a0", "龍": "#5b3fe0", "惡": "#5a4a40", "鋼": "#7f8fa6", "妖精": "#d873b8",
}


def js_array(src, name):
    i = src.index(f"const {name} = ") + len(f"const {name} = ")
    return json.loads(src[i:src.index("];", i) + 1])


def resolve(r, dex):
    """排名裡的名字（例：「九尾 阿羅拉 暗影」「代歐奇希斯 防禦」）→ (顯示名, POKEDEX id, 是否暗影)。
    POKEDEX 不收暗影，暗影的 IV 排名與一般型相同，所以連到一般型。
    盃賽排名（build_pvp_cups.py）會多帶 PvPoke 的 speciesId（r["sid"]），有的話直接用它對 POKEDEX。
    超級進化照官方中文寫成「超級大嘴娃」「超級噴火龍（X）」。"""
    parts = r["name"].split(" ")
    shadow = "暗影" in parts[1:]
    mega = "Mega" in parts[1:]
    tokens = [t for t in parts[1:] if t not in ("暗影", "Mega")]
    cands = [p for p in dex if p["dexNumber"] == r["dex"]]
    pick = None
    sid = (r.get("sid") or "").replace("_shadow", "")
    if sid:
        pick = next((p for p in cands if p["id"] == sid), None)
    if not pick:
        for t in tokens:
            pick = next((p for p in cands if t in p["name"]), None) or pick
    if not pick:
        pick = next((p for p in cands if p["name"] == parts[0]), None) or (cands[0] if cands else None)
    disp = ("超級" if mega else "") + parts[0] + (f"（{'・'.join(tokens)}）" if tokens else "")
    return disp, (pick["id"] if pick else None), shadow


THUMB_DIR = os.path.join(ROOT, "trade-list", "assets", "thumb")
_THUMBS = None


def local_img(remote, dexno, sid=""):
    """站內交易清單的 128px webp 縮圖（同網域、檔案小）。data/pokemon_images.js 有些網址是壞的
    （例：謎擬Ｑ、古月鳥指向不存在的 imgur），所以優先用站內圖：
    先找與 PokeMiners 檔名相同的縮圖（超級進化先找 pm<dex>.fMEGA[_X/_Y]），再找 pm<dex>.icon，
    最後用該編號第一個非異色型態。"""
    global _THUMBS
    if _THUMBS is None:
        _THUMBS = set(os.listdir(THUMB_DIR)) if os.path.isdir(THUMB_DIR) else set()
    base = os.path.splitext(remote.rsplit("/", 1)[-1])[0] if "pogo_assets" in remote else ""
    m = re.search(r"_mega(_[xy])?(?:_|$)", sid)
    mega = [f"pm{dexno}.fMEGA{(m.group(1) or '').upper()}.icon.webp"] if m else []
    for name in mega + ([base + ".webp"] if base else []) + [f"pm{dexno}.icon.webp"]:
        if name in _THUMBS:
            return "../../trade-list/assets/thumb/" + name
    forms = sorted(n for n in _THUMBS if n.startswith(f"pm{dexno}.f") and n.endswith(".icon.webp") and ".s.icon" not in n)
    if forms:
        return "../../trade-list/assets/thumb/" + forms[0]
    return remote if remote.startswith("https://raw.githubusercontent.com/") else ""


MOVE_TYPES = None
TYPE_ICON = {t: ("超" if t == "超能力" else t[0]) for t in TYPE_COLOR}   # 圓點裡的一個字：火、水、超…


def move_type(name):
    """data/pvp_move_types.json（generate_pokemon_data.py 產生）：招式中文名 → 屬性。"""
    global MOVE_TYPES
    if MOVE_TYPES is None:
        try:
            with open(os.path.join(ROOT, "data", "pvp_move_types.json"), encoding="utf-8") as f:
                MOVE_TYPES = json.load(f)
        except (OSError, ValueError):
            MOVE_TYPES = {}
    return MOVE_TYPES.get(name, "")


def move(name, elite, kind):
    t = move_type(name)
    attrs = f' style="--c:{TYPE_COLOR[t]}" data-ti="{e(TYPE_ICON[t])}" title="{e(t)}屬性"' if t in TYPE_COLOR else ' data-ti="?"'
    tag = '<em>限定</em>' if elite else ''
    return f'<span class="mv {kind}{" elite" if elite else ""}"{attrs}>{e(name)}{tag}</span>'


def row(i, r, dex, imgs, ivlink=True):
    disp, pid, shadow = resolve(r, dex)
    img = local_img(imgs.get(pid, "") if pid else "", r["dex"], r.get("sid", ""))
    types = [t for t in (r["type1"], r["type2"]) if t]
    tchips = "".join(f'<span class="ty" style="--c:{TYPE_COLOR.get(t, "#777")}">{e(t)}</span>' for t in types)
    charged = move(r["chargedMove1"], r["isEliteCharged1"], "cg")
    if r.get("chargedMove2"):
        charged += move(r["chargedMove2"], r["isEliteCharged2"], "cg")
    link = f'../?p={e(pid)}' if pid else "../"
    pic = ""
    if img:
        lazy = "eager" if i <= 6 else "lazy"
        pic = (f'<img src="{e(img)}" alt="{e(disp)}{"（暗影）" if shadow else ""}" width="76" height="76" loading="{lazy}" '
               f'decoding="async" referrerpolicy="no-referrer">')
    sd = '<span class="sd">暗影</span>' if shadow else ""
    medal = ' m1' if i == 1 else ' m2' if i == 2 else ' m3' if i == 3 else ''
    sh = ' is-sh' if shadow else ''
    return (f'<li class="r{medal}{sh}" data-t="{e(" ".join(types))}"{" data-s" if shadow else ""}>'
            f'<span class="pic{" sh" if shadow else ""}">{pic}<b class="no" aria-label="第 {i} 名">{i}</b></span>'
            f'<span class="who"><b class="nm">{e(disp)}</b>{sd}<span class="tys">{tchips}</span></span>'
            f'<span class="sc"><b>{r["score"]:.1f}</b><i><i style="width:{max(0, min(100, r["score"])):.1f}%"></i></i></span>'
            f'<span class="mvs"><span class="ml"><span class="k">一般</span>{move(r["fastMove"], r["isEliteFast"], "fm")}</span>'
            f'<span class="ml"><span class="k">特殊</span>{charged}</span></span>'
            + (f'<a class="go" href="{link}" aria-label="查{e(disp)}的 PvP IV 排名">查 IV</a>' if ivlink else '')
            + '</li>')


def render_page(o):
    """聯盟頁與盃賽頁共用的版面。o 是 dict：
    slug, url, title, desc, h1, eyebrow, lede（HTML）, chips（HTML）, tabs（HTML）, crumb（HTML，最後一層）,
    ranks（全部）, top, faq [(q, a)], faq_h, more（HTML）, next_p（HTML）, ld（list）,
    可選：extra（HTML，放在榜單前）, ivlink, extra_css, data_attrs（hero 上的 data-*）。"""
    dex, imgs = o["dex"], o["imgs"]
    top = o["top"]
    ivlink = o.get("ivlink", True)
    rows = "\n".join(row(i, r, dex, imgs, ivlink) for i, r in enumerate(top, 1))
    types = sorted({t for r in top for t in (r["type1"], r["type2"]) if t}, key=lambda t: list(TYPE_COLOR).index(t) if t in TYPE_COLOR else 99)
    tbtns = "".join(f'<button class="tf" data-t="{e(t)}" style="--c:{TYPE_COLOR.get(t, "#777")}">{e(t)}</button>' for t in types)
    # 盃賽常常沒有暗影（或全部都是同一種屬性），沒有東西可篩的按鈕就不放
    has_sh = any("暗影" in r["name"].split(" ")[1:] for r in top)
    sf = '<button class="sf" type="button" aria-pressed="false">只看暗影</button>' if has_sh else ''
    tbtns = f'<button class="tf on" data-t="">全部屬性</button>{tbtns}' if len(types) > 1 else ''
    tools = (f'<div class="tools">\n      <div class="tfs" role="group" aria-label="篩選">{sf}{tbtns}</div>\n'
             f'      <p class="cnt" id="cnt" aria-live="polite"></p>\n    </div>') if (sf or tbtns) else '<p class="cnt" id="cnt" aria-live="polite"></p>'
    faq_html = "\n".join(f'<details class="qa"><summary>{e(q)}</summary><p>{e(a)}</p></details>' for q, a in o["faq"])
    ld = json.dumps(o["ld"], ensure_ascii=False)
    extra = o.get("extra", "")
    page = f'''<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8866689605007086" crossorigin="anonymous"></script>
<script src="../../js/analytics.js"></script>
<script src="../../config.js"></script>
<script src="../../js/pageview-counter.js" defer></script>
<link rel="icon" type="image/png" sizes="192x192" href="../../img/masterball.png">
<title>{e(o["title"])}｜Pokémon Go 工具箱</title>
<meta name="description" content="{e(o["desc"])}">
<link rel="canonical" href="{o["url"]}">
<meta name="robots" content="index,follow">
<meta property="og:type" content="article">
<meta property="og:title" content="{e(o["title"])}">
<meta property="og:description" content="{e(o["desc"])}">
<meta property="og:url" content="{o["url"]}">
<script type="application/ld+json">{ld}</script>
<style>{CSS}{o.get("extra_css", "")}</style>
</head>
<body>
<header class="topbar">
  <a class="home" href="../../"><span class="logo" aria-hidden="true">🧰</span><span>Pokémon Go 工具箱</span></a>
  <nav class="tnav" aria-label="相關工具"><a href="../">PvP IV 排名查詢</a><a href="../cups/">盃賽排名</a><a href="../../backgrounds/">背卡一覽</a></nav>
  <a class="cta" href="../../trade-list/">做交換清單</a>
</header>

<main>
  <nav class="crumb" aria-label="導覽路徑"><a href="../../">Pokémon Go 工具箱</a> › <a href="../">PvP IV 排名</a> › {o["crumb"]}</nav>
  <nav class="lgs" aria-label="切換聯盟與盃賽">{o["tabs"]}</nav>
  <section class="hero"{o.get("data_attrs", "")}>
    <p class="eyebrow">{e(o["eyebrow"])}</p>
    <h1>{e(o["h1"])}</h1>
    <p class="lede">{o["lede"]}</p>
    <ul class="chips">{o["chips"]}</ul>
  </section>
{extra}
  <section class="board">
    {tools}
    <ol class="list" id="list">
{rows}
    </ol>
    <p class="more">{o["more"]}</p>
  </section>

  <section class="faq">
    <h2>{e(o["faq_h"])}</h2>
{faq_html}
  </section>

  <section class="next">
    <div><h2>找到想練的寶可夢了？</h2><p>{o["next_p"]}</p></div>
    <a class="bigcta" href="../">查我的 PvP IV 排名 →</a>
  </section>
</main>

<footer class="foot">
  <p>{credit_html("zh")}非官方資料，僅供參考。</p>
  <p>本站為非官方同人工具，與 Pokémon GO／Niantic 無隸屬關係。Pokémon 及其商標為 &copy;1995-2026 Nintendo, Creatures, GAME FREAK 所有。</p>
  <p><a href="../../about/">關於本站</a> · <a href="../../contact/">聯絡我們</a> · <a href="../../privacy/">隱私權政策</a> · <a href="../../disclaimer/">免責聲明</a> · <a href="../../">回工具箱</a></p>
</footer>

<script>{JS}{o.get("extra_js", "")}</script>
<script src="../../js/ads.js" defer></script>
</body>
</html>
'''
    out_dir = os.path.join(ROOT, "pvp-ranker", o["slug"])
    out = os.path.join(out_dir, "index.html")
    os.makedirs(out_dir, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    unmapped = [r["name"] for r in top if not resolve(r, dex)[1]]
    print(f"已寫出 pvp-ranker/{o['slug']}/index.html（{os.path.getsize(out):,} bytes），第 1 名 {resolve(top[0], dex)[0]}")
    if unmapped:
        print("  ⚠ 對不到 POKEDEX（沒有圖、連到工具首頁）：", unmapped)


def nav_tabs(current):
    """聯盟頁、盃賽頁、賽程總覽共用的切換列：本季賽程、三個聯盟、所有盃賽（目前這頁標 aria-current）。"""
    from build_pvp_cups import CUPS, HUB   # 盃賽清單在 build_pvp_cups.py（它也 import 本檔，所以放函式裡）
    items = [(HUB, "本季賽程")] + [(o["slug"], o["name"]) for o in LEAGUES] + [(c["slug"], c["short"]) for c in CUPS]
    return "".join(f'<a href="../{s}/" aria-current="page">{e(n)}</a>' if s == current else f'<a href="../{s}/">{e(n)}</a>'
                   for s, n in items)


def build_league(lg, src, dex, imgs, date):
    ranks = js_array(src, f"POKEMON_RANKINGS_{lg['cp']}")
    top = ranks[:TOP]
    name, url = lg["name"], league_url(lg)
    top3 = "、".join(resolve(r, dex)[0] for r in top[:3])
    month = f"{int(date[:4])} 年 {int(date[5:7])} 月"
    cap = "無 CP 上限" if lg["cp"] == 10000 else f"CP {lg['cp']}"
    title = f"Pokémon GO {name}排名 Top {TOP}｜PvP 強度排行與推薦招式（{month}）"
    desc = (f"Pokémon GO {name}（{cap}）寶可夢強度排名前 {TOP} 名：目前前三名是 {top3}。"
            f"列出每隻的屬性、推薦一般與特殊招式（含限定招式標示），點一下就能查自己那隻的 PvP IV 排名。")
    faq = lg["faq"]
    tabs = nav_tabs(lg["slug"])
    others = "、".join(f'<a href="../{o["slug"]}/">{e(o["name"])}排名</a>' for o in LEAGUES if o is not lg)
    ld = [
        {"@context": "https://schema.org", "@type": "Article", "headline": f"Pokémon GO {name}排名 Top {TOP}",
         "description": desc, "inLanguage": "zh-Hant", "dateModified": date, "mainEntityOfPage": url},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Pokémon Go 工具箱", "item": "https://pogokit.com/"},
            {"@type": "ListItem", "position": 2, "name": "PvP IV 排名", "item": BASE},
            {"@type": "ListItem", "position": 3, "name": f"{name}排名", "item": url}]},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]},
    ]
    render_page({
        "slug": lg["slug"], "url": url, "title": title, "desc": desc, "dex": dex, "imgs": imgs,
        "h1": f"Pokémon GO {name}排名 Top {TOP}", "eyebrow": lg["eyebrow"],
        "lede": (f'{e(lg["lede"])}這份榜單依 PvPoke 對戰模擬的分數排序，\n'
                 f'    列出前 {TOP} 名寶可夢與推薦招式；想知道你手上那隻的 IV 排第幾，點右邊的「查 IV」直接帶入。'),
        "chips": (f'<li>資料更新 <b>{date}</b></li><li>收錄 <b>{len(ranks)}</b> 隻・顯示前 <b>{TOP}</b> 名</li>'
                  f'<li><b class="lt">限定</b> 限定招式</li>'),
        "tabs": tabs, "crumb": f"<span>{e(name)}排名</span>",
        "ranks": ranks, "top": top, "faq": faq, "faq_h": f"{name}常見問題", "ld": ld,
        "more": (f'完整排名（{len(ranks)} 隻）與自己的 IV 名次，請用 <a href="../">PvP IV 排名查詢工具</a>。'
                 f'也可以看{others}，或本季的<a href="../cups/">盃賽排名</a>。'),
        "next_p": f"用 PvP IV 排名工具查你手上那隻的 IV 在{e(name)}排第幾，以及要升到幾級、CP 多少。",
    })


def build():
    src = open(os.path.join(ROOT, "data", "pokemon_data_and_rankings.js"), encoding="utf-8").read()
    dex = js_array(src, "POKEDEX")
    img_src = open(os.path.join(ROOT, "data", "pokemon_images.js"), encoding="utf-8").read()
    imgs = json.loads(img_src[img_src.index("{"):img_src.rindex("}") + 1])
    state, today, dates = load_state(), today_tw(), {}
    for lg in LEAGUES:
        fp = fingerprint(js_array(src, f"POKEMON_RANKINGS_{lg['cp']}"))
        st = state.get(lg["slug"])
        if not st or st.get("hash") != fp:
            st = state[lg["slug"]] = {"hash": fp, "date": today}
        build_league(lg, src, dex, imgs, st["date"])
        dates[league_url(lg)] = st["date"]
    save_state(state)
    update_sitemap(dates)


JS = r"""
(function(){var b=[].slice.call(document.querySelectorAll('.tf')),li=[].slice.call(document.querySelectorAll('#list .r')),
c=document.getElementById('cnt'),sf=document.querySelector('.sf'),t='',so=false;
function go(){var n=0;li.forEach(function(x){var s=(!t||(' '+x.dataset.t+' ').indexOf(' '+t+' ')>-1)&&(!so||x.hasAttribute('data-s'));
x.hidden=!s;if(s)n++;});c.textContent=(so?'暗影・':'')+(t?t+'屬性 ':'')+(t||so?n+' 隻':'共 '+li.length+' 隻');}
b.forEach(function(x){x.addEventListener('click',function(){t=x.dataset.t;b.forEach(function(y){y.classList.toggle('on',y===x);});go();
if(window.track)track('league_filter',{type:t||'all'});});});
if(sf)sf.addEventListener('click',function(){so=!so;sf.setAttribute('aria-pressed',so);sf.classList.toggle('on',so);go();
if(window.track)track('league_filter',{type:so?'shadow_on':'shadow_off'});});go();var a=document.querySelector('.lgs [aria-current]');if(a){var n=a.parentNode;n.scrollLeft=a.offsetLeft-n.offsetLeft-(n.clientWidth-a.offsetWidth)/2;}})();
"""

CSS = r"""
:root{--ink:#14111f;--ink-2:#3b3650;--muted:#6b6680;--line:#e7e4ef;--bg:#f6f4fa;--brand:#e0276c;--brand2:#7b5cff;--grad:linear-gradient(135deg,var(--brand),var(--brand2));--head-h:60px}
*{box-sizing:border-box}[hidden]{display:none!important}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans TC","Microsoft JhengHei",sans-serif;-webkit-font-smoothing:antialiased}
a{color:#5b3fd6}
.topbar{position:sticky;top:0;z-index:30;height:var(--head-h);display:flex;align-items:center;gap:14px;padding:0 max(16px,calc((100% - 1000px)/2));background:rgba(255,255,255,.86);backdrop-filter:saturate(1.6) blur(14px);-webkit-backdrop-filter:saturate(1.6) blur(14px);border-bottom:1px solid rgba(20,17,31,.07)}
.topbar .home{display:flex;align-items:center;gap:10px;margin-right:auto;color:var(--ink);text-decoration:none;font-weight:750;font-size:15.5px;white-space:nowrap}
.logo{display:grid;place-items:center;width:32px;height:32px;border-radius:10px;background:var(--grad);font-size:16px}
.tnav{display:flex;gap:4px}.tnav a{padding:6px 12px;border-radius:999px;color:var(--ink-2);text-decoration:none;font-size:14px;font-weight:600}.tnav a:hover{background:rgba(20,17,31,.05)}
.topbar .cta{padding:8px 16px;border-radius:999px;background:var(--ink);color:#fff;text-decoration:none;font-weight:700;font-size:14px;white-space:nowrap}
main{max-width:1000px;margin:0 auto;padding:14px 16px 64px}
.crumb{font-size:13px;color:var(--muted);margin:0 0 12px}.crumb a{color:var(--muted)}
.lgs{display:flex;gap:6px;margin:0 0 12px;overflow-x:auto;scrollbar-width:none}.lgs::-webkit-scrollbar{display:none}
.lgs a{flex:none;padding:7px 16px;border-radius:999px;background:#fff;border:1px solid var(--line);color:var(--ink-2);text-decoration:none;font-weight:750;font-size:.9rem}.lgs a[aria-current]{background:var(--ink);border-color:var(--ink);color:#fff}
.hero{position:relative;overflow:hidden;padding:40px 44px;border-radius:28px;color:#d9d4ea;background:radial-gradient(50% 80% at 100% 0%,rgba(123,92,255,.55),transparent 70%),radial-gradient(45% 70% at 0% 100%,rgba(224,39,108,.45),transparent 70%),#0d0a1a}
.eyebrow{margin:0 0 12px;color:#f9a8d4;font-size:13px;font-weight:750;letter-spacing:.16em}
.hero h1{margin:0 0 12px;color:#fff;font-size:clamp(1.9rem,4.6vw,3rem);line-height:1.12;letter-spacing:-.03em;font-weight:900;text-wrap:balance}
.lede{margin:0;max-width:44em;color:#bdb6d3;font-size:1rem;line-height:1.85}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0 0;padding:0;list-style:none}
.chips li{padding:5px 13px;border-radius:999px;font-size:.86rem;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12)}.chips b{color:#fff}
.board{margin-top:22px}
.tools{position:sticky;top:var(--head-h);z-index:20;margin:0 -16px;padding:10px 16px;background:var(--bg);box-shadow:0 6px 10px -10px rgba(20,17,31,.35)}
.tfs{display:flex;flex-wrap:wrap;gap:6px}
.tf{flex:none;padding:6px 13px;border:1px solid var(--line);border-radius:999px;background:#fff;color:var(--ink-2);font:inherit;font-size:.86rem;font-weight:700;cursor:pointer}
.tf[style]{border-color:color-mix(in srgb,var(--c) 35%,#fff);color:var(--c)}
.tf.on{background:var(--ink);border-color:var(--ink);color:#fff}.tf[style].on{background:var(--c);border-color:var(--c);color:#fff}
.sf{flex:none;padding:6px 13px;border:1px solid #c9b5f5;border-radius:999px;background:#f3edff;color:#6d28d9;font:inherit;font-size:.86rem;font-weight:800;cursor:pointer;margin-right:4px}.sf.on{background:#6d28d9;border-color:#6d28d9;color:#fff}
.cnt{margin:8px 0 0;color:var(--muted);font-size:.84rem}
.list{list-style:none;margin:8px 0 0;padding:0;display:grid;gap:10px}
.r{display:grid;grid-template-columns:76px minmax(0,1fr) 96px minmax(0,1.55fr) auto;grid-template-areas:"pic who sc mv go";align-items:center;gap:8px 16px;padding:12px 16px 12px 12px;background:#fff;border-radius:18px;box-shadow:0 1px 2px rgba(20,17,31,.06),0 6px 18px -14px rgba(20,17,31,.25)}
.m1,.m2,.m3{box-shadow:0 0 0 2px #f3e3a8,0 10px 26px -12px rgba(232,163,23,.45)}
.r.is-sh{background:linear-gradient(90deg,#f4edff,#fff 45%);box-shadow:inset 4px 0 0 #8b5cf6,0 1px 2px rgba(20,17,31,.06),0 6px 18px -14px rgba(76,29,149,.4)}
.r.is-sh.m1,.r.is-sh.m2,.r.is-sh.m3{box-shadow:inset 4px 0 0 #8b5cf6,0 0 0 2px #f3e3a8,0 10px 26px -12px rgba(232,163,23,.45)}
.pic{grid-area:pic;position:relative;display:block;width:76px;height:76px;border-radius:18px;overflow:hidden;background:radial-gradient(70% 70% at 50% 40%,#fff,#ece8f6)}
.pic img{width:100%;height:100%;object-fit:contain;transform:scale(1.18)}
.pic.sh{background:radial-gradient(75% 75% at 50% 45%,#7c4ddb,#2e1458 68%,#160a2c)}
.pic.sh img{filter:drop-shadow(0 0 4px rgba(214,180,255,.95)) drop-shadow(0 0 10px rgba(167,110,255,.7))}
.pic.sh::after{content:"暗影";position:absolute;right:0;bottom:0;padding:0 7px;border-radius:9px 0 0 0;background:#7c3aed;color:#fff;font-size:.66rem;font-weight:900;line-height:1.7}
.no{position:absolute;left:0;top:0;min-width:28px;height:24px;padding:0 6px;border-radius:0 0 10px 0;background:rgba(20,17,31,.72);color:#fff;font-size:.78rem;font-weight:900;line-height:24px;text-align:center;font-variant-numeric:tabular-nums}
.m1 .no{background:linear-gradient(135deg,#f7c948,#e8a317)}.m2 .no{background:linear-gradient(135deg,#cfd6e0,#8e9aae)}.m3 .no{background:linear-gradient(135deg,#e6a26c,#b86b34)}
.who{grid-area:who;min-width:0}.nm{font-size:1.05rem;font-weight:850;line-height:1.35}
.sd{display:inline-block;margin-left:6px;padding:0 8px;border-radius:999px;background:#6d28d9;color:#fff;font-size:.72rem;font-weight:800;line-height:1.6;vertical-align:2px}
.tys{display:flex;flex-wrap:wrap;gap:4px;margin-top:5px}.ty{padding:1px 9px;border-radius:999px;background:var(--c);color:#fff;font-size:.74rem;font-weight:800;line-height:1.55}
.sc{grid-area:sc;display:block}.sc b{display:block;font-size:1.35rem;font-weight:900;line-height:1.1;color:#5b3fd6;font-variant-numeric:tabular-nums}
.sc>i{display:block;height:4px;margin-top:6px;border-radius:4px;background:#ece8f6;overflow:hidden}.sc>i>i{display:block;height:100%;border-radius:4px;background:linear-gradient(90deg,#a78bfa,#6d4aff)}
.mvs{grid-area:mv;display:grid;gap:6px;min-width:0}
.ml{display:flex;flex-wrap:wrap;align-items:center;gap:5px 6px}
.ml .k{flex:none;width:2.4em;color:var(--muted);font-size:.72rem;font-weight:800}
.mv{--c:#8a8a9a;display:inline-flex;align-items:center;gap:5px;padding:2px 10px 2px 3px;border-radius:999px;font-size:.86rem;font-weight:750;line-height:1.5;color:color-mix(in srgb,var(--c) 55%,#000);background:color-mix(in srgb,var(--c) 12%,#fff);border:1px solid color-mix(in srgb,var(--c) 35%,#fff)}
.mv::before{content:attr(data-ti);flex:none;display:grid;place-items:center;width:19px;height:19px;border-radius:50%;background:var(--c);color:#fff;font-size:.66rem;font-weight:900;line-height:1}
.mv.cg{border-radius:8px}.mv.cg::before{border-radius:6px}
.mv em,.lt{font-style:normal;margin-left:2px;padding:0 5px;border-radius:5px;background:linear-gradient(135deg,#f7c948,#e8a317);color:#fff;font-size:.68rem;font-weight:900;line-height:1.6}
.mv.elite{border-color:#e8b93a;box-shadow:0 0 0 1px rgba(232,185,58,.35)}
.go{grid-area:go;display:inline-flex;align-items:center;justify-content:center;min-height:38px;padding:0 14px;border-radius:999px;background:var(--grad);color:#fff;text-decoration:none;font-weight:800;font-size:.84rem;white-space:nowrap}
.more{margin:18px 0 0;color:var(--muted);font-size:.92rem;text-align:center}
.faq{margin-top:56px}.faq h2{font-size:1.5rem;letter-spacing:-.02em;margin:0 0 12px}
.qa{background:#fff;border-radius:16px;padding:4px 18px;margin:0 0 10px;box-shadow:0 1px 2px rgba(20,17,31,.06)}
.qa summary{cursor:pointer;padding:12px 0;font-weight:800}.qa p{margin:0 0 14px;color:var(--ink-2)}
.next{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-top:40px;padding:30px 36px;border-radius:26px;color:#d9d4ea;background:radial-gradient(60% 120% at 100% 0%,rgba(123,92,255,.55),transparent 60%),#0d0a1a}
.next h2{color:#fff;margin:0 0 6px}.next p{margin:0}
.bigcta{flex:none;padding:13px 24px;border-radius:999px;background:#fff;color:var(--ink);text-decoration:none;font-weight:800;white-space:nowrap}
.foot{border-top:1px solid var(--line);padding:26px 16px 40px;color:var(--muted);font-size:.84rem;text-align:center}.foot p{margin:6px auto;max-width:760px}.foot a{color:var(--ink-2)}
@media(max-width:760px){
 :root{--head-h:54px}.tnav{display:none}main{padding:10px 12px 56px}
 .topbar .home{font-size:14.5px}.logo{width:28px;height:28px;font-size:14px}.topbar .cta{padding:7px 13px;font-size:13px}
 .hero{padding:26px 20px;border-radius:22px}.lede{font-size:.94rem}
 .tools{position:static;box-shadow:none;margin:0;padding:4px 0}.tfs{gap:5px}.tf,.sf{padding:4px 10px;font-size:.8rem}
 .r{grid-template-columns:76px minmax(0,1fr) auto;grid-template-areas:"pic who sc" "pic who go" "mv mv mv";gap:6px 12px;padding:12px}
 .pic{align-self:start}.sc{text-align:right;min-width:64px}.go{align-self:end;min-height:36px;padding:0 13px;font-size:.8rem}
 .mvs{padding-top:9px;border-top:1px solid #f0eef5}
 .next{flex-direction:column;align-items:flex-start;padding:24px 20px}
}
"""

if __name__ == "__main__":
    build()
    # 盃賽排名頁（/pvp-ranker/cups/ 與各盃賽）。放在這裡跑，CI 不用另外加步驟；
    # 盃賽抓不到或壞掉不影響上面三個聯盟頁，頁面維持上一版。
    try:
        import build_pvp_cups
        build_pvp_cups.build()
    except Exception as ex:  # noqa: BLE001
        print(f"::warning::盃賽排名頁沒有更新（{type(ex).__name__}: {ex}），維持上一版")
    # 偽百查詢頁（/fake-hundo/）：種族值由前面的 refresh_cp_data.py 更新，新寶可夢或平衡調整時要跟著重算。
    try:
        import build_fake_hundo
        build_fake_hundo.build()
    except Exception as ex:  # noqa: BLE001
        print(f"::warning::偽百查詢頁沒有更新（{type(ex).__name__}: {ex}），維持上一版")
