#!/usr/bin/env python3
"""
重建來源資料:data/pokemon.json、data/backgrounds.json
- 寶可夢 sprite + 中文名:本機 PokeMiners pogo_assets
- 可否極巨化(sprite 網格用):GAME_MASTER breadTierGroup
- 背卡 ↔ 寶可夢(含異色/極巨化/暗影/進化,直接明列):**Bulbapedia**「Background (GO)」
  透過 Bulbapedia 官方 api.php 讀取(需 cloudscraper 才能連線),批次之間有節流。
需求:pip install cloudscraper
跑完再跑 fetch_assets.py 下載圖片。
"""
import json, re, os, sys, time, urllib.request, urllib.parse
import cloudscraper

try:                                    # Windows 主控台預設 cp950,吐中文/符號會炸
    sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

POGO_ASSETS = os.environ.get("POGO_ASSETS", r"C:\Users\qian\Desktop\poke_web\pogo_assets")
HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 build"}
ADDR_URL = "https://raw.githubusercontent.com/PokeMiners/pogo_assets/master/Images/Pokemon%20-%20256x256/Addressable%20Assets"
BULBA_API = "https://bulbapedia.bulbagarden.net/w/api.php"
scraper = cloudscraper.create_scraper()
# Mega / Primal 是不可交換的暫時形態 → sprite 一律不列。
# 背卡則「不」依卡名排除:像「GO Mega Evolution」這張,wiki 列的是普通型態的
# 妙蛙花/噴火龍/路卡利歐(0003、0006、0448…而非 0003M、0006MX),那些都能交換,
# 只因卡名有 Mega 就整張砍掉是誤殺。真正的 Mega 專屬卡(如 GO Fest 2026 Mega Mewtwo
# 只列 0150MX/0150MY)會因為型態全被濾掉而自然清空,不必額外用名字判斷。
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

# ---- GM:可否極巨化 + 哪些 form 其實是「造型」----
gm = get_json("https://raw.githubusercontent.com/PokeMiners/game_masters/master/latest/latest.json")
lego_dex = set()
gm_tradable = {}    # dex → {form 代碼(基本型為 None): True/False/None};None=GM 沒講,見 _trad()/tradable()
# 近年的造型(WCS_2024、GOTOUR_2026_A、ROCK_STAR…)在檔名裡是寫成 form 而非 costume,
# 只有 GAME_MASTER 的 formSettings.isCostume 分得出來。抓下來,parse() 時把它們歸回 costume。
gm_costume = {}; gm_real = {}
# (dex, form) → 直接進化成的 {(dex, form)}。要帶 form 才對得起來:
# 阿羅拉小拉達進化成阿羅拉拉達,不是普通拉達。見下方 _descendants / 背卡補進化型。
evo_next = {}

def _formcode(species, form):
    """GM 的 form 是「物種_型態」(RATTATA_ALOLA);切掉物種前綴,基本型與 _NORMAL 一律當成 None,
    才對得上背卡資料裡 form 留空的寫法。"""
    if form.startswith(species + "_"): form = form[len(species) + 1:]
    return None if form in ("", "NORMAL") else form

def _trad(ps):
    """單一型態的 isTradable。GM 對某些型態根本沒寫這個欄位,不能一律當成 False ——
    王之劍蒼響 / 王之盾藏瑪然特就是這樣(欄位缺席,但 isTransferable 是 true),實際遊戲裡可以交換。
    真正鎖住的合體型態(黑白酋雷姆、基格爾德、奈克洛茲瑪合體、無極汰那)是「兩個欄位一起缺席」。
    → 缺席但可轉移 = GM 只是沒重寫,回 None 讓 tradable() 退回該 dex 基本型的值。"""
    t = ps.get("isTradable")
    if t is not None: return bool(t)
    return None if ps.get("isTransferable") else False

for e in gm:
    tid = e.get("templateId", "")
    m = re.match(r"V(\d+)_POKEMON_", tid)
    ps = e.get("data", {}).get("pokemonSettings")
    if m and ps:
        dex = int(m.group(1))
        if ps.get("pokemonClass") in ("POKEMON_CLASS_LEGENDARY", "POKEMON_CLASS_MYTHIC", "POKEMON_CLASS_ULTRA_BEAST"): lego_dex.add(dex)
        sp, f = ps.get("pokemonId", ""), ps.get("form") or ""
        gm_tradable.setdefault(dex, {})[f[len(sp) + 1:] if f.startswith(sp + "_") else (f or None)] = _trad(ps)
        # 進化分支。超級進化走的是 temporaryEvolution 欄位,不會有 "evolution",所以自然被排除;
        # 鐵面忍者(不是 evolutionBranch,是進化時額外生成的)也因此不會被算進來,正好。
        _src = (dex, _formcode(sp, f))
        for _b in (ps.get("evolutionBranch") or []):
            _t = _b.get("evolution") or ""
            _td = name2dex.get(_t)
            if not _td: continue
            _tgt = (_td, _formcode(_t, _b.get("form") or ""))
            if _tgt != _src: evo_next.setdefault(_src, set()).add(_tgt)
    fm = re.fullmatch(r"FORMS_V(\d+)_POKEMON_(.+)", tid)
    fs = e.get("data", {}).get("formSettings")
    if fm and fs:
        dex, species = int(fm.group(1)), fs.get("pokemon", "")
        for f in fs.get("forms", []):
            code = f["form"]
            if code.startswith(species + "_"): code = code[len(species) + 1:]
            (gm_costume if f.get("isCostume") else gm_real).setdefault(dex, set()).add(code)

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

