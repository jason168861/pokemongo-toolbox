# -*- coding: utf-8 -*-
"""活動頁產生器：data/events/<slug>.json → events/<slug>/index.html（完整靜態 HTML）。

同時重產：
  · events/index.html（活動總覽，卡片直接寫在 HTML 裡）
  · sitemap.xml 的 /events/ 區塊（lastmod 用各活動 JSON 的 updated，不再看檔案時間）

內容全部在初始 HTML 裡（SEO），js/events.js 只負責倒數、狀態、異色切換、目錄高亮、分享。
圖片一律用站內檔案：寶可夢 img/pokemon/、trade-list/assets/thumb/，道具 img/items/，橫幅 img/events/。

舊版（js/community-day.js 渲染）的 6、9 月頁面還沒轉成 JSON，總覽卡片用下方 LEGACY。

用法：python scripts/build_event_pages.py
"""
import ast
import html
import json
import math
import os
import re
import sys
from datetime import datetime
from urllib.parse import quote

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "events")
BASE = "https://pogokit.com"
SITE_NAME = "Pokémon Go 工具箱"

# 還沒轉成 JSON 的舊頁（舊渲染器），只用來產生總覽卡片與 sitemap
LEGACY = [
    {"slug": "26-09-communityday", "kind": "經典社群日", "title": "圓陸鯊社群日經典版", "dex": 443,
     "types": ["dragon", "ground"], "start": "2026-09-12T14:00", "end": "2026-09-12T17:00",
     "banner": "26-09-communityday", "updated": "2026-09-12"},
    {"slug": "26-06-communityday", "kind": "社群日", "title": "涼脊龍社群日", "dex": 996,
     "types": ["dragon", "ice"], "start": "2026-06-20T14:00", "end": "2026-06-20T17:00",
     "banner": "26-06-communityday", "updated": "2026-09-12"},
]

TYPES = {  # 中文、主色
    "normal": ("一般", "#9099a1"), "fire": ("火", "#f08b3e"), "water": ("水", "#4d90d5"),
    "electric": ("電", "#e9c22b"), "grass": ("草", "#5fb95a"), "ice": ("冰", "#62c4b8"),
    "fighting": ("格鬥", "#ce4069"), "poison": ("毒", "#a865c9"), "ground": ("地面", "#d48444"),
    "flying": ("飛行", "#8aa4dc"), "psychic": ("超能力", "#f2707a"), "bug": ("蟲", "#8db82f"),
    "rock": ("岩石", "#bfae7c"), "ghost": ("幽靈", "#5a6db0"), "dragon": ("龍", "#2f72c4"),
    "dark": ("惡", "#5a5366"), "steel": ("鋼", "#5a8ea1"), "fairy": ("妖精", "#e48fdc"),
}

ITEMS = {  # key → (名稱, 圖檔；None 表示用文字徽章)
    "ultra-ball": ("高級球", "ultra-ball"), "great-ball": ("超級球", "great-ball"),
    "pinap": ("凰梨果", "pinap"), "silver-pinap": ("銀色凰梨果", "silver-pinap"),
    "stardust": ("星星沙子", "stardust"), "incubator": ("孵化器", "incubator"),
    "incense": ("薰香", "incense"), "charged-tm": ("特殊招式學習器", "charged-tm"),
    "rocket-radar": ("火箭隊雷達", "rocket-radar"), "premium-pass": ("特級對戰入場券", "premium-pass"),
    "rare-candy": ("神奇糖果", "rare-candy"), "rare-candy-xl": ("神奇糖果XL", "rare-candy-xl"),
    "candy": ("糖果", "candy"), "candy-xl": ("糖果XL", "candy-xl"),
    "star-piece": ("星星碎片", "star-piece"), "lucky-egg": ("幸運蛋", "lucky-egg"),
    "xp": ("XP", None),
}

# 等級 → 這個等級在遊戲裡代表什麼（CP 表用）
CP_LEVELS = [(15, "田野／特殊調查獎勵"), (20, "團體戰、孵蛋"), (25, "團體戰（天氣加成）"),
             (30, "野生最高"), (35, "野生最高（天氣加成）")]

WEEK = "一二三四五六日"


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def write(p, text):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


# ---------------------------------------------------------------- 資料
def load_cp():
    t = read(os.path.join(ROOT, "data", "precomputed_pokemon_cp.js"))
    rows = ast.literal_eval(t[t.index("["):t.index("];") + 1])
    cpm = json.loads(re.search(r"const CP_MULTIPLIER = (\[.*?\]);", t, re.S).group(1))
    by_dex = {}
    for r in rows:   # 每個 dex 取基本型（名稱沒有括號的那筆優先）
        cur = by_dex.get(r["id"])
        if cur is None or ("(" in cur["name"] and "(" not in r["name"]):
            by_dex[r["id"]] = r
    return by_dex, cpm


def load_cp_static():
    p = os.path.join(ROOT, "js", "cp-static-slugs.js")
    if not os.path.exists(p):
        return {}
    return dict(re.findall(r'\["([^"]+)", "([^"]+)"\]', read(p)))


CP_ROWS, CPM = load_cp()
CP_STATIC = load_cp_static()


def cp_at(dex, level):
    r = CP_ROWS[dex]
    return max(10, int((r["atk"] + 15) * math.sqrt(r["def"] + 15) * math.sqrt(r["sta"] + 15)
                       * CPM[level - 1] ** 2 / 10))


