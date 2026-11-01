# -*- coding: utf-8 -*-
"""/<lang>/pvp-ranker/ 的介面文字與說明（build_pvp_i18n.py 使用）。

js 開頭的 key 會放進 window.PVP_I18N，覆蓋 js/pvp-ranker.js 的中文預設值。
{bulba} 會換成該語言的妙蛙種子名稱。
"""

P = {}

P["en"] = dict(
    title="Pokémon GO PvP IV Rankings – Best IVs for Great, Ultra & Master League | Pokémon GO Toolbox",
    desc=("Check your Pokémon's PvP IV rank in Great League, Ultra League and Master League, see the best IV spreads with their CP "
          "and level, and compare its evolutions. Free and fast on mobile."),
    h1="Pokémon GO PvP IV Rankings", crumb="PvP IV Rankings",
    panel="Search", panel_hint="(collapsible, movable)", close_aria="Collapse the panel", open_aria="Open the search panel",
    toggle="⚙ Adjust", in_label="Pokémon name or Pokédex number", in_ph="e.g. {bulba} or 1",
    atk="Attack (ATK)", def_="Defense (DEF)", hp="HP (STA)", cur_lv="Current level:", cur_cp="Current CP",
    qs_empty="Choose a Pokémon to see its ranks", qs_more="See full results (incl. evolutions) ↓",
    js=dict(evoOver="After evolving its CP will be about {cp}, over the cap", nowOver="Current CP {cp} is over the cap",
            over="Over cap", unranked="Not ranked", fast="Fast", charged="Charged", yourRank="Your rank",
            noRank="Your IV combination is not ranked in this league.", topIv="Rank 1 IVs",
            loadErrHtml="<h1>Data failed to load</h1><p>Please reload the page.</p>"),
    guide=("<h2>How PvP IV rankings work</h2>"
           "<p>In Great League (1,500 CP cap) and Ultra League (2,500 CP cap) the best IVs are usually <strong>not 15/15/15</strong>. "
           "A lower Attack IV lets a Pokémon reach a higher level under the CP cap, which raises its Defense and HP more than it loses "
           "in Attack — so its overall bulk (stat product) ends up higher.</p>"
           "<p>Enter your Pokémon's IVs to see where they rank among all 4,096 combinations in each league, the level and CP to power up to, "
           "and how the evolutions in the same family compare. Rank 1 is the best possible spread; outside the most competitive play, "
           "anything near the top is usually good enough.</p>"
           "<p>Master League has no CP cap, so a 15/15/15 Pokémon is the best there.</p>"),
)

P["ja"] = dict(
    title="ポケモンGO PvP個体値ランキング｜スーパー・ハイパー・マスターリーグの最適個体値｜ポケモンGO ツールボックス",
    desc=("ポケモンの個体値がスーパーリーグ・ハイパーリーグ・マスターリーグで何位かを調べ、最適な個体値とそのCP・レベル、"
          "進化後との比較を確認できます。無料、スマホでもすぐ使えます。"),
    h1="ポケモンGO PvP個体値ランキング", crumb="PvP個体値ランキング",
    panel="検索条件", panel_hint="（折りたたみ・移動できます）", close_aria="条件パネルを閉じる", open_aria="条件パネルを開く",
    toggle="⚙ 条件を変更", in_label="ポケモンの名前か図鑑番号", in_ph="例：{bulba} または 1",
    atk="こうげき (ATK)", def_="ぼうぎょ (DEF)", hp="HP (STA)", cur_lv="現在のレベル：", cur_cp="現在のCP",
    qs_empty="ポケモンを選ぶと順位が表示されます", qs_more="すべての結果を見る（進化後を含む）↓",
    js=dict(evoOver="進化後のCPは約 {cp} で、上限を超えます", nowOver="現在のCP {cp} は上限を超えています",
            over="上限超え", unranked="ランク外", fast="通常わざ", charged="ゲージわざ", yourRank="あなたの順位",
            noRank="この個体値はこのリーグのランキングに入っていません。", topIv="1位の個体値",
            loadErrHtml="<h1>データを読み込めませんでした</h1><p>ページを再読み込みしてください。</p>"),
    guide=("<h2>PvPの個体値ランキングのしくみ</h2>"
           "<p>スーパーリーグ（CP上限1500）とハイパーリーグ（CP上限2500）では、最適な個体値は<strong>15/15/15 ではない</strong>ことがほとんどです。"
           "こうげきの個体値が低いほど上限内で高いレベルまで強化でき、ぼうぎょとHPの伸びが、こうげきの低さを上回ります。"
           "その結果、総合的な耐久（ステータス積）が高くなります。</p>"
           "<p>個体値を入れると、各リーグで 4,096 通りのうち何位か、強化すべきレベルとCP、同じ進化系統のポケモンとの比較がわかります。"
           "1位が理論上の最適値ですが、上位であれば普段の対戦では十分です。</p>"
           "<p>マスターリーグにはCP上限がないため、15/15/15 がいちばん強くなります。</p>"),
)

