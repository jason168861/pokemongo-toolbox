#!/usr/bin/env python3
"""產生背卡一覽（/backgrounds/）用的「裁掉透明留白」寶可夢圖。

寶可夢圖示（trade-list/assets/img/*.png，256px）四周留白很多，皮卡丘主體只佔中間約 4 成，
直接縮小放進卡片會小到看不清楚。這支依 alpha 範圍裁掉留白，統一縮成高度 200px 的 webp，
卡片上就能把寶可夢畫得夠大又不糊（手機 2x 螢幕 110px 高 ≈ 220 實際像素）。

    python scripts/build_bg_sprites.py      # 需要 Pillow

輸出：
    trade-list/assets/bgmon/<原檔名>.webp
    trade-list/data/bg_sprites.json         {原始 url: [新 url, 寬, 高]}，build_bg_index.py 讀這份
只處理背卡一覽實際用到的圖；原圖比輸出新（被換過）才重做。跑完再跑 build_bg_index.py。
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_bg_index as B   # 共用 load() / sprite()，確保挑到的圖跟頁面一致

try:
    from PIL import Image
except ImportError:
    sys.exit("需要 Pillow：pip install Pillow")

H = 200          # 輸出高度（寬依比例，最寬 300）
MAX_W = 300
ALPHA = 16       # 跟 trade-list 的 make_trim 一樣，alpha > 16 才算主體
OUT_DIR = os.path.join(B.TL, "assets", "bgmon")
MANIFEST = os.path.join(B.TL, "data", "bg_sprites.json")


def crop(src, dst):
    im = Image.open(src).convert("RGBA")
    mask = im.getchannel("A").point(lambda a: 255 if a > ALPHA else 0)
    box = mask.getbbox()
    if box:
        im = im.crop(box)
    w, h = im.size
    s = min(H / h, MAX_W / w)
    im = im.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
    im.save(dst, "WEBP", quality=80, method=6)
    return im.size


def main():
    bgs, mons, _labels, _alias = B.load()
    urls = set()
    for bg in bgs:
        for p in bg["pokemon"]:
            zh, url = B.sprite(mons, p)
            if zh and url:
                urls.add(url)
    os.makedirs(OUT_DIR, exist_ok=True)
    old = {}
    if os.path.exists(MANIFEST):
        with open(MANIFEST, encoding="utf-8") as f:
            old = json.load(f)
    out, made, miss = {}, 0, []
    for url in sorted(urls):
        src = os.path.join(B.TL, url)
        if not os.path.exists(src):
            miss.append(url)
            continue
        name = os.path.splitext(os.path.basename(url))[0] + ".webp"
        dst = os.path.join(OUT_DIR, name)
        rel = "assets/bgmon/" + name
        if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src) and url in old:
            out[url] = old[url]
            continue
        w, h = crop(src, dst)
        out[url] = [rel, w, h]
        made += 1
    # 不再用到的舊圖刪掉，資料夾只留頁面用得到的
    keep = {os.path.basename(v[0]) for v in out.values()}
    gone = [fn for fn in os.listdir(OUT_DIR) if fn not in keep]
    for fn in gone:
        os.remove(os.path.join(OUT_DIR, fn))
    with open(MANIFEST, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    size = sum(os.path.getsize(os.path.join(OUT_DIR, fn)) for fn in os.listdir(OUT_DIR))
    print(f"背卡寶可夢圖：共 {len(out)} 張（新產生 {made}、刪除 {len(gone)}），合計 {size / 1e6:.1f}MB")
    if miss:
        print(f"  ⚠ 找不到原圖 {len(miss)} 張：{miss[:5]}")


if __name__ == "__main__":
    main()