def parse_dt(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M")


# ---------------------------------------------------------------- 小元件
def mon_name(ev, dex):
    return (ev.get("names") or {}).get(str(dex)) or CP_ROWS[dex]["name"]


POGO_ICONS = os.path.join(os.path.dirname(ROOT), "pogo_assets", "Images", "Pokemon - 256x256", "Addressable Assets")
MON_PX = 160


def ensure_mon_img(dex, shiny):
    """img/pokemon/pm<dex>[.s].webp：裁掉官方圖示四周的留白再縮成 160px（原圖主體只佔 6 成，放在卡片裡會顯得很小）。
    來源優先用同層 ../pogo_assets 的 256px 圖示，沒有就用 trade-list 的 128px 縮圖。已存在就不重做。"""
    s = ".s" if shiny else ""
    out = os.path.join(ROOT, "img", "pokemon", f"pm{dex}{s}.webp")
    if os.path.exists(out):
        return True
    srcs = [os.path.join(POGO_ICONS, f"pm{dex}{s}.icon.png"),
            os.path.join(ROOT, "trade-list", "assets", "thumb", f"pm{dex}{s}.icon.webp")]
    src = next((p for p in srcs if os.path.exists(p)), None)
    if not src:
        return False
    try:
        from PIL import Image
    except ImportError:
        return False
    im = Image.open(src).convert("RGBA")
    im = im.crop(im.getbbox())
    side = int(max(im.size) * 1.06)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - im.width) // 2, side - im.height - (side - max(im.size)) // 2), im)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    canvas.resize((MON_PX, MON_PX), Image.LANCZOS).save(out, quality=86, method=6)
    return True


def mon_img(dex, shiny=False, big=False, p="../../"):
    s = ".s" if shiny else ""
    if ensure_mon_img(dex, shiny):
        return f"{p}img/pokemon/pm{dex}{s}.webp"
    return f"{p}trade-list/assets/thumb/pm{dex}{s}.icon.webp"


def cp_link(dex, prefix="../../"):
    name = CP_ROWS[dex]["name"]
    if name in CP_STATIC:
        return f"{prefix}cp/{CP_STATIC[name]}/"
    return f"{prefix}?tab=cp-checker-app&mon=" + quote(name, safe="")


def type_chips(types):
    return "".join(f'<span class="ev-type" style="--tc:{TYPES[t][1]}">{TYPES[t][0]}</span>' for t in types)


ICON_SVG = {
    "clock": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 7v5l3 2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    "ticket": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 8a2 2 0 0 0 2-2h14a2 2 0 0 0 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 0-2 2H5a2 2 0 0 0-2-2v-2a2 2 0 0 0 0-4z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M14 7v10" stroke="currentColor" stroke-width="2" stroke-dasharray="2 2"/></svg>',
    "move": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20 15 9m-3-5 8 8-3 1-6-6zM4 20l3-1-2-2z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/></svg>',
    "trade": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8h13l-3-3M20 16H7l3 3" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "cal": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5" width="17" height="15" rx="3" fill="none" stroke="currentColor" stroke-width="2"/><path d="M8 3v4M16 3v4M3.5 10h17M12 13v4M10 15h4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    "share": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 15V4m0 0L8 8m4-4 4 4M6 12v6a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "spark": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2l2.2 6.6L21 11l-6.8 2.4L12 20l-2.2-6.6L3 11l6.8-2.4z" fill="currentColor"/></svg>',
}


def icon(key, ev=None):
    """bonus / highlight 圖示：道具圖、主角圖或內建 SVG。"""
    if key.startswith("mon:"):
        d = int(key[4:])
        return f'<img src="{mon_img(d)}" alt="" width="40" height="40" loading="lazy">'
    if key == "spawn" and ev:
        return f'<img src="{mon_img(ev["featured"])}" alt="" width="40" height="40" loading="lazy">'
    if key in ICON_SVG:
        return f'<span class="ev-svg">{ICON_SVG[key]}</span>'
    item = ITEMS.get(key)
    fn = item[1] if item and item[1] else key
    if os.path.exists(os.path.join(ROOT, "img", "items", f"{fn}.webp")):
        return f'<img src="../../img/items/{fn}.webp" alt="" width="40" height="40" loading="lazy">'
    print(f"⚠ 找不到圖示 {key}，改用星形")
    return f'<span class="ev-svg">{ICON_SVG["spark"]}</span>'


def reward_chip(ev, r, with_name=True):
    """任務獎勵：寶可夢（附 Lv15 CP）或道具 ×數量。"""
    if "mon" in r and "item" not in r:
        d = r["mon"]
        bg = '<span class="ev-bgtag" title="附特別背卡">背卡</span>' if r.get("bg") else ""
        cp = f'<small>CP {cp_at(d, 15)}</small>' if with_name else ""
        nm = f'<b>{esc(mon_name(ev, d))}</b>' if with_name else ""
        return (f'<span class="ev-rw ev-rw-mon{" has-bg" if r.get("bg") else ""}">'
                f'<img src="{mon_img(d)}" alt="{esc(mon_name(ev, d))}" width="44" height="44" loading="lazy">'
                f'{bg}<span class="ev-rw-t">{nm}{cp}</span></span>')
    key = r["item"]
    name, img = ITEMS[key]
    if key in ("candy", "candy-xl") and r.get("mon"):
        name = f"{mon_name(ev, r['mon'])}的{name}"
    n = r.get("n")
    qty = f"×{n:,}" if n else ""
    pic = (f'<img src="../../img/items/{img}.webp" alt="" width="44" height="44" loading="lazy">' if img
           else f'<span class="ev-xp">{esc(name)}</span>')
    label = f'<b>{esc(name)}</b>' if with_name else ""
    return (f'<span class="ev-rw" title="{esc(name)} {qty}">{pic}'
            f'<span class="ev-rw-t">{label}<small>{qty}</small></span></span>')


