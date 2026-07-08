import requests
import json
import re
import os
import pytz
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
# import locale
# locale.setlocale(locale.LC_CTYPE, 'chinese')
# ==================== 常數與設定區塊 START ====================

# 目標網站與備份來源
RAID_URL = "https://leekduck.com/raid-bosses/"
BASE_URL = "https://leekduck.com/"
FALLBACK_URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/raids.min.json"

# 模擬瀏覽器標頭
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# 輸出資料夾路徑
OUTPUT_DIR = "./data"
OUTPUT_FILENAME_PRETTY = os.path.join(OUTPUT_DIR, "raids.json")
OUTPUT_FILENAME_MIN = os.path.join(OUTPUT_DIR, "raids.min.json")


# ==================== 翻譯資料區塊 START ====================
# (沿用您範本中的翻譯邏輯)

# 定義特殊形態的翻譯字典
FORM_TRANSLATIONS = {
    'Alolan': '阿羅拉', 'Galarian': '伽勒爾', 'Hisuian': '洗翠', 'Origin': '起源',
    'Altered': '別種', 'Attack': '攻擊', 'Defense': '防禦', 'Speed': '速度',
    'Sunny': '太陽', 'Rainy': '雨水', 'Snowy': '雪雲', 'Overcast': '陰天',
    'Incarnate': '化身', 'Therian': '靈獸', 'Black': '闇黑', 'White': '焰白',
    'Plant': '草木', 'Sandy': '砂土', 'Trash': '垃圾', 'Confined': '懲戒', 'Unbound': '解放',
    'Aria': '歌聲', 'Pirouette': '舞步', 'Fan': '電風扇', 'Frost': '結冰', 'Heat': '加熱', 'Mow': '割草', 'Wash': '清洗',
    'Dusk': '黃昏', 'Midday': '白晝', 'Midnight': '黑夜', 'School': '魚群', 'Solo': '單獨', 'Dawn Wings': '日蝕奈克洛茲瑪', 'Ultra': '究極',
    'Hero': '百戰勇者', 'White Striped': '白條紋', 'Mega': '超級', 'Primal': '原始', "Farfetch'd": "大蔥鸭",
    'Shadow': '暗影'
}

