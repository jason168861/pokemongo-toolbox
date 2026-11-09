# -*- coding: utf-8 -*-
"""/<lang>/cp/ 靜態頁的介面文字與句型（build_cp_static_i18n.py 使用）。

寶可夢名稱、型態、屬性、天氣、聯盟、招式名稱不在這裡 —— 那些用遊戲官方文字
（data/cp_i18n_terms.json）。這裡只放句型，佔位字用 str.format 的 {name} 寫法。
注意各語言的 CP／HP 縮寫不同：德文 WP／KP，法文 PC／PV，西文 PC／PS。
"""

STR = {}

STR["en"] = dict(
    html_lang="en", og_locale="en_US", sep=", ", type_sep="/", paren="{a} ({b})", lv="Lv",
    site="Pokémon GO Toolbox", hub_name="100% IV CP", crumb_aria="Breadcrumb",
    title="{name} 100% IV CP (Hundo) – Raid & Research CP | Pokémon GO Toolbox",
    desc=("{name} (#{dex}, {types}) hundo CP: Field Research Lv15 {cp15}, Raids & Eggs Lv20 {cp20}, "
          "Weather Boosted Lv25 {cp25}. Plus an IV calculator, a Lv1–50 CP chart, type matchups and PvP rankings."),
    og_title="{name} 100% IV CP (Hundo) – Lv1–50 CP chart",
    h1="{name} 100% IV CP",
    t15="🔬 Field Research", t20="⚔️ Raids & Eggs", t25="☀️ Weather Boost",
    hundo_note=("These are the CPs at <strong>100% IV (15/15/15)</strong>. If a Pokémon from Field Research (Lv15), "
                "a raid or an egg (Lv20), or a weather-boosted raid (Lv25) shows exactly this CP, it is almost certainly "
                "a hundo. Not sure? Check it with the IV calculator below."),
    pill_max="Max CP", stats_pill="Atk <b>{a}</b> · Def <b>{d}</b> · Sta <b>{s}</b>",
    lead=("{name} (#{dex}) is a <strong>{types}</strong>-type Pokémon with base stats of <strong>{a}</strong> Attack, "
          "{d} Defense and {s} Stamina. At 100% IV its max CP is {cp40} at level 40 and {cp50} at level 50."),
    rev_h="{name} IV calculator",
    rev_sub="Enter the CP you saw when catching it (HP is optional) to list every possible level and IV combination.",
    f_cp="CP", f_hp="HP", f_lv="Level", lv_any="Any", lv15="Lv15 Field Research", lv20="Lv20 Raids & Eggs",
    lv25="Lv25 Weather Boost", btn="Calculate", ph_hp="Optional", ph_cp="e.g. {cp20}",
    rv=dict(sum1="CP {cp}{hp}: exactly one match — IV <strong>{hi}%</strong>. ",
            need="Please enter a CP (10 or higher).",
            none="No matching combination. Check the CP — weather boost and power-ups change the level.",
            sum="CP {cp}{hp}: {n} possible combinations, IV about <strong>{lo}%–{hi}%</strong>. ", hpPart=", HP {hp}",
            narrow="Add the HP to narrow it down.", lv="Lv", thLv="Level", thIv="Atk / Def / Sta", thHp="HP",
            all="Show all {n}"),
    ivt_h="{name} high-IV CP & HP chart",
    ivt_sub=("The 35 best IV combinations (IV% ≥ 91.1%) with their CP and HP at levels 15, 20, 25 and 40. "
             "Atk / Def / Sta are the IVs (0–15)."),
    ivt_iv="IVs Atk/Def/Sta", a="Atk", d="Def", s="Sta",
    cpt_h="{name} CP chart (Lv1–Lv50)",
    cpt_sub="<strong>100% IV</strong> (15/15/15) is the highest CP at each level and <strong>0% IV</strong> (0/0/0) the lowest.",
    cpt_cap="{name} CP by level (100% IV / 0% IV)", th_lv="Level", th_max="100% IV", th_min="0% IV", th_note="Notes",
    key15="🔬 Field Research", key20="⚔️ Raids (no weather boost) · 🥚 Eggs", key25="☀️ Raids (weather boosted)",
    bb="⭐ Best Buddy boost",
    cpt_foot="Lv{bb} is reached only with the Best Buddy boost; regular power-ups stop at Lv{max}. Data: Pokémon GO GAME_MASTER.",
    mu_h="{name} weaknesses & resistances", weak="Weak to", resist="Resists",
    mu_note="{name} is weak to {wlist}{dbl} and resists {rlist}. <strong>{prim}</strong>-type moves deal the most damage to it.",
    mu_dbl=" (double weakness: {dbls})",
    mu_w=" In <strong>{w}</strong> weather its moves are boosted, and catches get the weather boost (higher level and CP).",
    mu_none="Not enough type data.",
    role_h="{name} role & best moves",
    role_atk_hi=("{name}'s stats lean towards <strong>very high Attack</strong> (Attack {a} / Defense {d} / Stamina {s}), "
                 "so it is best used as a damage dealer in raids."),
    role_atk=("{name}'s stats lean towards <strong>Attack</strong> (Attack {a} / Defense {d} / Stamina {s}), "
              "so it works well as a damage dealer in raids."),
    role_def=("{name}'s stats lean towards <strong>Defense</strong> (Attack {a} / Defense {d} / Stamina {s}). "
              "It suits gym defense and drawn-out battles."),
    role_sta=("{name}'s stats lean towards <strong>Stamina</strong> (Attack {a} / Defense {d} / Stamina {s}). "
              "Its bulk keeps it on the field for a long time."),
    rec="Recommended moves", basis="(based on the {league})", buddy="Buddy distance", km="{km} km", nodata="Not enough data",
    lg_h="{name} PvP league rankings",
    lg_note="In PvP, {name} performs best in the <strong>{league}</strong> (rank {rank} of {total}, score {score}){extra}.",
    lg_extra=" — the {master} has no CP cap", lg_none="There is limited PvP ranking data for {name}.",
    lg_row="<b>{rank}</b> / {total} · {score} pts",
    rel_h="Related Pokémon", prev="← Previous", next="Next →", same="Popular Pokémon of the same type", fam_h="Other forms & evolutions",
    cta="Browse all Pokémon →", fab="Search Pokémon",
    foot_tag="100% IV CP, PvP rankings and a trade list generator",
    about="About", privacy="Privacy Policy", disclaimer="Disclaimer", trade="Trade List Generator",
    hub_title="Pokémon GO 100% IV CP List – Hundo CP for Raids, Research & Eggs | Pokémon GO Toolbox",
    hub_desc=("Hundo (100% IV) CP for {n} popular Pokémon in Pokémon GO: Field Research Lv15, Raids & Eggs Lv20 and "
              "Weather Boosted Lv25 — with an IV calculator and a full CP chart for each."),
    hub_h1="Pokémon GO 100% IV CP list",
    hub_intro=("<p>Spotting a hundo is all about the CP. Pokémon from <strong>Field Research</strong> are caught at level 15, "
               "<strong>raids and eggs</strong> at level 20 and <strong>weather-boosted raids</strong> at level 25 — so each "
               "Pokémon has one exact CP that means 100% IV.</p><p>Pick a Pokémon to see its hundo CP, an IV calculator "
               "and a CP chart for every level.</p>"),
    hub_q="Search by name or Pokédex number",
    hub_count="{n} popular Pokémon · the number under each name is its 100% IV CP at Lv20 (raids & eggs)",
    tile="Lv20 {cp}", ad="Advertisement",
)

