//【修改 1】: 從 firebase SDK 導入更多驗證相關的模組
import { initializeApp } from "https://www.gstatic.com/firebasejs/9.15.0/firebase-app.js";
import { getDatabase, ref, set, get } from "https://www.gstatic.com/firebasejs/9.15.0/firebase-database.js";
import { 
    getAuth, 
    GoogleAuthProvider, 
    signInWithPopup, 
    signOut, 
    onAuthStateChanged 
} from "https://www.gstatic.com/firebasejs/9.15.0/firebase-auth.js";

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
    };

    //【新增 5】: 登出函式
    const handleLogout = () => {
        signOut(auth)
    };
    window.addEventListener('click', (event) => {
        const userMenu = document.querySelector('.user-menu-dropdown');
        // 如果選單存在，且點擊的目標不是在 user-info 區塊內
        if (userMenu && !userInfoDisplay.contains(event.target)) {
            userMenu.classList.remove('show');
        }
    });
    //【新增 6】: 監聽使用者登入狀態的變化 (最關鍵的部分)
    onAuthStateChanged(auth, (user) => {
        currentUser = user; 
        if (user) {
            // --- 使用者已登入 ---
            authButton.style.display = 'none'; // 隱藏原本的登入按鈕
            userInfoDisplay.style.display = 'block'; // 顯示使用者資訊區塊

            // 動態產生頭像和隱藏的下拉選單 HTML
            userInfoDisplay.innerHTML = `
                <img src="${user.photoURL}" alt="使用者頭像" class="user-avatar" id="user-avatar-trigger">
                <div class="user-menu-dropdown">
                    <a href="#" id="menu-logout-btn">登出</a>
                </div>
            `;

            // 為頭像圖片加上點擊事件，用來開關選單
            document.getElementById('user-avatar-trigger').addEventListener('click', (event) => {
                event.stopPropagation(); // 防止觸發 window 的點擊事件而立即關閉
                document.querySelector('.user-menu-dropdown').classList.toggle('show');
            });

            // 為選單中的「登出」按鈕加上點擊事件
            document.getElementById('menu-logout-btn').addEventListener('click', (event) => {
                event.preventDefault(); // 防止頁面跳轉
                handleLogout(); // 呼叫登出函式
            });

            loadUserData(user.uid);

        } else {
            // --- 使用者已登出或未登入 ---
            authButton.style.display = 'inline-block'; // 顯示登入按鈕
            userInfoDisplay.style.display = 'none';    // 隱藏使用者資訊區塊
            userInfoDisplay.innerHTML = '';            // 清空內容
            authButton.onclick = handleLogin; // 將登入函式賦予給按鈕的點擊事件
            clearUserData();
        }
    });
    
    //【新增 7】: 讀取和清除資料的中央控制器
    async function loadUserData(userId) {
        // console.log(`正在為使用者 ${userId} 讀取資料...`);
        const pinnedResearchesPath = `users/${userId}/specialResearch/pinned`;
        const db = getDatabase();

        try {
            const snapshot = await get(ref(db, pinnedResearchesPath));
            if (snapshot.exists()) {
                const pinnedTitles = snapshot.val();
                // console.log('✅ 成功從 Firebase 讀取到資料，將其存入暫存區:', pinnedTitles);
                
                // 【修改】: 不再直接呼叫函式，而是將資料存到全域的暫存區
                window.pendingPinnedTitles = pinnedTitles;
                if (typeof window.applyPinnedStateToUI === 'function') {
                    window.applyPinnedStateToUI(pinnedTitles);
                }


            } else {
                // console.log('ℹ️ 在 Firebase 中找不到該使用者的釘選資料。');
                // 【修改】: 同樣設定暫存區，確保是乾淨的狀態
                window.pendingPinnedTitles = [];
                if (typeof window.applyPinnedStateToUI === 'function') {
                    window.applyPinnedStateToUI([]);
                }   
            }
        } catch (error) {
        }
    }

    function clearUserData() {
        // console.log("使用者已登出，清除本地狀態和暫存區...");
        // 【修改】: 清除暫存區
        window.pendingPinnedTitles = [];
        // 呼叫函式來更新畫面為登出狀態
        if (typeof window.applyPinnedStateToUI === 'function') {
            window.applyPinnedStateToUI([]);
        }
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
        
        // 【偵錯日誌 3】: 檢查將要寫入的資料
        // console.log(`🔷 準備寫入 Firebase... 路徑: ${fullPath}`, '資料:', data);

        try {
            await set(ref(db, fullPath), data);
            // 【偵錯日誌 4】: 確認寫入成功
            // console.log(`✅ 資料成功儲存至 Firebase!`);
        } catch (error) {
            // 【偵錯日誌 5】: 捕捉寫入時的錯誤
        }
    } 
}