def gcal_link(ev):
    s, e = parse_dt(ev["start"]), parse_dt(ev["end"])
    text = f"Pokémon GO {ev['title']}"
    details = f"{ev['title']}：時間、加成與任務整理 {BASE}/events/{ev['slug']}/"
    return ("https://calendar.google.com/calendar/render?action=TEMPLATE"
            f"&text={quote(text)}&dates={s:%Y%m%dT%H%M%S}/{e:%Y%m%dT%H%M%S}&details={quote(details)}")


def date_bits(dt):
    return {"m": dt.month, "d": dt.day, "w": WEEK[dt.weekday()], "y": dt.year}


# ---------------------------------------------------------------- 區塊
def sec(id_, title, body, ic="", extra=""):
    return (f'<section class="ev-sec" id="{id_}" aria-labelledby="{id_}-h">'
            f'<h2 id="{id_}-h"><span class="ev-h-ic">{ic}</span>{esc(title)}{extra}</h2>{body}</section>')


def render_hero(ev):
    s, e = parse_dt(ev["start"]), parse_dt(ev["end"])
    x = parse_dt(ev["extended_until"]) if ev.get("extended_until") else None
    b = date_bits(s)
    ext = f" · 部分加成至 {x:%H:%M}" if x else ""
    return f'''
<header class="ev-hero">
  <div class="ev-banner">
    <img src="../../img/events/{esc(ev["banner"])}.webp" alt="{esc(ev["title"])}主視覺" width="800" height="450" fetchpriority="high">
    <div class="ev-banner-tags"><span class="ev-kind">{esc(ev["kind"])}</span>{type_chips(ev["types"])}</div>
  </div>
  <div class="ev-hero-body">
    <p class="ev-eyebrow">{esc(ev.get("subtitle", ""))}</p>
    <h1>{esc(ev["title"])}</h1>
    <div class="ev-when" data-ev data-start="{ev["start"]}" data-end="{ev["end"]}"{f' data-ext="{ev["extended_until"]}"' if x else ""}>
      <div class="ev-cal" aria-hidden="true"><span>{b["m"]} 月</span><b>{b["d"]}</b><span>週{b["w"]}</span></div>
      <div class="ev-time">
        <b>{s:%H:%M} – {e:%H:%M}</b>
        <span>{b["y"]} 年 {b["m"]} 月 {b["d"]} 日（週{b["w"]}）· 各地皆為當地時間{ext}</span>
      </div>
      <div class="ev-status"><span class="ev-pill" data-pill>即將開始</span><span class="ev-count" data-count>{b["m"]}/{b["d"]} {s:%H:%M} 開始</span></div>
    </div>
    <div class="ev-actions">
      <a class="ev-btn ev-btn-main" href="{esc(gcal_link(ev))}" target="_blank" rel="noopener" data-track="calendar">{ICON_SVG["cal"]}加入 Google 日曆</a>
      <button class="ev-btn" type="button" data-share>{ICON_SVG["share"]}分享</button>
    </div>
  </div>
</header>'''


def render_highlights(ev):
    tiles = "".join(
        f'<div class="ev-hl"><span class="ev-hl-ic">{icon(h["icon"], ev)}</span>'
        f'<span class="ev-hl-t"><small>{esc(h["label"])}</small><b>{esc(h["value"])}</b><em>{esc(h.get("sub", ""))}</em></span></div>'
        for h in ev.get("highlights", []))
    return f'<div class="ev-hls">{tiles}</div>'


def render_timeline(ev):
    pts = ev.get("timeline") or []
    if not pts:
        return ""
    s, e = parse_dt(ev["start"]), parse_dt(ev["end"])
    x = parse_dt(ev["extended_until"]) if ev.get("extended_until") else e
    span = (x - s).total_seconds() or 1
    main_pct = (e - s).total_seconds() / span * 100
    stops = []
    for p in pts:
        h, m = map(int, p["at"].split(":"))
        pct = ((s.replace(hour=h, minute=m) - s).total_seconds()) / span * 100
        stops.append(f'<li style="--at:{pct:.2f}%"><b>{esc(p["at"])}</b><span>{esc(p["label"])}</span>'
                     f'<em>{esc(p.get("detail", ""))}</em></li>')
    return f'''
<section class="ev-tl" aria-label="活動時間軸" data-tl data-start="{ev["start"]}" data-end="{x:%Y-%m-%dT%H:%M}">
  <div class="ev-tl-bar"><span class="ev-tl-main" style="width:{main_pct:.2f}%">主要加成</span><span class="ev-tl-ext">延長加成</span><i class="ev-tl-now" data-now hidden></i></div>
  <ol class="ev-tl-stops">{"".join(stops)}</ol>
</section>'''


