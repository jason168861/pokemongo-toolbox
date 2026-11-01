# -*- coding: utf-8 -*-
"""
產生 /cp/<slug>/ 靜態頁的其他 6 種語言版本：/<lang>/cp/<slug>/（en ja ko fr de es），
以及各語言的 IV100 CP 列表頁 /<lang>/cp/。

- 寶可夢名稱、型態、屬性、天氣、聯盟、招式名稱都用遊戲官方文字（../pogo_assets/Texts），
  用到的部分抽出來存在 data/cp_i18n_terms.json；沒有 pogo_assets 時直接讀這個檔。
- 頁面句型在 scripts/cp_i18n_strings.py。
- 數字與表格沿用 build_cp_static.py 的資料與公式（同一份 CP 資料、同一套 CSS／反查 JS）。

用法（順序固定）：
    python scripts/build_cp_static.py        # 中文頁、共用 CSS/JS、sitemap 的 /cp/ 區塊
    python scripts/build_cp_static_i18n.py   # 本腳本：6 種語言 × 名單內每一隻 + 各語言列表頁

名單沿用 data/cp_static_targets.json。新增語言時，build_cp_static.I18N_LANGS 與
本檔的 TXT_FILE、cp_i18n_strings.STR 要一起加。
"""
import os, sys, json, re, hashlib, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_cp_static as B
from cp_i18n_strings import STR

ROOT, ORIGIN, esc = B.ROOT, B.ORIGIN, B.esc
LANGS = B.I18N_LANGS
TXT_FILE = {"en": "english", "ja": "japanese", "ko": "korean", "fr": "french", "de": "german",
            "es": "spanish", "zh": "chinesetraditional"}
POGO = os.environ.get("POGO_ASSETS", os.path.join(os.path.dirname(ROOT), "pogo_assets"))
TERMS_PATH = os.path.join(ROOT, "data", "cp_i18n_terms.json")

# 官方文字的對照補充
FORM_KEY = {"zacian": "form_zacian_hero", "zamazenta": "form_zamazenta_hero", "giratina": "form_giratina_altered",
            "landorus": "form_landorus_incarnate", "thundurus": "form_thundurus_incarnate",
            "zygarde": "form_zygarde_fifty_percent", "meloetta": "form_meloetta_aria"}
REGIONAL = [("_galarian", "galar"), ("_alola", "alola"), ("_hisuian", "hisui")]   # 用「…_pokedex_header」的地區名稱
NO_FORM = {"slowbro"}   # 「2021形態」只是資料上的區分，遊戲裡就是一般的呆殼獸
MANUAL_NAME = {"mewtwo_a": {"en": "Armored Mewtwo", "ja": "アーマードミュウツー", "ko": "아머드 뮤츠",
                            "fr": "Mewtwo Armuré", "de": "Rüstungs-Mewtu", "es": "Mewtwo Acorazado"}}
# 排名資料（台灣社群譯名）和官方中文不同的招式：對到官方英文名稱再查各語言
MOVE_FIX = {"加農水砲": "Hydro Cannon", "巨力錘": "Gigaton Hammer", "氣象球 冰": ("Weather Ball", "ice"),
            "氣象球 火": ("Weather Ball", "fire"), "泡影詠歎調": "Sparkling Aria", "潑冷水": "Chilling Water",
            "潛水": "Dive", "火焰球": "Pyro Ball", "狙擊": "Snipe Shot", "等離子閃電拳": "Plasma Fists",
            "逆鱗": "Outrage", "鼓擊": "Drum Beating"}
# 目前的 pogo_assets 文字檔還沒有的新招式：採用本傳遊戲的官方譯名（Pokémon GO 沿用同一套招式名稱）。
# pogo_assets 更新後若官方文字已有，會優先用官方文字。
MANUAL_MOVES = {
    "巨力錘": {"en": "Gigaton Hammer", "ja": "デカハンマー", "ko": "거대해머", "fr": "Marteau Mastoc", "de": "Riesenhammer", "es": "Martillo Colosal"},
    "潛水": {"en": "Dive", "ja": "ダイビング", "ko": "다이빙", "fr": "Plongée", "de": "Taucher", "es": "Buceo"},
    "火焰球": {"en": "Pyro Ball", "ja": "かえんボール", "ko": "화염볼", "fr": "Ballon Brûlant", "de": "Feuerball", "es": "Balón Ígneo"},
    "狙擊": {"en": "Snipe Shot", "ja": "ねらいうち", "ko": "노려맞히기", "fr": "Tir de Précision", "de": "Präzisionsschuss", "es": "Disparo Certero"},
    "等離子閃電拳": {"en": "Plasma Fists", "ja": "プラズマフィスト", "ko": "플라스마피스트", "fr": "Plasma Punch", "de": "Plasmafäuste", "es": "Puños Plasma"},
    "鼓擊": {"en": "Drum Beating", "ja": "ドラムアタック", "ko": "드럼어택", "fr": "Tambour Battant", "de": "Trommelschläge", "es": "Batería Asalto"},
}
WEATHER_KEY = {"clear": "weather_sunny", "rain": "weather_rainy", "partlycloudy": "weather_partly_cloudy",
               "cloudy": "weather_overcast", "windy": "weather_windy", "snow": "weather_snow", "fog": "weather_fog"}