P["ko"] = dict(
    title="포켓몬 GO PvP 개체값 순위｜슈퍼·하이퍼·마스터리그 최적 개체값｜포켓몬 GO 툴박스",
    desc=("포켓몬의 개체값이 슈퍼리그·하이퍼리그·마스터리그에서 몇 위인지 확인하고, 최적 개체값과 그 CP·레벨, 진화형과의 비교를 볼 수 있습니다. "
          "무료이며 휴대폰에서도 빠르게 사용할 수 있습니다."),
    h1="포켓몬 GO PvP 개체값 순위", crumb="PvP 개체값 순위",
    panel="검색 조건", panel_hint="(접기·이동 가능)", close_aria="조건 패널 접기", open_aria="조건 패널 열기",
    toggle="⚙ 조건 변경", in_label="포켓몬 이름 또는 도감 번호", in_ph="예: {bulba} 또는 1",
    atk="공격 (ATK)", def_="방어 (DEF)", hp="HP (STA)", cur_lv="현재 레벨:", cur_cp="현재 CP",
    qs_empty="포켓몬을 고르면 순위가 표시됩니다", qs_more="전체 결과 보기(진화형 포함) ↓",
    js=dict(evoOver="진화 후 CP는 약 {cp}로 상한을 넘습니다", nowOver="현재 CP {cp}는 상한을 넘었습니다",
            over="상한 초과", unranked="순위 밖", fast="노말 기술", charged="스페셜 기술", yourRank="내 순위",
            noRank="이 개체값 조합은 이 리그의 순위에 들지 않습니다.", topIv="1위 개체값",
            loadErrHtml="<h1>데이터를 불러오지 못했습니다</h1><p>페이지를 새로 고침해 주세요.</p>"),
    guide=("<h2>PvP 개체값 순위의 원리</h2>"
           "<p>슈퍼리그(CP 상한 1500)와 하이퍼리그(CP 상한 2500)에서는 최적 개체값이 대부분 <strong>15/15/15가 아닙니다</strong>. "
           "공격 개체값이 낮을수록 CP 상한 안에서 더 높은 레벨까지 강화할 수 있어, 방어와 HP가 오르는 폭이 공격 손해보다 커집니다. "
           "그 결과 전체적인 내구(스탯 곱)가 높아집니다.</p>"
           "<p>개체값을 입력하면 리그별로 4,096가지 조합 중 몇 위인지, 강화할 레벨과 CP, 같은 진화 계열과의 비교를 볼 수 있습니다. "
           "1위가 이론상 최적이지만, 상위권이라면 일반적인 대전에는 충분합니다.</p>"
           "<p>마스터리그는 CP 상한이 없으므로 15/15/15가 가장 강합니다.</p>"),
)