def render_toc(items):
    return ('<nav class="ev-toc" aria-label="本頁目錄"><div class="ev-toc-in">' +
            "".join(f'<a href="#{i}">{esc(t)}</a>' for i, t in items) + "</div></nav>")


def render_bonuses(ev):
    x = parse_dt(ev["extended_until"]) if ev.get("extended_until") else None
    e = parse_dt(ev["end"])
    cards = []
    for b in ev["bonuses"]:
        ext = b.get("window") == "extended" and x
        pill = (f'<span class="ev-win ext">至 {x:%H:%M}</span>' if ext else f'<span class="ev-win">至 {e:%H:%M}</span>')
        cards.append(f'<li class="ev-bonus{" is-ext" if ext else ""}"><span class="ev-bonus-ic">{icon(b["icon"], ev)}</span>'
                     f'<span class="ev-bonus-t">{esc(b["text"])}</span>{pill}</li>')
    note = f'<p class="ev-note">{esc(ev["bonus_note"])}</p>' if ev.get("bonus_note") else ""
    return sec("bonuses", "活動加成", f'<ul class="ev-bonuses">{"".join(cards)}</ul>{note}',
               icon("candy"))


def render_evolution(ev):
    evo = ev["evolution"]
    line = evo["line"]
    cards = []
    for i, d in enumerate(line):
        r = CP_ROWS[d]
        arrow = '<span class="ev-arrow" aria-hidden="true"></span>' if i < len(line) - 1 else ""
        star = " is-star" if d == evo.get("move", {}).get("learner") else ""
        cards.append(f'''<li class="ev-mon{star}">
  <a href="{cp_link(d)}" class="ev-mon-pic" aria-label="{esc(mon_name(ev, d))} 的 CP 表">
    <img class="n" src="{mon_img(d, big=True)}" alt="{esc(mon_name(ev, d))}" width="96" height="96" loading="lazy">
    <img class="s" src="{mon_img(d, True, big=True)}" alt="異色{esc(mon_name(ev, d))}" width="96" height="96" loading="lazy">
  </a>
  <b>{esc(mon_name(ev, d))}</b><small>#{d:03d}</small>
  <span class="ev-mon-cp">CP {cp_at(d, 20)}<em>Lv20 IV100</em></span>
</li>{arrow}''')
    mv = evo.get("move")
    move_html = ""
    if mv:
        tc = TYPES[mv["type"]]
        move_html = f'''
<div class="ev-move" style="--tc:{tc[1]}">
  <div class="ev-move-head"><span class="ev-type" style="--tc:{tc[1]}">{tc[0]}</span><span class="ev-move-k">特別招式</span></div>
  <div class="ev-move-name">{esc(mv["name"])}</div>
  <div class="ev-move-stats">
    <div><small>訓練家對戰</small><b>{mv["pvp"]}</b><i style="--w:{min(100, mv["pvp"] / 1.2):.0f}%"></i></div>
    <div><small>道館與團體戰</small><b>{mv["pve"]}</b><i style="--w:{min(100, mv["pve"] / 1.2):.0f}%"></i></div>
  </div>
  <p>{esc(mv["how"])}</p>
</div>'''
    lim = evo.get("limited")
    lim_html = ""
    if lim:
        lim_html = f'''
<div class="ev-limited">
  <span class="ev-limited-ic">{ICON_SVG["clock"]}</span>
  <div><b>{esc(lim["title"])}</b><p>{esc(lim["text"])}</p><small>{esc(lim.get("note", ""))}</small></div>
</div>'''
    body = (f'<ol class="ev-line">{"".join(cards)}</ol>'
            f'<div class="ev-evo-grid">{move_html}{lim_html}</div>')
    toggle = ('<button class="ev-shiny-toggle" type="button" aria-pressed="false" data-shiny>'
              f'{ICON_SVG["spark"]}<span>顯示異色</span></button>')
    return sec("evolution", "進化與特別招式", body, icon("move"), toggle)


def render_spawns(ev):
    sp = "".join(
        f'<li class="ev-spawn"><span class="ev-spawn-pic"><img src="{mon_img(s["dex"], big=True)}" alt="{esc(mon_name(ev, s["dex"]))}" width="88" height="88" loading="lazy">'
        f'{"<i class=ev-shiny-dot title=可遇見異色>" + ICON_SVG["spark"] + "</i>" if s.get("shiny") else ""}</span>'
        f'<b>{esc(mon_name(ev, s["dex"]))}</b><small>{"可能附特別背卡" if s.get("bg") else ""}</small></li>'
        for s in ev.get("spawns", []))
    sh = "".join(
        f'<li><span class="ev-pair"><img src="{mon_img(d, big=True)}" alt="{esc(mon_name(ev, d))}" width="72" height="72" loading="lazy">'
        f'<img src="{mon_img(d, True, big=True)}" alt="異色{esc(mon_name(ev, d))}" width="72" height="72" loading="lazy"></span>'
        f'<b>{esc(mon_name(ev, d))}</b></li>' for d in ev.get("shinies", []))
    lure = (f'<div class="ev-callout"><span class="ev-callout-ic">{icon("lure")}</span><p>{esc(ev["lure"])}</p></div>'
            if ev.get("lure") else "")
    body = f'''
<div class="ev-spawn-wrap">
  <div><h3>野生大量出現</h3><ul class="ev-spawns">{sp}</ul></div>
  <div><h3>可以入手的異色 <small>左：一般　右：異色</small></h3><ul class="ev-shinies">{sh}</ul></div>
</div>{lure}'''
    return sec("spawns", "野生出現與異色", body, f'<span class="ev-svg">{ICON_SVG["spark"]}</span>')


