#!/usr/bin/env python3
"""從 Pokémon GO 官方資料重新整理 data/precomputed_pokemon_cp.js。

一次處理三件事，全部只靠網路來源，**不需要本機的 pogo_assets clone**，所以可以掛在 CI 上跑：
  1. CP 與基礎數值  ← GAME_MASTER（Niantic 調平衡時會自動跟上）
  2. 中文名稱        ← 遊戲 APK 的 i18n_chinesetraditional
  3. 圖片            ← PokeMiners 的 GO 官方 256×256 圖示（取代原本的 PokeAPI 2D sprite）

## 每一列是怎麼認出「牠是哪一隻的哪個形態」的

第一次跑用 **CP 反查**:同一個 dex 底下，找 cp15/cp20/cp25 三個值都吻合的那組基礎數值。
認出來之後把 GAME_MASTER 的 templateId 寫進 `gm` 欄位，之後就直接用它對照。
這件事很重要 —— 一旦 Niantic 調整了某隻的基礎數值，舊的 CP 就再也對不上，
只靠 CP 反查會整列失聯；有 `gm` 就不會，而且才有辦法把「數值變了」報出來。

## 名稱改變時的舊連結

`?mon=<名稱>` 是拿名稱當網址的，改名等於換網址。改到的列會把舊名留在 `alt` 欄位，
前端搜尋也會比對 `alt`，這樣既有的連結與已被 Google 收錄的網址不會失效。

用法:python scripts/refresh_cp_data.py [--dry-run]
"""
import argparse, ast, json, math, os, re, sys, urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "precomputed_pokemon_cp.js")
GM_URL = "https://raw.githubusercontent.com/PokeMiners/game_masters/master/latest/latest.json"
I18N_URL = ("https://raw.githubusercontent.com/PokeMiners/pogo_assets/master/"
            "Texts/Latest%20APK/JSON/i18n_chinesetraditional.json")
SPRITE_DIR = "Images/Pokemon - 256x256/Addressable Assets"
SPRITE_BASE = ("https://raw.githubusercontent.com/PokeMiners/pogo_assets/master/"
               "Images/Pokemon%20-%20256x256/Addressable%20Assets/")
MAX_LEVEL, BEST_BUDDY_LEVEL = 50, 51

# 遊戲 APK 自己就沒有中文的形態，只能自己補。
# 這幾個是人工翻的，跟官方用語若有出入請直接改這裡（改完重跑就會生效）。
FORM_ZH_OVERRIDE = {
    "MEWTWO_A": "鎧甲",
    "DARMANITAN_ZEN": "達摩模式",
    "DARMANITAN_GALARIAN_STANDARD": "伽勒爾標準模式",
    "DARMANITAN_GALARIAN_ZEN": "伽勒爾達摩模式",
    "ZYGARDE_COMPLETE": "完全體",
    "EISCUE_ICE": "冰塊臉",
    "EISCUE_NOICE": "呆呆臉",
    "ETERNATUS_ETERNAMAX": "無極巨化",
    "CALYREX_ICE_RIDER": "白馬騎乘",
    "CALYREX_SHADOW_RIDER": "黑馬騎乘",
}
# 挑「預設型態」用的偏好順序:有些寶可夢連基本圖都帶 form 代碼(未知圖騰、結草兒、櫻花兒…)，
# 沒有 pm<dex>.icon.png 可用，得從牠自己的型態裡挑一個當代表。與 trade-list 同一套邏輯。
DEFAULT_FORMS = ("NORMAL", "STANDARD", "INCARNATE", "SPRING", "SHIELD", "ORDINARY", "DISGUISED",
                 "MIDDAY", "SOLO", "BAILE", "OVERCAST", "RED", "FIFTY_PERCENT", "PLANT", "WEST", "A")


def get_json(url, token=None):
    h = {"User-Agent": "Mozilla/5.0 refresh-cp", "Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = "Bearer " + token
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=180)
                      .read().decode("utf-8", "ignore"))


