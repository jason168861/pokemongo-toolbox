#!/usr/bin/env python3
"""產生 GO 對戰聯盟「盃賽」排名頁：
    /pvp-ranker/cups/          本季賽程總覽＋各盃賽入口
    /pvp-ranker/<盃賽>/         各盃賽排名 Top 100（版面與三個聯盟頁共用 build_pvp_league.render_page）

資料：
    排名  github.com/pvpoke/pvpoke（MIT）src/data/rankings/<cup>/overall/rankings-<cp>.json
    名稱  pvpoketw.com/data/gamemaster.json（中文寶可夢與招式名；處理方式與 generate_pokemon_data.py 相同）

    python scripts/build_pvp_cups.py        （也會由 build_pvp_league.py 在 CI 每次排程時呼叫）

自動更新：每次 CI 都重抓所有盃賽的排名；Top 100 有變才改「資料更新」日期（data/pvp_cup_state.json），
sitemap.xml 的盃賽區塊也由這支腳本整段重寫。
換季時要手動更新的只有下面的 SEASON（賽程）與 CUPS（新盃賽的中文名與規則，照官方繁中公告）。
PvPoke 有新的盃賽而這裡還沒設定時，執行時會印出提醒。
"""
import datetime, json, os, re, sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_pvp_league as L  # noqa: E402
from build_pvp_league import e, TOP, TW  # noqa: E402
from generate_pokemon_data import process_rankings  # noqa: E402
from pvpoke_credit import credit_html  # noqa: E402

ROOT = L.ROOT
STATE = os.path.join(ROOT, "data", "pvp_cup_state.json")
GM_URL = "https://pvpoketw.com/data/gamemaster.json"
RANK_URL = "https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/rankings/{cup}/overall/rankings-{cp}.json"
HUB = "cups"
UA = {"User-Agent": "pogokit.com data build (+https://pogokit.com/about/)"}

# ---- 本季賽程（官方繁中公告）----------------------------------------------------------------
# 每段都是太平洋時間 13:00 開始與結束；日期照公告原文（11/17→11/18 空一天、11/24～25 重疊都是原文如此）。
# 項目：great/ultra/master = 一般聯盟頁；其餘是 CUPS 的 slug。x4 = 對戰勝利星星沙子 4 倍。
SEASON = {
    "no": 28, "name": "黃昏之旅",
    "url": "https://pokemongo.com/zh_Hant/news/go-battle-league-twilight-trails",
    "windows": [
        ("2026-09-08", "2026-09-15", ["great-league-mega", "ultra-league-mega", "master-league-mega"], True),
        ("2026-09-15", "2026-09-22", ["great", "ultra-league-mega", "willpower-cup"], False),
        ("2026-09-22", "2026-09-29", ["ultra", "master-league-mega", "retro-cup"], True),
        ("2026-09-29", "2026-10-06", ["master", "color-cup"], True),
        ("2026-10-06", "2026-10-13", ["great-league-mega", "ultra-league-mega", "master-league-mega"], True),
        ("2026-10-13", "2026-10-20", ["great", "ultra-league-mega", "little-cup"], False),
        ("2026-10-20", "2026-10-27", ["ultra", "master-league-mega", "fantasy-cup"], True),
        ("2026-10-27", "2026-11-03", ["master", "halloween-cup"], True),
        ("2026-11-03", "2026-11-10", ["great-league-mega", "ultra-league-mega", "master-league-mega"], True),
        ("2026-11-10", "2026-11-17", ["great", "ultra-league-mega", "laic-cup"], False),
        ("2026-11-18", "2026-11-25", ["ultra", "master-league-mega", "laic-cup"], True),
        ("2026-11-24", "2026-12-01", ["master", "catch-cup"], True),
    ],
}
PLAIN = {"great": ("超級聯盟", "great-league"), "ultra": ("高級聯盟", "ultra-league"), "master": ("大師聯盟", "master-league")}