def task_row(ev, task, rewards):
    chips = "".join(reward_chip(ev, r) for r in rewards)
    return f'<li class="ev-task"><span class="ev-task-t">{esc(task)}</span><span class="ev-task-r">{chips}</span></li>'


def render_field(ev):
    if not ev.get("field_research"):
        return ""
    rows = "".join(task_row(ev, t["task"], t["rewards"]) for t in ev["field_research"])
    bg = "".join(task_row(ev, t["task"], t["rewards"]) for t in ev.get("field_research_bg", []))
    bg_html = (f'<h3 class="ev-sub">遇見附特別背卡的寶可夢</h3><ul class="ev-tasks is-bg">{bg}</ul>' if bg else "")
    note = f'<p class="ev-note">{esc(ev["field_note"])} 平常的田野調查任務請看 <a href="../../research/">田野調查任務列表</a>。</p>' if ev.get("field_note") else ""
    return sec("field", "田野調查", f'<ul class="ev-tasks">{rows}</ul>{bg_html}{note}',
               icon("pinap"))


def render_special(ev):
    sr = ev.get("special_research")
    if not sr:
        return ""
    n = len(sr["steps"])
    steps = []
    for i, st in enumerate(sr["steps"], 1):
        tasks = "".join(task_row(ev, t["task"], [t["reward"]]) for t in st["tasks"])
        done = "".join(reward_chip(ev, r) for r in st.get("rewards", []))
        steps.append(f'''
<details class="ev-step"{" open" if i == 1 else ""}>
  <summary><span class="ev-step-no">{i}</span><span class="ev-step-t">{esc(sr["name"])}（{i}/{n}）</span><span class="ev-step-prev">{"".join(reward_chip(ev, r, False) for r in st.get("rewards", []))}</span></summary>
  <ul class="ev-tasks">{tasks}</ul>
  <div class="ev-step-done"><span>完成全部課題</span><div>{done}</div></div>
</details>''')
    summary = "".join(f"<li>{esc(s)}</li>" for s in sr.get("summary", []))
    notes = "".join(f"<li>{esc(s)}</li>" for s in sr.get("notes", []))
    body = f'''
<div class="ev-ticket">
  <div class="ev-ticket-l"><small>付費特殊調查</small><b>{esc(sr["price"])}</b><em>{esc(sr.get("price_note", ""))}</em></div>
  <ul class="ev-ticket-r">{summary}</ul>
</div>
{"".join(steps)}
<ul class="ev-notes">{notes}</ul>'''
    return sec("special", "社群日特殊調查", body, icon("ticket"))


def render_tips(ev):
    if not ev.get("tips"):
        return ""
    items = "".join(f'<li><b>{esc(t["title"])}</b><p>{esc(t["text"])}</p></li>' for t in ev["tips"])
    return sec("tips", "攻略重點", f'<ol class="ev-tips">{items}</ol>', icon("star-piece"))


def render_cp(ev):
    line = ev["evolution"]["line"]
    head = "".join(f'<th scope="col">{esc(mon_name(ev, d))}</th>' for d in line)
    rows = "".join(
        f'<tr><th scope="row">Lv{lv}<small>{esc(label)}</small></th>' +
        "".join(f"<td>{cp_at(d, lv):,}</td>" for d in line) + "</tr>"
        for lv, label in CP_LEVELS)
    links = "、".join(f'<a href="{cp_link(d)}">{esc(mon_name(ev, d))}</a>' for d in line)
    body = f'''
<p class="ev-note ev-note-top">IV 15/15/15（100%）時的 CP，看到這些數字就是滿 IV。完整 Lv1～50 CP 表：{links}。</p>
<div class="ev-cp-wrap"><table class="ev-cp"><thead><tr><th scope="col">等級</th>{head}</tr></thead><tbody>{rows}</tbody></table></div>
<p class="ev-note">想拿去 PvP？用 <a href="../../pvp-ranker/">PvP IV 排名查詢</a> 看各聯盟的最佳 IV，或看 <a href="../../pvp-ranker/ultra-league/">高級聯盟排名</a>、<a href="../../pvp-ranker/master-league/">大師聯盟排名</a>。</p>'''
    return sec("cp", "IV100 CP 速查", body, icon("stardust"))


def render_faq(ev):
    if not ev.get("faq"):
        return ""
    items = "".join(f'<details class="ev-faq"><summary>{esc(f["q"])}</summary><p>{esc(f["a"])}</p></details>'
                    for f in ev["faq"])
    return sec("faq", "常見問題", items, icon("lucky-egg"))


