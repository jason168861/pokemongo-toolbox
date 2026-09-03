/* 表頭導覽列的互動：漢堡選單、功能選單展開。
 *
 * 給獨立工具頁（/raids/、/eggs/ …）用。首頁的同一份邏輯在 main.js 裡，
 * 因為那邊還要順便接 SPA 切換；這裡只有導覽，不能直接載 main.js
 * （它會去找首頁才有的 app-content 節點）。兩邊改動要一起改。
 */
(function () {
    'use strict';

    const hamburgerButton = document.querySelector('.hamburger-button');
    const navLinks = document.querySelector('.nav-links');
    if (!hamburgerButton || !navLinks) return;

    /* ---- 手機版選單 ------------------------------------------------------
       高度不能寫死成 calc(100vh - 50px)：手機瀏覽器的 100vh 是「網址列收起來
       之後」的高度，網址列還在時算出來的選單比實際可視範圍高，最後幾項會被推
       到螢幕外面且捲不到。改成開啟當下量「選單頂端到視窗底部」的真實距離。 */
    const headerBar = document.querySelector('.site-header-main');
    function sizeMenu() {
        // 量表頭的下緣，不要量選單自己 —— 選單收合時帶著 translateY(-8px)，
        // 量到的位置會比實際展開後高 8px。
        const top = headerBar ? headerBar.getBoundingClientRect().bottom : 52;
        document.documentElement.style.setProperty(
            '--menu-max-h', Math.max(160, window.innerHeight - top - 8) + 'px');
    }

    function setMenu(open) {
        if (open) sizeMenu();            // 先量再開，避免開啟動畫期間高度跳動
        navLinks.classList.toggle('is-open', open);
        hamburgerButton.classList.toggle('is-active', open);
        hamburgerButton.setAttribute('aria-expanded', String(open));
        document.documentElement.classList.toggle('nav-open', open);
    }
    const closeMenu = () => { if (navLinks.classList.contains('is-open')) setMenu(false); };

    hamburgerButton.addEventListener('click', () => {
        setMenu(!navLinks.classList.contains('is-open'));
    });
    // 點選單以外的地方（含背景遮罩）就關掉 —— 手機上沒有這個會覺得選單「黏住」
    document.addEventListener('click', (e) => {
        if (!navLinks.classList.contains('is-open')) return;
        if (navLinks.contains(e.target) || hamburgerButton.contains(e.target)) return;
        closeMenu();
    });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeMenu(); });
    // 轉螢幕方向／網址列收合都會改變可視高度，重新量一次
    window.addEventListener('resize', () => {
        if (navLinks.classList.contains('is-open')) sizeMenu();
    });

    document.querySelectorAll('.nav-group .group-title').forEach(title => {
        title.addEventListener('click', () => {
            const group = title.closest('.nav-group');
            if (!group) return;
            group.classList.toggle('is-expanded');
            // 觸控裝置（平板）沒有 mouseleave：再點一次標題也能解除抑制、重新打開
            group.classList.remove('menu-suppressed');
        });
    });

    // 獨立頁的連結都是真的會換頁，選單收不收其實看不太出來，
    // 但按下去到新頁面載入完之間有空窗，先收起來比較不會覺得卡住
    navLinks.querySelectorAll('.tab-button').forEach(b =>
        b.addEventListener('click', closeMenu));
}());
