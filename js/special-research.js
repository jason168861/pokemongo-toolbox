// js/special-research.js (完整最終版，未刪節)

// ====================================================================
//  【模組全域變數】
//  定義在最頂層，讓整個模組內的所有函式都能共用
// ====================================================================
let allResearches = [];
let isInitialized = false;
const container = document.getElementById('special-research-container');


// ====================================================================
//  【匯出的函式 (Exported Functions)】
//  這些函式需要被外部的 main.js 呼叫
// ====================================================================

/**
 * 從 main.js 接收使用者偏好設定，並更新資料狀態
 * @param {object | null} userData - 從 Firebase 讀取的使用者資料
 */
export function applyUserPreferences(userData) {
    const pinnedTitles = (userData && userData.pinnedResearches) ? userData.pinnedResearches : [];

    allResearches.forEach(research => {
        research.isPinned = pinnedTitles.includes(research.title);
    });

    if (isInitialized) {
        const allCards = container.querySelectorAll('.research-card');
        allCards.forEach(card => {
            const title = card.dataset.id;
            const isPinned = pinnedTitles.includes(title);
            card.classList.toggle('is-pinned', isPinned);
        });
        reorderAndRenderCards();
        console.log("已成功套用使用者置頂偏好設定。");
    }
}

/**
 * 初始化「特殊調查」App 的 UI 和事件
 */
export function initializeSpecialResearchApp() {
    if (isInitialized) return; // 防止重複初始化

    const searchInput = document.getElementById('special-search-input');
    const includeAllCheckbox = document.getElementById('search-include-all');
    const clearBtn = document.querySelector('#special-research-app .clear-search-btn');

    fetch('data/special_research.json')
        .then(response => {
            if (!response.ok) throw new Error('無法載入 JSON 檔案');
            return response.json();
        })
        .then(data => {
             const pinnedTitles = (initialUserPrefs && initialUserPrefs.pinnedResearches) 
                ? new Set(initialUserPrefs.pinnedResearches)
                : new Set();

            allResearches = data.map(research => ({
                ...research,
                isPinned: pinnedTitles.has(research.title) // 直接在這裡設定正確的置頂狀態
            }));

            generateResearchCards(allResearches);
            reorderAndRenderCards();

            // 綁定事件監聽器
            includeAllCheckbox.addEventListener('change', debounce(filterAndRender, 200));
            searchInput.addEventListener('input', debounce(filterAndRender, 300));
            searchInput.addEventListener('input', () => {
                clearBtn.style.display = searchInput.value ? 'block' : 'none';
            });
            window.addEventListener('resize', debounce(handleResize, 200));
            clearBtn.addEventListener('click', () => {
                searchInput.value = '';
                clearBtn.style.display = 'none';
                filterAndRender();
                searchInput.focus();
            });

            isInitialized = true;
        })
        .catch(error => {
            container.innerHTML = `<div class="no-results" style="color:red;">${error.message}</div>`;
            console.error('讀取資料時發生錯誤:', error);
        });
}

// ====================================================================
//  【內部輔助函式 (Internal Helper Functions)】
//  這些函式只供此模組內部使用，不需匯出
// ====================================================================

/**
 * 根據 isPinned 狀態重新排序 DOM 元素
 */
function reorderAndRenderCards() {
    if (!isInitialized) return;

    allResearches.sort((a, b) => {
        if (a.isPinned !== b.isPinned) {
            return a.isPinned ? -1 : 1;
        }
        return new Date(b.release_date) - new Date(a.release_date);
    });

    const fragment = document.createDocumentFragment();
    allResearches.forEach(research => {
        const cardElement = container.querySelector(`.research-card[data-id="${CSS.escape(research.title)}"]`);
        if (cardElement) {
            fragment.appendChild(cardElement);
        }
    });
    container.appendChild(fragment);
}

/**
 * Debounce 函式，用於延遲觸發，避免過於頻繁的執行
 */
function debounce(func, delay) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), delay);
    };
}

