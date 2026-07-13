import os
import requests
import json
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ==================== 翻譯資料區塊 START ====================

# 【修改點 1】擴充翻譯字典，並更名為更通用的 GENERAL_TRANSLATIONS
# (此區塊保持不變)
GENERAL_TRANSLATIONS = {
    # 寶可夢形態
    'Alolan': '阿羅拉', 'Galarian': '伽勒爾', 'Hisuian': '洗翠', 'Origin': '起源',
    'Altered': '別種', 'Attack': '攻擊', 'Defense': '防禦', 'Speed': '速度',
    'Sunny': '太陽', 'Rainy': '雨水', 'Snowy': '雪雲', 'Overcast': '陰天',
    'Incarnate': '化身', 'Therian': '靈獸', 'Black': '闇黑', 'White': '焰白',
    'Plant': '草木', 'Sandy': '砂土', 'Trash': '垃圾', 'Confined': '懲戒', 'Unbound': '解放',
    'Aria': '歌聲', 'Pirouette': '舞步', 'Fan': '電風扇', 'Frost': '結冰', 'Heat': '加熱', 'Mow': '割草', 'Wash': '清洗',
    'Dusk': '黃昏', 'Midday': '白晝', 'Midnight': '黑夜', 'School': '魚群', 'Solo': '單獨', 'Dawn Wings': '日蝕奈克洛茲瑪', 'Ultra': '究極',
    'Hero': '百戰勇者', 'White Striped': '白條紋','Paldean':'帕底亞',
    
    # 道具 & 資源
    'Stardust': '星星沙子',
    'Rare Candy': '神奇糖果',
    'Rare Candy XL': '神奇糖果XL',
    'Golden Razz Berry': '金莓果',
    'Razz Berry': '蔓莓果',
    'Poffin': '寶芬',
    'Silver Pinap Berry': '銀色凰梨果',
    'Pinap Berry': '凰梨果',
    'Ultra Ball': '高級球',
    'Great Ball': '超級球',
    'Poké Ball': '精靈球',
    'Sinnoh Stone': '神奧之石',
    'Unova Stone': '合眾之石',
    'Mega Energy': '超級能量', # 用於組合，例如 "妙蛙花 超級能量"
            'Stardust': '星星沙子', 'XP': 'XP', 'Poke Ball': '精靈球',
        'Great Ball': '超級球', 'Ultra Ball': '高級球', 'Egg Incubator': '孵化器',
        'Super Incubator': '超級孵化器', 'Lure Module': '誘餌模組',
        'Star Piece': '星星碎片','Star piece': '星星碎片', 'Premium Raid Pass': '特級對戰入場券',
        'Lucky Egg': '幸運蛋', 'Revive': '活力碎片', 'Rare Candy': '神奇糖果',
        'Kings Rock': '王者之證', 'Metal Coat': '金屬膜',
        'Up-Grade': '升級資料', 'Dragon Scale': '龍之鱗片',
        'Silver Pinap Berry': '銀色凰梨果', 'Encounter': '遭遇', 'Candy': '的糖果',
        'Kanto': '關都地區', 'Johto': '城都地區', 'Hoenn': '豐緣地區', 'Sinnoh': '神奧地區',
        'Unova Stone': '合眾之石', 'Shiny':'異色','Sinnoh Stone': '神奧之石',
        'Unova': '合眾地區', 'Kalos': '卡洛斯地區', 'Alola': '阿羅拉地區', 'Galar': '伽勒爾地區',
        'silver': '銀牌', 'gold': '金牌', 'platinum': '白金獎牌',
        'Gold Unova Medal': '合眾地區金牌', 'Platinum Kanto Medal': '關都地區白金獎牌',
        'Platinum Idol Medal': '白金偶像獎牌', 'Bronze Showcase Star Medal': '選秀會新星銅牌',
        'Arlo': '亞洛', 'Cliff': '克里夫', 'Sierra': '希爾拉',
        'Team GO Rocket Grunts': 'GO火箭隊手下', 'Team GO Rocket Grunt': 'GO火箭隊手下',
        'Team GO Rocket members': 'GO火箭隊手下', 'Team GO Rocket member': 'GO火箭隊手下',
        'Team GO Rocket Leader': 'GO火箭隊幹部', 'Team GO Rocket Boss': 'GO火箭隊老大',
        'Team GO Rocekt Leader Arlo': 'GO火箭隊幹部亞洛', 'Team GO Rocekt Leader Cliff': 'GO火箭隊幹部克里夫',
        'Team GO Rocekt Leader Sierra': 'GO火箭隊幹部希爾拉',
        'Team GO Rocket Leader Arlo/Cliff/Sierra': 'GO火箭隊幹部亞洛、克里夫或希爾拉',
        'Jessie or James': '潔西或詹姆斯', 'Nice': 'Nice', 'Great': 'Great',
        'Excellent': 'Excellent', 'Curveball': '曲球', 'Day': '白天', 'night': '晚上',
        'Sun Stone': '日之石', 'Incense': '薰香', 'Daily Adventure Incense': '每日冒險薰香',
        'Berries': '莓果', 'Berry': '莓果', 'Pinap Berries': '凰梨果', 'Pinap Berry': '凰梨果',
        'Razz Berries': '蔓莓果', 'Razz Berry': '蔓莓果', 'Golden Razz Berries': '金色蔓莓果',
        'Golden Razz Berry': '金色蔓莓果', 'Fast TM': '一般招式學習器','Elite Fast TM':'厲害一般招式學習器','Elite Charged TM': '厲害特殊招式學習器',
        'Charged TM': '特殊招式學習器', 'Charge TM': '特殊招式學習器', 'Great League': '超級聯盟',
        'Ultra League': '高級聯盟', 'Master League': '大師聯盟', 'GO Battle League': 'GO對戰聯盟',
        'Primal Reversion': '原始回歸', 'Primal Raid': '原始團體戰', 'Mega Evolve': '超級進化',
        'Mega Raid': '超級團體戰', 'Routes': '路線', 'Route': '路線',
        'Zygarde Cell': '基格爾德・細胞', 'Mateo': 'マテオ', 'Max Move': '極巨招式',
        'Max Particles': '究極能量', 'Max Battle': '極巨化對戰', 'Shadow Raids': '暗影團體戰',
        'Shadow Raid': '暗影團體戰', 'Party Challenges': '小隊挑戰',
        'Diamond Badge': '鑽石徽章', 'Pearl Badge': '珍珠徽章','Super Rocket Radar':'超級火箭隊雷達','Max Revive': '活力塊','Rocket Radar': '火箭隊雷達','Upgrade': '升級資料',
        'Mossy':'香草', 'Glacial':'冰寒', 'Magnetic':'磁鐵', 'Rainy':'雨露','Sticker': '貼圖', 'and': '和','Premium Battle Pass': '特級對戰入場券','Pose' : '姿勢',
        'Hyper Potion':'厲害傷藥','Super Potion':'好傷藥','Max Potion':'全滿藥','Potion':'傷藥','Mega Energy':'超級能量','Mysterious Component':'神秘零件',
        'Meteorite': '隕石','Poffin': '寶芬','Apex Shadow':'暗影至尊','Shadow':'暗影','Dynamax':'極巨化','Nanab berry': '蕉香果','Nanab Berry': '蕉香果',
        'Max Particle Pack':'極巨粒子組合','Max Particle':'極巨粒子','Crowned Sword Energy':'劍王能量','Crowned Shield Energy':'盾王能量','Max Mushroom': '極巨菇菇',
        'Blaze Fusion Energy':"火焰能量",'Volt Fusion Energy':'電壓能量','Poke ball':'精靈球','Flabébé':'花蓓蓓','Origin Dialga':'起源帝牙盧卡','Origin Palkia':'起源帕路奇亞',
        'Origin Giratina':'起源騎拉帝納','GreatBall':'超級球','Primal Energy':'原始能量','Master Ball':'大師球','star Piece':'星星碎片',
        'Solar Fusion Energy':'太陽能量','Lunar Fusion Energy':'月亮能量',
}

