#!/usr/bin/env python3
"""產生「偽百查詢」頁 /fake-hundo/。

偽百：練滿（Lv40／Lv50／最佳夥伴 Lv51）時，15/15/14 的 HP 與 15/15/15 完全相同。
攻擊、防禦 IV 本來就一樣，HP 又因無條件捨去而相同，所以實際數值和 100% 一模一樣。

    HP = floor((耐力種族值 + 耐力 IV) × CPM[等級])

資料：data/precomputed_pokemon_cp.js（refresh_cp_data.py 從 GAME_MASTER 更新的種族值）＋ build_cp_static 的 CPM。
傳說／幻之／究極異獸與「還能進化」的標籤取自 pvpoketw gamemaster（抓不到就不標，頁面照常產生）。

    python scripts/build_fake_hundo.py      （CI 由 build_pvp_league.py 結束時呼叫；種族值或新寶可夢一變就自動更新）

名單有變才改頁面上的日期（data/fake_hundo_state.json），並同步 sitemap.xml 這個網址的 <lastmod>。
"""
import hashlib, html, json, os, re, sys
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_cp_static as B  # noqa: E402
import build_pvp_league as L  # noqa: E402

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "fake-hundo", "index.html")
STATE = os.path.join(ROOT, "data", "fake_hundo_state.json")
URL = "https://pogokit.com/fake-hundo/"
LEVELS = (40, 50, 51)
GM_URL = "https://pvpoketw.com/data/gamemaster.json"
e = lambda s: html.escape(str(s), quote=True)


def hp(p, lv, s):
    return B.hp_iv(p, lv, s)


def is_fake(p, lv):
    return hp(p, lv, 14) == hp(p, lv, 15)


def load_tags():
    """speciesId → (標籤集合, 是否還能進化)。抓不到就回傳空 dict。"""
    try:
        import requests
        gm = requests.get(GM_URL, timeout=30, headers={"User-Agent": "pogokit.com data build"}).json()
    except Exception as ex:  # noqa: BLE001
        print(f"  ⚠ 讀不到 gamemaster（{ex}），這次不標傳說／未進化")
        return {}
    return {p["speciesId"]: (set(p.get("tags", [])), bool((p.get("family") or {}).get("evolutions")))
            for p in gm.get("pokemon", [])}


def species_id(p):
    tok = p["gm"].split("_POKEMON_", 1)[1].lower()
    return re.sub(r"_alola$", "_alolan", tok)


def lookup(tags, sid):
    """遊戲代號與 PvPoke speciesId 寫法不完全一樣（giratina→giratina_altered、chienpao→chien_pao、mewtwo_a→mewtwo_armored），
    對不到時退回前綴比對；都對不到就不標。"""
    sid = re.sub(r"_normal$", "", sid).replace("mewtwo_a", "mewtwo_armored")
    if sid in tags:
        return tags[sid]
    flat = sid.replace("_", "")
    for k in sorted(tags):
        if "_shadow" in k:
            continue
        if k.startswith(sid + "_") or k.replace("_", "").startswith(flat):
            return tags[k]
    return set(), False


def mon_link(name):
    """從 /fake-hundo/ 連到這隻的 CP 頁（有靜態頁連靜態頁，否則 ?mon= 深連結，編碼與 sitemap 一致）。"""
    s = B.SLUG_OF.get(name)
    return f"../cp/{s}/" if s else "../?tab=cp-checker-app&mon=" + quote(name)


def thumb(p):
    img = L.local_img(p.get("imageUrl", ""), p["id"])
    return img.replace("../../", "../", 1) if img.startswith("../../") else img