STR["ja"] = dict(
    html_lang="ja", og_locale="ja_JP", sep="・", type_sep="・", paren="{a}（{b}）", lv="Lv",
    site="ポケモンGO ツールボックス", hub_name="個体値100 CP", crumb_aria="パンくずリスト",
    title="{name} 個体値100のCP｜レイド・タスク・天候ブースト｜ポケモンGO ツールボックス",
    desc=("{name}（#{dex}・{types}）の個体値100%のCP：フィールドリサーチ Lv15 {cp15}、レイド・タマゴ Lv20 {cp20}、"
          "天候ブースト Lv25 {cp25}。CPから個体値を調べる計算機、Lv1〜50 のCP表、タイプ相性、PvPランキングも掲載。"),
    og_title="{name} 個体値100のCP｜Lv1〜50 CP表",
    h1="{name} 個体値100のCP",
    t15="🔬 フィールドリサーチ", t20="⚔️ レイド・タマゴ", t25="☀️ 天候ブースト",
    hundo_note=("上の数字は<strong>個体値100%（15/15/15）</strong>のときのCPです。フィールドリサーチ（Lv15）、レイドやタマゴ（Lv20）、"
                "天候ブーストのレイド（Lv25）で手に入れたポケモンのCPがこの数字ちょうどなら、ほぼ確実に個体値100です。"
                "確かめたいときは下の計算機を使ってください。"),
    pill_max="最大CP", stats_pill="こうげき <b>{a}</b> · ぼうぎょ <b>{d}</b> · HP <b>{s}</b>",
    lead=("{name}（#{dex}）は<strong>{types}</strong>タイプのポケモンで、種族値は こうげき <strong>{a}</strong>／ぼうぎょ {d}／HP {s}。"
          "個体値100%の最大CPは Lv40 で {cp40}、Lv50 で {cp50} です。"),
    rev_h="{name} 個体値チェッカー（CPから逆算）",
    rev_sub="捕まえたときのCP（HPも入れるとより正確）から、考えられるレベルと個体値の組み合わせをすべて表示します。",
    f_cp="CP", f_hp="HP", f_lv="レベル", lv_any="指定なし", lv15="Lv15 フィールドリサーチ", lv20="Lv20 レイド・タマゴ",
    lv25="Lv25 天候ブースト", btn="調べる", ph_hp="任意", ph_cp="例：{cp20}",
    rv=dict(sum1="CP {cp}{hp}：1 通りだけ、個体値 <strong>{hi}%</strong>。",
            need="CPを入力してください（10以上）。",
            none="当てはまる組み合わせがありません。CPを確認してください（天候ブーストや強化でレベルが変わります）。",
            sum="CP {cp}{hp}：{n} 通り、個体値はおよそ <strong>{lo}%〜{hi}%</strong>。", hpPart="・HP {hp}",
            narrow="HPを入れると絞り込めます。", lv="Lv", thLv="レベル", thIv="こうげき / ぼうぎょ / HP", thHp="HP",
            all="すべて表示（{n} 件）"),
    ivt_h="{name} 高個体値のCP・HP一覧",
    ivt_sub="個体値の合計が高い35通り（91.1%以上）と、Lv15／20／25／40 でのCPとHP。こうげき／ぼうぎょ／HP は個体値（0〜15）です。",
    ivt_iv="個体値 攻/防/HP", a="攻", d="防", s="HP",
    cpt_h="{name} レベル別CP一覧（Lv1〜Lv50）",
    cpt_sub="<strong>個体値100%</strong>（15/15/15）が各レベルの最大CP、<strong>個体値0%</strong>（0/0/0）が最小CPです。",
    cpt_cap="{name} レベル別CP（個体値100% / 0%）", th_lv="レベル", th_max="個体値100%", th_min="個体値0%", th_note="メモ",
    key15="🔬 フィールドリサーチ", key20="⚔️ レイド（天候ブーストなし）· 🥚 タマゴ", key25="☀️ レイド（天候ブースト）",
    bb="⭐ ベストバディブースト",
    cpt_foot="Lv{bb} はベストバディブースト時の上限で、通常の強化は Lv{max} までです。データ：Pokémon GO GAME_MASTER。",
    mu_h="{name} の弱点と耐性", weak="弱点", resist="耐性",
    mu_note="{name} の弱点は {wlist}{dbl}、耐性は {rlist} です。<strong>{prim}</strong>タイプのわざがいちばん効果的です。",
    mu_dbl="（{dbls} は二重弱点）",
    mu_w=" 天候が<strong>{w}</strong>のときはわざが強化され、捕まえるポケモンも天候ブーストでレベルとCPが高くなります。",
    mu_none="タイプのデータが足りません。",
    role_h="{name} の役割とおすすめわざ",
    role_atk_hi="{name} は<strong>こうげきが特に高い</strong>能力です（こうげき {a}／ぼうぎょ {d}／HP {s}）。レイドのアタッカーとして活躍します。",
    role_atk="{name} は<strong>こうげき寄り</strong>の能力です（こうげき {a}／ぼうぎょ {d}／HP {s}）。レイドのアタッカーに向いています。",
    role_def="{name} は<strong>ぼうぎょ寄り</strong>の能力です（こうげき {a}／ぼうぎょ {d}／HP {s}）。ジムの防衛や長期戦に向いています。",
    role_sta="{name} は<strong>HP寄り</strong>の能力です（こうげき {a}／ぼうぎょ {d}／HP {s}）。耐久力が高く、長く場に残れます。",
    rec="おすすめわざ", basis="（{league}の評価）", buddy="相棒の距離", km="{km} km", nodata="データ不足",
    lg_h="{name} のPvPリーグ評価",
    lg_note="PvPでは <strong>{league}</strong> がいちばん向いています（{total} 匹中 {rank} 位、スコア {score}）{extra}。",
    lg_extra="（{master}はCP上限なし）", lg_none="{name} のPvPランキングのデータは限られています。",
    lg_row="<b>{rank}</b> / {total} · {score} 点",
    rel_h="関連ポケモン", prev="← 前", next="次 →", same="同じタイプの人気ポケモン", fam_h="ほかのすがた・進化",
    cta="ポケモン一覧を見る →", fab="ポケモンを探す",
    foot_tag="個体値100のCP、PvPランキング、交換リスト作成",
    about="このサイトについて", privacy="プライバシーポリシー", disclaimer="免責事項", trade="交換リスト作成ツール",
    hub_title="ポケモンGO 個体値100 CP一覧｜レイド・タスク・タマゴの100%CP｜ポケモンGO ツールボックス",
    hub_desc=("ポケモンGO の人気ポケモン {n} 匹の個体値100（100%）CP一覧：フィールドリサーチ Lv15、レイド・タマゴ Lv20、"
              "天候ブースト Lv25。各ポケモンのページには個体値チェッカーとレベル別CP表もあります。"),
    hub_h1="ポケモンGO 個体値100 CP一覧",
    hub_intro=("<p>個体値100を見分ける決め手はCPです。<strong>フィールドリサーチ</strong>のポケモンは Lv15、"
               "<strong>レイドとタマゴ</strong>は Lv20、<strong>天候ブーストのレイド</strong>は Lv25 で手に入るため、"
               "個体値100を示すCPはポケモンごとにひとつに決まります。</p><p>ポケモンを選ぶと、個体値100のCP、"
               "個体値チェッカー、レベル別CP表が見られます。</p>"),
    hub_q="名前か図鑑番号で検索",
    hub_count="人気ポケモン {n} 匹 · 名前の下の数字はレイド・タマゴ（Lv20）での個体値100のCP",
    tile="Lv20 {cp}", ad="広告",
)