# ==================== 官方在地化文本（主要翻譯來源）====================
# 一勞永逸的關鍵：Pokémon GO 遊戲本身就有官方繁中翻譯。
# PokeMiners 每日 dump 遊戲文字資源，這裡下載「英文 ↔ 繁體中文」對照，
# 自動翻譯任務句型、道具與寶可夢名稱：
#   - 精確對照：沒有佔位符的字串（道具名、寶可夢名、單數任務句）
#   - 句型模板：帶 {0} 佔位符的任務句（如 "Catch {0} Pokémon" → "捕捉 {0} 隻寶可夢"）
# 【優先順序】官方文本優先；上方的手動字典只在官方查不到時後援
# （例如 LeekDuck 自創的造型寶可夢描述名）。
# 兩邊都查不到的字串會寫入 scripts/untranslated_report.json 供人工檢查。

# 文字來源（依序載入合併，後面的來源覆蓋前面）：
#   holoholo-text：最完整的官方遊戲文字 dump（含活動/特殊調查字串），持續更新。
#   格式標記：'txt' = PokeMiners 的 RESOURCE ID/TEXT 格式；'json' = {"data": [k,v,k,v,…]}
POGO_TEXT_SOURCES = [
    ("json",
     "https://raw.githubusercontent.com/sora10pls/holoholo-text/refs/heads/main/Release/English/en-us_raw.json",
     "https://raw.githubusercontent.com/sora10pls/holoholo-text/refs/heads/main/Release/Traditional%20Chinese/zh-tw_raw.json"),
    # Remote＝遠端下發的活動字串（活動限定的特殊調查標題/任務常只在這裡）
    ("json",
     "https://raw.githubusercontent.com/sora10pls/holoholo-text/refs/heads/main/Remote/English/en-us_raw.json",
     "https://raw.githubusercontent.com/sora10pls/holoholo-text/refs/heads/main/Remote/Traditional%20Chinese/zh-tw_raw.json"),
]

