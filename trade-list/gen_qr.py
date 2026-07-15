#!/usr/bin/env python3
"""重新產生匯出圖右下角的推廣 QR(assets/brand/qr.png)。
日後若網址改變(例如換成自訂網域),改下面的 URL 再跑一次即可。
需要:pip install segno
"""
import os, segno

URL = "https://jason168861.github.io/pokemongo-toolbox/trade-list/"

HERE = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(HERE, "assets", "brand", "qr.png")
os.makedirs(os.path.dirname(out), exist_ok=True)
segno.make(URL, error="h").save(out, scale=12, border=2, dark="#111111", light="#ffffff")
print("已產生", out, "→", URL)
