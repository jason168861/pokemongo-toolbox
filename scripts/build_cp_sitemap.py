#!/usr/bin/env python3
"""為 CP 查詢器產生「每隻寶可夢一個網址」的 sitemap（sitemap-cp.xml）。

讓 Google 能收錄 ?tab=cp-checker-app&mon=<名稱> 這種深連結，
使用者搜「皮卡丘 iv100 cp」就有機會搜到並直接開到該寶可夢的查詢結果。

來源：data/precomputed_pokemon_cp.js 裡的 POKEMON_CP_DATA（名稱清單）。
輸出：sitemap-cp.xml（repo 根目錄）。
在 CI（deploy.yml）中執行；本機也可手動跑。
"""
import ast
import os
from datetime import date
from urllib.parse import quote
from xml.sax.saxutils import escape

SITE = "https://jason168861.github.io/pokemongo-toolbox/"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "precomputed_pokemon_cp.js")
OUT = os.path.join(ROOT, "sitemap-cp.xml")


def load_names():
    text = open(SRC, encoding="utf-8").read()
    arr = ast.literal_eval(text[text.index("["):text.rindex("]") + 1])  # 單引號字典 → Python 字面值
    names, seen = [], set()
    for p in arr:
        n = (p.get("name") or "").strip()
        if n and n not in seen:
            seen.add(n)
            names.append(n)
    return names


def main():
    names = load_names()
    today = date.today().isoformat()
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for n in names:
        # mon 用名稱（UTF-8 編碼）；XML 內 & 需寫成 &amp;
        loc = SITE + "?tab=cp-checker-app&mon=" + quote(n)
        lines.append("  <url><loc>" + escape(loc) + "</loc>"
                     "<lastmod>" + today + "</lastmod>"
                     "<changefreq>monthly</changefreq><priority>0.5</priority></url>")
    lines.append("</urlset>\n")
    open(OUT, "w", encoding="utf-8").write("\n".join(lines))
    print(f"已產生 {OUT}，共 {len(names)} 個寶可夢網址")


if __name__ == "__main__":
    main()