_OFFICIAL = {"exact": {}, "loose": {}, "templates": []}
_UNTRANSLATED = set()

def _parse_pogo_text(raw):
    """解析 PokeMiners 的文字格式：RESOURCE ID: / TEXT: 交替出現，支援多行文本"""
    data = {}
    key = None
    last_key = None
    for line in raw.splitlines():
        if line.startswith("RESOURCE ID: "):
            key = line[13:].strip()
            last_key = None
        elif line.startswith("TEXT: ") and key:
            data[key] = line[6:].strip()
            last_key = key
            key = None
        elif last_key and line.strip():
            data[last_key] += " " + line.strip()  # 多行文本的後續行
    return data

def _normalize_text(s):
    """統一彎引號/不換行空格等差異，讓 LeekDuck 文字能對上官方文本"""
    return s.replace(" ", " ").replace("’", "'").replace("‘", "'").strip()

def _parse_pogo_json(raw):
    """解析 holoholo-text 的 JSON 格式：{"data": [key, value, key, value, …]}"""
    data = json.loads(raw)["data"]
    return dict(zip(data[0::2], data[1::2]))

def build_official_translation_db():
    """下載並建立官方英繁對照庫。下載失敗時退回純手動字典模式。"""
    en_map, zht_map = {}, {}
    for fmt, en_url, zht_url in POGO_TEXT_SOURCES:
        parse = _parse_pogo_json if fmt == "json" else _parse_pogo_text
        try:
            en_map.update(parse(requests.get(en_url, headers=HEADERS, timeout=60).text))
            zht_map.update(parse(requests.get(zht_url, headers=HEADERS, timeout=60).text))
        except Exception as e:
            print(f"⚠️ 無法下載官方文本 {en_url.split('/')[-1]}（{e}），略過此來源。")
    if not en_map:
        print("⚠️ 官方文本全數下載失敗，本次僅使用手動字典。")
        return
    ph_re = re.compile(r"\{(\d+)\}")

    for key, en_text in en_map.items():
        zh_text = zht_map.get(key)
        if not zh_text or zh_text == en_text:
            continue  # 該鍵沒有中文翻譯
        en_norm = _normalize_text(en_text)
        placeholders = ph_re.findall(en_norm)
        if placeholders:
            # 太通用的模板（如 "{0}s"、"{0} {1}"）幾乎什麼都能配到，會把
            # 真正的未知字串誤翻，要求字面文字至少 8 字元才收錄
            if len(ph_re.sub("", en_norm)) < 8:
                continue
            # 帶佔位符 → 轉成正則模板；記下佔位符出現順序供代回中文
            pattern = re.escape(en_norm)
            for n in set(placeholders):
                pattern = pattern.replace(re.escape("{%s}" % n), "(.+?)")
            _OFFICIAL["templates"].append(
                (re.compile("^" + pattern + "$", re.IGNORECASE), zh_text, placeholders, len(en_norm))
            )
        else:
            _OFFICIAL["exact"].setdefault(en_norm.lower(), zh_text)
            # 寬鬆索引：去掉標點/空白，容忍來源網站與遊戲內的細微差異
            # （如 "Chill Out, Frigibax" vs 官方 "Chill Out, Frigibax!"）。
            # 只收較長字串，避免短字串誤配。
            lk = re.sub(r"[^a-z0-9]", "", en_norm.lower())
            if len(lk) >= 8:
                _OFFICIAL["loose"].setdefault(lk, zh_text)

    # 長模板優先比對（字面文字越長越精確，避免被短模板搶先誤配）
    _OFFICIAL["templates"].sort(key=lambda t: -t[3])
    print(f"✅ 官方文本載入完成：{len(_OFFICIAL['exact'])} 條精確對照、{len(_OFFICIAL['templates'])} 個句型模板")