# ---------------- 官方文字 ----------------
REMOTE_FILE = {"en": "English", "ja": "Japanese", "ko": "Korean", "fr": "French", "de": "German",
               "es": "Spanish", "zh": "ChineseTraditional"}


def _load_txt(lang):
    """APK 內建文字 + 遠端更新文字（新招式常只在遠端那份）。"""
    with open(os.path.join(POGO, "Texts", "Latest APK", "JSON", f"i18n_{TXT_FILE[lang]}.json"), encoding="utf-8") as f:
        d = json.load(f)["data"]
    out = {k: (v or "").strip() for k, v in zip(d[0::2], d[1::2])}
    rp = os.path.join(POGO, "Texts", "Latest Remote", REMOTE_FILE[lang] + ".txt")
    if os.path.exists(rp):
        txt = open(rp, encoding="utf-8").read()
        for k, v in re.findall(r"RESOURCE ID: ([^\r\n]+)\r?\nTEXT: ([^\r\n]*)", txt):
            out[k.strip()] = v.strip()
    return out


def _used_moves(targets):
    used = set()
    for t in targets:
        for lg in B.RANKS.get(B._norm(t["name"]), {}).values():
            for f in ("fast", "c1", "c2"):
                if (lg.get(f) or "").strip():
                    used.add(lg[f].strip())
    return used


def extract_terms(targets):
    tx = {l: _load_txt(l) for l in LANGS + ["zh"]}
    en = tx["en"]
    zh_move, en_move = {}, {}
    for k, v in tx["zh"].items():
        if k.startswith("move_name_"):
            zh_move.setdefault(v, k)
    for k, v in en.items():
        if k.startswith("move_name_"):
            en_move.setdefault(v, k)
    region_key = {}
    for suf, word in REGIONAL:
        ks = [k for k in en if k.endswith("_pokedex_header") and word in k]
        if ks:
            region_key[suf] = ks[0]
    terms = {l: {"names": {}, "types": {}, "weather": {}, "league": {}, "moves": {}} for l in LANGS}
    missing = []
    for t in targets:
        p = B.CP_DATA[t["name"]]; slug = t["slug"]
        form_key = None
        if "(" in t["name"] and slug not in NO_FORM and slug not in MANUAL_NAME:
            form_key = FORM_KEY.get(slug) or ("form_" + slug if "form_" + slug in en else None)
            if not form_key:
                form_key = next((k for suf, k in region_key.items() if slug.endswith(suf)), None)
            if not form_key:
                missing.append("form:" + slug)
        for l in LANGS:
            if slug in MANUAL_NAME:
                terms[l]["names"][slug] = MANUAL_NAME[slug][l]
                continue
            base = tx[l].get(f"pokemon_name_{p['id']:04d}")
            if not base:
                missing.append(f"name:{slug}:{l}")
                base = en.get(f"pokemon_name_{p['id']:04d}", slug)
            form = tx[l].get(form_key) if form_key else None
            terms[l]["names"][slug] = STR[l]["paren"].format(a=base, b=form) if form else base
    for l in LANGS:
        for ty in B.TYPE_DEF:
            terms[l]["types"][ty] = tx[l]["pokemon_type_" + ty]
        for w, k in WEATHER_KEY.items():
            terms[l]["weather"][w] = tx[l][k]
        for lg in ("great", "ultra", "master"):
            terms[l]["league"][lg] = tx[l][f"combat_{lg}_league"]
    for mv in sorted(_used_moves(targets)):
        fix = MOVE_FIX.get(mv)
        typ = None
        if isinstance(fix, tuple):
            key, typ = en_move.get(fix[0]), fix[1]
        else:
            key = zh_move.get(mv) or (en_move.get(fix) if fix else None)
        if not key:
            if mv in MANUAL_MOVES:
                for l in LANGS:
                    terms[l]["moves"][mv] = MANUAL_MOVES[mv][l]
            else:
                missing.append("move:" + mv)
            continue
        for l in LANGS:
            nm = tx[l].get(key) or en[key]
            terms[l]["moves"][mv] = STR[l]["paren"].format(a=nm, b=tx[l]["pokemon_type_" + typ]) if typ else nm
    if missing:
        # 缺字就停下來，不要用英文或代號默默頂替
        raise SystemExit("找不到官方文字（補 FORM_KEY／MANUAL_NAME／MOVE_FIX／MANUAL_MOVES 後再跑）：" + ", ".join(missing))
    return terms


