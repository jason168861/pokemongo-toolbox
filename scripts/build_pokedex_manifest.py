# ============================================================================
# 全寶可夢圖鑑 manifest 產生器
# 掃描本地 PokeMiners 圖片檔名 → 解析出每隻寶可夢的所有變體（造型/服裝/性別/異色）
# → 併入官方繁中名（holoholo-text）→ 輸出 data/pokedex_manifest.json。
#
# 圖片不進 repo，前端改用 jsDelivr CDN 直連 PokeMiners（見 IMAGE_BASE）。
# 本地目錄只當「產生清單的來源」，用來確認哪些圖真的存在。
#
# 檔名規則：pm{全國編號}[.f{造型}][.c{服裝}][.g{性別}][.s].icon.png
# 執行：在 repo 根目錄  python scripts/build_pokedex_manifest.py
# ============================================================================

import os
import re
import json
import requests

LOCAL_DIR = r"C:\Users\qian\Desktop\poke_web\pogo_assets\Images\Pokemon - 256x256\Addressable Assets"
IMAGE_BASE = "https://cdn.jsdelivr.net/gh/PokeMiners/pogo_assets@master/Images/Pokemon%20-%20256x256/Addressable%20Assets/"
OUTPUT = "./data/pokedex_manifest.json"
REPORT = "./scripts/pokedex_untranslated_forms.json"

HOLO_EN = "https://raw.githubusercontent.com/sora10pls/holoholo-text/refs/heads/main/Release/English/en-us_raw.json"
HOLO_ZHT = "https://raw.githubusercontent.com/sora10pls/holoholo-text/refs/heads/main/Release/Traditional%20Chinese/zh-tw_raw.json"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# 屬性代碼 → 中文（阿爾宙斯、多龍巴魯托系列等的屬性 form）
TYPE_ZH = {
    "NORMAL": "一般", "FIRE": "火", "WATER": "水", "GRASS": "草", "ELECTRIC": "電",
    "ICE": "冰", "FIGHTING": "格鬥", "POISON": "毒", "GROUND": "地面", "FLYING": "飛行",
    "PSYCHIC": "超能力", "BUG": "蟲", "ROCK": "岩石", "GHOST": "幽靈", "DRAGON": "龍",
    "DARK": "惡", "STEEL": "鋼", "FAIRY": "妖精",
}

# 通用造型代碼 → 中文（官方沒有單一 key 或需要固定用詞的，手動指定）
FORM_MANUAL = {
    "ALOLA": "阿羅拉", "ALOLAN": "阿羅拉", "GALARIAN": "伽勒爾", "GALAR": "伽勒爾",
    "HISUIAN": "洗翠", "HISUI": "洗翠", "PALDEAN": "帕底亞", "PALDEA": "帕底亞",
    "MEGA": "Mega", "MEGA_X": "Mega X", "MEGA_Y": "Mega Y",
    "GIGANTAMAX": "超極巨化", "GMAX": "超極巨化", "ETERNAMAX": "無極巨化",
    "PRIMAL": "原始回歸", "INCARNATE": "化身形態", "THERIAN": "靈獸形態",
    "ORIGIN": "起源形態", "ALTERED": "別種形態",
    "ATTACK": "攻擊形態", "DEFENSE": "防禦形態", "SPEED": "速度形態",
    # 蓑衣蟲 / 結草貴婦
    "PLANT": "草木蓑衣", "SANDY": "砂土蓑衣", "TRASH": "垃圾蓑衣",
    "WORMADAM_PLANT": "草木蓑衣", "WORMADAM_SANDY": "砂土蓑衣", "WORMADAM_TRASH": "垃圾蓑衣",
    "OVERCAST": "陰天", "SUNSHINE": "太陽", "EAST_SEA": "東海", "WEST_SEA": "西海",
    "FEMALE": "♀", "MALE": "♂", "A": "覺醒", "COPY_2019": "仿造",
    # 堅盾劍怪 / 蒼響 / 藏瑪然特
    "BLADE": "刀劍形態", "SHIELD": "盾牌形態", "STANDARD": "一般",
    "HERO": "百戰勇者", "CROWNED_SWORD": "劍王", "CROWNED_SHIELD": "盾王",
    # 火焰雞? 達摩狒狒
    "ZEN": "達摩模式", "GALARIAN_STANDARD": "伽勒爾一般", "GALARIAN_ZEN": "伽勒爾達摩模式",
    # 奈克洛茲瑪
    "DUSK_MANE": "黃昏之鬃", "DAWN_WINGS": "拂曉之翼", "ULTRA": "究極",
    # 基格爾德
    "COMPLETE": "完全體形態", "FIFTY_PERCENT": "50% 形態", "TEN_PERCENT": "10% 形態",
    # 胡帕 / 莫魯貝可 / 謎擬Q / 顫弦蠑螈 / 磁石魚
    "UNBOUND": "解放形態", "CONFINED": "懲戒形態",
    "FULL_BELLY": "滿腹模式", "HANGRY": "空腹模式",
    "BUSTED": "破魂之形", "DISGUISED": "化形",
    "AMPED": "高調的樣子", "LOW_KEY": "低調的樣子",
    "SOLO": "單獨的樣子", "SCHOOL": "魚群的樣子",
    # 南瓜精 / 吼吼鯨等大小
    "SMALL": "小尺寸", "AVERAGE": "普通尺寸", "LARGE": "大尺寸", "SUPER": "特大尺寸",
}

