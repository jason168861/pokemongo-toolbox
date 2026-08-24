#!/usr/bin/env python3
"""產生 stardust/index.html —— 星星沙子怎麼賺。

名單讀 data/stardust_bonus.json（js/info-hub.js 讀的是同一份），
進化階段讀 data/pokemon_data_and_rankings.js 的 family.stage，
用來算出「這隻給的量是同階段基礎值的幾倍」。

    python scripts/build_stardust_page.py

⚠ BASE / DAILY 這幾個數字是遊戲機制，不是從資料檔算出來的。
  遊戲改版時要手動更新，改完記得順便看一下 caveat 那段還對不對。
"""
import json, os, re, html

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(HERE, "stardust")
OUT = os.path.join(OUT_DIR, "index.html")
# 圖示用本機的（跟 /backgrounds/、/tradable/ 一致）。
# 舊的「特別資訊」分頁是直接連 jsDelivr 的 CDN，但這 24 張本機都有，
# 沒必要為了它們多一個外部相依 —— CDN 掛了整頁的圖就沒了。
TL = os.path.join(HERE, "trade-list")
SPRITE = "../trade-list/assets/img/"

e = html.escape

# 基礎捕捉星沙，依進化階段。
BASE = {1: 100, 2: 300, 3: 500}
# 每日捕捉獎勵：每天第一隻的額外量，以及連續第 7 天的額外量。
DAILY_FIRST = 600
DAILY_STREAK7 = 3000
# 倍率加成。天氣加成只作用在捕捉；星星碎片作用在期間內的所有來源。
WEATHER_MULT = 1.25
STAR_PIECE_MULT = 1.5
# 餵莓果：一顆的量、單隻上限、30 分鐘內可累計的寶可夢數。
BERRY_DUST = 30
BERRY_PER_MON = 10
BERRY_MONS = 10


def load():
    with open(os.path.join(HERE, "data", "stardust_bonus.json"), encoding="utf-8") as f:
        mons = json.load(f)["pokemon"]
    # family.stage：1 = 未進化、2 = 第二階段、3 = 第三階段
    # 這個 .js 裡不只一個陣列（POKEDEX 後面還有排名資料），
    # 所以不能抓最後一個 "]"，要從 POKEDEX 開始數括號配對。
    src = open(os.path.join(HERE, "data", "pokemon_data_and_rankings.js"), encoding="utf-8").read()
    start = src.index("[", src.index("const POKEDEX"))
    depth, end = 0, None
    for i in range(start, len(src)):
        if src[i] == "[":
            depth += 1
        elif src[i] == "]":
            depth -= 1
            if depth == 0:
                end = i
                break
    dex = json.loads(src[start:end + 1])
    stage = {}
    for p in dex:
        st = (p.get("family") or {}).get("stage")
        if st:
            stage.setdefault(p["dexNumber"], st)
    return mons, stage


def sprite(m):
    fn = f"pm{m['dex']}" + (f".f{m['form']}" if m.get("form") else "") + ".icon.png"
    if not os.path.exists(os.path.join(TL, "assets", "img", fn)):
        raise SystemExit(f"找不到圖示 {fn}（{m['name']}）——"
                         f"跑過 trade-list/fetch_assets.py 了嗎？")
    return SPRITE + fn


