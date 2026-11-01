# -*- coding: utf-8 -*-
"""
PvP IV 排名的其他語言版本：/<lang>/pvp-ranker/（由 build_cp_static_i18n.py 一起呼叫，不單獨執行）。

做法：
- 頁面以中文版 pvp-ranker/index.html 的工具區塊為範本，換掉介面文字、說明改成該語言的版本。
- 同一支 js/pvp-ranker.js：頁面先載入 /<lang>/pvp-ranker/pvp-i18n.js，設定 window.PVP_I18N（介面文字），
  並把 POKEDEX、排名資料裡的寶可夢／招式／屬性名稱、LEAGUES 的聯盟名稱換成該語言。
  排名資料是用「名稱」和 POKEDEX 對應的，所以兩邊用同一張對照表一起換，對應關係不變。
- 名稱用遊戲官方文字（Mega／原始回歸用 pokemon_name_XXXX_YYYY），對照表也存進 data/cp_i18n_terms.json。
"""
import os, re, json, hashlib, collections
import build_cp_static as B
from cp_i18n_strings import STR
from pvp_i18n_strings import P

ROOT, ORIGIN, esc = B.ROOT, B.ORIGIN, B.esc
LANGS = B.I18N_LANGS
DATA_SCRIPTS = ["data/precomputed_pokemon_cp.js", "data/pokemon_translation_map.js", "data/pokemon_names_from_api.js",
                "data/pokemon_data_and_rankings.js", "data/pokemon_images.js", "js/pvp-logic.js"]
RANK_VARS = ("POKEMON_RANKINGS_1500", "POKEMON_RANKINGS_2500", "POKEMON_RANKINGS_10000")
# 排名資料有、但目前 pogo_assets 文字檔還沒收錄的寶可夢（第九世代）。
# 英文、日文用官方名稱；其他語言還沒有可靠的官方對照前先用英文官方名稱，不自行翻譯。
PVP_MANUAL = {
    "來悲粗茶": ("Poltchageist", "チャデス"), "斯魔茶": ("Sinistcha", "ヤバソチャ"), "厄鬼椪": ("Ogerpon", "オーガポン"),
    "吉雉雞": ("Fezandipiti", "キチキギス"), "夠讚狗": ("Okidogi", "イイネイヌ"), "願增猿": ("Munkidori", "マシマシラ"),
    "桃歹郎": ("Pecharunt", "モモワロウ"), "太樂巴戈斯": ("Terapagos", "テラパゴス"), "蜜集大蛇": ("Hydrapple", "カミツオロチ"),
    "裹蜜蟲": ("Dipplin", "カミッチュ"), "鋁鋼橋龍": ("Archaludon", "ブリジュラス"), "波盪水": ("Walking Wake", "ウネルミナモ"),
    "猛雷鼓": ("Raging Bolt", "タケルライコ"), "破空焰": ("Gouging Fire", "ウガツホムラ"), "鐵斑葉": ("Iron Leaves", "テツノイサハ"),
    "鐵磐岩": ("Iron Boulder", "テツノイワオ"), "鐵頭殼": ("Iron Crown", "テツノカシラ"),
}


def _rank_moves():
    moves = set()
    for var in RANK_VARS:
        for e in B._json_block(B._RANK_SRC, var):
            for f in ("fastMove", "chargedMove1", "chargedMove2"):
                if (e.get(f) or "").strip():
                    moves.add(e[f].strip())
    return moves


