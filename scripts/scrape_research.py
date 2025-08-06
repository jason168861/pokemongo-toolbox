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
    'Hero': '百戰勇者', 'White Striped': '白條紋',
    
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
    'Mega Energy': '超級能量' # 用於組合，例如 "妙蛙花 超級能量"
}

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
    """將寶可夢英文名稱翻譯成中文"""
    if not eng_name or not name_map:
        return eng_name
    
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
    
    return eng_name

# ==================================================================
#                    【⭐️ 這裡是修正的核心 ⭐️】
# 將下方的 translate_item_resource 函式替換掉您原本的函式
# ==================================================================
def translate_item_resource(eng_name, general_map, pokemon_map):
    """翻譯道具、資源，並處理像超級能量和帶有數量的道具等特殊情況。"""
    # 優先處理超級能量，例如 "Venusaur Mega Energy"
    mega_energy_match = re.match(r'(.+?)\s+Mega Energy', eng_name)
    if mega_energy_match:
        pokemon_name = mega_energy_match.group(1).strip()
        translated_pokemon = pokemon_map.get(pokemon_name, pokemon_name)
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
            
    # 如果遍歷完字典都找不到匹配的開頭，則返回原始名稱
    return eng_name

# ==================== 翻譯資料區塊 END ======================

URL = "https://leekduck.com/research/"
BASE_URL = "https://leekduck.com/"
HEADERS = { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36" }

def scrape_research_data_full():
    pokemon_name_map = load_json_map("./data/pokemon_translation_map.json")
    task_translation_map = load_json_map("./scripts/task_translation_map.json") 
    category_translation_map = load_json_map("./scripts/category_translation_map.json") # <-- 新增此行

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
            translated_task = task_translation_map.get(task_description, task_description)

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
    
if __name__ == "__main__":
    scrape_research_data_full()