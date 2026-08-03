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
import os, re, math, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGIN = "https://jason168861.github.io/pokemongo-toolbox"

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

# ---- 每隻的「差異化」內容（目前只有烈空坐）----
# types/weak/resist/role/moves/leagues 都是 Pokémon GO 現況；未來改成自動生成。
ENRICH = {
    "烈空坐": {
        "slug": "rayquaza",
        "types": ["龍", "飛行"],
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
                    ("超級聯盟", 43, "#361", 841, "77.8"),
                    ("特級聯盟", 39, "#445", 1143, "77.2")],
        "league_note": ("烈空坐在對戰中更適合<strong>大師聯盟</strong> —— 這裡沒有 CP 上限，牠不必刻意壓等。"
                        "在超級與特級聯盟因體質偏脆、CP 又常超標，表現只算普通，一般不是首選。"),
    }
}

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
    p = CP_DATA[name]; e = ENRICH[name]
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

    types_html = "".join(f'<span class="type t{i}">{esc(t)}</span>' for i, t in enumerate(e["types"]))
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
      <img src="{esc(p['imageUrl'])}" alt="{esc(name)}" width="84" height="84" loading="lazy">
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
</div>

<a class="fab" href="../../?tab=cp-checker-app" aria-label="搜尋其他寶可夢">🔍 <span>搜尋寶可夢</span></a>
</body>
</html>"""

def main():
    for name in ENRICH:
        out_dir = os.path.join(ROOT, "cp", ENRICH[name]["slug"])
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, "index.html")
        open(out, "w", encoding="utf-8").write(build(name))
        print("wrote", os.path.relpath(out, ROOT))

if __name__ == "__main__":
    main()
