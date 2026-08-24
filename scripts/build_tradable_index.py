#!/usr/bin/env python3
"""產生 tradable/index.html —— 哪些寶可夢不能交換。

資料來源是 PokeMiners 鏡像的 GAME_MASTER（遊戲本身的設定檔），
判斷邏輯跟 trade-list/build_data.py 的 _trad() / tradable() 一致。

⚠ 那兩個函式在 build_data.py 才是正本。這裡是複製過來的 ——
  複製的原因是 build_data.py 跑起來需要一整份本機 sprite dump，
  只為了產生這一頁不值得。為了避免兩邊悄悄長歪，最後會做一次
  交叉檢查：pokemon.local.json 裡的每一隻都必須被這裡判為可交換，
  對不上就印警告。改 build_data.py 的交換邏輯時，記得同步這裡。

    python scripts/build_tradable_index.py
"""
import json, os, re, html, glob, collections, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TL = os.path.join(HERE, "trade-list")
OUT_DIR = os.path.join(HERE, "tradable")
OUT = os.path.join(OUT_DIR, "index.html")
GM_URL = "https://raw.githubusercontent.com/PokeMiners/game_masters/master/latest/latest.json"
ASSET = "../trade-list/"

e = html.escape

CLASS_ZH = {
    "POKEMON_CLASS_MYTHIC": "幻之寶可夢",
    "POKEMON_CLASS_LEGENDARY": "傳說寶可夢",
    "POKEMON_CLASS_ULTRA_BEAST": "究極異獸",
}


# --- 以下兩個函式與 build_data.py 同步 -------------------------------------
def _trad(ps):
    """單一型態的 isTradable。

    GAME_MASTER 對某些型態根本沒寫這個欄位，不能一律當成 False ——
    王之劍蒼響 / 王之盾藏瑪然特就是這樣（欄位缺席，但 isTransferable 是 true），
    實際遊戲裡可以交換。真正鎖住的合體型態則是「兩個欄位一起缺席」。
    """
    t = ps.get("isTradable")
    if t is not None:
        return bool(t)
    return None if ps.get("isTransferable") else False


def make_tradable(tr):
    def tradable(dex, form=None):
        """GM 沒收錄這隻/這個型態就當作可交換。"""
        t = tr.get(dex)
        if not t:
            return True
        v = t.get(form)
        if v is None:
            v = t.get(None)
        return v is True
    return tradable
# ---------------------------------------------------------------------------


def load_gm():
    print("抓 GAME_MASTER…")
    with urllib.request.urlopen(GM_URL, timeout=180) as r:
        gm = json.load(r)
    print(f"  {len(gm):,} 筆模板")
    tr, cls = collections.defaultdict(dict), {}
    for ent in gm:
        m = re.match(r"V(\d+)_POKEMON_", ent.get("templateId", ""))
        ps = ent.get("data", {}).get("pokemonSettings")
        if not (m and ps):
            continue
        dex = int(m.group(1))
        sp, f = ps.get("pokemonId", ""), ps.get("form") or ""
        form = f[len(sp) + 1:] if f.startswith(sp + "_") else (f or None)
        tr[dex][form] = _trad(ps)
        if ps.get("pokemonClass"):
            cls.setdefault(dex, ps["pokemonClass"])
    return dict(tr), cls


def load_names():
    with open(os.path.join(TL, "data", "names", "zh.json"), encoding="utf-8") as f:
        zh = json.load(f)
    with open(os.path.join(TL, "data", "pokemon.local.json"), encoding="utf-8") as f:
        mons = json.load(f)
    # 型態的中文名。站上本來就有一份（主站的圖鑑清單），直接沿用，
    # 才不會在頁面上出現 DAWN_WINGS 這種原始代碼。
    forms = {}
    with open(os.path.join(HERE, "data", "pokedex_manifest.json"), encoding="utf-8") as f:
        for mon in json.load(f)["pokemon"]:
            for v in mon["variants"]:
                if v.get("form") and v.get("label"):
                    forms.setdefault((mon["dex"], v["form"]), v["label"])
    return zh, mons, forms


def sprite_path(dex):
    """非交換的寶可夢不在 pokemon.local.json 裡，但 sprite dump 抓的範圍比較大，
    圖通常還是有。

    有幾隻沒有「無型態」的圖，只有分型態的檔（凱路迪歐只有 fORDINARY、
    蓋諾賽克特只有 fBURN/fCHILL…）。那種就退而求其次挑第一個非異色的型態圖，
    不然清單上會出現幾個空格。真的找不到才不放圖（不要給出 404 的 <img>）。
    """
    rel = f"assets/img/pm{dex}.icon.png"
    if os.path.exists(os.path.join(TL, rel)):
        return rel
    cands = sorted(glob.glob(os.path.join(TL, "assets", "img", f"pm{dex}.f*.icon.png")))
    cands = [c for c in cands if ".s.icon.png" not in c]
    return os.path.relpath(cands[0], TL).replace(os.sep, "/") if cands else None


