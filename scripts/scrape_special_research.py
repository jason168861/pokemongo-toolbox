# ============================================================================
# 特殊調查爬蟲（增量更新）
# 資料來源：Serebii 的特殊調查列表（涵蓋 2018 年至今所有特殊調查）。
# 執行方式：在 repo 根目錄執行 `python scripts/scrape_special_research.py`
#
# 增量策略：已存在於 data/special_research.json 的條目原樣保留（不重抓、
# 不重翻），只抓索引頁上新增的調查，對 Serebii 也比較友善。
# 翻譯：重用 scrape_research.py 的官方在地化文本引擎（官方優先），
# 翻不到的字串寫入 scripts/untranslated_report_special.json 供人工檢查。
# ============================================================================

import os
import sys
import json
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrape_research import (
    HEADERS,
    GENERAL_TRANSLATIONS,
    POKEMON_TYPES_ZH,
    CITIES_ZH,
    load_json_map,
    build_official_translation_db,
    official_translate,
    translate_name,
    translate_item_resource,
    translate_task_description,
    record_untranslated,
    _UNTRANSLATED,
)

INDEX_URL = "https://www.serebii.net/pokemongo/specialresearch.shtml"
BASE_URL = "https://www.serebii.net/"
OUTPUT = "./data/special_research.json"
REPORT = "./scripts/untranslated_report_special.json"

MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
}

def _month_num(name):
    """月份名稱容錯：接受 Serebii 偶見的錯字（如 'Januar'），用前綴比對"""
    for k, v in MONTHS.items():
        if k.lower().startswith(name.lower()) and len(name) >= 3:
            return v
    return None

def translate_release_date(text):
    """把 Serebii 的英文日期轉成既有資料的中文格式（轉不動就保留原文）"""
    t = re.sub(r"(\d+)(?:st|nd|rd|th)", r"\1", " ".join(text.split()))
    t = re.sub(r"\b(?:st|nd|rd|th)\b\s*", "", t)   # 孤立的序數尾（日期數字漏打）
    t = re.sub(r"\s{2,}", " ", t).strip()
    m = re.match(r"^(\w+) (\d+) - (\w+) (\d+) (\d{4})", t)
    if m and _month_num(m.group(1)) and _month_num(m.group(3)):
        return f"{m.group(5)}年{_month_num(m.group(1))}月{m.group(2)}日 - {_month_num(m.group(3))}月{m.group(4)}日"
    m = re.match(r"^(\w+) (\d+) - (\d+) (\d{4})", t)
    if m and _month_num(m.group(1)):
        return f"{m.group(4)}年{_month_num(m.group(1))}月{m.group(2)}日 - {m.group(3)}日"
    m = re.match(r"^(\w+) (\d+) (\d{4})", t)
    if m and _month_num(m.group(1)):
        return f"{m.group(3)}年{_month_num(m.group(1))}月{m.group(2)}日"
    m = re.match(r"^(\w+) (\d{4})", t)   # 只有月份沒有日（Serebii 偶見）
    if m and _month_num(m.group(1)):
        return f"{m.group(2)}年{_month_num(m.group(1))}月"
    return text.strip()

def extract_release_date(tab_table):
    """從標題表格取出 'Date Released: ...' 的日期部分"""
    text = tab_table.get_text(" ", strip=True)
    m = re.search(r"Date Released:\s*(.+)", text)
    if not m:
        return ""
    raw = m.group(1)
    # 先清掉序數尾（含 Serebii 漏打日期數字的孤立 st/nd/rd/th），再取日期樣式的開頭
    clean = re.sub(r"(\d+)(?:st|nd|rd|th)", r"\1", raw)
    clean = re.sub(r"\b(?:st|nd|rd|th)\b\s*", "", clean)
    dm = re.match(
        r"([A-Z][a-z]+(?: \d+)?(?:\s*-\s*(?:[A-Z][a-z]+ )?\d+)?,? \d{4})", clean)
    return translate_release_date(dm.group(1)) if dm else raw[:60]

MANUAL_MAP = {}   # main() 載入 task_translation_map.json 後填入，供獎勵/標題查詢

