# -*- coding: utf-8 -*-
"""
產生「靜態預先產生」的單隻寶可夢 CP 頁面（內容全部寫死在原始 HTML）。

背景：GitHub Pages 是純靜態主機，?tab=cp-checker-app&mon=XXX 這類查詢字串網址
回傳的原始 HTML 都是同一個 index.html —— Google 因此把 1079 個 ?mon= 網址全部
canonical 收斂到 ?tab=cp-checker-app，判為重複而不收錄（GSC 實測：Google 所選
標準網址 = ?tab=cp-checker-app）。

解法：每隻輸出一個真正獨立的檔案（不同路徑、內容寫死在原始 HTML、自帶 self-canonical），
Google 一抓就看得到不同文件，才有機會收錄。

名單在 data/cp_static_targets.json（依搜尋需求挑選）；內容由 auto_enrich() 從
data/pokemon_data_and_rankings.js 的 POKEDEX / rankings 自動生成（烈空坐另有手寫版）。
同時產生 js/cp-static-slugs.js（給 CP 查詢工具做 ?mon= 轉址與站內連結），
並更新 sitemap.xml 裡的 /cp/ 區塊。
⚠ CI 的 refresh_cp_data.py 若把名單裡的寶可夢改名，要更新 data/cp_static_targets.json 的名稱並重跑本腳本，
  否則新名稱不會轉址到靜態頁，build_cp_sitemap.py 也會把它重新列進 sitemap-cp.xml。

用法：  python scripts/build_cp_static.py
輸出：  cp/<slug>/index.html
"""
import os, re, math, html, json
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGIN = "https://pogokit.com"

# ---- 讀 CP 資料與 CPM ----
cp_js = open(os.path.join(ROOT, "data", "precomputed_pokemon_cp.js"), encoding="utf-8").read()
CPM = [float(x) for x in re.search(r"CP_MULTIPLIER\s*=\s*\[([^\]]+)\]", cp_js).group(1).split(",")]
CP_DATA = {}
for o in re.findall(r"\{[^{}]*\}", re.search(r"POKEMON_CP_DATA\s*=\s*(\[.*?\]);", cp_js, re.S).group(1)):
    d = {}
    for k, v in re.findall(r"'(\w+)':\s*(\"[^\"]*\"|[0-9]+)", o):
        d[k] = v[1:-1] if v.startswith('"') else int(v)
    if "name" in d:
        CP_DATA[d["name"]] = d

MAX_LEVEL, BB = 50, 51
KEY = {15: "🔬 田野調查 · 🤝 小隊合作",
       20: "⚔️ 團體戰（無天氣加成）· 🥚 孵化的蛋",
       25: "☀️ 團體戰（天氣加成）"}

def cp_at(p, L, iv):
    m = CPM[L - 1]
    return max(10, int((p["atk"] + iv) * math.sqrt(p["def"] + iv) * math.sqrt(p["sta"] + iv) * m * m / 10))

# ---- 高 IV CP·HP 對照表（IV 100%～91.1%，仿使用者附圖）----
IV_TABLE_LEVELS = [15, 20, 25, 40]   # 與參考圖一致
IV_MIN_SUM = 41                       # IV 總和 41/45 = 91.11%

def cp_iv(p, L, a, d, s):
    m = CPM[L - 1]
    return max(10, int((p["atk"] + a) * math.sqrt(p["def"] + d) * math.sqrt(p["sta"] + s) * m * m / 10))

def hp_iv(p, L, s):
    return max(10, int((p["sta"] + s) * CPM[L - 1]))

def build_iv_table(p):
    combos = []
    for a in range(15, -1, -1):
        for d in range(15, -1, -1):
            for s in range(15, -1, -1):
                tot = a + d + s
                if tot >= IV_MIN_SUM:
                    combos.append((tot, a, d, s, cp_iv(p, 40, a, d, s)))
    combos.sort(key=lambda c: (-c[0], -c[4]))   # IV% 由高到低，同 IV% 內 CP 由高到低
    body = ""
    for tot, a, d, s, _ in combos:
        pct = tot / 45 * 100
        cells = "".join(f'<td>{cp_iv(p,L,a,d,s)}</td><td class="hp">{hp_iv(p,L,s)}</td>' for L in IV_TABLE_LEVELS)
        ivc = (f'<td class="iv v{a}">{a}</td><td class="iv v{d}">{d}</td><td class="iv v{s}">{s}</td>')
        hundo = ' class="hundo"' if tot == 45 else ''
        body += f'<tr{hundo}><td class="pct">{pct:.2f}%</td>{ivc}{cells}</tr>'
    heads1 = "".join(f'<th colspan="2">L{L}</th>' for L in IV_TABLE_LEVELS)
    heads2 = "".join('<th>CP</th><th>HP</th>' for _ in IV_TABLE_LEVELS)
    return (f'<table class="iv"><thead>'
            f'<tr><th rowspan="2">IV%</th><th colspan="3">個體值 攻/防/耐</th>{heads1}</tr>'
            f'<tr><th>攻</th><th>防</th><th>耐</th>{heads2}</tr>'
            f'</thead><tbody>{body}</tbody></table>')

def dex_neighbor(pid, step):
    d = pid + step
    while 1 <= d <= 1025:
        for p in CP_DATA.values():
            if p["id"] == d:
                return p["name"]
        d += step
    return None

# ================= 屬性相剋 / 資料 join（自動生成差異化內容用）=================
TYPE_ZH = {"normal": "一般", "fire": "火", "water": "水", "electric": "電", "grass": "草", "ice": "冰",
           "fighting": "格鬥", "poison": "毒", "ground": "地面", "flying": "飛行", "psychic": "超能力",
           "bug": "蟲", "rock": "岩石", "ghost": "幽靈", "dragon": "龍", "dark": "惡", "steel": "鋼", "fairy": "妖精"}
TYPE_COLOR = {"normal": "#9099a1", "fire": "#ff9d55", "water": "#4d90d5", "electric": "#f4d23c",
              "grass": "#63bc5a", "ice": "#73cec0", "fighting": "#ce4069", "poison": "#ab6ac8",
              "ground": "#d97845", "flying": "#8fa8dd", "psychic": "#f97176", "bug": "#90c12c",
              "rock": "#c7b78b", "ghost": "#5269ad", "dragon": "#0b6dc3", "dark": "#5a5465",
              "steel": "#5a8ea1", "fairy": "#ec8fe6"}