# ---- 可否交換(GM pokemonSettings.isTradable,權威來源,不用自己維護名單)----
# 不可交換的:幻之寶可夢(夢幻→薩戮德;美錄坦/美錄梅塔/桃歹郎是例外,GM 標 true)
#   以及合體/究極型態:黑白酋雷姆、基格爾德(全型態)、奈克洛茲瑪合體、無極汰那。
#   王之劍/王之盾不在此列(GM 只是漏寫 isTradable,見 _trad())。
# 交換清單放這些等於讓人做出無效的清單 → 與 Mega/Primal 同政策,sprite 與背卡一律不列。
# 注意:實際的排除放在最後(見「拿掉不可交換的變體」),不能在這裡就從 pokemon 裡刪掉——
#   背卡的型態解析要靠完整的 form 清單才對得到「0646B → BLACK」,先刪會讓它退回 wiki 原圖、
#   form 變成 None 反而繞過這道過濾(實測會漏掉 40 筆)。
def tradable(dex, form=None):
    """GM 沒收錄這隻/這個型態就當作可交換(寧可多列,不要因 GM 落後 sprite dump 而漏掉新寶可夢)。"""
    t = gm_tradable.get(dex)
    if not t: return True
    v = t.get(form)
    if v is None: v = t.get(None)       # 該型態沒明講 → 退回基本型的值
    return v is True                    # 基本型也沒明講(幻之寶可夢:代歐奇希斯、達克萊伊…)→ 不可交換

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
    # 檔名寫成 form、但 GM 標了 isCostume 的(WCS_2024、GOTOUR_2026_A…)→ 歸回 costume
    if v["form"] and v["form"] in gm_costume.get(v["dex"], ()):
        v["costume"], v["form"] = v["form"], None
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

# 有些寶可夢沒有「無 form」基本圖(基本型本身也帶 form 代碼,如酋雷姆 NORMAL、四季鹿 SPRING、堅盾劍怪 SHIELD)。
# 背卡未指定型態時要挑「預設型態」,否則前端會誤挑到第一個變體(如酋雷姆挑到黑色)。記到 pokemon.base_form。
DEFAULT_FORMS = ("NORMAL", "STANDARD", "INCARNATE", "SPRING", "SHIELD", "ORDINARY",
                 "DISGUISED", "MIDDAY", "SOLO", "BAILE", "AMPED", "OVERCAST", "RED", "FIFTY_PERCENT")
for _p in pokemon.values():
    _vs = _p["variants"]
    if any((not v["form"]) and not v["costume"] and not v["gender"] for v in _vs):
        continue   # 有無-form 基本圖 → 不需要 base_form
    _forms = [v["form"] for v in _vs if v["form"] and not v["costume"] and not v["gender"]]
    for _pref in DEFAULT_FORMS:
        if _pref in _forms:
            _p["base_form"] = _pref; break

# ---- 型態解析共用工具(Bulbapedia 短碼後綴 與 Fandom 描述式 ci 共用) ----
# 目標:背卡標的若是特定型態(帕底亞肯泰羅、Origin 神獸、Therian 三精靈…)就對到正確 sprite,而非基本圖。
#   兩來源都對照該 dex「實際擁有的 form 代碼」比對,只在唯一/明確命中時採用,否則退回基本圖(絕不標錯)。
#   未來新型態只要 form 代碼的字首縮寫或關鍵詞對得上就自動生效,無需維護對照表。
COSTUME_ONLY = set()   # 想「只用基本圖、不解析型態」的 dex 放這裡。皮卡丘造型雖非精確年份仍照解析(使用者要造型)。
REGIONAL_PREFIX = {"alolan": "ALOLA", "galarian": "GALARIAN", "hisuian": "HISUI", "paldean": "PALDEA"}

def _forms_of(dex):
    """可拿來跟 wiki 文字比對的「真型態」。
    近年造型在檔名裡也寫成 form,若不濾掉,Fandom 的『Pikachu red』(訓練家赤紅)會誤中
    GOFEST_2026_CAP_RED(GO Fest 紅帽)。GM 的 formSettings 有標 isCostume,以它為準;
    但 GM 落後 sprite dump(2026 的新造型還沒進 GM),所以規則是:
      該 dex 在 GM 有列過造型 → 只信 GM 認證的真型態;GM 沒列過造型(如未知圖騰)→ 全部都算真型態。
    被濾掉的仍留在 pokemon.json 變體裡(造型網格照顯示),只是不參與文字比對。"""
    p = pokemon.get(dex); out = []
    if p:
        strict = dex in gm_costume
        real = gm_real.get(dex, set())
        for v in p["variants"]:
            if not v["form"] or v["form"] in out: continue
            if strict and v["form"] not in real: continue
            out.append(v["form"])
    return out

def resolve_suffix(dex, suf):
    """Bulbapedia 短碼(128PA / 483O / 386A / 888C)→ 該 dex 的 form 代碼。唯一命中才採用,對不到→None。"""
    if dex in COSTUME_ONLY or not suf or suf == suf.lower(): return None   # 純小寫=性別/造型(如 916f)
    S = suf.upper(); cand = []
    for f in _forms_of(dex):
        toks = [t for t in re.split(r'[^A-Z0-9]+', f.upper()) if t]
        initials = "".join(t[0] for t in toks)              # PALDEA_AQUA→'PA'、ORIGIN→'O'、CROWNED_SWORD→'CS'
        if S == initials or initials.startswith(S) or (len(toks) == 1 and len(S) >= 3 and toks[0].startswith(S)):
            cand.append(f)                                  # 888C→CROWNED_SWORD(縮寫前綴,唯一才算)
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

