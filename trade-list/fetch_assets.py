#!/usr/bin/env python3
"""
把工具用到的所有圖片存到本機,前端一律讀本機檔(不佔來源站流量,也不會因對方策略變動而破圖)。
- 寶可夢 sprite:來自 PokeMiners → assets/img/
- 背卡:來自 Bulbapedia archives / Fandom → assets/bg/
產出 data/pokemon.local.json / data/backgrounds.local.json(url 指向本機),前端讀這兩個。

未來更新:先跑 build_data.py 刷新來源資料,再跑本檔即可 —— sprite 已存在會跳過,背卡一律重抓(抓最新藝術圖)。
"""
import json, os, re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

try:                                    # Windows 主控台預設 cp950,吐中文會炸
    sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "assets", "img")
BGD = os.path.join(HERE, "assets", "bg")
os.makedirs(IMG, exist_ok=True); os.makedirs(BGD, exist_ok=True)
POGO_ASSETS = os.environ.get("POGO_ASSETS", os.path.join(os.path.dirname(os.path.dirname(HERE)), "pogo_assets"))

# 匯出圖樣式(skin)用的官方素材:屬性徽章當浮水印、屬性場景當頁首橫幅、隊徽當隊伍樣式的浮水印。
# 徽章檔名是 badge enum(GAME_MASTER 的 BADGE_TYPE_*:18=一般 … 35=妖精),照順序對應。
TYPE_ORDER = ["normal", "fighting", "flying", "poison", "ground", "rock", "bug", "ghost", "steel",
              "fire", "water", "grass", "electric", "psychic", "ice", "dragon", "dark", "fairy"]
TEAMS = {"team_blue": "mystic", "team_red": "valor", "team_yellow": "instinct"}

def dl(url, path, no_referer=False, force=False, tries=3):
    if os.path.exists(path) and not force and os.path.getsize(path) > 0:
        return "skip"
    # 不送 Referer(urllib 的預設行為)。no_referer 參數保留給語意清楚。
    headers = {"User-Agent": "Mozilla/5.0 asset-fetch"}
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            data = urllib.request.urlopen(req, timeout=60).read()
            if len(data) < 100:  # 疑似錯誤頁
                raise IOError("too small")
            with open(path, "wb") as f: f.write(data)
            return "ok"
        except Exception as e:
            if a == tries - 1: return f"ERR {e}"

def sprite_local(url):
    return os.path.basename(url.split("?")[0])  # pm25.icon.png

def wiki_sprite_local(url):
    """背卡專用的 wiki 造型原圖(本機 PokeMiners 對不到時的兜底):
    Bulbapedia .../GO0025Willow.png、Fandom .../Pikachu_willow.png/revision/latest?cb=…"""
    m = re.search(r"/images/[0-9a-f/]+/([^/]+\.(?:png|jpg|jpeg|webp))/revision", url, re.I)
    name = m.group(1) if m else os.path.basename(url.split("?")[0])
    return "wiki_" + re.sub(r"[^A-Za-z0-9._-]", "_", name)

def bg_local(url):
    m = re.search(r"/images/[0-9a-f/]+/([^/]+\.(?:png|jpg|jpeg|webp))/revision", url, re.I)
    name = m.group(1) if m else os.path.basename(url.split("?")[0])
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)