# ---- 盃賽 ---------------------------------------------------------------------------------------
# cup/cp = PvPoke 的盃賽代號與 CP 上限；rules = 官方公告的參賽條件；
# drop_mega = PvPoke 的模擬含超級進化、但官方 GBL 版不能用時，從榜單拿掉；note = 與官方規則的差異。
TYPE_ONLY = "僅限{}屬性寶可夢參加。"
CUPS = [
    {"slug": "great-league-mega", "cup": "mega", "cp": 1500, "name": "超級聯盟：超級版", "short": "超級聯盟：超級版",
     "rules": ["寶可夢 CP 必須在 1,500 以下。", "可以使用超級進化寶可夢（CP 超過上限時，對戰中會暫時降低等級）。"],
     "lede": "超級聯盟的超級進化版本：規則和超級聯盟一樣是 CP 1500，但多了超級進化寶可夢，前段班的組成跟一般超級聯盟很不一樣。"},
    {"slug": "ultra-league-mega", "cup": "mega", "cp": 2500, "name": "高級聯盟：超級版", "short": "高級聯盟：超級版",
     "rules": ["寶可夢 CP 必須在 2,500 以下。", "可以使用超級進化寶可夢（CP 超過上限時，對戰中會暫時降低等級）。"],
     "lede": "高級聯盟的超級進化版本：CP 2500 上限，加入超級進化寶可夢後，不少原本的主力會被擠下前段班。"},
    {"slug": "master-league-mega", "cup": "mega", "cp": 10000, "name": "大師聯盟：超級版", "short": "大師聯盟：超級版",
     "rules": ["沒有 CP 上限。", "可以使用超級進化寶可夢。"],
     "lede": "大師聯盟的超級進化版本：沒有 CP 上限，傳說寶可夢之外，超級進化寶可夢也能上場。"},
    {"slug": "willpower-cup", "cup": "willpower", "cp": 1500, "name": "意志力盃：超級聯盟版", "short": "意志力盃",
     "rules": ["寶可夢 CP 必須在 1,500 以下。", TYPE_ONLY.format("格鬥、超能力和惡"), "無法參賽：沙奈朵、索羅亞、索羅亞克。"],
     "lede": "意志力盃只開放格鬥、超能力和惡三種屬性，三者彼此剋制，帶惡屬性或能打惡屬性的寶可夢特別吃香。"},
    {"slug": "retro-cup", "cup": "retro", "cp": 1500, "name": "復古盃：超級聯盟版", "short": "復古盃",
     "rules": ["寶可夢 CP 必須在 1,500 以下。", "不可使用惡、鋼和妖精屬性寶可夢。"],
     "lede": "復古盃拿掉了惡、鋼、妖精三種屬性，等於回到這些屬性還沒出現時的對戰環境，一般、幽靈與龍屬性的地位跟著上升。"},
    {"slug": "color-cup", "cup": "colormega", "cp": 1500, "name": "超級四色盃：超級聯盟版", "short": "超級四色盃",
     "rules": ["寶可夢 CP 必須在 1,500 以下。", "可以使用超級進化寶可夢。", TYPE_ONLY.format("草、火、水和電")],
     "lede": "超級四色盃只開放草、火、水、電四種屬性，而且能用超級進化寶可夢；屬性之間互相剋制，第二屬性常常決定勝負。"},
    {"slug": "little-cup", "cup": "little", "cp": 500, "name": "小小盃", "short": "小小盃", "ivlink": False,
     "rules": ["寶可夢 CP 必須在 500 以下。", "僅限可進化並且從未進化過的寶可夢參加。"],
     "lede": "小小盃把 CP 上限壓到 500，只能派出還沒進化過的寶可夢，很多平常用不到的基本型態在這裡反而是主力。"},
    {"slug": "fantasy-cup", "cup": "fantasy", "cp": 1500, "name": "奇幻盃：超級聯盟版", "short": "奇幻盃",
     "rules": ["寶可夢 CP 必須在 1,500 以下。", TYPE_ONLY.format("龍、鋼和妖精")],
     "lede": "奇幻盃只開放龍、鋼、妖精三種屬性：鋼剋妖精、妖精剋龍，龍又被鋼抵抗，雙屬性的搭配是這個盃賽的重點。"},
    {"slug": "halloween-cup", "cup": "halloweenmega", "cp": 1500, "name": "超級萬聖節盃：超級聯盟版", "short": "超級萬聖節盃",
     "rules": ["寶可夢 CP 必須在 1,500 以下。", "可以使用超級進化寶可夢。", TYPE_ONLY.format("蟲、毒、幽靈、惡和妖精")],
     "lede": "超級萬聖節盃只開放蟲、毒、幽靈、惡、妖精五種屬性，而且可以用超級進化寶可夢。"},
    {"slug": "laic-cup", "cup": "laic2027", "cp": 1500, "name": "2026 GO Championship 拉丁美洲盃", "short": "拉丁美洲盃",
     "drop_mega": True,
     "rules": ["寶可夢 CP 必須在 1,500 以下。", "不可使用火、惡、鋼和妖精屬性寶可夢。", "不可使用傳說的寶可夢、幻之寶可夢和究極異獸。",
               "GO 對戰聯盟版本不可使用超級進化寶可夢（現場賽事可以）。",
               "無法參賽：吉利蛋、卡比獸、大尾立、果然翁、太陽珊瑚（伽勒爾的樣子）、刺龍王、恰雷姆、七夕青鳥、彷徨夜靈、胖嘟嘟、滴蛛霸、智揮猩、棄世猴、土王。"],
     "note": "PvPoke 的這份排名是依現場賽事規則（可以用超級進化）模擬的；本頁已拿掉超級進化寶可夢，分數仍是在含超級進化的環境下算出來的，僅供參考。",
     "lede": "拉丁美洲盃是 2026 年拉丁美洲國際錦標賽的同規則盃賽：不能用火、惡、鋼、妖精，也不能用傳說、幻之寶可夢和究極異獸，另外還有一串禁用名單。"},
    {"slug": "catch-cup", "cup": "catch", "cp": 1500, "name": "超級速成盃：超級聯盟版", "short": "超級速成盃",
     "rules": ["寶可夢 CP 必須在 1,500 以下。", "可以使用超級進化寶可夢。", "僅限使用「黃昏之旅」賽季期間（2026/9/9 04:00～12/2 05:00，台灣時間）捕捉到的寶可夢。", "不可使用幻之寶可夢。"],
     "note": "PvPoke 沒辦法判斷捕捉日期，這份排名是假設本季能捕捉到的寶可夢都能參賽，而且沒有包含超級進化寶可夢；請以自己本季實際抓到的寶可夢為準。",
     "lede": "超級速成盃只能派出這一季抓到的寶可夢，考驗的是這季有沒有把握機會抓到好用的寶可夢、並把牠養起來。"},
]
CUP_BY_SLUG = {c["slug"]: c for c in CUPS}
# PvPoke 有、但本站刻意不做頁面的格式（線下賽、自訂、非 GBL 的舊格式）；新出現且不在這裡的會提醒
KNOWN_UNUSED = {"all", "custom", "championshipseries", "spectral", "cauldron", "battlefrontiermaster", "trail", "fable",
                "gymbreakers", "premier", "classic", "remix"}