/**
 * 根據輸入過濾畫面上的卡片
 */
function filterAndRender() {
    const searchInput = document.getElementById('special-search-input');
    const includeAllCheckbox = document.getElementById('search-include-all');
    const searchTerm = searchInput.value.toLowerCase().trim();
    const searchInside = includeAllCheckbox.checked;
    const allCardElements = container.querySelectorAll('.research-card');
    let noResultsMessage = container.querySelector('.no-results');
    let hasResults = false;

    allCardElements.forEach(card => card.style.display = 'none');

    if (!searchTerm) {
        allCardElements.forEach(card => card.style.display = 'block');
        if (noResultsMessage) noResultsMessage.style.display = 'none';
        return;
    }

    allResearches.forEach(research => {
        if (!research || !research.title) return;
        let isMatch = research.title.toLowerCase().includes(searchTerm);
        
        if (!isMatch && searchInside) {
            isMatch = research.steps.some(step =>
                (step.tasks && step.tasks.some(task =>
                    (task.description && task.description.toLowerCase().includes(searchTerm)) ||
                    (task.reward && task.reward.text && task.reward.text.toLowerCase().includes(searchTerm))
                )) ||
                (step.total_rewards && step.total_rewards.some(reward =>
                    (reward.text && reward.text.toLowerCase().includes(searchTerm))
                ))
            );
        }

        if (isMatch) {
            hasResults = true;
            const cardToShow = container.querySelector(`.research-card[data-id="${CSS.escape(research.title)}"]`);
            if (cardToShow) cardToShow.style.display = 'block';
        }
    });

    if (noResultsMessage) {
        noResultsMessage.style.display = hasResults ? 'none' : 'block';
    }
}

/**
 * 處理瀏覽器視窗大小變化的邏輯
 */
function handleResize() {
    const allOpenCards = container.querySelectorAll('.research-card .research-content.show');
    allOpenCards.forEach(content => {
        if (content.classList.contains('show')) {
            content.style.maxHeight = content.scrollHeight + 50 + 'px';
        }
        
        const card = content.closest('.research-card');
        const toggleAllBtn = card.querySelector('.toggle-all-steps-btn');
        if (toggleAllBtn) {
             if (window.innerWidth < 768) {
                toggleAllBtn.style.display = 'inline-flex';
            } else {
                toggleAllBtn.style.display = 'none';
            }
        }
    });

    if (window.innerWidth >= 768) {
        const allActiveStepHeaders = container.querySelectorAll('.step-header.active');
        const allStepContentsWithStyle = container.querySelectorAll('.step-content[style*="max-height"]');
        allActiveStepHeaders.forEach(header => header.classList.remove('active'));
        allStepContentsWithStyle.forEach(content => content.style.maxHeight = null);

        const allToggleButtons = container.querySelectorAll('.toggle-all-steps-btn');
        allToggleButtons.forEach(btn => {
            btn.dataset.state = 'collapsed';
            const btnText = btn.querySelector('.btn-text');
            if (btnText) btnText.textContent = '全部展開';
        });
    }
}

/**
 * 同步「全部展開/收合」按鈕的狀態
 */
function syncToggleButtonState(card) {
    if (!card) return;
    const toggleAllBtn = card.querySelector('.toggle-all-steps-btn');
    const btnText = toggleAllBtn.querySelector('.btn-text');
    if (!toggleAllBtn || !btnText) return;

    const allStepHeaders = card.querySelectorAll('.step-header');
    const activeStepHeaders = card.querySelectorAll('.step-header.active');
    if (allStepHeaders.length === 0) return;

    if (activeStepHeaders.length === allStepHeaders.length) {
        toggleAllBtn.dataset.state = 'expanded';
        btnText.textContent = '全部收合';
    } else {
        toggleAllBtn.dataset.state = 'collapsed';
        btnText.textContent = '全部展開';
    }
}

/**
 * 產生單個獎勵或任務列表的 HTML
 */
