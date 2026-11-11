#!/usr/bin/env python3
"""產生 PvP 對戰模擬器（/pvp-sim/）用的資料與對戰引擎。

    python scripts/build_pvp_sim.py              # 下載最新資料（引擎維持固定版本）
    PVPOKE_DIR=…/pvpoke python scripts/build_pvp_sim.py   # 改讀本機 clone，不連網

產出：
  data/pvp_sim.json      精簡版 gamemaster（寶可夢、招式、對戰設定）＋三個聯盟的推薦招式與排名順序
  js/pvpoke-engine.js    PvPoke 的對戰引擎原始碼（MIT），包在一個函式裡，只對外公開 window.PvPokeEngine

來源：
  - 對戰引擎、gamemaster、排名：PvPoke（https://github.com/pvpoke/pvpoke，MIT License）
  - 中文寶可夢與招式名稱：PvPoke 繁中版（https://pvpoketw.com/）的 gamemaster
  - 圖片：站內交易清單的縮圖（trade-list/assets/thumb/）

引擎鎖在 ENGINE_COMMIT 指定的版本：引擎換版可能改變資料格式，要人工確認後再改這個值。
資料（gamemaster、排名）每次都抓最新的；兩者的 timestamp 會寫進 JSON，頁面上顯示資料日期。

不在 CI：遊戲平衡調整或新寶可夢上線後，在本機重跑再提交。
"""
import json, os, re, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DATA = os.path.join(ROOT, "data", "pvp_sim.json")
OUT_ENGINE = os.path.join(ROOT, "js", "pvpoke-engine.js")
THUMB_DIR = os.path.join(ROOT, "trade-list", "assets", "thumb")
IMAGES_JS = os.path.join(ROOT, "data", "pokemon_images.js")

ENGINE_COMMIT = "a9dfd500421cacf2842d54d8adcb15830c1eef2b"   # 2026-11-09，已在本機用排名資料驗證 1,800 場結果一致
RAW = "https://raw.githubusercontent.com/pvpoke/pvpoke/{ref}/{path}"
TW_GM = "https://pvpoketw.com/data/gamemaster.json"
UA = {"User-Agent": "pogokit.com data build (+https://pogokit.com/about/)"}
ENGINE_FILES = [
    "src/js/GameMaster.js",
    "src/js/battle/DamageCalculator.js",
    "src/js/battle/timeline/TimelineEvent.js",
    "src/js/battle/timeline/TimelineAction.js",
    "src/js/battle/actions/ActionLogic.js",
    "src/js/battle/Battle.js",
    "src/js/pokemon/Pokemon.js",
    "src/js/pokemon/Player.js",
]
LEAGUES = (1500, 2500, 10000)
POKEMON_KEYS = ("dex", "speciesId", "baseStats", "types", "fastMoves", "chargedMoves", "tags", "defaultIVs",
                "level25CP", "eliteMoves", "legacyMoves", "extraChargedMoves", "levelFloor", "levelCap",
                "originalFormId", "formChange", "nativeStatBuffs", "aliasId")


def fetch(path, ref="master"):
    """PvPoke repo 內的檔案：有 PVPOKE_DIR 就讀本機，否則從 GitHub 下載。"""
    local = os.environ.get("PVPOKE_DIR")
    if local:
        with open(os.path.join(local, path), encoding="utf-8") as f:
            return f.read()
    req = urllib.request.Request(RAW.format(ref=ref, path=path), headers=UA)
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8")


def fetch_url(url):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8")


# ---------- 中文名稱 ----------

def zh_display(tw_name):
    """pvpoketw 的名稱（例：「嘎啦嘎啦 阿羅拉 暗影」「噴火龍 Mega X」）→（顯示名, 是否暗影）。
    寫法和 /pvp-ranker/ 聯盟排名頁一致：型態放全形括號，暗影另外用標籤顯示，Mega 寫成「超級」。"""
    parts = tw_name.split(" ")
    shadow = "暗影" in parts[1:]
    mega = "Mega" in parts[1:]
    tokens = [t for t in parts[1:] if t not in ("暗影", "Mega")]
    name = ("超級" if mega else "") + parts[0] + (f"（{'・'.join(tokens)}）" if tokens else "")
    return name, shadow


# ---------- 圖片 ----------

def load_images():
    with open(IMAGES_JS, encoding="utf-8") as f:
        src = f.read()
    return dict(re.findall(r'"([a-z0-9_]+)":\s*"([^"]+)"', src))