def render_more(ev, all_events):
    others = [o for o in all_events if o["slug"] != ev["slug"]][:3]
    cards = "".join(mini_card(o, "../") for o in others)
    tools = [("../../?tab=cp-checker-app", "IV100 CP 查詢", "看任何寶可夢的滿 IV CP"),
             ("../../research/", "田野調查任務", "現在轉補給站會拿到什麼"),
             ("../../raids/", "團體戰頭目", "本期頭目與剋制"),
             ("../../eggs/", "孵蛋列表", "各距離蛋會孵出什麼")]
    t = "".join(f'<a class="ev-tool" href="{h}"><b>{esc(n)}</b><small>{esc(s)}</small></a>' for h, n, s in tools)
    return (f'<section class="ev-sec ev-more" aria-label="更多"><h2>其他活動</h2><div class="ev-cards">{cards}</div>'
            f'<h2>好用工具</h2><div class="ev-tools">{t}</div></section>')


def render_sources(ev):
    src = "".join(f'<li><a href="{esc(s["url"])}" target="_blank" rel="noopener">{esc(s["label"])}</a></li>'
                  for s in ev.get("sources", []))
    return (f'<aside class="ev-src"><p>{esc(ev.get("source_note", ""))}</p><ul>{src}</ul>'
            f'<p>最後更新：{esc(ev["updated"])}</p></aside>')


# ---------------------------------------------------------------- 頁面骨架
def header_html(prefix, events_active=True):
    """與 events/26-09-communityday/ 相同的表頭（功能選單）。prefix 是到網站根目錄的相對路徑。"""
    p = prefix
    act = ' active' if events_active else ''
    return f'''<header class="site-header-main">
  <a class="site-brand" href="{p}" aria-label="Pokémon Go 工具箱 首頁"><span class="site-brand-mark">🧰</span><span class="site-brand-name">Pokémon Go 工具箱</span></a>
  <a class="header-support" href="https://buymeacoffee.com/pogokit" target="_blank" rel="noopener" aria-label="請我喝杯咖啡 (Buy Me a Coffee)">☕ 支持</a>
  <div id="auth-container"><span id="user-info" style="display:none;"></span><button id="auth-button">登入</button></div>
  <nav class="app-nav">
    <button class="hamburger-button" aria-label="開啟選單" aria-expanded="false"><span></span><span></span><span></span></button>
    <div class="nav-links">
      <a class="tab-button" href="{p}">功能說明</a>
      <div class="nav-group mega-group"><button class="group-title">功能選單</button>
        <div class="sub-links mega-menu">
          <div class="mega-col"><div class="mega-heading">常用查詢</div>
            <a class="tab-button tab-button-hot" href="{p}trade-list/">🔴 交易清單產生器</a>
            <a class="tab-button" href="{p}?tab=cp-checker-app">IV100 CP 查詢</a>
            <a class="tab-button" href="{p}pvp-ranker/">PvP IV 排名查詢</a>
            <a class="tab-button" href="{p}pvp-ranker/great-league/">PvP 聯盟排名 Top 100</a>
            <a class="tab-button" href="{p}id-selector/">寶可夢編號篩選器</a>
            <a class="tab-button" href="{p}search-filters/">搜尋篩選指令</a>
          </div>
          <div class="mega-col"><div class="mega-heading">遊戲資訊</div>
            <a class="tab-button{act}" href="{p}events/">社群日整理</a>
            <a class="tab-button" href="{p}raids/">團體戰列表</a>
            <a class="tab-button" href="{p}eggs/">孵蛋列表</a>
            <a class="tab-button" href="{p}research/">田野調查任務</a>
            <a class="tab-button" href="{p}special-research/">特殊調查</a>
            <a class="tab-button" href="{p}stardust/">星星沙子怎麼賺</a>
          </div>
        </div>
      </div>
        <a class="tab-button tab-support" href="https://buymeacoffee.com/pogokit" target="_blank" rel="noopener">☕ 支持本站</a>
    </div>
  </nav>
</header>'''


def footer_html(p):
    return f'''<footer class="site-footer">
  <p>&copy; <span id="copyright-year">{datetime.now().year}</span> Pokémon Go 工具箱. All rights reserved by their respective owners.</p>
  <p>This website is an unofficial fan-made tool, is not officially affiliated with Pokémon GO, and is intended to fall under Fair Use doctrine, similar to any other informational site such as a wiki.</p>
  <p>Pokémon and its trademarks are &copy;1995-2025 Nintendo, Creatures, and GAME FREAK.</p>
  <p class="footer-links"><a href="{p}about/">關於本站</a> · <a href="{p}contact/">聯絡我們</a> · <a href="{p}privacy/">隱私權政策</a> · <a href="{p}disclaimer/">免責聲明</a> · <a href="https://buymeacoffee.com/pogokit" target="_blank" rel="noopener">☕ 請我喝杯咖啡</a></p>
</footer>'''


def head_html(p, title, desc, url, og_image, jsonld, preload=None, og_type="article"):
    ld = "".join(f'<script type="application/ld+json">{json.dumps(j, ensure_ascii=False)}</script>\n' for j in jsonld)
    pre = f'<link rel="preload" as="image" href="{preload}" fetchpriority="high">\n' if preload else ""
    # 廣告與分析的載入方式與其他活動頁完全相同（adsbygoogle 在 head、ads.js 在 body 最後）
    return f'''<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta name="robots" content="index,follow">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{og_image}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" type="image/png" sizes="192x192" href="{p}img/masterball.png">
{pre}<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8866689605007086" crossorigin="anonymous"></script>
<script src="{p}js/analytics.js"></script>
<script src="{p}config.js"></script>
<link rel="stylesheet" href="{p}css/main.css">
<link rel="stylesheet" href="{p}css/events.css">
{ld}</head>'''