# ---- 造型解析(第二層:對到本機 PokeMiners 造型代碼)----
# 只在「唯一命中」時採用:query 的每個 token 都要出現在造型代碼的 token 裡,且全 dex 只有一個候選。
#   Jan2020 → JAN_2020_NOEVOLVE ✓   Mystic → SPRING_2023_MYSTIC ✓   Kurta → KURTA ✓
#   summer  → SUMMER_2018 / SUMMER_2023_A..E 兩個以上 → 放棄(交給第三層 wiki 原圖)
# 對不到不是錯誤,是設計:對不到就用 wiki 自己的圖,永遠正確。
TRAINER_TOKENS = set()   # 由 Bulbapedia GoTour<年><訓練家> 後綴自動推導,見下方。避免「May(訓練家)」誤中 MAY_2019 造型

def _toks(s):
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', s)          # GoTour → Go Tour
    s = re.sub(r'([A-Za-z])(\d)', r'\1 \2', s)             # Jan2020 → Jan 2020
    s = re.sub(r'(\d)([A-Za-z])', r'\1 \2', s)
    return [t for t in re.split(r'[^A-Za-z0-9]+', s.lower()) if t]

def _costumes_of(dex):
    p = pokemon.get(dex)
    return sorted({v["costume"] for v in p["variants"] if v["costume"]}) if p else []

def resolve_costume(dex, text):
    """wiki 造型字串(Bulbapedia 'Jan2020' / Fandom 去物種名後的 'mystic')→ 本機造型代碼;不唯一就 None。"""
    want = set(_toks(text))
    if not want or (want & TRAINER_TOKENS): return None
    cand = [c for c in _costumes_of(dex) if want <= set(_toks(c))]
    return cand[0] if len(cand) == 1 else None

def _has_shiny(dex, form=None, costume=None):
    p = pokemon.get(dex)
    return bool(p) and any(v["shiny"] and v["form"] == form and v["costume"] == costume and not v["gender"] for v in p["variants"])

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

# 訓練家名封鎖字:由 GoTour2023May / GoTour2025Hilbert… 這類後綴自動推導,不維護對照表。
# 用途:避免 Fandom 的「Pikachu may」(訓練家小遙)誤中本機的 MAY_2019_NOEVOLVE(五月造型)。
TRAINER_TOKENS.update(t for g in re.finditer(r'\{\{MSP/GO\|(?:size=\d+\|)?\d+ ?GoTour\d{4}([A-Za-z]+)\|', wt)
                        for t in _toks(g.group(1)))

# 後綴可含數字(0009Jul2023)、dex 後可有空格(0521 f)、首參數可能是 size=(size=80|0132PokopiaHat)。
# 舊正則只認純字母後綴,會讓這三類「整筆消失」——2026-07 實測 1271 個標籤漏掉 85 個。
MSP = re.compile(r'\{\{MSP/GO\|(?:size=\d+\|)?((\d+) ?([A-Za-z0-9]*))\|([^|}]*)((?:\|[a-z-]+=[^|}]*)*)\}\}')
MEGA_SUFFIX = {"M", "MX", "MY", "P"}          # Mega/Primal 不可交換,與 EXCLUDE_FORM 同政策
BULBA_SPRITE = "https://archives.bulbagarden.net/media/upload"
bulba_need = set()                            # 需要向 Bulbapedia 問圖網址的 (dex, suffix)
STAT = {"msp_total": 0, "msp_parsed": 0, "form": 0, "costume": 0, "wiki": 0, "unmapped": {}}

def parse_mons(text):
    # GMax 後綴=超極巨化;dynamax=yes=只有極巨化版(無一般)。
    # 後綴三層解析:① 型態(resolve_suffix)② 造型(resolve_costume)③ 都對不到 → 記下來用 wiki 原圖。
    STAT["msp_total"] += len(re.findall(r'\{\{MSP/GO\|', text))
    entries = []
    for m in MSP.finditer(text):
        STAT["msp_parsed"] += 1
        raw = m.group(1); dex = int(m.group(2)); suf = m.group(3); params = m.group(5)
        if suf in MEGA_SUFFIX: continue
        gmax = suf == "GMax"
        form = costume = wiki = None
        if suf and not gmax:
            form = resolve_suffix(dex, suf)                 # 128PA→PALDEA_AQUA、483O→ORIGIN…
            if form: STAT["form"] += 1
            else:
                costume = resolve_costume(dex, suf)         # Jan2020→JAN_2020_NOEVOLVE、Mystic→SPRING_2023_MYSTIC…
                if costume: STAT["costume"] += 1
                else:
                    # 對不到本機 sprite → 用 wiki 自己的圖 File:GO<第一參數>.png(必定存在,就是頁面上顯示的那張)
                    wiki = "GO" + raw + ".png"              # Willow / Explorer / GoTour2025Hilbert / 0521 f…
                    bulba_need.add(wiki); STAT["wiki"] += 1
                    STAT["unmapped"][raw] = STAT["unmapped"].get(raw, 0) + 1
        entries.append({"dex": dex, "form": form, "costume": costume, "wiki": wiki,
                        "ckey": ckey_of(suf) if wiki else None, "gmax": gmax,
                        "shiny": "shiny=yes" in params,
                        "dynamax": "dynamax=yes" in params,
                        "shadow": "shadow=yes" in params})
    return dedup_mons(entries)

def ckey_of(text):
    """跨來源的造型識別碼:Bulbapedia 'Willow' 與 Fandom(去物種名後)'willow' 都算同一個造型,
    合併同名卡時才不會出現兩隻威洛博士皮卡丘;而 Willow 與 Red 仍是不同 key,不會被併掉。"""
    return "-".join(sorted(_toks(text))) or None

