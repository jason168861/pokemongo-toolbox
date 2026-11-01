# -*- coding: utf-8 -*-
"""各語言首頁（/<lang>/）與 CP 列表頁搜尋的文字（build_cp_static_i18n.py 使用）。"""

HOME = {}

HOME["en"] = dict(
    hub_err="Couldn't load the Pokémon list. Please check your connection and try again.",
    home_title="Pokémon GO Toolbox – Trade List Generator, 100% IV CP & PvP IV Rankings",
    home_desc=("Free Pokémon GO tools: make a trade list image with shiny, forms and backgrounds, check the 100% IV (hundo) CP "
               "of any Pokémon, and find the best PvP IVs for Great, Ultra and Master League."),
    home_h1="Pokémon GO Toolbox",
    home_lead="Free tools for everyday Pokémon GO: trade lists, hundo CP checks and PvP IV rankings. No sign-up, works on your phone.",
    c_trade_t="Trade List Generator",
    c_trade_d="Pick shiny, costume, Dynamax and background Pokémon, sort them into Looking For and For Trade, and export one image to share.",
    c_cp_t="100% IV CP",
    c_cp_d="Look up the hundo CP of any Pokémon for Field Research, raids, eggs and weather boost — with an IV calculator.",
    c_pvp_t="PvP IV Rankings",
    c_pvp_d="Enter your Pokémon's IVs to see its rank in Great, Ultra and Master League, plus the best IVs and the CP and level to aim for.",
    more_t="More tools (Traditional Chinese)",
    more_d="The site started as a Traditional Chinese toolbox. These tools are only available in Chinese for now:",
    more_links=["Raids", "Eggs", "Field Research", "Search strings", "Background list"],
    lang_label="Language",
    hub_popular="Popular Pokémon",
    hub_none="No Pokémon found.",
    hub_more="Showing the first {n} results — type more to narrow it down.",
    hub_search_note="Search covers all {n} Pokémon and forms; popular ones open a full page.",
)

HOME["ja"] = dict(
    hub_err="ポケモンの一覧を読み込めませんでした。通信状況を確認して、もう一度お試しください。",
    home_title="ポケモンGO ツールボックス｜交換リスト作成・個体値100のCP・PvP個体値ランキング",
    home_desc=("無料のポケモンGO ツール集：色違い・すがた・背景つきポケモンで交換リストの画像を作成、どのポケモンでも個体値100のCPを確認、"
               "スーパー・ハイパー・マスターリーグのPvP最適個体値を調べられます。"),
    home_h1="ポケモンGO ツールボックス",
    home_lead="毎日のポケモンGO に役立つ無料ツール：交換リスト、個体値100のCPチェック、PvP個体値ランキング。登録不要、スマホで使えます。",
    c_trade_t="交換リスト作成ツール",
    c_trade_d="色違い・コスチューム・ダイマックス・背景つきのポケモンを選び、「ほしいもの」と「ゆずれるもの」に分けて、1枚の画像にまとめて共有できます。",
    c_cp_t="個体値100のCP",
    c_cp_d="フィールドリサーチ・レイド・タマゴ・天候ブーストでの個体値100のCPを調べられます。個体値チェッカーつき。",
    c_pvp_t="PvP個体値ランキング",
    c_pvp_d="個体値を入れると、スーパー・ハイパー・マスターリーグでの順位と、最適な個体値・目標のCPとレベルがわかります。",
    more_t="そのほかのツール（繁体字中国語）",
    more_d="このサイトは繁体字中国語のツール集から始まりました。次のツールは今のところ中国語のみです：",
    more_links=["レイド", "タマゴ", "フィールドリサーチ", "検索ワード", "背景一覧"],
    lang_label="言語",
    hub_popular="人気のポケモン",
    hub_none="見つかりませんでした。",
    hub_more="最初の {n} 件を表示しています。もう少し入力すると絞り込めます。",
    hub_search_note="検索はすべてのポケモンとすがた（{n} 件）が対象で、人気のポケモンは専用ページを開けます。",
)