def cup_url(slug):
    return L.BASE + slug + "/"


# ---- 時間：太平洋時間 13:00 → 台灣時間 ----------------------------------------------------------
def _nth_sunday(y, m, n):
    d = datetime.date(y, m, 1)
    d += datetime.timedelta(days=(6 - d.weekday()) % 7)
    return d + datetime.timedelta(weeks=n - 1)


def pacific_1pm(day):
    """'2026-11-10' 太平洋時間 13:00 → aware datetime（台灣時間）。美國夏令時間：3 月第 2 個週日～11 月第 1 個週日。"""
    d = datetime.date.fromisoformat(day)
    dst = _nth_sunday(d.year, 3, 2) <= d < _nth_sunday(d.year, 11, 1)
    utc = datetime.datetime(d.year, d.month, d.day, 13, tzinfo=datetime.timezone.utc) + datetime.timedelta(hours=7 if dst else 8)
    return utc.astimezone(TW)


WD = "一二三四五六日"


def tw_label(dt, year=False):
    return (f"{dt.year}/" if year else "") + f"{dt.month}/{dt.day}（{WD[dt.weekday()]}）{dt:%H:%M}"


def windows():
    out = []
    for s, t, items, x4 in SEASON["windows"]:
        a, b = pacific_1pm(s), pacific_1pm(t)
        out.append({"start": a, "end": b, "items": items, "x4": x4,
                    "ms": (int(a.timestamp() * 1000), int(b.timestamp() * 1000))})
    return out


def item_link(key, here=None):
    if key in PLAIN:
        name, slug = PLAIN[key]
    else:
        c = CUP_BY_SLUG[key]
        name, slug = c["name"], c["slug"]
    cls = ' class="cur"' if key == here else ''
    return f'<a{cls} href="../{slug}/">{e(name)}</a>'


# ---- 資料 -------------------------------------------------------------------------------------
def fetch(url):
    r = requests.get(url, timeout=30, headers=UA)
    r.raise_for_status()
    return r.json()


def cup_ranks(c, gm):
    raw = fetch(RANK_URL.format(cup=c["cup"], cp=c["cp"]))
    if c.get("drop_mega"):
        raw = [r for r in raw if not re.search(r"_(mega|primal)(_|$)", r.get("speciesId", ""))]
    known = {p["speciesId"] for p in gm["pokemon"]}
    miss = [r["speciesId"] for r in raw if r.get("speciesId") not in known]
    raw = [r for r in raw if r.get("speciesId") in known]
    rows = process_rankings(raw, gm)
    for r, src in zip(rows, raw):
        r["sid"] = src["speciesId"]
    if miss:
        print(f"  ⚠ {c['slug']}：繁中版 gamemaster 還沒有 {len(miss)} 隻（先略過）：{miss[:6]}")
    return rows


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


# ---- 頁面 -------------------------------------------------------------------------------------
STATUS_JS = r"""
(function(){var now=Date.now();function lab(el){var s=JSON.parse(el.getAttribute('data-wins')||'[]'),k='',t='';
for(var i=0;i<s.length;i++){if(now>=s[i][0]&&now<s[i][1]){k='on';t='開放中';break;}if(now<s[i][0]){k='next';t='即將開放';break;}}
if(!k){k=s.length?'past':'none';t=s.length?'本季場次已結束':'本季未開放';}el.setAttribute('data-st',k);var x=el.querySelector('.st');if(x)x.textContent=t;}
[].forEach.call(document.querySelectorAll('[data-wins]'),lab);
[].forEach.call(document.querySelectorAll('.wins li[data-s]'),function(li){var a=+li.getAttribute('data-s'),b=+li.getAttribute('data-e');
li.classList.toggle('past',now>=b);li.classList.toggle('now',now>=a&&now<b);});var a=document.querySelector('.lgs [aria-current]');if(a){var n=a.parentNode;n.scrollLeft=a.offsetLeft-n.offsetLeft-(n.clientWidth-a.offsetWidth)/2;}})();
"""