def dedup_mons(entries):
    """同一張卡去重。key 必須含 form/costume/ckey,否則三隻造型皮卡丘會被併成一隻普通皮卡丘。"""
    agg = {}
    for e in entries:
        k = (e["dex"], e.get("form"), e.get("costume"), e.get("ckey"), e["gmax"], e["dynamax"], e["shadow"])
        a = agg.get(k)
        if a is None:
            agg[k] = dict(e); continue
        a["shiny"] = a["shiny"] or e["shiny"]
        for f in ("wiki", "sprite", "sprite_shiny"):     # 兩來源互補:誰有圖就用誰的(Fandom 才有獨立異色圖)
            if not a.get(f) and e.get(f): a[f] = e[f]
    return list(agg.values())

def tidy_mons(entries, final=False):
    """去重 + 排序 + 拿掉空欄位(JSON 保持精簡)。final=True 時連中間欄位 wiki/ckey 一起拿掉。"""
    out = sorted(dedup_mons(entries),
                 key=lambda x: (x["dex"], str(x.get("form")), str(x.get("costume")), str(x.get("ckey")),
                                x["gmax"], x["dynamax"], x["shadow"]))
    for o in out:
        for k in ("form", "costume", "wiki", "ckey", "sprite", "sprite_shiny"):
            if o.get(k) is None: o.pop(k, None)
        if final:
            o.pop("wiki", None); o.pop("ckey", None)
    return out

def clean_cell(s):
    """把 wiki 表格欄位轉成純文字。卡名不一定是純文字 —— 例如
    「[[Mega Evolution]]{{tt|*|As of August 31, 2026, …}}」,
    直接用正則抓會抓到提示框內容當卡名。"""
    def tpl(m):
        parts = [p.strip() for p in m.group(1).split('|')]
        args = [p for p in parts[1:] if p and '=' not in p]
        if not args: return ''
        if parts[0].lower() == 'tt': return args[0]       # {{tt|顯示|提示}} → 顯示
        # 其餘遊戲類模板的顯示名是最後一個參數,但結尾常掛一個複數字尾:
        #   {{game3|Gold and Silver|Gold Version|s}} → Gold Version(不是 s)
        #   {{game|Black and White|s|Black Version}} → Black Version
        while len(args) > 1 and len(args[-1]) <= 2 and args[-1].islower():
            args.pop()
        return args[-1]
    for _ in range(3):                                    # 巢狀模板:由內而外反覆代換
        s, n = re.subn(r'\{\{([^{}]*)\}\}', tpl, s)
        if not n: break
    s = re.sub(r'\[\[[^\]|]*\|([^\]]*)\]\]', r'\1', s)    # [[目標|顯示]] → 顯示
    s = re.sub(r'\[\[([^\]]*)\]\]', r'\1', s)             # [[目標]] → 目標
    s = re.sub(r"'{2,}", '', s)                           # 粗體/斜體
    s = re.sub(r'<[^>]*>', '', s)                         # HTML 標籤
    s = re.sub(r'\s+', ' ', s).strip()
    return s.rstrip('*').strip()                          # 去掉註腳星號({{tt|*|…}} 留下的)

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
            # 卡片名在圖片那格的「下一格」:跳過 |100px]] 收尾,再取下一個 | 欄位。
            after = block[img.end():]
            after = after[after.find("\n"):] if "\n" in after else ""
            nm = re.search(r"\|\s*(?:rowspan=\d+\s*\|)?\s*([^\n]*)", after)
            cur = {"type": kind, "image_name": img.group(1).strip(),
                   "name": clean_cell(nm.group(1)) if nm else "", "pokemon": []}
            rows.append(cur)
        if cur is not None:
            cur["pokemon"] += parse_mons(block)
    # 合併每張背卡的寶可夢(去重)
for r in rows:
    r["pokemon"] = tidy_mons(r["pokemon"])
rows = [r for r in rows if r["pokemon"]]

# 圖片網址(cloudscraper 批次 imageinfo);找不到的檔名不會出現在回傳裡
def bulba_image_urls(names):
    names = sorted(names); out = {}
    for i in range(0, len(names), 40):
        ttl = "|".join("File:" + x.replace(" ", "_") for x in names[i:i+40])
        q = bulba({"action": "query", "titles": ttl, "prop": "imageinfo", "iiprop": "url", "format": "json"})
        for pg in q["query"]["pages"].values():
            ii = pg.get("imageinfo")
            if ii: out[pg["title"].replace("File:", "").replace("_", " ")] = ii[0]["url"]
        time.sleep(0.3)
    return out

um = bulba_image_urls({r["image_name"] for r in rows})
for r in rows: r["image_url"] = um.get(r["image_name"])

# 第三層:對不到本機 sprite 的造型,改用 Bulbapedia 頁面上那張 256×256 原圖
sm = bulba_image_urls(bulba_need)
_miss = []
for r in rows:
    for o in r["pokemon"]:
        if not o.get("wiki"): continue
        u = sm.get(o["wiki"])
        if u: o["sprite"] = u                  # Bulbapedia 的異色是星星疊圖,無獨立異色檔 → 前端用原圖+星星角標
        else: _miss.append(o["wiki"])
    r["pokemon"] = tidy_mons(r["pokemon"])
if _miss:
    print(f"⚠ Bulbapedia 造型原圖找不到 {len(_miss)} 筆(將退回基本圖):{sorted(set(_miss))[:10]}", file=sys.stderr)

# ---- Fandom 補充 ----
# Fandom 用 {{I|名稱|…|ci=型態圖名|…}}:ci 可能是「型態」(Tauros aqua→帕底亞水種)或「造型」(Pikachu willow)。
#   型態 → resolve_form();造型 → resolve_costume();都對不到 → 用 Fandom 自己的 File:<ci>.png(含 <ci> shiny.png)。
#   (共用工具 resolve_form / resolve_costume / name_to_dex / _has_shiny / _nrm 已在 Bulbapedia 前定義。)

