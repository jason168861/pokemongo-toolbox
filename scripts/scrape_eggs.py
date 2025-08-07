import requests
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin
# import locale
# locale.setlocale(locale.LC_CTYPE, 'chinese')
# ==================== 翻譯資料區塊 START ====================

# 定義特殊形態的翻譯字典
FORM_TRANSLATIONS = {
    'Alolan': '阿羅拉', 'Galarian': '伽勒爾', 'Hisuian': '洗翠', 'Origin': '起源',
    'Altered': '別種', 'Attack': '攻擊', 'Defense': '防禦', 'Speed': '速度',
    'Sunny': '太陽', 'Rainy': '雨水', 'Snowy': '雪雲', 'Overcast': '陰天',
    'Incarnate': '化身', 'Therian': '靈獸', 'Black': '闇黑', 'White': '焰白',
    'Plant': '草木', 'Sandy': '砂土', 'Trash': '垃圾', 'Confined': '懲戒', 'Unbound': '解放',
    'Aria': '歌聲', 'Pirouette': '舞步', 'Fan': '電風扇', 'Frost': '結冰', 'Heat': '加熱', 'Mow': '割草', 'Wash': '清洗',
    'Dusk': '黃昏', 'Midday': '白晝', 'Midnight': '黑夜', 'School': '魚群', 'Solo': '單獨', 'Dawn Wings': '日蝕奈克洛茲瑪', 'Ultra': '究極',
    'Hero': '百戰勇者', 'White Striped': '白條紋' # 處理像 Basculin (White Striped) 的情況
}

def load_translations():
    """載入寶可夢名稱翻譯檔"""
    try:
        with open("./data/pokemon_translation_map.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ 錯誤：找不到 pokemon_translation_map.json 檔案。")
        return None
    except json.JSONDecodeError:
        print("❌ 錯誤：pokemon_translation_map.json 格式有誤。")
        return None

def translate_name(eng_name, name_map, form_map):
    """將英文名稱翻譯成中文，能處理地區形態和特殊名稱"""
    if not eng_name:
        return ""

    # 處理括號內的特殊形態, e.g., "Basculin (White Striped)" -> "Basculin", "White Striped"
    form_in_parentheses_match = re.match(r'(.+?)\s*\((.+?)\)', eng_name)
    if form_in_parentheses_match:
        base_name = form_in_parentheses_match.group(1).strip()
        form_name = form_in_parentheses_match.group(2).strip()
        if base_name in name_map and form_name in form_map:
            return f"{name_map[base_name]} ({form_map[form_name]})"

    # 處理地區形態, e.g., "Alolan Meowth" -> "Alolan", "Meowth"
    parts = eng_name.split()
    if len(parts) > 1 and parts[0] in form_map:
        form_name = parts[0]
        base_name = " ".join(parts[1:])
        if base_name in name_map:
            return f"{form_map[form_name]} {name_map[base_name]}"

    # 處理一般名稱
    if eng_name in name_map:
        return name_map[eng_name]

    # 如果都找不到，回傳原文並印出警告
    print(f"  > 翻譯警告：在字典中找不到 '{eng_name}'，將使用原文。")
    return eng_name

# ==================== 翻譯資料區塊 END ======================

URL = "https://leekduck.com/eggs/"
BASE_URL = "https://leekduck.com/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def scrape_egg_data():
    # 在爬蟲開始前，先載入翻譯資料
    name_translation_map = load_translations()
    if name_translation_map is None:
        return # 如果翻譯檔載入失敗，則停止執行

    try:
        print("正在從 LeekDuck 抓取資料...")
        response = requests.get(URL, headers=HEADERS)
        response.raise_for_status()
        print("成功取得網頁內容！")

        soup = BeautifulSoup(response.text, "lxml")
        all_pokemon_data = []
        
        # 【修改點 1】尋找所有的 h2 標籤，讓後續邏輯來判斷類型
        egg_section_headers = soup.find_all("h2", string=re.compile(r'km Eggs'))

        for header in egg_section_headers:
            header_text = header.text.strip()
            egg_distance_match = re.search(r'(\d+)', header_text)
            if not egg_distance_match: continue
            
            egg_distance = int(egg_distance_match.group(1))
            
            # 【修改點 2】判斷蛋的來源 (source)
            source = "regular" # 預設為一般
            if "Adventure Sync Rewards" in header_text:
                source = "adventure_sync"
            elif "From Route Gift" in header_text:
                source = "route_gift"
            
            print(f"正在處理 {egg_distance}km 蛋池 (來源: {source})...")

            pokemon_list_ul = header.find_next_sibling("ul", class_="egg-list-flex")
            if not pokemon_list_ul: continue

            for item in pokemon_list_ul.find_all("li", class_="egg-list-item"):
                # 【修改點 3】在 pokemon_info 中加入 eggDistance 和 source
                pokemon_info = {
                    "eggDistance": egg_distance,
                    "source": source 
                }
                
                name_tag = item.find("span", class_="hatch-pkmn")
                
                if name_tag:
                    english_name = name_tag.text.strip()
                    chinese_name = translate_name(english_name, name_translation_map, FORM_TRANSLATIONS)
                    pokemon_info["name"] = chinese_name
                
                cp_tag = item.find("div", class_="font-size-smaller")
                img_tag = item.find("div", class_="egg-list-img").find("img")
                shiny_tag = item.find("img", class_="shiny-icon")

                if cp_tag:
                    cp_match = re.search(r'[\d,]+\s*-\s*[\d,]+', cp_tag.text)
                    if cp_match:
                        pokemon_info["cpRange"] = cp_match.group(0).replace(',', '')

                if img_tag and img_tag.has_attr('src'):
                    absolute_url = urljoin(BASE_URL, img_tag['src'])
                    pokemon_info["imageUrl"] = absolute_url

                pokemon_info["isShiny"] = shiny_tag is not None

                if "name" in pokemon_info and "imageUrl" in pokemon_info:
                    all_pokemon_data.append(pokemon_info)
                else:
                    print(f"  > 警告：跳過一筆不完整的資料 (名稱或圖片網址缺失)。")
        output_data = {
            # 格式化日期為 "YYYY年M月D日"
        "lastUpdated": datetime.now().strftime('%Y年%m月%d日%H時').replace('年0', '年').replace('月0', '月'),
            "pokemon": all_pokemon_data
        }

        output_filename = "./data/eggs.json"
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ 成功！ 資料已儲存至 {output_filename}")
        print(f"共擷取到 {len(all_pokemon_data)} 筆寶可夢資料。")

    except requests.exceptions.RequestException as e:
        print(f"❌ 抓取網頁時發生錯誤: {e}")
    except Exception as e:
        print(f"❌ 處理資料時發生未知錯誤: {e}")
if __name__ == "__main__":
    scrape_egg_data()