# 每個「防守屬性」被哪些屬性 剋 / 抵抗 / 免疫（標準第六世代相剋表；PoGo 免疫＝×0.390625）
TYPE_DEF = {
    "normal":   (["fighting"], [], ["ghost"]),
    "fire":     (["water", "ground", "rock"], ["fire", "grass", "ice", "bug", "steel", "fairy"], []),
    "water":    (["electric", "grass"], ["fire", "water", "ice", "steel"], []),
    "electric": (["ground"], ["electric", "flying", "steel"], []),
    "grass":    (["fire", "ice", "poison", "flying", "bug"], ["water", "electric", "grass", "ground"], []),
    "ice":      (["fire", "fighting", "rock", "steel"], ["ice"], []),
    "fighting": (["flying", "psychic", "fairy"], ["bug", "rock", "dark"], []),
    "poison":   (["ground", "psychic"], ["grass", "fighting", "poison", "bug", "fairy"], []),
    "ground":   (["water", "grass", "ice"], ["poison", "rock"], ["electric"]),
    "flying":   (["electric", "ice", "rock"], ["grass", "fighting", "bug"], ["ground"]),
    "psychic":  (["bug", "ghost", "dark"], ["fighting", "psychic"], []),
    "bug":      (["fire", "flying", "rock"], ["grass", "fighting", "ground"], []),
    "rock":     (["water", "grass", "fighting", "ground", "steel"], ["normal", "fire", "poison", "flying"], []),
    "ghost":    (["ghost", "dark"], ["poison", "bug"], ["normal", "fighting"]),
    "dragon":   (["ice", "dragon", "fairy"], ["fire", "water", "grass", "electric"], []),
    "dark":     (["fighting", "bug", "fairy"], ["ghost", "dark"], ["psychic"]),
    "steel":    (["fire", "fighting", "ground"], ["normal", "grass", "ice", "flying", "psychic", "bug", "rock", "dragon", "steel", "fairy"], ["poison"]),
    "fairy":    (["poison", "steel"], ["fighting", "bug", "dark"], ["dragon"]),
}
WEATHER_ZH = {"clear": "晴朗", "rain": "下雨", "partlycloudy": "多雲", "cloudy": "陰天",
              "windy": "刮風", "snow": "下雪", "fog": "濃霧"}
TYPE_WEATHER = {"grass": "clear", "fire": "clear", "ground": "clear", "water": "rain", "electric": "rain",
                "bug": "rain", "normal": "partlycloudy", "rock": "partlycloudy", "fairy": "cloudy",
                "fighting": "cloudy", "poison": "cloudy", "dragon": "windy", "flying": "windy",
                "psychic": "windy", "ice": "snow", "steel": "snow", "dark": "fog", "ghost": "fog"}

def _single_mult(atk, deft):
    weak, resist, immune = TYPE_DEF[deft]
    if atk in weak:   return 1.6
    if atk in resist: return 0.625
    if atk in immune: return 0.390625
    return 1.0

def _fmt_mult(m):
    q = math.floor(m * 100 + 0.5) / 100   # 四捨五入到小數兩位（0.625→0.63，不用銀行家捨入）
    return "×" + f"{q:.2f}".rstrip("0").rstrip(".")

def matchups(types):
    """回傳 (weaknesses, resistances)：weak=[(zh, mult_str, is_double)]、resist=[(zh, mult_str)]。"""
    weak, resist = [], []
    for atk in TYPE_DEF:
        m = 1.0
        for dt in types:
            m *= _single_mult(atk, dt)
        if m > 1.0001:
            weak.append((TYPE_ZH[atk], _fmt_mult(m), m, m >= 2.5))
        elif m < 0.9999:
            resist.append((TYPE_ZH[atk], _fmt_mult(m), m))
    weak.sort(key=lambda x: -x[2])
    resist.sort(key=lambda x: x[2])
    return ([(z, s, d) for z, s, _, d in weak], [(z, s) for z, s, _ in resist])

def weathers_of(types):
    seen, out = set(), []
    for t in types:
        w = TYPE_WEATHER.get(t)
        if w and w not in seen:
            seen.add(w); out.append(WEATHER_ZH[w])
    return "、".join(out)

# ---- 讀 POKEDEX（屬性/英文 slug）與 PvP rankings（招式/名次）----
def _norm(s):
    return re.sub(r"[\s()（）]|形態", "", s or "")

def _json_block(txt, name):
    i = txt.find("const " + name); j = txt.find("[", i); depth = 0; k = j
    while k < len(txt):
        c = txt[k]
        if c == "[": depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0: break
        k += 1
    return json.loads(txt[j:k + 1])

_RANK_SRC = open(os.path.join(ROOT, "data", "pokemon_data_and_rankings.js"), encoding="utf-8").read()
POKEDEX = _json_block(_RANK_SRC, "POKEDEX")
PDX_BY_NAME = {_norm(d["name"]): d for d in POKEDEX}


def pdx_of(name, pid):
    """名稱對不到排名資料的寫法時（鎧甲超夢、堅盾劍怪、基格爾德…），退回同圖鑑編號的第一筆（基本型態）。
    名單裡用到退回的幾隻，型態間屬性都相同。"""
    return PDX_BY_NAME.get(_norm(name)) or next((d for d in POKEDEX if d.get("dexNumber") == pid), None)
LEAGUE_ZH = {"great": "超級聯盟", "ultra": "高級聯盟", "master": "大師聯盟"}
RANKS = {}
for _lg, _var in (("great", "POKEMON_RANKINGS_1500"), ("ultra", "POKEMON_RANKINGS_2500"), ("master", "POKEMON_RANKINGS_10000")):
    _arr = _json_block(_RANK_SRC, _var)
    for _i, _e in enumerate(_arr):
        RANKS.setdefault(_norm(_e["name"]), {})[_lg] = {
            "rank": _i + 1, "total": len(_arr), "score": _e["score"],
            "fast": _e["fastMove"], "c1": _e["chargedMove1"], "c2": _e["chargedMove2"],
            "buddy": _e.get("buddyDistance")}