STR["ko"] = dict(
    html_lang="ko", og_locale="ko_KR", sep=", ", type_sep="/", paren="{a} ({b})", lv="Lv",
    site="포켓몬 GO 툴박스", hub_name="100% 개체값 CP", crumb_aria="이동 경로",
    title="{name} 100% 개체값 CP｜레이드·필드리서치·날씨 부스트｜포켓몬 GO 툴박스",
    desc=("{name}(#{dex}, {types}) 100% 개체값 CP: 필드리서치 Lv15 {cp15}, 레이드·알 Lv20 {cp20}, 날씨 부스트 Lv25 {cp25}. "
          "CP로 개체값을 역산하는 계산기, Lv1~50 CP 표, 타입 상성과 PvP 순위도 확인하세요."),
    og_title="{name} 100% 개체값 CP｜Lv1~50 CP 표",
    h1="{name} 100% 개체값 CP",
    t15="🔬 필드리서치", t20="⚔️ 레이드·알", t25="☀️ 날씨 부스트",
    hundo_note=("위 숫자는 <strong>개체값 100%(15/15/15)</strong>일 때의 CP입니다. 필드리서치(Lv15), 레이드나 알(Lv20), "
                "날씨 부스트 레이드(Lv25)에서 얻은 포켓몬의 CP가 이 숫자와 정확히 같다면 거의 확실히 100% 개체입니다. "
                "확인하려면 아래 계산기를 사용하세요."),
    pill_max="최대 CP", stats_pill="공격 <b>{a}</b> · 방어 <b>{d}</b> · HP <b>{s}</b>",
    lead=("{name}(#{dex})의 타입은 <strong>{types}</strong>이며, 종족값은 공격 <strong>{a}</strong> / 방어 {d} / HP {s}입니다. "
          "개체값 100%일 때 최대 CP는 Lv40에서 {cp40}, Lv50에서 {cp50}입니다."),
    rev_h="{name} 개체값 계산기(CP 역산)",
    rev_sub="잡았을 때의 CP(HP를 함께 입력하면 더 정확)를 입력하면 가능한 레벨과 개체값 조합을 모두 보여 줍니다.",
    f_cp="CP", f_hp="HP", f_lv="레벨", lv_any="전체", lv15="Lv15 필드리서치", lv20="Lv20 레이드·알", lv25="Lv25 날씨 부스트",
    btn="계산", ph_hp="선택 입력", ph_cp="예: {cp20}",
    rv=dict(sum1="CP {cp}{hp}: 조합은 1개뿐, 개체값 <strong>{hi}%</strong>. ",
            need="CP를 입력하세요(10 이상).",
            none="맞는 조합이 없습니다. CP를 확인하세요(날씨 부스트나 강화로 레벨이 바뀝니다).",
            sum="CP {cp}{hp}: 가능한 조합 {n}개, 개체값 약 <strong>{lo}%~{hi}%</strong>. ", hpPart=", HP {hp}",
            narrow="HP를 입력하면 범위를 좁힐 수 있습니다.", lv="Lv", thLv="레벨", thIv="공격 / 방어 / HP", thHp="HP",
            all="전체 보기({n}개)"),
    ivt_h="{name} 고개체 CP·HP 표",
    ivt_sub="개체값 합계가 높은 35가지 조합(91.1% 이상)과 Lv15/20/25/40에서의 CP와 HP입니다. 공격/방어/HP는 개체값(0~15)입니다.",
    ivt_iv="개체값 공격/방어/HP", a="공", d="방", s="HP",
    cpt_h="{name} 레벨별 CP 표(Lv1~Lv50)",
    cpt_sub="<strong>개체값 100%</strong>(15/15/15)가 각 레벨의 최대 CP, <strong>개체값 0%</strong>(0/0/0)가 최소 CP입니다.",
    cpt_cap="{name} 레벨별 CP(개체값 100% / 0%)", th_lv="레벨", th_max="개체값 100%", th_min="개체값 0%", th_note="비고",
    key15="🔬 필드리서치", key20="⚔️ 레이드(날씨 부스트 없음) · 🥚 알", key25="☀️ 레이드(날씨 부스트)",
    bb="⭐ 베스트 파트너 부스트",
    cpt_foot="Lv{bb}는 베스트 파트너 부스트를 받을 때의 상한이며, 일반 강화는 Lv{max}까지입니다. 데이터: Pokémon GO GAME_MASTER.",
    mu_h="{name} 약점과 저항", weak="약점", resist="저항",
    mu_note="약점: {wlist}{dbl}. 저항: {rlist}. <strong>{prim}</strong> 타입 기술로 공격하면 가장 효과적입니다.",
    mu_dbl=" (이중 약점: {dbls})",
    mu_w=" 날씨가 <strong>{w}</strong>일 때 기술이 강화되고, 잡는 포켓몬도 날씨 부스트로 레벨과 CP가 높아집니다.",
    mu_none="타입 데이터가 부족합니다.",
    role_h="{name} 역할과 추천 기술",
    role_atk_hi="{name}의 능력치는 <strong>공격이 매우 높은</strong> 편입니다(공격 {a} / 방어 {d} / HP {s}). 레이드 딜러로 활약합니다.",
    role_atk="{name}의 능력치는 <strong>공격</strong> 위주입니다(공격 {a} / 방어 {d} / HP {s}). 레이드 딜러에 적합합니다.",
    role_def="{name}의 능력치는 <strong>방어</strong> 위주입니다(공격 {a} / 방어 {d} / HP {s}). 체육관 방어나 장기전에 적합합니다.",
    role_sta="{name}의 능력치는 <strong>HP</strong> 위주입니다(공격 {a} / 방어 {d} / HP {s}). 내구력이 높아 오래 버틸 수 있습니다.",
    rec="추천 기술", basis="({league} 기준)", buddy="파트너 거리", km="{km} km", nodata="데이터 부족",
    lg_h="{name} PvP 리그 순위",
    lg_note="PvP에서는 <strong>{league}</strong>에서 가장 좋은 성적을 냅니다({total}마리 중 {rank}위, 점수 {score}){extra}.",
    lg_extra=" — {master}는 CP 제한 없음", lg_none="{name}의 PvP 순위 데이터가 부족합니다.",
    lg_row="<b>{rank}</b> / {total} · {score}점",
    rel_h="관련 포켓몬", prev="← 이전", next="다음 →", same="같은 타입의 인기 포켓몬", fam_h="다른 모습·진화",
    cta="전체 포켓몬 보기 →", fab="포켓몬 검색",
    foot_tag="100% 개체값 CP, PvP 순위, 교환 목록 생성기",
    about="사이트 소개", privacy="개인정보처리방침", disclaimer="면책 조항", trade="교환 목록 생성기",
    hub_title="포켓몬 GO 100% 개체값 CP 목록｜레이드·필드리서치·알｜포켓몬 GO 툴박스",
    hub_desc=("포켓몬 GO 인기 포켓몬 {n}마리의 100% 개체값 CP: 필드리서치 Lv15, 레이드·알 Lv20, 날씨 부스트 Lv25. "
              "포켓몬별 개체값 계산기와 레벨별 CP 표도 제공합니다."),
    hub_h1="포켓몬 GO 100% 개체값 CP 목록",
    hub_intro=("<p>100% 개체를 알아보는 핵심은 CP입니다. <strong>필드리서치</strong> 보상은 Lv15, <strong>레이드와 알</strong>은 Lv20, "
               "<strong>날씨 부스트 레이드</strong>는 Lv25로 얻기 때문에, 포켓몬마다 100% 개체를 뜻하는 CP가 하나로 정해집니다.</p>"
               "<p>포켓몬을 고르면 100% 개체값 CP, 개체값 계산기, 레벨별 CP 표를 볼 수 있습니다.</p>"),
    hub_q="이름 또는 도감 번호로 검색",
    hub_count="인기 포켓몬 {n}마리 · 이름 아래 숫자는 레이드·알(Lv20)에서의 100% 개체값 CP",
    tile="Lv20 {cp}", ad="광고",
)

