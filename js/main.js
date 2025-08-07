// 導入所有 App 的初始化函式
import { initializeApp } from "https://www.gstatic.com/firebasejs/9.15.0/firebase-app.js";
import { 
    getAuth, 
    GoogleAuthProvider, 
    signInWithPopup, 
    signOut, 
    onAuthStateChanged 
} from "https://www.gstatic.com/firebasejs/9.15.0/firebase-auth.js";
import { 
    getDatabase, 
    ref, 
    set, // 用於寫入資料
    get   // 用於讀取資料
} from "https://www.gstatic.com/firebasejs/9.15.0/firebase-database.js";

import { initializeCpChecker } from './cp-checker.js';
import { initializeIdSelector } from './id-selector.js';
import { initializeResearchApp } from './research.js';
import { initializeEggsApp } from './eggs.js';
import { initializeLevelUpApp } from './level-up.js';
import { initializeSearchFiltersApp } from './search-filters.js';
import { initializeSpecialResearchApp,applyUserPreferences } from './special-research.js'; // <-- 【新增】
import { initializeInfoHubApp } from './info-hub.js'; // <-- 【新增】

document.addEventListener('DOMContentLoaded', () => {
        const app = initializeApp(firebaseConfig); // 這行您應該已經有了
    const auth = getAuth(app);
    const db = getDatabase(app);
    const provider = new GoogleAuthProvider();

    let currentUserId = null; // 用來存放當前登入者的 UID

    const loginBtn = document.getElementById('login-btn');
    const logoutBtn = document.getElementById('logout-btn');
    const authContainer = document.getElementById('auth-container');
    const userInfoDiv = document.getElementById('user-info');
    const userNameSpan = document.getElementById('user-name');
    const userPhotoImg = document.getElementById('user-photo');

    // 登入功能
    loginBtn.addEventListener('click', () => {
        signInWithPopup(auth, provider)
            .then((result) => {
                // 登入成功，onAuthStateChanged 會自動處理後續
                console.log("登入成功:", result.user);
            }).catch((error) => {
                console.error("登入失敗:", error);
                alert("Google 登入失敗，請檢查彈出視窗是否被阻擋，或稍後再試。");
            });
    });

    // 登出功能
    logoutBtn.addEventListener('click', () => {
        signOut(auth).then(() => {
            // 登出成功，onAuthStateChanged 會自動處理後續
            console.log("已登出");
        }).catch((error) => {
            console.error("登出失敗:", error);
        });
    });

    // 監聽使用者登入狀態的變化
    onAuthStateChanged(auth, (user) => {
        if (user) {
            // --- 使用者已登入 ---
            currentUserId = user.uid;
            
            // 更新 UI
            userNameSpan.textContent = user.displayName;
            userPhotoImg.src = user.photoURL;
            userInfoDiv.style.display = 'flex';
            loginBtn.style.display = 'none';

            // 從資料庫載入使用者資料
            loadUserData(currentUserId);

        } else {
            // --- 使用者已登出 ---
            currentUserId = null;

            // 更新 UI
            userInfoDiv.style.display = 'none';
            loginBtn.style.display = 'block';
            applyUserPreferences(null);
            // TODO: 清除或重設 App 狀態 (例如取消所有置頂)
            // 這個部分可以在未來優化，例如詢問使用者是否要清除本機狀態
        }
    });

    // 從 Firebase 讀取使用者資料
    function loadUserData(userId) {
        const userRef = ref(db, 'users/' + userId);
        get(userRef).then((snapshot) => {
            if (snapshot.exists()) {
                const userData = snapshot.val();
                console.log("成功從 Firebase 載入資料:", userData);
                
                // 【關鍵】通知 special-research 模組去應用這些資料
                // 我們需要一個方法來將資料傳遞給它
                // 我們假設 specialResearchApp 有一個 applyUserPreferences 的方法
                applyUserPreferences(userData);
                
            } else {
                console.log("此使用者尚無儲存資料。");
                applyUserPreferences(null);
            }
        }).catch((error) => {
            console.error("讀取資料失敗:", error);
        });
    }

    // 將 App 狀態儲存到 Firebase
    // 這個函式會被其他模組 (如 special-research.js) 呼叫
    window.saveAppState = function(dataToSave) {
        if (!currentUserId) {
            // 如果使用者沒登入，就不執行儲存
            return;
        }
        const userRef = ref(db, 'users/' + currentUserId);
        set(userRef, dataToSave)
            .then(() => {
                console.log("資料成功同步到 Firebase!");
            })
            .catch((error) => {
                console.error("資料同步失敗:", error);
            });
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