# 活動服裝被編成 form 的前綴/樣式：統一歸「特殊造型」，不逐一翻年份
COSTUME_FORM_RE = re.compile(
    r"(^\d+$)|(\d{4})|^(GOFEST|GOTOUR|WCS|WILDAREA|ADVENTURE|ANNIVERSARY|DIWALI|"
    r"COSTUME|TSHIRT|VISOR|SWIM|VS|FOSSIL|COIN|BB|POP_STAR|ROCK_STAR|FLYING_5TH|"
    r"FLYING_OKINAWA|SPRING|SUMMER|WINTER|FALL|HALLOWEEN|HOLIDAY)")


def load_holo(url):
    d = requests.get(url, headers=HEADERS, timeout=60).json()["data"]
    return dict(zip(d[0::2], d[1::2]))


def build_translators():
    en = load_holo(HOLO_EN)
    zht = load_holo(HOLO_ZHT)

    def name_zh(dex):
        return zht.get("pokemon_name_%04d" % dex)

    forms = {"_missing": set()}

    def form_zh(code):
        if not code:
            return None
        if code in FORM_MANUAL:
            return FORM_MANUAL[code]
        if code in TYPE_ZH:
            return TYPE_ZH[code] + "屬性"
        if code.startswith("UNOWN_"):
            return "未知圖騰 " + code.split("_", 1)[1].replace("_", " ")
        # holoholo 的 form_{小寫代碼}（THERIAN→form_therian 之類）
        for key in ("form_" + code.lower(),
                    "pokedex_info_form_" + code.lower()):
            if key in zht and zht[key] != en.get(key):
                return zht[key]
        # 活動服裝類 → 統一歸「特殊造型」
        if COSTUME_FORM_RE.search(code):
            return "特殊造型"
        forms["_missing"].add(code)
        return None

    return name_zh, form_zh, forms


def parse_filename(fn):
    m = re.match(r"^pm(\d+)(?:\.f([A-Za-z0-9_]+))?(?:\.c([A-Za-z0-9_]+))?"
                 r"(?:\.g(\d))?(\.s)?\.icon\.png$", fn)
    if not m:
        return None
    dex, form, costume, gender, shiny = m.groups()
    return {
        "dex": int(dex),
        "form": form,
        "costume": costume.upper() if costume else None,
        "gender": int(gender) if gender else None,
        "shiny": bool(shiny),
        "file": fn,
    }


def prettify_costume(code):
    """服裝代碼美化，讓不同活動服裝能區分：HOLIDAY_2022 → Holiday 2022"""
    return code.replace("_NOEVOLVE", "").replace("_", " ").title()


def make_label(v, form_zh):
    """組出人看得懂的變體標籤，如「Mega X」「服裝 Holiday 2022」「阿羅拉 ♀」"""
    parts = []
    if v["form"]:
        parts.append(form_zh(v["form"]) or v["form"])
    if v["costume"]:
        parts.append("服裝 " + prettify_costume(v["costume"]))
    if v["gender"] == 2:
        parts.append("♀")
    elif v["gender"] == 1:
        parts.append("♂")
    return " · ".join(parts) if parts else "一般"


def main():
    print("⏳ 載入官方繁中文本…")
    name_zh, form_zh, forms = build_translators()

    print("⏳ 掃描本地圖片檔名…")
    files = [f for f in os.listdir(LOCAL_DIR) if f.endswith(".icon.png")]
    by_dex = {}
    skipped = []
    for fn in files:
        v = parse_filename(fn)
        if not v:
            skipped.append(fn)
            continue
        by_dex.setdefault(v["dex"], []).append(v)

    pokemon = []
    for dex in sorted(by_dex):
        variants = by_dex[dex]
        # 排序：一般在前 → 造型（Mega 等）→ 服裝排最後；各自的異色緊跟在本體後
        variants.sort(key=lambda v: (
            bool(v["costume"]), bool(v["form"]), v["form"] or "",
            v["costume"] or "", v["gender"] or 0, v["shiny"]))
        out_variants = []
        for v in variants:
            out_variants.append({
                "label": make_label(v, form_zh),
                "file": v["file"],
                "shiny": v["shiny"],
                "form": v["form"],
                "costume": v["costume"],
                "gender": v["gender"],
            })
        pokemon.append({
            "dex": dex,
            "name": name_zh(dex) or ("#%d" % dex),
            "variants": out_variants,
            # 方便前端做「有無異色 / 有無 Mega / 有無服裝」篩選的快速旗標
            "hasShiny": any(v["shiny"] for v in variants),
            "hasMega": any(v["form"] and "MEGA" in v["form"] for v in variants),
            "hasCostume": any(v["costume"] for v in variants),
        })

    manifest = {
        "imageBase": IMAGE_BASE,
        "count": len(pokemon),
        "variantCount": sum(len(p["variants"]) for p in pokemon),
        "pokemon": pokemon,
    }
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = os.path.getsize(OUTPUT) / 1024
    print(f"\n🎉 完成！{len(pokemon)} 隻寶可夢、{manifest['variantCount']} 個變體 "
          f"→ {OUTPUT}（{size_kb:.0f} KB）")
    if skipped:
        print(f"⚠️ {len(skipped)} 個檔名無法解析：{skipped[:5]}")

    missing = sorted(forms["_missing"])
    if missing:
        with open(REPORT, "w", encoding="utf-8") as f:
            json.dump(missing, f, ensure_ascii=False, indent=2)
        print(f"📝 {len(missing)} 種造型代碼查不到官方中文（暫顯示英文代碼），"
              f"清單見 {REPORT}")
    else:
        print("✅ 所有造型都有中文。")


if __name__ == "__main__":
    main()
