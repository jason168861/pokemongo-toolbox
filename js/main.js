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

// 【新增】將此函式移出 DOMContentLoaded，使其可被其他模組引用
export async function saveDataForCurrentUser(path, data) {
    const auth = getAuth();
    const db = getDatabase();
    if (auth.currentUser) {
        const userId = auth.currentUser.uid;
        const fullPath = `users/${userId}/${path}`;
        try {
            await set(ref(db, fullPath), data);
        } catch (error) {
            console.error(`無法儲存資料到 Firebase: ${error}`);
        }
    } 
}

// 導入所有 App 的初始化函式
import { initializeCpChecker } from './cp-checker.js';
import { initializeIdSelector } from './id-selector.js';
import { initializeResearchApp } from './research.js';
import { initializeEggsApp } from './eggs.js';
import { initializeRaidsApp } from './raids.js'; // <-- 新增此行
import { initializeLevelUpApp } from './level-up.js';
import { initializeSearchFiltersApp } from './search-filters.js';
import { initializeFilterBuilder } from './filter-builder.js';
import { initializeSpecialResearchApp } from './special-research.js'; // <-- 【新增】
import { initializeInfoHubApp } from './info-hub.js'; // <-- 【新增】
import { initializePvpRanker } from './pvp-ranker.js';

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
        const idSelectorPath = `users/${userId}/idSelector/selected`;
        try {
            const idSnapshot = await get(ref(db, idSelectorPath));
            if (idSnapshot.exists()) {
                const savedIds = idSnapshot.val();
                // 暫存讀取到的資料
                window.pendingSelectedIds = savedIds; 
                // 如果 id-selector 模組已初始化，直接呼叫其讀取函式
                if (typeof window.loadIdSelectorState === 'function') {
                    window.loadIdSelectorState(savedIds);
                }
            }
        } catch(error) {
            console.error("讀取寶可夢編號資料時發生錯誤:", error);
        }

        // --- 篩選指令產生器的組合 ---
        try {
            const fbSnapshot = await get(ref(db, `users/${userId}/filterBuilder/sets`));
            const fbData = fbSnapshot.exists() ? fbSnapshot.val() : null;
            if (typeof window.loadFilterBuilderState === 'function') {
                window.loadFilterBuilderState(fbData);   // 已初始化 → 直接套用（雲端沒資料時會把本機的推上去）
            } else {
                window.pendingFilterBuilder = fbData;    // 還沒開過該分頁 → 先暫存，初始化時再套用
            }
        } catch (error) {
            console.error("讀取篩選組合資料時發生錯誤:", error);
        }
    }

    function clearUserData() {
        // --- 清除特殊調查資料 (原有邏輯) ---
        window.pendingPinnedTitles = [];
        if (typeof window.applyPinnedStateToUI === 'function') {
            window.applyPinnedStateToUI([]);
        }

        // --- 【新增】清除編號篩選器資料 ---
        window.pendingSelectedIds = [];
        // 如果 id-selector 模組已初始化，直接呼叫其清除函式
        if (typeof window.clearIdSelectorState === 'function') {
            window.clearIdSelectorState();
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
    let raidsAppInitialized = false; // <-- 新增此行
    let levelUpAppInitialized = false; 
    let pvpRankerAppInitialized = false;
    let searchFiltersAppInitialized = false;
    let specialResearchAppInitialized = false;
    let infoHubAppInitialized = false; // <-- 【新增】
    let mapAppInitialized = false;
    // 【SEO】每個分頁的標題與描述，切換時動態套用，讓每個 ?tab= 網址在
    // 搜尋結果有各自明確的標題與摘要（而不是全部顯示同一段主頁文字）。
    const SITE_BASE = 'https://pogokit.com/';
    const TAB_SEO = {
        // 首頁的標題要跟 index.html <head> 裡寫死的那份一致 —— 這裡會在載入後蓋掉它，
        // 兩邊不同步的話 Google 抓到的會是這一份。交易清單是最多人搜的功能，
        // 而且很多人是從別人分享的清單圖找過來（圖底部印 pogokit.com/t），所以放最前面，
        // 英文關鍵字也直接寫進去，外國人搜 trade list 才對得上。
        'docs-app': {
            title: 'Pokémon Go 交易清單產生器 Trade List Maker｜IV100 CP、PvP 排名與搜尋指令｜Pokémon Go 工具箱',
            desc: '免費製作 Pokémon GO 交易清單圖片（Trade List Maker，支援 7 種語言）：選好想要與可換的寶可夢，一鍵產生分享圖。另有 IV100 CP 查詢、PvP IV 排名、編號篩選器、搜尋篩選指令、團體戰、孵蛋與田野調查，資料每日更新。'
        },
        'cp-checker-app': {
            // 避免使用括號：Google 改寫標題時容易從括號中間截斷，變成「25 等）｜…」
            title: 'IV100 CP 查詢表：15、20、25 等滿 IV CP 速查｜Pokémon Go 工具箱',
            desc: '輸入寶可夢名稱或編號，立即查出 IV 100% 在 15、20、25 等的 CP 數值，快速判斷團體戰捕捉與研究獎勵是否值得。'
        },
        'pvp-ranker-app': {
            title: 'PvP IV 排名查詢器（超級／高級／大師聯盟）｜Pokémon Go 工具箱',
            desc: '輸入攻擊、防禦、體力 IV，查出你的寶可夢在超級、高級、大師聯盟 GO 對戰聯盟中的 PvP 排名與最佳等級。'
        },
        'id-selector-app': {
            title: '寶可夢編號篩選器｜勾選即產生搜尋編號 - Pokémon Go 工具箱',
            desc: '點選想要的寶可夢，自動產生逗號分隔的全國圖鑑編號字串，直接貼進 Pokémon GO 遊戲內搜尋框，快速批次整理背包。'
        },
        'search-filters-app': {
            title: 'Pokémon Go 搜尋篩選指令大全（中文對照）｜工具箱',
            desc: '完整整理 Pokémon GO 遊戲內搜尋列的篩選語法：屬性、CP、IV、天氣、招式、暗影、異色與邏輯運算子，附中文說明與範例。'
        },
        'raids-app': {
            title: '當期團體戰頭目列表（含天氣加成 CP）｜Pokémon Go 工具箱',
            desc: '查看 Pokémon GO 目前 1 星、3 星、5 星傳說與超級團體戰頭目、屬性、CP 範圍與天氣加成，資料每日更新。'
        },
        'eggs-app': {
            title: '當期孵蛋列表（2／5／7／10／12 公里蛋池）｜Pokémon Go 工具箱',
            desc: '一覽 Pokémon GO 目前各距離蛋池可孵化的寶可夢，包含冒險同步與路線禮物蛋，資料每日更新。'
        },
        'research-app': {
            title: '田野調查任務與獎勵一覽｜Pokémon Go 工具箱',
            desc: '查詢 Pokémon GO 當期田野調查任務與對應獎勵寶可夢，可切換精選獎勵或所有任務，資料每日更新。'
        },
        'special-research-app': {
            title: '特殊調查任務流程與獎勵查詢｜Pokémon Go 工具箱',
            desc: '搜尋 Pokémon GO 特殊調查任務名稱，查看完整關卡流程與獎勵內容，找攻略不再翻來翻去。'
        },
        'info-hub-app': {
            title: '特別資訊：多星星沙子寶可夢等補充資料｜Pokémon Go 工具箱',
            desc: 'Pokémon GO 補充型資訊整理，例如捕捉時可獲得較多星星沙子的寶可夢清單。'
        },
        'map-app': {
            title: '補給站／道館地圖 + S2 網格｜Pokémon Go 工具箱',
            desc: '在地圖上查看 Pokémon GO 補給站與道館位置，支援 S2 網格（L14/L17）切換、地點搜尋與範圍測量，方便判斷道館生成與活動範圍。'
        },
        'trade-list': {
            title: '交易清單產生器：選寶可夢與背卡做圖｜Pokémon Go 工具箱',
            desc: 'Pokémon GO 交易清單產生器：挑選寶可夢（含異色、極巨化、超極巨化、造形）與特殊背卡，分「想要／可提供」，一鍵匯出交易清單圖片。'
        }
    };

    function applySeo(targetAppId) {
        // ?mon= 深連結的 SEO 是「單一寶可夢」層級的（index.html 的 head 腳本先設好、
        // cp-checker.js 的 syncMonUrlSeo() 補完）。這裡設的是分頁層級的通用值，
        // 會把 canonical 蓋成不帶 mon 的 ?tab=cp-checker-app —— Google 就會把那 1079
        // 個網址全部歸給同一頁。有 mon 時直接跳過，讓細的那層說了算。
        if (targetAppId === 'cp-checker-app' && new URLSearchParams(location.search).get('mon')) return;

        const seo = TAB_SEO[targetAppId] || TAB_SEO['docs-app'];
        document.title = seo.title;
        let descTag = document.querySelector('meta[name="description"]');
        if (descTag) descTag.setAttribute('content', seo.desc);
        let canonical = document.querySelector('link[rel="canonical"]');
        if (canonical) {
            canonical.setAttribute('href',
                targetAppId === 'docs-app' ? SITE_BASE : SITE_BASE + '?tab=' + targetAppId);
        }
    }

    function activateTab(targetAppId) {
        // 哪些工具真的有人用 —— 沒人用的就不必再花力氣維護
        if (window.track) window.track('tool_open', { tool: targetAppId });
        // 0. 移除 index.html 那段同步腳本注入的「開場先切到深連結分頁」暫用樣式（見該處註解）。
        //    JS 已經接手，之後一律由 .active class 控制顯示；不移除的話它寫死的
        //    #docs-app{display:none} 會讓使用者之後切回首頁時看到空白。
        const bootStyle = document.getElementById('boot-tab-style');
        if (bootStyle) bootStyle.remove();

        // 1. 更新內容區塊的顯示狀態
        appContents.forEach(content => {
            if (content.id === targetAppId) {
                content.classList.add('active');
            } else {
                content.classList.remove('active');
            }
        });

        // 2. 更新按鈕的 active 狀態
        tabButtons.forEach(btn => {
            if (btn.dataset.target === targetAppId) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
        
        // 3. 處理 App 的延遲載入 (將原本的邏輯搬移至此)
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
        } else if (targetAppId === 'raids-app' && !raidsAppInitialized) {
            initializeRaidsApp();
            raidsAppInitialized = true;
        } else if (targetAppId === 'pvp-ranker-app' && !pvpRankerAppInitialized) {
            initializePvpRanker();
            pvpRankerAppInitialized = true;
        } else if (targetAppId === 'level-up-app' && !levelUpAppInitialized) {
            initializeLevelUpApp();
            levelUpAppInitialized = true;
        } else if (targetAppId === 'search-filters-app' && !searchFiltersAppInitialized) {
            initializeSearchFiltersApp();
            initializeFilterBuilder();   // 同分頁的「篩選指令產生器」
            searchFiltersAppInitialized = true;
        } else if (targetAppId === 'special-research-app' && !specialResearchAppInitialized) {
            initializeSpecialResearchApp();
            specialResearchAppInitialized = true;
        } else if (targetAppId === 'info-hub-app' && !infoHubAppInitialized) {
            initializeInfoHubApp();
            infoHubAppInitialized = true;
        } else if (targetAppId === 'map-app' && !mapAppInitialized) {
            mapAppInitialized = true;
            // 動態載入：map-app.js 有 51KB，靜態 import 會讓每個頁面都下載它。
            // 這支同時依賴 index.html 載入的 Leaflet (L) 與 s2geometry (S2)。
            import('./map-app.js').then(m => m.initializeMapApp());
        }

        // 地圖分頁：捲動位置會沿用上一個分頁，若已往下捲會看不到地圖上方的
        // 控制列（搜尋框/面板），新用戶不知道那裡可以操作 → 進入時拉回頂端。
        // 並鎖住頁面捲動（地圖已滿版，說明文字改為 ❓ 彈窗），避免滑動時捲離地圖。
        if (targetAppId === 'map-app') {
            window.scrollTo(0, 0);
        }
        document.documentElement.classList.toggle('map-noscroll', targetAppId === 'map-app');

        // 4.【SEO】更新此分頁對應的標題與描述
        applySeo(targetAppId);
    }

    // 【SEO 改版】改用 ?tab= 查詢參數當網址（Google 會視為不同頁面收錄），
    // 取代原本的 #hash（hash 不會被當成獨立網址）。
    /* 暫時下架的分頁。markup、CSS、JS、資料全部留著，只是進不去 ——
       ?tab=map-app 會被當成無效網址退回首頁，導覽與首頁卡片也拿掉了。
       要重新開啟：把這個陣列清空，並把 index.html 兩處標了「地圖暫時下架」的
       註解取消（<head> 的 Leaflet/S2 載入、導覽列連結、首頁卡片）。 */
    const DISABLED_TABS = ['map-app'];

    function isValidTab(id) {
        return id && DISABLED_TABS.indexOf(id) === -1
            && Array.prototype.some.call(appContents, c => c.id === id);
    }

    // ?hl=en 之類的語言覆寫（index.html 的首頁翻譯用）要留在網址上，
    // 不然一重新整理就變回瀏覽器語言，沒辦法拿來檢查外國訪客看到的畫面。
    const HL = new URLSearchParams(location.search).get('hl');

    function navigateTo(targetAppId, replace) {
        const keep = HL ? (targetAppId === 'docs-app' ? '?hl=' : '&hl=') + encodeURIComponent(HL) : '';
        const url = (targetAppId === 'docs-app'
            ? window.location.pathname
            : window.location.pathname + '?tab=' + targetAppId) + keep;
        if (replace) {
            history.replaceState({ tab: targetAppId }, '', url);
        } else {
            history.pushState({ tab: targetAppId }, '', url);
        }
        activateTab(targetAppId);
    }

    // 點擊分頁按鈕/連結 → 更新網址 + 切換內容
    tabButtons.forEach(button => {
        button.addEventListener('click', (e) => {
            // 按住 Ctrl/Cmd/Shift 點 <a> 連結時交給瀏覽器開新分頁/視窗
            if (e.ctrlKey || e.metaKey || e.shiftKey) return;
            if (!button.dataset.target) return;   // 沒有 data-target = 真正跳頁的連結（如交易清單），交給瀏覽器正常導覽
            e.preventDefault();   // <a>：阻止整頁重新載入，改走 SPA 切換
            navigateTo(button.dataset.target, false);
        });
    });

    // 上一頁/下一頁（pushState）
    window.addEventListener('popstate', () => {
        const params = new URLSearchParams(window.location.search);
        const targetAppId = params.get('tab') || 'docs-app';
        if (isValidTab(targetAppId)) activateTab(targetAppId);
    });

    // 向後相容：舊的 #hash 書籤仍可運作
    window.addEventListener('hashchange', () => {
        const targetAppId = window.location.hash.substring(1);
        if (isValidTab(targetAppId)) navigateTo(targetAppId, true);
    });

    // 頁面初次載入：優先讀 ?tab=，其次舊的 #hash，都沒有就進主頁
    function handleInitialLoad() {
        const params = new URLSearchParams(window.location.search);
        const queryTab = params.get('tab');
        const hashTab = window.location.hash.substring(1);
        // 網址已經帶了有效的 ?tab= → 只切內容，不要重寫網址。
        // navigateTo() 是用 pathname + '?tab=' 重建網址的，會把 &mon= 這類深連結參數一起清掉；
        // 雖然 cp-checker 之後會補回來，中間仍有一瞬間停在別的網址 —— Google 算的是渲染後的網址，
        // 只要那次補救沒跑完（渲染有時間預算），整批 ?mon= 網址就會被判定「頁面會重新導向」而不收錄。
        if (isValidTab(queryTab) && queryTab !== 'docs-app') { activateTab(queryTab); return; }
        const initialTabId = isValidTab(queryTab) ? queryTab
                           : (isValidTab(hashTab) ? hashTab : 'docs-app');
        navigateTo(initialTabId, true);
    }

    handleInitialLoad(); // 立即執行初次載入處理

    // 預設載入第一個 App
    // initializeCpChecker();
    // cpAppInitialized = true;
   const nav = document.querySelector('.app-nav');

    // 1. 定義一個函式來設定 CSS 變數
    const siteHeader = document.querySelector('.site-header-main');
    function setNavHeight() {
        const navHeight = nav.offsetHeight; // 取得導覽列的實際高度
        document.documentElement.style.setProperty('--nav-height', `${navHeight}px`);
        // --nav-height 量的是 .app-nav，但真正 sticky 卡在畫面頂端的是外層的 .site-header-main
        // （手機上 .app-nav 只有 30px、整條頁首卻有 55px）。要把東西釘在頁首下面得用這個，
        // 用 --nav-height 會少算、被頁首蓋住一截。另開變數是為了不動到既有用 --nav-height 的頁面。
        if (siteHeader) {
            document.documentElement.style.setProperty('--header-height', `${siteHeader.offsetHeight}px`);
        }
    }


    // 3. 頁面載入時，立即執行一次高度計算
    setNavHeight();
    // DOMContentLoaded 當下版面還沒穩定（字體、圖片都還在載），這時量到的高度會偏掉，
    // 釘在頁首下方的元素就會跟頁首之間露出縫隙。load 後再量一次，之後交給 ResizeObserver 持續校正。
    window.addEventListener('load', setNavHeight);
    if (window.ResizeObserver && siteHeader) new ResizeObserver(setNavHeight).observe(siteHeader);

    // 4. 為視窗加上事件監聽器
    window.addEventListener('resize', setNavHeight); // 當視窗大小改變時，重新計算高度
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

    /* ---- 手機版選單 ------------------------------------------------------
       高度不能寫死成 calc(100vh - 50px)：手機瀏覽器的 100vh 是「網址列收起來
       之後」的高度，網址列還在時算出來的選單比實際可視範圍高，最後幾項會被推
       到螢幕外面且捲不到。改成開啟當下量「選單頂端到視窗底部」的真實距離。 */
    const headerBar = document.querySelector('.site-header-main');
    function sizeMenu() {
        // 量表頭的下緣，不要量選單自己 —— 選單收合時帶著 translateY(-8px)，
        // 量到的位置會比實際展開後高 8px。
        const top = headerBar ? headerBar.getBoundingClientRect().bottom : 52;
        // 底部留 8px，才看得出「下面還有東西可以捲」
        document.documentElement.style.setProperty(
            '--menu-max-h', Math.max(160, window.innerHeight - top - 8) + 'px');
    }

    function setMenu(open) {
        if (open) sizeMenu();            // 先量再開，避免開啟動畫期間高度跳動
        navLinks.classList.toggle('is-open', open);
        hamburgerButton.classList.toggle('is-active', open);
        hamburgerButton.setAttribute('aria-expanded', String(open));
        // 背景遮罩 + 鎖住頁面捲動，都掛在這個 class 上（只在手機的斷點內生效）
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
    const groupTitles = document.querySelectorAll('.nav-group .group-title');

    groupTitles.forEach(title => {
        title.addEventListener('click', () => {
            const group = title.closest('.nav-group');
            if (group) {
                group.classList.toggle('is-expanded');
                // 觸控裝置（平板）沒有 mouseleave：再點一次標題也能解除抑制、重新打開
                group.classList.remove('menu-suppressed');
            }
        });
    });
    // 開場動畫開關的單一來源在 index.html 的 <script>（那裡才來得及在首次繪製前
    // 移除深藍色遮罩，寫在這裡會先閃一下）。這邊只是跟著讀，不要各寫各的。
    const SHOW_INTRO_ANIMATION = window.SHOW_INTRO_ANIMATION === true;

    (function initIntro() {
        const overlay = document.getElementById('loading-overlay');
        if (!overlay) return;
        if (!SHOW_INTRO_ANIMATION) { overlay.remove(); return; }

        const canvas = overlay.querySelector('#intro-fx');
        const stage = overlay.querySelector('.iv-stage');
        const ctx = canvas && canvas.getContext('2d');
        if (!canvas || !stage || !ctx) { overlay.remove(); return; }

        const T = { charge: 850, burst: 420, reveal: 650 };
        let W, H, dpr, cx, cy, rafId, running = false, phase = 'idle';
        let stars = [], inward = [], sparks = [], timers = [];

        function resize() {
            dpr = Math.min(window.devicePixelRatio || 1, 2);
            W = canvas.width = innerWidth * dpr;
            H = canvas.height = innerHeight * dpr;
            canvas.style.width = innerWidth + 'px';
            canvas.style.height = innerHeight + 'px';
            const r = stage.getBoundingClientRect();
            cx = (r.left + r.width / 2) * dpr;
            cy = (r.top + r.height / 2) * dpr;
        }
        window.addEventListener('resize', resize);

        function makeStars() {
            stars = [];
            const n = Math.round((innerWidth * innerHeight) / 9000);
            for (let i = 0; i < n; i++) {
                stars.push({ x: Math.random() * W, y: Math.random() * H,
                    r: (Math.random() * 1.4 + .3) * dpr, a: Math.random(), tw: Math.random() * .04 + .008 });
            }
        }
        function spawnInward() {
            const ang = Math.random() * Math.PI * 2;
            const dist = (Math.max(W, H) * 0.5) * (0.55 + Math.random() * 0.5);
            inward.push({ ang, dist, speed: (2.4 + Math.random() * 2.2) * dpr, size: (Math.random() * 1.8 + .6) * dpr });
        }
        function explode() {
            for (let i = 0; i < 140; i++) {
                const ang = Math.random() * Math.PI * 2, sp = (Math.random() * 8 + 3) * dpr;
                sparks.push({ x: cx, y: cy, vx: Math.cos(ang) * sp, vy: Math.sin(ang) * sp,
                    size: (Math.random() * 2.4 + .8) * dpr, life: 1, decay: Math.random() * .012 + .008,
                    color: Math.random() < .6 ? [255,207,92] : (Math.random() < .5 ? [255,255,255] : [130,180,255]) });
            }
        }
        function draw() {
            ctx.clearRect(0, 0, W, H);
            for (const s of stars) {
                s.a += s.tw; ctx.globalAlpha = 0.35 + Math.abs(Math.sin(s.a)) * 0.6;
                ctx.fillStyle = '#cfe0ff'; ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, 7); ctx.fill();
            }
            ctx.globalAlpha = 1;
            if (phase === 'charge') {
                if (Math.random() < .9) { spawnInward(); spawnInward(); }
                for (const p of inward) {
                    p.dist -= p.speed;
                    const x = cx + Math.cos(p.ang) * p.dist, y = cy + Math.sin(p.ang) * p.dist;
                    const al = Math.max(0, 1 - p.dist / (Math.max(W, H) * .55));
                    ctx.globalAlpha = al * .9; ctx.fillStyle = '#ffdd88';
                    ctx.beginPath(); ctx.arc(x, y, p.size, 0, 7); ctx.fill();
                    ctx.globalAlpha = al * .35;
                    const x2 = cx + Math.cos(p.ang) * (p.dist + p.speed * 4), y2 = cy + Math.sin(p.ang) * (p.dist + p.speed * 4);
                    ctx.strokeStyle = '#ffcf5c'; ctx.lineWidth = p.size;
                    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x2, y2); ctx.stroke();
                }
                inward = inward.filter(p => p.dist > 6);
            }
            if (sparks.length) {
                for (const p of sparks) {
                    p.x += p.vx; p.y += p.vy; p.vx *= .97; p.vy *= .97; p.life -= p.decay;
                    if (p.life <= 0) continue;
                    ctx.globalAlpha = Math.max(0, p.life);
                    ctx.fillStyle = 'rgb(' + p.color[0] + ',' + p.color[1] + ',' + p.color[2] + ')';
                    ctx.beginPath(); ctx.arc(p.x, p.y, p.size * p.life, 0, 7); ctx.fill();
                }
                sparks = sparks.filter(p => p.life > 0);
            }
            ctx.globalAlpha = 1;
            rafId = requestAnimationFrame(draw);
        }
        function after(ms, fn) { timers.push(setTimeout(fn, ms)); }
        function finish() {
            overlay.classList.add('hidden');
            after(850, () => { cancelAnimationFrame(rafId); running = false; overlay.remove(); });
        }
        function skip() { if (running) { timers.forEach(clearTimeout); timers = []; finish(); } }

        resize(); makeStars();
        phase = 'charge'; running = true;
        void overlay.offsetWidth;
        overlay.classList.add('intro-run');
        draw();
        after(T.charge, () => { phase = 'burst'; overlay.classList.add('burst'); explode(); });
        after(T.charge + T.burst, () => { phase = 'idle'; overlay.classList.add('reveal'); });
        after(T.charge + T.burst + T.reveal, finish);
        overlay.addEventListener('click', skip);
    })();
    // 當選單中的任何一個頁籤按鈕被點擊時，自動收合選單
    tabButtonsInMenu.forEach(button => button.addEventListener('click', closeMenu));
    const desktopSubmenuButtons = document.querySelectorAll('.nav-group .sub-links .tab-button');

    desktopSubmenuButtons.forEach(button => {
        button.addEventListener('click', () => {
            const group = button.closest('.nav-group');
            if (group) {
                // 選完項目後抑制選單（不然滑鼠還停在原地、選單會一直開著），
                // 滑鼠離開該區域後解除，之後 hover 即可再次展開
                group.classList.add('menu-suppressed');
                button.blur();   // 放掉焦點，避免 :focus-within 讓選單持續顯示
                group.addEventListener('mouseleave', () => {
                    group.classList.remove('menu-suppressed');
                }, { once: true });
            }
        });
    });
});


