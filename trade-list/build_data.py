#!/usr/bin/env python3
"""
重建來源資料:data/pokemon.json、data/backgrounds.json
- 寶可夢 sprite + 中文名:本機 PokeMiners pogo_assets
- 可否極巨化(sprite 網格用):GAME_MASTER breadTierGroup
- 背卡 ↔ 寶可夢(含異色/極巨化/暗影/進化,直接明列):**Bulbapedia**「Background (GO)」
  Bulbapedia 在 Cloudflare 後面,用 cloudscraper 取 API;圖床 archives 可直接下載。
需求:pip install cloudscraper
跑完再跑 fetch_assets.py 下載圖片。
"""
import json, re, os, sys, time, urllib.request, urllib.parse
import cloudscraper

POGO_ASSETS = os.environ.get("POGO_ASSETS", r"C:\Users\qian\Desktop\poke_web\pogo_assets")
HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 build"}
ADDR_URL = "https://raw.githubusercontent.com/PokeMiners/pogo_assets/master/Images/Pokemon%20-%20256x256/Addressable%20Assets"
BULBA_API = "https://bulbapedia.bulbagarden.net/w/api.php"
scraper = cloudscraper.create_scraper()
# Mega / Primal 是不可交換的暫時形態 → 背卡與 sprite 一律不列
EXCLUDE_BG = re.compile(r'Mega|Primal', re.I)
EXCLUDE_FORM = re.compile(r'MEGA|PRIMAL')

def get_json(u):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=90).read().decode("utf-8", "ignore"))
def bulba(params):
    return scraper.get(BULBA_API, params=params, timeout=90).json()