def main():
    pk = json.load(open(os.path.join(HERE, "data", "pokemon.json"), encoding="utf-8"))
    bg = json.load(open(os.path.join(HERE, "data", "backgrounds.json"), encoding="utf-8"))

    # 收集 sprite url
    sprite_urls = set()
    for p in pk.values():
        for v in p["variants"]: sprite_urls.add(v["url"])
        if p.get("gigantamax"):
            for k in ("normal", "shiny"):
                if p["gigantamax"].get(k): sprite_urls.add(p["gigantamax"][k])

    # 背卡條目裡對不到本機 sprite 的造型,用 wiki 原圖(一樣存到本機)
    wiki_urls = set()
    for b in bg:
        for m in b.get("pokemon", []):
            for k in ("sprite", "sprite_shiny"):
                if m.get(k): wiki_urls.add(m[k])

    jobs = []  # (url, path, no_referer, force)
    for u in sprite_urls:
        jobs.append((u, os.path.join(IMG, sprite_local(u)), False, False))
    for u in wiki_urls:
        jobs.append((u, os.path.join(IMG, wiki_sprite_local(u)), True, False))
    for b in bg:
        if b.get("image_url"):
            jobs.append((b["image_url"], os.path.join(BGD, bg_local(b["image_url"])), True, True))  # 背卡一律重抓

    print(f"要處理:{len(sprite_urls)} sprite + {len(wiki_urls)} wiki 造型圖 + {len(bg)} 背卡 = {len(jobs)} 檔", flush=True)
    ok = skip = err = 0
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = {ex.submit(dl, u, p, nr, fo): u for (u, p, nr, fo) in jobs}
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            if r == "ok": ok += 1
            elif r == "skip": skip += 1
            else: err += 1; print("  ", r, futs[f][-40:], flush=True)
            if i % 400 == 0: print(f"  進度 {i}/{len(jobs)} (ok {ok}/skip {skip}/err {err})", flush=True)

    # 寫出 local 版 JSON(url 指向本機)
    for p in pk.values():
        for v in p["variants"]: v["url"] = "assets/img/" + sprite_local(v["url"])
        if p.get("gigantamax"):
            for k in ("normal", "shiny"):
                if p["gigantamax"].get(k): p["gigantamax"][k] = "assets/img/" + sprite_local(p["gigantamax"][k])
    for b in bg:
        if b.get("image_url"): b["image_url"] = "assets/bg/" + bg_local(b["image_url"])
        for m in b.get("pokemon", []):
            for k in ("sprite", "sprite_shiny"):
                if m.get(k): m[k] = "assets/img/" + wiki_sprite_local(m[k])

    json.dump(pk, open(os.path.join(HERE, "data", "pokemon.local.json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(bg, open(os.path.join(HERE, "data", "backgrounds.local.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"\n完成:ok {ok} / 已存在跳過 {skip} / 失敗 {err}", flush=True)
    print("已寫出 data/pokemon.local.json 與 data/backgrounds.local.json", flush=True)
    make_thumbs()
    make_style_assets()
    make_trim()

def make_thumbs():
    """產生網格用的小 WebP 縮圖(sprite 128px、背卡 220px),大幅加速載入。原圖仍供匯出高解析用。"""
    try:
        from PIL import Image
    except ImportError:
        print("(略過縮圖:未安裝 Pillow,pip install Pillow)", flush=True); return
    import glob
    def gen(srcdir, dstdir, size):
        src = os.path.join(HERE, srcdir); dst = os.path.join(HERE, dstdir); os.makedirs(dst, exist_ok=True)
        ok = 0
        for fn in os.listdir(src):
            if not fn.lower().endswith((".png", ".jpg", ".jpeg", ".webp")): continue
            out = os.path.join(dst, os.path.splitext(fn)[0] + ".webp")
            if os.path.exists(out): continue
            try:
                im = Image.open(os.path.join(src, fn)).convert("RGBA"); im.thumbnail((size, size), Image.LANCZOS)
                im.save(out, "WEBP", quality=82, method=4); ok += 1
            except Exception: pass
        print(f"縮圖 {dstdir}: 新增 {ok}", flush=True)
    gen("assets/img", "assets/thumb", 128)     # 網格/清單用小縮圖
    gen("assets/bg", "assets/bgthumb", 220)    # 網格/清單用背卡縮圖
    gen("assets/bg", "assets/bgexp", 384)      # 匯出 PNG 用中尺寸背卡(原圖動輒 500KB+,卡片只畫 264px)


def make_style_assets():
    """匯出圖樣式用的官方素材,從本機 PokeMiners clone 轉存成小 WebP。

    來源(POGO_ASSETS 底下):
      Images/Badges/Types/Badge_18..35.png      → assets/type/badge_<屬性>.webp   屬性徽章(浮水印)
      Images/Type Backgrounds/details_type_bg_* → assets/type/bg_<屬性>.webp      屬性場景(頁首橫幅)
      Images/Pokestops and Gyms/team_*.png      → assets/team/<隊伍>.webp         隊徽(浮水印)

    原圖加起來約 1.8MB,但都只拿來當低透明度的裝飾 —— 縮到 256/320px 存 WebP 後不到 1/3,
    而且前端只有選到那個樣式時才會下載。
    """
    try:
        from PIL import Image
    except ImportError:
        print("(略過樣式素材:未安裝 Pillow)", flush=True); return
    src_badge = os.path.join(POGO_ASSETS, "Images", "Badges", "Types")
    src_tbg   = os.path.join(POGO_ASSETS, "Images", "Type Backgrounds")
    src_team  = os.path.join(POGO_ASSETS, "Images", "Pokestops and Gyms")
    if not os.path.isdir(src_badge):
        print(f"(略過樣式素材:找不到 {src_badge},請設 POGO_ASSETS)", flush=True); return
    dst_t = os.path.join(HERE, "assets", "type"); os.makedirs(dst_t, exist_ok=True)
    dst_m = os.path.join(HERE, "assets", "team"); os.makedirs(dst_m, exist_ok=True)

    def conv(src, out, size, q):
        if not os.path.exists(src): return None
        im = Image.open(src).convert("RGBA")
        im.thumbnail((size, size), Image.LANCZOS)
        im.save(out, "WEBP", quality=q, method=6)
        return os.path.getsize(out)

    total = n = 0
    for i, t in enumerate(TYPE_ORDER):
        s = conv(os.path.join(src_badge, f"Badge_{18+i}.png"), os.path.join(dst_t, f"badge_{t}.webp"), 256, 84)
        if s: total += s; n += 1
        s = conv(os.path.join(src_tbg, f"details_type_bg_{t}.png"), os.path.join(dst_t, f"bg_{t}.webp"), 256, 76)
        if s: total += s; n += 1
    for f, team in TEAMS.items():
        s = conv(os.path.join(src_team, f + ".png"), os.path.join(dst_m, f"{team}.webp"), 320, 84)
        if s: total += s; n += 1
    print(f"樣式素材 assets/type + assets/team:{n} 檔 / {total//1024} KB", flush=True)


def make_trim():
    """算出每張 sprite 的「不透明範圍」(去透明邊用),存成 data/trim.json。

    前端本來是即時用 canvas getImageData 掃描算的,但那是一趟 GPU→CPU 同步讀回:
    實測手機等級 CPU 每張約 1.9ms,滑過 2500 張就是 5 秒主執行緒時間,捲動明顯卡頓
    (而且降低掃描解析度也沒用 —— 貴的是讀回這個動作本身,不是像素數量)。
    這裡用 Pillow 一次算好:比即時掃描更準(全解析度,不是縮到 96px),前端只要查表。
    輸出的是比例(0~1),所以縮圖與原圖共用同一份;key 是去副檔名的檔名,
    assets/thumb/pm25.s.icon.webp 與 assets/img/pm25.s.icon.png 都對得到 pm25.s.icon。
    """
    try:
        from PIL import Image
    except ImportError:
        print("(略過 trim.json:未安裝 Pillow)", flush=True); return
    src = os.path.join(HERE, "assets", "img")
    out, skipped = {}, 0
    for fn in sorted(os.listdir(src)):
        if not fn.lower().endswith((".png", ".jpg", ".jpeg", ".webp")): continue
        try:
            im = Image.open(os.path.join(src, fn)).convert("RGBA")
            w, h = im.size
            # 與前端同一個門檻:alpha > 16 才算主體
            box = im.getchannel("A").point(lambda a: 255 if a > 16 else 0).getbbox()
            if not box: skipped += 1; continue          # 整張透明 → 不裁
            x0, y0, x1, y1 = box
            out[os.path.splitext(fn)[0]] = [round(x0 / w, 4), round(y0 / h, 4),
                                            round((x1 - x0) / w, 4), round((y1 - y0) / h, 4)]
        except Exception:
            skipped += 1
    p = os.path.join(HERE, "data", "trim.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"去邊範圍 data/trim.json: {len(out)} 筆"
          f"{f'(略過 {skipped})' if skipped else ''} / {os.path.getsize(p)//1024} KB", flush=True)


if __name__ == "__main__":
    main()