FILE_RE = re.compile(r'\[\[File:([A-Za-z][^\]\|]+?\.png)')
MONI_RE = re.compile(r'\{\{I\|([^\|\}]+)((?:\|[^}]*?))?\}\}')
fandom_need = set()          # 需要向 Fandom 問網址的 ci 圖名

def flatten_nested(body):
    """「同一列 N 張卡共用同一批寶可夢」的活動(寶可夢中心集章、National Trust…)在 Fandom 是用
    巢狀表格排版:外層一列的第一格塞一整張 {| … |},裡面才是 3 欄一排的卡片。
        |-  /  |  /  {| … |[[File:A]] |[[File:B]] |[[File:C]] / |- / |[[File:D]] … / |}  /  |{{I|Pikachu}}
    巢狀的 |- 會把外層這一列切碎,B、C 連同後面「共用的寶可夢」一起失聯。
    先把巢狀(depth≥2)的 |- 降級成普通儲存格分隔,外層一列才拿得到完整的「N 張圖 + 寶可夢」。"""
    out, depth = [], 0
    for line in body.split("\n"):
        s = line.lstrip()
        if s.startswith("{|"): depth += 1
        elif s.startswith("|}"): depth = max(depth - 1, 0)
        elif depth >= 2 and s.startswith("|-"): line = "|"
        out.append(line)
    return "\n".join(out)

RS_MON = re.compile(r'rowspan\s*=\s*"?\d+"?\s*\|\s*\{\{I\|')   # 寶可夢那一格標了 rowspan

def fandom_rows(body, kind):
    """一個章節 body → 背卡列表,每隻帶 dex(+form/costume/ci)。
    一列可能有多張圖(見 flatten_nested),此時整列的寶可夢由這幾張圖共用。
    兩種 rowspan 續行都要接:寶可夢在上一列(圖在這列)、圖在上一列(寶可夢在這列)。"""
    raw, span_mons = [], []
    for block in re.split(r'\n\|-', flatten_nested(body)):
        mons = []
        for m in MONI_RE.finditer(block):
            rest = m.group(2) or ""; cm = re.search(r'ci=([^\|\}]+)', rest)
            mons.append((m.group(1).strip(), cm.group(1).strip() if cm else None))
        ims = list(FILE_RE.finditer(block))
        if mons:
            span_mons = list(mons) if RS_MON.search(block) else []
        elif ims and span_mons:
            mons = list(span_mons)      # 這列只有圖:寶可夢在上一列被 rowspan 攤開(里約、巴黎二號卡)
        for im in ims:
            eol = block.find("\n", im.end())                                # 地名在同一行的 <br> 後面;
            tail = block[im.end(): eol if eol >= 0 else len(block)]          # 跨行找會撈到活動日期
            nm = re.search(r'<br\s*/?>\s*([^\n<|\[]+)', tail)
            raw.append({"image_name": im.group(1).strip().replace("_", " "),
                        "name": nm.group(1).strip() if nm else "", "mons": list(mons)})
        if not ims and raw and mons:
            raw[-1]["mons"] += mons
    out = []
    for r in raw:
        entries = []
        for base, ci in r["mons"]:
            dex, pref = name_to_dex(base)
            if not dex: continue
            form = pref or (resolve_form(dex, ci) if ci else None)
            costume = wiki = ckey = None
            if ci and not form:
                sp = set(_toks(en_names.get(dex, "")))
                rest = " ".join(t for t in _toks(ci) if t not in sp)      # 去掉物種名,剩修飾詞
                if rest:
                    costume = resolve_costume(dex, rest)
                    if not costume:
                        wiki = ci                                          # Pikachu willow / Eevee explorer…
                        ckey = ckey_of(rest); fandom_need.add(ci)
            entries.append({"dex": dex, "form": form, "costume": costume, "wiki": wiki, "ckey": ckey,
                            "shiny": _has_shiny(dex, form, costume) if not wiki else False,
                            "dynamax": False, "shadow": False, "gmax": False})
        if entries:
            out.append({"type": kind, "source": "fandom", "image_name": r["image_name"],
                        "name": r["name"], "pokemon": tidy_mons(entries)})
    return out