def auto_enrich(name, p):
    """用現有資料自動組出屬性剋制／定位／招式／PvP 內容。"""
    key = _norm(name)
    d = pdx_of(name, p["id"])
    types = d["types"] if d else []
    slug = d["id"] if d else p["gm"].split("_POKEMON_")[-1].lower()
    type_line = "／".join(TYPE_ZH[t] for t in types) if types else "未知"
    types_disp = [(TYPE_ZH[t], TYPE_COLOR[t]) for t in types] or [(type_line, "#9099a1")]
    c1 = TYPE_COLOR[types[0]] if types else "#9099a1"
    c2 = TYPE_COLOR[types[-1]] if types else "#6a5ae0"
    grad = f"linear-gradient(140deg,{c1},{c2})"

    weak, resist = matchups(types) if types else ([], [])
    cp40, cp50 = cp_at(p, 40, 15), cp_at(p, 50, 15)

    lead = (f"{name}（#{p['id']}）是 <strong>{type_line}</strong> 屬性，"
            f"基礎數值 攻擊 <strong>{p['atk']}</strong>／防禦 {p['def']}／耐力 {p['sta']}，"
            f"滿 IV 最大 CP 為 L40 {cp40}、L50 {cp50}。")

    wnote = ""
    if weak:
        prim = weak[0][0]
        dbls = [z for z, s, dd in weak if dd]
        dbl = "，其中對 " + "、".join(dbls) + " 為雙重弱點" if dbls else ""
        wlist = "、".join(z for z, s, dd in weak[:4])
        rlist = "、".join(z for z, s in resist[:4]) if resist else "—"
        wnote = f"用 <strong>{prim}</strong>系招式打 {name} 效果最好；牠怕 {wlist}{dbl}，對 {rlist} 則有抗性。"
    ws = weathers_of(types)
    if ws:
        wnote += f" 天氣為 <strong>{ws}</strong> 時，{name} 的招式會加成、被捕捉時 CP 也較高。"

    atk, dfe, sta = p["atk"], p["def"], p["sta"]
    if atk >= dfe and atk >= sta:
        word = "高攻攻擊手" if atk >= 240 else "攻擊"
        rnote = "攻擊數值突出，適合在團體戰擔任輸出。"
    elif dfe >= atk and dfe >= sta:
        word, rnote = "防禦", "防禦很高，適合放道館或防守型對戰，續戰力佳。"
    else:
        word, rnote = "耐久", "血量厚實，能長時間站場。"
    role = f"{name} 的數值偏 <strong>{word}</strong>（攻擊 {atk}／防禦 {dfe}／耐力 {sta}）。{rnote}"

    r = RANKS.get(key, {})
    moves, leagues = [], []
    league_note = f"{name} 在主要對戰聯盟的排名資料有限。"
    avail = [lg for lg in ("master", "ultra", "great") if lg in r]
    if avail:
        best = max(avail, key=lambda lg: r[lg]["score"])
        b = r[best]
        moves.append(("推薦招式", f"{esc(b['fast'])} ＋ {esc(b['c1'])}／{esc(b['c2'])} <em>（依{LEAGUE_ZH[best]}排名）</em>"))
        if b.get("buddy"):
            moves.append(("好友距離", f"{b['buddy']} 公里"))
        for lg in ("master", "ultra", "great"):
            if lg in r:
                v = r[lg]
                leagues.append((LEAGUE_ZH[lg], round(v["score"], 1), f"#{v['rank']}", v["total"], f"{v['score']}"))
        extra = "（此聯盟無 CP 上限）" if best == "master" else ""
        league_note = (f"在對戰聯盟中，{name} 於 <strong>{LEAGUE_ZH[best]}</strong> 最實用"
                       f"（第 {b['rank']} 名／共 {b['total']}，評分 {b['score']}）{extra}。")

    return {
        "slug": slug, "types": types_disp, "type_line": type_line, "grad": grad, "lead": lead,
        "weak": weak or [("—", "", False)], "resist": resist or [("—", "")],
        "type_note": wnote or "屬性相剋資料不足。", "role": role,
        "moves": moves, "leagues": leagues, "league_note": league_note,
    }

# ---- 手寫覆寫（想人工潤飾的少數幾隻放這裡；其餘走 auto_enrich）----
MANUAL_ENRICH = {
    "烈空坐": {
        "slug": "rayquaza",
        "types": [("龍", TYPE_COLOR["dragon"]), ("飛行", TYPE_COLOR["flying"])],
        "grad": f"linear-gradient(140deg,{TYPE_COLOR['dragon']},{TYPE_COLOR['flying']})",
        "type_line": "龍／飛行",
        "lead": ("烈空坐（#384）是<strong>龍／飛行</strong>屬性的傳說寶可夢，基礎數值 攻擊 <strong>284</strong>／防禦 170／耐力 213"
                 " —— 以全遊戲數一數二的攻擊力，牠是典型的<strong>高攻低防「玻璃大砲」</strong>，主要價值在團體戰的龍系爆發輸出。"),
        "weak": [("冰", "×2.56", True), ("岩石", "×1.6", False), ("龍", "×1.6", False), ("妖精", "×1.6", False)],
        "resist": [("地面", "免疫 ×0.39"), ("草", "×0.39"), ("火", "×0.63"), ("水", "×0.63"), ("格鬥", "×0.63"), ("蟲", "×0.63")],
        "type_note": ("龍／飛行的組合最怕冰系 —— 兩種屬性都被冰剋，形成雙重弱點。用<strong>冰系</strong>招式打烈空坐傷害最高；"
                      "帶牠出戰時要避開對方的冰、岩石與妖精。天氣為<strong>刮風</strong>時，牠的龍系與飛行系招式都會加成，野外遇到時 CP 也較高。"),
        "role": ("烈空坐是<strong>五星傳說團體戰頭目</strong>，可捕獲、有異色（閃光）版本。憑 284 攻擊，牠是最強的龍系攻擊手之一，"
                 "適合在團體戰面對其他龍系對手（如快龍、暴飛龍、烈咬陸鯊）時打出高輸出；但防禦僅 170，續戰力偏低，屬於秒傷取向的玻璃大砲。"),
        "moves": [("團體戰輸出", "龍尾 ＋ <b>畫龍點睛</b>（招牌絕招，龍系爆發最高）"),
                  ("對戰 PvP", "龍尾 ＋ 廣域破壞／畫龍點睛 <em>（皆為菁英招式）</em>"),
                  ("好友距離", "20 公里")],
        "leagues": [("大師聯盟", 76, "#96", 405, "76.3"),
                    ("高級聯盟", 43, "#361", 841, "77.8"),
                    ("超級聯盟", 39, "#445", 1143, "77.2")],
        "league_note": ("烈空坐在對戰中更適合<strong>大師聯盟</strong> —— 這裡沒有 CP 上限，牠不必刻意壓等。"
                        "在高級與超級聯盟因體質偏脆、CP 又常超標，表現只算普通，一般不是首選。"),
    }
}

def get_enrich(name, p):
    return MANUAL_ENRICH.get(name) or auto_enrich(name, p)

# 要產生靜態頁的清單：data/cp_static_targets.json（[{name, slug}]，依搜尋需求排序）
with open(os.path.join(ROOT, "data", "cp_static_targets.json"), encoding="utf-8") as _f:
    TARGET_LIST = json.load(_f)["targets"]
SLUG_OF = {t["name"]: t["slug"] for t in TARGET_LIST}
POOL = []   # main() 填入：所有靜態頁的 名稱／slug／圖／屬性，給「同屬性的熱門寶可夢」用

