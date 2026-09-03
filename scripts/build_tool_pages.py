# -*- coding: utf-8 -*-
"""把 index.html 的表頭／頁尾同步到各獨立工具頁。

背景：這些工具原本都擠在 index.html 裡用 ?tab= 切換。?tab= 是查詢字串，
搜尋引擎只認得一個網址（首頁），所有工具的內容都被算成同一頁的一部分，
等於整站只有一頁有內容。2026-09 把它們拆成 /raids/、/eggs/ … 等實體目錄，
每個工具才有自己的網址、標題與描述可以被收錄。

cp-checker 沒有拆：它已經有 ?mon= 深連結產生的大量子頁，
再多一層目錄會讓既有的 126 個站內連結和外部連結全部要改，得不償失。

拆完之後，各頁的內容就直接編輯 <目錄>/index.html，跟 /about/ 那些一樣。
唯一會重複的是表頭（導覽列）和頁尾 —— 改了 index.html 的導覽列之後
跑這支，就會同步到 8 個工具頁，不必一個一個改。

用法：
    python scripts/build_tool_pages.py           # 同步全部
    python scripts/build_tool_pages.py raids     # 只同步指定目錄
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# app id -> 產生設定
SPEC = [
    ('raids-app', dict(
        dir='raids', init='initializeRaidsApp', mod='raids.js', css=['raids.css'],
        title='團體戰頭目列表',
        desc='Pokémon GO 當期團體戰頭目一覽：各星級頭目、屬性剋制、捕捉時的滿 IV CP（含天氣加成），每日更新。',
    )),
    ('eggs-app', dict(
        dir='eggs', init='initializeEggsApp', mod='eggs.js', css=['eggs.css'],
        title='孵蛋列表',
        desc='Pokémon GO 當期孵蛋池一覽：2km、5km、7km、10km 與各種特殊蛋分別會孵出哪些寶可夢，附孵化後的滿 IV CP，每日更新。',
    )),
    ('research-app', dict(
        dir='research', init='initializeResearchApp', mod='research.js', css=['research.css'],
        title='田野調查任務',
        desc='Pokémon GO 當期田野調查任務一覽：轉補給站可以拿到哪些任務、各任務的獎勵寶可夢與滿 IV CP，可依獎勵搜尋，每日更新。',
    )),
    ('special-research-app', dict(
        dir='special-research', init='initializeSpecialResearchApp',
        mod='special-research.js', css=['special-research.css'], firebase=True,
        title='特殊調查攻略',
        desc='Pokémon GO 特殊調查逐階段任務內容與獎勵整理，可釘選正在進行的調查，登入後跨裝置同步。',
    )),
    ('search-filters-app', dict(
        dir='search-filters', init='initializeSearchFiltersApp', mod='search-filters.js',
        css=['search-filters.css', 'filter-builder.css'], firebase=True,
        extra_mod='filter-builder.js', extra_init='initializeFilterBuilder',
        title='搜尋篩選指令大全',
        desc='Pokémon GO 遊戲內搜尋列可用的篩選指令完整整理，含屬性、招式、年份、可交換等語法，並可勾選條件直接產生能貼上的搜尋字串。',
    )),
    ('id-selector-app', dict(
        dir='id-selector', init='initializeIdSelector', mod='id-selector.js',
        css=['id-selector.css'], firebase=True, bigdata=True,
        title='寶可夢編號篩選器',
        desc='勾選想要的寶可夢，自動產生可以直接貼進 Pokémon GO 搜尋列的編號字串，用來一次找出或排除特定的一批寶可夢。登入後選取結果會同步。',
    )),
    ('pvp-ranker-app', dict(
        dir='pvp-ranker', init='initializePvpRanker', mod='pvp-ranker.js',
        # pvp-logic.js 提供 getCP()，pvp-ranker.js 當全域用
        css=['pvp-ranker.css'], bigdata=True, plain=['js/pvp-logic.js'],
        title='PvP IV 排名查詢',
        desc='查詢 Pokémon GO 對戰聯盟中各寶可夢的 IV 排名：輸入寶可夢就能看到超級聯盟、高級聯盟的最佳 IV 組合、對應 CP 與等級。',
    )),
]

# id-selector / pvp-ranker 依賴的全域資料（POKEDEX、排名、圖片對照）
BIGDATA = [
    'data/precomputed_pokemon_cp.js',
    'data/pokemon_translation_map.js',
    'data/pokemon_names_from_api.js',
    'data/pokemon_data_and_rankings.js',
    'data/pokemon_images.js',
]

DIRS = dict((app, s['dir']) for app, s in SPEC)


def read(path):
    with io.open(os.path.join(ROOT, path), encoding='utf-8') as f:
        return f.read().replace('\r\n', '\n')


def extract_div(html, app_id):
    """抓出 <div id="app_id" ...> ... </div>，用 div 層數配對找結尾。"""
    m = re.search(r'<div id="%s"[^>]*>' % re.escape(app_id), html)
    if not m:
        raise SystemExit('找不到區塊：' + app_id)
    i, depth = m.end(), 1
    tag = re.compile(r'<(/?)div\b', re.I)
    while depth:
        t = tag.search(html, i)
        if not t:
            raise SystemExit('div 沒有配對：' + app_id)
        depth += -1 if t.group(1) else 1
        i = t.end()
    return html[m.start():html.index('>', i - 1) + 1]


def to_parent(url):
    """區塊搬到子目錄後，站內相對連結要多一層 ../。"""
    if re.match(r'^(https?:|//|#|\.\./|/|mailto:|tel:|data:|javascript:)', url):
        return url
    return '../' + url


def rewrite_links(frag):
    return re.sub(r'\b(href|src|data-src|poster)="([^"]+)"',
                  lambda m: '%s="%s"' % (m.group(1), to_parent(m.group(2))), frag)


def build_header(html):
    a = html.index('<header class="site-header-main">')
    b = html.index('</header>', a) + len('</header>')
    nav = html[a:b]
    # 已拆出去的分頁改指真實網址（不再由 SPA 攔截）
    for app, d in DIRS.items():
        nav = nav.replace(' data-target="%s" href="?tab=%s"' % (app, app),
                          ' href="../%s/"' % d)
    nav = nav.replace('href="?tab=', 'href="../?tab=')   # 仍留在首頁的（cp-checker）
    nav = nav.replace('class="tab-button active" data-target="docs-app" href="./"',
                      'class="tab-button" href="../"')
    nav = re.sub(r'href="((?!\.\./|https?:|/|\?|#)[^"]+)"', r'href="../\1"', nav)
    return nav.replace('href=".././"', 'href="../"')


def mark_active(nav, cur_dir):
    """導覽列的 active 底線寫死在「功能說明」上，移到目前這一頁。"""
    return nav.replace('class="tab-button" href="../%s/"' % cur_dir,
                       'class="tab-button active" href="../%s/"' % cur_dir)


FOOTER = u'''    <footer class="site-footer">
        <p>&copy; <span id="copyright-year"></span> Pokémon Go 工具箱. All rights reserved by their respective owners.</p>
        <p>This website is an unofficial fan-made tool, is not officially affiliated with Pokémon GO, and is intended to fall under Fair Use doctrine, similar to any other informational site such as a wiki.</p>
        <p>Pokémon and its trademarks are &copy;1995-2025 Nintendo, Creatures, and GAME FREAK.</p>
        <p>All images and names owned and trademarked by Nintendo, Niantic, The Pokémon Company, and GAME FREAK are property of their respective owners.</p>
        <p class="footer-links"><a href="../about/">關於本站</a> · <a href="../contact/">聯絡我們</a> · <a href="../privacy/">隱私權政策</a> · <a href="../disclaimer/">免責聲明</a></p>
    </footer>'''

TPL = u'''<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}｜Pokémon Go 工具箱</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="https://pogokit.com/{dir}/">
<meta name="robots" content="index,follow">
<meta property="og:title" content="{title}｜Pokémon Go 工具箱">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="https://pogokit.com/{dir}/">
<meta property="og:type" content="website">
<link rel="icon" type="image/png" sizes="192x192" href="../img/masterball.png">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8866689605007086" crossorigin="anonymous"></script>
<script src="../js/analytics.js"></script>
<script src="../config.js"></script>
<script src="../js/pageview-counter.js" defer></script>
<script src="../js/zh-search.js"></script>
{css}
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"WebPage","name":"{title}","description":"{desc}","url":"https://pogokit.com/{dir}/","inLanguage":"zh-Hant","isPartOf":{{"@type":"WebSite","name":"Pokémon Go 工具箱","url":"https://pogokit.com/"}},"breadcrumb":{{"@type":"BreadcrumbList","itemListElement":[{{"@type":"ListItem","position":1,"name":"首頁","item":"https://pogokit.com/"}},{{"@type":"ListItem","position":2,"name":"{title}","item":"https://pogokit.com/{dir}/"}}]}}}}
</script>
</head>
<body>
{header}
    <div class="main-container">
{section}
    </div>
{footer}
{bigdata}
<script type="module">
{imports}
document.getElementById('copyright-year').textContent = new Date().getFullYear();
{inits}
</script>
<script src="../js/site-nav.js" defer></script>
</body>
</html>
'''


def sync(html, only):
    """把 index.html 的表頭／頁尾換進各工具頁（其餘內容原封不動）。"""
    header = build_header(html)
    for app, s in SPEC:
        if only and s['dir'] not in only:
            continue
        path = os.path.join(ROOT, s['dir'], 'index.html')
        cur = io.open(path, encoding='utf-8', newline='').read()
        new = cur
        a, b = cur.index('<header class="site-header-main">'), cur.index('</header>') + 9
        new = new[:a] + mark_active(header, s['dir']) + new[b:]
        a = new.index('<footer class="site-footer">')
        b = new.index('</footer>', a) + 9
        new = new[:a] + FOOTER.strip() + new[b:]
        if new != cur:
            io.open(path, 'w', encoding='utf-8', newline='').write(new)
            print('  /%s/  已更新表頭／頁尾' % s['dir'])
        else:
            print('  /%s/  無變動' % s['dir'])


def main():
    html = read('index.html')
    only = sys.argv[1:]
    if '<div id="raids-app"' not in html:
        # index.html 已經拆過了 —— 只剩表頭／頁尾需要同步
        return sync(html, only)
    header = build_header(html)

    for app, s in SPEC:
        if only and s['dir'] not in only:
            continue
        frag = extract_div(html, app)
        frag = rewrite_links(frag)
        # 獨立頁只有這一個 app，一定要是 active 才顯示得出來
        if 'class="app-content active"' not in frag:
            frag = frag.replace('class="app-content"', 'class="app-content active"', 1)

        css = '\n'.join('<link rel="stylesheet" href="../css/%s">' % c
                        for c in ['main.css'] + s['css'])
        # 傳統 <script>（非 module）：這些檔案靠全域變數互通，順序不能亂
        plain = (BIGDATA if s.get('bigdata') else []) + list(s.get('plain', []))
        big = '\n'.join('<script src="../%s"></script>' % d for d in plain)
        imports = "import { %s } from '../js/%s';" % (s['init'], s['mod'])
        inits = '%s();' % s['init']
        if s.get('extra_mod'):
            imports += "\nimport { %s } from '../js/%s';" % (s['extra_init'], s['extra_mod'])
            inits += '\n%s();' % s['extra_init']
        if s.get('firebase'):
            # 這幾頁的選取／釘選會存雲端，要接上表頭的登入按鈕
            imports = "import { initUserAuth } from '../js/user-data.js';\n" + imports
            inits = 'initUserAuth();\n' + inits

        out = TPL.format(title=s['title'], desc=s['desc'], dir=s['dir'], css=css,
                         header=mark_active(header, s['dir']), section=frag, footer=FOOTER,
                         bigdata=big, imports=imports, inits=inits)

        d = os.path.join(ROOT, s['dir'])
        if not os.path.isdir(d):
            os.makedirs(d)
        with io.open(os.path.join(d, 'index.html'), 'w', encoding='utf-8', newline='') as f:
            f.write(out)
        print('  /%s/  %d KB' % (s['dir'], len(out.encode('utf-8')) // 1024))


if __name__ == '__main__':
    main()