def thumb(sid, dex, images, thumbs):
    """speciesId → 站內縮圖（相對網站根目錄）。找不到對應型態就用同編號的一般型態。"""
    base_id = re.sub(r"_(shadow|xs|xl)$", "", sid)
    remote = images.get(base_id) or images.get(base_id.split("_")[0]) or ""
    cands = []
    m = re.search(r"_mega(_[xy])?$", base_id)
    if m:
        cands.append(f"pm{dex}.fMEGA{(m.group(1) or '').upper()}.icon.webp")
    if remote:
        cands.append(os.path.splitext(remote.rsplit("/", 1)[-1])[0] + ".webp")
    cands.append(f"pm{dex}.icon.webp")
    for c in cands:
        if c in thumbs:
            return "trade-list/assets/thumb/" + c
    forms = sorted(n for n in thumbs if n.startswith(f"pm{dex}.f") and n.endswith(".icon.webp") and ".s.icon" not in n)
    return "trade-list/assets/thumb/" + forms[0] if forms else ""


# ---------- 引擎 ----------

ENGINE_PRELUDE = r"""
	// ---- PogoKit：瀏覽器端的最小執行環境 ----
	// PvPoke 原本跑在它自己的網站上（jQuery、介面物件、設定）。這裡只用到對戰計算，
	// 所以只補上引擎實際會碰到的幾個名稱，全部是這個函式裡的區域變數，不會汙染 window。
	var host = "", webRoot = "", siteVersion = "";
	var settings = { gamemaster: "gamemaster", hardMovesetLinks: false, colorblindMode: false };
	var InterfaceMaster = { getInstance: function(){ return { init: function(){} }; }, getInterface: function(){ return null; } };
	var __pending = null;
	var $ = function(){ var o = { insertAfter: function(){ return o; }, eq: function(){ return o; }, append: function(){ return o; } }; return o; };
	$.ajax = function(opts){ __pending = opts; };
	$.getJSON = function(){};
	$.each = function(obj, fn){ if (Array.isArray(obj)) obj.forEach(function(v, i){ fn(i, v); }); else for (var k in obj) fn(k, obj[k]); };
"""

ENGINE_EXPORT = r"""
	// ---- PogoKit：對外介面 ----
	window.PvPokeEngine = {
		version: "%s",
		load: function(data){
			GameMaster.getInstance();          // 建立實例時會呼叫上面的 $.ajax（只記下 callback）
			if (__pending) { __pending.success(data); __pending = null; }
			return GameMaster.getInstance();
		},
		GameMaster: GameMaster, Battle: Battle, Pokemon: Pokemon, DamageCalculator: DamageCalculator,
		DamageMultiplier: typeof DamageMultiplier !== "undefined" ? DamageMultiplier : null,
		// 沙盒模式（使用者改開盾、延後放招、換人擋招）要用到：
		ActionLogic: ActionLogic, Player: Player, TimelineAction: TimelineAction
	};
"""


