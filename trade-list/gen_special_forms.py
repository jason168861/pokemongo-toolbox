#!/usr/bin/env python3
"""特殊型態的顯示素材:至尊(Apex)的金色光暈 sprite、黃昏岩狗狗的進化徽章。

設定在 data/special_forms.json(手動維護,build_data.py / fetch_assets.py 不會碰)。

    python gen_special_forms.py           # 只補缺的
    python gen_special_forms.py --force   # 全部重畫(改了特效參數時)

為什麼要另外畫:
  * 至尊洛奇亞 / 鳳王(form S)的 sprite 跟一般版只差姿勢,不熟的人分不出來;
    遊戲裡的至尊特效是執行時才下載的素材,APK 與 PokeMiners 都沒有 → 自己畫一個金色外光暈 + 星光。
  * 黃昏岩狗狗(form DUSK)的 sprite 跟一般岩狗狗「逐像素完全一樣」,只能靠徽章區分 →
    右上角放它進化後的黃昏鬃岩狼人(異色對異色),跟遊戲圖鑑網站的標法一樣。

產出(檔名是 index.html 讀的慣例,改名要兩邊一起改):
    fx: "apex"  → assets/img/fx_<sprite 檔名>            256px PNG,光暈與星光已烘進去
                  assets/thumb/fx_<sprite 檔名>.webp     128px 網格縮圖(thumbOf 的對應規則)
    badge_evo   → assets/badge_evo_<進化後 sprite 檔名>   128px 圓形徽章
sprite 一律讀本機 assets/img(fetch_assets.py 下載好的),不需要 PokeMiners clone。
畫法只由 sprite 本身決定(沒有亂數),重跑結果一樣,git 不會出現無意義的 diff。
"""
import argparse, json, math, os, sys

from PIL import Image, ImageDraw, ImageFilter

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
SIZE = 256


def P(*parts):
    return os.path.join(HERE, *parts)


def load_data(name):
    for fn in (f"{name}.local.json", f"{name}.json"):
        p = P("data", fn)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    sys.exit(f"找不到 data/{name}.json,先跑 build_data.py / fetch_assets.py")


def fname(url):
    return url.split("/")[-1].split("?")[0]


def variants_of(poke, dex, form):
    """跟 index.html 的 loadSpecialForms 同一條規則:同 dex、form 代碼完全相同。"""
    p = poke.get(str(dex))
    if not p:
        return []
    return [v for v in p["variants"] if (v.get("form") or None) == (form or None)]