def build():
    tags = load_tags()
    mons = sorted(B.CP_DATA.values(), key=lambda p: (p["id"], p["name"]))
    rows, allrows = [], []
    for p in mons:
        f = {lv: is_fake(p, lv) for lv in LEVELS}
        t, evolves = lookup(tags, species_id(p))
        legend = bool(t & {"legendary", "mythical", "ultrabeast"})
        evolves = evolves and not legend   # 毒貝比這種會進化的究極異獸照常顯示
        allrows.append([p["name"], p["sta"]])
        if any(f.values()):
            rows.append({"p": p, "f": f, "legend": legend, "evolves": evolves})
    cnt = {k: sum(1 for r in rows if r["f"][k]) for k in LEVELS}
    both = sum(1 for r in rows if r["f"][40] and r["f"][50])

    # 名單沒變就不改日期
    fp = hashlib.sha256(json.dumps([[r["p"]["name"], [r["f"][k] for k in LEVELS]] for r in rows],
                                   ensure_ascii=False).encode()).hexdigest()[:16]
    try:
        state = json.load(open(STATE, encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    if state.get("hash") != fp:
        state = {"hash": fp, "date": L.today_tw()}
        with open(STATE, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2); fh.write("\n")
    date = state["date"]

    cards = []
    for r in rows:
        p, f = r["p"], r["f"]
        lvs = "".join(
            f'<span class="lv{" y" if f[k] else ""}"><b>Lv{k}</b>{"偽百" if f[k] else "－"}'
            f'<i>HP {hp(p, k, 15)}／{hp(p, k, 14)}</i></span>' for k in LEVELS)
        badge = ('<span class="tg lg">傳說・幻之</span>' if r["legend"] else "") + ('<span class="tg ev">未進化</span>' if r["evolves"] else "")
        grp = " ".join(g for g, ok in (("b", f[40] and f[50]), ("s40", f[40] and not f[50]), ("s50", f[50] and not f[40]),
                                        ("l51", f[51])) if ok)
        img = thumb(p)
        pic = f'<img src="{e(img)}" alt="" width="64" height="64" loading="lazy" decoding="async">' if img else ""
        cards.append(f'<li class="c" data-g="{grp}" data-n="{e(p["name"])}"{" data-lg" if r["legend"] else ""}{" data-ev" if r["evolves"] else ""}>'
                     f'<a href="{e(mon_link(p["name"]))}"><span class="pic">{pic}</span>'
                     f'<span class="nm"><b>{e(p["name"])}</b><small>#{p["id"]} · 耐力 {p["sta"]}</small>{badge}</span></a>'
                     f'<span class="lvs">{lvs}</span></li>')

    ex = B.CP_DATA.get("噴火龍")
    example = (f"以噴火龍為例（耐力種族值 {ex['sta']}）：Lv50 時 15/15/15 的 HP 是 ({ex['sta']}+15)×{B.CPM[49]} = "
               f"{(ex['sta'] + 15) * B.CPM[49]:.2f}，捨去後 {hp(ex, 50, 15)}；15/15/14 是 ({ex['sta']}+14)×{B.CPM[49]} = "
               f"{(ex['sta'] + 14) * B.CPM[49]:.2f}，捨去後也是 {hp(ex, 50, 14)}。三項數值完全一樣，所以 15/15/14 的噴火龍就是偽百。") if ex else ""
    faq = [
        ("偽百是什麼？", "寶可夢練到滿等（Lv40、Lv50，或最佳夥伴的 Lv51）時，15/15/14 的 HP 跟 15/15/15 一模一樣。"
                     "攻擊和防禦 IV 本來就相同，HP 又因為無條件捨去而相同，所以實際數值和 100% 完全一樣，對戰與團體戰表現也一樣。"),
        ("14/15/15、15/14/15 算偽百嗎？", "不算。攻擊或防禦少 1 點，攻擊值或防禦值本身就跟 100% 不一樣了。偽百只看耐力差 1 點（15/15/14）而 HP 剛好捨去成同一個數字的情況。"),
        ("為什麼有的只有 Lv40 或只有 Lv50 才是偽百？", "HP 是「（耐力種族值＋耐力 IV）× 等級係數」再捨去小數，不同等級的係數不同，"
                                          "捨去後會不會撞在同一個整數也就不同。所以同一隻寶可夢可能 Lv40 是偽百、Lv50 卻差 1 滴血（單偽 40），反過來也有（單偽 50）。"),
        ("暗影或淨化的寶可夢一樣嗎？", "一樣。暗影、淨化的種族值與一般型態相同，HP 計算也相同，所以偽百名單通用。"),
        ("沒在名單上的寶可夢呢？", "代表牠在 Lv40、Lv50、Lv51 時，15/15/14 的 HP 都比 100% 少 1，沒有偽百。可以在上面的搜尋框輸入名字確認。"),
        ("資料從哪裡來？會更新嗎？", "種族值取自 Pokémon GO 遊戲資料（GAME_MASTER），本站每天會自動檢查；遊戲調整種族值或推出新寶可夢時，這份名單會自動重新計算。"),
    ]
    faq_html = "\n".join(f'<details class="qa"><summary>{e(q)}</summary><p>{e(a)}</p></details>' for q, a in faq)
    title = "寶可夢 GO 偽百查詢｜Lv40、Lv50、Lv51 偽百完整名單"
    desc = (f"Pokémon GO 偽百（15/15/14 練滿後 HP 與 100% 相同）完整名單：Lv40 {cnt[40]} 隻、Lv50 {cnt[50]} 隻、"
            f"最佳夥伴 Lv51 {cnt[51]} 隻，含單偽 40、單偽 50 與傳說寶可夢，可直接搜尋名字。")
    ld = [
        {"@context": "https://schema.org", "@type": "Article", "headline": title, "description": desc,
         "inLanguage": "zh-Hant", "dateModified": date, "mainEntityOfPage": URL},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Pokémon Go 工具箱", "item": "https://pogokit.com/"},
            {"@type": "ListItem", "position": 2, "name": "偽百查詢", "item": URL}]},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]},
    ]
    allj = json.dumps(allrows, ensure_ascii=False, separators=(",", ":"))
    cpm = json.dumps({str(k): B.CPM[k - 1] for k in LEVELS})
    page = f'''<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8866689605007086" crossorigin="anonymous"></script>
<script src="../js/analytics.js"></script>
<script src="../config.js"></script>
<script src="../js/pageview-counter.js" defer></script>
<link rel="icon" type="image/png" sizes="192x192" href="../img/masterball.png">
<title>{e(title)}｜Pokémon Go 工具箱</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{URL}">
<meta name="robots" content="index,follow">
<meta property="og:type" content="article">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{URL}">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
<style>{L.CSS}{CSS}</style>
</head>
<body>
<header class="topbar">
  <a class="home" href="../"><span class="logo" aria-hidden="true">🧰</span><span>Pokémon Go 工具箱</span></a>
  <nav class="tnav" aria-label="相關工具"><a href="../?tab=cp-checker-app">IV100 CP 查詢</a><a href="../pvp-ranker/">PvP IV 排名</a></nav>
  <a class="cta" href="../trade-list/">做交換清單</a>
</header>

<main>
  <nav class="crumb" aria-label="導覽路徑"><a href="../">Pokémon Go 工具箱</a> › <span>偽百查詢</span></nav>
  <section class="hero">
    <p class="eyebrow">IV 個體值 · 練滿後的數值</p>
    <h1><span class="nw">寶可夢 GO</span> <span class="nw">偽百查詢</span></h1>
    <p class="lede">「偽百」是 <b>15/15/14</b> 的寶可夢練到滿等時，HP 跟 <b>15/15/15</b> 剛好一樣，攻擊、防禦本來就相同，
    所以實際數值和 100% 完全一樣。這頁列出所有在 Lv40、Lv50、最佳夥伴 Lv51 有偽百的寶可夢，輸入名字就能查。</p>
    <ul class="chips"><li>Lv40 <b>{cnt[40]}</b> 隻</li><li>Lv50 <b>{cnt[50]}</b> 隻</li><li>Lv51 <b>{cnt[51]}</b> 隻</li><li>40、50 都偽百 <b>{both}</b> 隻</li><li>資料更新 <b>{date}</b></li></ul>
  </section>

  <section class="how">
    <h2>怎麼判斷？</h2>
    <p>HP 的算法是 <code>（耐力種族值 ＋ 耐力 IV）× 等級係數</code>，再<strong>無條件捨去</strong>小數。
    耐力 IV 從 15 變 14，HP 少不到 1 的時候，捨去後就是同一個數字。{e(example)}</p>
    <p class="note">只有 <b>15/15/14</b> 才可能是偽百；14/15/15、15/14/15 的攻擊或防禦本身就不同，不算。暗影、淨化的寶可夢種族值相同，名單通用。</p>
  </section>

  <section class="board">
    <div class="tools">
      <label class="sb"><span>🔍</span><input id="q" type="search" placeholder="輸入寶可夢名稱，例如：噴火龍" autocomplete="off" enterkeyhint="search"></label>
      <div class="tabs" role="group" aria-label="篩選">
        <button class="t on" data-g="">全部偽百</button><button class="t" data-g="b">40、50 都偽百</button>
        <button class="t" data-g="s40">單偽 40</button><button class="t" data-g="s50">單偽 50</button><button class="t" data-g="l51">Lv51（最佳夥伴）</button>
      </div>
      <div class="opts"><label><input type="checkbox" id="lg"> 只看傳說・幻之</label><label><input type="checkbox" id="ev"> 顯示未進化型態</label></div>
      <p class="cnt" id="cnt" aria-live="polite"></p>
      <p class="none" id="none" hidden></p>
    </div>
    <ul class="grid" id="list">
{chr(10).join(cards)}
    </ul>
    <p class="legend">每格是該等級 15/15/15 與 15/15/14 的 HP；兩個數字一樣就是偽百。點寶可夢可以看牠的完整 CP 表。</p>
  </section>

  <section class="faq">
    <h2>偽百常見問題</h2>
{faq_html}
  </section>

  <section class="next">
    <div><h2>想確認手上那隻的 IV？</h2><p>用 IV100 CP 查詢輸入 CP，就能反查可能的等級與 IV 組合。</p></div>
    <a class="bigcta" href="../?tab=cp-checker-app">IV100 CP 查詢 →</a>
  </section>
</main>

<footer class="foot">
  <p>種族值取自 Pokémon GO 遊戲資料（GAME_MASTER），由本站計算，非官方資料。</p>
  <p>本站為非官方同人工具，與 Pokémon GO／Niantic 無隸屬關係。Pokémon 及其商標為 &copy;1995-2026 Nintendo, Creatures, GAME FREAK 所有。</p>
  <p><a href="../about/">關於本站</a> · <a href="../contact/">聯絡我們</a> · <a href="../privacy/">隱私權政策</a> · <a href="../disclaimer/">免責聲明</a> · <a href="../">回工具箱</a></p>
</footer>

<script>var ALL={allj},CPM={cpm};{JS}</script>
<script src="../js/ads.js" defer></script>
</body>
</html>
'''
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    L.update_sitemap({URL: date})
    print(f"已寫出 fake-hundo/index.html（{os.path.getsize(OUT):,} bytes）：Lv40 {cnt[40]}、Lv50 {cnt[50]}、Lv51 {cnt[51]}、40+50 {both}")