function generateListHtml(items, type) {
    const placeholderSrc = "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=";
    return items.map(item => {
        if (type === 'task') {
            const description = item.description;
            const rewardText = item.reward.text;
            const imageUrls = item.reward.image_urls || [];
            const imagesHtml = imageUrls.map(url => `<img src="${placeholderSrc}" data-src="${url}" alt="reward" class="reward-icon lazy-load">`).join('');
            const rewardTextHtml = rewardText ? `<span>(${rewardText})</span>` : '';
            return `<li class="task-item"><span class="task-description">${description}</span><div class="task-reward">${rewardTextHtml}${imagesHtml}</div></li>`;
        } else {
            const description = item.text;
            const imageUrls = item.image_url ? [item.image_url] : [];
            const imagesHtml = imageUrls.map(url => `<img src="${placeholderSrc}" data-src="${url}" alt="reward" class="reward-icon lazy-load">`).join('');
            return `<li class="total-reward-item">${imagesHtml}<span class="total-reward-text">${description}</span></li>`;
        }
    }).join('');
}

/**
 * 產生單個調查的詳細步驟 HTML
 */
function generateDetailsHtml(research) {
    return research.steps.map(step => {
        const tasksHtml = generateListHtml(step.tasks, 'task');
        const totalRewardsHtml = step.total_rewards && step.total_rewards.length > 0
            ? `<div class="total-rewards-container">
                <h4>🎉 完成階段總獎勵</h4>
                <ul class="total-rewards-grid">${generateListHtml(step.total_rewards, 'total')}</ul>
            </div>`
            : '';
        return `
            <div class="step">
                <div class="step-header">
                    <h3>${step.step_title}</h3>
                    <span class="step-icon">+</span>
                </div>
                <div class="step-content">
                    <ul>${tasksHtml}</ul>
                    ${totalRewardsHtml}
                </div>
            </div>
        `;
    }).join('');
}

/**
 * 根據資料陣列產生所有調查卡片的基礎 UI
 */
function generateResearchCards(researches) {
    container.innerHTML = '';
    const fragment = document.createDocumentFragment();

    researches.forEach((research) => {
        const card = document.createElement('div');
        card.className = 'research-card';
        card.dataset.id = research.title;
        if (research.isPinned) {
            card.classList.add('is-pinned');
        }
        card.innerHTML = `
            <div class="research-title">
                <div class="research-title-block">
                    <button class="pin-btn" aria-label="置頂/取消置頂">📌</button>
                    <span class="research-title-text">${research.title}</span>
                </div>
                <div class="title-right-controls">
                    <span class="research-date">發布日期: ${research.release_date || 'N/A'}</span>
                    <span class="icon">+</span>
                </div>
            </div>
            <div class="toggle-all-steps-container">
                <button class="toggle-all-steps-btn" data-state="collapsed" style="display: none;">
                    <span class="btn-icon">▼</span>
                    <span class="btn-text">全部展開</span>
                </button>
            </div>
            <div class="research-content"></div>
        `;
        fragment.appendChild(card);
    });

    const noResultsDiv = document.createElement('div');
    noResultsDiv.className = 'no-results';
    noResultsDiv.textContent = '找不到符合條件的調查 😅 試試看別的關鍵字吧！';
    noResultsDiv.style.display = 'none';
    fragment.appendChild(noResultsDiv);

    container.appendChild(fragment);
    addGlobalClickListener();
}

/**
 * 為整個容器綁定點擊事件 (事件代理)
 */