EXTRA_CSS = r"""
.st{display:inline-block;padding:0 10px;border-radius:999px;font-weight:800;background:rgba(255,255,255,.14);color:#fff}
[data-st=on] .st{background:#16a34a}[data-st=next] .st{background:#e0276c}[data-st=past] .st,[data-st=none] .st{background:rgba(255,255,255,.14);color:#cfc8e6}
.cupinfo{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:18px}
.card{background:#fff;border-radius:20px;padding:18px 22px;box-shadow:0 1px 2px rgba(20,17,31,.06),0 6px 18px -14px rgba(20,17,31,.25)}
.card h2{margin:0 0 10px;font-size:1.12rem;letter-spacing:-.01em}
.rules{margin:0;padding:0 0 0 1.2em;color:var(--ink-2);font-size:.95rem}.rules li{margin:2px 0}
.warn{margin:12px 0 0;padding:10px 12px;border-radius:12px;background:#fff7e6;border:1px solid #f3d9a4;color:#7a4b00;font-size:.88rem;line-height:1.65}
.wins{list-style:none;margin:0;padding:0;display:grid;gap:6px}
.wins li{display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px;padding:8px 12px;border-radius:12px;background:#f6f4fa;font-size:.92rem;font-variant-numeric:tabular-nums}
.wins li.now{background:#ecfdf3;box-shadow:inset 3px 0 0 #16a34a}.wins li.past{opacity:.55}
.wins .x4{padding:0 7px;border-radius:6px;background:linear-gradient(135deg,#f7c948,#e8a317);color:#fff;font-size:.72rem;font-weight:900}
.wins .nowtag{display:none;padding:0 8px;border-radius:999px;background:#16a34a;color:#fff;font-size:.74rem;font-weight:800}.wins li.now .nowtag{display:inline-block}
.muted{color:var(--muted);font-size:.86rem;margin:10px 0 0}
.lgs a.cur{background:var(--ink);border-color:var(--ink);color:#fff}
@media(max-width:760px){.cupinfo{grid-template-columns:1fr}.card{padding:16px}}
"""

HUB_CSS = r"""
.sec{margin-top:30px}.sec>h2{font-size:1.4rem;letter-spacing:-.02em;margin:0 0 4px}.sec>p.sub{margin:0 0 12px;color:var(--muted);font-size:.92rem}
.nowbox{display:grid;gap:10px;margin-top:18px}
.nowbox .card{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px}
.nowbox .lab{font-weight:850;font-size:.95rem}.nowbox .tm{color:var(--muted);font-size:.86rem;font-variant-numeric:tabular-nums}
.pills{display:flex;flex-wrap:wrap;gap:6px}
.pills a{padding:5px 12px;border-radius:999px;background:#f3edff;color:#5b3fd6;text-decoration:none;font-weight:750;font-size:.88rem}
.sched{list-style:none;margin:0;padding:0;display:grid;gap:8px}
.sched li{display:grid;grid-template-columns:200px minmax(0,1fr);align-items:center;gap:6px 14px;padding:12px 16px;background:#fff;border-radius:16px;box-shadow:0 1px 2px rgba(20,17,31,.06)}
.sched li.now{box-shadow:inset 4px 0 0 #16a34a,0 0 0 2px #bbf7d0}.sched li.past{opacity:.55}
.sched .tm{font-size:.86rem;font-weight:750;color:var(--ink-2);font-variant-numeric:tabular-nums;line-height:1.5}
.sched .x4,.x4b{display:inline-block;padding:0 7px;border-radius:6px;background:linear-gradient(135deg,#f7c948,#e8a317);color:#fff;font-size:.72rem;font-weight:900;margin-left:4px}
.sched .nowtag{display:none;margin-left:6px;padding:0 8px;border-radius:999px;background:#16a34a;color:#fff;font-size:.74rem;font-weight:800}.sched li.now .nowtag{display:inline-block}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:12px}
.cc{display:flex;flex-direction:column;gap:8px;padding:16px 18px;background:#fff;border-radius:20px;color:var(--ink);text-decoration:none;box-shadow:0 1px 2px rgba(20,17,31,.06),0 6px 18px -14px rgba(20,17,31,.25)}
.cc:hover{box-shadow:0 0 0 2px #d9ccff,0 10px 24px -14px rgba(76,29,149,.4)}
.cc .hd{display:flex;align-items:center;justify-content:space-between;gap:8px}
.cc h3{margin:0;font-size:1.06rem;line-height:1.35}.cc .cap{flex:none;padding:1px 9px;border-radius:999px;background:#f3edff;color:#5b3fd6;font-size:.76rem;font-weight:800}
.cc .rl{margin:0;color:var(--muted);font-size:.86rem;line-height:1.6}
.cc .t3{display:flex;gap:8px}.cc .t3 span{display:flex;flex-direction:column;align-items:center;width:33%;font-size:.76rem;font-weight:750;text-align:center;line-height:1.3}
.cc .t3 img{width:56px;height:56px;object-fit:contain;border-radius:14px;background:radial-gradient(70% 70% at 50% 40%,#fff,#ece8f6);margin-bottom:3px}
.cc .ft{display:flex;align-items:center;justify-content:space-between;color:var(--muted);font-size:.8rem}
.cc .ft b{color:#5b3fd6}
.cc[data-st=on]{box-shadow:0 0 0 2px #bbf7d0,0 6px 18px -14px rgba(20,17,31,.25)}
.cc .st2{padding:0 8px;border-radius:999px;font-size:.74rem;font-weight:800;background:#f1f0f5;color:var(--muted)}
.cc[data-st=on] .st2{background:#16a34a;color:#fff}.cc[data-st=next] .st2{background:#e0276c;color:#fff}
.nw{display:inline-block}
@media(max-width:760px){.sched li{grid-template-columns:1fr}.grid{grid-template-columns:1fr}}
"""