def load_terms(targets):
    if os.path.isdir(os.path.join(POGO, "Texts")):
        terms = extract_terms(targets)
        with open(TERMS_PATH, "w", encoding="utf-8", newline="\n") as f:
            json.dump(terms, f, ensure_ascii=False, indent=1, sort_keys=True); f.write("\n")
        return terms
    print("（找不到 pogo_assets，改用已存的 data/cp_i18n_terms.json）")
    with open(TERMS_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------- 內容 ----------------
def matchups_ids(types):
    weak, resist = [], []
    for atk in B.TYPE_DEF:
        m = 1.0
        for dt in types:
            m *= B._single_mult(atk, dt)
        if m > 1.0001:
            weak.append((atk, B._fmt_mult(m), m, m >= 2.5))
        elif m < 0.9999:
            resist.append((atk, B._fmt_mult(m), m))
    weak.sort(key=lambda x: -x[2]); resist.sort(key=lambda x: x[2])
    return weak, resist


def iv_table(p, S):
    combos = []
    for a in range(15, -1, -1):
        for d in range(15, -1, -1):
            for s in range(15, -1, -1):
                if a + d + s >= B.IV_MIN_SUM:
                    combos.append((a + d + s, a, d, s, B.cp_iv(p, 40, a, d, s)))
    combos.sort(key=lambda c: (-c[0], -c[4]))
    body = ""
    for tot, a, d, s, _ in combos:
        cells = "".join(f'<td>{B.cp_iv(p, L, a, d, s)}</td><td class="hp">{B.hp_iv(p, L, s)}</td>' for L in B.IV_TABLE_LEVELS)
        hundo = ' class="hundo"' if tot == 45 else ''
        body += (f'<tr{hundo}><td class="pct">{tot / 45 * 100:.2f}%</td><td class="iv v{a}">{a}</td>'
                 f'<td class="iv v{d}">{d}</td><td class="iv v{s}">{s}</td>{cells}</tr>')
    heads1 = "".join(f'<th colspan="2">{S["lv"]}{L}</th>' for L in B.IV_TABLE_LEVELS)
    heads2 = "".join(f'<th>{S["f_cp"]}</th><th>{S["f_hp"]}</th>' for _ in B.IV_TABLE_LEVELS)
    return (f'<table class="iv"><thead><tr><th rowspan="2">IV%</th><th colspan="3">{S["ivt_iv"]}</th>{heads1}</tr>'
            f'<tr><th>{S["a"]}</th><th>{S["d"]}</th><th>{S["s"]}</th>{heads2}</tr></thead><tbody>{body}</tbody></table>')


def enrich(t, lang, T):
    S = STR[lang]; p = B.CP_DATA[t["name"]]; slug = t["slug"]; name = T["names"][slug]
    d = B.pdx_of(t["name"], p["id"])
    types = d["types"] if d else []
    tn = [T["types"][x] for x in types]
    types_txt = S["type_sep"].join(tn) if tn else "?"
    cp40, cp50 = B.cp_at(p, 40, 15), B.cp_at(p, 50, 15)
    lead = S["lead"].format(name=esc(name), dex=p["id"], types=esc(types_txt), a=p["atk"], d=p["def"], s=p["sta"],
                            cp40=cp40, cp50=cp50)
    weak, resist = matchups_ids(types) if types else ([], [])
    if weak:
        dbls = [T["types"][x] for x, _, _, dd in weak if dd]
        note = S["mu_note"].format(
            name=esc(name), wlist=esc(S["sep"].join(T["types"][x] for x, _, _, _ in weak[:4])),
            dbl=S["mu_dbl"].format(dbls=esc(S["sep"].join(dbls))) if dbls else "",
            rlist=esc(S["sep"].join(T["types"][x] for x, _, _ in resist[:4])) if resist else "—",
            prim=esc(T["types"][weak[0][0]]))
    else:
        note = S["mu_none"]
    ws = []
    for x in types:
        w = B.TYPE_WEATHER.get(x)
        if w and T["weather"][w] not in ws:
            ws.append(T["weather"][w])
    if ws and weak:
        note += S["mu_w"].format(w=esc(S["sep"].join(ws)))
    atk, dfe, sta = p["atk"], p["def"], p["sta"]
    if atk >= dfe and atk >= sta:
        rk = "role_atk_hi" if atk >= 240 else "role_atk"
    elif dfe >= atk and dfe >= sta:
        rk = "role_def"
    else:
        rk = "role_sta"
    role = S[rk].format(name=esc(name), a=atk, d=dfe, s=sta)
    r = B.RANKS.get(B._norm(t["name"]), {})
    moves, leagues = [], []
    league_note = S["lg_none"].format(name=esc(name))
    avail = [lg for lg in ("master", "ultra", "great") if lg in r]
    if avail:
        best = max(avail, key=lambda lg: r[lg]["score"]); b = r[best]
        mv = lambda m: esc(T["moves"].get((m or "").strip(), (m or "").strip()))
        moves.append((S["rec"], f'{mv(b["fast"])} ＋ {mv(b["c1"])}／{mv(b["c2"])} <em>{esc(S["basis"].format(league=T["league"][best]))}</em>'
                      if lang in ("ja",) else
                      f'{mv(b["fast"])} + {mv(b["c1"])} / {mv(b["c2"])} <em>{esc(S["basis"].format(league=T["league"][best]))}</em>'))
        if b.get("buddy"):
            moves.append((S["buddy"], esc(S["km"].format(km=b["buddy"]))))
        for lg in ("master", "ultra", "great"):
            if lg in r:
                v = r[lg]
                leagues.append((T["league"][lg], round(v["score"], 1), v["rank"], v["total"], v["score"]))
        extra = S["lg_extra"].format(master=T["league"]["master"]) if best == "master" else ""
        league_note = S["lg_note"].format(name=esc(name), league=esc(T["league"][best]), rank=b["rank"],
                                          total=b["total"], score=b["score"], extra=esc(extra))
    return dict(types=[(T["types"][x], B.TYPE_COLOR[x]) for x in types], type_ids=types, types_txt=types_txt,
                lead=lead, weak=weak, resist=resist, note=note, role=role,
                moves=moves, leagues=leagues, league_note=league_note)


def lang_nav(slug, lang, to_root):
    """頁尾的語言切換列（中文版在 /cp/<slug>/）。"""
    items = [("zh", "繁體中文", f"{to_root}cp/{slug}/" if slug else f"{to_root}?tab=cp-checker-app")]
    names = {"en": "English", "ja": "日本語", "ko": "한국어", "fr": "Français", "de": "Deutsch", "es": "Español"}
    items += [(l, names[l], f"{to_root}{l}/cp/{slug + '/' if slug else ''}") for l in LANGS]
    return " · ".join(f'<b>{n}</b>' if l == lang else f'<a href="{u}" hreflang="{STR[l]["html_lang"] if l != "zh" else "zh-Hant"}">{n}</a>'
                      for l, n, u in items)


def build_page(t, lang, T, pool):
    S = STR[lang]; p = B.CP_DATA[t["name"]]; slug = t["slug"]; name = T["names"][slug]; e = enrich(t, lang, T)
    R = "../../../"   # /<lang>/cp/<slug>/ → 網站根目錄
    url = f"{ORIGIN}/{lang}/cp/{slug}/"
    cp15, cp20, cp25 = B.cp_at(p, 15, 15), B.cp_at(p, 20, 15), B.cp_at(p, 25, 15)
    cp40, cp50, cp51 = B.cp_at(p, 40, 15), B.cp_at(p, 50, 15), B.cp_at(p, B.BB, 15)
    fmt = dict(name=name, dex=p["id"], types=e["types_txt"], cp15=cp15, cp20=cp20, cp25=cp25)
    title, desc, og_title = S["title"].format(**fmt), S["desc"].format(**fmt), S["og_title"].format(**fmt)
    c1 = e["types"][0][1] if e["types"] else "#6a5ae0"
    c2 = e["types"][-1][1] if e["types"] else "#4aa3e8"
    keys = {15: S["key15"], 20: S["key20"], 25: S["key25"]}
    rows = ""
    for L in range(1, B.BB + 1):
        note = S["bb"] if L == B.BB else keys.get(L, "")
        cls = ("key " if L in keys else "") + ("bb" if L == B.BB else "")
        rows += (f'<tr class="{cls.strip()}"><th scope="row">{S["lv"]}{L}</th><td class="mx">{B.cp_at(p, L, 15)}</td>'
                 f'<td class="mn">{B.cp_at(p, L, 0)}</td><td class="nt">{esc(note)}</td></tr>')
    types_html = "".join(f'<span class="type" style="background:{c}">{esc(z)}</span>' for z, c in e["types"])
    weak_html = "".join(f'<span class="chip wk{" dbl" if dd else ""}">{esc(T["types"][x])} <em>{esc(m)}</em></span>'
                        for x, m, _, dd in e["weak"]) or "—"
    resist_html = "".join(f'<span class="chip rs">{esc(T["types"][x])} <em>{esc(m)}</em></span>'
                          for x, m, _ in e["resist"]) or "—"
    moves_html = "".join(f'<li><span class="k">{esc(k)}</span><span class="v">{v}</span></li>' for k, v in e["moves"])
    moves_ul = f'<ul class="moves">{moves_html}</ul>' if moves_html else ""   # 沒有 PvP 資料就不顯示招式列
    league_html = "".join(
        f'<div class="lrow"><span class="lname">{esc(n)}</span><span class="lbar"><i style="width:{w}%"></i></span>'
        f'<span class="lrk">{S["lg_row"].format(rank="#" + str(rk), total=tot, score=sc)}</span></div>'
        for n, w, rk, tot, sc in e["leagues"])
    league_card = (f'<section class="card"><h2>{esc(S["lg_h"].format(name=name))}</h2><div class="league">{league_html}</div>'
                   f'<p class="note">{e["league_note"]}</p></section>') if league_html else ""
    # 圖鑑相鄰（只在有靜態頁的寶可夢之間移動）與同屬性熱門
    by_dex = sorted(pool, key=lambda x: (x["dex"], x["rank"]))
    i = next(k for k, x in enumerate(by_dex) if x["slug"] == slug)
    prv = by_dex[i - 1] if i > 0 else None
    nxt = by_dex[i + 1] if i + 1 < len(by_dex) else None
    nav2 = ""
    if prv or nxt:
        a = f'<a class="pv" href="../{prv["slug"]}/"><small>{esc(S["prev"])}</small>{esc(T["names"][prv["slug"]])}</a>' if prv else '<span></span>'
        b = f'<a class="nx" href="../{nxt["slug"]}/"><small>{esc(S["next"])}</small>{esc(T["names"][nxt["slug"]])}</a>' if nxt else '<span></span>'
        nav2 = f'<div class="nav2">{a}{b}</div>'
    mine = set(e["type_ids"])
    same = [x for x in pool if x["slug"] != slug and mine & set(x["type_ids"])]
    same.sort(key=lambda x: (x["type_ids"][0] not in mine, x["rank"]))
    grid = "".join(f'<a href="../{x["slug"]}/"><img src="{esc(x["img"])}" alt="" width="56" height="56" loading="lazy">'
                   f'{esc(T["names"][x["slug"]])}</a>' for x in same[:8])
    grid_html = f'<p class="sub" style="margin:0 0 10px">{esc(S["same"])}</p><div class="grid">{grid}</div>' if grid else ""
    rv_data = B.rv_data_json(p, slug, lang, S["rv"])
    ld = json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": S["site"], "item": ORIGIN + "/"},
        {"@type": "ListItem", "position": 2, "name": S["hub_name"], "item": f"{ORIGIN}/{lang}/cp/"},
        {"@type": "ListItem", "position": 3, "name": name, "item": url}]}, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="{S['html_lang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8866689605007086" crossorigin="anonymous"></script>
