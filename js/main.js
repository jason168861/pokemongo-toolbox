//【修改 1】: 從 firebase SDK 導入更多驗證相關的模組
import { initializeApp } from "https://www.gstatic.com/firebasejs/9.15.0/firebase-app.js";
import { getDatabase, ref, runTransaction, set, get } from "https://www.gstatic.com/firebasejs/9.15.0/firebase-database.js";
import { 
    getAuth, 
    GoogleAuthProvider, 
    signInWithPopup, 
    signOut, 
    onAuthStateChanged 
} from "https://www.gstatic.com/firebasejs/9.15.0/firebase-auth.js";

//【新增】: 為了方便跨檔案操作，匯出一些函式
import { loadPinnedResearchesForUser } from './special-research.js';

// 導入所有 App 的初始化函式
import { initializeCpChecker } from './cp-checker.js';
import { initializeIdSelector } from './id-selector.js';
import { initializeResearchApp } from './research.js';
import { initializeEggsApp } from './eggs.js';
import { initializeLevelUpApp } from './level-up.js';
import { initializeSearchFiltersApp } from './search-filters.js';
import { initializeSpecialResearchApp } from './special-research.js'; // <-- 【新增】
import { initializeInfoHubApp } from './info-hub.js'; // <-- 【新增】

document.addEventListener('DOMContentLoaded', () => {
        const app = initializeApp(window.firebaseConfig); // 假設您的 config 在 window 上
    const auth = getAuth(app);
    const db = getDatabase(app);
    const provider = new GoogleAuthProvider();

    //【新增 3】: 獲取 DOM 元素
    const authButton = document.getElementById('auth-button');
    const userInfoDisplay = document.getElementById('user-info');
    let currentUser = null; // 用來儲存當前登入的使用者資訊

    //【新增 4】: 登入函式
    const handleLogin = () => {
        signInWithPopup(auth, provider)
            .then((result) => {
                console.log("登入成功:", result.user.displayName);
                // 登入成功後 onAuthStateChanged 會自動處理後續
            }).catch((error) => {
                console.error("登入失敗:", error);
                alert(`登入時發生錯誤: ${error.message}`);
            });
    };

    //【新增 5】: 登出函式
    const handleLogout = () => {
        signOut(auth).then(() => {
            console.log("已登出");
            // 登出成功後 onAuthStateChanged 會自動處理後續
        }).catch((error) => {
            console.error("登出失敗:", error);
        });
    };

    //【新增 6】: 監聽使用者登入狀態的變化 (最關鍵的部分)
    onAuthStateChanged(auth, (user) => {
        currentUser = user; // 更新當前使用者狀態
        if (user) {
            // --- 使用者已登入 ---
            userInfoDisplay.textContent = `你好, ${user.displayName}`;
            userInfoDisplay.style.display = 'inline';
            authButton.textContent = '登出';
            authButton.onclick = handleLogout;

            // 觸發讀取使用者資料的函式
            loadUserData(user.uid);

        } else {
            // --- 使用者已登出或未登入 ---
            userInfoDisplay.style.display = 'none';
            authButton.textContent = '使用 Google 登入';
            authButton.onclick = handleLogin;
            
            // 觸發清除使用者資料的函式
            clearUserData();
        }
    });
    
    //【新增 7】: 讀取和清除資料的中央控制器
    async function loadUserData(userId) {
        console.log(`正在為使用者 ${userId} 讀取資料...`);
        // 讀取特殊調查的釘選資料
        const pinnedResearchesPath = `users/${userId}/specialResearch/pinned`;
        const snapshot = await get(ref(db, pinnedResearchesPath));
        if (snapshot.exists()) {
            const pinnedTitles = snapshot.val();
            // 呼叫 special-research.js 中的函式來更新畫面
            if (typeof loadPinnedResearchesForUser === 'function') {
                loadPinnedResearchesForUser(pinnedTitles);
            }
        }
        // 未來若有其他要記憶的功能，可以繼續加在這裡
        // 例如： loadPokemonSelections(userId);
    }

    function clearUserData() {
        console.log("使用者已登出，清除本地狀態...");
        // 清除特殊調查的釘選狀態
        if (typeof loadPinnedResearchesForUser === 'function') {
            loadPinnedResearchesForUser([]); // 傳入空陣列來重設
        }
        // 未來若有其他要記憶的功能，可以繼續加在這裡
    }
    
    // --- 全域控制與頁籤切換邏輯 ---
    document.getElementById('copyright-year').textContent = new Date().getFullYear();

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
    let infoHubAppInitialized = false; // <-- 【新增】

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
            } else if (targetAppId === 'info-hub-app' && !infoHubAppInitialized) { // <-- 【新增】
                initializeInfoHubApp();
                infoHubAppInitialized = true;
            }
        });
    });

    // 預設載入第一個 App
    // initializeCpChecker();
    // cpAppInitialized = true;
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
    window.addEventListener('touchstart', () => {
        // 只有當焦點在輸入框上時，才需要準備監聽後續的滑動
        if (document.activeElement && (document.activeElement.tagName === "INPUT" || document.activeElement.tagName === "TEXTAREA")) {
            
            // 監聽「一次」touchmove 事件。{ once: true } 能確保它觸發後就自動移除，效能更好。
            window.addEventListener('touchmove', function hideKeyboard() {
                document.activeElement.blur(); // 讓輸入框失焦，進而收合鍵盤
            }, { once: true });
        }
    });
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
    const loadingOverlay = document.getElementById('loading-overlay');
    const pokeballLoader = document.querySelector('.pokeball-loader');

    // 1. 【新增】頁面載入後，立即為寶貝球加上 .shaking class 來觸發晃動動畫
    if (pokeballLoader) {
        pokeballLoader.classList.add('shaking');
    }

    // 2. 【修改】延遲時間，必須等待晃動動畫 (2.5秒) 結束後才開始打開
    setTimeout(() => {
        // 觸發 "打開" 動畫
        loadingOverlay.classList.add('start-animation');

        // 3. 等待打開動畫和閃光效果快結束時，再讓整個遮罩層淡出
        setTimeout(() => {
            loadingOverlay.classList.add('hidden');
            
            // 4. 在淡出動畫結束後，將其從 DOM 中移除，避免影響後續操作
            setTimeout(() => {
                loadingOverlay.remove();
            }, 600); // 這個時間對應 #loading-overlay 的 transition 時間

        }, 800); // 這個時間要比寶貝球打開+閃光的動畫時間稍短

    }, 1200); // 這裡的 2600ms = 2.5秒晃動 + 0.1秒緩衝
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


export async function saveDataForCurrentUser(path, data) {
    const auth = getAuth();
    const db = getDatabase();
    if (auth.currentUser) {
        const userId = auth.currentUser.uid;
        const fullPath = `users/${userId}/${path}`;
        try {
            await set(ref(db, fullPath), data);
            console.log(`資料成功儲存至: ${fullPath}`);
        } catch (error) {
            console.error("儲存資料失敗:", error);
        }
    } else {
        console.log("使用者未登入，資料未儲存。");
    }
}