CSS = """
:root{--bg:#f3f5f8;--card:#fff;--ink:#14171c;--ink2:#3a3f47;--muted:#68707c;--line:#e6e9ee;--soft:#f6f7f9;
 --blue:#1877f2;--blue2:#4aa3e8;--red:#e63946;--green:#2f9e57;--accent:#6a5ae0;--accent2:#4aa3e8}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font-family:system-ui,-apple-system,"Segoe UI","PingFang TC","Microsoft JhengHei",sans-serif;
 line-height:1.7;-webkit-font-smoothing:antialiased}
.wrap{max-width:720px;margin:0 auto;padding:18px 16px 84px}
.crumb{font-size:13px;color:var(--muted);margin:2px 0 14px}
.crumb a{color:var(--blue);text-decoration:none}
.crumb a:hover{text-decoration:underline}
.card{background:var(--card);border-radius:16px;box-shadow:0 1px 2px rgba(16,24,40,.05),0 6px 20px rgba(16,24,40,.05);
 padding:22px;margin-bottom:16px}
h2{font-size:18.5px;margin:0 0 12px;color:var(--ink);letter-spacing:-.01em;display:flex;align-items:center;gap:10px}
h2::before{content:"";width:5px;height:20px;border-radius:3px;background:linear-gradient(var(--accent),var(--accent2));flex:none}
.sub{color:var(--muted);font-size:13.5px;margin:-4px 0 14px}
/* 廣告框預留（與 css/main.css、js/ads.js 相同；ads.js 會把廣告放進這個框） */
.site-ad{box-sizing:border-box;width:min(100% - 32px,1100px);min-height:120px;margin:28px auto 32px;padding:8px 0;text-align:center}
.site-ad-label{display:block;margin:0 0 6px;color:#7b8190;font:11px/1.3 system-ui,sans-serif;letter-spacing:.04em}
.site-ad ins,.site-ad .site-ad-ph{display:block;min-height:100px;overflow:hidden}
@media(max-width:600px){.site-ad{width:calc(100% - 24px);min-height:100px;margin:20px auto 24px}.site-ad ins,.site-ad .site-ad-ph{min-height:80px}}
.site-ad[data-ad-reserved]{visibility:hidden}
/* 主視覺 */
.card.hero{padding:0;overflow:hidden}
.band{height:84px;background:linear-gradient(120deg,var(--accent),var(--accent2))}
.hero-main{display:flex;gap:18px;align-items:flex-start;padding:0 22px;margin-top:-56px}
.sprite{width:120px;height:120px;flex:none;border-radius:50%;background:#fff;padding:8px;
 box-shadow:0 4px 14px rgba(16,24,40,.14);object-fit:contain}
.hero-txt{padding-top:64px;min-width:0}
.dexno{font-size:13px;color:var(--muted);font-weight:700;letter-spacing:.04em}
h1{font-size:27px;line-height:1.25;margin:2px 0 8px;font-weight:800;letter-spacing:-.015em}
.types{display:flex;gap:8px;flex-wrap:wrap}
.type{font-size:12.5px;font-weight:700;color:#fff;padding:3px 12px;border-radius:999px}
/* 注意：不要叫 .hundo —— 高 IV 表 100% 那一列是 tr.hundo，同名會把那一列也變成 grid */
.h-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;padding:18px 22px 0}
.h-tile{background:var(--soft);border:1px solid var(--line);border-radius:14px;padding:12px 10px 10px;text-align:center}
.h-tile .h-lab{display:block;font-size:12.5px;color:var(--ink2);font-weight:600}
.h-tile b{display:block;font-size:28px;line-height:1.2;margin:4px 0 2px;font-weight:800;font-variant-numeric:tabular-nums;color:var(--ink)}
.h-tile .h-lv{font-size:12px;color:var(--muted);font-weight:600}
.h-tile.main{background:linear-gradient(160deg,#fff,#f1f6ff);border-color:#cfe0fb}
.h-tile.main b{color:var(--blue)}
.hundo-note{margin:10px 22px 0;font-size:13px;color:var(--muted)}
.hundo-note strong{color:var(--ink)}
.chips{display:flex;flex-wrap:wrap;gap:8px;padding:12px 22px 0}
.pill{font-size:12.5px;background:var(--soft);border:1px solid var(--line);border-radius:999px;padding:4px 11px;color:var(--ink2);font-variant-numeric:tabular-nums}
.pill b{color:var(--ink)}
.lead{font-size:15px;color:var(--ink2);margin:0;padding:14px 22px 22px}
.lead strong,.note strong,.role strong{color:var(--ink)}
@media (max-width:480px){
 .hero-main{flex-direction:column;align-items:flex-start;margin-top:-60px;gap:8px}.hero-txt{padding-top:0}
 .sprite{width:104px;height:104px}
 h1{font-size:24px}
 .h-grid{gap:8px;padding:16px 16px 0}.h-tile{padding:10px 4px 8px}.h-tile b{font-size:23px}
 .h-tile .h-lab{font-size:11.5px}
 .hero-main,.chips{padding-left:16px;padding-right:16px}.hundo-note{margin:10px 16px 0}.lead{padding:14px 16px 18px}
 .card{padding:18px 16px}
}
/* CP 反查 IV */
.rv{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;align-items:end}
.rv label{display:flex;flex-direction:column;gap:4px;font-size:12.5px;font-weight:700;color:var(--ink2)}
.rv input,.rv select{font:inherit;font-size:16px;padding:9px 10px;border:1px solid #cfd5dd;border-radius:10px;background:#fff;width:100%;min-width:0}
.rv input:focus,.rv select:focus{outline:2px solid #bcd5fb;border-color:var(--blue)}
.rv button{font:inherit;font-weight:800;font-size:15px;border:0;border-radius:10px;padding:10px 12px;background:var(--blue);color:#fff;cursor:pointer}
.rv button:hover{background:#166fe0}
@media (max-width:480px){.rv{grid-template-columns:1fr 1fr}.rv button{grid-column:span 2}}
.rv-msg{font-size:13.5px;color:var(--muted);margin:12px 0 0}
.rv-msg strong{color:var(--ink)}
table.rvt{border-collapse:collapse;width:100%;font-size:13.5px;font-variant-numeric:tabular-nums;margin-top:10px}
table.rvt th,table.rvt td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:right;white-space:nowrap}
table.rvt thead th{color:var(--muted);font-size:12.5px;font-weight:700}
table.rvt td.l,table.rvt th.l{text-align:left}
table.rvt tr.top td{background:#fff5f5}
table.rvt td.iv{font-weight:800}
.rv-more{margin-top:10px;font:inherit;font-size:13.5px;background:none;border:1px solid var(--line);border-radius:999px;padding:6px 14px;cursor:pointer;color:var(--ink2)}
/* 表格 */
.tbl-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--line);border-radius:12px}
table.cp{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}
table.cp caption{caption-side:top;text-align:left;color:var(--muted);font-size:13px;padding:10px 12px 6px}
table.cp th,table.cp td{border-top:1px solid var(--line);padding:7px 12px;text-align:right;white-space:nowrap}
table.cp thead th{background:var(--soft);color:var(--ink);font-weight:700}
table.cp tbody th{text-align:left;font-weight:600}
table.cp td.mx{font-weight:700;color:var(--green)}
table.cp td.mn{color:var(--muted)}
table.cp td.nt,table.cp thead th:last-child{text-align:left;white-space:normal;color:var(--muted);font-size:13px;width:42%}
table.cp thead th:last-child{color:var(--ink)}
table.cp tr.key th,table.cp tr.key td{background:#eef7f1}
table.cp tr.bb th,table.cp tr.bb td{background:#fff7e8}
.foot-t{color:var(--muted);font-size:13px;margin:12px 0 0}
/* 高 IV CP·HP 對照表 */
table.iv{border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums;white-space:nowrap;min-width:560px;width:100%}
table.iv th,table.iv td{border-top:1px solid var(--line);border-left:1px solid var(--line);padding:4px 7px;text-align:right}
table.iv thead th{background:var(--soft);color:var(--ink);font-weight:700;text-align:center}
table.iv td.pct{text-align:left;color:var(--muted)}
table.iv tr.hundo td.pct{color:var(--red);font-weight:800}
table.iv td.hp{color:var(--muted)}
table.iv td.iv{color:#fff;font-weight:700;text-align:center}
table.iv td.v15{background:#e63946}
table.iv td.v14{background:#2b6cb0}
table.iv td.v13{background:#2f9e57}
table.iv td.v12{background:#d98324}
table.iv td.v11{background:#8a8f98}
.iv-legend{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 0;font-size:12px;color:var(--muted)}
.iv-legend span{display:inline-flex;align-items:center;gap:5px}
.iv-legend i{width:12px;height:12px;border-radius:3px;display:inline-block}
/* 屬性剋制、招式、聯盟 */
.matchup{display:flex;flex-direction:column;gap:10px;margin:4px 0 12px}
.mg{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.mlab{flex:none;min-width:44px;font-size:13px;font-weight:700;color:var(--muted)}
.chip{font-size:13px;font-weight:600;padding:5px 11px;border-radius:9px;display:inline-flex;gap:6px;align-items:center}
.chip em{font-style:normal;font-size:11.5px;opacity:.85;font-variant-numeric:tabular-nums}
.chip.wk{background:#fdecec;color:#c5221f}.chip.wk.dbl{background:#f9d5d3;color:#a50e0e;font-weight:800}
.chip.rs{background:#e7f5ec;color:#1e7e46}
.note{color:var(--muted);font-size:13.5px;margin:6px 0 0}
.role{font-size:14.5px;color:var(--ink2);margin:0 0 14px}
ul.moves{list-style:none;margin:4px 0 0;padding:0;display:flex;flex-direction:column;gap:9px}
ul.moves li{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px}
ul.moves .k{flex:none;width:82px;font-size:12.5px;font-weight:700;color:var(--muted)}
ul.moves .v{font-size:14px}ul.moves .v b{color:var(--blue)}
ul.moves .v em{font-style:normal;font-size:12px;color:#d97706;font-weight:700}
.league{display:grid;gap:10px;margin:6px 0 12px}
.lrow{display:grid;grid-template-columns:76px 1fr auto;gap:12px;align-items:center}
.lname{font-size:13.5px;font-weight:600}
.lbar{height:9px;background:#e9ebee;border-radius:999px;overflow:hidden}
.lbar i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,var(--accent),var(--accent2))}
.lrk{font-size:12.5px;color:var(--muted);font-variant-numeric:tabular-nums;white-space:nowrap}
.lrk b{color:var(--ink);font-size:13.5px}
@media (max-width:480px){.lrow{grid-template-columns:64px 1fr}.lrk{grid-column:2;text-align:right}}
/* 相關寶可夢 */
.nav2{display:flex;justify-content:space-between;gap:10px;margin:0 0 14px}
.nav2 a{flex:1;display:block;background:var(--soft);border:1px solid var(--line);border-radius:12px;padding:9px 12px;
 color:var(--ink);text-decoration:none;font-size:14px;font-weight:600}
.nav2 a small{display:block;color:var(--muted);font-weight:600;font-size:11.5px}
.nav2 a.nx{text-align:right}
.nav2 a:hover{border-color:#bcd5fb;background:#f1f6ff}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:10px}
.grid a{display:flex;flex-direction:column;align-items:center;gap:4px;background:var(--soft);border:1px solid var(--line);
 border-radius:12px;padding:10px 6px;text-decoration:none;color:var(--ink);font-size:13px;font-weight:600;text-align:center}
.grid a img{width:56px;height:56px;object-fit:contain}
.grid a:hover{border-color:#bcd5fb;background:#f1f6ff}
.cta{display:inline-block;background:var(--blue);color:#fff;text-decoration:none;font-weight:700;
 padding:11px 20px;border-radius:10px;font-size:15px}
.cta:hover{background:#166fe0}
.pagefoot{text-align:center;color:var(--muted);font-size:12.5px;margin-top:22px}
.pagefoot a{color:var(--muted)}
/* 浮動搜尋鈕 */
.fab{position:fixed;right:16px;bottom:16px;z-index:60;display:inline-flex;align-items:center;gap:8px;
 background:var(--blue);color:#fff;text-decoration:none;font-weight:700;font-size:14px;
 padding:12px 18px;border-radius:999px;box-shadow:0 6px 18px rgba(24,119,242,.45)}
.fab:hover{background:#166fe0}
@media (max-width:480px){.fab{padding:12px 16px}}
/* 各語言的 IV100 CP 列表頁（/<lang>/cp/） */
.hubq{width:100%;font:inherit;font-size:16px;padding:11px 14px;border:1px solid #cfd5dd;border-radius:12px;margin:4px 0 14px}
.hubq:focus{outline:2px solid #bcd5fb;border-color:var(--blue)}
.hub{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
.hub a{display:flex;align-items:center;gap:8px;background:#fff;border:1px solid var(--line);border-radius:12px;padding:6px 10px 6px 6px;text-decoration:none;color:var(--ink);font-size:13.5px;font-weight:600;line-height:1.3;min-width:0}
.hub a img{width:48px;height:48px;flex:none;object-fit:contain}
.hub a small{display:block;color:var(--muted);font-weight:600;font-size:11.5px;font-variant-numeric:tabular-nums}
.hub a:hover{border-color:#bcd5fb;background:#f1f6ff}
.hub a[hidden]{display:none}
.hub>div{display:flex;align-items:center;gap:8px;background:#fff;border:1px solid var(--line);border-radius:12px;padding:6px 10px 6px 6px;font-size:13.5px;font-weight:600;line-height:1.3;min-width:0}
.hub>div img{width:48px;height:48px;flex:none;object-fit:contain}
.hub>div small{display:block;color:var(--muted);font-weight:600;font-size:11.5px;font-variant-numeric:tabular-nums}
.hub[hidden],#popwrap[hidden],.sub[hidden]{display:none}
/* 各語言首頁（/<lang>/）的工具卡 */
.tools{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:0 0 16px}
.tool{display:block;background:#fff;border:1px solid var(--line);border-radius:16px;padding:18px;text-decoration:none;color:var(--ink);box-shadow:0 1px 2px rgba(16,24,40,.05),0 6px 20px rgba(16,24,40,.05)}
.tool:hover{border-color:#bcd5fb}
.tool .ico{font-size:28px;line-height:1}
.tool b{display:block;font-size:17px;margin:8px 0 4px}
.tool span:last-child{display:block;color:var(--ink2);font-size:14px;line-height:1.6}
.more a{color:var(--blue);text-decoration:none;font-weight:600}.more a:hover{text-decoration:underline}
"""