HOME["ko"] = dict(
    hub_err="포켓몬 목록을 불러오지 못했습니다. 연결 상태를 확인한 뒤 다시 시도해 주세요.",
    home_title="포켓몬 GO 툴박스｜교환 목록 생성기·100% 개체값 CP·PvP 개체값 순위",
    home_desc=("무료 포켓몬 GO 도구: 색이 다른 포켓몬·모습·배경으로 교환 목록 이미지를 만들고, 모든 포켓몬의 100% 개체값 CP를 확인하고, "
               "슈퍼·하이퍼·마스터리그의 PvP 최적 개체값을 찾아보세요."),
    home_h1="포켓몬 GO 툴박스",
    home_lead="매일 쓰는 무료 포켓몬 GO 도구: 교환 목록, 100% 개체값 CP 확인, PvP 개체값 순위. 가입 없이 휴대폰에서 바로 사용하세요.",
    c_trade_t="교환 목록 생성기",
    c_trade_d="색이 다른 포켓몬, 의상, 다이맥스, 배경 포켓몬을 골라 ‘원하는 것’과 ‘줄 수 있는 것’으로 나누고 한 장의 이미지로 공유하세요.",
    c_cp_t="100% 개체값 CP",
    c_cp_d="필드리서치, 레이드, 알, 날씨 부스트에서의 100% 개체값 CP를 확인하세요. 개체값 계산기 포함.",
    c_pvp_t="PvP 개체값 순위",
    c_pvp_d="개체값을 입력하면 슈퍼·하이퍼·마스터리그 순위와 최적 개체값, 목표 CP와 레벨을 알려 줍니다.",
    more_t="다른 도구(중국어 번체)",
    more_d="이 사이트는 중국어 번체 도구 모음에서 시작했습니다. 아래 도구는 지금은 중국어로만 제공됩니다:",
    more_links=["레이드", "알", "필드리서치", "검색어", "배경 목록"],
    lang_label="언어",
    hub_popular="인기 포켓몬",
    hub_none="포켓몬을 찾지 못했습니다.",
    hub_more="처음 {n}개만 표시합니다. 조금 더 입력하면 좁힐 수 있습니다.",
    hub_search_note="검색은 모든 포켓몬과 모습({n}개)이 대상이며, 인기 포켓몬은 전용 페이지로 이동합니다.",
)

HOME["fr"] = dict(
    hub_err="Impossible de charger la liste des Pokémon. Vérifiez votre connexion et réessayez.",
    home_title="Boîte à outils Pokémon GO – liste d’échange, PC à 100 % IV et classement PvP des IV",
    home_desc=("Outils gratuits pour Pokémon GO : créez une image de liste d’échange (chromatiques, formes, fonds), consultez les PC à 100 % IV "
               "de chaque Pokémon et trouvez les meilleurs IV PvP pour la Ligue Super, Hyper et Master."),
    home_h1="Boîte à outils Pokémon GO",
    home_lead="Des outils gratuits pour Pokémon GO au quotidien : listes d’échange, PC des hundos et classement PvP des IV. Sans inscription, sur mobile.",
    c_trade_t="Générateur de liste d’échange",
    c_trade_d="Choisissez des Pokémon chromatiques, costumés, Dynamax ou avec un fond, classez-les en « Je recherche » / « Je propose » et partagez une seule image.",
    c_cp_t="PC à 100 % IV",
    c_cp_d="Consultez les PC d’un hundo pour les études de terrain, les raids, les Œufs et le bonus météo, avec un calculateur d’IV.",
    c_pvp_t="Classement PvP des IV",
    c_pvp_d="Saisissez les IV de votre Pokémon pour voir son rang en Ligue Super, Hyper et Master, ainsi que les meilleurs IV et les PC et niveau à viser.",
    more_t="Autres outils (chinois traditionnel)",
    more_d="Le site est né comme une boîte à outils en chinois traditionnel. Ces outils ne sont pour l’instant disponibles qu’en chinois :",
    more_links=["Raids", "Œufs", "Études de terrain", "Termes de recherche", "Liste des fonds"],
    lang_label="Langue",
    hub_popular="Pokémon populaires",
    hub_none="Aucun Pokémon trouvé.",
    hub_more="Affichage des {n} premiers résultats — précisez votre recherche.",
    hub_search_note="La recherche couvre les {n} Pokémon et formes ; les plus populaires ouvrent une page complète.",
)