P["fr"] = dict(
    title="Classement PvP des IV Pokémon GO – meilleurs IV en Ligue Super, Hyper et Master | Boîte à outils Pokémon GO",
    desc=("Découvrez le rang PvP des IV de votre Pokémon en Ligue Super, Hyper et Master, les meilleures combinaisons avec leurs PC et "
          "niveau, et comparez ses évolutions. Gratuit et rapide sur mobile."),
    h1="Classement PvP des IV Pokémon GO", crumb="Classement PvP des IV",
    panel="Recherche", panel_hint="(repliable, déplaçable)", close_aria="Replier le panneau", open_aria="Ouvrir le panneau de recherche",
    toggle="⚙ Modifier", in_label="Nom du Pokémon ou numéro du Pokédex", in_ph="ex. : {bulba} ou 1",
    atk="Attaque (ATK)", def_="Défense (DEF)", hp="PV (END)", cur_lv="Niveau actuel :", cur_cp="PC actuels",
    qs_empty="Choisissez un Pokémon pour voir ses rangs", qs_more="Voir tous les résultats (évolutions comprises) ↓",
    js=dict(evoOver="Après évolution, ses PC seront d’environ {cp} : au-dessus de la limite", nowOver="Les PC actuels ({cp}) dépassent la limite",
            over="Au-dessus de la limite", unranked="Non classé", fast="Immédiate", charged="Chargée", yourRank="Votre rang",
            noRank="Votre combinaison d’IV n’est pas classée dans cette ligue.", topIv="IV n° 1",
            loadErrHtml="<h1>Échec du chargement des données</h1><p>Veuillez recharger la page.</p>"),
    guide=("<h2>Comment fonctionne le classement PvP des IV</h2>"
           "<p>En Ligue Super (limite de 1 500 PC) et en Ligue Hyper (limite de 2 500 PC), les meilleurs IV ne sont presque jamais "
           "<strong>15/15/15</strong>. Un IV d’Attaque plus faible permet de monter plus haut en niveau sous la limite de PC, ce qui augmente "
           "davantage la Défense et les PV que l’Attaque perdue : la robustesse globale (produit des statistiques) est donc plus élevée.</p>"
           "<p>Saisissez les IV de votre Pokémon pour voir son rang parmi les 4 096 combinaisons de chaque ligue, le niveau et les PC à viser, "
           "et la comparaison avec les évolutions de la même famille. Le rang 1 est la combinaison idéale ; hors compétition de haut niveau, "
           "un bon rang suffit généralement.</p>"
           "<p>La Ligue Master n’a pas de limite de PC : un Pokémon 15/15/15 y est le meilleur.</p>"),
)

P["de"] = dict(
    title="Pokémon GO PvP-IV-Rankings – beste IV für Super-, Hyper- & Meisterliga | Pokémon GO Toolbox",
    desc=("Prüfe den PvP-IV-Rang deines Pokémon in Super-, Hyper- und Meisterliga, sieh die besten IV-Kombinationen mit WP und Level "
          "und vergleiche seine Entwicklungen. Kostenlos und schnell auf dem Handy."),
    h1="Pokémon GO PvP-IV-Rankings", crumb="PvP-IV-Rankings",
    panel="Suche", panel_hint="(einklappbar, verschiebbar)", close_aria="Bereich einklappen", open_aria="Suchbereich öffnen",
    toggle="⚙ Ändern", in_label="Pokémon-Name oder Pokédex-Nummer", in_ph="z. B. {bulba} oder 1",
    atk="Angriff (ATK)", def_="Verteidigung (DEF)", hp="KP (AUSD)", cur_lv="Aktuelles Level:", cur_cp="Aktuelle WP",
    qs_empty="Wähle ein Pokémon, um die Ränge zu sehen", qs_more="Alle Ergebnisse (inkl. Entwicklungen) ↓",
    js=dict(evoOver="Nach der Entwicklung hat es etwa {cp} WP – über dem Limit", nowOver="Aktuelle WP {cp} liegen über dem Limit",
            over="Über dem Limit", unranked="Nicht gerankt", fast="Sofort", charged="Lade", yourRank="Dein Rang",
            noRank="Deine IV-Kombination ist in dieser Liga nicht gerankt.", topIv="IV auf Rang 1",
            loadErrHtml="<h1>Daten konnten nicht geladen werden</h1><p>Bitte lade die Seite neu.</p>"),
    guide=("<h2>So funktionieren PvP-IV-Rankings</h2>"
           "<p>In der Superliga (WP-Limit 1.500) und der Hyperliga (WP-Limit 2.500) sind die besten IV fast nie <strong>15/15/15</strong>. "
           "Ein niedrigerer Angriffs-IV lässt das Pokémon unter dem WP-Limit ein höheres Level erreichen; dadurch steigen Verteidigung und KP "
           "stärker, als Angriff verloren geht – die Gesamtwerte (Stat-Produkt) sind also höher.</p>"
           "<p>Gib die IV deines Pokémon ein und sieh, auf welchem Rang sie unter allen 4.096 Kombinationen in jeder Liga liegen, auf welches "
           "Level und welche WP du hochleveln solltest und wie die Entwicklungen derselben Familie abschneiden. Rang 1 ist die ideale "
           "Kombination; abseits von Turnieren reicht meist ein guter Rang.</p>"
           "<p>Die Meisterliga hat kein WP-Limit, dort ist ein 15/15/15-Pokémon am stärksten.</p>"),
)

