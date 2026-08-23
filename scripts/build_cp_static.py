# -*- coding: utf-8 -*-
"""
產生「靜態預先產生」的單隻寶可夢 CP 頁面（內容全部寫死在原始 HTML）。

背景：GitHub Pages 是純靜態主機，?tab=cp-checker-app&mon=XXX 這類查詢字串網址
回傳的原始 HTML 都是同一個 index.html —— Google 因此把 1079 個 ?mon= 網址全部
canonical 收斂到 ?tab=cp-checker-app，判為重複而不收錄（GSC 實測：Google 所選
標準網址 = ?tab=cp-checker-app）。

解法：每隻輸出一個真正獨立的檔案（不同路徑、內容寫死在原始 HTML、自帶 self-canonical），
Google 一抓就看得到不同文件，才有機會收錄。

目前只做「烈空坐」一隻做收錄測試。確認有效後，把 ENRICH 改成用
data/pokemon_data_and_rankings.js 的 POKEDEX / rankings 自動生成全部。

用法：  python scripts/build_cp_static.py
輸出：  cp/<slug>/index.html
"""
import os, re, math, html, json

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
    d = PDX_BY_NAME.get(key)
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
        "moves": moves or [("—", "資料不足")], "leagues": leagues, "league_note": league_note,
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

# 要產生靜態頁的清單（挑 ?mon= 收不了的重要寶可夢；auto 生成，加名字即可）
TARGETS = [
    "烈空坐",
    "雷公", "雷吉艾斯", "雷吉斯奇魯", "由克希", "露奈雅拉", "轟擂金剛猩", "騎拉帝納 (起源形態)",
    "火焰雞", "烈咬陸鯊", "波士可多拉",
    "閃電鳥", "火焰鳥", "急凍鳥", "炎帝", "水君",
]