def row(dex, name, note=""):
    sp = sprite_path(dex)
    img = (f'<img src="{e(ASSET + sp)}" alt="{e(name)}" width="56" height="56" loading="lazy" decoding="async">'
           if sp else '<span class="noimg">—</span>')
    return (f'<li>{img}<span class="dex">#{dex}</span>'
            f'<span class="nm">{e(name)}</span>'
            f'{f"<span class=note>{e(note)}</span>" if note else ""}</li>')


def build():
    tr, cls = load_gm()
    tradable = make_tradable(tr)
    zh, mons, forms = load_names()

    def nm(dex):
        n = zh.get(str(dex))
        if n and n != "--":
            return n
        ent = mons.get(str(dex))
        return (ent or {}).get("zh") or f"#{dex}"

    # 1) 整隻不能換
    blocked = [d for d in sorted(tr) if not tradable(d)]
    # 2) 幻之寶可夢裡「可以」換的例外 —— 最容易被誤會的一群
    myth_ok = [d for d in sorted(cls)
               if cls[d] == "POKEMON_CLASS_MYTHIC" and tradable(d) and sprite_path(d)]
    # 3) 基本型可換、但特定型態不能換
    form_blocked = []
    for d in sorted(tr):
        if not tradable(d):
            continue
        bad = sorted(f for f in tr[d] if f and not tradable(d, f))
        if bad:
            form_blocked.append((d, bad))

    # --- 交叉檢查：交易清單收錄的每一隻都必須被判為可交換 ---
    drift = [d for d in mons if not tradable(int(d))]
    if drift:
        print(f"  ⚠ 與 build_data.py 判斷不一致的有 {len(drift)} 隻:{drift[:10]}")
    else:
        print(f"  交叉檢查通過:pokemon.local.json 的 {len(mons)} 隻全部判為可交換")

    blocked_html = "\n".join(row(d, nm(d), CLASS_ZH.get(cls.get(d), "")) for d in blocked)
    myth_html = "\n".join(row(d, nm(d)) for d in myth_ok)
    # manifest 沒收錄的型態補在這裡。目前只有一個：奈克洛茲瑪的 ULTRA。
    # 之後 manifest 補上了就可以刪掉這行（forms 會優先）。
    EXTRA_FORM_ZH = {(800, "ULTRA"): "究極奈克洛茲瑪"}

    def form_zh(dex, code):
        """有中文名就用中文名，兩邊都沒有才退回原始代碼（總比不顯示好）。"""
        return forms.get((dex, code)) or EXTRA_FORM_ZH.get((dex, code), code)

    form_html = "\n".join(
        f'<li><span class="dex">#{d}</span><span class="nm">{e(nm(d))}</span>'
        f'<span class="note">{e("、".join(form_zh(d, b) for b in bad))} 不可交換</span></li>'
        for d, bad in form_blocked)

    desc = (f"Pokémon GO 有 {len(blocked)} 隻寶可夢完全不能交換，另有 {len(form_blocked)} 隻只有特定型態不能換。"
            f"本頁依遊戲設定檔 GAME_MASTER 的 isTradable 欄位整理，並列出常被誤會的例外。")

    ld = json.dumps({
        "@context": "https://schema.org", "@type": "Article",
        "headline": "Pokémon GO 哪些寶可夢不能交換",
        "description": desc, "inLanguage": "zh-Hant",
        "mainEntityOfPage": "https://pogokit.com/tradable/",
    }, ensure_ascii=False)

    page = f'''<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8866689605007086" crossorigin="anonymous"></script>
<script src="../js/zh-search.js"></script>
<script src="../js/analytics.js"></script>
<script src="../config.js"></script>
<script src="../js/pageview-counter.js" defer></script>
<link rel="icon" type="image/png" sizes="192x192" href="../img/masterball.png">
<title>Pokémon GO 哪些寶可夢不能交換？完整清單與例外｜Pokémon Go 工具箱</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="https://pogokit.com/tradable/">
<meta name="robots" content="index,follow">
<meta property="og:type" content="article">
<meta property="og:title" content="Pokémon GO 哪些寶可夢不能交換？完整清單與例外">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="https://pogokit.com/tradable/">
<script type="application/ld+json">{ld}</script>
<link rel="stylesheet" href="../backgrounds/style.css">
<link rel="stylesheet" href="style.css">
</head>
<body>
<header class="topbar">
  <a class="home" href="../">← Pokémon Go 工具箱</a>
  <a class="cta" href="../trade-list/">🔴 做交換清單</a>
</header>

<main>
  <article class="page">
    <h1>Pokémon GO 哪些寶可夢不能交換？</h1>

    <p class="lede">絕大多數寶可夢都可以交換，所以與其背「哪些能換」，不如記住
    <strong>不能換的那 {len(blocked)} 隻</strong>。這一頁就是那份清單，
    以及幾個常被誤會、其實換得到的例外。</p>

    <p>判斷依據是遊戲設定檔（GAME_MASTER）裡每隻寶可夢的 <code>isTradable</code> 欄位，
    不是玩家整理的名單，所以會隨遊戲更新自動跟著變。
    <a href="../trade-list/">交易清單產生器</a>用的是同一份判斷 ——
    列不出來的寶可夢，就是換不到的。</p>

    <div class="stats">
      <div><b>{len(blocked)}</b><span>完全不能換</span></div>
      <div><b>{len(form_blocked)}</b><span>特定型態不能換</span></div>
      <div><b>{len(myth_ok)}</b><span>可以換的幻之寶可夢</span></div>
      <div><b>{len(mons):,}</b><span>可交換（含型態造型）</span></div>
    </div>

    <section>
      <h2>完全不能交換的寶可夢</h2>
      <p>幾乎都是幻之寶可夢 —— 這類只能靠特殊調查或活動取得，官方一律鎖住交換。
      另外兩隻是能量型態受限的傳說寶可夢。</p>
      <ul class="mlist">
{blocked_html}
      </ul>
    </section>

    <section>
      <h2>例外：這些幻之寶可夢可以交換</h2>
      <p>「幻之寶可夢不能交換」是很常見的誤解。實際上遊戲設定檔裡，下面這幾隻是開放交換的 ——
      如果你手上有多的，是可以拿來換東西的。</p>
      <ul class="mlist">
{myth_html}
      </ul>
    </section>

    <section>
      <h2>只有特定型態不能交換</h2>
      <p>這幾隻本體換得到，但合體之後的型態換不了。要交換的話得先解除合體。</p>
      <ul class="mlist plain">
{form_html}
      </ul>
    </section>

    <h2>這份清單是怎麼判定的</h2>
    <p>每隻寶可夢在 GAME_MASTER 裡都有一組設定，其中 <code>isTradable</code> 直接寫明能不能交換。
    本頁逐一讀取這個欄位產生，沒有人工維護的名單，所以不會因為漏更新而過期。</p>
    <p>不過有一個地方不能照字面讀：<strong>部分型態根本沒有寫這個欄位</strong>。
    如果一律當成「不能換」，蒼響的王之劍型態、藏瑪然特的王之盾型態就會被誤判 ——
    它們的欄位缺席，但另一個欄位 <code>isTransferable</code>（能不能傳送給博士）是開的，
    實際遊戲裡也換得到。真正被鎖住的合體型態則是兩個欄位一起缺席。
    所以判斷方式是：欄位缺席但可傳送 → 沿用該寶可夢基本型的設定；兩個都缺席 → 不可交換。</p>
    <p class="caveat">資料隨 GAME_MASTER 更新，可能與遊戲內當下狀態有短暫落差。
    尚未在 Pokémon GO 實裝的寶可夢即使設定檔裡標為可交換，遊戲內也還取得不到。</p>

    <section class="next">
      <h2>做一張交換清單</h2>
      <p>確認想要的寶可夢換得到之後，可以用<a href="../trade-list/">交易清單產生器</a>
      把它們挑成一張圖片，分成「我想要的」和「我能提供的」貼給對方。
      清單裡本來就過濾掉不可交換的寶可夢，不會做出換不到的清單。</p>
      <p><a class="bigcta" href="../trade-list/">🔴 開始製作交換清單</a></p>
    </section>
  </article>
</main>

<footer class="foot">
  <p>交換限制依遊戲設定檔（GAME_MASTER）判定，非官方資料，可能與遊戲內當下狀態有落差。</p>
  <p>本站為非官方同人工具，與 Pokémon GO／Niantic 無隸屬關係。
     Pokémon 及其商標為 &copy;1995-2026 Nintendo, Creatures, GAME FREAK 所有。</p>
  <p><a href="../about/">關於本站</a> · <a href="../contact/">聯絡我們</a> · <a href="../privacy/">隱私權政策</a> · <a href="../disclaimer/">免責聲明</a> · <a href="../">回工具箱</a></p>
</footer>
</body>
</html>
'''
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)

    print(f"已寫出 tradable/index.html（{os.path.getsize(OUT):,} bytes）")
    print(f"  完全不可交換 {len(blocked)} 隻、特定型態不可交換 {len(form_blocked)} 隻、"
          f"可交換的幻之寶可夢 {len(myth_ok)} 隻")
    nopic = [d for d in blocked if not sprite_path(d)]
    if nopic:
        print(f"  ⚠ 沒有圖示的:{[nm(d) for d in nopic]}")


if __name__ == "__main__":
    build()
