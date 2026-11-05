import requests
import json
import os
import math

TYPE_ZH = {
    "normal": "一般", "fighting": "格鬥", "flying": "飛行", "poison": "毒",
    "ground": "地面", "rock": "岩石", "bug": "蟲", "ghost": "幽靈",
    "steel": "鋼", "fire": "火", "water": "水", "grass": "草",
    "electric": "電", "psychic": "超能力", "ice": "冰", "dragon": "龍",
    "dark": "惡", "fairy": "妖精", "none": ""
}


def write_move_types(gm_data, path=os.path.join("data", "pvp_move_types.json")):
    """招式中文名 → 屬性（中文），給 scripts/build_pvp_league.py 的排名頁替招式上色。
    另存一個小檔，而不是塞進 pokemon_data_and_rankings.js —— 那支 PvP 工具每次都要整包下載。"""
    types = {}
    for m in gm_data.get('moves', []):
        name, t = m.get('name'), TYPE_ZH.get(m.get('type', 'none'), '')
        if name and t:
            types.setdefault(name, t)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(types, f, ensure_ascii=False, indent=0, sort_keys=True)
        f.write('\n')


def get_pokemon_family_info(pokemon_id, pokemon_map, family_map, stage_memo):
    """確定寶可夢的家族ID和進化階段"""
    pokemon_data = pokemon_map.get(pokemon_id)
    if not pokemon_data:
        return pokemon_id.split('_')[0], 1

    source_family_id = pokemon_data.get('family', {}).get('id')
    base_form_id = family_map.get(source_family_id, pokemon_id.split('_')[0])

    if pokemon_id in stage_memo:
        stage = stage_memo[pokemon_id]
    else:
        parent_id = pokemon_data.get('family', {}).get('parent')
        if not parent_id:
            stage = 1
        else:
            _, parent_stage = get_pokemon_family_info(parent_id, pokemon_map, family_map, stage_memo)
            stage = parent_stage + 1
        stage_memo[pokemon_id] = stage
    
    return base_form_id, stage

def process_gamemaster(game_master):
    """處理 gamemaster.json 生成 POKEDEX"""
    print("正在處理寶可夢基本數據...")
    raw_pokemon_list = game_master.get('pokemon', [])
    if not raw_pokemon_list:
        print("錯誤：在獲取的 JSON 中找不到 'pokemon' 列表。")
        return None

    filtered_list = [p for p in raw_pokemon_list if '_shadow' not in p.get('speciesId', '')]
    pokemon_map = {p['speciesId']: p for p in filtered_list}

    family_map = {}
    for p in filtered_list:
        if not p.get('family', {}).get('parent'):
            source_family_id = p.get('family', {}).get('id')
            if source_family_id:
                family_map[source_family_id] = p.get('speciesId', '')

    processed_pokedex = []
    stage_memo = {}

    for raw_pokemon in filtered_list:
        species_id = raw_pokemon['speciesId']
        family_id, stage = get_pokemon_family_info(species_id, pokemon_map, family_map, stage_memo)

        name = raw_pokemon.get('speciesName', species_id)
        if "_mega" in species_id: name = f"{name.split(' ')[0]} (Mega)"
        elif "_alolan" in species_id: name = f"{name.split(' ')[0]} (阿羅拉)"
        elif "_galarian" in species_id: name = f"{name.split(' ')[0]} (伽勒爾)"
        elif "_hisuian" in species_id: name = f"{name.split(' ')[0]} (洗翠)"
        
        processed_pokemon = {
            'id': species_id,
            'dexNumber': raw_pokemon['dex'],
            'name': name,
            'stats': {
                'atk': raw_pokemon['baseStats']['atk'],
                'def': raw_pokemon['baseStats']['def'],
                'sta': raw_pokemon['baseStats']['hp']
            },
            'types': [t for t in raw_pokemon.get('types', []) if t != "none"],
            'family': { 'id': family_id, 'stage': stage }
        }

        if 'tags' in raw_pokemon and 'alias' in raw_pokemon['tags']:
            processed_pokemon['aliases'] = [alias.lower() for alias in raw_pokemon.get('tags', {}).get('alias', [])]

        processed_pokedex.append(processed_pokemon)
    
    print(f"已處理 {len(processed_pokedex)} 筆寶可夢條目。")
    return processed_pokedex