def extract_pvp_terms(tx, terms, move_name, missing):
    """terms[l]['pvp_names']（POKEDEX 中文名 → 該語言）與 terms[l]['pvp_moves']（排名資料的中文招式名 → 該語言）。
    move_name(mv) 回傳 {lang: 名稱} 或 None（沿用 build_cp_static_i18n 的招式對照）。"""
    en = tx["en"]
    gm = {p["gm"].split("_POKEMON_", 1)[1].lower(): p["name"] for p in B.CP_DATA.values()}
    alias = lambda s: s.replace("_alolan", "_alola").replace("_paldean", "_paldea")
    special = collections.defaultdict(dict)   # dex → {'mega': key, 'mega_x': key, 'mega_y': key, 'primal': key}
    for k, v in en.items():
        m = re.match(r"pokemon_name_(\d{4})_\d{4}$", k)
        if not m:
            continue
        dex = int(m.group(1))
        if v.startswith("Primal "):
            special[dex]["primal"] = k
        elif v.startswith("Mega "):
            special[dex]["mega_x" if v.endswith(" X") else "mega_y" if v.endswith(" Y") else "mega"] = k
    for l in LANGS:
        terms[l]["pvp_names"] = {}
    for d in B.POKEDEX:
        pid, dex, zhn = d["id"], d["dexNumber"], d["name"]
        cp_name = gm.get(pid) or gm.get(alias(pid))
        toks = pid.split("_")
        sp_key = None
        for suf in ("mega_x", "mega_y", "mega", "primal"):
            if pid.endswith("_" + suf) and special[dex].get(suf):
                sp_key = special[dex][suf]
                break
        base_cp, rest = None, []
        if not cp_name and not sp_key and "_" in pid:
            for k in range(len(toks) - 1, 0, -1):
                cand = "_".join(toks[:k])
                if cand in gm or alias(cand) in gm:
                    base_cp, rest = gm.get(cand) or gm.get(alias(cand)), toks[k:]
                    break
        base_zh = re.sub(r"\s*\(.*$", "", zhn).strip()
        for l in LANGS:
            if base_zh in PVP_MANUAL and not cp_name:
                name = PVP_MANUAL[base_zh][1 if l == "ja" else 0]
            elif cp_name:
                name = terms[l]["all"][cp_name]
            elif sp_key:
                name = tx[l].get(sp_key) or en[sp_key]
            elif "_" not in pid:
                name = tx[l].get(f"pokemon_name_{dex:04d}") or en.get(f"pokemon_name_{dex:04d}", zhn)
            elif base_cp and ("(" in base_cp or len(rest) == 1 and rest[0] in ("incarnate", "altered", "aria", "normal", "standard", "ordinary", "average", "hero")):
                name = terms[l]["all"][base_cp]   # 預設型態（化身、別種…），CP 資料那一筆就是同一個型態
            else:
                base = tx[l].get(f"pokemon_name_{dex:04d}") or en.get(f"pokemon_name_{dex:04d}", zhn)
                suf = " ".join(t.title() for t in (rest or toks[1:]))
                name = STR[l]["paren"].format(a=base, b=suf)
            terms[l]["pvp_names"][zhn] = name
    # 不同的中文名對到同一個名稱 → 加上代號區分（排名資料靠名稱對應，必須一對一）
    for l in LANGS:
        inv = collections.defaultdict(list)
        for d in B.POKEDEX:
            inv[terms[l]["pvp_names"][d["name"]]].append(d)
        for name, ds in inv.items():
            zh_names = {d["name"] for d in ds}
            if len(zh_names) > 1:
                for d in ds[1:]:
                    if d["name"] != ds[0]["name"]:
                        # 用代號去掉物種名稱後的部分當後綴（eiscue_ice → Ice）
                        sp = d["id"].split("_")
                        tail = [t for t in sp[1:] if t not in name.lower()] or sp[1:]
                        terms[l]["pvp_names"][d["name"]] = STR[l]["paren"].format(a=name, b=" ".join(t.title() for t in tail))
    for l in LANGS:
        if l != "ja":   # 日文本來就有漢字；其他語言的名稱不能再有中文
            left = sorted(v for v in terms[l]["pvp_names"].values() if re.search(r"[\u4e00-\u9fff]", v))
            if left:
                missing.append(f"pvp-name:{l}:" + "、".join(left[:20]))
    for l in LANGS:
        terms[l]["pvp_moves"] = {}
    for mv in sorted(_rank_moves()):
        if mv == "none":
            continue
        names = move_name(mv)
        if not names:
            missing.append("pvp-move:" + mv)
            continue
        for l in LANGS:
            terms[l]["pvp_moves"][mv] = names[l]


