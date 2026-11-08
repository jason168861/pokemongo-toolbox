#!/usr/bin/env python3
"""產生「交換指南」頁 /trade-guide/：星星沙子費用、友誼等級、特殊交換、亮晶晶交換、遠距交換、交換進化。

資料來源（每一項都要有來源，不憑印象寫）：
- 友誼等級的天數、特殊交換折扣、攻擊加成、團體戰額外精靈球、亮晶晶首飾門檻、遠距交換每日上限、
  亮晶晶寶可夢強化星沙折扣、交換進化（noCandyCostViaTrade）：GAME_MASTER（PokeMiners game_masters latest.json）
- 交換條件、特殊交換對象、每天一次、糖果獎勵、交換後能力重新決定等：遊戲內官方說明文字（pogo_assets Texts）
- 遠距交換規則：官方公告 https://pokemongo.com/zh_Hant/news/pgo-remote-trade-2025
- 基本費用 100／20,000／1,000,000：GAME_MASTER 沒有，取自多個攻略網站（Pokémon GO Hub、mein-mmo、PokeTools）彼此一致，
  且乘上 GAME_MASTER 的折扣（20%／92%／96%）正好得到各等級的數字
- 交換後 IV 下限（1／2／3／5／12）：官方沒有公布，是社群研究數據，頁面上明確標示

    python scripts/build_trade_guide.py              （會下載 GAME_MASTER 約 20MB）
    GM_PATH=/path/latest.json python scripts/build_trade_guide.py
"""
import html, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_pvp_league as L  # noqa: E402   共用版面 CSS、縮圖、日期

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "trade-guide", "index.html")
URL = "https://pogokit.com/trade-guide/"
GM_URL = "https://raw.githubusercontent.com/PokeMiners/game_masters/master/latest/latest.json"
NEWS_REMOTE = "https://pokemongo.com/zh_Hant/news/pgo-remote-trade-2025"
UPDATED = "2026-11-09"   # 內容最後人工核對的日期
e = lambda s: html.escape(str(s), quote=True)

LEVELS = [  # (GAME_MASTER 等級, 官方中文名)
    (1, "好朋友"), (2, "給力好朋友"), (3, "麻吉好朋友"), (4, "正港好朋友"), (5, "正港好朋友＋")]
BASE = {"reg_in": 100, "reg_new": 20000, "sp_in": 20000, "sp_new": 1000000}   # 好朋友（無折扣）時的費用
IV_FLOOR = {1: 1, 2: 2, 3: 3, 4: 5}   # 社群研究；正港好朋友＋ 官方未公布


def load_gm():
    p = os.environ.get("GM_PATH")
    if p and os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    import requests
    return requests.get(GM_URL, timeout=120).json()


def load_zh_names():
    """官方繁中寶可夢名稱：pogo_assets Texts（本機）；沒有的話用站上的 CP 資料。"""
    pogo = os.environ.get("POGO_ASSETS", os.path.join(os.path.dirname(ROOT), "pogo_assets"))
    f = os.path.join(pogo, "Texts", "Latest APK", "ChineseTraditional.txt")
    names = {}
    if os.path.exists(f):
        k = None
        for line in open(f, encoding="utf-8"):
            if line.startswith("RESOURCE ID: "):
                k = line[13:].strip()
            elif line.startswith("TEXT: ") and k:
                m = re.match(r"pokemon_name_(\d{4})$", k)
                if m:
                    names[int(m.group(1))] = line[6:].strip()
                k = None
    return names


def form_note(fs):
    """同一組交換進化包含地區型態或不同尺寸時，在名字後面註明。"""
    if any("ALOLA" in f for f in fs):
        return "<small>（含阿羅拉的樣子）</small>"
    if sum(1 for f in fs if f) > 2:
        return "<small>（各種尺寸）</small>"
    return ""


def cost(kind, lv, disc):
    if kind == "reg_in":
        return BASE[kind]          # 圖鑑已有的一般交換：各等級都是 100
    return round(BASE[kind] * (1 - disc.get(lv, 0)))