CSS = """
:root{--bg:#f0f2f5;--card:#fff;--ink:#1c1e21;--ink2:#3a3b3c;--muted:#606770;--line:#dddfe2;
 --blue:#1877f2;--blue2:#4aa3e8;--red:#e63946;--green:#2f9e57;--dragon:#6a5ae0;--flying:#4aa3e8}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font-family:system-ui,-apple-system,"Segoe UI","PingFang TC","Microsoft JhengHei",sans-serif;
 line-height:1.75;-webkit-font-smoothing:antialiased}
.wrap{max-width:640px;margin:0 auto;padding:20px 16px 70px}
.crumb{font-size:13px;color:var(--muted);margin:4px 0 16px}
.crumb a{color:var(--blue);text-decoration:none}
.crumb a:hover{text-decoration:underline}
.card{background:var(--card);border-radius:10px;box-shadow:0 2px 4px rgba(0,0,0,.08);padding:22px 22px;margin-bottom:16px}
.head{display:flex;gap:16px;align-items:center}
.head img{width:84px;height:84px;border-radius:16px;background:linear-gradient(140deg,var(--dragon),var(--flying));padding:6px;flex:none}
.dexno{font-size:13px;color:var(--muted);font-weight:600;letter-spacing:.04em}
h1{font-size:26px;margin:2px 0 8px;font-weight:750;letter-spacing:-.01em}
.types{display:flex;gap:8px}
.type{font-size:12.5px;font-weight:700;color:#fff;padding:3px 12px;border-radius:999px}
.t0{background:var(--dragon)}.t1{background:var(--flying)}
.lead{font-size:15px;color:var(--ink2);margin:16px 0 0}
.lead strong{color:var(--ink)}
h2{font-size:19px;margin:0 0 10px;color:var(--ink);letter-spacing:-.01em}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:12px}
.stat{background:#f7f8fa;border-radius:11px;padding:13px 15px}
.stat .v{font-size:23px;font-weight:730;font-variant-numeric:tabular-nums}
.stat .v small{font-size:.5em;color:var(--muted);font-weight:600}
.stat .l{font-size:12px;color:var(--ink2);margin-top:1px}
.tbl-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
table.cp{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}
table.cp caption{caption-side:top;text-align:left;color:var(--muted);font-size:13px;padding-bottom:8px}
table.cp th,table.cp td{border:1px solid #e4e6eb;padding:7px 10px;text-align:right;white-space:nowrap}
table.cp thead th{background:#f7f8fa;color:var(--ink);font-weight:700}
table.cp tbody th{text-align:left;background:#fafbfc}
table.cp td.mx{font-weight:700;color:var(--green)}
table.cp td.mn{color:var(--muted)}
table.cp td.nt,table.cp thead th:last-child{text-align:left;white-space:normal;color:var(--muted);font-size:13px;width:42%}
table.cp thead th:last-child{color:var(--ink)}
table.cp tr:nth-child(even) td,table.cp tr:nth-child(even) th{background:#fcfcfd}
table.cp tr.key th,table.cp tr.key td{background:#eef7f1}
table.cp tr.bb th,table.cp tr.bb td{background:#fff7e8}
.foot-t{color:var(--muted);font-size:13px;margin:12px 0 0}
.matchup{display:flex;flex-direction:column;gap:10px;margin:4px 0 12px}
.mg{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.mlab{flex:none;width:44px;font-size:13px;font-weight:700;color:var(--muted)}
.chip{font-size:13px;font-weight:600;padding:5px 11px;border-radius:9px;display:inline-flex;gap:6px;align-items:center}
.chip em{font-style:normal;font-size:11.5px;opacity:.85;font-variant-numeric:tabular-nums}
.chip.wk{background:#fdecec;color:#c5221f}.chip.wk.dbl{background:#f9d5d3;color:#a50e0e;font-weight:800}
.chip.rs{background:#e7f5ec;color:#1e7e46}
.note{color:var(--muted);font-size:13px;margin:6px 0 0}
.note strong,.lead strong,.role strong{color:var(--ink)}
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
.lbar i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,var(--blue),var(--blue2))}
.lrk{font-size:12.5px;color:var(--muted);font-variant-numeric:tabular-nums;white-space:nowrap}
.lrk b{color:var(--ink);font-size:13.5px}
.related p{margin:0 0 8px;font-size:14px}
.related a{color:var(--blue);text-decoration:none;padding:2px 4px;border-radius:4px}
.related a:hover{background:#eaf2fd;text-decoration:underline}
.related strong{color:var(--muted);font-weight:600}
.cta{display:inline-block;background:var(--blue);color:#fff;text-decoration:none;font-weight:700;
 padding:11px 20px;border-radius:8px;font-size:15px}
.cta:hover{background:#166fe0}
.pagefoot{text-align:center;color:var(--muted);font-size:12.5px;margin-top:22px}
.pagefoot a{color:var(--muted)}
@media (max-width:480px){.lrow{grid-template-columns:64px 1fr}.lrk{grid-column:2;text-align:right}}
/* 高 IV CP·HP 對照表 */
table.iv{border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums;white-space:nowrap;min-width:560px}
table.iv th,table.iv td{border:1px solid #e4e6eb;padding:4px 7px;text-align:right}
table.iv thead th{background:#f7f8fa;color:var(--ink);font-weight:700;text-align:center}
table.iv td.pct{text-align:left;color:var(--muted)}
table.iv tr.hundo td.pct{color:var(--red);font-weight:800}
table.iv td.hp{color:var(--muted)}
table.iv td.iv{color:#fff;font-weight:700;text-align:center}
table.iv td.v15{background:#e63946}
table.iv td.v14{background:#2b6cb0}
table.iv td.v13{background:#2f9e57}
table.iv td.v12{background:#d98324}
table.iv td.v11{background:#8a8f98}
table.iv tbody tr:nth-child(even) td:not(.iv){background:#fcfcfd}
.iv-legend{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 0;font-size:12px;color:var(--muted)}
.iv-legend span{display:inline-flex;align-items:center;gap:5px}
.iv-legend i{width:12px;height:12px;border-radius:3px;display:inline-block}
/* 浮動搜尋鈕 */
.fab{position:fixed;right:16px;bottom:16px;z-index:60;display:inline-flex;align-items:center;gap:8px;
 background:var(--blue);color:#fff;text-decoration:none;font-weight:700;font-size:14px;
 padding:12px 18px;border-radius:999px;box-shadow:0 6px 18px rgba(24,119,242,.45)}
.fab:hover{background:#166fe0}
.fab:active{transform:translateY(1px)}
@media (max-width:480px){.fab{padding:12px 16px}}
"""