def esc(s): return html.escape(str(s), quote=True)

# ---- CP 反查 IV：/cp/<slug>/ 與 /<lang>/cp/<slug>/ 共用 js/cp-reverse.js ----
# 每頁在 <script type="application/json" id="rvData"> 放 {a,d,s,slug,lang,t:{介面文字}}；
# 介面文字是站內自己寫的固定字串（不是使用者輸入），可以直接拼進 innerHTML。
RV_JS_FILE = """// 由 scripts/build_cp_static.py 產生，請勿手改。/cp/<slug>/ 與 /<lang>/cp/<slug>/ 共用的「CP 反查 IV」。
(function(){
var el=document.getElementById('rvData'),f=document.getElementById('rvForm'),o=document.getElementById('rvOut');
if(!el||!f||!o)return;
var D=JSON.parse(el.textContent),T=D.t,C=__CPM__,F=[],i;
for(i=0;i<C.length;i++){F.push([i+1,C[i]]);if(i+1<C.length)F.push([i+1.5,Math.sqrt((C[i]*C[i]+C[i+1]*C[i+1])/2)]);}
function cp(m,a,d,s){return Math.max(10,Math.floor((D.a+a)*Math.sqrt(D.d+d)*Math.sqrt(D.s+s)*m*m/10));}
function hp(m,s){return Math.max(10,Math.floor((D.s+s)*m));}
function fm(s,v){return s.replace(/\\{(\\w+)\\}/g,function(_,k){return v[k];});}
f.addEventListener('submit',function(ev){ev.preventDefault();
 var c=parseInt(document.getElementById('rvCp').value,10),h=parseInt(document.getElementById('rvHp').value,10),L=parseFloat(document.getElementById('rvLv').value);
 if(!(c>=10)){o.innerHTML='<p class="rv-msg">'+T.need+'</p>';return;}
 var r=[];F.forEach(function(x){if(L&&x[0]!==L)return;for(var a=0;a<16;a++)for(var d=0;d<16;d++)for(var s=0;s<16;s++){if(cp(x[1],a,d,s)!==c)continue;var hh=hp(x[1],s);if(h&&hh!==h)continue;r.push([x[0],a,d,s,hh]);}});
 if(!r.length){o.innerHTML='<p class="rv-msg">'+T.none+'</p>';return;}
 r.sort(function(x,y){return (y[1]+y[2]+y[3])-(x[1]+x[2]+x[3])||x[0]-y[0];});
 var hi=r[0][1]+r[0][2]+r[0][3],lo=r[r.length-1][1]+r[r.length-1][2]+r[r.length-1][3],rows='';
 r.forEach(function(x,k){var t=x[1]+x[2]+x[3];rows+='<tr'+(k>=30?' hidden':'')+(t===45?' class="top"':'')+'><td class="l">'+T.lv+x[0]+'</td><td class="iv">'+x[1]+' / '+x[2]+' / '+x[3]+'</td><td>'+(t/45*100).toFixed(1)+'%</td><td>'+x[4]+'</td></tr>';});
 o.innerHTML='<p class="rv-msg">'+fm(r.length===1&&T.sum1?T.sum1:T.sum,{cp:'<strong>'+c+'</strong>',hp:h?fm(T.hpPart,{hp:'<strong>'+h+'</strong>'}):'',n:'<strong>'+r.length+'</strong>',lo:Math.round(lo/45*100),hi:Math.round(hi/45*100)})+(r.length>1&&!h?T.narrow:'')+'</p>'
  +'<div class="tbl-wrap"><table class="rvt"><thead><tr><th class="l">'+T.thLv+'</th><th>'+T.thIv+'</th><th>IV%</th><th>'+T.thHp+'</th></tr></thead><tbody>'+rows+'</tbody></table></div>'
  +(r.length>30?'<button type="button" class="rv-more">'+fm(T.all,{n:r.length})+'</button>':'');
 var m=o.querySelector('.rv-more');if(m)m.onclick=function(){o.querySelectorAll('tr[hidden]').forEach(function(t){t.hidden=false;});m.remove();};
 if(window.track)window.track('cp_reverse_static',{mon:D.slug,lang:D.lang,hits:r.length});
});
})();
"""

