# -*- coding: utf-8 -*-
"""外語頁（/<lang>/…）共用的網站表頭：品牌、三個工具、語言切換。樣式在 css/site-i18n.css。"""
from html import escape as _e
from cp_i18n_strings import STR
from i18n_home_strings import HOME

LANG_NAMES = {"zh": "繁體中文", "en": "English", "ja": "日本語", "ko": "한국어", "fr": "Français", "de": "Deutsch", "es": "Español"}
LANG_ORDER = ["zh", "en", "ja", "ko", "fr", "de", "es"]


def esc(s):
    return _e(str(s), quote=True)


def site_header(lang, home_href, active, alts):
    """home_href：從目前頁面到 /<lang>/ 的相對路徑；active：t（交易清單）／c（CP）／p（PvP）／空字串；
    alts：{語言: 這一頁該語言版本的相對網址}（zh 指中文版）。語言選單用真正的 <a>，爬蟲也看得到。"""
    t, c, p = HOME[lang]["nav"]
    on = lambda k: " on" if active == k else ""
    nav = (f'<a class="t{on("t")}" href="{home_href}../trade-list/?lang={lang}">📋 {esc(t)}</a>'
           f'<a class="c{on("c")}" href="{home_href}cp/">💯 {esc(c)}</a>'
           f'<a class="p{on("p")}" href="{home_href}pvp-ranker/">⚔️ {esc(p)}</a>')
    items = []
    for l in LANG_ORDER:
        if l not in alts:
            continue
        code = "zh-Hant" if l == "zh" else l
        cls = ' class="on"' if l == lang else ""
        items.append(f'<a href="{alts[l]}" hreflang="{code}" lang="{code}"{cls}>{LANG_NAMES[l]}</a>')
    menu = "".join(items)
    return (f'<header class="xh"><div class="xh-in">'
            f'<a class="xh-brand" href="{home_href}"><span class="xh-logo">🧰</span>{esc(STR[lang]["site"])}</a>'
            f'<nav class="xh-nav" aria-label="{esc(STR[lang]["site"])}">{nav}</nav>'
            f'<details class="xlang"><summary>🌐 {LANG_NAMES[lang]}</summary><div class="xlang-menu">{menu}</div></details>'
            f'</div></header>')