def build():
    gm = load_gm()
    D = {x["templateId"]: x["data"] for x in gm}
    fs = {lv: D[f"FRIENDSHIP_LEVEL_{lv}"]["friendshipMilestoneSettings"] for lv, _ in LEVELS}
    disc = {lv: fs[lv].get("tradingDiscount", 0) for lv, _ in LEVELS}
    # 天數：每天最多 1 點友誼點數。正港好朋友＋ 是正港好朋友之後再累積 relativePointsToReach
    days = {}
    for lv, _ in LEVELS:
        s = fs[lv]
        days[lv] = (days[lv - 1] + s["relativePointsToReach"]) if s.get("relativePointsToReach") else s.get("minPointsToReach", 0)
    atk = {lv: round((fs[lv].get("attackBonusPercentage", 1) - 1) * 100) for lv, _ in LEVELS}
    balls = {lv: fs[lv].get("raidBallBonus", 0) for lv, _ in LEVELS}
    lucky_disc = round(D["LUCKY_POKEMON_SETTINGS"]["luckyPokemonSettings"]["powerUpStardustDiscountPercent"] * 100)
    rts = D["REMOTE_TRADE_SETTINGS"]["remoteTradeSettings"]
    trinket_lv = min(lv for lv, _ in LEVELS if fs[lv].get("unlockedLuckyFriendApplicator"))
    lvname = dict(LEVELS)

    # 交換進化：GAME_MASTER 的 noCandyCostViaTrade
    zh = load_zh_names()
    dex = {}
    for x in gm:
        s = x["data"].get("pokemonSettings")
        m = re.match(r"V(\d{4})_POKEMON_", x["templateId"])
        if s and m:
            dex.setdefault(s["pokemonId"], int(m.group(1)))
    evo, forms = {}, {}
    for x in gm:
        s = x["data"].get("pokemonSettings")
        if not s:
            continue
        for b in s.get("evolutionBranch") or []:
            if b.get("noCandyCostViaTrade") and b.get("evolution"):
                a, t = dex.get(s["pokemonId"]), dex.get(b["evolution"])
                if a and t:
                    evo.setdefault((a, t), b.get("candyCost"))
                    forms.setdefault((a, t), set()).add(s.get("form") or "")
    evo = sorted(evo.items())
    if not evo:
        raise SystemExit("GAME_MASTER 裡找不到交換進化資料，停止（避免寫出空的清單）")
    miss = [d for pair, _ in evo for d in pair if d not in zh]
    if miss:
        raise SystemExit(f"找不到官方中文名稱（圖鑑編號 {miss}）：請設定 POGO_ASSETS 指向 pogo_assets")

    # ---- 表格 ----
    cols = [("reg_in", "一般寶可夢", "圖鑑已登錄"), ("reg_new", "一般寶可夢", "圖鑑未登錄"),
            ("sp_in", "傳說・異色", "圖鑑已登錄"), ("sp_new", "傳說・異色", "圖鑑未登錄")]
    head = "".join(f"<th>{e(a)}<small>{e(b)}</small></th>" for _, a, b in cols)
    body = "".join(
        f'<tr><th>{e(n)}<small>{"無折扣" if not disc[lv] else f"特殊交換 −{round(disc[lv] * 100)}%"}</small></th>'
        + "".join(f'<td data-l="{e(a + "・" + b)}">{cost(k, lv, disc):,}</td>' for k, a, b in cols) + "</tr>"
        for lv, n in LEVELS)
    cost_table = f'<div class="tw"><table class="ct"><thead><tr><th>友誼等級</th>{head}</tr></thead><tbody>{body}</tbody></table></div>'

    fbody = "".join(
        f'<tr><th>{e(n)}</th><td data-l="需要天數">{days[lv]} 天</td><td data-l="特殊交換折扣">{"—" if not disc[lv] else f"{round(disc[lv] * 100)}%"}</td>'
        f'<td data-l="交換後 IV 下限*">{IV_FLOOR.get(lv, "未公布")}</td><td data-l="一起戰鬥攻擊加成">+{atk[lv]}%</td>'
        f'<td data-l="團體戰額外精靈球">{balls[lv] or "—"}</td></tr>' for lv, n in LEVELS)
    friend_table = (f'<div class="tw"><table class="ft"><thead><tr><th>友誼等級</th><th>需要天數</th><th>特殊交換折扣</th>'
                    f'<th>交換後 IV 下限*</th><th>一起戰鬥攻擊加成</th><th>團體戰額外精靈球</th></tr></thead><tbody>{fbody}</tbody></table></div>')

    evo_html = "".join(
        f'<li><span class="ev"><img src="../trade-list/assets/thumb/pm{a}.icon.webp" alt="" width="52" height="52" loading="lazy">'
        f'<b>{e(zh.get(a, a))}</b>{form_note(forms.get((a, t), set()))}</span><span class="ar">→</span>'
        f'<span class="ev"><img src="../trade-list/assets/thumb/pm{t}.icon.webp" alt="" width="52" height="52" loading="lazy">'
        f'<b>{e(zh.get(t, t))}</b></span><span class="cc">原本要 {c} 顆糖果</span></li>' for (a, t), c in evo)

    calc_opts = "".join(f'<option value="{lv}">{e(n)}</option>' for lv, n in LEVELS)
    calc_data = json.dumps({str(lv): {k: cost(k, lv, disc) for k in BASE} for lv, _ in LEVELS})

    best_sp = cost("sp_new", 4, disc)
    faq = [
        ("交換寶可夢要多少星星沙子？", f"圖鑑裡已經有的一般寶可夢，交換只要 100 星星沙子，跟友誼等級無關。"
                             f"特殊交換（圖鑑沒有的寶可夢、傳說、異色等）比較貴：圖鑑沒有的一般寶可夢在好朋友時要 20,000，"
                             f"正港好朋友降到 800；圖鑑沒有的傳說或異色寶可夢最貴，好朋友時要 1,000,000，正港好朋友是 {best_sp:,}。"),
        ("什麼是特殊交換？", "遊戲說明：傳說的寶可夢、幻之寶可夢、究極異獸、淨化後的寶可夢、異色寶可夢，以及自己圖鑑裡沒有的寶可夢，都要用特殊交換。"
                      "特殊交換一天只能進行一次（部分活動期間例外），而且友誼等級要達到好朋友。"),
        ("交換後 IV 會變嗎？", "會。遊戲說明寫明交換後寶可夢的基礎能力會被隨機調整，也就是 IV 會重新決定。"
                        "友誼等級越高、IV 的下限越高（社群研究數據：好朋友 1、給力 2、麻吉 3、正港 5），亮晶晶交換則保證每項至少 12。"),
        ("交換來的寶可夢可以再換出去嗎？", "不行。遊戲規則是交換來的寶可夢不能再拿去交換。"),
        ("哪些寶可夢不能交換？", "暗影寶可夢和幻之寶可夢不能交換（少數幻之寶可夢例外），另外還有一些特定型態也不能交換。完整名單請看「不可交換寶可夢清單」。"),
        ("怎麼樣會變成亮晶晶寶可夢？", f"成為正港好朋友後持續互動，有機會變成亮晶晶好朋友，下一次交換的兩隻寶可夢都一定會變成亮晶晶寶可夢。"
                             f"給力好朋友以上也可以用「亮晶晶首飾」直接變成亮晶晶好朋友。亮晶晶寶可夢強化所需的星星沙子減少 {lucky_disc}%。"),
        ("遠距交換是什麼？", f"友誼等級達到「正港好朋友＋」後可以獲得遠距交換的額度，不必在附近也能交換。"
                      f"遠距交換不算特殊交換；30 天內捕獲的寶可夢、交換過的寶可夢、暗影與幻之寶可夢等不能用遠距交換。"),
        ("交換能拿到幾顆糖果？", "交換時會拿到糖果，兩隻寶可夢的捕捉地點距離越遠（最多到約 100 公里），拿到的糖果越多。"),
    ]
    faq_html = "\n".join(f'<details class="qa"><summary>{e(q)}</summary><p>{e(a)}</p></details>' for q, a in faq)
    title = "Pokémon GO 交換要多少星星沙子？費用表、特殊交換、亮晶晶與遠距交換整理"
    desc = (f"Pokémon GO 交換寶可夢的星星沙子費用表：一般交換 100，特殊交換 20,000～1,000,000，正港好朋友最低 800。"
            f"整理友誼等級折扣、交換後 IV 下限、亮晶晶交換、遠距交換規則與 {len(evo)} 組交換進化。")
    ld = [
        {"@context": "https://schema.org", "@type": "Article", "headline": title, "description": desc,
         "inLanguage": "zh-Hant", "dateModified": UPDATED, "mainEntityOfPage": URL},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Pokémon Go 工具箱", "item": "https://pogokit.com/"},
            {"@type": "ListItem", "position": 2, "name": "交換指南", "item": URL}]},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]},
    ]
    toc = [("cost", "星沙費用"), ("calc", "費用試算"), ("special", "特殊交換"), ("friend", "友誼等級"),
           ("lucky", "亮晶晶交換"), ("remote", "遠距交換"), ("evo", "交換進化"), ("rules", "交換規則"), ("faq", "常見問題")]
    toc_html = "".join(f'<a href="#{a}">{e(b)}</a>' for a, b in toc)
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
  <nav class="tnav" aria-label="相關工具"><a href="../tradable/">不可交換清單</a><a href="../stardust/">星沙攻略</a></nav>
  <a class="cta" href="../trade-list/">做交換清單</a>