<script src="{R}js/analytics.js"></script>
<script src="{R}config.js"></script>
<script src="{R}js/pageview-counter.js" defer></script>
<link rel="icon" type="image/png" sizes="192x192" href="{R}img/masterball.png">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
{B.alternates(slug)}
<meta name="robots" content="index,follow">
<meta property="og:type" content="article">
<meta property="og:site_name" content="{esc(S['site'])}">
<meta property="og:title" content="{esc(og_title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{esc(p['imageUrl'])}">
<meta property="og:locale" content="{S['og_locale']}">
<script type="application/ld+json">{ld}</script>
<link rel="stylesheet" href="{R}css/cp-static.css">
</head>
<body style="--accent:{c1};--accent2:{c2}">
<div class="wrap">
  <nav class="crumb" aria-label="{esc(S['crumb_aria'])}">
    <a href="{R}">{esc(S['site'])}</a> ›
    <a href="../">{esc(S['hub_name'])}</a> ›
    <span>{esc(name)}</span>
  </nav>
  <aside class="site-ad" aria-label="{esc(S['ad'])}" data-ad-reserved><span class="site-ad-label">{esc(S['ad'])}</span><div class="site-ad-ph"></div></aside>

  <header class="card hero">
    <div class="band"></div>
    <div class="hero-main">
      <img class="sprite" src="{esc(p['imageUrl'])}" alt="{esc(name)}" width="120" height="120">
      <div class="hero-txt">
        <div class="dexno">#{p['id']}</div>
        <h1>{esc(S['h1'].format(name=name))}</h1>
        <div class="types">{types_html}</div>
      </div>
    </div>
    <div class="h-grid">
      <div class="h-tile"><span class="h-lab">{esc(S['t15'])}</span><b>{cp15}</b><span class="h-lv">{S['lv']}15</span></div>
      <div class="h-tile main"><span class="h-lab">{esc(S['t20'])}</span><b>{cp20}</b><span class="h-lv">{S['lv']}20</span></div>
      <div class="h-tile"><span class="h-lab">{esc(S['t25'])}</span><b>{cp25}</b><span class="h-lv">{S['lv']}25</span></div>
    </div>
    <p class="hundo-note">{S['hundo_note']}</p>
    <div class="chips">
      <span class="pill">{esc(S['pill_max'])} <b>{S['lv']}40 {cp40}</b></span><span class="pill"><b>{S['lv']}50 {cp50}</b></span><span class="pill"><b>{S['lv']}51 {cp51}</b></span>
      <span class="pill">{S['stats_pill'].format(a=p['atk'], d=p['def'], s=p['sta'])}</span>
    </div>
    <p class="lead">{e['lead']}</p>
  </header>

  <section class="card" id="rev">
    <h2>{esc(S['rev_h'].format(name=name))}</h2>
    <p class="sub">{esc(S['rev_sub'])}</p>
    <form class="rv" id="rvForm">
      <label>{esc(S['f_cp'])}<input id="rvCp" type="number" inputmode="numeric" min="10" placeholder="{esc(S['ph_cp'].format(cp20=cp20))}"></label>
      <label>{esc(S['f_hp'])}<input id="rvHp" type="number" inputmode="numeric" min="10" placeholder="{esc(S['ph_hp'])}"></label>
      <label>{esc(S['f_lv'])}<select id="rvLv"><option value="">{esc(S['lv_any'])}</option><option value="15">{esc(S['lv15'])}</option><option value="20">{esc(S['lv20'])}</option><option value="25">{esc(S['lv25'])}</option></select></label>
      <button type="submit">{esc(S['btn'])}</button>
    </form>
    <div id="rvOut" aria-live="polite"></div>
  </section>

  <section class="card">
    <h2>{esc(S['ivt_h'].format(name=name))}</h2>
    <p class="sub">{esc(S['ivt_sub'])}</p>
    <div class="tbl-wrap">{iv_table(p, S)}</div>
    <div class="iv-legend">
      <span><i style="background:#e63946"></i>15</span><span><i style="background:#2b6cb0"></i>14</span>
      <span><i style="background:#2f9e57"></i>13</span><span><i style="background:#d98324"></i>12</span>
      <span><i style="background:#8a8f98"></i>11</span>
    </div>
  </section>

  <section class="card">
    <h2>{esc(S['cpt_h'].format(name=name))}</h2>
    <p class="sub">{S['cpt_sub']}</p>
    <div class="tbl-wrap">
      <table class="cp">
        <caption>{esc(S['cpt_cap'].format(name=name))}</caption>
        <thead><tr><th>{esc(S['th_lv'])}</th><th>{esc(S['th_max'])}</th><th>{esc(S['th_min'])}</th><th>{esc(S['th_note'])}</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <p class="foot-t">{esc(S['cpt_foot'].format(bb=B.BB, max=B.MAX_LEVEL))}</p>
  </section>

  <section class="card">
    <h2>{esc(S['mu_h'].format(name=name))}</h2>
    <div class="matchup">
      <div class="mg"><span class="mlab">{esc(S['weak'])}</span>{weak_html}</div>
      <div class="mg"><span class="mlab">{esc(S['resist'])}</span>{resist_html}</div>
    </div>
    <p class="note">{e['note']}</p>
  </section>

  <section class="card">
    <h2>{esc(S['role_h'].format(name=name))}</h2>
    <p class="role">{e['role']}</p>
    {moves_ul}
  </section>

  {league_card}

  <section class="card">
    <h2>{esc(S['rel_h'])}</h2>
    {nav2}
    {grid_html}
  </section>

  <div style="text-align:center;margin-top:8px"><a class="cta" href="../">{esc(S['cta'])}</a></div>

  <p class="pagefoot"><a href="{R}">{esc(S['site'])}</a> · {esc(S['foot_tag'])}</p>
  <p class="pagefoot"><a href="{R}trade-list/?lang={lang}">{esc(S['trade'])}</a> · <a href="{R}about/">{esc(S['about'])}</a> · <a href="{R}privacy/#en">{esc(S['privacy'])}</a> · <a href="{R}disclaimer/">{esc(S['disclaimer'])}</a></p>
  <p class="pagefoot">{lang_nav(slug, lang, R)}</p>