try:
    fwt = get_json("https://pokemongo.fandom.com/api.php?action=parse&page=Backgrounds&prop=wikitext&format=json")["parse"]["wikitext"]["*"]
    def _fsec(title):
        """章節內容:標題 → 下一個二級標題(=== 子標題不算,所以 ===2023=== 這種年份不會被切掉)。
        原本是寫死結束標記 ==Unreleased,但該標題早就不存在(現在叫 ==Unused==),
        find() 回 -1 讓 location 一路吃到 ==Unused==/==Trivia==,未發行的卡也會被當成正式卡。"""
        i = fwt.find(title)
        if i < 0: return ""
        m = re.search(r'\n==[^=\n]+==', fwt[i + len(title):])
        return fwt[i: i + len(title) + m.start()] if m else fwt[i:]
    fboth = (fandom_rows(_fsec("List of Location Backgrounds"), "location")
             + fandom_rows(_fsec("List of Special Backgrounds"), "special"))
    def fandom_image_urls(names):
        names = sorted(names); out = {}
        for k in range(0, len(names), 40):
            ttl = "|".join("File:" + urllib.parse.quote(x.replace(" ", "_")) for x in names[k:k + 40])
            q = get_json(f"https://pokemongo.fandom.com/api.php?action=query&titles={ttl}&prop=imageinfo&iiprop=url&format=json")
            for pg in q["query"]["pages"].values():
                ii = pg.get("imageinfo")
                if ii: out[pg["title"].replace("File:", "").replace("_", " ")] = ii[0]["url"]
            time.sleep(0.2)
        return out

    # 第三層:對不到本機 sprite 的造型 → Fandom 的 File:<ci>.png,異色另有 File:<ci> shiny.png
    csm = fandom_image_urls({f"{ci}.png" for ci in fandom_need} | {f"{ci} shiny.png" for ci in fandom_need})
    for r in fboth:
        for o in r["pokemon"]:
            if not o.get("wiki"): continue
            u = csm.get(f"{o['wiki']}.png"); us = csm.get(f"{o['wiki']} shiny.png")
            if u: o["sprite"] = u
            if us: o["sprite_shiny"] = us; o["shiny"] = True
        r["pokemon"] = tidy_mons(r["pokemon"])

    # 與 Bulbapedia 同名的卡「合併寶可夢」而非整列丟棄(兩邊互有詳略,舊寫法一次丟掉 36 張卡 371 筆)
    by_key = {}
    for r in rows: by_key[(r["type"], _nrm(r["image_name"]))] = r
    cand, seen_img, merged, madd = [], set(), 0, 0
    for r in fboth:
        exist = by_key.get((r["type"], _nrm(r["image_name"])))
        if exist:
            # 只補「Bulbapedia 這張卡完全沒提到的物種」。
            # 兩邊對同一個造型的叫法不同(Bulbapedia 0131Mystic vs Fandom 'Lapras blanche'、
            # 0001Jan2020 vs 'Bulbasaur party hat'),無法自動判定是不是同一件,
            # 若整包倒進去會讓熱門卡出現一堆重複格子。Bulbapedia 有明列後綴、是較完整的來源,
            # 該 dex 只要它提過就以它為準;Fandom 的價值在補它整隻漏掉的。
            have_dex = {m["dex"] for m in exist["pokemon"]}
            add = [m for m in r["pokemon"] if m["dex"] not in have_dex]
            if not add: continue
            before = len(exist["pokemon"])
            exist["pokemon"] = tidy_mons(exist["pokemon"] + add)
            if len(exist["pokemon"]) > before: merged += 1; madd += len(exist["pokemon"]) - before
            continue
        if r["image_name"] in seen_img: continue
        seen_img.add(r["image_name"]); cand.append(r)
    fum = fandom_image_urls({r["image_name"] for r in cand})
    fadd = {"location": 0, "special": 0}
    for r in cand:
        url = fum.get(r["image_name"])
        if not url: continue
        r["image_url"] = url; rows.append(r); by_key[(r["type"], _nrm(r["image_name"]))] = r; fadd[r["type"]] += 1
    print(f"Fandom 補充背卡:location {fadd['location']} / special {fadd['special']}"
          f" / 合併進既有卡 {merged} 張(新增 {madd} 筆寶可夢)", file=sys.stderr)
except Exception as ex:
    import traceback; traceback.print_exc()
    print("Fandom 補充失敗(略過):", ex, file=sys.stderr)

for r in rows: r["pokemon"] = tidy_mons(r["pokemon"], final=True)   # 收尾:拿掉中間欄位 wiki/ckey

# ---- 背卡的進化型補完 ----
# 遊戲裡「異色」與「背卡」都會跟著進化保留:抓到一隻有背卡的異色初階,進化之後就是一隻
# 有背卡的異色進化型。但兩個 wiki 都只記錄「活動當下抓得到什麼」,於是有兩種缺漏:
#   (1) 進化型有列出來,卻沒跟著標 shiny=yes  → 補旗標
#   (2) 進化型整隻沒被列出來(皮卡丘在卡上、雷丘不在) → 補條目
# 兩種都會讓使用者在挑選畫面找不到,以為那個組合換不到。
#
# 判斷來源是 GM 的 evolutionBranch(型態感知),幾個必要的界線:
#   * 祖先有「造型」的一律不傳。NOEVOLVE 造型根本不能進化;而且進化後的造型 sprite 多半
#     也不存在。⚠ 光看 costume 欄位不夠 —— 造型代碼對不到本機 sprite 時,costume 會留空、
#     改用 wiki 原圖(sprite 欄位),那些其實也是造型(GO0025Leaf = 戴小茂帽子的皮卡丘)。
#     兩個欄位都要擋,只擋 costume 會多生出 160 筆錯的。
#   * 新條目只帶 shiny,不帶 dynamax / gmax / shadow —— 那三個是「活動當下開放什麼」,
#     不是進化能繼承的東西。
#   * 目標型態必須真的有對應的本機 sprite,否則前端會破圖。
#   * 要跑在「拿掉不可交換變體」之前:那一步會把 pokemon[].variants 砍掉,
#     砍完再問「這隻有沒有這個型態 / 有沒有異色」會得到錯的答案。
def _descendants(dex, form, seen=None):
    seen = set() if seen is None else seen
    out = set()
    for t in evo_next.get((dex, form), ()):
        if t in seen: continue
        seen.add(t); out.add(t); out |= _descendants(t[0], t[1], seen)
    return out

def _plain_variant(dex, form):
    """該型態有沒有「非造型、非公母專屬」的本機 sprite;回傳 (有沒有, 有沒有異色)。"""
    vs = [v for v in pokemon.get(dex, {}).get("variants", [])
          if (v["form"] or None) == form and not v["costume"] and not v["gender"]]
    return bool(vs), any(v["shiny"] for v in vs)