HUB_JS = r"""
(function(){var now=Date.now();[].forEach.call(document.querySelectorAll('.sched li[data-s]'),function(li){var a=+li.getAttribute('data-s'),b=+li.getAttribute('data-e');
li.classList.toggle('past',now>=b);li.classList.toggle('now',now>=a&&now<b);});
[].forEach.call(document.querySelectorAll('.cc[data-wins]'),function(el){var s=JSON.parse(el.getAttribute('data-wins')),k='past',t='本季場次已結束';
for(var i=0;i<s.length;i++){if(now>=s[i][0]&&now<s[i][1]){k='on';t='開放中';break;}if(now<s[i][0]){k='next';t='即將開放';break;}}
el.setAttribute('data-st',k);el.querySelector('.st2').textContent=t;});
var box=document.getElementById('nowbox');if(box){var lis=[].slice.call(document.querySelectorAll('.sched li[data-s]')),cur=lis.filter(function(li){return li.classList.contains('now');}),
nx=lis.filter(function(li){return +li.getAttribute('data-s')>now;})[0];var h='';
function card(li,lab){return '<div class="card"><span class="lab">'+lab+'</span><span class="tm">'+li.getAttribute('data-label')+(li.hasAttribute('data-x4')?' <span class="x4b">星沙×4</span>':'')+'</span><span class="pills">'+li.querySelector('.pills').innerHTML+'</span></div>';}
cur.forEach(function(li){h+=card(li,'🟢 現在開放');});if(nx)h+=card(nx,'⏭ 下一段');
if(!h)h='<div class="card"><span class="lab">本季賽程已結束</span><span class="tm">下一季的賽程公布後會更新這頁。</span></div>';box.innerHTML=h;}})();
"""


def wins_attr(ws, slug):
    return e(json.dumps([list(w["ms"]) for w in ws if slug in w["items"]]))


def build_cup(c, ranks, date, ws, dex, imgs):
    name, url, slug = c["name"], cup_url(c["slug"]), c["slug"]
    n = min(TOP, len(ranks))
    top = ranks[:n]
    top3 = "、".join(L.resolve(r, dex)[0] for r in top[:3])
    month = f"{int(date[:4])} 年 {int(date[5:7])} 月"
    cap = "無 CP 上限" if c["cp"] == 10000 else f"CP {c['cp']:,}"
    mine = [w for w in ws if slug in w["items"]]
    when_txt = "、".join(f"{tw_label(w['start'])}～{tw_label(w['end'])}" for w in mine)
    title = f"Pokémon GO {name}推薦排名 Top {n}｜強度排行與推薦招式（{month}）"
    desc = (f"Pokémon GO {name}（{cap}）推薦寶可夢排名前 {n} 名：目前前三名是 {top3}。"
            f"附參賽規則、本季開放時間（台灣時間）與每隻的推薦招式。")
    rules_li = "".join(f"<li>{e(x)}</li>" for x in c["rules"])
    warn = f'<p class="warn">⚠ {e(c["note"])}</p>' if c.get("note") else ""
    if mine:
        win_li = "".join(
            f'<li data-s="{w["ms"][0]}" data-e="{w["ms"][1]}"><b>{tw_label(w["start"])} ～ {tw_label(w["end"])}</b>'
            f'{"<span class=x4>星沙 ×4</span>" if w["x4"] else ""}<span class="nowtag">開放中</span></li>' for w in mine)
        when = (f'<ul class="wins">{win_li}</ul><p class="muted">官方公告以太平洋時間 13:00 切換，這裡已換算成台灣時間。'
                f'<a href="../{HUB}/">看本季完整賽程 →</a></p>')
    else:
        when = f'<p class="muted">第 {SEASON["no"]} 季（{e(SEASON["name"])}）沒有開放這個盃賽。<a href="../{HUB}/">看本季賽程 →</a></p>'
    extra = (f'  <section class="cupinfo">\n    <div class="card"><h2>參賽規則</h2><ul class="rules">{rules_li}</ul>{warn}</div>\n'
             f'    <div class="card"><h2>本季開放時間（台灣時間）</h2>{when}</div>\n  </section>\n')
    cp_word = "CP 500" if c["cp"] == 500 else ("沒有 CP 上限" if c["cp"] == 10000 else f"CP {c['cp']}")
    if c["cp"] == 1500:
        iv_a = ("盃賽的 IV 排名只跟 CP 上限有關。這個盃賽是 CP 1500，所以 IV 怎麼挑跟超級聯盟完全一樣：攻擊 IV 低、防禦與 HP 高的個體能升到更高等級，"
                "總能力值更大。點榜單上的「查 IV」就能查你手上那隻的名次。")
    elif c["cp"] == 2500:
        iv_a = "這個盃賽是 CP 2500，IV 怎麼挑跟高級聯盟一樣；點榜單上的「查 IV」就能查你手上那隻的名次。"
    elif c["cp"] == 10000:
        iv_a = "沒有 CP 上限，攻擊、防禦、HP 都是越高越好，15/15/15 最理想，跟大師聯盟一樣。"
    else:
        iv_a = ("CP 500 的上限很低，同樣是攻擊 IV 低、防禦與 HP 高的個體能升到更高等級。"
                "很多寶可夢只要升到 10～20 級左右就會碰到上限，不需要花太多星星沙子。")
    faq = [
        (f"{name}的規則是什麼？", "".join(c["rules"])),
        (f"{name}什麼時候開放？", (f"第 {SEASON['no']} 季（{SEASON['name']}）的開放時間（台灣時間）：{when_txt}。" if mine
                              else f"第 {SEASON['no']} 季（{SEASON['name']}）沒有開放這個盃賽。") + "實際以遊戲內與官方公告為準。"),
        ("這份排名的分數怎麼來的？", f"分數來自 PvPoke 的對戰模擬：只用符合{name}規則的寶可夢，讓牠們用推薦招式互相以各種護盾數對打，"
                           "綜合勝率與表現算成 0～100 的分數。分數越高，代表在這個盃賽越全面，但實戰仍要看隊伍搭配與對手。"),
        (f"{name}要什麼樣的 IV？", iv_a),
        L.FAQ_ELITE,
        ("排名多久更新？", "本站每天會多次檢查 PvPoke 的最新排名，前 100 名有變動就自動重新產生這頁，頁首的「資料更新」就是最近一次變動的日期。"),
    ]
    if c.get("note"):
        faq.insert(3, ("這份排名跟官方規則完全一樣嗎？", c["note"]))
    tabs = f'<a href="../{HUB}/">本季賽程</a>' + "".join(
        (f'<a href="../{o["slug"]}/" aria-current="page">{e(o["short"])}</a>' if o is c else f'<a href="../{o["slug"]}/">{e(o["short"])}</a>')
        for o in CUPS)
    ld = [
        {"@context": "https://schema.org", "@type": "Article", "headline": f"Pokémon GO {name}推薦排名 Top {n}",
         "description": desc, "inLanguage": "zh-Hant", "dateModified": date, "mainEntityOfPage": url},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Pokémon Go 工具箱", "item": "https://pogokit.com/"},
            {"@type": "ListItem", "position": 2, "name": "PvP IV 排名", "item": L.BASE},
            {"@type": "ListItem", "position": 3, "name": "盃賽排名", "item": cup_url(HUB)},
            {"@type": "ListItem", "position": 4, "name": f"{name}排名", "item": url}]},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]},
    ]
    ivtxt = "；想知道你手上那隻的 IV 排第幾，點右邊的「查 IV」直接帶入。" if c.get("ivlink", True) else "。"
    L.render_page({
        "slug": slug, "url": url, "title": title, "desc": desc, "dex": dex, "imgs": imgs,
        "h1": (f"Pokémon GO {name}推薦排名" if len(name) <= 9 else f"{name}推薦排名"), "eyebrow": f"GO 對戰聯盟盃賽 · {cap}",
        "lede": f"{e(c['lede'])}這份榜單依 PvPoke 對戰模擬的分數排序，列出前 {n} 名寶可夢與推薦招式{ivtxt}",
        "chips": (f'<li>資料更新 <b>{date}</b></li><li>收錄 <b>{len(ranks)}</b> 隻・顯示前 <b>{n}</b> 名</li>'
                  f'<li><span class="st">本季開放時間</span></li><li><b class="lt">限定</b> 限定招式</li>'),
        "data_attrs": f' data-wins="{wins_attr(ws, slug)}"',
        "tabs": tabs, "crumb": f'<a href="../{HUB}/">盃賽排名</a> › <span>{e(name)}</span>',
        "ranks": ranks, "top": top, "faq": faq, "faq_h": f"{name}常見問題", "ld": ld,
        "extra": extra, "ivlink": c.get("ivlink", True), "extra_css": EXTRA_CSS, "extra_js": STATUS_JS,
        "more": (f'也可以看本季其他盃賽：<a href="../{HUB}/">盃賽排名與賽程</a>，'
                 f'或一般的<a href="../great-league/">超級聯盟</a>、<a href="../ultra-league/">高級聯盟</a>、<a href="../master-league/">大師聯盟</a>排名。'),
        "next_p": (f"用 PvP IV 排名工具查你手上那隻在 {cp_word} 的 IV 排第幾，以及要升到幾級、CP 多少。" if c.get("ivlink", True)
                   else "PvP IV 排名工具目前支援 CP 1500／2500／無上限，可以查你手上那隻在其他聯盟的 IV 名次。"),
    })