def official_translate(text):
    """用官方文本翻譯，找不到回傳 None"""
    if not text:
        return None
    t = _normalize_text(text)
    hit = _OFFICIAL["exact"].get(t.lower())
    if hit:
        return hit
    # 寬鬆比對：去標點/空白後再試，並容忍尾端複數 s 的差異
    lk = re.sub(r"[^a-z0-9]", "", t.lower())
    if len(lk) >= 8:
        hit = _OFFICIAL["loose"].get(lk) \
            or (_OFFICIAL["loose"].get(lk[:-1]) if lk.endswith("s") else _OFFICIAL["loose"].get(lk + "s"))
        if hit:
            return hit
    for regex, zh_tmpl, placeholders, _ in _OFFICIAL["templates"]:
        m = regex.match(t)
        if m:
            out = zh_tmpl
            for i, n in enumerate(placeholders):
                val = m.group(i + 1)
                # 代入值本身可能還是英文（如 "Charizard Mega Energy" 捕到 "Charizard"），
                # 先查一次精確對照把它翻成中文；數字等查不到就原樣代入
                val = _OFFICIAL["exact"].get(_normalize_text(val).lower(), val)
                out = out.replace("{%s}" % n, val)
            return out
    return None

def record_untranslated(text):
    _UNTRANSLATED.add(text)
    return text

# 組合式翻譯規則：官方文本沒有的「參數化句型」（活動限定字串常見），
# 把屬性/地區/寶可夢名當參數代換，一條規則涵蓋一整族句子。
POKEMON_TYPES_ZH = {
    'Normal': '一般', 'Fire': '火', 'Water': '水', 'Grass': '草', 'Electric': '電',
    'Ice': '冰', 'Fighting': '格鬥', 'Poison': '毒', 'Ground': '地面', 'Flying': '飛行',
    'Psychic': '超能力', 'Bug': '蟲', 'Rock': '岩石', 'Ghost': '幽靈', 'Dragon': '龍',
    'Dark': '惡', 'Steel': '鋼', 'Fairy': '妖精',
}
REGIONS_ZH = {
    'Kanto': '關都', 'Johto': '城都', 'Hoenn': '豐緣', 'Sinnoh': '神奧', 'Unova': '合眾',
    'Kalos': '卡洛斯', 'Alola': '阿羅拉', 'Galar': '伽勒爾', 'Hisui': '洗翠', 'Paldea': '帕底亞',
}
CITIES_ZH = {
    'Amsterdam': '阿姆斯特丹', 'Bangkok': '曼谷', 'Buenos Aires': '布宜諾斯艾利斯',
    'Cancun': '坎昆', 'Miami': '邁阿密', 'Sydney': '雪梨', 'Valencia': '瓦倫西亞',
    'Vancouver': '溫哥華', 'Tokyo': '東京', 'Chicago': '芝加哥', 'Copenhagen': '哥本哈根',
    'Nagasaki': '長崎', 'Taipei': '台北', 'New Taipei City': '新北', 'Seoul': '首爾',
    'Barcelona': '巴塞隆納', 'Mexico City': '墨西哥城', 'Singapore': '新加坡',
}

def _count_zh(s):
    return '1' if s.lower() in ('a', 'an') else s

