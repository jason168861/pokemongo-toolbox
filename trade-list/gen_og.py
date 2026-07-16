#!/usr/bin/env python3
"""產生社群分享用的 Open Graph 圖(assets/brand/og.png,1200x630)。
被 index.html 的 og:image / twitter:image 引用。日後想改字或換寶可夢再跑一次即可。
需要:Pillow;字型走 Windows 內建(msjhbd/arialbd)。
"""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1200, 630
FONTS = "C:/Windows/Fonts/"

def font(name, size, index=0):
    return ImageFont.truetype(FONTS + name, size, index=index)

# 背景漸層(深色霓虹,呼應工具預設主題)
top, bot = (15, 18, 32), (26, 31, 54)
img = Image.new("RGB", (W, H), top)
px = img.load()
for y in range(H):
    t = y / H
    r = int(top[0] + (bot[0] - top[0]) * t)
    g = int(top[1] + (bot[1] - top[1]) * t)
    b = int(top[2] + (bot[2] - top[2]) * t)
    for x in range(W):
        px[x, y] = (r, g, b)

# 左上角紫/粉光暈
glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gd = ImageDraw.Draw(glow)
gd.ellipse([-260, -320, 520, 360], fill=(123, 92, 255, 60))
gd.ellipse([760, 300, 1400, 820], fill=(224, 39, 108, 45))
img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
d = ImageDraw.Draw(img)

PAD = 70
# 小標
d.text((PAD, 92), "POKÉMON GO", font=font("arialbd.ttf", 34), fill=(224, 39, 108))
# 主標(英文)
d.text((PAD, 140), "Trade List Maker", font=font("arialbd.ttf", 96), fill=(238, 240, 251))
# 中文副標
d.text((PAD, 258), "交易清單產生器", font=font("msjhbd.ttc", 60), fill=(180, 190, 230))
# 功能說明
d.text((PAD, 344), "Shiny · Forms · Costumes · Dynamax · Backgrounds",
       font=font("arialbd.ttf", 34), fill=(154, 163, 199))
d.text((PAD, 392), "→ export a shareable image · 7 languages · free",
       font=font("arialbd.ttf", 30), fill=(123, 92, 255))

# 底部一排寶可夢圖示
icons = ["pm25", "pm6", "pm149", "pm150", "pm384", "pm445", "pm448", "pm282"]
size, gap, y = 118, 14, H - 118 - 46
x = PAD
for name in icons:
    p = os.path.join(HERE, "assets", "img", name + ".icon.png")
    if not os.path.exists(p):
        continue
    sp = Image.open(p).convert("RGBA").resize((size, size), Image.LANCZOS)
    img.paste(sp, (x, y), sp)
    x += size + gap
    if x + size > W - PAD:
        break

# 網址(右下)
url = "jason168861.github.io/pokemongo-toolbox"
uf = font("arialbd.ttf", 26)
tw = d.textlength(url, font=uf)
d.text((W - PAD - tw, 96), url, font=uf, fill=(122, 132, 170))

out = os.path.join(HERE, "assets", "brand", "og.png")
os.makedirs(os.path.dirname(out), exist_ok=True)
img.save(out, "PNG")
print("已產生", out, img.size)