STR["fr"] = dict(
    html_lang="fr", og_locale="fr_FR", sep=", ", type_sep="/", paren="{a} ({b})", lv="niv. ",
    site="Boîte à outils Pokémon GO", hub_name="PC à 100 % IV", crumb_aria="Fil d’Ariane",
    title="{name} PC à 100 % IV (hundo) – raids et études | Boîte à outils Pokémon GO",
    desc=("PC à 100 % IV de {name} (#{dex}, {types}) : études de terrain niv. 15 {cp15}, raids et Œufs niv. 20 {cp20}, "
          "météo boostée niv. 25 {cp25}. Avec un calculateur d’IV, le tableau des PC niv. 1–50, les faiblesses et le classement PvP."),
    og_title="{name} PC à 100 % IV (hundo) – PC niv. 1–50",
    h1="{name} : PC à 100 % IV",
    t15="🔬 Études de terrain", t20="⚔️ Raids et Œufs", t25="☀️ Météo boostée",
    hundo_note=("Ces valeurs sont les PC à <strong>100 % IV (15/15/15)</strong>. Si un Pokémon obtenu par une étude de terrain "
                "(niv. 15), un raid ou un Œuf (niv. 20), ou un raid avec bonus météo (niv. 25) affiche exactement ces PC, c’est "
                "presque à coup sûr un hundo. En cas de doute, vérifiez avec le calculateur ci-dessous."),
    pill_max="PC max", stats_pill="Att. <b>{a}</b> · Déf. <b>{d}</b> · Endu. <b>{s}</b>",
    lead=("{name} (#{dex}) est un Pokémon de type <strong>{types}</strong> avec des statistiques de base de <strong>{a}</strong> "
          "en Attaque, {d} en Défense et {s} en Endurance. À 100 % IV, ses PC max sont de {cp40} au niveau 40 et de {cp50} au niveau 50."),
    rev_h="Calculateur d’IV de {name}",
    rev_sub="Saisissez les PC affichés à la capture (et les PV si vous les avez) pour voir toutes les combinaisons de niveau et d’IV possibles.",
    f_cp="PC", f_hp="PV", f_lv="Niveau", lv_any="Tous", lv15="Niv. 15 études de terrain", lv20="Niv. 20 raids et Œufs",
    lv25="Niv. 25 météo boostée", btn="Calculer", ph_hp="Facultatif", ph_cp="ex. : {cp20}",
    rv=dict(sum1="PC {cp}{hp} : une seule combinaison, IV <strong>{hi} %</strong>. ",
            need="Saisissez des PC (10 ou plus).",
            none="Aucune combinaison ne correspond. Vérifiez les PC (le bonus météo et les améliorations changent le niveau).",
            sum="PC {cp}{hp} : {n} combinaisons possibles, IV d’environ <strong>{lo} %–{hi} %</strong>. ", hpPart=", PV {hp}",
            narrow="Ajoutez les PV pour affiner.", lv="niv. ", thLv="Niveau", thIv="Att. / Déf. / Endu.", thHp="PV",
            all="Tout afficher ({n})"),
    ivt_h="{name} : PC et PV avec de hauts IV",
    ivt_sub=("Les 35 meilleures combinaisons d’IV (≥ 91,1 %) avec leurs PC et PV aux niveaux 15, 20, 25 et 40. "
             "Att. / Déf. / Endu. sont les IV (0–15)."),
    ivt_iv="IV Att./Déf./Endu.", a="Att", d="Déf", s="End",
    cpt_h="{name} : PC par niveau (niv. 1–50)",
    cpt_sub="<strong>100 % IV</strong> (15/15/15) donne les PC les plus hauts à chaque niveau, <strong>0 % IV</strong> (0/0/0) les plus bas.",
    cpt_cap="PC de {name} par niveau (100 % IV / 0 % IV)", th_lv="Niveau", th_max="100 % IV", th_min="0 % IV", th_note="Remarque",
    key15="🔬 Études de terrain", key20="⚔️ Raids (sans bonus météo) · 🥚 Œufs", key25="☀️ Raids (bonus météo)",
    bb="⭐ Bonus Meilleur Copain",
    cpt_foot=("Le niveau {bb} n’est accessible qu’avec le bonus Meilleur Copain ; les améliorations normales s’arrêtent au niveau {max}. "
              "Données : GAME_MASTER de Pokémon GO."),
    mu_h="{name} : faiblesses et résistances", weak="Faiblesses", resist="Résistances",
    mu_note="{name} est faible contre {wlist}{dbl} et résiste à {rlist}. Les attaques de type <strong>{prim}</strong> lui infligent le plus de dégâts.",
    mu_dbl=" (double faiblesse : {dbls})",
    mu_w=" Avec la météo <strong>{w}</strong>, ses attaques sont boostées et les captures bénéficient du bonus météo (niveau et PC plus élevés).",
    mu_none="Données de type insuffisantes.",
    role_h="{name} : rôle et meilleures attaques",
    role_atk_hi=("Les statistiques de {name} reposent sur une <strong>Attaque très élevée</strong> (Attaque {a} / Défense {d} / Endurance {s}) : "
                 "c’est un excellent attaquant en raid."),
    role_atk=("Les statistiques de {name} sont orientées <strong>Attaque</strong> (Attaque {a} / Défense {d} / Endurance {s}) : "
              "il convient bien comme attaquant en raid."),
    role_def=("Les statistiques de {name} sont orientées <strong>Défense</strong> (Attaque {a} / Défense {d} / Endurance {s}) : "
              "il convient à la défense des arènes et aux longs combats."),
    role_sta=("Les statistiques de {name} sont orientées <strong>Endurance</strong> (Attaque {a} / Défense {d} / Endurance {s}) : "
              "sa robustesse lui permet de rester longtemps au combat."),
    rec="Attaques conseillées", basis="(selon la {league})", buddy="Distance copain", km="{km} km", nodata="Données insuffisantes",
    lg_h="{name} : classement PvP par ligue",
    lg_note="En PvP, {name} est le plus performant en <strong>{league}</strong> (rang {rank} sur {total}, score {score}){extra}.",
    lg_extra=" — la {master} n’a pas de limite de PC", lg_none="Les données de classement PvP de {name} sont limitées.",
    lg_row="<b>{rank}</b> / {total} · {score} pts",
    rel_h="Pokémon liés", prev="← Précédent", next="Suivant →", same="Pokémon populaires du même type", fam_h="Autres formes et évolutions",
    cta="Voir tous les Pokémon →", fab="Chercher un Pokémon",
    foot_tag="PC à 100 % IV, classements PvP et générateur de liste d’échange",
    about="À propos", privacy="Confidentialité", disclaimer="Avertissement", trade="Générateur de liste d’échange",
    hub_title="Pokémon GO : PC à 100 % IV de chaque Pokémon – raids, études et Œufs | Boîte à outils Pokémon GO",
    hub_desc=("PC à 100 % IV (hundo) de {n} Pokémon populaires dans Pokémon GO : études de terrain niv. 15, raids et Œufs niv. 20, "
              "météo boostée niv. 25 — avec un calculateur d’IV et le tableau des PC pour chacun."),
    hub_h1="Pokémon GO : liste des PC à 100 % IV",
    hub_intro=("<p>Pour repérer un hundo, tout se joue sur les PC. Les Pokémon des <strong>études de terrain</strong> sont obtenus "
               "au niveau 15, ceux des <strong>raids et des Œufs</strong> au niveau 20 et ceux des <strong>raids avec bonus météo</strong> "
               "au niveau 25 : chaque Pokémon a donc une valeur de PC précise qui signifie 100 % IV.</p><p>Choisissez un Pokémon pour voir "
               "ses PC à 100 % IV, un calculateur d’IV et un tableau des PC à chaque niveau.</p>"),
    hub_q="Rechercher par nom ou numéro du Pokédex",
    hub_count="{n} Pokémon populaires · le nombre sous chaque nom correspond à ses PC à 100 % IV au niveau 20 (raids et Œufs)",
    tile="Niv. 20 : {cp}", ad="Publicité",
)