def compose_translate(task_text):
    """規則組合翻譯，翻不出來回傳 None"""
    m = re.match(r'^Earn (\d+) hearts? with an? ([A-Za-z]+)-type buddy$', task_text, re.IGNORECASE)
    if m:
        t = POKEMON_TYPES_ZH.get(m.group(2).capitalize())
        if t:
            return f'將{t}屬性的寶可夢設成夥伴，並和牠獲得{m.group(1)}顆心心'
    m = re.match(r'^Catch (an?|\d+) Pokémon originally discovered in the ([A-Za-z]+) region$',
                 task_text, re.IGNORECASE)
    if m:
        r = REGIONS_ZH.get(m.group(2).capitalize())
        if r:
            return f'捕捉 {_count_zh(m.group(1))} 隻最初發現於{r}地區的寶可夢'
    # "Catch a Scatterbug" / "Catch 3 Scatterbug"：後半段翻得出寶可夢名才成立
    m = re.match(r'^Catch (an?|\d+) (.+)$', task_text)
    if m:
        name = official_translate(m.group(2))
        if name:
            return f'捕捉 {_count_zh(m.group(1))} 隻{name}'
    # "Explore 2km"（官方模板要求 km 前有空格，這裡容忍無空格寫法）
    m = re.match(r'^Explore (\d+)\s*km$', task_text, re.IGNORECASE)
    if m:
        return f'探索 {m.group(1)} 公里'
    m = re.match(r'^Use an? ([A-Za-z]+)-type Charged Attack in (\d+) battles?$', task_text, re.IGNORECASE)
    if m:
        t = POKEMON_TYPES_ZH.get(m.group(1).capitalize())
        if t:
            return f'在 {m.group(2)} 場對戰中使出{t}屬性的特殊招式'
    m = re.match(r'^Earn a Candy exploring with an? ([A-Za-z]+) type as your buddy$', task_text, re.IGNORECASE)
    if m:
        t = POKEMON_TYPES_ZH.get(m.group(1).capitalize())
        if t:
            return f'和{t}屬性的夥伴寶可夢一起走路獲得 1 顆糖果'
    m = re.match(r'^Power up ([A-Za-z]+) Pokémon (\d+) times$', task_text, re.IGNORECASE)
    if m:
        t = POKEMON_TYPES_ZH.get(m.group(1).capitalize())
        if t:
            return f'強化{t}屬性的寶可夢 {m.group(2)} 次'
    # City Safari 城市限定任務
    m = re.match(r'^Spin an? PokéStops? or Gyms? in (.+)$', task_text, re.IGNORECASE)
    if m and m.group(1) in CITIES_ZH:
        return f'在{CITIES_ZH[m.group(1)]}轉動補給站或道館的轉盤'
    m = re.match(r'^Take a Snapshot of your Eevee in (.+)$', task_text, re.IGNORECASE)
    if m and m.group(1) in CITIES_ZH:
        return f'在{CITIES_ZH[m.group(1)]}為你的伊布拍攝 1 張 GO Snapshot 照片'
    return None

# ==================== 官方在地化文本 END ====================

def load_json_map(filename):
    """通用函式，用於載入 JSON 格式的翻譯檔"""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"📄 提示：找不到可選的翻譯檔 {filename}。")
        return {}
    except json.JSONDecodeError:
        print(f"❌ 錯誤：{filename} 格式有誤。")
        return {}

def translate_name(eng_name, name_map, form_map):
    """將寶可夢英文名稱翻譯成中文：官方文本優先，手動字典後援"""
    if not eng_name:
        return eng_name

    # 官方文本優先（涵蓋所有寶可夢的官方繁中名）
    official = official_translate(eng_name)
    if official:
        return official

    form_in_parentheses_match = re.match(r'(.+?)\s*\((.+?)\)', eng_name)
    if form_in_parentheses_match:
        base_name, form_name = form_in_parentheses_match.groups()
        base_name, form_name = base_name.strip(), form_name.strip()
        if base_name in name_map and form_name in form_map:
            return f"{name_map[base_name]} ({form_map[form_name]})"

    parts = eng_name.split()
    if len(parts) == 2 and parts[0] == 'Spinda' and parts[1].isdigit():
        return f"晃晃斑 {parts[1]} 號"

    if len(parts) > 1 and parts[0] in form_map:
        form_name = parts[0]
        base_name = " ".join(parts[1:])
        if base_name in name_map:
            return f"{form_map[form_name]} {name_map[base_name]}"

    if eng_name in name_map:
        return name_map[eng_name]

    return record_untranslated(eng_name)