def data_js(lang, T):
    S = P[lang]
    i18n = dict(S["js"])
    i18n["defaultMon"] = T["pvp_names"].get("妙蛙種子", "")
    zh_type = {v: k for k, v in B.TYPE_ZH.items()}
    types = {zhn: T["types"][tid] for zhn, tid in zh_type.items()}
    league = {k: T["league"][k] for k in ("great", "ultra", "master")}
    j = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return ("// 由 scripts/build_pvp_i18n.py 產生，請勿手改。\n"
            "// 介面文字（js/pvp-ranker.js 讀 window.PVP_I18N），並把寶可夢／招式／屬性／聯盟名稱換成這個語言。\n"
            f"window.PVP_I18N={j(i18n)};\n"
            "(function(){\n"
            f"var N={j(T['pvp_names'])},M={j(T['pvp_moves'])},Y={j(types)},G={j(league)};\n"
            "function nm(o){if(N[o.name])o.name=N[o.name];}\n"
            "if(typeof POKEDEX!=='undefined')POKEDEX.forEach(nm);\n"
            "[" + ",".join(f"typeof {v}!=='undefined'?{v}:[]" for v in RANK_VARS) + "].forEach(function(a){a.forEach(function(e){nm(e);"
            "['fastMove','chargedMove1','chargedMove2'].forEach(function(k){if(M[e[k]])e[k]=M[e[k]];});"
            "['type1','type2'].forEach(function(k){if(Y[e[k]])e[k]=Y[e[k]];});});});\n"
            "if(typeof LEAGUES!=='undefined')LEAGUES.forEach(function(l){if(G[l.key])l.name=G[l.key];});\n"
            "})();\n")


def alternates():
    out = [f'<link rel="alternate" hreflang="zh-Hant" href="{ORIGIN}/pvp-ranker/">']
    out += [f'<link rel="alternate" hreflang="{l}" href="{ORIGIN}/{l}/pvp-ranker/">' for l in LANGS]
    out.append(f'<link rel="alternate" hreflang="x-default" href="{ORIGIN}/en/pvp-ranker/">')
    return "\n".join(out)