def build_hub(data, dates, ws, dex, imgs):
    url = cup_url(HUB)
    first, last = ws[0]["start"], ws[-1]["end"]
    sched = "".join(
        f'<li data-s="{w["ms"][0]}" data-e="{w["ms"][1]}" data-label="{tw_label(w["start"])} ～ {tw_label(w["end"])}"{" data-x4" if w["x4"] else ""}>'
        f'<span class="tm">{tw_label(w["start"])}<br>～ {tw_label(w["end"])}'
        f'{"<span class=x4>星沙×4</span>" if w["x4"] else ""}<span class="nowtag">開放中</span></span>'
        f'<span class="pills">{"".join(item_link(k) for k in w["items"])}</span></li>' for w in ws)
    cards = []
    for c in CUPS:
        ranks = data.get(c["slug"])
        if not ranks:
            continue
        t3 = []
        for r in ranks[:3]:
            disp, pid, shadow = L.resolve(r, dex)
            img = L.local_img(imgs.get(pid, "") if pid else "", r["dex"], r.get("sid", ""))
            t3.append(f'<span><img src="{e(img)}" alt="" width="56" height="56" loading="lazy" decoding="async">{e(disp)}{"（暗影）" if shadow else ""}</span>')
        cap = "無上限" if c["cp"] == 10000 else f"CP {c['cp']}"
        rl = "；".join(x.rstrip("。") for x in c["rules"][1:3]) or c["rules"][0].rstrip("。")
        cards.append(f'<a class="cc" href="../{c["slug"]}/" data-wins="{wins_attr(ws, c["slug"])}">'
                     f'<span class="hd"><h3>{e(c["name"])}</h3><span class="cap">{cap}</span></span>'
                     f'<p class="rl">{e(rl)}</p><span class="t3">{"".join(t3)}</span>'
                     f'<span class="ft"><span class="st2">本季</span><span>看排名 Top {min(TOP, len(ranks))} <b>→</b></span></span></a>')
    faq = [
        ("盃賽和一般聯盟有什麼不同？", "一般的超級、高級、大師聯盟只限制 CP；盃賽另外限制屬性、禁用特定寶可夢，或只開放某些條件的寶可夢（例如小小盃只能用未進化的寶可夢）。"
                          "每個盃賽的強勢寶可夢都不一樣，所以要另外看排名。"),
        ("盃賽什麼時候切換？", "官方公告的時間是太平洋時間 13:00，換算台灣時間是隔天清晨：夏令時間期間是 04:00，11 月第一個週日之後是 05:00。這頁的時間都已換算成台灣時間。"),
        ("「星沙 ×4」是什麼？", "標示的時段，對戰勝利時拿到的星星沙子變成 4 倍（不包括每組對戰結束時的獎勵）。"),
        ("排名從哪裡來？多久更新？", "排名是 PvPoke 的對戰模擬結果，本站每天會多次檢查，前 100 名有變動就自動更新各盃賽頁。賽程則照官方公告整理，換季時更新。"),
    ]
    ld = [
        {"@context": "https://schema.org", "@type": "Article", "headline": f"GO 對戰聯盟第 {SEASON['no']} 季「{SEASON['name']}」賽程與盃賽排名",
         "inLanguage": "zh-Hant", "dateModified": max(dates.values()) if dates else L.today_tw(), "mainEntityOfPage": url},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Pokémon Go 工具箱", "item": "https://pogokit.com/"},
            {"@type": "ListItem", "position": 2, "name": "PvP IV 排名", "item": L.BASE},
            {"@type": "ListItem", "position": 3, "name": "盃賽排名", "item": url}]},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]},
    ]
    title = f"GO 對戰聯盟賽程與盃賽排名｜第 {SEASON['no']} 季「{SEASON['name']}」每週盃賽推薦寶可夢"
    desc = (f"Pokémon GO 對戰聯盟第 {SEASON['no']} 季「{SEASON['name']}」完整賽程（台灣時間）與 {len(cards)} 個聯盟／盃賽的推薦排名："
            "意志力盃、復古盃、小小盃、奇幻盃、拉丁美洲盃、超級速成盃與各聯盟超級版，附參賽規則與推薦招式。")
    faq_html = "\n".join(f'<details class="qa"><summary>{e(q)}</summary><p>{e(a)}</p></details>' for q, a in faq)
    tabs = (f'<a href="../{HUB}/" aria-current="page">本季賽程</a>'
            + "".join(f'<a href="../{PLAIN[k][1]}/">{PLAIN[k][0]}</a>' for k in PLAIN))
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
<title>{e(title)}｜Pokémon Go 工具箱</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{url}">
<meta name="robots" content="index,follow">
<meta property="og:type" content="article">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
<style>{L.CSS}{EXTRA_CSS}{HUB_CSS}</style>
</head>
<body>
<header class="topbar">
  <a class="home" href="../../"><span class="logo" aria-hidden="true">🧰</span><span>Pokémon Go 工具箱</span></a>
  <nav class="tnav" aria-label="相關工具"><a href="../">PvP IV 排名查詢</a><a href="../great-league/">聯盟排名</a><a href="../../backgrounds/">背卡一覽</a></nav>
  <a class="cta" href="../../trade-list/">做交換清單</a>
