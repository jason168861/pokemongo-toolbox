// 導入所有 App 的初始化函式
import { initializeCpChecker } from './cp-checker.js';
import { initializeIdSelector } from './id-selector.js';
import { initializeResearchApp } from './research.js';
import { initializeEggsApp } from './eggs.js';
import { initializeLevelUpApp } from './level-up.js';
import { initializeSearchFiltersApp } from './search-filters.js';
import { initializeSpecialResearchApp } from './special-research.js'; // <-- 【新增】

document.addEventListener('DOMContentLoaded', () => {
    // --- 全域控制與頁籤切換邏輯 ---
    const tabButtons = document.querySelectorAll('.tab-button');
    const appContents = document.querySelectorAll('.app-content');
    
    // 狀態旗標，用來判斷 App 是否已初始化
    let cpAppInitialized = false;
    let idAppInitialized = false;
    let researchAppInitialized = false;
    let eggsAppInitialized = false;
    let levelUpAppInitialized = false; 
    let searchFiltersAppInitialized = false;
    let specialResearchAppInitialized = false;

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            tabButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');

            const targetAppId = button.dataset.target;

            appContents.forEach(content => content.classList.remove('active'));
            const targetApp = document.getElementById(targetAppId);
            targetApp.classList.add('active');
            
            // --- 延遲載入邏輯：只在第一次點擊時初始化對應的 App ---
            if (targetAppId === 'cp-checker-app' && !cpAppInitialized) {
                initializeCpChecker();
                cpAppInitialized = true;
            } else if (targetAppId === 'id-selector-app' && !idAppInitialized) {
                initializeIdSelector();
                idAppInitialized = true;
            } else if (targetAppId === 'research-app' && !researchAppInitialized) {
                initializeResearchApp();
                researchAppInitialized = true;
            } else if (targetAppId === 'eggs-app' && !eggsAppInitialized) {
                initializeEggsApp();
                eggsAppInitialized = true;
            } else if (targetAppId === 'level-up-app' && !levelUpAppInitialized) {
                initializeLevelUpApp();
                levelUpAppInitialized = true;
            } else if (targetAppId === 'search-filters-app' && !searchFiltersAppInitialized) {
                initializeSearchFiltersApp();
                searchFiltersAppInitialized = true;
            } else if (targetAppId === 'special-research-app' && !specialResearchAppInitialized) { // <-- 【新增】
                initializeSpecialResearchApp();
                specialResearchAppInitialized = true;
            }
        });
    });

    // 預設載入第一個 App
    initializeCpChecker();
    cpAppInitialized = true;
   const nav = document.querySelector('.app-nav');
    let lastScrollTop = 0;

    // 1. 定義一個函式來設定 CSS 變數
    function setNavHeight() {
        const navHeight = nav.offsetHeight; // 取得導覽列的實際高度
        document.documentElement.style.setProperty('--nav-height', `${navHeight}px`);
    }

    // 2. 定義一個函式來處理滾動事件
    function handleScroll() {
        let scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        if (document.activeElement && document.activeElement.tagName === 'INPUT') {
            document.activeElement.blur();
        }
        if (scrollTop > lastScrollTop && scrollTop > nav.offsetHeight) {
            // 向下滑動
            nav.classList.add('app-nav--hidden');
            document.body.classList.add('nav-is-hidden'); // 【新增】告訴 body 導覽列已隱藏
        } else {
            // 向上滑動
            nav.classList.remove('app-nav--hidden');
            document.body.classList.remove('nav-is-hidden'); // 【新增】告訴 body 導覽列已顯示
        }
        lastScrollTop = scrollTop <= 0 ? 0 : scrollTop;
    }
    // 3. 頁面載入時，立即執行一次高度計算
    setNavHeight();

    // 4. 為視窗加上事件監聽器
    window.addEventListener('resize', setNavHeight); // 當視窗大小改變時，重新計算高度
    window.addEventListener('scroll', handleScroll); // 當滾動時，處理導覽列的顯示/隱藏
    const hamburgerButton = document.querySelector('.hamburger-button');
    const navLinks = document.querySelector('.nav-links');
    const tabButtonsInMenu = navLinks.querySelectorAll('.tab-button');

    // 當漢堡按鈕被點擊時
    hamburgerButton.addEventListener('click', () => {
        // 切換選單的展開/收合狀態
        navLinks.classList.toggle('is-open');
        // 切換漢堡按鈕自身的 "X" 狀態
        hamburgerButton.classList.toggle('is-active');
        // 更新 aria 屬性，有助於無障礙閱讀
        const isExpanded = navLinks.classList.contains('is-open');
        hamburgerButton.setAttribute('aria-expanded', isExpanded);
    });

    // 當選單中的任何一個頁籤按鈕被點擊時，自動收合選單
    tabButtonsInMenu.forEach(button => {
        button.addEventListener('click', () => {
            if (navLinks.classList.contains('is-open')) {
                navLinks.classList.remove('is-open');
                hamburgerButton.classList.remove('is-active');
                hamburgerButton.setAttribute('aria-expanded', 'false');
            }
        });
    });
});