# ---- 多國語言寶可夢名稱(產出 data/names/<code>.json) + 中文預設 ----
LANG_FILES = {"zh": "chinesetraditional", "en": "english", "ja": "japanese", "ko": "korean", "fr": "french", "de": "german", "es": "spanish"}
os.makedirs(os.path.join(HERE, "data", "names"), exist_ok=True)
zh = {}; en_names = {}
for code, fname in LANG_FILES.items():
    data = json.load(open(os.path.join(POGO_ASSETS, "Texts/Latest APK/JSON", f"i18n_{fname}.json"), encoding="utf-8"))["data"]
    m = {data[i]: data[i+1] for i in range(0, len(data)-1, 2)}
    names = {str(int(g.group(1))): v for k, v in m.items() if (g := re.fullmatch(r"pokemon_name_(\d{4})", k))}
    json.dump(names, open(os.path.join(HERE, "data", "names", f"{code}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    if code == "zh": zh = {int(k): v for k, v in names.items()}
    if code == "en": en_names = {int(k): v for k, v in names.items()}
# 英文名 → 全國圖鑑編號(Fandom 用英文名,需反查 dex)
name2dex = {v.upper().replace(" ", "_"): d for d, v in en_names.items()}

# ---- GM:可否極巨化 ----
gm = get_json("https://raw.githubusercontent.com/PokeMiners/game_masters/master/latest/latest.json")
lego_dex = set()
for e in gm:
    m = re.match(r"V(\d+)_POKEMON_", e.get("templateId", ""))
    ps = e.get("data", {}).get("pokemonSettings")
    if not (m and ps): continue
    dex = int(m.group(1))
    if ps.get("pokemonClass") in ("POKEMON_CLASS_LEGENDARY", "POKEMON_CLASS_MYTHIC", "POKEMON_CLASS_ULTRA_BEAST"): lego_dex.add(dex)

# 可極巨化名單:用 Bulbapedia「Dynamax (GO)」實際開放清單。
# (GM 的 breadTierGroup 幾乎每隻都有,是預設層級,不代表真的能極巨化,不可用)
dmax_dex = set()
try:
    dwt = bulba({"action": "parse", "page": "Dynamax (GO)", "prop": "wikitext", "format": "json"})["parse"]["wikitext"]["*"]
    di = dwt.find("capable of Dynamaxing")
    dmax_dex = {int(m.group(1)) for m in re.finditer(r'\{\{MSP/GO\|(\d+)', dwt[di:] if di >= 0 else dwt)}
    print(f"可極巨化(Bulbapedia):{len(dmax_dex)} 隻", file=sys.stderr)
except Exception as ex:
    print("Dynamax 名單抓取失敗:", ex, file=sys.stderr)

# ---- sprite 變體(本機 PokeMiners)----
def parse(fn):
    toks = fn[:-len(".icon.png")].split(".")
    m = re.fullmatch(r"pm(\d+)", toks[0])
    if not m: return None
    v = {"dex": int(m.group(1)), "form": None, "costume": None, "female": False, "shiny": False, "gmax": False}
    for t in toks[1:]:
        if t == "s": v["shiny"] = True
        elif t == "g2": v["female"] = True
        elif t == "fGIGANTAMAX": v["gmax"] = True
        elif t.startswith("f"): v["form"] = t[1:]
        elif t.startswith("c"): v["costume"] = t[1:]
    return v
ADDR = os.path.join(POGO_ASSETS, "Images", "Pokemon - 256x256", "Addressable Assets")
pokemon = {}
for fn in sorted(os.listdir(ADDR)):
    if not fn.endswith(".icon.png"): continue
    v = parse(fn)
    if not v: continue
    if v["form"] and EXCLUDE_FORM.search(v["form"]): continue  # Mega/Primal 不可交換,不列入
    dex = v["dex"]
    p = pokemon.setdefault(dex, {"id": dex, "zh": zh.get(dex, f"#{dex}"), "variants": [], "gigantamax": None, "dynamax_capable": dex in dmax_dex, "legendary": dex in lego_dex})
    url = f"{ADDR_URL}/{fn}"
    if v["gmax"]:
        p["gigantamax"] = p["gigantamax"] or {}
        p["gigantamax"]["shiny" if v["shiny"] else "normal"] = url
    else:
        p["variants"].append({"url": url, "shiny": v["shiny"], "gender": "female" if v["female"] else None, "form": v["form"], "costume": v["costume"]})
pokemon = {k: v for k, v in pokemon.items() if v["variants"] or v["gigantamax"]}

# ---- 型態解析共用工具(Bulbapedia 短碼後綴 與 Fandom 描述式 ci 共用) ----
# 目標:背卡標的若是特定型態(帕底亞肯泰羅、Origin 神獸、Therian 三精靈…)就對到正確 sprite,而非基本圖。
#   兩來源都對照該 dex「實際擁有的 form 代碼」比對,只在唯一/明確命中時採用,否則退回基本圖(絕不標錯)。
#   未來新型態只要 form 代碼的字首縮寫或關鍵詞對得上就自動生效,無需維護對照表。
COSTUME_ONLY = {25}   # 皮卡丘後綴幾乎都是造型,且易誤對到某個造型 form → 一律用基本圖
REGIONAL_PREFIX = {"alolan": "ALOLA", "galarian": "GALARIAN", "hisuian": "HISUI", "paldean": "PALDEA"}

def _forms_of(dex):
    p = pokemon.get(dex); out = []
    if p:
        for v in p["variants"]:
            if v["form"] and v["form"] not in out: out.append(v["form"])
    return out

def resolve_suffix(dex, suf):
    """Bulbapedia 短碼(128PA / 483O / 386A)→ 該 dex 的 form 代碼。以字首縮寫唯一命中為準,對不到→None。"""
    if dex in COSTUME_ONLY or not suf or suf == suf.lower(): return None   # 純小寫=性別/造型(如 916f)
    S = suf.upper(); cand = []
    for f in _forms_of(dex):
        toks = [t for t in re.split(r'[^A-Z0-9]+', f.upper()) if t]
        initials = "".join(t[0] for t in toks)              # PALDEA_AQUA→'PA'、ORIGIN→'O'
        if S == initials or (len(toks) == 1 and len(S) >= 3 and toks[0].startswith(S)):
            cand.append(f)
    cand = list(dict.fromkeys(cand))
    return cand[0] if len(cand) == 1 else None              # 只在唯一命中時採用,避免同字首誤判

def resolve_form(dex, ci):
    """Fandom 描述式 ci('Tauros aqua')→ form 代碼;修飾詞 token 與 form token 前綴互含(長度≥3)。對不到→None。"""
    if dex in COSTUME_ONLY: return None
    forms = _forms_of(dex)
    if not forms: return None
    sp = {t for t in re.split(r'[^a-z0-9]+', en_names.get(dex, "").lower()) if t}
    mtok = [t for t in re.split(r'[^a-z0-9]+', ci.lower()) if t and t not in sp]   # 去物種名,剩修飾詞
    if not mtok: return None
    match = lambda a, b: len(a) >= 3 and len(b) >= 3 and (a.startswith(b) or b.startswith(a))
    for f in forms:
        ftok = [t for t in re.split(r'[^a-z0-9]+', f.lower()) if t]                 # PALDEA_AQUA→['paldea','aqua']
        if all(any(match(a, b) for b in ftok) for a in mtok): return f
    return None

def _has_shiny(dex, form=None):
    p = pokemon.get(dex)
    return bool(p) and any(v["shiny"] and v["form"] == form and not v["costume"] and not v["gender"] for v in p["variants"])

def name_to_dex(nm):
    """Fandom 顯示名 → (dex, 隱含型態);支援「Alolan Vulpix」這種地區型前綴。"""
    nm = nm.strip()
    sp = {"Ho-Oh": 250, "Deerling": 585, "Flamigo": 973}.get(nm)
    if sp: return sp, None
    d = name2dex.get(nm.upper().replace(" ", "_"))
    if d: return d, None
    parts = nm.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() in REGIONAL_PREFIX:
        d = name2dex.get(parts[1].upper().replace(" ", "_"))
        if d: return d, REGIONAL_PREFIX[parts[0].lower()]
    return None, None

def _nrm(s):
    s = s.lower(); s = re.sub(r'\.(png|jpg|webp)$', '', s)
    for w in ("go ", "special ", "location ", "background", "card"): s = s.replace(w, "")
    return re.sub(r'[^a-z0-9]', '', s)

# ---- Bulbapedia 背卡 ----
print("抓 Bulbapedia…", file=sys.stderr)
wt = bulba({"action": "parse", "page": "Background (GO)", "prop": "wikitext", "format": "json"})["parse"]["wikitext"]["*"]

MSP = re.compile(r'\{\{MSP/GO\|(\d+)([A-Za-z]*)\|([^|}]*)((?:\|[a-z]+=[^|}]*)*)\}\}')
def parse_mons(text):
    # GMax 後綴=超極巨化;dynamax=yes=只有極巨化版(無一般)。以 (dex,form,gmax,dynamax,shadow) 區分,不合併。
    entries = []
    for m in MSP.finditer(text):
        dex = int(m.group(1)); suf = m.group(2); params = m.group(4)
        gmax = suf == "GMax"
        form = None if gmax else resolve_suffix(dex, suf)   # 128PA→PALDEA_AQUA…;對不到→基本圖
        entries.append({"dex": dex, "form": form, "gmax": gmax,
                        "shiny": "shiny=yes" in params,
                        "dynamax": "dynamax=yes" in params,
                        "shadow": "shadow=yes" in params})
    agg = {}
    for e in entries:
        k = (e["dex"], e["form"], e["gmax"], e["dynamax"], e["shadow"])
        a = agg.setdefault(k, {"dex": e["dex"], "form": e["form"], "gmax": e["gmax"], "dynamax": e["dynamax"], "shadow": e["shadow"], "shiny": False})
        a["shiny"] |= e["shiny"]
    return list(agg.values())

def section(title):
    head = "===" + title + "==="
    i = wt.find(head)
    if i < 0: return ""
    start = i + len(head)
    m = re.search(r'\n==+[^=]', wt[start:])  # 下一個標題(== 或 ===,不限層級)
    return wt[start: start + m.start()] if m else wt[start:]

rows = []
for kind, title in [("location", "Locations"), ("special", "Special")]:
    body = section(title)
    cur = None
    for block in re.split(r"\n\|-", body):
        img = re.search(r"\[\[File:(GO [^\|\]]*background[^\|\]]*\.png)", block)
        if img:
            name = ""
            after = block[img.end():]
            nm = re.search(r"\|\s*(?:rowspan=\d+\s*\|)?\s*([^\n|{]+?)\s*\n", after)
            if nm: name = nm.group(1).strip()
            cur = {"type": kind, "image_name": img.group(1).strip(), "name": name, "pokemon": []}
            rows.append(cur)
        if cur is not None:
            cur["pokemon"] += parse_mons(block)
    # 合併每張背卡的寶可夢(去重)
for r in rows:
    agg = {}
    for o in r["pokemon"]:
        k = (o["dex"], o.get("form"), o["gmax"], o["dynamax"], o["shadow"])
        a = agg.setdefault(k, {"dex": o["dex"], "form": o.get("form"), "gmax": o["gmax"], "dynamax": o["dynamax"], "shadow": o["shadow"], "shiny": False})
        a["shiny"] |= o["shiny"]
    r["pokemon"] = sorted(agg.values(), key=lambda x: (x["dex"], str(x.get("form")), x["gmax"], x["dynamax"], x["shadow"]))
    for o in r["pokemon"]:                     # form=None 不寫進 JSON,保持精簡
        if o.get("form") is None: o.pop("form", None)
rows = [r for r in rows if r["pokemon"]]

# 背卡圖 URL(cloudscraper 批次 imageinfo)
uniq = sorted({r["image_name"] for r in rows}); um = {}
for i in range(0, len(uniq), 40):
    ttl = "|".join("File:" + x.replace(" ", "_") for x in uniq[i:i+40])
    q = bulba({"action": "query", "titles": ttl, "prop": "imageinfo", "iiprop": "url", "format": "json"})
    for pg in q["query"]["pages"].values():
        ii = pg.get("imageinfo")
        if ii: um[pg["title"].replace("File:", "").replace("_", " ")] = ii[0]["url"]
    time.sleep(0.3)
for r in rows: r["image_url"] = um.get(r["image_name"])

# ---- Fandom 補充:Bulbapedia 沒有的 location / special 背卡 ----
# Fandom 用 {{I|名稱|…|ci=型態圖名|…}}:ci 可能是「型態」(Tauros aqua→帕底亞水種)或「造型」(Pikachu baseball)。
#   型態 → resolve_form() 對到 form 代碼,存進 pokemon.form,前端挑對應變體;造型 → 退回基本圖。
#   (型態解析工具 resolve_form / name_to_dex / _has_shiny / _nrm 已在 Bulbapedia 前定義,兩來源共用。)

FILE_RE = re.compile(r'\[\[File:([A-Za-z][^\]\|]+?\.png)')
MONI_RE = re.compile(r'\{\{I\|([^\|\}]+)((?:\|[^}]*?))?\}\}')
def fandom_rows(body, kind):
    """一個章節 body → 背卡列表,每隻帶 dex(+form)。rowspan 續行的寶可夢掛回上一張圖。"""
    raw = []
    for block in re.split(r'\n\|-', body):
        im = FILE_RE.search(block)
        mons = []
        for m in MONI_RE.finditer(block):
            rest = m.group(2) or ""; cm = re.search(r'ci=([^\|\}]+)', rest)
            mons.append((m.group(1).strip(), cm.group(1).strip() if cm else None))
        if im:
            raw.append({"image_name": im.group(1).strip().replace("_", " "), "mons": mons})
        elif raw and mons:
            raw[-1]["mons"] += mons
    out = []
    for r in raw:
        seen = {}
        for base, ci in r["mons"]:
            dex, pref = name_to_dex(base)
            if not dex: continue
            form = pref or (resolve_form(dex, ci) if ci else None)
            key = (dex, form)
            if key in seen: continue
            e = {"dex": dex, "shiny": _has_shiny(dex, form), "dynamax": False, "shadow": False, "gmax": False}
            if form: e["form"] = form
            seen[key] = e
        if seen:
            out.append({"type": kind, "source": "fandom", "image_name": r["image_name"], "pokemon": list(seen.values())})
    return out

try:
    fwt = get_json("https://pokemongo.fandom.com/api.php?action=parse&page=Backgrounds&prop=wikitext&format=json")["parse"]["wikitext"]["*"]
    def _fsec(a, b):
        i = fwt.find(a); j = fwt.find(b) if b else len(fwt)
        return fwt[i:j] if i >= 0 else ""
    fboth = (fandom_rows(_fsec("List of Location Backgrounds", "\n==Unreleased"), "location")
             + fandom_rows(_fsec("List of Special Backgrounds", "List of Location Backgrounds"), "special"))
    # 依 type 各自對照 Bulbapedia 既有名稱(正規化後比對),只補缺的
    have = {"location": set(), "special": set()}
    for r in rows: have.setdefault(r["type"], set()).add(_nrm(r["image_name"]))
    cand, seen_img = [], set()
    for r in fboth:
        if _nrm(r["image_name"]) in have.get(r["type"], set()): continue
        if r["image_name"] in seen_img: continue
        seen_img.add(r["image_name"]); cand.append(r)
    funiq = sorted({r["image_name"] for r in cand}); fum = {}
    for k in range(0, len(funiq), 40):
        ttl = "|".join("File:" + urllib.parse.quote(x.replace(" ", "_")) for x in funiq[k:k + 40])
        q = get_json(f"https://pokemongo.fandom.com/api.php?action=query&titles={ttl}&prop=imageinfo&iiprop=url&format=json")
        for pg in q["query"]["pages"].values():
            ii = pg.get("imageinfo")
            if ii: fum[pg["title"].replace("File:", "").replace("_", " ")] = ii[0]["url"]
        time.sleep(0.2)
    fadd = {"location": 0, "special": 0}
    for r in cand:
        url = fum.get(r["image_name"])
        if not url: continue
        r["image_url"] = url; rows.append(r); fadd[r["type"]] += 1
    print(f"Fandom 補充背卡:location {fadd['location']} / special {fadd['special']}", file=sys.stderr)
except Exception as ex:
    import traceback; traceback.print_exc()
    print("Fandom 補充失敗(略過):", ex, file=sys.stderr)

json.dump({str(k): v for k, v in sorted(pokemon.items())}, open(os.path.join(HERE, "data", "pokemon.json"), "w", encoding="utf-8"), ensure_ascii=False)
rows = [r for r in rows if not EXCLUDE_BG.search(r["image_name"])]  # 排除 Mega 專屬(不可交換)
json.dump(rows, open(os.path.join(HERE, "data", "backgrounds.json"), "w", encoding="utf-8"), ensure_ascii=False)
combos = sum(len(r["pokemon"]) for r in rows)
print(f"寶可夢 {len(pokemon)} / 變體 {sum(len(p['variants']) for p in pokemon.values())} / 超極巨化 {sum(1 for p in pokemon.values() if p['gigantamax'])}")
print(f"背卡 {len(rows)} / 有圖 {sum(1 for r in rows if r['image_url'])} / 背卡×寶可夢 {combos} / 極巨化 {sum(1 for r in rows for m in r['pokemon'] if m['dynamax'])} / 超極巨化 {sum(1 for r in rows for m in r['pokemon'] if m['gmax'])} / 可異色 {sum(1 for r in rows for m in r['pokemon'] if m['shiny'])}")
print("完成。接著跑 fetch_assets.py。")