def process_rankings(rankings_data, gm_data):
    """處理特定聯盟的排名數據"""
    pokemon_lookup = {p['speciesId']: p for p in gm_data['pokemon']}
    move_lookup = {m['moveId']: m for m in gm_data['moves']}
    type_translate_map = TYPE_ZH

    processed_rankings = []
    for p_rank in rankings_data:
        species_id = p_rank.get('speciesId')
        p_gm = pokemon_lookup.get(species_id, {})

        species_name_ch = p_gm.get('speciesName', species_id)
        stats = p_rank.get('stats', {})
        attack = stats.get('atk', 0)
        defense = stats.get('def', 0)
        hp = stats.get('hp', 0)
        
        moveset_ids = p_rank.get('moveset', [])
        fast_move_id = moveset_ids[0] if moveset_ids else None
        fast_move_gm = move_lookup.get(fast_move_id, {})
        cm1_id = moveset_ids[1] if len(moveset_ids) > 1 else None
        cm1_gm = move_lookup.get(cm1_id, {})
        cm2_id = moveset_ids[2] if len(moveset_ids) > 2 else None
        cm2_gm = move_lookup.get(cm2_id, {})

        # === 【邏輯修正】從寶可夢資料中檢查 Elite Move ===
        # 先從 p_gm (該寶可夢的 gamemaster 資料) 中安全地取得 eliteMoves 列表
        pokemon_elite_moves = p_gm.get('eliteMoves', [])

        # 檢查當前招式 ID 是否存在於該寶可夢的 eliteMoves 列表中
        is_elite_fast = fast_move_id in pokemon_elite_moves
        is_elite_cm1 = cm1_id in pokemon_elite_moves
        is_elite_cm2 = cm2_id in pokemon_elite_moves
        # === 修正結束 ===

        fast_move_energy = fast_move_gm.get('energyGain', 0)
        cm1_energy_cost = cm1_gm.get('energy', 0)
        cm2_energy_cost = cm2_gm.get('energy', 0)

        pokemon_dict = {
            'name': species_name_ch,
            'score': p_rank.get('score', 0),
            'dex': p_gm.get('dex', 0),
            'type1': type_translate_map.get(p_gm.get('types', ['none'])[0]),
            'type2': type_translate_map.get(p_gm.get('types', ['none', 'none'])[1]),
            'atk': round(attack, 1),
            'def': round(defense, 1),
            'hp': hp,
            'statProduct': round(attack * defense * hp),
            'level': p_rank.get('level', 0),
            'fastMove': fast_move_gm.get('name', fast_move_id),
            'chargedMove1': cm1_gm.get('name', cm1_id),
            'chargedMove2': cm2_gm.get('name', cm2_id) if cm2_id else '',
            # 這裡不需要改，因為 is_elite_... 的值已經被正確計算了
            'isEliteFast': is_elite_fast,
            'isEliteCharged1': is_elite_cm1,
            'isEliteCharged2': is_elite_cm2,
            'cm1Turns': math.ceil(cm1_energy_cost / fast_move_energy) if fast_move_energy > 0 else 0,
            'cm2Turns': math.ceil(cm2_energy_cost / fast_move_energy) if fast_move_energy > 0 and cm2_energy_cost > 0 else 0,
            'buddyDistance': p_gm.get('buddyDistance', 0),
            'thirdMoveCost': p_gm.get('thirdMoveCost', 0)
        }
        processed_rankings.append(pokemon_dict)
    
    return processed_rankings

def fetch_and_generate_data():
    """主函數：獲取、處理並生成 JS 數據文件"""
    OUTPUT_PATH = os.path.join("data", "pokemon_data_and_rankings.js")
    
    try:
        print("正在獲取遊戲主數據 (gamemaster.json)...")
        gm_url = "https://pvpoketw.com/data/gamemaster.json"
        game_master = requests.get(gm_url, timeout=15).json()
        print("主數據獲取成功。")

        leagues_to_fetch = ['1500', '2500', '10000']
        all_rankings_data = {}
        for cp in leagues_to_fetch:
            print(f"正在獲取 CP {cp} 的排名數據...")
            rankings_url = f"https://pvpoketw.com/data/rankings/all/overall/rankings-{cp}.json"
            rankings_json = requests.get(rankings_url, timeout=15).json()
            all_rankings_data[cp] = rankings_json
            print(f"CP {cp} 排名數據獲取成功。")

    except requests.exceptions.RequestException as e:
        print(f"錯誤：數據獲取失敗。 {e}")
        return
    except json.JSONDecodeError as e:
        print(f"錯誤：解析 JSON 失敗。 {e}")
        return
        
    pokedex_data = process_gamemaster(game_master)
    
    processed_rankings = {}
    for cp, ranking_data in all_rankings_data.items():
        print(f"正在處理 CP {cp} 的排名...")
        processed_rankings[cp] = process_rankings(ranking_data, game_master)
        print(f"CP {cp} 排名處理完成。")

    if not os.path.exists("data"):
        os.makedirs("data")

    try:
        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            f.write("const POKEDEX = ")
            json.dump(pokedex_data, f, ensure_ascii=False, indent=2)
            f.write(";\n\n")
            
            for cp, data in processed_rankings.items():
                f.write(f"const POKEMON_RANKINGS_{cp} = ")
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write(";\n\n")
        
        print(f"成功！數據文件已建立於: {OUTPUT_PATH} 🎉")
        write_move_types(game_master)

    except IOError as e:
        print(f"錯誤：無法寫入文件。 {e}")

if __name__ == "__main__":
    fetch_and_generate_data()