</header>

<main>
  <nav class="crumb" aria-label="導覽路徑"><a href="../../">Pokémon Go 工具箱</a> › <a href="../">PvP IV 排名</a> › <span>盃賽排名</span></nav>
  <nav class="lgs" aria-label="切換聯盟">{tabs}</nav>
  <section class="hero">
    <p class="eyebrow">GO 對戰聯盟 · 第 {SEASON["no"]} 季 · {e(SEASON["name"])}</p>
    <h1><span class="nw">GO 對戰聯盟</span><span class="nw">賽程與盃賽排名</span></h1>
    <p class="lede">每一兩週換一次的盃賽，規則都不一樣：有的只開放特定屬性，有的禁用特定寶可夢，有的只能用沒進化過的寶可夢。
    這頁整理本季每個時段開放的聯盟與盃賽（已換算成台灣時間），每個盃賽都有依 PvPoke 對戰模擬排序的推薦排名。</p>
    <ul class="chips"><li>本季 <b>{tw_label(first, True)}</b> ～ <b>{tw_label(last, True)}</b></li><li>盃賽 <b>{len(cards)}</b> 個</li><li><a href="{e(SEASON["url"])}" target="_blank" rel="noopener" style="color:#fff">官方公告 ↗</a></li></ul>
  </section>

  <div class="nowbox" id="nowbox" aria-live="polite"></div>

  <section class="sec">
    <h2>本季賽程（台灣時間）</h2>
    <p class="sub">官方以太平洋時間 13:00 切換；11/17→11/18 中間空一天、11/24～11/25 重疊，都是官方公告原文的日期。</p>
    <ol class="sched">{sched}</ol>
  </section>

  <section class="sec">
    <h2>各盃賽推薦排名</h2>
    <p class="sub">點進去看參賽規則、開放時間與 Top 100 推薦寶可夢。</p>
    <div class="grid">{"".join(cards)}</div>
  </section>

  <section class="faq">
    <h2>盃賽常見問題</h2>
{faq_html}
  </section>

  <section class="next">
    <div><h2>選好要練的寶可夢了？</h2><p>用 PvP IV 排名工具查你手上那隻的 IV 排第幾，以及要升到幾級、CP 多少。</p></div>
    <a class="bigcta" href="../">查我的 PvP IV 排名 →</a>
  </section>