RV_T_ZH = {"need": "請輸入 CP（10 以上）。",
           "none": "找不到符合的組合。請確認 CP 是否正確（天氣加成、強化過都會改變等級）。",
           "sum": "CP {cp}{hp}：共 {n} 種可能，IV 約 <strong>{lo}%～{hi}%</strong>。", "hpPart": "、HP {hp}",
           "sum1": "CP {cp}{hp}：只有 1 種可能，IV <strong>{hi}%</strong>。",
           "narrow": "再填 HP 可以縮小範圍。", "lv": "Lv", "thLv": "等級", "thIv": "攻 / 防 / 耐", "thHp": "HP",
           "all": "顯示全部 {n} 筆"}


def rv_data_json(p, slug, lang, t):
    """頁面上的 #rvData；把 </ 換成 <\\/，避免字串裡出現 </script> 提早結束標籤。"""
    return json.dumps({"a": p["atk"], "d": p["def"], "s": p["sta"], "slug": slug, "lang": lang, "t": t},
                      ensure_ascii=False).replace("</", "<\\/")


# 其他語言版本（scripts/build_cp_static_i18n.py 產生）：/<lang>/cp/<slug>/
I18N_LANGS = ["en", "ja", "ko", "fr", "de", "es"]


def alternates(slug):
    """同一隻寶可夢 7 個語言版本互相標示；x-default 指向英文版。"""
    out = [f'<link rel="alternate" hreflang="zh-Hant" href="{ORIGIN}/cp/{slug}/">']
    out += [f'<link rel="alternate" hreflang="{l}" href="{ORIGIN}/{l}/cp/{slug}/">' for l in I18N_LANGS]
    out.append(f'<link rel="alternate" hreflang="x-default" href="{ORIGIN}/en/cp/{slug}/">')
    return "\n".join(out)


def write_assets():
    """共用的 css/cp-static.css 與 js/cp-reverse.js（每頁不再各自內嵌，瀏覽多頁時可快取）。"""
    with open(os.path.join(ROOT, "css", "cp-static.css"), "w", encoding="utf-8", newline="\n") as f:
        f.write("/* 由 scripts/build_cp_static.py 產生，請勿手改（改 CSS 常數）。/cp/ 與 /<lang>/cp/ 靜態頁共用。 */\n" + CSS.strip() + "\n")
    with open(os.path.join(ROOT, "js", "cp-reverse.js"), "w", encoding="utf-8", newline="\n") as f:
        f.write(RV_JS_FILE.replace("__CPM__", json.dumps(CPM[:BB])))


def mon_url(name, from_static=True):
    """站內連到某隻寶可夢：有靜態頁就連靜態頁，沒有就連 ?mon= 深連結（編碼與 build_cp_sitemap.py 的 quote() 一致）。"""
    s = SLUG_OF.get(name)
    if s:
        return f"../{s}/" if from_static else f"cp/{s}/"
    return ("../../" if from_static else "") + "?tab=cp-checker-app&mon=" + quote(name)


