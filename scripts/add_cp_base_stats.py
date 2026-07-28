#!/usr/bin/env python3
"""把「基礎數值(atk/def/sta)」與「CPM 對照表」補進 data/precomputed_pokemon_cp.js。

有了這兩樣，前端就能算出任意等級的 CP，不用再多一份資料檔：
    CP(等級) = max(10, floor((atk+IV) * √(def+IV) * √(sta+IV) * CPM² / 10))

怎麼對到 GAME_MASTER 的基礎數值:
    檔案裡的名稱有 57 個 dex 重複(地區形態)，而且形態名混了中文與 GM 代碼
    (阿羅拉形態 / Crowned_sword形態…)，用名稱對照要維護一張又臭又長的表。
    改成**用 CP 值反查**:同一個 dex 底下，找 cp15/cp20/cp25 三個值都吻合的那組基礎數值。
    三個數字同時命中幾乎不可能巧合，而且「對得上」本身就是驗證 —— 不需要名稱對照表。

順帶修好 3 筆壞資料:獨劍鞘 / 雙劍鞘 / 堅盾劍怪 在原檔裡 cp15=cp20=cp25=10
    (公式下限，代表產生當時沒抓到基礎數值)。這幾筆用 GM 的數值重算。

冪等:重跑不會變動已經正確的資料。需要網路(抓 PokeMiners game_master)。
用法:python scripts/add_cp_base_stats.py
"""
import ast, json, math, os, re, sys, urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "precomputed_pokemon_cp.js")
GM_URL = "https://raw.githubusercontent.com/PokeMiners/game_masters/master/latest/latest.json"
MAX_LEVEL = 50          # 一般上限
BEST_BUDDY_LEVEL = 51   # 最佳夥伴 +1 級


def fetch_gm():
    req = urllib.request.Request(GM_URL, headers={"User-Agent": "Mozilla/5.0 build"})
    return json.loads(urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "ignore"))


def main():
    print("抓 GAME_MASTER…", flush=True)
    gm = fetch_gm()

    # CPM:PLAYER_LEVEL_SETTINGS.cpMultiplier,index = 等級-1(整數級)
    cpm = None
    for e in gm:
        if e.get("templateId") == "PLAYER_LEVEL_SETTINGS":
            cpm = e["data"]["playerLevel"]["cpMultiplier"]; break
    if not cpm:
        sys.exit("GAME_MASTER 裡找不到 PLAYER_LEVEL_SETTINGS.cpMultiplier")
    cpm = [round(x, 8) for x in cpm[:BEST_BUDDY_LEVEL]]
    print(f"CPM:Lv1={cpm[0]} / Lv15={cpm[14]} / Lv50={cpm[49]} / Lv51={cpm[50]}")

    # 每個 dex 底下所有型態的基礎數值(去重:同數值的不同型態算同一組)
    stats = {}
    for e in gm:
        m = re.match(r"V(\d+)_POKEMON_", e.get("templateId", ""))
        ps = e.get("data", {}).get("pokemonSettings")
        if not (m and ps):
            continue
        st = ps.get("stats") or {}
        a, d, s = st.get("baseAttack"), st.get("baseDefense"), st.get("baseStamina")
        if None in (a, d, s):
            continue
        stats.setdefault(int(m.group(1)), {}).setdefault((a, d, s), e["templateId"])

    def cp_at(a, d, s, level, iv=15):
        return max(10, int((a + iv) * math.sqrt(d + iv) * math.sqrt(s + iv) * cpm[level - 1] ** 2 / 10))

    text = open(SRC, encoding="utf-8").read()
    # 只取第一個陣列:重跑時檔尾已經有 CP_MULTIPLIER,用 rindex 會把兩個陣列一起吃進來(不冪等)
    arr = ast.literal_eval(text[text.index("["):text.index("];") + 1])

    matched = fixed = unmatched = 0
    misses = []
    for p in arr:
        cands = stats.get(p["id"], {})
        hit = [k for k in cands if all(cp_at(*k, L) == p["cp%d" % L] for L in (15, 20, 25))]
        if not hit and p["cp15"] == p["cp20"] == p["cp25"] == 10 and cands:
            # 原檔是壞的(CP 全是公式下限)→ 用該 dex 的基本型(templateId 沒有形態後綴的那個)重算
            base = min(cands.items(), key=lambda kv: len(kv[1]))
            hit = [base[0]]
            a, d, s = base[0]
            for L in (15, 20, 25):
                p["cp%d" % L] = cp_at(a, d, s, L)
            fixed += 1
            print(f"  修正 {p['name']}(原本 CP 全 10)→ atk={a} def={d} sta={s} "
                  f"cp15={p['cp15']} cp20={p['cp20']} cp25={p['cp25']}  [{base[1]}]")
        if hit:
            a, d, s = hit[0]
            p["atk"], p["def"], p["sta"] = a, d, s
            matched += 1
        else:
            unmatched += 1
            misses.append((p["id"], p["name"]))
            p.pop("atk", None); p.pop("def", None); p.pop("sta", None)

    print(f"\n對到基礎數值 {matched} / 順帶修好 {fixed} / 仍對不到 {unmatched}")
    if misses:
        print("  對不到(前端會自動略過全等級表):", misses[:10])

    # 寫回:保持原本 const 名稱與單引號字典風格,另外多輸出一個 CPM 常數
    body = ", ".join(
        "{" + ", ".join(f"'{k}': {json.dumps(v, ensure_ascii=False)}" for k, v in p.items()) + "}"
        for p in arr)
    out = (f"const POKEMON_CP_DATA = [{body}];\n"
           f"// 等級 → CP 倍率(GAME_MASTER PLAYER_LEVEL_SETTINGS.cpMultiplier,index = 等級-1)\n"
           f"// 索引 {MAX_LEVEL} 是最佳夥伴的 Lv{BEST_BUDDY_LEVEL}\n"
           f"const CP_MULTIPLIER = {json.dumps(cpm)};\n")
    open(SRC, "w", encoding="utf-8", newline="\n").write(out)
    print(f"已寫回 {os.path.relpath(SRC, ROOT)}  ({len(out)//1024} KB)")


if __name__ == "__main__":
    main()
