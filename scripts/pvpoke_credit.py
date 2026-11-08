"""PvPoke 排名資料的來源與授權標示（MIT License 要求附上版權與授權聲明）。

用到 PvPoke 排名的頁面都從這裡取同一段文字：PvP 聯盟／盃賽排名頁、/<lang>/pvp-ranker/、
/cp/<slug>/ 與 /<lang>/cp/<slug>/ 的「對戰聯盟表現」。手寫頁（pvp-ranker/、id-selector/、
首頁 CP 查詢的 js/cp-checker.js、about/）的文字要與這裡一致。
"""
PVPOKE_URL = "https://pvpoke.com/"
LICENSE_URL = "https://github.com/pvpoke/pvpoke/blob/master/LICENSE"
PVPOKE_TW_URL = "https://pvpoketw.com/"

_LABEL = {
    "zh": "PvP 排名資料", "en": "PvP ranking data", "ja": "PvPランキングデータ", "ko": "PvP 랭킹 데이터",
    "fr": "Données de classement PvP", "de": "PvP-Ranglistendaten", "es": "Datos de clasificación PvP",
}


def credit_html(lang="zh"):
    """回傳一段行內 HTML（不含外層 <p>）。"""
    a = lambda href, text: f'<a href="{href}" target="_blank" rel="noopener">{text}</a>'
    if lang == "zh":
        return (f'PvP 排名資料：{a(PVPOKE_URL, "PvPoke")} 對戰模擬（© PvPoke LLC，{a(LICENSE_URL, "MIT License")}），'
                f'中文名稱取自 {a(PVPOKE_TW_URL, "PvPoke 繁中版")}。')
    return f'{_LABEL.get(lang, _LABEL["en"])}: {a(PVPOKE_URL, "PvPoke")} (© PvPoke LLC, {a(LICENSE_URL, "MIT License")})'