def load_translations():
    """載入寶可夢名稱翻譯檔"""
    translation_file = os.path.join(OUTPUT_DIR, "pokemon_translation_map.json")
    try:
        with open(translation_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ 警告：找不到翻譯檔 {translation_file}，部分名稱可能無法翻譯。")
        return {} # 回傳空字典以避免程式中斷
    except json.JSONDecodeError:
        print(f"❌ 錯誤：{translation_file} 格式有誤。")
        return None

def translate_name(eng_name, name_map, form_map):
    """將英文名稱翻譯成中文，能處理地區形態、超級進化和特殊名稱"""
    if not eng_name:
        return ""

    # 處理暗影，例如 "Shadow Palkia"、"Shadow Necrozma (Dusk Mane)"
    # 先剝掉 "Shadow " 前綴，把剩下的部分照常翻譯，再冠上「暗影」
    if eng_name.startswith("Shadow "):
        rest = eng_name[len("Shadow "):]
        return f"{form_map.get('Shadow', '暗影')} {translate_name(rest, name_map, form_map)}"

    # 處理超級進化，例如 "Mega Charizard X"
    if eng_name.startswith("Mega ") or eng_name.startswith("Primal "):
        parts = eng_name.split(" ", 1)
        form_type = parts[0] # "Mega" 或 "Primal"
        base_name = parts[1]
        
        translated_base = name_map.get(base_name, base_name)
        translated_form = form_map.get(form_type, form_type)
        return f"{translated_form} {translated_base}"

    # 處理括號內的特殊形態, e.g., "Basculin (White Striped)"
    match = re.match(r'(.+?)\s*\((.+?)\)', eng_name)
    if match:
        base_name, form_name = match.groups()
        base_name = base_name.strip()
        form_name = form_name.strip()
        if base_name in name_map and form_name in form_map:
            return f"{name_map[base_name]} ({form_map[form_name]})"

    # 處理地區形態, e.g., "Alolan Meowth"
    parts = eng_name.split()
    if len(parts) > 1 and parts[0] in form_map:
        form_name, base_name = parts[0], " ".join(parts[1:])
        if base_name in name_map:
            return f"{form_map[form_name]} {name_map[base_name]}"

    # 處理一般名稱
    if eng_name in name_map:
        return name_map[eng_name]

    print(f"  > 翻譯警告：在字典中找不到 '{eng_name}'，將使用原文。")
    return eng_name

# ==================== 翻譯資料區塊 END ======================


def scrape_raid_data():
    """主函式，用於抓取、解析和儲存團體戰頭目資料"""
    
    # 建立輸出資料夾 (如果不存在)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 載入翻譯資料
    name_translation_map = load_translations()
    if name_translation_map is None: # 僅在JSON格式錯誤時停止
        return
        
    bosses = []
    
    try:
        # --- 主要抓取邏輯 ---
        print(f"🚀 正在從 {RAID_URL} 抓取團體戰資料...")
        response = requests.get(RAID_URL, headers=HEADERS, timeout=15)
        response.raise_for_status() # 如果請求失敗 (如 404, 500)，會拋出例外
        print("✅ 成功取得網頁內容！正在解析...")

        soup = BeautifulSoup(response.text, "lxml")
        
        # 找到所有 tier 的區塊 (包含一般和暗影頭目)
        all_tiers = soup.select(".raid-bosses .tier, .shadow-raid-bosses .tier")
        if not all_tiers:
            raise ValueError("在頁面中找不到 '.tier' 區塊。")

        for tier_div in all_tiers:
            # 取得 tier 名稱
            header = tier_div.find("h2", class_="header")
            if not header:
                continue
            current_tier = header.get_text(strip=True)
            print(f"\n--- 正在處理分類：{current_tier} ---")

            # 找到這個 tier 內所有的頭目卡片
            for card in tier_div.find_all("div", class_="card"):
                # 抓取英文名稱並翻譯
                name_tag = card.find("p", class_="name")
                if not name_tag:
                    continue
                eng_name = name_tag.get_text(strip=True)
                translated_boss_name = translate_name(eng_name, name_translation_map, FORM_TRANSLATIONS)
                print(f"  - 找到頭目: {translated_boss_name} ({eng_name})")

                # 小工具：把 "CP 1957 - 2042" 解析成 (min, max)，失敗回傳 (0, 0)
                def parse_cp(tag):
                    if not tag:
                        return 0, 0
                    txt = tag.get_text(strip=True).replace("CP", "").strip()
                    try:
                        lo, hi = [int(p.strip()) for p in txt.split(' - ')]
                        return lo, hi
                    except ValueError:
                        return 0, 0

                # 小工具：圖片的名稱優先讀 title，新版改用 alt
                def img_name(img):
                    return (img.get('title') or img.get('alt') or '').lower()

                # 解析CP範圍
                cp_min, cp_max = parse_cp(card.find("div", class_="cp-range"))

                # 解析天氣加成後的CP範圍（改版後 boosted-cp 移到 .boosted-cp-row，不再位於 .weather-boosted 內）
                boosted_cp_min, boosted_cp_max = parse_cp(card.find("span", class_="boosted-cp"))

                # 解析天氣類型（仍在 .weather-boosted .boss-weather 內；新版 img 用 alt 標名稱）
                boosted_weathers = []
                boost_section = card.find("div", class_="weather-boosted")
                if boost_section:
                    for img in boost_section.select(".boss-weather img"):
                        boosted_weathers.append({
                            "name": img_name(img),
                            "image": urljoin(BASE_URL, img['src'])
                        })

                # 解析寶可夢屬性
                types = []
                for img in card.select(".boss-type img"):
                    types.append({
                        "name": img_name(img),
                        "image": urljoin(BASE_URL, img['src'])
                    })

                # 抓取寶可夢圖片
                boss_img_tag = card.select_one(".boss-img img")
                image_url = urljoin(BASE_URL, boss_img_tag['src']) if boss_img_tag else ""

                # 組合最終的 JSON 物件
                boss_data = {
                    "name": translated_boss_name,
                    "englishName": eng_name,
                    "tier": current_tier,
                    "canBeShiny": card.find("svg", class_="shiny-icon") is not None,
                    "types": types,
                    "combatPower": {
                        "normal": {"min": cp_min, "max": cp_max},
                        "boosted": {"min": boosted_cp_min, "max": boosted_cp_max}
                    },
                    "boostedWeather": boosted_weathers,
                    "image": image_url
                }
                bosses.append(boss_data)

    except (requests.exceptions.RequestException, ValueError) as e:
        # --- 備份抓取邏輯 (Fallback) ---
        print(f"\n❌ 主要抓取失敗 ({e})，嘗試從備份來源下載...")
        try:
            response = requests.get(FALLBACK_URL, timeout=15)
            response.raise_for_status()
            fallback_data = response.json()
            print("✅ 成功從備份來源下載資料！")
            
            # 確保從 fallback_data 正確提取 bosses 列表
            boss_list_from_fallback = fallback_data.get('bosses', []) if isinstance(fallback_data, dict) else fallback_data
            
            # 備份資料也需要翻譯
            for boss in boss_list_from_fallback:
                if 'name' in boss:
                    original_name = boss['name']
                    boss['englishName'] = original_name
                    boss['name'] = translate_name(original_name, name_translation_map, FORM_TRANSLATIONS)
            
            bosses = boss_list_from_fallback

        except requests.exceptions.RequestException as fallback_e:
            print(f"❌ 備份來源也抓取失敗: {fallback_e}")
            return # 雙重失敗，直接結束程式
    
    except Exception as e:
        print(f"❌ 處理資料時發生未知錯誤: {e}")
        return

    # --- 寫入檔案 ---
    if bosses:
        print("\n💾 正在將資料寫入檔案...")
        taipei_tz = pytz.timezone('Asia/Taipei')
        now_taipei = datetime.now(pytz.utc).astimezone(taipei_tz)
        try:
            # 寫入格式化的 JSON
            output_data = {
                "lastUpdated": now_taipei.strftime('%Y年%m月%d日%H時').replace('年0', '年').replace('月0', '月'),
                "bosses": bosses
            }
        
            with open(OUTPUT_FILENAME_PRETTY, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=4, ensure_ascii=False)
            
            # 寫入壓縮的 JSON
            with open(OUTPUT_FILENAME_MIN, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False)

            print(f"✅ 成功！ 資料已儲存至 {OUTPUT_FILENAME_PRETTY} 和 {OUTPUT_FILENAME_MIN}")
            print(f"總共擷取到 {len(bosses)} 筆頭目資料。")
        except IOError as e:
            print(f"❌ 寫入檔案時發生錯誤: {e}")
    else:
        print("🤷‍♂️ 沒有抓取到任何資料，不寫入檔案。")


if __name__ == "__main__":
    scrape_raid_data()