evo_shiny_n = evo_added_n = 0
for r in rows:
    listed = {(m["dex"], m.get("form")) for m in r["pokemon"]}
    reach = {}                                   # (dex, form) → 祖先裡是否有異色
    for m in r["pokemon"]:
        if m.get("costume") or m.get("sprite"): continue      # 造型不外傳(見上方說明)
        for t in _descendants(m["dex"], m.get("form")):
            reach[t] = reach.get(t, False) or bool(m["shiny"])
    # (1) 已經在卡上的 → 只補異色旗標
    for m in r["pokemon"]:
        k = (m["dex"], m.get("form"))
        if not m["shiny"] and reach.get(k) and _plain_variant(*k)[1]:
            m["shiny"] = True; evo_shiny_n += 1
    # (2) 不在卡上的 → 補條目
    for (dex, form), sh in sorted(reach.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        if (dex, form) in listed: continue
        ok, has_shiny = _plain_variant(dex, form)
        if not ok: continue
        e = {"dex": dex, "shiny": sh and has_shiny, "dynamax": False, "shadow": False, "gmax": False}
        if form: e["form"] = form
        r["pokemon"].append(e); evo_added_n += 1
    # 只重新排序,不能再呼叫 tidy_mons —— 它會再去重一次,而此時 ckey 已經被 final=True 拿掉了,
    # 「只差在 ckey 的造型條目」會被當成重複而併掉(實測會少 47 筆造型)。
    # 新條目是照 listed 檢查過才 append 的,本來就不會撞。
    r["pokemon"].sort(key=lambda x: (x["dex"], str(x.get("form")), str(x.get("costume")),
                                     x["gmax"], x["dynamax"], x["shadow"]))

# ---- 拿掉不可交換的變體(型態解析都做完了,現在才刪才不會影響上面的 form 比對)----
untradable_n = 0
for _p in pokemon.values():
    _keep = [v for v in _p["variants"] if tradable(_p["id"], v["form"])]
    untradable_n += len(_p["variants"]) - len(_keep); _p["variants"] = _keep
    if _p["gigantamax"] and not tradable(_p["id"]): _p["gigantamax"] = None
pokemon = {k: v for k, v in pokemon.items() if v["variants"] or v["gigantamax"]}
# 背卡側套同一條規則(黑酋雷姆、王之劍蒼響…背卡有列但換不了),整張卡只剩不可交換的就丟掉
bg_untradable = 0
for r in rows:
    keep = [m for m in r["pokemon"] if tradable(m["dex"], m.get("form"))]
    bg_untradable += len(r["pokemon"]) - len(keep); r["pokemon"] = keep

# 套用人工修正「之前」的樣子,另存一份給 bg-editor 用。
# ⚠ 少了這一步,編輯器會拿套用後的結果再疊一次 ops —— 條目的 key 早就變了
#   (133||||||GO0133Explorer.png → 133||MAY_2023||||),於是既有修正在畫面上全部對不到、
#   看起來像沒生效。編輯器的模型必須是「原始資料 + ops」,那就得看得到原始資料。
# 空卡先濾掉,與正式輸出的卡片集合一致(不然編輯器會列出永遠不會存在的卡)
json.dump([r for r in rows if r["pokemon"]],
          open(os.path.join(HERE, "data", "backgrounds.raw.json"), "w", encoding="utf-8"), ensure_ascii=False)

# ---- 人工修正:套用 data/bg_overrides.json ----
# 這支程式每次都把 backgrounds.json 整份重寫,所以直接改產出檔會被下一次 update.py 蓋掉。
# 人工修正一律寫在獨立的疊加檔裡(跟 aliases.json 一樣不會被重建碰到),在最後套上去。
# 放在最後 = 人工的判斷最大:連「不可交換」的過濾都已經跑完了,你說要留就留。
# 用 bg-editor.html 編輯這個檔。
def _spr_key(s):
    """sprite 欄位正規化成「同一個名字」。
    ⚠ 這裡的兩端看到的值不一樣:build_data 手上的 rows 存的是遠端網址
    (…/GO0133Explorer.png),但 bg-editor 讀的是 backgrounds.local.json,
    fetch_assets 已經把它換成本機檔名(assets/img/wiki_GO0133Explorer.png)。
    不統一的話 key 對不起來,人工修正會全部靜靜失效(實測 178 筆有 137 筆對不到)。
    → 去路徑、去 wiki_ 前綴,再套 fetch_assets.wiki_sprite_local 的同一套字元替換。"""
    if not s: return ""
    # Fandom 的網址是 .../images/3/37/Eevee_explorer.png/revision/latest?cb=… ——
    # 直接取最後一段會拿到「latest?cb=…」,而且 cb 每次都不一樣。
    # 這段抽檔名的規則與 fetch_assets.wiki_sprite_local() 相同,兩邊才會得到同一個名字。
    m = re.search(r"/images/[0-9a-f/]+/([^/]+\.(?:png|jpg|jpeg|webp))/revision", s, re.I)
    n = m.group(1) if m else s.split("?")[0].rsplit("/", 1)[-1]
    if n.startswith("wiki_"): n = n[5:]
    return re.sub(r"[^A-Za-z0-9._-]", "_", n)

def bg_key(m):
    """條目在一張卡裡的識別碼。要能跨重建保持一致 → 只用會被寫進 JSON 的欄位。"""
    return "|".join([str(m["dex"]), m.get("form") or "", m.get("costume") or "",
                     *("1" if m.get(k) else "" for k in ("gmax", "dynamax", "shadow")),
                     _spr_key(m.get("sprite"))])

def norm_op_key(k):
    """舊的 op 可能存了本機檔名版本的 key,比對前一起正規化(不必改既有的 overrides 檔)。"""
    p = str(k or "").split("|")
    if len(p) == 7: p[6] = _spr_key(p[6])
    return "|".join(p)

ov_removed = ov_set = ov_added = ov_miss = ov_card = 0
ov_missed = []      # 對不到目標的 op,健檢時列出來 —— 不然只有一個數字,不知道要去改哪筆
_ovp = os.path.join(HERE, "data", "bg_overrides.json")
if os.path.exists(_ovp):
    _ov = json.load(open(_ovp, encoding="utf-8"))
    by_name = {r["image_name"]: r for r in rows}
    _drop = set()
    for op in _ov.get("ops", []):
        r = by_name.get(op.get("card"))
        if not r:                                 # 卡不見了(來源改名/移除)→ 記一筆,不要靜靜吞掉
            ov_miss += 1; ov_missed.append((op.get("card"), "整張卡不在了", op.get("key") or "")); continue
        # ---- 卡片層級:同一張卡被 Bulbapedia 與 Fandom 各收一次 ----
        # 兩份的寶可夢清單常互有對方沒有的(春櫻:3 筆 vs 2 筆,只重疊 1),
        # 所以預設是「合併」不是「刪掉」—— 先把條目搬過去,再把這張整個丟掉。
        if op.get("op") in ("mergeCard", "hideCard"):
            if op["op"] == "mergeCard":
                dst = by_name.get(op.get("into"))
                if not dst: ov_miss += 1; continue
                dst["pokemon"] = tidy_mons(dst["pokemon"] + r["pokemon"], final=True)
            _drop.add(op["card"]); ov_card += 1
            continue
        if op.get("op") == "add":
            mon = {"dex": 0, "shiny": False, "dynamax": False, "shadow": False, "gmax": False}
            mon.update(op.get("mon") or {})
            r["pokemon"].append(mon); ov_added += 1
            continue
        want = norm_op_key(op.get("key"))
        hit = [m for m in r["pokemon"] if bg_key(m) == want]
        if not hit:                                # 條目不見了(來源已修好?)→ 同上
            ov_miss += 1; ov_missed.append((op.get("card"), "找不到這個條目", want)); continue
        for m in hit:
            if op.get("op") == "remove":
                r["pokemon"].remove(m); ov_removed += 1
            else:
                for k, v in (op.get("fields") or {}).items():
                    if v is None: m.pop(k, None)
                    else: m[k] = v
                ov_set += 1
    rows = [r for r in rows if r["image_name"] not in _drop]
    for r in rows:
        r["pokemon"].sort(key=lambda x: (x["dex"], str(x.get("form")), str(x.get("costume")),
                                         x["gmax"], x["dynamax"], x["shadow"]))

json.dump({str(k): v for k, v in sorted(pokemon.items())}, open(os.path.join(HERE, "data", "pokemon.json"), "w", encoding="utf-8"), ensure_ascii=False)
rows = [r for r in rows if r["pokemon"]]   # 只留還有可交換寶可夢的卡(Mega 專屬卡會在此自然清空)
json.dump(rows, open(os.path.join(HERE, "data", "backgrounds.json"), "w", encoding="utf-8"), ensure_ascii=False)
combos = sum(len(r["pokemon"]) for r in rows)
print(f"寶可夢 {len(pokemon)} / 變體 {sum(len(p['variants']) for p in pokemon.values())} / 超極巨化 {sum(1 for p in pokemon.values() if p['gigantamax'])}")
print(f"背卡 {len(rows)} / 有圖 {sum(1 for r in rows if r['image_url'])} / 背卡×寶可夢 {combos} / 極巨化 {sum(1 for r in rows for m in r['pokemon'] if m['dynamax'])} / 超極巨化 {sum(1 for r in rows for m in r['pokemon'] if m['gmax'])} / 可異色 {sum(1 for r in rows for m in r['pokemon'] if m['shiny'])}")

# ---- 健檢:來源格式一改,這裡就會現形,不用等肉眼發現 ----
_cos = sum(1 for r in rows for m in r["pokemon"] if m.get("costume"))
_spr = sum(1 for r in rows for m in r["pokemon"] if m.get("sprite"))
print("─" * 60)
print(f"[健檢] Bulbapedia MSP 標籤 {STAT['msp_total']} / 成功解析 {STAT['msp_parsed']}"
      f"{'  ← ⚠ 有漏,正則要修' if STAT['msp_parsed'] < STAT['msp_total'] else '  ✔ 全數解析'}")
print(f"[健檢] 後綴解析:型態 {STAT['form']} / 對到本機造型 {STAT['costume']} / 走 wiki 原圖 {STAT['wiki']}")
print(f"[健檢] 產出帶造型的背卡條目 {_cos} 筆(本機 sprite) + {_spr} 筆(wiki 原圖)")
print(f"[健檢] 不可交換而排除:sprite {untradable_n} 個變體 / 背卡 {bg_untradable} 筆(依 GM isTradable)")
print(f"[健檢] 背卡進化型補完:補異色旗標 {evo_shiny_n} 筆 / 補整筆條目 {evo_added_n} 筆(依 GM evolutionBranch)")
print(f"[健檢] 人工修正(bg_overrides.json):刪 {ov_removed} / 改 {ov_set} / 加 {ov_added} / 整張卡 {ov_card}"
      + (f"  ⚠ 對不到目標 {ov_miss} 筆(來源可能已變動,請用 bg-editor.html 檢查)" if ov_miss else ""))
for _c, _why, _k in ov_missed[:10]:
    print(f"          · {_c[:44]:46s} {_why}  {_k}")
if STAT["unmapped"]:
    top = sorted(STAT["unmapped"].items(), key=lambda kv: -kv[1])[:15]
    print(f"[健檢] 對不到本機 sprite 的後綴 {len(STAT['unmapped'])} 種(已用 wiki 原圖,非錯誤):")
    print("        " + ", ".join(f"{k}×{v}" for k, v in top) + (" …" if len(STAT["unmapped"]) > 15 else ""))
print("─" * 60)
print("完成。接著跑 fetch_assets.py。")