# ---------------- 至尊:金色外光暈 + 星光 ----------------
def star(canvas, cx, cy, r, rgb):
    """四角星 + 柔光。4 倍超取樣再縮回來,邊緣才不會鋸齒。"""
    ss = 4
    R = max(2, int(r * ss))
    big = Image.new("RGBA", (R * 4, R * 4), (0, 0, 0, 0))
    c = R * 2
    pts = []
    for i in range(8):
        ang = math.pi / 4 * i - math.pi / 2
        rad = R if i % 2 == 0 else R * 0.22
        pts.append((c + rad * math.cos(ang), c + rad * math.sin(ang)))
    ImageDraw.Draw(big).polygon(pts, fill=rgb + (255,))
    glow = big.split()[3].filter(ImageFilter.GaussianBlur(R * 0.35)).point(lambda v: min(255, int(v * 1.4)))
    halo = Image.new("RGBA", big.size, rgb + (0,))
    halo.putalpha(glow)
    halo.alpha_composite(big)
    halo = halo.resize((R * 4 // ss, R * 4 // ss), Image.LANCZOS)
    canvas.alpha_composite(halo, (int(cx - halo.width / 2), int(cy - halo.height / 2)))


def apex_fx(sprite):
    sp = sprite.convert("RGBA")
    if sp.size != (SIZE, SIZE):
        sp = sp.resize((SIZE, SIZE), Image.LANCZOS)
    # 先縮到 82% 置中,四周留位子給光暈 —— 原圖主體常貼到邊,不縮的話外光暈會被 256 的邊切掉
    k = 0.82
    w = int(SIZE * k)
    base = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    base.alpha_composite(sp.resize((w, w), Image.LANCZOS), ((SIZE - w) // 2, (SIZE - w) // 2))

    a = base.split()[3]
    grow = (a.filter(ImageFilter.MaxFilter(17))
             .filter(ImageFilter.GaussianBlur(11))
             .point(lambda v: min(255, int(v * 2.2))))
    glow = Image.new("RGBA", base.size, (255, 196, 64, 0))
    glow.putalpha(grow)

    out = Image.new("RGBA", base.size, (0, 0, 0, 0))
    out.alpha_composite(glow)
    out.alpha_composite(base)

    # 星光貼著主體外框的四個角附近(由 bbox 決定,不是畫布角落 → 大小不同的寶可夢看起來一致)
    x0, y0, x1, y1 = a.getbbox() or (0, 0, SIZE, SIZE)
    bw, bh = x1 - x0, y1 - y0
    clamp = lambda v: max(12, min(SIZE - 12, v))
    for fx, fy, r in ((0.06, 0.08, 13), (0.95, 0.16, 10), (0.90, 0.88, 12), (0.10, 0.90, 8), (0.62, -0.02, 7)):
        star(out, clamp(x0 + bw * fx), clamp(y0 + bh * fy), r, (255, 240, 170))
    return out


# ---------------- 黃昏:進化後樣子的圓形徽章 ----------------
def evo_badge(evo, D=128):
    ss = 4
    big = D * ss
    b = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    dr = ImageDraw.Draw(b)
    dr.ellipse((0, 0, big - 1, big - 1), fill=(60, 64, 90, 255))          # 深色細外框:淺色背卡上也看得出圓
    m = int(big * 0.04)
    dr.ellipse((m, m, big - 1 - m, big - 1 - m), fill=(255, 255, 255, 255))
    m2 = int(big * 0.085)
    dr.ellipse((m2, m2, big - 1 - m2, big - 1 - m2), fill=(236, 240, 248, 255))

    evo = evo.convert("RGBA")
    bb = evo.split()[3].getbbox()
    if bb:
        evo = evo.crop(bb)
    inner = big - 2 * m2
    s = inner * 0.98 / max(evo.size)
    evo = evo.resize((max(1, int(evo.width * s)), max(1, int(evo.height * s))), Image.LANCZOS)
    layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    layer.alpha_composite(evo, ((big - evo.width) // 2, (big - evo.height) // 2 + int(inner * 0.04)))
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).ellipse((m2, m2, big - 1 - m2, big - 1 - m2), fill=255)
    layer.putalpha(Image.composite(layer.split()[3], Image.new("L", (big, big), 0), mask))
    b.alpha_composite(layer)
    return b.resize((D, D), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser(description="產生特殊型態的顯示素材")
    ap.add_argument("--force", action="store_true", help="已存在的也重畫")
    args = ap.parse_args()

    with open(P("data", "special_forms.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    poke = load_data("pokemon")
    made = skipped = problems = 0

    def need(*paths):
        return args.force or not all(os.path.exists(p) for p in paths)

    for e in cfg.get("forms", []):
        tag = f"#{e['dex']} form={e.get('form')}"
        vs = variants_of(poke, e["dex"], e.get("form"))
        if not vs:
            print(f"  ⚠ {tag}:pokemon.json 裡找不到這個型態(資料改了?)")
            problems += 1
            continue
        for v in vs:
            if e.get("no_shiny") and v.get("shiny"):
                continue                                   # 遊戲裡沒有異色(至尊洛奇亞 / 鳳王)→ 不畫
            f = fname(v["url"])
            src = P("assets", "img", f)

            if e.get("fx") == "apex":
                out = P("assets", "img", "fx_" + f)
                th = P("assets", "thumb", "fx_" + os.path.splitext(f)[0] + ".webp")
                if need(out, th):
                    if not os.path.exists(src):
                        print(f"  ⚠ {tag}:缺 sprite {src}(先跑 fetch_assets.py)")
                        problems += 1
                    else:
                        im = apex_fx(Image.open(src))
                        im.save(out, optimize=True)
                        t = im.copy()
                        t.thumbnail((128, 128), Image.LANCZOS)
                        os.makedirs(os.path.dirname(th), exist_ok=True)
                        t.save(th, "WEBP", quality=86, method=6)
                        print(f"  ✔ 至尊光暈 {os.path.relpath(out, HERE)}")
                        made += 1
                else:
                    skipped += 1

            be = e.get("badge_evo")
            if be:
                evs = [x for x in variants_of(poke, be["dex"], be.get("form"))
                       if bool(x.get("shiny")) == bool(v.get("shiny")) and not x.get("gender")]
                if not evs:
                    print(f"  ⚠ {tag}:找不到進化後 #{be['dex']} form={be.get('form')} 的{'異色' if v.get('shiny') else '一般'}圖")
                    problems += 1
                    continue
                ef = fname(evs[0]["url"])
                out = P("assets", "badge_evo_" + ef)
                esrc = P("assets", "img", ef)
                if need(out):
                    if not os.path.exists(esrc):
                        print(f"  ⚠ {tag}:缺進化後 sprite {esrc}")
                        problems += 1
                    else:
                        evo_badge(Image.open(esrc)).save(out, optimize=True)
                        print(f"  ✔ 進化徽章 {os.path.relpath(out, HERE)}")
                        made += 1
                else:
                    skipped += 1

    print(f"[特殊型態] 新產生 {made} / 已存在略過 {skipped} / 問題 {problems}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