def build_engine():
    lic = fetch("LICENSE", ENGINE_COMMIT).strip()
    parts = []
    for p in ENGINE_FILES:
        src = fetch(p, ENGINE_COMMIT).replace("\r\n", "\n")
        parts.append(f"\n\t// ===== {p} =====\n" + src)
    head = ("/*!\n * PvPoke battle engine — https://github.com/pvpoke/pvpoke\n"
            f" * commit {ENGINE_COMMIT}\n * files: " + ", ".join(p.replace("src/js/", "") for p in ENGINE_FILES) + "\n *\n"
            " * Bundled unmodified by pogokit.com (scripts/build_pvp_sim.py) for the PvP battle simulator.\n"
            " * Only a small shim (see below) is added so it runs without jQuery or the PvPoke UI.\n *\n"
            + "\n".join(" * " + l if l else " *" for l in lic.split("\n")) + "\n */\n")
    body = (head + "(function(){\n" + ENGINE_PRELUDE + "".join(parts) + ENGINE_EXPORT % ENGINE_COMMIT[:7] + "})();\n")
    with open(OUT_ENGINE, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    print(f"已寫出 js/pvpoke-engine.js（{len(body.encode('utf-8')):,} bytes，PvPoke {ENGINE_COMMIT[:7]}）")


# ---------- 資料 ----------

def build_data():
    gm = json.loads(fetch("src/data/gamemaster.min.json"))
    tw = json.loads(fetch_url(TW_GM))
    tw_mon = {p["speciesId"]: p["speciesName"] for p in tw["pokemon"]}
    tw_move = {m["moveId"]: m["name"] for m in tw["moves"]}
    images = load_images()
    thumbs = set(os.listdir(THUMB_DIR)) if os.path.isdir(THUMB_DIR) else set()
    # 縮圖裡寶可夢實際的範圍（交易清單 fetch_assets.py 產生的 data/trim.json：[x, y, 寬, 高] 比例），
    # 頁面用它把每隻置中、放大到差不多大小（有的圖很寬、有的很小）
    trim_path = os.path.join(ROOT, "trade-list", "data", "trim.json")
    trim = json.load(open(trim_path, encoding="utf-8")) if os.path.exists(trim_path) else {}

    # 對戰中會變身的型態（謎擬Ｑ現形、堅盾劍怪刀劍形態、莫魯貝可空腹…）在 gamemaster 標成未推出，
    # 但引擎變身時要讀它們的資料，所以要留下；只是不放進選單（hide）。
    # 古月鳥的 alternativeFormId 是 "variable"（引擎依 HP 選 cramorant_gulping／gorging），
    # 所以會變身的寶可夢，同一個前綴的未推出型態全部留下。
    changers = {p["speciesId"].split("_")[0] for p in gm["pokemon"] if p.get("released") and p.get("formChange")}
    alt = {p["speciesId"] for p in gm["pokemon"] if not p.get("released") and p["speciesId"].split("_")[0] in changers}

    pokemon, no_zh, no_img = [], [], []
    for p in gm["pokemon"]:
        sid = p["speciesId"]
        if not p.get("released") and sid not in alt:
            continue
        o = {k: p[k] for k in POKEMON_KEYS if k in p}
        if not p.get("released"):
            o["hide"] = 1
        tw_name = tw_mon.get(sid)
        if tw_name and not re.match(r"^[A-Za-z]", tw_name):
            o["speciesName"], o["sh"] = zh_display(tw_name)
        else:
            o["speciesName"], o["sh"] = p["speciesName"], "shadow" in (p.get("tags") or [])
            no_zh.append(sid)
        o["en"] = p["speciesName"]
        o["img"] = thumb(sid, p["dex"], images, thumbs).replace("trade-list/assets/thumb/", "")
        if not o["img"]:
            no_img.append(sid)
        tb = trim.get(o["img"].replace(".webp", ""))
        if tb:
            o["tb"] = [round(v, 3) for v in tb]
        pokemon.append(o)

    moves = []
    for m in gm["moves"]:
        o = dict(m)
        o["en"] = m["name"]
        zh = tw_move.get(m["moveId"])
        if zh and not re.match(r"^[A-Za-z]", zh):
            o["name"] = zh
        moves.append(o)

    released = {p["speciesId"] for p in pokemon}
    ranks = {}
    for cp in LEAGUES:
        r = json.loads(fetch(f"src/data/rankings/all/overall/rankings-{cp}.json"))
        ranks[str(cp)] = [[x["speciesId"]] + x["moveset"][:3] + [round(x.get("score", 0), 1)]
                          for x in r if x["speciesId"] in released and x.get("moveset")]

    data = {
        "v": 1,
        "gm": gm.get("timestamp", ""),
        "engine": ENGINE_COMMIT[:7],
        "settings": gm["settings"],
        "cups": [c for c in gm["cups"] if c["name"] == "all"],
        "formats": [],
        "pokemon": pokemon,
        "moves": moves,
        "ranks": ranks,
    }
    # 引擎載入 gamemaster 時會讀到的其他欄位，給空值就好
    for k in ("rankingScenarios", "pokemonTags", "pokemonTraits", "shadowPokemon", "greatLeagueIneligible"):
        data[k] = gm.get(k, []) if k == "shadowPokemon" else []
    with open(OUT_DATA, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"已寫出 data/pvp_sim.json（{os.path.getsize(OUT_DATA):,} bytes）：寶可夢 {len(pokemon)}、招式 {len(moves)}，"
          f"排名 " + "、".join(f"{k}:{len(v)}" for k, v in ranks.items()) + f"；gamemaster {data['gm']}")
    if no_zh:
        print(f"  ⚠ {len(no_zh)} 隻沒有中文名稱（用英文）：{', '.join(no_zh[:12])}")
    if no_img:
        print(f"  ⚠ {len(no_img)} 隻沒有站內縮圖：{', '.join(no_img[:12])}")


TYPES = ["normal", "fire", "water", "grass", "electric", "ice", "fighting", "poison", "ground", "flying", "psychic", "bug",
         "rock", "ghost", "dragon", "dark", "steel", "fairy"]


def build_type_icons():
    """屬性圖示：PokeMiners pogo_assets 的 Images/Types/POKEMON_TYPE_*.png（64px）→ img/types/<屬性>.webp。
    沒有 POGO_ASSETS 就略過（圖示已提交，平常不必重產）。"""
    src = os.path.join(os.environ.get("POGO_ASSETS", os.path.join(os.path.dirname(ROOT), "pogo_assets")), "Images", "Types")
    if not os.path.isdir(src):
        print("（略過屬性圖示：找不到 pogo_assets/Images/Types）")
        return
    from PIL import Image
    out = os.path.join(ROOT, "img", "types")
    os.makedirs(out, exist_ok=True)
    total = 0
    for t in TYPES:
        im = Image.open(os.path.join(src, f"POKEMON_TYPE_{t.upper()}.png")).convert("RGBA").resize((48, 48), Image.LANCZOS)
        path = os.path.join(out, f"{t}.webp")
        im.save(path, "WEBP", quality=88, method=6)
        total += os.path.getsize(path)
    print(f"已寫出 img/types/*.webp（18 個，共 {total:,} bytes）")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    build_engine()
    build_data()
    build_type_icons()