# ==================================================================
#                    【⭐️ 這裡是修正的核心 ⭐️】
# 將下方的 translate_item_resource 函式替換掉您原本的函式
# ==================================================================
def translate_item_resource(eng_name, general_map, pokemon_map):
    """翻譯道具、資源：官方文本優先，手動字典後援。"""
    # 官方文本優先：先試完整字串，再試剝掉尾端數量（例如 " ×1500"）
    official = official_translate(eng_name)
    if official:
        return official
    qty_match = re.match(r"^(.*?)\s*([×x]\s*[\d,]+)$", eng_name)
    if qty_match:
        base, qty = qty_match.groups()
        official = official_translate(base.strip())
        if official:
            return f"{official} {qty}"

    # 超級能量組合字，例如 "Venusaur Mega Energy"（官方沒有這種合成字串）
    mega_energy_match = re.match(r'(.+?)\s+Mega Energy', eng_name)
    if mega_energy_match:
        pokemon_name = mega_energy_match.group(1).strip()
        translated_pokemon = official_translate(pokemon_name) or pokemon_map.get(pokemon_name, pokemon_name)
        translated_mega_energy = general_map.get('Mega Energy', 'Mega Energy')
        return f"{translated_pokemon} {translated_mega_energy}"

    # 按長度降序排序字典鍵，以優先匹配更長的名稱
    # 例如，確保 "Golden Razz Berry" 比 "Razz Berry" 先被匹配
    sorted_item_keys = sorted(general_map.keys(), key=len, reverse=True)

    for item_key in sorted_item_keys:
        # 檢查傳入的英文名是否以字典中的某個鍵（道具名）開頭
        if eng_name.startswith(item_key):
            # 如果是，則找到了我們的道具
            # 取得道具名稱後面的剩餘部分（通常是數量，例如 " ×1500"）
            remaining_part = eng_name[len(item_key):].strip()
            
            # 翻譯道具名稱
            translated_item = general_map[item_key]
            
            # 將翻譯後的名稱與剩餘的數量部分重新組合
            return f"{translated_item} {remaining_part}".strip()
            
    # 官方與手動字典都查不到，記錄下來供人工檢查
    return record_untranslated(eng_name)

def translate_task_description(task_text, task_map):
    """翻譯田野調查任務：官方句型模板優先，手動字典與規則後援。"""
    official = official_translate(task_text)
    if official:
        return official

    if task_text in task_map:
        return task_map[task_text]

    curveball_match = re.match(
        r'^Make (an? |\d+ )?(Nice|Great|Excellent)? ?(Curveball )?Throws(?: in a row)?$',
        task_text
    )
    if curveball_match:
        count_part = curveball_match.group(1) or '1 '
        throw_type = curveball_match.group(2) or ''
        is_curveball = curveball_match.group(3) is not None
        in_a_row = 'in a row' in task_text

        count = count_part.replace('an ', '1 ').replace('a ', '1 ').strip()
        translated_throw_type = throw_type.strip()
        if is_curveball:
            translated_throw_type = f"{translated_throw_type} 曲球".strip()

        if in_a_row:
            return f"連續投出 {count} 次 {translated_throw_type}".replace('  ', ' ').strip()
        return f"投出 {count} 次 {translated_throw_type}".replace('  ', ' ').strip()

    composed = compose_translate(task_text)
    if composed:
        return composed

    return record_untranslated(task_text)

# ==================== 翻譯資料區塊 END ======================