def esc(s): return html.escape(str(s), quote=True)

def build(name):
    p = CP_DATA[name]; e = get_enrich(name, p)
    pid = p["id"]; slug = e["slug"]
    url = f"{ORIGIN}/cp/{slug}/"
    cp40, cp50 = cp_at(p, 40, 15), cp_at(p, 50, 15)
    title = f"{name} IV100 CP 速查｜Lv1-50 全等級 CP 表｜Pokémon Go 工具箱"
    desc = (f"{name}（#{pid}，{e['type_line']}）的 IV 100% CP 速查與 Lv1～50 全等級 CP 對照表："
            f"滿 IV 最大 CP L40 {cp40}／L50 {cp50}，含屬性剋制、推薦招式、團體戰與 PvP 聯盟定位。")

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
    league_html = "".join(
        f'<div class="lrow"><span class="lname">{esc(n)}</span>'
        f'<span class="lbar"><i style="width:{w}%"></i></span>'
        f'<span class="lrk"><b>{esc(rk)}</b> / {tot} · {sc} 分</span></div>'
        for n, w, rk, tot, sc in e["leagues"])

    prev_n, next_n = dex_neighbor(pid, -1), dex_neighbor(pid, +1)
    rel = []
    if prev_n: rel.append(f'上一隻 <a href="../../?tab=cp-checker-app&mon={esc(prev_n)}">{esc(prev_n)}</a>')
    if next_n: rel.append(f'下一隻 <a href="../../?tab=cp-checker-app&mon={esc(next_n)}">{esc(next_n)}</a>')
    related_html = ('<p><strong>圖鑑相鄰：</strong>' + '　·　'.join(rel) + '</p>') if rel else ''

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
<meta name="robots" content="index,follow">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Pokémon Go 工具箱">
<meta property="og:title" content="{esc(name)} IV100 CP 查詢｜Lv1-50 全等級 CP 表">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{esc(p['imageUrl'])}">
<meta property="og:locale" content="zh_TW">
<script type="application/ld+json">{ld}</script>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <nav class="crumb" aria-label="麵包屑">
    <a href="../../">工具箱首頁</a> ›
    <a href="../../?tab=cp-checker-app">IV100 CP 查詢</a> ›
    <span>{esc(name)}</span>
  </nav>

  <div class="card">
    <div class="head">
      <img src="{esc(p['imageUrl'])}" alt="{esc(name)}" width="84" height="84" loading="lazy" style="background:{e['grad']}">
      <div>
        <div class="dexno">#{pid}</div>
        <h1>{esc(name)} IV100 CP 查詢</h1>
        <div class="types">{types_html}</div>
      </div>
    </div>
    <p class="lead">{e['lead']} 以下提供牠的 Lv1～50 全等級 CP 對照表、屬性剋制、角色定位、推薦招式與對戰聯盟表現。</p>
  </div>

  <div class="card">
    <h2>{esc(name)} 關鍵數據</h2>
    <div class="stats">
      <div class="stat"><div class="v">{cp40}</div><div class="l">滿 IV 最大 CP（L40）</div></div>
      <div class="stat"><div class="v">{cp50}</div><div class="l">滿 IV 最大 CP（L50）</div></div>
      <div class="stat"><div class="v">{p['atk']}</div><div class="l">基礎攻擊</div></div>
      <div class="stat"><div class="v">{p['def']}<small> / {p['sta']}</small></div><div class="l">防禦 / 耐力</div></div>
    </div>
  </div>

  <div class="card">
    <h2>{esc(name)} 高 IV CP·HP 對照表（IV 100%～91.1%）</h2>
    <p class="foot-t" style="margin:0 0 12px">IV 總和最高的 35 種組合（IV% ≥ 91.1%），以及各自在 L15／L20／L25／L40 的 CP 與 HP。
       攻／防／耐為個體值（0～15）。</p>
    <div class="tbl-wrap">{iv_table}</div>
    <div class="iv-legend">
      <span><i style="background:#e63946"></i>15</span>
      <span><i style="background:#2b6cb0"></i>14</span>
      <span><i style="background:#2f9e57"></i>13</span>
      <span><i style="background:#d98324"></i>12</span>
      <span><i style="background:#8a8f98"></i>11</span>
    </div>
  </div>

  <div class="card">
    <h2>{esc(name)} 全等級 CP 對照表（Lv1～Lv{MAX_LEVEL}）</h2>
    <p class="foot-t" style="margin:0 0 12px">{esc(name)}（#{pid}）基礎數值 攻擊 {p['atk']}／防禦 {p['def']}／耐力 {p['sta']}。
       <strong>100% IV</strong>（15/15/15）為該等級 CP 上限，<strong>0% IV</strong>（0/0/0）為下限。</p>
    <div class="tbl-wrap">
      <table class="cp">
        <caption>{esc(name)} 各等級 CP（100% IV / 0% IV）</caption>
        <thead><tr><th>等級</th><th>100% IV</th><th>0% IV</th><th>說明</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <p class="foot-t">Lv{BB} 為最佳夥伴狀態下的等級上限；一般強化上限為 Lv{MAX_LEVEL}。資料來源為 Pokémon GO GAME_MASTER。</p>
  </div>

  <div class="card">
    <h2>{esc(name)} 屬性與剋制</h2>
    <div class="matchup">
      <div class="mg"><span class="mlab">弱點</span>{weak_html}</div>
      <div class="mg"><span class="mlab">抗性</span>{resist_html}</div>
    </div>
    <p class="note">{e['type_note']}</p>
  </div>

  <div class="card">
    <h2>{esc(name)} 角色定位與推薦招式</h2>
    <p class="role">{e['role']}</p>
    <ul class="moves">{moves_html}</ul>
  </div>

  <div class="card">
    <h2>{esc(name)} 對戰聯盟表現</h2>
    <div class="league">{league_html}</div>
    <p class="note">{e['league_note']}</p>
  </div>

  <div class="card related">
    <h2>相關寶可夢</h2>
    {related_html}
    <p><strong>互動查詢：</strong>在工具裡即時查 <a href="../../?tab=cp-checker-app&mon={esc(name)}">{esc(name)}</a> 的完整資料。</p>
  </div>

  <div style="text-align:center;margin-top:8px">
    <a class="cta" href="../../?tab=cp-checker-app&mon={esc(name)}">開啟互動 CP 查詢工具 →</a>
  </div>

  <p class="pagefoot"><a href="../../">Pokémon Go 工具箱</a> · IV100 CP、PvP 排名、搜尋指令、團體戰與孵蛋查詢</p>
  <p class="pagefoot"><a href="../../privacy/">隱私權政策</a> · <a href="../../disclaimer/">免責聲明</a></p>
</div>

<a class="fab" href="../../?tab=cp-checker-app" aria-label="搜尋其他寶可夢">🔍 <span>搜尋寶可夢</span></a>
</body>
</html>"""

def main():
    for name in TARGETS:
        p = CP_DATA.get(name)
        if not p:
            print("SKIP（找不到 CP 資料）:", name); continue
        e = get_enrich(name, p)
        out_dir = os.path.join(ROOT, "cp", e["slug"])
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, "index.html")
        open(out, "w", encoding="utf-8").write(build(name))
        print("wrote", os.path.relpath(out, ROOT), "  (" + e["type_line"] + ")")

if __name__ == "__main__":
    main()