STR["de"] = dict(
    html_lang="de", og_locale="de_DE", sep=", ", type_sep="/", paren="{a} ({b})", lv="Lv",
    site="Pokémon GO Toolbox", hub_name="100 % IV WP", crumb_aria="Brotkrümelnavigation",
    title="{name} 100 % IV WP (Hundo) – Raid- & Forschungs-WP | Pokémon GO Toolbox",
    desc=("100 % IV WP von {name} (#{dex}, {types}): Feldforschung Lv15 {cp15}, Raids & Eier Lv20 {cp20}, Wetterbonus Lv25 {cp25}. "
          "Mit IV-Rechner, WP-Tabelle Lv1–50, Schwächen und PvP-Rankings."),
    og_title="{name} 100 % IV WP (Hundo) – WP-Tabelle Lv1–50",
    h1="{name} 100 % IV WP",
    t15="🔬 Feldforschung", t20="⚔️ Raids & Eier", t25="☀️ Wetterbonus",
    hundo_note=("Das sind die WP bei <strong>100 % IV (15/15/15)</strong>. Hat ein Pokémon aus der Feldforschung (Lv15), einem Raid "
                "oder Ei (Lv20) oder einem Raid mit Wetterbonus (Lv25) genau diese WP, ist es mit ziemlicher Sicherheit ein Hundo. "
                "Zur Kontrolle hilft der IV-Rechner weiter unten."),
    pill_max="Max. WP", stats_pill="Angr. <b>{a}</b> · Vert. <b>{d}</b> · Ausd. <b>{s}</b>",
    lead=("{name} (#{dex}) ist ein Pokémon vom Typ <strong>{types}</strong> mit den Basiswerten Angriff <strong>{a}</strong>, "
          "Verteidigung {d} und Ausdauer {s}. Mit 100 % IV erreicht es maximal {cp40} WP auf Level 40 und {cp50} WP auf Level 50."),
    rev_h="{name} IV-Rechner (aus WP)",
    rev_sub="Gib die WP beim Fang ein (KP sind optional) und sieh alle möglichen Kombinationen aus Level und IV.",
    f_cp="WP", f_hp="KP", f_lv="Level", lv_any="Alle", lv15="Lv15 Feldforschung", lv20="Lv20 Raids & Eier", lv25="Lv25 Wetterbonus",
    btn="Berechnen", ph_hp="Optional", ph_cp="z. B. {cp20}",
    rv=dict(sum1="WP {cp}{hp}: genau eine Kombination, IV <strong>{hi} %</strong>. ",
            need="Bitte WP eingeben (mindestens 10).",
            none="Keine passende Kombination. Prüfe die WP – Wetterbonus und Power-ups ändern das Level.",
            sum="WP {cp}{hp}: {n} mögliche Kombinationen, IV etwa <strong>{lo} %–{hi} %</strong>. ", hpPart=", KP {hp}",
            narrow="Mit den KP lässt sich das eingrenzen.", lv="Lv", thLv="Level", thIv="Angr. / Vert. / Ausd.", thHp="KP",
            all="Alle {n} anzeigen"),
    ivt_h="{name}: WP & KP mit hohen IV",
    ivt_sub=("Die 35 besten IV-Kombinationen (≥ 91,1 %) mit ihren WP und KP auf Level 15, 20, 25 und 40. "
             "Angr. / Vert. / Ausd. sind die IV (0–15)."),
    ivt_iv="IV Angr./Vert./Ausd.", a="Angr", d="Vert", s="Ausd",
    cpt_h="{name}: WP-Tabelle (Lv1–Lv50)",
    cpt_sub="<strong>100 % IV</strong> (15/15/15) ergeben die höchsten WP pro Level, <strong>0 % IV</strong> (0/0/0) die niedrigsten.",
    cpt_cap="WP von {name} pro Level (100 % IV / 0 % IV)", th_lv="Level", th_max="100 % IV", th_min="0 % IV", th_note="Hinweis",
    key15="🔬 Feldforschung", key20="⚔️ Raids (ohne Wetterbonus) · 🥚 Eier", key25="☀️ Raids (mit Wetterbonus)",
    bb="⭐ Bester-Kumpel-Boost",
    cpt_foot="Level {bb} ist nur mit dem Bester-Kumpel-Boost erreichbar; normale Power-ups enden bei Level {max}. Daten: Pokémon GO GAME_MASTER.",
    mu_h="{name}: Schwächen und Resistenzen", weak="Schwächen", resist="Resistenzen",
    mu_note="{name} ist schwach gegen {wlist}{dbl} und resistent gegen {rlist}. Attacken vom Typ <strong>{prim}</strong> richten den meisten Schaden an.",
    mu_dbl=" (doppelte Schwäche: {dbls})",
    mu_w=" Bei Wetter <strong>{w}</strong> werden seine Attacken verstärkt, und Fänge erhalten den Wetterbonus (höheres Level und mehr WP).",
    mu_none="Zu wenige Typdaten.",
    role_h="{name}: Rolle und beste Attacken",
    role_atk_hi=("Die Werte von {name} sind auf <strong>sehr hohen Angriff</strong> ausgelegt (Angriff {a} / Verteidigung {d} / Ausdauer {s}) "
                 "– ideal als Angreifer in Raids."),
    role_atk=("Die Werte von {name} sind auf <strong>Angriff</strong> ausgelegt (Angriff {a} / Verteidigung {d} / Ausdauer {s}) "
              "– gut als Angreifer in Raids."),
    role_def=("Die Werte von {name} sind auf <strong>Verteidigung</strong> ausgelegt (Angriff {a} / Verteidigung {d} / Ausdauer {s}) "
              "– passend für die Arenaverteidigung und lange Kämpfe."),
    role_sta=("Die Werte von {name} sind auf <strong>Ausdauer</strong> ausgelegt (Angriff {a} / Verteidigung {d} / Ausdauer {s}) "
              "– es hält lange im Kampf durch."),
    rec="Empfohlene Attacken", basis="(laut {league})", buddy="Kumpel-Distanz", km="{km} km", nodata="Zu wenige Daten",
    lg_h="{name}: PvP-Liga-Rankings",
    lg_note="Im PvP schneidet {name} in der <strong>{league}</strong> am besten ab (Platz {rank} von {total}, Wertung {score}){extra}.",
    lg_extra=" – die {master} hat kein WP-Limit", lg_none="Für {name} gibt es nur wenige PvP-Ranking-Daten.",
    lg_row="<b>{rank}</b> / {total} · {score} Pkt.",
    rel_h="Verwandte Pokémon", prev="← Vorheriges", next="Nächstes →", same="Beliebte Pokémon desselben Typs", fam_h="Andere Formen & Entwicklungen",
    cta="Alle Pokémon ansehen →", fab="Pokémon suchen",
    foot_tag="100 % IV WP, PvP-Rankings und Tauschlisten-Generator",
    about="Über die Seite", privacy="Datenschutz", disclaimer="Haftungsausschluss", trade="Tauschlisten-Generator",
    hub_title="Pokémon GO 100 % IV WP-Liste – Hundo-WP für Raids, Forschung & Eier | Pokémon GO Toolbox",
    hub_desc=("100 % IV WP (Hundo) für {n} beliebte Pokémon in Pokémon GO: Feldforschung Lv15, Raids & Eier Lv20 und Wetterbonus Lv25 "
              "– jeweils mit IV-Rechner und vollständiger WP-Tabelle."),
    hub_h1="Pokémon GO 100 % IV WP-Liste",
    hub_intro=("<p>Einen Hundo erkennst du an den WP. Pokémon aus der <strong>Feldforschung</strong> haben Level 15, aus "
               "<strong>Raids und Eiern</strong> Level 20 und aus <strong>Raids mit Wetterbonus</strong> Level 25 – deshalb gibt es "
               "für jedes Pokémon genau einen WP-Wert, der 100 % IV bedeutet.</p><p>Wähle ein Pokémon, um seine Hundo-WP, einen "
               "IV-Rechner und eine WP-Tabelle für jedes Level zu sehen.</p>"),
    hub_q="Nach Name oder Pokédex-Nummer suchen",
    hub_count="{n} beliebte Pokémon · die Zahl unter dem Namen sind die 100 % IV WP auf Level 20 (Raids & Eier)",
    tile="Lv20 {cp} WP", ad="Anzeige",
)