def build(name):
    p = CP_DATA[name]; e = get_enrich(name, p)
    pid = p["id"]; slug = SLUG_OF[name]
    url = f"{ORIGIN}/cp/{slug}/"
    cp15, cp20, cp25 = cp_at(p, 15, 15), cp_at(p, 20, 15), cp_at(p, 25, 15)
    cp40, cp50, cp51 = cp_at(p, 40, 15), cp_at(p, 50, 15), cp_at(p, BB, 15)
    title = f"{name} IV100 CP 速查｜Lv1-50 全等級 CP 表｜Pokémon Go 工具箱"
    desc = (f"{name}（#{pid}，{e['type_line']}）IV 100% CP：田野調查 Lv15 {cp15}、團體戰 Lv20 {cp20}、"
            f"天氣加成 Lv25 {cp25}；含 CP 反查 IV、Lv1～50 全等級 CP 表、屬性剋制、推薦招式與 PvP 聯盟定位。")
    c1 = e["types"][0][1] if e["types"] else "#6a5ae0"
    c2 = e["types"][-1][1] if e["types"] else "#4aa3e8"

    # CP 表
    rows = ""
    for L in range(1, BB + 1):
        note = "⭐ 最佳夥伴加成" if L == BB else KEY.get(L, "")
        cls = ("key " if L in KEY else "") + ("bb" if L == BB else "")
        rows += (f'<tr class="{cls.strip()}"><th scope="row">Lv{L}</th>'
                 f'<td class="mx">{cp_at(p,L,15)}</td><td class="mn">{cp_at(p,L,0)}</td>'
                 f'<td class="nt">{note}</td></tr>')

    iv_table = build_iv_table(p)
    types_html = "".join(f'<span class="type" style="background:{c}">{esc(z)}</span>' for z, c in e["types"])
    weak_html = "".join(f'<span class="chip wk{" dbl" if d else ""}">{esc(t)} <em>{esc(m)}</em></span>'
                        for t, m, d in e["weak"])
    resist_html = "".join(f'<span class="chip rs">{esc(t)} <em>{esc(m)}</em></span>' for t, m in e["resist"])
    moves_html = "".join(f'<li><span class="k">{esc(k)}</span><span class="v">{v}</span></li>' for k, v in e["moves"])
    moves_ul = f'<ul class="moves">{moves_html}</ul>' if moves_html else ""   # 沒有 PvP 資料就不顯示招式列
    league_html = "".join(
        f'<div class="lrow"><span class="lname">{esc(n)}</span>'
        f'<span class="lbar"><i style="width:{w}%"></i></span>'
        f'<span class="lrk"><b>{esc(rk)}</b> / {tot} · {sc} 分</span></div>'
        for n, w, rk, tot, sc in e["leagues"])
    league_card = (f'<section class="card"><h2>{esc(name)} 對戰聯盟表現</h2><div class="league">{league_html}</div>'
                   f'<p class="note">{e["league_note"]}</p></section>') if league_html else ""

    # 圖鑑相鄰 + 同屬性的熱門寶可夢（都連到有靜態頁的優先，方便爬蟲與使用者在 /cp/ 之間移動）
    prev_n, next_n = dex_neighbor(pid, -1), dex_neighbor(pid, +1)
    nav2 = ""
    if prev_n or next_n:
        a = (f'<a class="pv" href="{esc(mon_url(prev_n))}"><small>← 上一隻</small>{esc(prev_n)}</a>' if prev_n else '<span></span>')
        b = (f'<a class="nx" href="{esc(mon_url(next_n))}"><small>下一隻 →</small>{esc(next_n)}</a>' if next_n else '<span></span>')
        nav2 = f'<div class="nav2">{a}{b}</div>'
    my_types = {z for z, _ in e["types"]}
    same = [t for t in POOL if t["name"] != name and my_types & set(t["types"])]
    same.sort(key=lambda t: (t["types"][0] not in my_types, t["rank"]))
    grid = "".join(f'<a href="../{t["slug"]}/"><img src="{esc(t["img"])}" alt="" width="56" height="56" loading="lazy">{esc(t["name"])}</a>'
                   for t in same[:8])
    grid_html = (f'<p class="sub" style="margin:0 0 10px">同屬性的熱門寶可夢</p><div class="grid">{grid}</div>') if grid else ""

    rv_data = rv_data_json(p, slug, "zh", RV_T_ZH)

    ld = (
        '{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":['
        '{"@type":"ListItem","position":1,"name":"Pokémon Go 工具箱","item":"' + ORIGIN + '/"},'
        '{"@type":"ListItem","position":2,"name":"IV100 CP 查詢","item":"' + ORIGIN + '/?tab=cp-checker-app"},'
        '{"@type":"ListItem","position":3,"name":"' + name + ' CP","item":"' + url + '"}]}'
    )

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8866689605007086" crossorigin="anonymous"></script>
<script src="../../js/zh-search.js"></script>
<script src="../../js/analytics.js"></script>
<!-- 全站瀏覽計數：config.js 是 CI 產生的，沒有的話計數器會自己停用（不會報錯） -->
<script src="../../config.js"></script>
<script src="../../js/pageview-counter.js" defer></script>
<link rel="icon" type="image/png" sizes="192x192" href="../../img/masterball.png">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
{alternates(slug)}
<meta name="robots" content="index,follow">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Pokémon Go 工具箱">
<meta property="og:title" content="{esc(name)} IV100 CP 查詢｜Lv1-50 全等級 CP 表">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{esc(p['imageUrl'])}">
<meta property="og:locale" content="zh_TW">
<script type="application/ld+json">{ld}</script>
<link rel="stylesheet" href="../../css/cp-static.css">
</head>
<body style="--accent:{c1};--accent2:{c2}">
<div class="wrap">
  <nav class="crumb" aria-label="麵包屑">
    <a href="../../">工具箱首頁</a> ›
    <a href="../../?tab=cp-checker-app">IV100 CP 查詢</a> ›
    <span>{esc(name)}</span>
  </nav>
  <!-- 廣告框預留：位置與 js/ads.js 原本插入的位置相同（麵包屑之後），先佔好高度，廣告載入時版面不會跳動 -->
  <aside class="site-ad" aria-label="廣告" data-ad-reserved><span class="site-ad-label">廣告</span><div class="site-ad-ph"></div></aside>

  <header class="card hero">
    <div class="band"></div>
    <div class="hero-main">
      <img class="sprite" src="{esc(p['imageUrl'])}" alt="{esc(name)}" width="120" height="120">
      <div class="hero-txt">
        <div class="dexno">#{pid}</div>
        <h1>{esc(name)} IV100 CP</h1>
        <div class="types">{types_html}</div>
      </div>
    </div>
    <div class="h-grid">
      <div class="h-tile"><span class="h-lab">🔬 田野調查</span><b>{cp15}</b><span class="h-lv">Lv15</span></div>
      <div class="h-tile main"><span class="h-lab">⚔️ 團體戰・孵蛋</span><b>{cp20}</b><span class="h-lv">Lv20</span></div>
      <div class="h-tile"><span class="h-lab">☀️ 天氣加成</span><b>{cp25}</b><span class="h-lv">Lv25</span></div>
    </div>
    <p class="hundo-note">以上是 <strong>IV 100%（15/15/15）</strong>時的 CP。在田野調查（Lv15）、團體戰或孵蛋（Lv20）、天氣加成團體戰（Lv25）抓到時，CP 正好是上面的數字，幾乎可以確定是 100% 個體；其他情況或想確認，請用下面的「CP 反查 IV」。</p>
    <div class="chips">
      <span class="pill">最大 CP <b>Lv40 {cp40}</b></span><span class="pill"><b>Lv50 {cp50}</b></span><span class="pill"><b>Lv51 {cp51}</b></span>
      <span class="pill">攻 <b>{p['atk']}</b> · 防 <b>{p['def']}</b> · 耐 <b>{p['sta']}</b></span>
    </div>
    <p class="lead">{e['lead']}</p>
  </header>

  <section class="card" id="rev">
    <h2>{esc(name)} CP 反查 IV</h2>
    <p class="sub">輸入抓到時的 CP（可再加 HP），列出所有可能的等級與個體值組合。</p>
    <form class="rv" id="rvForm">
      <label>CP<input id="rvCp" type="number" inputmode="numeric" min="10" placeholder="例：{cp20}"></label>
      <label>HP<input id="rvHp" type="number" inputmode="numeric" min="10" placeholder="選填"></label>
      <label>等級<select id="rvLv"><option value="">不限</option><option value="15">Lv15 田野調查</option><option value="20">Lv20 團體戰・孵蛋</option><option value="25">Lv25 天氣加成</option></select></label>
      <button type="submit">查詢</button>
    </form>
    <div id="rvOut" aria-live="polite"></div>
  </section>

  <section class="card">
    <h2>{esc(name)} 高 IV CP·HP 對照表</h2>
    <p class="sub">IV 總和最高的 35 種組合（IV% ≥ 91.1%），以及各自在 Lv15／20／25／40 的 CP 與 HP。攻／防／耐為個體值（0～15）。</p>
    <div class="tbl-wrap">{iv_table}</div>
    <div class="iv-legend">
      <span><i style="background:#e63946"></i>15</span>
      <span><i style="background:#2b6cb0"></i>14</span>
      <span><i style="background:#2f9e57"></i>13</span>
      <span><i style="background:#d98324"></i>12</span>
      <span><i style="background:#8a8f98"></i>11</span>
    </div>
  </section>

  <section class="card">
    <h2>{esc(name)} 全等級 CP 對照表（Lv1～Lv{MAX_LEVEL}）</h2>
    <p class="sub"><strong>100% IV</strong>（15/15/15）為該等級的 CP 上限，<strong>0% IV</strong>（0/0/0）為下限。</p>
    <div class="tbl-wrap">
      <table class="cp">
        <caption>{esc(name)} 各等級 CP（100% IV / 0% IV）</caption>
        <thead><tr><th>等級</th><th>100% IV</th><th>0% IV</th><th>說明</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <p class="foot-t">Lv{BB} 為最佳夥伴狀態下的等級上限；一般強化上限為 Lv{MAX_LEVEL}。資料來源為 Pokémon GO GAME_MASTER。</p>
  </section>

  <section class="card">
    <h2>{esc(name)} 屬性與剋制</h2>
    <div class="matchup">
      <div class="mg"><span class="mlab">弱點</span>{weak_html}</div>
      <div class="mg"><span class="mlab">抗性</span>{resist_html}</div>
    </div>
    <p class="note">{e['type_note']}</p>
  </section>

  <section class="card">
    <h2>{esc(name)} 角色定位與推薦招式</h2>
    <p class="role">{e['role']}</p>
    {moves_ul}
  </section>

  {league_card}

  <section class="card">
    <h2>相關寶可夢</h2>
    {nav2}
    {grid_html}
  </section>

  <div style="text-align:center;margin-top:8px">
    <a class="cta" href="../../?tab=cp-checker-app">查詢其他寶可夢的 IV100 CP →</a>
  </div>

  <p class="pagefoot"><a href="../../">Pokémon Go 工具箱</a> · IV100 CP、PvP 排名、搜尋指令、團體戰與孵蛋查詢</p>
  <p class="pagefoot"><a href="../../about/">關於本站</a> · <a href="../../privacy/">隱私權政策</a> · <a href="../../disclaimer/">免責聲明</a></p>
