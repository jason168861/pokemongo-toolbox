# -*- coding: utf-8 -*-
"""（舊入口）sitemap.xml 的 /events/ 區塊現在由 scripts/build_event_pages.py 一起產生。

events/index.html 已改成預先產生的靜態頁，不再有 window.CD_LIST，所以這支只轉呼叫新的產生器，
避免照舊流程執行時把活動網址從 sitemap 刪掉。
用法：python scripts/build_events_sitemap.py（等同 python scripts/build_event_pages.py）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_event_pages  # noqa: E402

if __name__ == "__main__":
    build_event_pages.main()