def build():
    mons, stage = load()
    for m in mons:
        m["stage"] = stage.get(m["dex"], 1)
        m["base"] = BASE.get(m["stage"], 100)
        m["mult"] = m["stardust"] / m["base"]
        # 四捨五入到整數會誤導：750/100 是 7.5 卻寫成「8 倍」、700/300 是 2.33
        # 卻寫成「2 倍」，同一份表裡有的高估有的低估。留一位小數，整數就不顯示小數點。
        m["mult_txt"] = f"{m['mult']:.1f}".rstrip("0").rstrip(".")
    mons.sort(key=lambda m: -m["stardust"])

    rows = "\n".join(
        f'''        <li>
          <img src="{e(sprite(m))}" alt="{e(m['name'])}" width="56" height="56" loading="lazy" decoding="async">
          <span class="nm">{e(m['name'])}</span>
          <span class="dust">{m['stardust']:,}</span>
          <span class="mult">同階段基礎 {m['base']} ・ {m['mult_txt']} 倍</span>
        </li>''' for m in mons)

    top = mons[0]
    desc = (f"Pokémon GO 捕捉星星沙子完整說明：基礎值依進化階段為 {BASE[1]}／{BASE[2]}／{BASE[3]}，"
            f"每日第一隻額外 {DAILY_FIRST}、連續第七天額外 {DAILY_STREAK7:,}，"
            f"另有 {len(mons)} 隻寶可夢捕捉時給得特別多（最高 {top['name']} {top['stardust']:,}）。")

    ld = json.dumps({
        "@context": "https://schema.org", "@type": "Article",
        "headline": "Pokémon GO 星星沙子怎麼賺",
        "description": desc, "inLanguage": "zh-Hant",
        "mainEntityOfPage": "https://pogokit.com/stardust/",
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
<title>Pokémon GO 星星沙子怎麼賺？捕捉量、每日獎勵與高星沙寶可夢｜Pokémon Go 工具箱</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="https://pogokit.com/stardust/">
<meta name="robots" content="index,follow">
<meta property="og:type" content="article">
<meta property="og:title" content="Pokémon GO 星星沙子怎麼賺？捕捉量、每日獎勵與高星沙寶可夢">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="https://pogokit.com/stardust/">
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
    <h1>Pokémon GO 星星沙子怎麼賺？</h1>

    <p class="lede">星星沙子是強化寶可夢、學第二招式、交換都要用的資源，
    而且不能課金買，只能靠玩累積。所以「同樣抓一隻，拿多少沙子」差很多 ——
    這一頁把所有來源整理清楚：捕捉能拿多少、還有哪些管道、
    以及天氣與星星碎片的加成怎麼疊 —— 最後附上那 {len(mons)} 隻捕捉時給得特別多的寶可夢。</p>

    <h2>捕捉的基礎量：看進化階段</h2>

    <p>抓一般寶可夢拿到的星星沙子，取決於牠在進化鏈上的位置。越後面的階段給越多：</p>

    <div class="stats">
      <div><b>{BASE[1]}</b><span>未進化</span></div>
      <div><b>{BASE[2]}</b><span>第二階段</span></div>
      <div><b>{BASE[3]}</b><span>第三階段</span></div>
    </div>

    <p>所以同樣花一顆球，抓一隻已經進化過的會比抓最初階的划算。
    野外遇到第三階段的寶可夢時，就算圖鑑早就登錄過了，還是值得抓 ——
    光是沙子就有 {BASE[3]} 起跳，是最初階的 {BASE[3] // BASE[1]} 倍。</p>

    <p>另外，<strong>天氣與寶可夢屬性相符時（天氣加成），捕捉拿到的沙子會多 25%</strong>。
    所以下雨天去抓水屬性、大太陽去抓火屬性，不只 CP 比較高，沙子也比較多。</p>

    <h2>每日捕捉獎勵：連續七天差很多</h2>

    <p>除了寶可夢本身的量之外，每天抓到的<strong>第一隻</strong>會再多給一筆：</p>

    <ul class="notes">
      <li><strong>每天第一隻：額外 {DAILY_FIRST} 星星沙子</strong></li>
      <li><strong>連續第七天：額外 {DAILY_STREAK7:,} 星星沙子</strong></li>
    </ul>

    <p>這個獎勵跟抓到什麼無關 —— 抓一隻最普通的波波，跟抓一隻稀有寶可夢，
    拿到的每日獎勵是一樣的。所以就算某天沒空玩，
    <strong>花十秒抓一隻路邊的寶可夢，也值得</strong>：斷掉連續紀錄的話，
    第七天那筆 {DAILY_STREAK7:,} 就要重新從第一天累積。</p>

    <p>換個方式看：連續七天每天抓一隻，光是每日獎勵就有
    {DAILY_FIRST * 6 + DAILY_STREAK7:,} 星星沙子（前六天各 {DAILY_FIRST}、第七天 {DAILY_STREAK7:,}），
    平均一天約 {(DAILY_FIRST * 6 + DAILY_STREAK7) // 7:,}。這是最穩定、也最不花時間的沙子來源。</p>

    <h2>捕捉以外的來源</h2>

    <p>捕捉不是唯一管道，而且對很多人來說也不是最大宗。把來源分成
    「不用特地做、玩了就會累積」和「要特地花時間換」兩類，比較好安排：</p>

    <h3>幾乎不用額外花時間的</h3>

    <ul class="notes">
      <li><strong>孵蛋。</strong>孵化時會給一筆沙子，距離越長給越多 ——
          2、5、7、10、12 公里各有各的量。反正走路本來就在走，蛋位不要空著。</li>
      <li><strong>時時刻刻調查。</strong>每週一早上結算上一週走的距離，
          分成 5、25、50、100 公里幾個級距，走到 100 公里那檔拿最多。
          這是完全被動的收入，只要記得把功能打開。</li>
      <li><strong>好友禮物。</strong>打開朋友送的禮物有機會開到沙子。
          單次不多，但朋友多的話每天累積起來很可觀。</li>
    </ul>

    <h3>要特地花時間、但效率高的</h3>

    <ul class="notes">
      <li><strong>餵道館裡的寶可夢莓果。</strong>這是最容易被低估的一項 ——
          <strong>一顆莓果 {BERRY_DUST} 沙子，跟餵哪一種莓果無關</strong>。
          同一隻寶可夢最多餵 {BERRY_PER_MON} 顆，30 分鐘內最多累計 {BERRY_MONS} 隻
          （不同寶可夢分開計算）。全部餵滿就是
          {BERRY_DUST} × {BERRY_PER_MON} × {BERRY_MONS} =
          <strong>{BERRY_DUST * BERRY_PER_MON * BERRY_MONS:,} 沙子</strong>，
          而且完全不需要打贏任何東西。附近道館多的話，這是投報率最高的做法之一。</li>
      <li><strong>團體戰。</strong>參戰本身就有沙子獎勵。</li>
      <li><strong>各種調查任務。</strong>田野調查、特殊調查、蒐藏家挑戰、
          活動限定的調查，很多獎勵裡都含沙子。順手解掉就有。</li>
      <li><strong>對戰。</strong>跟朋友對戰每天最多算 3 場；
          GO 對戰聯盟打完有獎勵；跟隊長對戰每天 1 場，輸贏都給；
          火箭隊則要贏了才有。</li>
    </ul>

    <h2>加成怎麼疊</h2>

    <p>上面所有的量都還會再乘上加成。這是為什麼「同樣玩一小時，有人拿的沙子是別人的兩倍」：</p>

    <div class="stats">
      <div><b>×{WEATHER_MULT}</b><span>天氣加成（捕捉）</span></div>
      <div><b>×{STAR_PIECE_MULT}</b><span>星星碎片（全部來源）</span></div>
      <div><b>×2 起</b><span>活動加倍（依官方公告）</span></div>
    </div>

    <p><strong>天氣加成只作用在捕捉</strong> —— 天氣與寶可夢屬性相符時，抓到的沙子多 25%。
    <strong>星星碎片則是作用在期間內的所有來源</strong>，包含餵莓果、孵蛋、任務獎勵，
    所以它不該隨便用掉。</p>

    <p>最划算的用法是<strong>疊在一起</strong>：官方辦沙子加倍活動的時候開星星碎片，
    再去餵滿一輪道館莓果。同樣的動作，拿到的量會差好幾倍。
    反過來說，平常隨手開一片星星碎片去抓幾隻波波，等於把道具浪費掉。</p>

    <h2>這 {len(mons)} 隻捕捉時給得特別多</h2>

    <p>有些寶可夢的捕捉星沙不照上面的基礎值走，而是固定給一個更高的量。
    下面依給的量排序，並標出是同階段基礎值的幾倍：</p>

    <ul class="dustlist">
{rows}
    </ul>

    <p>最誇張的是{top['name']}，一隻 {top['stardust']:,} ——
    等於同階段一般寶可夢（{top['base']}）的 {top['mult_txt']} 倍。
    活動期間如果這些寶可夢大量出現，會是補沙子的好機會。</p>

    <h2>幾件容易搞錯的事</h2>

    <ul class="notes">
      <li><strong>星星沙子不能買。</strong>它跟寶可幣不一樣，沒有課金管道，
          所以「每天固定拿的那些」長期下來反而是大宗。</li>
      <li><strong>沙子是共用的，糖果不是。</strong>沙子任何寶可夢都能用，
          所以強化前要想清楚 —— 花在不會長期使用的寶可夢上，等於浪費。</li>
      <li><strong>交換也要花沙子。</strong>距離越遠、越沒登錄過的寶可夢，交換費用越高。
          所以交換前先確認雙方要換什麼，不要換到一半才發現沙子不夠。</li>
      <li><strong>加成要先開再做事。</strong>星星碎片是「期間內」生效，
          先開再去餵莓果、解任務、開禮物，才吃得到那 {STAR_PIECE_MULT} 倍。
          事後才想到就來不及了。</li>
    </ul>

    <p class="caveat">以上數值依遊戲版本可能調整，活動期間也常有額外加成，
    實際以遊戲內顯示為準。</p>

    <section class="next">
      <h2>先把交換清單準備好</h2>
      <p>交換要花星星沙子，所以事前談清楚很重要。用<a href="../trade-list/">交易清單產生器</a>
      把「我想要的」和「我能提供的」做成一張圖片貼給對方，
      雙方一次看懂，不用來回問，也不會換到一半才發現搞錯。</p>
      <p><a class="bigcta" href="../trade-list/">🔴 開始製作交換清單</a></p>
    </section>
  </article>
</main>

<footer class="foot">
  <p>本頁數值整理自遊戲內實際表現，非官方資料，可能隨改版變動。</p>
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
    print(f"已寫出 stardust/index.html（{os.path.getsize(OUT):,} bytes）")
    print(f"  高星沙寶可夢 {len(mons)} 隻，最高 {top['name']} {top['stardust']:,}")
    miss = [m["name"] for m in mons if m["dex"] not in stage]
    if miss:
        print(f"  ⚠ 找不到進化階段（當成第 1 階）:{miss}")


if __name__ == "__main__":
    build()