def page_html(lang, T, lang_nav_html):
    S, C = P[lang], STR[lang]
    zh = open(os.path.join(ROOT, "pvp-ranker", "index.html"), encoding="utf-8").read()
    seg = zh[zh.index('<div class="main-container">'):zh.index('<footer')]
    seg = re.sub(r"<!--.*?-->", "", seg, flags=re.S)
    seg, n = re.subn(r'<section class="tool-guide">.*?</section>', '<section class="tool-guide">' + S["guide"] + '</section>', seg, flags=re.S)
    assert n == 1
    L = T["league"]
    reps = [
        ("<h1>Pokémon Go PvP IV 排名查詢器</h1>", f"<h1>{esc(S['h1'])}</h1>"),
        ('查詢條件<span class="controls-header-hint">(可收合、移動)</span>',
         f'{esc(S["panel"])}<span class="controls-header-hint">{esc(S["panel_hint"])}</span>'),
        ('aria-label="收合條件面板"', f'aria-label="{esc(S["close_aria"])}"'),
        ("輸入寶可夢名稱或編號", esc(S["in_label"])),
        ('placeholder="例如：妙蛙種子 或 1"', f'placeholder="{esc(S["in_ph"].format(bulba=T["pvp_names"].get("妙蛙種子", "")))}"'),
        ("攻擊 (ATK)", esc(S["atk"])), ("防禦 (DEF)", esc(S["def_"])), ("體力 (HP)", esc(S["hp"])),
        ("目前等級: <span", f"{esc(S['cur_lv'])} <span"),
        ("<label>目前CP</label>", f"<label>{esc(S['cur_cp'])}</label>"),
        ("選擇寶可夢後顯示排名", esc(S["qs_empty"])),
        ('<span class="pvp-qs-label">超級聯盟</span>', f'<span class="pvp-qs-label">{esc(L["great"])}</span>'),
        ('<span class="pvp-qs-label">高級聯盟</span>', f'<span class="pvp-qs-label">{esc(L["ultra"])}</span>'),
        ('<span class="pvp-qs-label">大師聯盟</span>', f'<span class="pvp-qs-label">{esc(L["master"])}</span>'),
        ("查看完整結果（含進化型）↓", esc(S["qs_more"])),
        ('aria-label="開啟查詢條件">⚙ 調整條件', f'aria-label="{esc(S["open_aria"])}">{esc(S["toggle"])}'),
    ]
    for a, b in reps:
        assert seg.count(a) == 1, (lang, a)
        seg = seg.replace(a, b)
    # 工具區塊不能再有中文（日文本來就有漢字，改成只確認原本的中文字串都換掉了）
    if lang == "ja":
        left = [x for x, _ in reps if re.search(r"[一-鿿]", x) and x in seg]
    else:
        left = re.findall(r"[一-鿿]+", re.sub(r"<[^>]+>", " ", seg))
    assert not left, (lang, left[:5])
    url = f"{ORIGIN}/{lang}/pvp-ranker/"
    R = "../../"
    scripts = "\n".join(f'<script src="{R}{s}"></script>' for s in DATA_SCRIPTS)
    return f"""<!doctype html>
<html lang="{C['html_lang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8866689605007086" crossorigin="anonymous"></script>
<script src="{R}js/analytics.js"></script>
<script src="{R}config.js"></script>
<script src="{R}js/pageview-counter.js" defer></script>
<script src="{R}js/zh-search.js"></script>
<link rel="icon" type="image/png" sizes="192x192" href="{R}img/masterball.png">
<title>{esc(S['title'])}</title>
<meta name="description" content="{esc(S['desc'])}">
<link rel="canonical" href="{url}">
{alternates()}
<meta name="robots" content="index,follow">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{esc(C['site'])}">
<meta property="og:title" content="{esc(S['h1'])}">
<meta property="og:description" content="{esc(S['desc'])}">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="{C['og_locale']}">
<link rel="stylesheet" href="{R}css/main.css">
<link rel="stylesheet" href="{R}css/pvp-ranker.css">
<style>.pk-top{{max-width:1100px;margin:0 auto;padding:12px 16px 0;font-size:13px;color:#606770}}.pk-top a{{color:#1877f2;text-decoration:none}}
.pk-foot{{text-align:center;color:#606770;font-size:13px;line-height:2;padding:8px 16px 40px}}.pk-foot a{{color:#606770}}</style>
</head>
<body>
<nav class="pk-top" aria-label="{esc(C['crumb_aria'])}"><a href="../">{esc(C['site'])}</a> › <span>{esc(S['crumb'])}</span></nav>
<aside class="site-ad" aria-label="{esc(C['ad'])}" data-ad-reserved><span class="site-ad-label">{esc(C['ad'])}</span><div class="site-ad-ph"></div></aside>
{seg}
<footer class="pk-foot">
  <p><a href="{R}trade-list/?lang={lang}">{esc(C['trade'])}</a> · <a href="../cp/">{esc(C['hub_name'])}</a> · <a href="{R}about/">{esc(C['about'])}</a> · <a href="{R}privacy/#en">{esc(C['privacy'])}</a> · <a href="{R}disclaimer/">{esc(C['disclaimer'])}</a></p>
  <p>{lang_nav_html}</p>
</footer>
{scripts}
<script src="pvp-i18n.js"></script>
<script type="module">
import {{ initializePvpRanker }} from '{R}js/pvp-ranker.js';
initializePvpRanker();
</script>
<script src="{R}js/ads.js" defer></script>
</body>
</html>"""


def generate(terms, lang_nav_fn):
    """寫出 6 種語言的 /<lang>/pvp-ranker/index.html 與 pvp-i18n.js，回傳 {網址: 指紋}（給 sitemap）。"""
    out = {}
    for lang in LANGS:
        T = terms[lang]
        d = os.path.join(ROOT, lang, "pvp-ranker")
        os.makedirs(d, exist_ok=True)
        js = data_js(lang, T)
        names = {"en": "English", "ja": "日本語", "ko": "한국어", "fr": "Français", "de": "Deutsch", "es": "Español"}
        nav = " · ".join(['<a href="../../pvp-ranker/" hreflang="zh-Hant">繁體中文</a>'] +
                         [f'<b>{names[l]}</b>' if l == lang else f'<a href="../../{l}/pvp-ranker/" hreflang="{l}">{names[l]}</a>' for l in LANGS])
        page = page_html(lang, T, nav)
        with open(os.path.join(d, "pvp-i18n.js"), "w", encoding="utf-8", newline="\n") as f:
            f.write(js)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8", newline="\n") as f:
            f.write(page)
        out[f"{ORIGIN}/{lang}/pvp-ranker/"] = hashlib.sha1((page + js).encode("utf-8")).hexdigest()[:16]
    return out
