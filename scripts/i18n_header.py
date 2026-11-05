# -*- coding: utf-8 -*-
"""外語頁（/<lang>/…）與中文 /cp/<slug>/ 共用的網站表頭：品牌、三個工具、語言切換。樣式在 css/site-i18n.css。"""
from html import escape as _e
from cp_i18n_strings import STR
from i18n_home_strings import HOME

LANG_NAMES = {"zh": "繁體中文", "en": "English", "ja": "日本語", "ko": "한국어", "fr": "Français", "de": "Deutsch", "es": "Español"}
LANG_ORDER = ["zh", "en", "ja", "ko", "fr", "de", "es"]
# 中文頁用（中文沒有 /zh/ 首頁，CP 查詢在首頁的 ?tab=cp-checker-app，所以連結另外處理）
ZH_SITE, ZH_NAV = "Pokémon Go 工具箱", ("交易清單", "IV100 CP", "PvP 排名")


def esc(s):
    return _e(str(s), quote=True)


def site_header(lang, home_href, active, alts):
    """home_href：從目前頁面到 /<lang>/ 的相對路徑；active：t（交易清單）／c（CP）／p（PvP）／空字串；
    alts：{語言: 這一頁該語言版本的相對網址}（zh 指中文版）。語言選單用真正的 <a>，爬蟲也看得到。"""
    if lang == "zh":   # home_href 指網站根目錄
        (t, c, p), site = ZH_NAV, ZH_SITE
        urls = (f"{home_href}trade-list/", f"{home_href}?tab=cp-checker-app", f"{home_href}pvp-ranker/")
    else:
        (t, c, p), site = HOME[lang]["nav"], STR[lang]["site"]
        urls = (f"{home_href}../trade-list/?lang={lang}", f"{home_href}cp/", f"{home_href}pvp-ranker/")
    on = lambda k: " on" if active == k else ""
    nav = (f'<a class="t{on("t")}" href="{urls[0]}">📋 {esc(t)}</a>'
           f'<a class="c{on("c")}" href="{urls[1]}">💯 {esc(c)}</a>'
           f'<a class="p{on("p")}" href="{urls[2]}">⚔️ {esc(p)}</a>')
    items = []
    for l in LANG_ORDER:
        if l not in alts:
            continue
        code = "zh-Hant" if l == "zh" else l
        cls = ' class="on"' if l == lang else ""
        items.append(f'<a href="{alts[l]}" hreflang="{code}" lang="{code}"{cls}>{LANG_NAMES[l]}</a>')
    menu = "".join(items)
    return (f'<header class="xh"><div class="xh-in">'
            f'<a class="xh-brand" href="{home_href}"><span class="xh-logo">🧰</span>{esc(site)}</a>'
            f'<nav class="xh-nav" aria-label="{esc(site)}">{nav}</nav>'
            f'<details class="xlang"><summary>🌐 {LANG_NAMES[lang]}</summary><div class="xlang-menu">{menu}</div></details>'
            f'</div></header>')
