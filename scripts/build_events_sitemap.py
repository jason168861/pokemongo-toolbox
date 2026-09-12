# -*- coding: utf-8 -*-
"""依 events/index.html 的 CD_LIST，自動更新 sitemap.xml 裡的社群日網址。

作法：
  · 讀 events/index.html 的 window.CD_LIST（每筆的 slug / date / endHour）。
  · 移除 sitemap.xml 內既有的所有 /events/ 網址，改插入重新產生的區塊
    （含總覽 /events/ 一筆）。其餘網址原封不動。
  · 冪等：重覆執行結果相同。過去的活動 priority 較低。

用法：
    python scripts/build_events_sitemap.py
新增/修改社群日頁後跑一次即可（見 events/README.md 的流程）。
"""
import io
import os
import re
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HUB = os.path.join(ROOT, "events", "index.html")
SITEMAP = os.path.join(ROOT, "sitemap.xml")
BASE = "https://pogokit.com"


def read(p):
    return io.open(p, encoding="utf-8").read()


def parse_cd_list(html):
    """從 window.CD_LIST = [ ... ]; 取出每筆的 slug / date / endHour。"""
    m = re.search(r"window\.CD_LIST\s*=\s*\[(.*?)\];", html, re.S)
    if not m:
        return []
    body = re.sub(r"//[^\n]*", "", m.group(1))          # 去掉 // 註解（含被註解的範例）
    out = []
    for obj in re.findall(r"\{[^{}]*\}", body, re.S):
        slug = re.search(r"slug\s*:\s*['\"]([^'\"]+)['\"]", obj)
        date = re.search(r"date\s*:\s*['\"]([^'\"]+)['\"]", obj)
        endh = re.search(r"endHour\s*:\s*(\d+)", obj)
        if slug and date:
            out.append({
                "slug": slug.group(1).strip(),
                "date": date.group(1).strip(),
                "endHour": int(endh.group(1)) if endh else 17,
            })
    return out


def lastmod_of(*rel_parts):
    """用檔案的修改時間當 lastmod，抓不到就用今天。"""
    p = os.path.join(ROOT, *rel_parts)
    try:
        return datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d")
    except OSError:
        return datetime.now().strftime("%Y-%m-%d")


def url_block(loc, lastmod, priority):
    return ("  <url>\n"
            "    <loc>%s</loc>\n"
            "    <lastmod>%s</lastmod>\n"
            "    <priority>%s</priority>\n"
            "  </url>\n") % (loc, lastmod, priority)


def build_block(events):
    now = datetime.now()
    parts = ["  <!-- 社群日：由 scripts/build_events_sitemap.py 自動產生，勿手改此區塊 -->\n"]
    parts.append(url_block(BASE + "/events/", lastmod_of("events", "index.html"), "0.8"))
    for e in sorted(events, key=lambda x: x["date"], reverse=True):
        page = os.path.join(ROOT, "events", e["slug"], "index.html")
        if not os.path.exists(page):
            print("  略過（找不到頁面）：%s" % e["slug"])
            continue
        try:
            y, mo, d = (int(x) for x in e["date"].split("-"))
            past = datetime(y, mo, d, e["endHour"]) < now
        except ValueError:
            past = False
        parts.append(url_block(
            "%s/events/%s/" % (BASE, e["slug"]),
            lastmod_of("events", e["slug"], "index.html"),
            "0.5" if past else "0.7"))
    return "".join(parts)


def run():
    events = parse_cd_list(read(HUB))
    xml = read(SITEMAP)
    # 移除既有的所有 /events/ 網址與舊的自動註解
    xml = re.sub(r"[ \t]*<!-- 社群日：[^\n]*\n", "", xml)
    xml = re.sub(r"[ \t]*<url>\s*<loc>" + re.escape(BASE) + r"/events/[^<]*</loc>.*?</url>\s*\n",
                 "", xml, flags=re.S)
    block = build_block(events)
    xml = xml.replace("</urlset>", block + "</urlset>")
    io.open(SITEMAP, "w", encoding="utf-8").write(xml)
    print("已更新 sitemap.xml：社群日網址 %d 筆（＋總覽 1 筆）"
          % sum(1 for e in events if os.path.exists(os.path.join(ROOT, "events", e["slug"], "index.html"))))


if __name__ == "__main__":
    run()