function addGlobalClickListener() {
    container.addEventListener('click', (event) => {
        const target = event.target;

        // --- 處理【置頂按鈕】點擊 ---
        if (target.closest('.pin-btn')) {
            event.stopPropagation();
            const card = target.closest('.research-card');
            const researchId = card.dataset.id;
            const researchData = allResearches.find(r => r.title === researchId);

            if (researchData) {
                researchData.isPinned = !researchData.isPinned;
                card.classList.toggle('is-pinned', researchData.isPinned);
                reorderAndRenderCards();
                
                if (window.saveAppState) {
                    const currentStateToSave = {
                        pinnedResearches: allResearches
                            .filter(r => r.isPinned)
                            .map(r => r.title)
                    };
                    window.saveAppState(currentStateToSave);
                }
            }
            return;
        }

        // --- 處理【卡片標題】點擊 (展開/收合整個調查) ---
        const title = target.closest('.research-title');
        if (title) {
            const card = title.closest('.research-card');
            const content = card.querySelector('.research-content');
            const toggleAllBtn = card.querySelector('.toggle-all-steps-btn');
            
            if (!card.dataset.detailsRendered) {
                const researchId = card.dataset.id;
                const researchData = allResearches.find(r => r.title === researchId);
                
                if (researchData) {
                    content.innerHTML = generateDetailsHtml(researchData);
                    card.dataset.detailsRendered = 'true';
                    
                    toggleAllBtn.addEventListener('click', () => {
                        const currentState = toggleAllBtn.dataset.state;
                        const allStepHeaders = content.querySelectorAll('.step-header');
                        const allStepContents = content.querySelectorAll('.step-content');
                        const btnText = toggleAllBtn.querySelector('.btn-text');

                        if (currentState === 'collapsed') {
                            allStepHeaders.forEach(header => header.classList.add('active'));
                            allStepContents.forEach(stepContent => stepContent.style.maxHeight = stepContent.scrollHeight + "px");
                            btnText.textContent = '全部收合';
                            toggleAllBtn.dataset.state = 'expanded';
                        } else {
                            allStepHeaders.forEach(header => header.classList.remove('active'));
                            allStepContents.forEach(stepContent => stepContent.style.maxHeight = null);
                            btnText.textContent = '全部展開';
                            toggleAllBtn.dataset.state = 'collapsed';
                        }
                        
                        setTimeout(() => {
                            if (content.classList.contains('show')) {
                               content.style.maxHeight = content.scrollHeight + 50 + "px";
                            }
                        }, 300);
                    });
                }
            }
            
            const isActive = title.classList.contains('active');
            title.classList.toggle('active', !isActive);
            
            if (!isActive) {
                content.classList.add('show');
                if (window.innerWidth < 768) {
                    toggleAllBtn.style.display = 'inline-flex';
                }
                content.style.maxHeight = content.scrollHeight + 50 + "px";
                const imagesToLoad = content.querySelectorAll('img.lazy-load');
                imagesToLoad.forEach(img => {
                    if (img.dataset.src) {
                       img.src = img.dataset.src;
                       img.classList.remove('lazy-load');
                       img.onload = () => { img.style.opacity = '1'; };
                    }
                });
            } else {
                content.style.maxHeight = null;
                content.classList.remove('show');
                toggleAllBtn.style.display = 'none';
            }
             setTimeout(() => {
               if (content.classList.contains('show')) {
                  content.style.maxHeight = content.scrollHeight + 50 + "px";
               }
            }, 10);
        }

        // --- 處理【關卡】點擊 (僅在手機版寬度生效) ---
        const stepHeader = target.closest('.step-header');
        if (stepHeader && window.innerWidth < 768) {
            const stepContent = stepHeader.nextElementSibling;
            const researchContent = stepHeader.closest('.research-content');

            stepHeader.classList.toggle('active');
            
            if (stepHeader.classList.contains('active')) {
                const contentScrollHeight = stepContent.scrollHeight;
                stepContent.style.maxHeight = contentScrollHeight + "px";
                if (researchContent) researchContent.style.maxHeight = (researchContent.scrollHeight + contentScrollHeight + 50) + "px";
            } else {
                const contentScrollHeight = stepContent.scrollHeight;
                stepContent.style.maxHeight = null;
                if (researchContent) researchContent.style.maxHeight = (researchContent.scrollHeight - contentScrollHeight + 50) + "px";
            }
            syncToggleButtonState(stepHeader.closest('.research-card'));
            return;
        }
    });
}