</header>

<main>
  <nav class="crumb" aria-label="導覽路徑"><a href="../">Pokémon Go 工具箱</a> › <span>交換指南</span></nav>
  <section class="hero">
    <p class="eyebrow">交換 · 星星沙子 · 友誼等級</p>
    <h1><span class="nw">Pokémon GO</span> <span class="nw">交換指南</span></h1>
    <p class="lede">交換一次要多少星星沙子、什麼是特殊交換、友誼等級差在哪、怎麼換到亮晶晶寶可夢，一頁整理清楚。
    費用、折扣與規則都對照遊戲資料和官方說明，社群推算的數字會另外標示。</p>
    <ul class="chips"><li>一般交換 <b>100</b> 星沙</li><li>特殊交換 <b>一天 1 次</b></li><li>正港好朋友特殊交換 <b>−{round(disc[4] * 100)}%</b></li><li>內容核對 <b>{UPDATED}</b></li></ul>
  </section>

  <div class="tiles">
    <div class="tile"><b>100</b><span>圖鑑已有的一般寶可夢<br>（任何友誼等級）</span></div>
    <div class="tile"><b>20,000 → {cost("reg_new", 4, disc):,}</b><span>圖鑑沒有的寶可夢<br>（好朋友 → 正港好朋友）</span></div>
    <div class="tile"><b>1,000,000 → {best_sp:,}</b><span>圖鑑沒有的傳說・異色<br>（好朋友 → 正港好朋友）</span></div>
    <div class="tile"><b>12/12/12</b><span>亮晶晶交換的 IV 下限<br>（社群研究）</span></div>
  </div>

  <nav class="toc" aria-label="本頁目錄">{toc_html}</nav>

  <section class="card" id="cost">
    <h2><span class="ic">✨</span>星星沙子費用表</h2>
    <p>交換時雙方都要付星星沙子。費用看兩件事：<b>是不是特殊交換</b>，以及<b>兩人的友誼等級</b>。友誼等級只會讓特殊交換變便宜，圖鑑已有的一般寶可夢永遠是 100。</p>
    {cost_table}
    <p class="note">「傳說・異色」指傳說的寶可夢、異色寶可夢等特殊交換對象（定義見下方）。「圖鑑已登錄／未登錄」是看<b>收到的那一方</b>的圖鑑。
    活動期間交換費用可能另外打折（例如減半或 1/4），以活動公告為準。</p>
  </section>

  <section class="card" id="calc">
    <h2><span class="ic">🧮</span>費用試算</h2>
    <div class="calc">
      <label>友誼等級<select id="cLv">{calc_opts}</select></label>
      <label>要交換的寶可夢<select id="cKind"><option value="reg">一般寶可夢</option><option value="sp">傳說・異色等特殊對象</option></select></label>
      <label>收到的人圖鑑裡<select id="cDex"><option value="in">已經有</option><option value="new">還沒有</option></select></label>
    </div>
    <p class="out" id="cOut" aria-live="polite"></p>
  </section>

  <section class="card" id="special">
    <h2><span class="ic">⭐</span>什麼是特殊交換</h2>
    <p>遊戲說明列出的特殊交換對象：</p>
    <ul class="pills"><li>傳說的寶可夢</li><li>幻之寶可夢</li><li>究極異獸</li><li>淨化後的寶可夢</li><li>異色寶可夢</li><li>自己圖鑑裡沒有的寶可夢</li></ul>
    <ul class="dots">
      <li>特殊交換<b>一天只能 1 次</b>（部分活動期間例外）。</li>
      <li>友誼等級要達到<b>好朋友</b>才能進行特殊交換。</li>
      <li>大部分幻之寶可夢其實不能交換，可以交換的例外請看<a href="../tradable/">不可交換寶可夢清單</a>。</li>
    </ul>
  </section>

  <section class="card" id="friend">
    <h2><span class="ic">🤝</span>友誼等級</h2>
    <p>每天和朋友互動（送禮物、交換、一起戰鬥等），每位朋友每天最多加 1 點友誼點數，所以下表的天數就是<b>每天都互動</b>時最快需要的天數。</p>
    {friend_table}
    <p class="note">* 交換後 IV 下限不是官方公布的數字，是社群收集大量交換結果整理出的數據（每一項 IV 至少多少）。「正港好朋友＋」的下限官方未公布。
    攻擊加成是和朋友一起打團體戰、道館時的攻擊力加成。</p>
  </section>

  <section class="card" id="lucky">
    <h2><span class="ic">🍀</span>亮晶晶交換</h2>
    <ul class="dots">
      <li><b>亮晶晶好朋友</b>：和朋友成為正港好朋友後，繼續每天互動，就有機會變成亮晶晶好朋友。<b>下一次交換的兩隻寶可夢都一定會變成亮晶晶寶可夢</b>；交換完成後，亮晶晶好朋友的狀態就會結束。</li>
      <li><b>亮晶晶首飾</b>：{e(lvname[trinket_lv])}以上的朋友，可以用這個道具直接變成亮晶晶好朋友。</li>
      <li><b>強化更省星沙</b>：亮晶晶寶可夢強化所需的星星沙子減少 {lucky_disc}%。</li>
      <li><b>IV 比較好</b>：亮晶晶交換後每項 IV 至少 12（社群研究數據）。</li>
      <li>一般交換也有機會變成亮晶晶，社群普遍觀察到<b>越早以前捕捉的寶可夢機率越高</b>；官方沒有公布確切機率。</li>
    </ul>
  </section>

  <section class="card" id="remote">
    <h2><span class="ic">🌏</span>遠距交換（正港好朋友＋）</h2>
    <p>2025 年 12 月起，友誼等級在「正港好朋友」之上新增「正港好朋友＋」。達到後可以獲得<b>遠距交換</b>的額度，不用人在附近也能交換。</p>
    <ul class="dots">
      <li>每位正港好朋友＋ 同時只會有 1 次遠距交換額度；遊戲資料設定每天最多進行 {rts.get("maxRemoteTradesPerDay", 1)} 次遠距交換。</li>
      <li>雙方先從對方標記的寶可夢中各挑最多 3 隻想要的，再各自選 1 隻交出。</li>
      <li><b>遠距交換不算特殊交換</b>。如果兩人是亮晶晶好朋友，遠距交換一樣會是亮晶晶交換。</li>
      <li>不能遠距交換的寶可夢：30 日內捕獲的、先前交換過的、暗影寶可夢、幻之寶可夢、正在防禦道館或能量點的、目前的夥伴、處於超級進化形態的、合體的寶可夢、蒼響（劍之王）與藏瑪然特（盾之王）、在寶可夢遊樂場的寶可夢。</li>
    </ul>
    <p class="note">規則整理自<a href="{NEWS_REMOTE}" target="_blank" rel="noopener">官方公告</a>。</p>
  </section>

  <section class="card" id="evo">
    <h2><span class="ic">🔁</span>交換進化：交換來的免費進化</h2>
    <p>下面這些寶可夢平常進化要很多糖果，但<b>透過交換得到的</b>可以 0 顆糖果直接進化（資料來自遊戲資料）。</p>
    <ul class="evos">{evo_html}</ul>
  </section>

  <section class="card" id="rules">
    <h2><span class="ic">📋</span>交換的基本規則</h2>
    <ul class="dots">
      <li>訓練家等級要 <b>10 級</b>以上，而且雙方要是遊戲內的朋友。</li>
      <li>一般交換時，雙方距離要在 <b>100 公尺</b>內（遠距交換除外）。</li>
      <li>交換後，寶可夢的 <b>IV 會隨機重新決定</b>；如果對方的訓練家等級比較低，CP 和 HP 會被調低。</li>
      <li><b>交換來的寶可夢不能再拿去交換</b>。</li>
      <li>交換會拿到糖果，兩隻寶可夢捕捉地點<b>距離越遠（最多約 100 公里）糖果越多</b>。</li>
      <li>曾經超級進化或原始回歸的寶可夢，交換出去後超級等級（原始等級）會重置；當過夥伴的，夥伴等級也會重置。</li>
      <li>常常和朋友交換，也會提升友誼等級。</li>
    </ul>
  </section>

  <section class="faq" id="faq">
    <h2>交換常見問題</h2>
{faq_html}
  </section>

  <p class="src">資料來源：費用折扣、友誼等級、亮晶晶強化折扣與交換進化取自 Pokémon GO 遊戲資料（GAME_MASTER）；交換規則取自遊戲內的官方說明文字；
  遠距交換取自<a href="{NEWS_REMOTE}" target="_blank" rel="noopener">官方公告</a>；基本費用（100／20,000／1,000,000）與 IV 下限為攻略社群整理的數據。最後核對：{UPDATED}。</p>

  <section class="next">
    <div><h2>準備好要交換了？</h2><p>用交換清單產生器，把「我想要的」和「我能提供的」做成一張圖，直接貼給朋友或社團。</p></div>
    <a class="bigcta" href="../trade-list/">做交換清單 →</a>
  </section>
  <p class="rel">相關：<a href="../tradable/">哪些寶可夢不能交換</a> · <a href="../stardust/">星星沙子怎麼賺</a> · <a href="../fake-hundo/">偽百查詢</a></p>