</div>

<a class="fab" href="../" aria-label="{esc(S['fab'])}">🔍 <span>{esc(S['fab'])}</span></a>
<script type="application/json" id="rvData">{rv_data}</script>
<script src="{R}js/cp-reverse.js" defer></script>
<script src="{R}js/ads.js" defer></script>
</body>
</html>"""


def hub_alternates():
    out = [f'<link rel="alternate" hreflang="{l}" href="{ORIGIN}/{l}/cp/">' for l in LANGS]
    out.append(f'<link rel="alternate" hreflang="x-default" href="{ORIGIN}/en/cp/">')
    return "\n".join(out)


def build_hub(lang, T, pool):
    S = STR[lang]; R = "../../"; n = len(pool)
    url = f"{ORIGIN}/{lang}/cp/"
    tiles = []
    for x in sorted(pool, key=lambda x: (x["dex"], x["rank"])):
        nm = T["names"][x["slug"]]
        key = " ".join([nm.lower(), str(x["dex"]), x["en"].lower(), x["slug"].replace("_", " ")])
        tiles.append(f'<a href="{x["slug"]}/" data-k="{esc(key)}"><img src="{esc(x["img"])}" alt="" width="48" height="48" loading="lazy">'
                     f'<span>{esc(nm)}<small>{esc(S["tile"].format(cp=x["cp20"]))}</small></span></a>')
    return f"""<!doctype html>