HOME["de"] = dict(
    hub_err="Die Pokémon-Liste konnte nicht geladen werden. Prüfe deine Verbindung und versuche es erneut.",
    home_title="Pokémon GO Toolbox – Tauschlisten-Generator, 100 % IV WP & PvP-IV-Rankings",
    home_desc=("Kostenlose Pokémon GO Tools: Tauschliste mit schillernden Pokémon, Formen und Hintergründen als Bild erstellen, 100 % IV WP (Hundo) "
               "jedes Pokémon nachschlagen und die besten PvP-IV für Super-, Hyper- und Meisterliga finden."),
    home_h1="Pokémon GO Toolbox",
    home_lead="Kostenlose Tools für den Pokémon GO Alltag: Tauschlisten, Hundo-WP und PvP-IV-Rankings. Ohne Anmeldung, auch auf dem Handy.",
    c_trade_t="Tauschlisten-Generator",
    c_trade_d="Schillernde, kostümierte, Dynamax- und Hintergrund-Pokémon auswählen, in „Gesucht“ und „Biete“ sortieren und als ein Bild teilen.",
    c_cp_t="100 % IV WP",
    c_cp_d="Hundo-WP jedes Pokémon für Feldforschung, Raids, Eier und Wetterbonus nachschlagen – mit IV-Rechner.",
    c_pvp_t="PvP-IV-Rankings",
    c_pvp_d="IV deines Pokémon eingeben und den Rang in Super-, Hyper- und Meisterliga sehen – samt besten IV sowie Ziel-WP und -Level.",
    more_t="Weitere Tools (traditionelles Chinesisch)",
    more_d="Die Seite begann als Toolbox auf traditionellem Chinesisch. Diese Tools gibt es vorerst nur auf Chinesisch:",
    more_links=["Raids", "Eier", "Feldforschung", "Suchbegriffe", "Hintergrund-Liste"],
    lang_label="Sprache",
    hub_popular="Beliebte Pokémon",
    hub_none="Kein Pokémon gefunden.",
    hub_more="Die ersten {n} Treffer werden angezeigt – tippe weiter, um einzugrenzen.",
    hub_search_note="Die Suche umfasst alle {n} Pokémon und Formen; beliebte Pokémon öffnen eine eigene Seite.",
)

HOME["es"] = dict(
    hub_err="No se pudo cargar la lista de Pokémon. Revisa tu conexión e inténtalo de nuevo.",
    home_title="Herramientas Pokémon GO – lista de intercambio, PC con 100 % IV y ranking PvP de IV",
    home_desc=("Herramientas gratuitas para Pokémon GO: crea una imagen de lista de intercambio con variocolor, formas y fondos, consulta los PC con "
               "100 % IV de cualquier Pokémon y encuentra los mejores IV para PvP en Liga Super Ball, Ultra Ball y Master Ball."),
    home_h1="Herramientas Pokémon GO",
    home_lead="Herramientas gratuitas para el día a día en Pokémon GO: listas de intercambio, PC de hundos y ranking PvP de IV. Sin registro y desde el móvil.",
    c_trade_t="Generador de listas de intercambio",
    c_trade_d="Elige Pokémon variocolor, disfrazados, Dinamax o con fondo, sepáralos en «Busco» y «Ofrezco» y comparte una sola imagen.",
    c_cp_t="PC con 100 % IV",
    c_cp_d="Consulta los PC de un hundo para investigación de campo, incursiones, Huevos y clima potenciado, con calculadora de IV.",
    c_pvp_t="Ranking PvP de IV",
    c_pvp_d="Escribe los IV de tu Pokémon para ver su puesto en la Liga Super Ball, Ultra Ball y Master Ball, además de los mejores IV y los PC y nivel objetivo.",
    more_t="Más herramientas (chino tradicional)",
    more_d="El sitio nació como una caja de herramientas en chino tradicional. Estas herramientas, por ahora, solo están en chino:",
    more_links=["Incursiones", "Huevos", "Investigación de campo", "Términos de búsqueda", "Lista de fondos"],
    lang_label="Idioma",
    hub_popular="Pokémon populares",
    hub_none="No se encontró ningún Pokémon.",
    hub_more="Se muestran los {n} primeros resultados; escribe más para afinar.",
    hub_search_note="La búsqueda incluye los {n} Pokémon y formas; los más populares abren una página completa.",
)

# 中文工具頁（「更多工具」連結）
MORE_PATHS = ["raids/", "eggs/", "research/", "search-filters/", "backgrounds/"]
