// 使用者登入與雲端資料（Firebase）。
//
// 首頁（main.js）和各獨立工具頁（/id-selector/、/special-research/ …）
// 都要用到同一套登入流程，所以抽出來共用 —— 不然獨立頁得整份載入 main.js，
// 而 main.js 會去找只有首頁才有的分頁節點。
//
// 讀取到的資料一律透過 window.* 掛鉤交給各工具模組（applyPinnedStateToUI、
// loadIdSelectorState、loadFilterBuilderState）。工具還沒初始化時先放進
// window.pending*，由工具自己在初始化時取用。
import { initializeApp } from "https://www.gstatic.com/firebasejs/9.15.0/firebase-app.js";
import { getDatabase, ref, set, get } from "https://www.gstatic.com/firebasejs/9.15.0/firebase-database.js";
import {
    getAuth,
    GoogleAuthProvider,
    signInWithPopup,
    signOut,
    onAuthStateChanged
} from "https://www.gstatic.com/firebasejs/9.15.0/firebase-auth.js";

export async function saveDataForCurrentUser(path, data) {
    // 沒有 config.js（本機預覽）時 initUserAuth() 不會初始化 Firebase，
    // 這時 getAuth() 會直接丟例外 —— 本來就沒登入，靜靜跳過就好
    if (!window.firebaseConfig) return;
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

/** 接上表頭的登入按鈕，並在登入狀態改變時載入／清除雲端資料。
 *  每頁只會呼叫一次；沒有 window.firebaseConfig（本機預覽）時直接跳過。 */
export function initUserAuth() {
    if (!window.firebaseConfig) return;
    const app = initializeApp(window.firebaseConfig);
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
}