def translate_reward_text(text, pokemon_map):
    """翻譯獎勵文字，維持既有資料的格式：
       '{名} 遭遇'、'{名} 的糖果 * N'、'{道具} * N'、'500 XP'"""
    t = " ".join(text.split())
    if not t:
        return t

    # 手動字典可直接放整條獎勵字串（例如帶括號附註的特殊寫法）
    if t in MANUAL_MAP:
        return MANUAL_MAP[t]

    t = re.sub(r"\s*\*$", "", t)   # Serebii 偶爾出現尾端孤立星號（數量留白）

    # 數量後綴 "* 20"
    qty = None
    m = re.match(r"^(.*?)\s*\*\s*([\d,]+)$", t)
    if m:
        t, qty = m.group(1).strip(), m.group(2)

    def with_qty(s):
        return f"{s} * {qty}" if qty else s

    # 活動限定獎勵的參數化句型：貼圖 / T恤 / 屬性獎牌 / 姿勢
    m = re.match(r"^(.*)\s+Sticker$", t)
    if m:
        base = official_translate(m.group(1)) or m.group(1)
        return with_qty(f"{base}貼圖")
    m = re.match(r"^(.*)\s+T-Shirt$", t)
    if m:
        base = official_translate(m.group(1)) or m.group(1)
        return with_qty(f"{base} T恤")
    m = re.match(r"^([A-Za-z]+)\s+Medal$", t)
    if m and m.group(1).capitalize() in POKEMON_TYPES_ZH:
        return with_qty(f"{POKEMON_TYPES_ZH[m.group(1).capitalize()]}屬性獎牌")
    m = re.match(r"^(.*)\s+Pose$", t)
    if m:
        base = official_translate(m.group(1)) or m.group(1)
        return with_qty(f"{base} 姿勢")

    # "500 XP" 原樣保留
    if re.match(r"^[\d,]+\s*XP$", t, re.IGNORECASE):
        return with_qty(t)

    # "{Pokemon} Encounter"
    m = re.match(r"^(.*?)\s+Encounter$", t)
    if m:
        return with_qty(f"{translate_name(m.group(1), pokemon_map, GENERAL_TRANSLATIONS)} 遭遇")

    # "{Pokemon} (XL )Candy"：名字部分翻得出來才視為寶可夢糖果
    # （'Rare Candy' 這種道具會在這裡翻不出名字，交給下面的道具翻譯）
    m = re.match(r"^(.*?)\s+(XL\s+)?Candy$", t, re.IGNORECASE)
    if m:
        name = official_translate(m.group(1)) or pokemon_map.get(m.group(1))
        if name:
            suffix = " 的糖果XL" if m.group(2) else " 的糖果"
            return with_qty(f"{name}{suffix}")

    # 其餘視為道具/資源（官方文本優先 → 手動字典 → 回報）
    return with_qty(translate_item_resource(t, GENERAL_TRANSLATIONS, pokemon_map))

def parse_reward_cell_tasks(td, pokemon_map):
    """任務獎勵欄：彙整文字 + 所有圖片（沿用既有 image_urls 陣列格式）"""
    text = translate_reward_text(td.get_text(" ", strip=True), pokemon_map)
    urls = [urljoin(BASE_URL, img["src"]) for img in td.find_all("img") if img.has_attr("src")]
    return {"text": text, "image_urls": urls}

def parse_total_reward_cell(td, pokemon_map):
    """總獎勵欄：一格裡有多個獎勵（巢狀小表格的葉子列各是一個獎勵）"""
    rewards = []
    leaf_rows = [tr for tr in td.find_all("tr") if not tr.find("tr")]
    if leaf_rows:
        for tr in leaf_rows:
            text = tr.get_text(" ", strip=True)
            if not text:
                continue
            img = tr.find("img")
            rewards.append({
                "text": translate_reward_text(text, pokemon_map),
                "image_url": urljoin(BASE_URL, img["src"]) if img and img.has_attr("src") else None,
            })
    else:
        text = td.get_text(" ", strip=True)
        if text:
            img = td.find("img")
            rewards.append({
                "text": translate_reward_text(text, pokemon_map),
                "image_url": urljoin(BASE_URL, img["src"]) if img and img.has_attr("src") else None,
            })
    return rewards