<html lang="{S['html_lang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8866689605007086" crossorigin="anonymous"></script>
<script src="{R}js/analytics.js"></script>
<script src="{R}config.js"></script>
<script src="{R}js/pageview-counter.js" defer></script>
<link rel="icon" type="image/png" sizes="192x192" href="{R}img/masterball.png">
<title>{esc(S['hub_title'])}</title>
<meta name="description" content="{esc(S['hub_desc'].format(n=n))}">
<link rel="canonical" href="{url}">
{hub_alternates()}
<meta name="robots" content="index,follow">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{esc(S['site'])}">
<meta property="og:title" content="{esc(S['hub_h1'])}">
<meta property="og:description" content="{esc(S['hub_desc'].format(n=n))}">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="{S['og_locale']}">
<link rel="stylesheet" href="{R}css/cp-static.css">
</head>
<body>
<div class="wrap">
  <nav class="crumb" aria-label="{esc(S['crumb_aria'])}"><a href="{R}">{esc(S['site'])}</a> › <span>{esc(S['hub_name'])}</span></nav>
  <aside class="site-ad" aria-label="{esc(S['ad'])}" data-ad-reserved><span class="site-ad-label">{esc(S['ad'])}</span><div class="site-ad-ph"></div></aside>
  <section class="card">
    <h1 style="font-size:25px">{esc(S['hub_h1'])}</h1>
    {S['hub_intro']}
  </section>
  <section class="card">
    <input class="hubq" id="hubq" type="search" placeholder="{esc(S['hub_q'])}" aria-label="{esc(S['hub_q'])}">
    <p class="sub">{esc(S['hub_count'].format(n=n))}</p>
    <div class="hub" id="hub">{''.join(tiles)}</div>
  </section>
  <p class="pagefoot"><a href="{R}trade-list/?lang={lang}">{esc(S['trade'])}</a> · <a href="{R}about/">{esc(S['about'])}</a> · <a href="{R}privacy/#en">{esc(S['privacy'])}</a> · <a href="{R}disclaimer/">{esc(S['disclaimer'])}</a></p>
  <p class="pagefoot">{lang_nav('', lang, R)}</p>