</main>

<footer class="foot">
  <p>{credit_html("zh")}非官方資料，僅供參考。賽程整理自 <a href="{e(SEASON["url"])}" target="_blank" rel="noopener">Pokémon GO 官方公告</a>。</p>
  <p>本站為非官方同人工具，與 Pokémon GO／Niantic 無隸屬關係。Pokémon 及其商標為 &copy;1995-2026 Nintendo, Creatures, GAME FREAK 所有。</p>
  <p><a href="../../about/">關於本站</a> · <a href="../../contact/">聯絡我們</a> · <a href="../../privacy/">隱私權政策</a> · <a href="../../disclaimer/">免責聲明</a> · <a href="../../">回工具箱</a></p>
</footer>

<script>{HUB_JS}</script>
<script src="../../js/ads.js" defer></script>
</body>
</html>
'''
    out_dir = os.path.join(ROOT, "pvp-ranker", HUB)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print(f"已寫出 pvp-ranker/{HUB}/index.html（{len(cards)} 個盃賽）")


# ---- sitemap：整段重寫盃賽區塊 -----------------------------------------------------------------
SM_BEGIN = "<!-- PvP 盃賽：由 scripts/build_pvp_cups.py 自動產生，勿手改此區塊 -->"
SM_END = "<!-- /PvP 盃賽 -->"


def write_sitemap(dates):
    path = L.SITEMAP
    with open(path, encoding="utf-8", newline="") as f:
        xml = f.read()
    nl = "\r\n" if "\r\n" in xml else "\n"
    hub_date = max(dates.values()) if dates else L.today_tw()
    entries = [(cup_url(HUB), hub_date, "0.8")] + [(cup_url(s), d, "0.7") for s, d in dates.items()]
    lines = [f"  {SM_BEGIN}"]
    for loc, d, pr in entries:
        lines += ["  <url>", f"    <loc>{loc}</loc>", f"    <lastmod>{d}</lastmod>", f"    <priority>{pr}</priority>", "  </url>"]
    lines.append(f"  {SM_END}")
    block = nl.join(lines)
    if SM_BEGIN in xml:
        new = re.sub(r"[ \t]*" + re.escape(SM_BEGIN) + r".*?" + re.escape(SM_END), lambda m: block, xml, flags=re.S)
    else:
        # 第一次：接在大師聯盟那筆後面
        anchor = re.search(r"<loc>" + re.escape(L.BASE + "master-league/") + r"</loc>.*?</url>", xml, flags=re.S)
        i = anchor.end() if anchor else xml.index("</urlset>")
        new = xml[:i] + nl + block + xml[i:]
    if new != xml:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(new)


def build():
    gm = fetch(GM_URL)
    src = open(os.path.join(ROOT, "data", "pokemon_data_and_rankings.js"), encoding="utf-8").read()
    dex = L.js_array(src, "POKEDEX")
    img_src = open(os.path.join(ROOT, "data", "pokemon_images.js"), encoding="utf-8").read()
    imgs = json.loads(img_src[img_src.index("{"):img_src.rindex("}") + 1])
    ws = windows()
    state, today = load_state(), L.today_tw()
    data, dates, failed = {}, {}, []
    for c in CUPS:
        try:
            ranks = cup_ranks(c, gm)
        except (requests.RequestException, ValueError) as ex:
            print(f"  ⚠ {c['slug']} 排名抓不到（{ex}），這頁維持上一版")
            failed.append(c["slug"])
            if c["slug"] in state:
                dates[c["slug"]] = state[c["slug"]]["date"]
            continue
        if not ranks:
            print(f"  ⚠ {c['slug']} 排名是空的，這頁維持上一版")
            failed.append(c["slug"])
            if c["slug"] in state:
                dates[c["slug"]] = state[c["slug"]]["date"]
            continue
        fp = L.fingerprint(ranks)
        st = state.get(c["slug"])
        if not st or st.get("hash") != fp:
            st = state[c["slug"]] = {"hash": fp, "date": today}
        data[c["slug"]] = ranks
        dates[c["slug"]] = st["date"]
        build_cup(c, ranks, st["date"], ws, dex, imgs)
    if data and not failed:   # 有盃賽抓不到時總覽維持上一版，免得卡片少一張
        build_hub(data, dates, ws, dex, imgs)
        save_state(state)
        write_sitemap(dates)
    used = {c["cup"] for c in CUPS} | KNOWN_UNUSED
    new = sorted({f["cup"] for f in gm.get("formats", []) if f.get("showFormat") and f.get("cup") not in used})
    if new:
        print("ℹ PvPoke 有本站還沒建頁的盃賽格式（換季時請到 CUPS／SEASON 補上）：", new)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build()