</main>

<footer class="foot">
  <p>本站為非官方同人工具，與 Pokémon GO／Niantic 無隸屬關係。Pokémon 及其商標為 &copy;1995-2026 Nintendo, Creatures, GAME FREAK 所有。</p>
  <p><a href="../about/">關於本站</a> · <a href="../contact/">聯絡我們</a> · <a href="../privacy/">隱私權政策</a> · <a href="../disclaimer/">免責聲明</a> · <a href="../">回工具箱</a></p>
</footer>

<script>var COST={calc_data};{JS}</script>
<script src="../js/ads.js" defer></script>
</body>
</html>
'''
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    print(f"已寫出 trade-guide/index.html（{os.path.getsize(OUT):,} bytes），交換進化 {len(evo)} 組，"
          f"折扣 {[disc[lv] for lv, _ in LEVELS]}，天數 {[days[lv] for lv, _ in LEVELS]}")


JS = r"""
(function(){var lv=document.getElementById('cLv'),k=document.getElementById('cKind'),d=document.getElementById('cDex'),o=document.getElementById('cOut');
lv.value='4';function go(){var key=(k.value==='reg'?'reg_':'sp_')+(d.value==='in'?'in':'new'),n=COST[lv.value][key];
o.innerHTML='每人需要 <b>'+n.toLocaleString('en-US')+'</b> 星星沙子'+(key==='reg_in'?'（一般交換）':'（特殊交換，一天 1 次）');}
[lv,k,d].forEach(function(x){x.addEventListener('change',function(){go();if(window.track)track('trade_calc',{lv:lv.value,kind:k.value,dex:d.value});});});go();})();
"""

CSS = r"""
.nw{display:inline-block}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:16px}
.tile{display:flex;flex-direction:column;gap:4px;padding:16px;border-radius:18px;background:#fff;box-shadow:0 1px 2px rgba(20,17,31,.06),0 6px 18px -14px rgba(20,17,31,.25)}
.tile b{font-size:1.25rem;font-weight:900;color:#5b3fd6;font-variant-numeric:tabular-nums;line-height:1.3}.tile span{color:var(--muted);font-size:.84rem;line-height:1.5}
.toc{position:sticky;top:var(--head-h);z-index:20;display:flex;gap:6px;margin:16px -16px 0;padding:10px 16px;background:var(--bg);overflow-x:auto;scrollbar-width:none}
.toc::-webkit-scrollbar{display:none}
.toc a{flex:none;padding:6px 13px;border-radius:999px;background:#fff;border:1px solid var(--line);color:var(--ink-2);text-decoration:none;font-weight:750;font-size:.86rem}
.card{margin-top:16px;background:#fff;border-radius:22px;padding:20px 24px;box-shadow:0 1px 2px rgba(20,17,31,.06),0 6px 18px -14px rgba(20,17,31,.25);scroll-margin-top:120px}
.card h2{display:flex;align-items:center;gap:10px;margin:0 0 10px;font-size:1.25rem;letter-spacing:-.01em}
.ic{display:grid;place-items:center;width:34px;height:34px;border-radius:11px;background:linear-gradient(135deg,#fde8f1,#ede7ff);font-size:1rem}
.card p{margin:0 0 10px;color:var(--ink-2)}.note{color:var(--muted)!important;font-size:.88rem}
.tw{overflow-x:auto;margin:6px 0 10px;border:1px solid var(--line);border-radius:14px}
table{width:100%;border-collapse:collapse;font-size:.92rem;font-variant-numeric:tabular-nums}
th,td{padding:10px 12px;border-bottom:1px solid var(--line);text-align:center;white-space:nowrap}
thead th{background:#f6f4fa;font-size:.84rem;color:var(--ink-2)}th small{display:block;font-weight:600;color:var(--muted);font-size:.74rem}
tbody th{text-align:left;font-weight:800}tbody tr:last-child>*{border-bottom:0}
.ct td{font-weight:800;color:#5b3fd6}
.calc{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.calc label{display:flex;flex-direction:column;gap:4px;font-size:.84rem;font-weight:750;color:var(--muted)}
.calc select{height:44px;padding:0 10px;border:1px solid var(--line);border-radius:12px;background:#fff;font:inherit;font-size:16px;color:var(--ink)}
.out{margin:12px 0 0!important;padding:12px 14px;border-radius:14px;background:linear-gradient(135deg,#fdf2f8,#f3edff);color:var(--ink)!important;font-size:1.02rem}
.out b{font-size:1.3rem;color:#5b3fd6}
.pills{display:flex;flex-wrap:wrap;gap:6px;list-style:none;margin:0 0 10px;padding:0}.pills li{padding:5px 12px;border-radius:999px;background:#f3edff;color:#5b3fd6;font-weight:750;font-size:.88rem}
.dots{margin:0;padding-left:1.2em;color:var(--ink-2)}.dots li{margin:6px 0}
.evos{list-style:none;margin:6px 0 0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:8px}
.evos li{display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:14px;background:#f6f4fa;flex-wrap:wrap}
.ev{display:flex;align-items:center;gap:6px}.ev small{color:var(--muted);font-size:.74rem}.ev img{width:52px;height:52px;object-fit:contain}.ev b{font-size:.94rem}
.ar{color:var(--muted);font-weight:900}.cc{margin-left:auto;color:var(--muted);font-size:.78rem}
.src{margin:22px 0 0;color:var(--muted);font-size:.84rem;line-height:1.7}
.rel{margin:18px 0 0;text-align:center;color:var(--muted);font-size:.92rem}
@media(max-width:600px){
 .tw{overflow:visible;border:0;margin:6px 0 10px}
 .tw table,.tw tbody,.tw tr,.tw th,.tw td{display:block}.tw thead{display:none}
 .tw tr{margin:0 0 8px;padding:10px 12px;border:1px solid var(--line);border-radius:14px}
 .tw tbody th{padding:0 0 6px;border:0;font-size:1rem}.tw tbody th small{display:inline;margin-left:6px}
 .tw td{display:flex;justify-content:space-between;gap:12px;padding:5px 0;border:0;border-top:1px dashed var(--line);text-align:right;white-space:normal}
 .tw td::before{content:attr(data-l);color:var(--muted);font-weight:700;font-size:.84rem;text-align:left}
}
@media(max-width:760px){.tiles{grid-template-columns:1fr 1fr}.tile b{font-size:1.05rem}.toc{margin:12px -12px 0;padding:8px 12px}
 .card{padding:16px;border-radius:18px}.calc{grid-template-columns:1fr}th,td{padding:9px 10px}.evos{grid-template-columns:1fr}}
"""

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build()
