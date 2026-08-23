#!/usr/bin/env python3
"""產生 js/zh-search.js —— 繁簡通用搜尋用的字元對照表。

站上的名稱全是繁體(來源 PokeMiners 只有 i18n_chinesetraditional),
使用者打簡體會一個字都對不到。前端把「被搜尋的字串」與「使用者輸入」
都用這張表正規化成簡體再比對。

只收「站上資料實際出現、而且繁簡不同」的字(約 480 個 / 6KB),
不是整套 OpenCC 字典(那有兩萬多字,沒必要送到瀏覽器)。

什麼時候要重跑:新增了含中文的資料檔、或 data/ 的名稱來源換過。

    pip install opencc-python-reimplemented
    python scripts/build_zh_table.py
"""
import json, os, re, sys

try:
    import opencc
except ImportError:
    sys.exit("需要 opencc:pip install opencc-python-reimplemented")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 所有可能被搜尋到的中文來源。漏掉某個檔的後果是「那些字轉不了」,
# 不會壞掉,但簡體搜尋會對不到 → 有新的中文資料檔記得加進來。
SOURCES = [
    "trade-list/data/names/zh.json",
    "trade-list/data/aliases.json",
    "data/pokemon_names_from_api.js",
    "data/pokemon_translation_map.js",
    "data/research.json",
    "data/raids.json",
    "data/eggs.json",
    "data/special_research.json",
]

TPL = '''/* 繁簡通用搜尋。
   站上的名稱全是繁體(來源 PokeMiners 只有 i18n_chinesetraditional,沒有簡體),
   所以使用者打「妙蛙种子」會一個字都對不到。

   做法:把「被搜尋的字串」與「使用者輸入」都正規化成簡體再比對。
   方向很重要 —— 繁→簡是多對一(發/髮→发),轉過去只會合併、不會產生歧義;
   反過來簡→繁是一對多,得試所有組合,會爆炸。

   這張表只收「站上資料實際出現、而且繁簡不同」的字({n} 個),不是整套 OpenCC 字典。
   由 scripts/build_zh_table.py 產生,不要手改。 */
(function(){{
  var T2S={tbl};
  // 只在有中文時才逐字轉,英數字的搜尋(charizard、pm25)完全不受影響
  window.zhNorm=function(s){{
    s=String(s==null?'':s);
    if(!/[\\u4e00-\\u9fff]/.test(s)) return s;
    var out='',c;
    for(var i=0;i<s.length;i++){{ c=s[i]; out+=(T2S[c]||c); }}
    return out;
  }};
  // 搜尋一律用這個:小寫 + 繁簡正規化。查詢與被查的字串「兩邊都要過」才對得起來
  window.zhLower=function(s){{ return window.zhNorm(String(s==null?'':s).toLowerCase()); }};
}})();
'''


def main():
    t2s = opencc.OpenCC("t2s")
    chars, missing = set(), []
    for rel in SOURCES:
        p = os.path.join(HERE, rel)
        if not os.path.exists(p):
            missing.append(rel); continue
        chars |= set(re.findall(r"[一-鿿]", open(p, encoding="utf-8").read()))

    m = {}
    for c in sorted(chars):
        s = t2s.convert(c)
        if s != c and len(s) == 1:      # 只收單字對單字,一對多的留給原字(不會更差)
            m[c] = s

    out = os.path.join(HERE, "js", "zh-search.js")
    open(out, "w", encoding="utf-8", newline="\n").write(
        TPL.format(n=len(m), tbl=json.dumps(m, ensure_ascii=False, separators=(",", ":"))))

    print(f"掃過 {len(SOURCES) - len(missing)} 個來源,漢字 {len(chars)} 個")
    print(f"繁簡不同而需要對照的:{len(m)} 個")
    print(f"已寫出 js/zh-search.js({os.path.getsize(out):,} bytes)")
    if missing:
        print("⚠ 找不到(略過):" + ", ".join(missing))


if __name__ == "__main__":
    main()