</div>

<a class="fab" href="../../?tab=cp-checker-app" aria-label="搜尋其他寶可夢">🔍 <span>搜尋寶可夢</span></a>
<script type="application/json" id="rvData">{rv_data}</script>
<script src="../../js/cp-reverse.js" defer></script>
<script src="../../js/ads.js" defer></script>
</body>
</html>"""


def write_slug_module(targets):
    """給 js/cp-checker.js 用：哪些寶可夢有靜態頁（?mon= 轉址與站內連結用）。"""
    body = ",\n".join(f'  [{json.dumps(t["name"], ensure_ascii=False)}, {json.dumps(t["slug"])}]' for t in targets)
    js = ("// 由 scripts/build_cp_static.py 產生，請勿手改。\n"
          "// [名稱, slug]：有 /cp/<slug>/ 靜態頁的寶可夢。名單在 data/cp_static_targets.json。\n"
          "export const CP_STATIC = new Map([\n" + body + "\n]);\n")
    open(os.path.join(ROOT, "js", "cp-static-slugs.js"), "w", encoding="utf-8", newline="\n").write(js)


def write_sitemap_block(targets, fps):
    """sitemap.xml 裡的 /cp/ 靜態頁區塊（只換這個區塊，其他內容不動）。
    lastmod 只在該頁內容（指紋）改變時才換成今天，狀態存在 data/cp_static_lastmod.json；
    每次都寫今天的話，Google 久了會不再相信 lastmod。"""
    path = os.path.join(ROOT, "sitemap.xml")
    xml = open(path, encoding="utf-8", newline="").read()
    nl = "\r\n" if "\r\n" in xml else "\n"
    # 移除舊的 /cp/ 網址（含以前手寫的）與舊區塊註解
    xml = re.sub(r"[ \t]*<!-- CP 靜態頁：[^\n]*\n", "", xml)
    xml = re.sub(r"[ \t]*<url>\s*<loc>" + re.escape(ORIGIN) + r"/cp/[^<]*</loc>.*?</url>[ \t]*\r?\n", "", xml, flags=re.S)
    today = __import__("datetime").date.today().isoformat()
    state_path = os.path.join(ROOT, "data", "cp_static_lastmod.json")
    try:
        with open(state_path, encoding="utf-8") as f:
            old = json.load(f)
    except (OSError, ValueError):
        old = {}
    state = {}
    for t in targets:
        prev = old.get(t["slug"]) or {}
        state[t["slug"]] = {"fp": fps[t["slug"]],
                            "lastmod": prev["lastmod"] if prev.get("fp") == fps[t["slug"]] and prev.get("lastmod") else today}
    with open(state_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(state, f, ensure_ascii=False, indent=1, sort_keys=True); f.write("\n")
    lines = ["  <!-- CP 靜態頁：由 scripts/build_cp_static.py 自動產生，勿手改此區塊 -->"]
    for t in targets:
        lines += ["  <url>", f"    <loc>{ORIGIN}/cp/{t['slug']}/</loc>", f"    <lastmod>{state[t['slug']]['lastmod']}</lastmod>",
                  "    <priority>0.6</priority>", "  </url>"]
    xml = xml.replace("</urlset>", nl.join(lines) + nl + "</urlset>")
    open(path, "w", encoding="utf-8", newline="").write(xml)


def main():
    global POOL
    targets = [t for t in TARGET_LIST if t["name"] in CP_DATA]
    for t in TARGET_LIST:
        if t["name"] not in CP_DATA:
            print("SKIP（找不到 CP 資料）:", t["name"])
    POOL = []
    for rank, t in enumerate(targets):
        p = CP_DATA[t["name"]]; e = get_enrich(t["name"], p)
        POOL.append({"name": t["name"], "slug": t["slug"], "img": p["imageUrl"], "rank": rank,
                     "types": [z for z, _ in e["types"]]})
    write_assets()
    fps = {}
    for t in targets:
        out_dir = os.path.join(ROOT, "cp", t["slug"])
        os.makedirs(out_dir, exist_ok=True)
        page = build(t["name"])
        fps[t["slug"]] = __import__("hashlib").sha1(page.encode("utf-8")).hexdigest()[:16]
        with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8", newline="\n") as f:
            f.write(page)
    write_slug_module(targets)
    write_sitemap_block(targets, fps)
    print(f"已產生 {len(targets)} 個 /cp/<slug>/ 靜態頁、js/cp-static-slugs.js，並更新 sitemap.xml 的 CP 區塊")


if __name__ == "__main__":
    main()