STR["es"] = dict(
    html_lang="es", og_locale="es_ES", sep=", ", type_sep="/", paren="{a} ({b})", lv="Nv. ",
    site="Herramientas Pokémon GO", hub_name="PC con 100 % IV", crumb_aria="Ruta de navegación",
    title="{name} PC con 100 % IV (hundo) – incursiones e investigación | Herramientas Pokémon GO",
    desc=("PC con 100 % IV de {name} (#{dex}, {types}): investigación de campo Nv. 15 {cp15}, incursiones y Huevos Nv. 20 {cp20}, "
          "clima potenciado Nv. 25 {cp25}. Con calculadora de IV, tabla de PC Nv. 1–50, debilidades y rankings PvP."),
    og_title="{name} PC con 100 % IV (hundo) – tabla de PC Nv. 1–50",
    h1="{name}: PC con 100 % IV",
    t15="🔬 Investigación de campo", t20="⚔️ Incursiones y Huevos", t25="☀️ Clima potenciado",
    hundo_note=("Estos son los PC con <strong>100 % IV (15/15/15)</strong>. Si un Pokémon de una investigación de campo (Nv. 15), "
                "una incursión o un Huevo (Nv. 20) o una incursión con clima potenciado (Nv. 25) muestra exactamente estos PC, es "
                "casi seguro un hundo. Si tienes dudas, compruébalo con la calculadora de abajo."),
    pill_max="PC máx.", stats_pill="Ata. <b>{a}</b> · Def. <b>{d}</b> · Res. <b>{s}</b>",
    lead=("{name} (#{dex}) es un Pokémon de tipo <strong>{types}</strong> con estadísticas base de <strong>{a}</strong> de Ataque, "
          "{d} de Defensa y {s} de Resistencia. Con 100 % IV alcanza {cp40} PC en el nivel 40 y {cp50} PC en el nivel 50."),
    rev_h="Calculadora de IV de {name}",
    rev_sub="Escribe los PC que viste al capturarlo (y los PS si los tienes) para ver todas las combinaciones posibles de nivel e IV.",
    f_cp="PC", f_hp="PS", f_lv="Nivel", lv_any="Cualquiera", lv15="Nv. 15 investigación de campo", lv20="Nv. 20 incursiones y Huevos",
    lv25="Nv. 25 clima potenciado", btn="Calcular", ph_hp="Opcional", ph_cp="p. ej. {cp20}",
    rv=dict(sum1="PC {cp}{hp}: una sola combinación, IV <strong>{hi} %</strong>. ",
            need="Escribe los PC (10 o más).",
            none="No hay ninguna combinación. Revisa los PC (el clima potenciado y los aumentos de nivel cambian el nivel).",
            sum="PC {cp}{hp}: {n} combinaciones posibles, IV de aprox. <strong>{lo} %–{hi} %</strong>. ", hpPart=", PS {hp}",
            narrow="Añade los PS para afinar.", lv="Nv. ", thLv="Nivel", thIv="Ata. / Def. / Res.", thHp="PS",
            all="Mostrar las {n}"),
    ivt_h="{name}: PC y PS con IV altos",
    ivt_sub=("Las 35 mejores combinaciones de IV (≥ 91,1 %) con sus PC y PS en los niveles 15, 20, 25 y 40. "
             "Ata. / Def. / Res. son los IV (0–15)."),
    ivt_iv="IV Ata./Def./Res.", a="Ata", d="Def", s="Res",
    cpt_h="{name}: tabla de PC por nivel (Nv. 1–50)",
    cpt_sub="<strong>100 % IV</strong> (15/15/15) da los PC más altos de cada nivel y <strong>0 % IV</strong> (0/0/0) los más bajos.",
    cpt_cap="PC de {name} por nivel (100 % IV / 0 % IV)", th_lv="Nivel", th_max="100 % IV", th_min="0 % IV", th_note="Notas",
    key15="🔬 Investigación de campo", key20="⚔️ Incursiones (sin clima potenciado) · 🥚 Huevos", key25="☀️ Incursiones (clima potenciado)",
    bb="⭐ Bonificación de Mejor compañero",
    cpt_foot=("El nivel {bb} solo se alcanza con la bonificación de Mejor compañero; los aumentos normales llegan hasta el nivel {max}. "
              "Datos: GAME_MASTER de Pokémon GO."),
    mu_h="{name}: debilidades y resistencias", weak="Debilidades", resist="Resistencias",
    mu_note="{name} es débil contra {wlist}{dbl} y resiste {rlist}. Los ataques de tipo <strong>{prim}</strong> le hacen más daño.",
    mu_dbl=" (doble debilidad: {dbls})",
    mu_w=" Con clima <strong>{w}</strong>, sus ataques se potencian y las capturas reciben la bonificación de clima (más nivel y PC).",
    mu_none="Datos de tipo insuficientes.",
    role_h="{name}: rol y mejores ataques",
    role_atk_hi=("Las estadísticas de {name} destacan por un <strong>Ataque muy alto</strong> (Ataque {a} / Defensa {d} / Resistencia {s}): "
                 "rinde mejor como atacante en incursiones."),
    role_atk=("Las estadísticas de {name} se inclinan al <strong>Ataque</strong> (Ataque {a} / Defensa {d} / Resistencia {s}): "
              "funciona bien como atacante en incursiones."),
    role_def=("Las estadísticas de {name} se inclinan a la <strong>Defensa</strong> (Ataque {a} / Defensa {d} / Resistencia {s}): "
              "es útil para defender gimnasios y en combates largos."),
    role_sta=("Las estadísticas de {name} se inclinan a la <strong>Resistencia</strong> (Ataque {a} / Defensa {d} / Resistencia {s}): "
              "aguanta mucho tiempo en combate."),
    rec="Ataques recomendados", basis="(según la {league})", buddy="Distancia de compañero", km="{km} km", nodata="Datos insuficientes",
    lg_h="{name}: rankings de ligas PvP",
    lg_note="En PvP, {name} rinde mejor en la <strong>{league}</strong> (puesto {rank} de {total}, puntuación {score}){extra}.",
    lg_extra=" — la {master} no tiene límite de PC", lg_none="Hay pocos datos de ranking PvP de {name}.",
    lg_row="<b>{rank}</b> / {total} · {score} pts",
    rel_h="Pokémon relacionados", prev="← Anterior", next="Siguiente →", same="Pokémon populares del mismo tipo", fam_h="Otras formas y evoluciones",
    cta="Ver todos los Pokémon →", fab="Buscar Pokémon",
    foot_tag="PC con 100 % IV, rankings PvP y generador de listas de intercambio",
    about="Acerca de", privacy="Privacidad", disclaimer="Aviso legal", trade="Generador de listas de intercambio",
    hub_title="Pokémon GO: PC con 100 % IV de cada Pokémon – incursiones, investigación y Huevos | Herramientas Pokémon GO",
    hub_desc=("PC con 100 % IV (hundo) de {n} Pokémon populares de Pokémon GO: investigación de campo Nv. 15, incursiones y Huevos Nv. 20 "
              "y clima potenciado Nv. 25, con calculadora de IV y tabla de PC para cada uno."),
    hub_h1="Pokémon GO: lista de PC con 100 % IV",
    hub_intro=("<p>Para reconocer un hundo, todo depende de los PC. Los Pokémon de <strong>investigación de campo</strong> se obtienen "
               "al nivel 15, los de <strong>incursiones y Huevos</strong> al nivel 20 y los de <strong>incursiones con clima potenciado</strong> "
               "al nivel 25, así que cada Pokémon tiene un valor de PC exacto que significa 100 % IV.</p><p>Elige un Pokémon para ver "
               "sus PC con 100 % IV, una calculadora de IV y una tabla de PC de todos los niveles.</p>"),
    hub_q="Buscar por nombre o número de la Pokédex",
    hub_count="{n} Pokémon populares · el número bajo cada nombre son sus PC con 100 % IV al nivel 20 (incursiones y Huevos)",
    tile="Nv. 20: {cp}", ad="Publicidad",
)