</div>
<script>(function(){{var q=document.getElementById('hubq'),a=[].slice.call(document.querySelectorAll('#hub a'));
q.addEventListener('input',function(){{var v=q.value.trim().toLowerCase();a.forEach(function(x){{x.hidden=!!v&&x.getAttribute('data-k').indexOf(v)<0;}});}});}})();</script>
<script src="{R}js/ads.js" defer></script>
</body>
</html>"""


# ---------------- sitemap ----------------
def write_sitemap_block(urls_fp):
    """sitemap.xml 裡的多語言 /<lang>/cp/ 區塊；lastmod 只在頁面內容（指紋）改變時才換成今天。"""
    path = os.path.join(ROOT, "sitemap.xml")
    xml = open(path, encoding="utf-8", newline="").read()
    nl = "\r\n" if "\r\n" in xml else "\n"
    xml = re.sub(r"[ \t]*<!-- CP 多語言頁：[^\n]*\n", "", xml)
    pat = "|".join(LANGS)
    xml = re.sub(r"[ \t]*<url>\s*<loc>" + re.escape(ORIGIN) + r"/(?:" + pat + r")/cp/[^<]*</loc>.*?</url>[ \t]*\r?\n", "", xml, flags=re.S)
    state_path = os.path.join(ROOT, "data", "cp_static_i18n_lastmod.json")
    try:
        with open(state_path, encoding="utf-8") as f:
            old = json.load(f)
    except (OSError, ValueError):
        old = {}
    today = datetime.date.today().isoformat()
    state = {u: {"fp": fp, "lastmod": (old.get(u) or {}).get("lastmod") if (old.get(u) or {}).get("fp") == fp else today}
             for u, fp in urls_fp.items()}
    for u in state:
        state[u]["lastmod"] = state[u]["lastmod"] or today
    with open(state_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(state, f, ensure_ascii=False, indent=1, sort_keys=True); f.write("\n")
    lines = ["  <!-- CP 多語言頁：由 scripts/build_cp_static_i18n.py 自動產生，勿手改此區塊 -->"]
    for u in urls_fp:
        lines += ["  <url>", f"    <loc>{u}</loc>", f"    <lastmod>{state[u]['lastmod']}</lastmod>",
                  f"    <priority>{'0.5' if u.endswith('/cp/') else '0.6'}</priority>", "  </url>"]
    xml = xml.replace("</urlset>", nl.join(lines) + nl + "</urlset>")
    open(path, "w", encoding="utf-8", newline="").write(xml)


def main():
    targets = [t for t in B.TARGET_LIST if t["name"] in B.CP_DATA]
    terms = load_terms(targets)
    en_names = terms["en"]["names"]
    pool = []
    for rank, t in enumerate(targets):
        p = B.CP_DATA[t["name"]]; d = B.pdx_of(t["name"], p["id"])
        pool.append({"slug": t["slug"], "dex": p["id"], "rank": rank, "img": p["imageUrl"], "cp20": B.cp_at(p, 20, 15),
                     "type_ids": d["types"] if d else [], "en": en_names[t["slug"]]})
    urls_fp = {}
    for lang in LANGS:
        T = terms[lang]
        base = os.path.join(ROOT, lang, "cp")
        for t in targets:
            page = build_page(t, lang, T, pool)
            out = os.path.join(base, t["slug"])
            os.makedirs(out, exist_ok=True)
            with open(os.path.join(out, "index.html"), "w", encoding="utf-8", newline="\n") as f:
                f.write(page)
            urls_fp[f"{ORIGIN}/{lang}/cp/{t['slug']}/"] = hashlib.sha1(page.encode("utf-8")).hexdigest()[:16]
        hub = build_hub(lang, T, pool)
        with open(os.path.join(base, "index.html"), "w", encoding="utf-8", newline="\n") as f:
            f.write(hub)
        urls_fp[f"{ORIGIN}/{lang}/cp/"] = hashlib.sha1(hub.encode("utf-8")).hexdigest()[:16]
    write_sitemap_block(urls_fp)
    print(f"已產生 {len(LANGS)} 種語言 × {len(targets)} 隻 = {len(LANGS) * len(targets)} 頁，加上 {len(LANGS)} 個列表頁；sitemap.xml 已更新")


if __name__ == "__main__":
    main()