JS = r"""
(function(){var q=document.getElementById('q'),lg=document.getElementById('lg'),ev=document.getElementById('ev'),cnt=document.getElementById('cnt'),
none=document.getElementById('none'),tabs=[].slice.call(document.querySelectorAll('.t')),cs=[].slice.call(document.querySelectorAll('#list .c')),g='';
function norm(s){return (s||'').replace(/\s+/g,'').toLowerCase();}
function hp(sta,iv,l){return Math.max(10,Math.floor((sta+iv)*CPM[l]));}
function go(){var k=norm(q.value),n=0;cs.forEach(function(c){var ok=(!g||(' '+c.dataset.g+' ').indexOf(' '+g+' ')>-1)&&(!lg.checked||c.hasAttribute('data-lg'))
&&(k?norm(c.dataset.n).indexOf(k)>-1:(ev.checked||!c.hasAttribute('data-ev')));c.hidden=!ok;if(ok)n++;});
cnt.textContent=(k?'「'+q.value.trim()+'」':'')+'共 '+n+' 筆';none.hidden=true;
if(k&&!n){var m=ALL.filter(function(a){return norm(a[0]).indexOf(k)>-1;}).slice(0,6);
if(m.length){none.innerHTML=m.map(function(a){return '<b>'+a[0].replace(/[<&]/g,'')+'</b> 沒有偽百：'+['40','50','51'].map(function(l){return 'Lv'+l+' HP '+hp(a[1],15,l)+'／'+hp(a[1],14,l);}).join('、');}).join('<br>')
+'<br><small>15/15/14 的 HP 都比 100% 少 1，要 15/15/15 才一樣。</small>';none.hidden=false;}}}
tabs.forEach(function(b){b.addEventListener('click',function(){g=b.dataset.g;tabs.forEach(function(x){x.classList.toggle('on',x===b);});go();
if(window.track)track('fake_hundo_filter',{type:g||'all'});});});
q.addEventListener('input',go);lg.addEventListener('change',go);ev.addEventListener('change',go);go();})();
"""