def scrape_one(url, pokemon_map, task_map):
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    tab = soup.find("table", class_="tab")
    title_eng = tab.find("tr").get_text(" ", strip=True) if tab else ""
    # 標題：官方文本 → 手動字典（task_translation_map.json 可放標題翻譯）
    #      → City Safari 城市規則 → 保留英文
    title = official_translate(title_eng) or task_map.get(title_eng)
    if not title:
        m = re.match(r"^City Safari:\s*(.+)$", title_eng)
        if m and m.group(1) in CITIES_ZH:
            title = f"City Safari：{CITIES_ZH[m.group(1)]}"
    title = title or record_untranslated(title_eng)
    release_date = extract_release_date(tab) if tab else ""

    steps = []
    current = None
    for dex in soup.find_all("table", class_="dextab"):
        body = dex.find("tbody") or dex
        for tr in body.find_all("tr", recursive=False):
            tds = tr.find_all("td", recursive=False)
            if not tds:
                continue
            first_text = tds[0].get_text(" ", strip=True)
            # 關卡標題列，如 "1 / 3"
            if re.match(r"^\d+\s*/\s*\d+$", first_text):
                current = {"step_title": first_text, "tasks": [], "total_rewards": []}
                steps.append(current)
                continue
            # 表頭列
            if first_text in ("Task", "") and len(tds) <= 3 and not tr.find("img"):
                if first_text == "Task":
                    continue
                if not first_text:
                    continue
            if current is None or len(tds) < 2:
                continue
            task = {
                "description": translate_task_description(first_text, task_map),
                "reward": parse_reward_cell_tasks(tds[1], pokemon_map),
            }
            current["tasks"].append(task)
            # 第三欄（帶 rowspan）＝這一關的總獎勵
            if len(tds) >= 3:
                current["total_rewards"] = parse_total_reward_cell(tds[2], pokemon_map)

    return {
        "title": title,
        "release_date": release_date,
        "source_url": url,
        "steps": steps,
    }

def main():
    pokemon_map = load_json_map("./data/pokemon_translation_map.json")
    task_map = load_json_map("./scripts/task_translation_map.json")
    MANUAL_MAP.update(task_map)   # 獎勵/標題字串也可放在同一個手動字典
    build_official_translation_db()

    # 既有資料：以 URL 尾段當 key，原樣保留（增量更新）
    try:
        with open(OUTPUT, encoding="utf-8") as f:
            existing = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        existing = []
    known = {e["source_url"].split("/")[-1].lower() for e in existing}

    print("⏳ 抓取 Serebii 特殊調查索引…")
    resp = requests.get(INDEX_URL, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    hrefs = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # 索引頁的連結是相對路徑，如 "specialresearch/waterworks.shtml"
        if "specialresearch/" in href and href.endswith(".shtml") \
                and not href.endswith("specialresearch/.shtml"):
            hrefs.append(urljoin(INDEX_URL, href))
    # 去重、保持索引頁順序
    seen = set()
    urls = [u for u in hrefs if not (u.lower() in seen or seen.add(u.lower()))]
    new_urls = [u for u in urls if u.split("/")[-1].lower() not in known]
    print(f"✅ 索引共 {len(urls)} 條，本地已有 {len(existing)} 條，需新增 {len(new_urls)} 條")

    added = 0
    for i, url in enumerate(new_urls, 1):
        name = url.split("/")[-1]
        try:
            entry = scrape_one(url, pokemon_map, task_map)
            if entry["steps"]:
                existing.append(entry)
                added += 1
                print(f"  [{i}/{len(new_urls)}] ✅ {entry['title']}（{entry['release_date']}）")
            else:
                print(f"  [{i}/{len(new_urls)}] ⚠️ {name} 解析不到任何關卡，略過")
        except Exception as e:
            print(f"  [{i}/{len(new_urls)}] ❌ {name} 失敗：{e}")
        time.sleep(1)   # 對 Serebii 友善一點

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)
    print(f"\n🎉 完成！新增 {added} 條，總計 {len(existing)} 條 → {OUTPUT}")

    if _UNTRANSLATED:
        with open(REPORT, "w", encoding="utf-8") as f:
            json.dump(sorted(_UNTRANSLATED), f, indent=2, ensure_ascii=False)
        print(f"⚠️ 有 {len(_UNTRANSLATED)} 條字串查不到翻譯（保留英文原文），已寫入 {REPORT}")
    else:
        print("✅ 所有字串皆已翻譯。")
        if os.path.exists(REPORT):
            os.remove(REPORT)

if __name__ == "__main__":
    main()