def sprite_filenames(token=None):
    """用 GitHub trees API 列出 sprite 檔名(3700 多個，實測不會被 truncate)。"""
    api = "https://api.github.com/repos/PokeMiners/pogo_assets/git/trees/"
    node = get_json(api + "master", token)
    for part in SPRITE_DIR.split("/"):
        nxt = next((x for x in node["tree"] if x["path"] == part), None)
        if not nxt:
            raise RuntimeError("找不到 sprite 目錄:" + part)
        node = get_json(api + nxt["sha"], token)
    if node.get("truncated"):
        raise RuntimeError("sprite 清單被 GitHub 截斷了，需要改用分頁抓取")
    return {x["path"] for x in node["tree"] if x["path"].endswith(".icon.png")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只印出會變動什麼，不寫檔")
    args = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN")

    print("抓 GAME_MASTER…", flush=True)
    gm = get_json(GM_URL)
    cpm = None
    by_tid, by_dex = {}, {}
    for e in gm:
        tid = e.get("templateId", "")
        if tid == "PLAYER_LEVEL_SETTINGS":
            cpm = [round(x, 8) for x in e["data"]["playerLevel"]["cpMultiplier"][:BEST_BUDDY_LEVEL]]
        m = re.match(r"V(\d+)_POKEMON_", tid)
        ps = e.get("data", {}).get("pokemonSettings")
        if not (m and ps):
            continue
        st = ps.get("stats") or {}
        a, d, s = st.get("baseAttack"), st.get("baseDefense"), st.get("baseStamina")
        if None in (a, d, s):
            continue
        species = ps.get("pokemonId", "")
        raw_form = ps.get("form") or ""
        code = raw_form[len(species) + 1:] if raw_form.startswith(species + "_") else (raw_form or None)
        rec = {"tid": tid, "dex": int(m.group(1)), "species": species, "form": code,
               "atk": a, "def": d, "sta": s}
        by_tid[tid] = rec
        by_dex.setdefault(rec["dex"], []).append(rec)
    if not cpm:
        sys.exit("GAME_MASTER 缺 PLAYER_LEVEL_SETTINGS.cpMultiplier")

    def cp_at(r, level, iv=15):
        return max(10, int((r["atk"] + iv) * math.sqrt(r["def"] + iv) * math.sqrt(r["sta"] + iv)
                           * cpm[level - 1] ** 2 / 10))

    print("抓 APK 中文語系…", flush=True)
    d = get_json(I18N_URL)["data"]
    i18n = {d[i]: d[i + 1] for i in range(0, len(d) - 1, 2)}
    has_han = lambda s: bool(re.search(r"[一-鿿]", s or ""))

    print("列出 PokeMiners 圖示…", flush=True)
    sprites = sprite_filenames(token)
    print(f"  {len(sprites)} 個圖示檔")

    def zh_name(p, rec):
        """只修名稱裡的**英文**，其餘一律不動，回傳 None 表示維持原樣。

        本來想直接用 APK 重寫整個名稱，實測是錯的:APK 的形態字串是給遊戲介面用的完整說法，
        套進「XX (YY形態)」會變成「洛托姆 (旋轉洛托姆形態)」「酋雷姆 (闇黑酋雷姆形態)」，
        比原本的「電風扇形態」「闇黑形態」還糟;更嚴重的是有些形態 APK 根本沒有對應字串，
        整個重寫會讓「椰蛋樹 (阿羅拉形態)」掉成「椰蛋樹」、「南瓜精 (Small形態)」掉成「南瓜精」
        —— 弄丟辨識度還會跟基本型撞名(?mon=南瓜精 會變成兩隻搶同一個網址)。"""
        name = p["name"]
        if not re.search(r"[A-Za-z]", name):
            return None
        base = re.sub(r"\s*[(（].*", "", name).strip()
        g = re.search(r"[(（](.*?)[)）]", name)
        label = g.group(1) if g else None
        if re.search(r"[A-Za-z]", base):                      # 物種名是英文 → 換 APK 官方中文
            zh = i18n.get("pokemon_name_%04d" % rec["dex"])
            if has_han(zh):
                base = zh
        if label and re.search(r"[A-Za-z]", label):           # 形態標籤是英文 → APK,再退回自己的表
            code = (rec["form"] or re.sub(r"形態$", "", label)).upper()
            lab = None
            for key in (f"form_{rec['species'].lower()}_{code.lower()}", f"form_{code.lower()}"):
                if has_han(i18n.get(key)):
                    lab = i18n[key]; break
            if lab is None:
                lab = FORM_ZH_OVERRIDE.get(f"{rec['species']}_{code}")
            if lab is None:
                return None                                   # 補不出來就整列維持原樣,不要弄成半中半英
            lab = lab.strip()
            label = lab if lab.endswith(("形態", "模式", "尺寸", "臉", "樣子")) else lab + "形態"
        new = f"{base} ({label})" if label else base
        return new if new != name else None

    def image_url(rec):
        """挑這個形態的 GO 圖示。排除異色(.s.)、雌性(.g2.)、造型(.c…)。"""
        def ok(fn):
            return fn in sprites
        if rec["form"] and ok(f"pm{rec['dex']}.f{rec['form']}.icon.png"):
            return SPRITE_BASE + f"pm{rec['dex']}.f{rec['form']}.icon.png"
        if ok(f"pm{rec['dex']}.icon.png"):
            return SPRITE_BASE + f"pm{rec['dex']}.icon.png"
        # 連基本圖都帶 form 代碼 → 從該 dex 的純型態圖裡挑一個代表
        plain = sorted(fn for fn in sprites
                       if re.fullmatch(rf"pm{rec['dex']}\.f[A-Z0-9_]+\.icon\.png", fn))
        for pref in DEFAULT_FORMS:
            want = f"pm{rec['dex']}.f{pref}.icon.png"
            if want in plain:
                return SPRITE_BASE + want
        return SPRITE_BASE + plain[0] if plain else None

    text = open(SRC, encoding="utf-8").read()
    rows = ast.literal_eval(text[text.index("["):text.index("];") + 1])

    stat_chg, name_chg, img_chg, lost = [], [], [], []
    for p in rows:
        rec = by_tid.get(p.get("gm")) if p.get("gm") else None
        if rec is None:   # 第一次跑(或 GM 改了 templateId):用 CP 反查認人
            rec = next((r for r in by_dex.get(p["id"], [])
                        if all(cp_at(r, L) == p.get("cp%d" % L) for L in (15, 20, 25))), None)
        if rec is None:
            lost.append((p["id"], p["name"]))
            continue
        p["gm"] = rec["tid"]
        before = (p.get("atk"), p.get("def"), p.get("sta"))
        if before != (rec["atk"], rec["def"], rec["sta"]) and before != (None, None, None):
            stat_chg.append((p["name"], before, (rec["atk"], rec["def"], rec["sta"])))
        p["atk"], p["def"], p["sta"] = rec["atk"], rec["def"], rec["sta"]
        for L in (15, 20, 25):
            p["cp%d" % L] = cp_at(rec, L)

        nm = zh_name(p, rec)
        if nm and nm != p["name"]:
            name_chg.append((p["name"], nm))
            p["alt"] = p["name"]      # 舊名留著,讓既有的 ?mon= 連結還能用
            p["name"] = nm
        url = image_url(rec)
        if url and url != p.get("imageUrl"):
            img_chg.append(p["name"])
            p["imageUrl"] = url

    print(f"\n基礎數值有變動:{len(stat_chg)}")
    for n, a, b in stat_chg[:20]:
        print(f"   {n}:{a} → {b}")
    print(f"名稱有變動:{len(name_chg)}")
    for a, b in name_chg[:40]:
        print(f"   {a} → {b}")
    print(f"圖片有變動:{len(img_chg)}")
    # 圖片品質健檢:原本用 PokeAPI 的網址只認 dex，同一隻的各形態必然共用一張圖
    # (代歐奇希斯 4 個形態同一張)。換成 GO 圖示後這裡的「共用」筆數應該要明顯下降。
    from collections import Counter
    per_form = sum(1 for p in rows if re.search(r"\.f[A-Z0-9_]+\.icon\.png$", p.get("imageUrl") or ""))
    shared = sum(c for c in Counter(p.get("imageUrl") for p in rows).values() if c > 1)
    print(f"  形態專屬圖 {per_form} / 共用同一張圖的列 {shared} / 沒圖 "
          f"{sum(1 for p in rows if not p.get('imageUrl'))}")
    still_en = [p["name"] for p in rows if re.search(r"[A-Za-z]", p["name"])]
    print(f"名稱仍含英文:{len(still_en)}" + (f"  {still_en[:10]}" if still_en else ""))
    if lost:
        print(f"⚠ 對不到 GAME_MASTER 的 {len(lost)} 筆(保留原值):{lost[:10]}")

    if args.dry_run:
        print("\n--dry-run:沒有寫檔")
        return

    body = ", ".join("{" + ", ".join(f"'{k}': {json.dumps(v, ensure_ascii=False)}"
                                     for k, v in p.items()) + "}" for p in rows)
    out = (f"const POKEMON_CP_DATA = [{body}];\n"
           f"// 等級 → CP 倍率(GAME_MASTER PLAYER_LEVEL_SETTINGS.cpMultiplier,index = 等級-1)\n"
           f"// 索引 {MAX_LEVEL} 是最佳夥伴的 Lv{BEST_BUDDY_LEVEL}\n"
           f"const CP_MULTIPLIER = {json.dumps(cpm)};\n")
    open(SRC, "w", encoding="utf-8", newline="\n").write(out)
    print(f"\n已寫回 {os.path.relpath(SRC, ROOT)}  ({len(out)//1024} KB)")


if __name__ == "__main__":
    main()