CSS = r"""
.nw{display:inline-block}
.how{margin-top:18px;background:#fff;border-radius:20px;padding:18px 22px;box-shadow:0 1px 2px rgba(20,17,31,.06),0 6px 18px -14px rgba(20,17,31,.25)}
.how h2{margin:0 0 8px;font-size:1.15rem}.how p{margin:0 0 8px;color:var(--ink-2)}.how .note{margin:0;color:var(--muted);font-size:.9rem}
.how code{padding:1px 6px;border-radius:6px;background:#f3edff;color:#5b3fd6;font-size:.9em}
.board{margin-top:22px}
.tools{position:static;margin:0;padding:0;box-shadow:none;background:none}
.sb{display:flex;align-items:center;gap:8px;padding:0 14px;height:48px;border-radius:14px;background:#fff;border:1px solid var(--line);box-shadow:0 1px 2px rgba(20,17,31,.05)}
.sb input{flex:1;min-width:0;border:0;outline:0;background:none;font:inherit;font-size:16px;color:var(--ink)}
.tabs{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.t{padding:7px 14px;border:1px solid var(--line);border-radius:999px;background:#fff;color:var(--ink-2);font:inherit;font-size:.88rem;font-weight:750;cursor:pointer}
.t.on{background:var(--ink);border-color:var(--ink);color:#fff}
.opts{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:10px;font-size:.9rem;color:var(--ink-2)}.opts label{display:flex;align-items:center;gap:6px;min-height:32px}
.none{margin:10px 0 0;padding:12px 14px;border-radius:14px;background:#fff7e6;border:1px solid #f3d9a4;color:#7a4b00;font-size:.92rem;line-height:1.7}
.grid{list-style:none;margin:10px 0 0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px}
.c{background:#fff;border-radius:18px;padding:12px 14px;box-shadow:0 1px 2px rgba(20,17,31,.06),0 6px 18px -14px rgba(20,17,31,.25)}
.c a{display:flex;align-items:center;gap:12px;color:var(--ink);text-decoration:none}
.c .pic{flex:none;width:64px;height:64px;border-radius:16px;overflow:hidden;background:radial-gradient(70% 70% at 50% 40%,#fff,#ece8f6)}
.c .pic img{width:100%;height:100%;object-fit:contain;transform:scale(1.15)}
.c .nm{display:flex;flex-wrap:wrap;align-items:center;gap:4px 6px;min-width:0}.c .nm b{font-size:1.02rem;font-weight:850}
.c .nm small{flex-basis:100%;color:var(--muted);font-size:.78rem}
.tg{padding:0 8px;border-radius:999px;font-size:.7rem;font-weight:800;line-height:1.7}.tg.lg{background:#fde8f1;color:#be185d}.tg.ev{background:#f1f0f5;color:var(--muted)}
.lvs{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:10px}
.lv{display:flex;flex-direction:column;align-items:center;padding:6px 4px;border-radius:12px;background:#f6f4fa;color:var(--muted);font-size:.8rem;line-height:1.35}
.lv b{font-size:.74rem;color:var(--muted)}.lv i{font-style:normal;font-size:.72rem;font-variant-numeric:tabular-nums}
.lv.y{background:linear-gradient(135deg,#fdf2f8,#f3edff);color:#5b3fd6;font-weight:850;box-shadow:inset 0 0 0 1px #d9ccff}.lv.y b{color:#be185d}
.legend{margin:14px 0 0;color:var(--muted);font-size:.88rem;text-align:center}
@media(max-width:760px){.grid{grid-template-columns:1fr}.how{padding:16px}}
"""

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build()