URL = "https://leekduck.com/research/"
BASE_URL = "https://leekduck.com/"
HEADERS = { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36" }

def scrape_research_data_full():
    pokemon_name_map = load_json_map("./data/pokemon_translation_map.json")
    task_translation_map = load_json_map("./scripts/task_translation_map.json")
    category_translation_map = load_json_map("./scripts/category_translation_map.json") # <-- 新增此行

    build_official_translation_db()   # 官方英繁對照庫（自動翻譯後援）

    print("⏳ 正在從 LeekDuck 的田野調查頁面抓取資料...")
    response = requests.get(URL, headers=HEADERS)
    response.raise_for_status()
    print("✅ 成功取得網頁內容！")

    soup = BeautifulSoup(response.text, "lxml")
    
    research_data = []
    task_categories = soup.find_all("div", class_="task-category")

    for category in task_categories:
        category_title_eng = category.find("h2").text.strip()
        translated_category = category_translation_map.get(category_title_eng, category_title_eng)

        category_data = {
            "category": translated_category,
            "tasks": []
        }
        print(f"🔍 正在處理分類：{translated_category}")

        for task_item in category.find_all("li", class_="task-item"):
            task_text_span = task_item.find("span", class_="task-text")
            if not task_text_span: continue
            
            task_description = task_text_span.text.strip()
            translated_task = translate_task_description(task_description, task_translation_map)

            task_data = {
                "description": translated_task,
                "rewards": []
            }
            
            reward_list = task_item.find("ul", class_="reward-list")
            if not reward_list: continue

            for reward_li in reward_list.find_all("li", class_="reward", recursive=False):
                reward_info = {}
                reward_type = reward_li.get("data-reward-type")
                
                reward_info['isFeatured'] = reward_li.get("data-reward-filter") == "less"
                
                if reward_type == "encounter":
                    reward_info['type'] = 'encounter'
                    name = reward_li.find("span", class_="reward-label").find("span").text.strip()
                    reward_info['name'] = translate_name(name, pokemon_name_map, GENERAL_TRANSLATIONS)
                    reward_info['imageUrl'] = urljoin(BASE_URL, reward_li.find("img", class_="reward-image")['src'])
                    reward_info['isShiny'] = reward_li.find("img", class_="shiny-icon") is not None
                    
                    max_cp_tag = reward_li.find("span", class_="max-cp")
                    min_cp_tag = reward_li.find("span", class_="min-cp")
                    reward_info['maxCp'] = max_cp_tag.text.replace('Max CP', '').strip() if max_cp_tag else None
                    reward_info['minCp'] = min_cp_tag.text.replace('Min CP', '').strip() if min_cp_tag else None
                
                elif reward_type in ["item", "resource"]:
                    # 將所有資訊都填入 reward_info，但不在此處 append
                    reward_info['type'] = 'item'
                    reward_info['pokemonIconUrl'] = None

                    reward_bubble = reward_li.find("span", class_="reward-bubble")
                    if reward_bubble:
                        # 抓取主要道具圖片
                        main_image_tag = reward_bubble.find("img", class_="reward-image", recursive=False)
                        if main_image_tag and main_image_tag.has_attr('src'):
                            reward_info['imageUrl'] = urljoin(BASE_URL, main_image_tag['src'])

                        # 專門為超級能量抓取額外的寶可夢圖示
                        resource_info_div = reward_bubble.find("div", class_="resource-info")
                        if resource_info_div:
                            pokemon_icon_tag = resource_info_div.find("img")
                            if pokemon_icon_tag and pokemon_icon_tag.has_attr('src'):
                                reward_info['pokemonIconUrl'] = urljoin(BASE_URL, pokemon_icon_tag['src'])

                        # 抓取道具名稱
                        label_span = reward_li.find("span", class_="reward-label")
                        if label_span:
                            eng_name = label_span.text.strip()
                            reward_info['name'] = translate_item_resource(eng_name, GENERAL_TRANSLATIONS, pokemon_name_map)
                        
                        # 抓取數量
                        quantity_tag = reward_bubble.find("div", class_="quantity")
                        if quantity_tag:
                            reward_info['quantity'] = quantity_tag.text.strip()
                
                if reward_info:
                    task_data["rewards"].append(reward_info)
            
            if task_data["rewards"]:
                category_data["tasks"].append(task_data)
        
        if category_data["tasks"]:
            research_data.append(category_data)

    output_filename = "./data/research.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(research_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n🎉 成功！ 田野調查資料已儲存至 {output_filename}")

    # 手動字典和官方文本都翻不到的字串 → 寫入報告供人工檢查
    report_path = "./scripts/untranslated_report.json"
    if _UNTRANSLATED:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(sorted(_UNTRANSLATED), f, indent=2, ensure_ascii=False)
        print(f"⚠️ 有 {len(_UNTRANSLATED)} 條字串連官方文本都查不到（頁面上顯示英文原文），已寫入 {report_path}")
    else:
        print("✅ 所有字串皆已翻譯，沒有遺漏。")
        if os.path.exists(report_path):
            os.remove(report_path)   # 清掉上次的舊報告，避免誤導

if __name__ == "__main__":
    scrape_research_data_full()