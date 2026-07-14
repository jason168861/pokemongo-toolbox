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
zh = {}
for code, fname in LANG_FILES.items():
    data = json.load(open(os.path.join(POGO_ASSETS, "Texts/Latest APK/JSON", f"i18n_{fname}.json"), encoding="utf-8"))["data"]
    m = {data[i]: data[i+1] for i in range(0, len(data)-1, 2)}
    names = {str(int(g.group(1))): v for k, v in m.items() if (g := re.fullmatch(r"pokemon_name_(\d{4})", k))}
    json.dump(names, open(os.path.join(HERE, "data", "names", f"{code}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    if code == "zh": zh = {int(k): v for k, v in names.items()}

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

# ---- Bulbapedia 背卡 ----
print("抓 Bulbapedia…", file=sys.stderr)
wt = bulba({"action": "parse", "page": "Background (GO)", "prop": "wikitext", "format": "json"})["parse"]["wikitext"]["*"]

MSP = re.compile(r'\{\{MSP/GO\|(\d+)([A-Za-z]*)\|([^|}]*)((?:\|[a-z]+=[^|}]*)*)\}\}')
def parse_mons(text):
    # GMax 後綴=超極巨化;dynamax=yes=只有極巨化版(無一般)。以 (dex,gmax,dynamax) 區分,不合併。
    entries = []
    for m in MSP.finditer(text):
        dex = int(m.group(1)); suf = m.group(2); params = m.group(4)
        entries.append({"dex": dex, "gmax": suf == "GMax",
                        "shiny": "shiny=yes" in params,
                        "dynamax": "dynamax=yes" in params,
                        "shadow": "shadow=yes" in params})
    agg = {}
    for e in entries:
        k = (e["dex"], e["gmax"], e["dynamax"], e["shadow"])
        a = agg.setdefault(k, {"dex": e["dex"], "gmax": e["gmax"], "dynamax": e["dynamax"], "shadow": e["shadow"], "shiny": False})
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
        k = (o["dex"], o["gmax"], o["dynamax"], o["shadow"])
        a = agg.setdefault(k, {"dex": o["dex"], "gmax": o["gmax"], "dynamax": o["dynamax"], "shadow": o["shadow"], "shiny": False})
        a["shiny"] |= o["shiny"]
    r["pokemon"] = sorted(agg.values(), key=lambda x: (x["dex"], x["gmax"], x["dynamax"], x["shadow"]))
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

# ---- Fandom 補充:Bulbapedia 沒有的 location 背卡(Pokelid / MLB / City Safari 等) ----
def _n2d_f(nm):
    nm = nm.strip()
    return {"Ho-Oh": 250, "Deerling": 585, "Flamigo": 973}.get(nm) or name2dex.get(nm.upper().replace(" ", "_"))
try:
    fwt = get_json("https://pokemongo.fandom.com/api.php?action=parse&page=Backgrounds&prop=wikitext&format=json")["parse"]["wikitext"]["*"]
    fi = fwt.find("List of Location Backgrounds"); fbody = fwt[fi:fi + 80000]
    toks = [("img", m.group(1).strip()) if m.group(1) else ("mon", m.group(2).strip())
            for m in re.finditer(r'\[\[File:(Location[^\]\|]+\.png)|\{\{I\|([^\|\}]+)', fbody)]
    frows = []; st = {"pend": [], "mns": []}
    def _flush():
        if st["pend"] and st["mns"]:
            dl = sorted({d for n in st["mns"] if (d := _n2d_f(n))})
            for im in st["pend"]: frows.append({"image_name": im, "pokemon": dl})
        st["pend"] = []; st["mns"] = []
    for typ, val in toks:
        if typ == "img":
            if st["mns"]: _flush()
            st["pend"].append(val)
        else:
            st["mns"].append(val)
    _flush()
    fseen = {}
    for r in frows:
        if r["pokemon"]: fseen.setdefault(r["image_name"], r)
    frows = list(fseen.values())
    def _nrm(s):
        s = s.lower(); s = re.sub(r'\.(png|jpg|webp)$', '', s)
        s = s.replace("go ", "").replace("background", "").replace("location card", "").replace("location", "")
        return re.sub(r'[^a-z0-9]', '', s)
    have = {_nrm(r["image_name"]) for r in rows if r["type"] == "location"}
    funiq = sorted({r["image_name"] for r in frows}); fum = {}
    for k in range(0, len(funiq), 40):
        ttl = "|".join("File:" + urllib.parse.quote(x.replace(" ", "_")) for x in funiq[k:k + 40])
        q = get_json(f"https://pokemongo.fandom.com/api.php?action=query&titles={ttl}&prop=imageinfo&iiprop=url&format=json")
        for pg in q["query"]["pages"].values():
            ii = pg.get("imageinfo")
            if ii: fum[pg["title"].replace("File:", "").replace("_", " ")] = ii[0]["url"]
        time.sleep(0.2)
    fadd = 0
    for r in frows:
        if _nrm(r["image_name"]) in have: continue
        url = fum.get(r["image_name"])
        if not url: continue
        # Fandom 沒標異色 → 該寶可夢若有異色 base 圖就給異色(前端沒圖會自動略過)
        def _has_shiny(dex):
            p = pokemon.get(dex)
            return bool(p) and any(v["shiny"] and not v["form"] and not v["costume"] and not v["gender"] for v in p["variants"])
        rows.append({"type": "location", "source": "fandom", "image_name": r["image_name"], "image_url": url,
                     "pokemon": [{"dex": d, "shiny": _has_shiny(d), "dynamax": False, "shadow": False, "gmax": False} for d in r["pokemon"]]})
        fadd += 1
    print(f"Fandom 補充 location 背卡:{fadd}", file=sys.stderr)
except Exception as ex:
    print("Fandom 補充失敗(略過):", ex, file=sys.stderr)

json.dump({str(k): v for k, v in sorted(pokemon.items())}, open(os.path.join(HERE, "data", "pokemon.json"), "w", encoding="utf-8"), ensure_ascii=False)
rows = [r for r in rows if not EXCLUDE_BG.search(r["image_name"])]  # 排除 Mega 專屬(不可交換)
json.dump(rows, open(os.path.join(HERE, "data", "backgrounds.json"), "w", encoding="utf-8"), ensure_ascii=False)
combos = sum(len(r["pokemon"]) for r in rows)
print(f"寶可夢 {len(pokemon)} / 變體 {sum(len(p['variants']) for p in pokemon.values())} / 超極巨化 {sum(1 for p in pokemon.values() if p['gigantamax'])}")
print(f"背卡 {len(rows)} / 有圖 {sum(1 for r in rows if r['image_url'])} / 背卡×寶可夢 {combos} / 極巨化 {sum(1 for r in rows for m in r['pokemon'] if m['dynamax'])} / 超極巨化 {sum(1 for r in rows for m in r['pokemon'] if m['gmax'])} / 可異色 {sum(1 for r in rows for m in r['pokemon'] if m['shiny'])}")
print("完成。接著跑 fetch_assets.py。")