def tail_html(p):
    return f'''<script src="{p}js/events.js" defer></script>
<script type="module">import {{ initUserAuth }} from '{p}js/user-data.js'; initUserAuth();</script>
<script src="{p}js/site-nav.js" defer></script>
<script src="{p}js/ads.js" defer></script>
</body>
</html>
'''


def jsonld_event(ev):
    url = f"{BASE}/events/{ev['slug']}/"
    s, e = parse_dt(ev["start"]), parse_dt(ev["end"])
    event = {
        "@context": "https://schema.org", "@type": "Event", "name": f"Pokémon GO {ev['title']}",
        "description": ev["description"], "startDate": f"{s:%Y-%m-%dT%H:%M}+08:00", "endDate": f"{e:%Y-%m-%dT%H:%M}+08:00",
        "eventAttendanceMode": "https://schema.org/OnlineEventAttendanceMode",
        "eventStatus": "https://schema.org/EventScheduled",
        "location": {"@type": "VirtualLocation", "url": "https://pokemongo.com/"},
        "image": [f"{BASE}/img/events/{ev['banner']}.jpg"],
        "organizer": {"@type": "Organization", "name": "Niantic", "url": "https://pokemongo.com/"},
        "url": url,
    }
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "首頁", "item": BASE + "/"},
        {"@type": "ListItem", "position": 2, "name": "活動整理", "item": BASE + "/events/"},
        {"@type": "ListItem", "position": 3, "name": ev["title"], "item": url}]}
    out = [event, crumbs]
    if ev.get("faq"):
        out.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}}
            for f in ev["faq"]]})
    return out


def build_event(ev, all_events):
    p = "../../"
    url = f"{BASE}/events/{ev['slug']}/"
    sections = [render_bonuses(ev), render_evolution(ev), render_spawns(ev), render_field(ev),
                render_special(ev), render_tips(ev), render_cp(ev), render_faq(ev)]
    toc = [("bonuses", "加成"), ("evolution", "進化與招式"), ("spawns", "野生與異色")]
    if ev.get("field_research"):
        toc.append(("field", "田野調查"))
    if ev.get("special_research"):
        toc.append(("special", "特殊調查"))
    if ev.get("tips"):
        toc.append(("tips", "攻略"))
    toc.append(("cp", "IV100 CP"))
    if ev.get("faq"):
        toc.append(("faq", "FAQ"))
    accent = ev.get("accent") or TYPES[ev["types"][0]][1]
    t1 = TYPES[ev["types"][0]][1]
    t2 = TYPES[ev["types"][-1]][1]
    body = f'''
<body class="ev-body">
{header_html(p)}
<div class="main-container ev-page" style="--ac:{accent};--t1:{t1};--t2:{t2}">
<nav class="ev-crumb" aria-label="麵包屑"><a href="{p}">首頁</a><span>›</span><a href="../">活動整理</a><span>›</span><span aria-current="page">{esc(ev["title"])}</span></nav>
<article class="ev-article">
{render_hero(ev)}
<p class="ev-lede">{esc(ev["lede"])}</p>
{render_highlights(ev)}
{render_timeline(ev)}
{render_toc(toc)}
{"".join(sections)}
{render_sources(ev)}
</article>
{render_more(ev, all_events)}
</div>
{footer_html(p)}
<div class="ev-toast" role="status" aria-live="polite" hidden></div>
{tail_html(p)}'''
    head = head_html(p, ev["seo_title"] + "｜" + SITE_NAME, ev["description"], url,
                     f"{BASE}/img/events/{ev['banner']}.jpg", jsonld_event(ev),
                     preload=f"../../img/events/{ev['banner']}.webp")
    write(os.path.join(ROOT, "events", ev["slug"], "index.html"), head + body)


# ---------------------------------------------------------------- 總覽
def card_info(ev):
    dex = ev.get("dex") or ev.get("featured")
    title = ev["title"]
    return dex, title


def mini_card(ev, rel):
    """rel：從目前頁面到 events/ 的相對路徑（總覽是 ./，活動頁是 ../）。"""
    dex, title = card_info(ev)
    s, e = parse_dt(ev["start"]), parse_dt(ev["end"])
    b = date_bits(s)
    t1 = TYPES[ev["types"][0]][1]
    t2 = TYPES[ev["types"][-1]][1]
    root = rel + "../"
    banner = f"{root}img/events/{ev['banner']}.webp"
    return f'''<a class="ev-card" href="{rel}{esc(ev["slug"])}/" style="--t1:{t1};--t2:{t2}" data-ev data-start="{ev["start"]}" data-end="{ev.get("extended_until") or ev["end"]}">
  <span class="ev-card-pic"><img src="{banner}" alt="" width="400" height="225" loading="lazy"><span class="ev-pill" data-pill>{"已結束" if e < datetime.now() else "即將開始"}</span></span>
  <span class="ev-card-body"><img class="ev-card-mon" src="{mon_img(dex, p=root)}" alt="" width="56" height="56" loading="lazy">
    <span><small>{esc(ev["kind"])} · {b["y"]}/{b["m"]:02d}/{b["d"]:02d} 週{b["w"]}</small><b>{esc(title)}</b><em>{s:%H:%M}–{e:%H:%M} 當地時間</em></span></span>
</a>'''