P["es"] = dict(
    title="Ranking PvP de IV de Pokémon GO – mejores IV para Liga Super Ball, Ultra Ball y Master Ball | Herramientas Pokémon GO",
    desc=("Comprueba el puesto PvP de los IV de tu Pokémon en la Liga Super Ball, Ultra Ball y Master Ball, mira las mejores combinaciones "
          "con sus PC y nivel y compara sus evoluciones. Gratis y rápido en el móvil."),
    h1="Ranking PvP de IV de Pokémon GO", crumb="Ranking PvP de IV",
    panel="Búsqueda", panel_hint="(plegable, movible)", close_aria="Plegar el panel", open_aria="Abrir el panel de búsqueda",
    toggle="⚙ Ajustar", in_label="Nombre del Pokémon o número de la Pokédex", in_ph="p. ej. {bulba} o 1",
    atk="Ataque (ATK)", def_="Defensa (DEF)", hp="PS (RES)", cur_lv="Nivel actual:", cur_cp="PC actuales",
    qs_empty="Elige un Pokémon para ver sus puestos", qs_more="Ver todos los resultados (incluye evoluciones) ↓",
    js=dict(evoOver="Tras evolucionar tendrá unos {cp} PC, por encima del límite", nowOver="Los PC actuales ({cp}) superan el límite",
            over="Supera el límite", unranked="Sin clasificar", fast="Rápido", charged="Cargado", yourRank="Tu puesto",
            noRank="Tu combinación de IV no está clasificada en esta liga.", topIv="IV n.º 1",
            loadErrHtml="<h1>No se pudieron cargar los datos</h1><p>Vuelve a cargar la página.</p>"),
    guide=("<h2>Cómo funciona el ranking PvP de IV</h2>"
           "<p>En la Liga Super Ball (límite de 1500 PC) y la Liga Ultra Ball (límite de 2500 PC), los mejores IV casi nunca son "
           "<strong>15/15/15</strong>. Un IV de Ataque más bajo permite subir más de nivel sin pasar del límite de PC, lo que aumenta la Defensa "
           "y los PS más de lo que se pierde en Ataque: la resistencia total (producto de estadísticas) es mayor.</p>"
           "<p>Escribe los IV de tu Pokémon para ver su puesto entre las 4096 combinaciones de cada liga, el nivel y los PC a los que subirlo "
           "y cómo se comparan las evoluciones de la misma familia. El puesto 1 es la combinación ideal; fuera del juego competitivo, "
           "un buen puesto suele ser suficiente.</p>"
           "<p>La Liga Master Ball no tiene límite de PC, así que un Pokémon 15/15/15 es el mejor allí.</p>"),
)