def build_index(all_events):
    p = "../"
    now = datetime.now()
    upcoming = [e for e in all_events if parse_dt(e.get("extended_until") or e["end"]) >= now]
    feature = sorted(upcoming, key=lambda e: e["start"])[0] if upcoming else None
    feat_html = ""
    if feature:
        s, e = parse_dt(feature["start"]), parse_dt(feature["end"])
        b = date_bits(s)
        feat_html = f'''
<a class="ev-feature" href="./{esc(feature["slug"])}/" style="--t1:{TYPES[feature["types"][0]][1]};--t2:{TYPES[feature["types"][-1]][1]};--ac:{feature.get("accent") or TYPES[feature["types"][0]][1]}">
  <span class="ev-feature-pic"><img src="../img/events/{esc(feature["banner"])}.webp" alt="{esc(feature["title"])}" width="800" height="450" fetchpriority="high"></span>
  <span class="ev-feature-body" data-ev data-start="{feature["start"]}" data-end="{feature["end"]}"{f' data-ext="{feature["extended_until"]}"' if feature.get("extended_until") else ""}>
    <span class="ev-feature-k">下一場活動 · {esc(feature["kind"])}</span>
    <b>{esc(feature["title"])}</b>
    <span class="ev-feature-d">{b["y"]} 年 {b["m"]} 月 {b["d"]} 日（週{b["w"]}）{s:%H:%M}–{e:%H:%M}</span>
    <span class="ev-status"><span class="ev-pill" data-pill>即將開始</span><span class="ev-count" data-count></span></span>
    <span class="ev-feature-go">看完整整理 →</span>
  </span>
</a>'''
    cards = "".join(mini_card(e, "./") for e in all_events if e is not feature)
    ld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": "Pokémon GO 活動整理",
           "url": BASE + "/events/", "inLanguage": "zh-Hant",
           "hasPart": [{"@type": "WebPage", "name": e["title"], "url": f"{BASE}/events/{e['slug']}/"} for e in all_events]},
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "首頁", "item": BASE + "/"},
              {"@type": "ListItem", "position": 2, "name": "活動整理", "item": BASE + "/events/"}]}]
    og = f"{BASE}/img/events/{(feature or all_events[0])['banner']}.jpg"
    head = head_html(p, "Pokémon GO 社群日與活動整理｜時間、加成、任務一次看｜" + SITE_NAME,
                     "Pokémon GO 每月社群日與活動整理：活動時間倒數、加成、特別招式、田野調查與特殊調查任務、異色與 IV100 CP，一頁看懂該準備什麼。",
                     BASE + "/events/", og, ld, og_type="website")
    body = f'''
<body class="ev-body">
{header_html(p)}
<div class="main-container ev-page ev-hub">
<nav class="ev-crumb" aria-label="麵包屑"><a href="{p}">首頁</a><span>›</span><span aria-current="page">活動整理</span></nav>
<header class="ev-hub-head">
  <h1>社群日與活動整理</h1>
  <p>每場活動的時間、加成、特別招式、任務獎勵與 IV100 CP，整理成一頁。時間都是當地時間，倒數會依你的裝置時區計算。</p>
</header>
{feat_html}
<h2 class="ev-hub-h">{"其他活動" if feature else "所有活動"}</h2>
<div class="ev-cards">{cards}</div>
</div>
{footer_html(p)}
{tail_html(p)}'''
    write(os.path.join(ROOT, "events", "index.html"), head + body)


# ---------------------------------------------------------------- sitemap
def update_sitemap(all_events):
    path = os.path.join(ROOT, "sitemap.xml")
    xml = read(path)
    now = datetime.now()

    def block(loc, lastmod, pr):
        return f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{lastmod}</lastmod>\n    <priority>{pr}</priority>\n  </url>\n"
    newest = max(e["updated"] for e in all_events)
    parts = ["  <!-- 社群日：由 scripts/build_event_pages.py 自動產生，勿手改此區塊 -->\n",
             block(BASE + "/events/", newest, "0.8")]
    for e in all_events:
        past = parse_dt(e.get("extended_until") or e["end"]) < now
        parts.append(block(f"{BASE}/events/{e['slug']}/", e["updated"], "0.5" if past else "0.7"))
    new_block = "".join(parts)
    pat = re.compile(r"[ \t]*<!-- 社群日：[^\n]*\n(?:[ \t]*<url>\s*<loc>" + re.escape(BASE) +
                     r"/events/[^<]*</loc>.*?</url>\s*\n)*", re.S)
    if pat.search(xml):
        xml = pat.sub(lambda m: new_block, xml, count=1)
    else:
        xml = xml.replace("</urlset>", new_block + "</urlset>")
    write(path, xml)


def main():
    events = []
    for fn in sorted(os.listdir(DATA_DIR)):
        if fn.endswith(".json"):
            ev = json.loads(read(os.path.join(DATA_DIR, fn)))
            events.append(ev)
    all_events = sorted(events + LEGACY, key=lambda e: e["start"], reverse=True)
    for ev in events:
        build_event(ev, all_events)
        print("活動頁：events/%s/" % ev["slug"])
    build_index(all_events)
    update_sitemap(all_events)
    print("總覽 events/index.html、sitemap.xml 已更新（共 %d 場）" % len(all_events))


if __name__ == "__main__":
    main()
