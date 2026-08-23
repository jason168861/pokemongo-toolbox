// js/special-research.js (優化後版本)
import { saveDataForCurrentUser } from './main.js';
    let allResearches = [];
let container = null; // container 也提升，讓所有函式都能存取
let searchInput = null;
let includeAllCheckbox = null;
let clearBtn = null;
window.applyPinnedStateToUI = function(pinnedTitles) {
    if (!container || !allResearches) return;
    if (!Array.isArray(pinnedTitles)) pinnedTitles = [];

    let needsRender = false;
    allResearches.forEach(research => {
        const shouldBePinned = pinnedTitles.includes(research.title);
        if (research.isPinned !== shouldBePinned) {
            research.isPinned = shouldBePinned;
            needsRender = true;
        }
    });

    if (needsRender) {
        // console.log("🎨 正在套用釘選狀態並更新畫面...");
        allResearches.forEach(research => {
            const card = container.querySelector(`.research-card[data-id="${research.title}"]`);
            if (card) {
                card.classList.toggle('is-pinned', research.isPinned);
            }
        });
        reorderAndRenderCards();
    }
}

        function reorderAndRenderCards() {
        // 核心排序邏輯：
        // 1. isPinned 為 true 的排在前面
        // 2. 如果 isPinned 狀態相同，則依照原有的發布日期排序
        allResearches.sort((a, b) => {
            if (a.isPinned !== b.isPinned) {
                return a.isPinned ? -1 : 1;
            }
            return new Date(b.release_date) - new Date(a.release_date);
        });

        const fragment = document.createDocumentFragment();
        // 根據排序後的新順序，將 DOM 元素重新插入到 fragment 中
        allResearches.forEach(research => {
            // 透過 data-id 找到對應的 DOM 元素
            const cardElement = container.querySelector(`.research-card[data-id="${research.title}"]`);
            if (cardElement) {
                fragment.appendChild(cardElement);
            }
        });

        // 最後一次性地將排序好的所有卡片重新加回容器，實現畫面上的重新排序
        container.appendChild(fragment);
    }
    // Debounce 函式保持不變
    function debounce(func, delay) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), delay);
        };
    }
    function syncToggleButtonState(card) {
    if (!card) return; // 安全檢查

    const toggleAllBtn = card.querySelector('.toggle-all-steps-btn');
    const btnText = card.querySelector('.toggle-all-steps-btn .btn-text');

    // 再次安全檢查，確保按鈕和文字元素都存在
    if (!toggleAllBtn || !btnText) {
        return;
    }

    // 獲取此卡片中所有的關卡標題，以及已展開的關卡標題
    const allStepHeaders = card.querySelectorAll('.step-header');
    const activeStepHeaders = card.querySelectorAll('.step-header.active');

    // 如果沒有任何關卡，則不執行任何操作
    if (allStepHeaders.length === 0) {
        return;
    }

    // 核心邏輯：如果展開的數量等於總數，代表全部已展開
    if (activeStepHeaders.length === allStepHeaders.length) {
        toggleAllBtn.dataset.state = 'expanded';
        btnText.textContent = '全部收合';
    } else {
        // 否則 (全部收合、或部分展開)，都將按鈕狀態設為可展開
        toggleAllBtn.dataset.state = 'collapsed';
        btnText.textContent = '全部展開';
    }
}
function handleResize() {
    const allOpenCards = container.querySelectorAll('.research-card .research-content.show');
    allOpenCards.forEach(content => {
        // 這段是為了確保展開的卡片在視窗大小改變時高度能自適應，需要保留
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

    // 當視窗寬度大於等於 768px (進入電腦版)，執行狀態重設
    if (window.innerWidth >= 768) {
        // 找到所有在手機上被展開的關卡標題和內容
        const allActiveStepHeaders = container.querySelectorAll('.step-header.active');
        const allStepContentsWithStyle = container.querySelectorAll('.step-content[style*="max-height"]');

        // 1. 移除標題的 active 狀態
        allActiveStepHeaders.forEach(header => {
            header.classList.remove('active');
        });

        // 2. 移除內容區塊上殘留的 max-height 行內樣式
        allStepContentsWithStyle.forEach(content => {
            content.style.maxHeight = null;
        });

        // 3. 【新增的關鍵修正】重設「全部展開/收合」按鈕的狀態與文字
        const allToggleButtons = container.querySelectorAll('.toggle-all-steps-btn');
        allToggleButtons.forEach(btn => {
            btn.dataset.state = 'collapsed';
            const btnText = btn.querySelector('.btn-text');
            if (btnText) {
                btnText.textContent = '全部展開';
            }
        });
    }
}

// --- 【新增】移除高亮的輔助函式 ---
function removeHighlights(container) {
    const marks = container.querySelectorAll('mark');
    marks.forEach(mark => {
        const parent = mark.parentNode;
        parent.replaceChild(document.createTextNode(mark.textContent), mark);
        parent.normalize(); // 合併相鄰的文字節點
    });
}

// --- 【新增】套用高亮的輔助函式 ---
function highlightMatches(container, searchTerm) {
    if (!searchTerm) return;
    const regex = new RegExp(searchTerm, 'gi');
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
    let node;
    const nodesToProcess = [];
    while (node = walker.nextNode()) {
        if (node.parentElement.tagName !== 'SCRIPT' && node.parentElement.tagName !== 'STYLE') {
            nodesToProcess.push(node);
        }
    }
    nodesToProcess.forEach(node => {
        const text = node.textContent;
        if (regex.test(text)) {
            const fragment = document.createDocumentFragment();
            const parts = text.split(regex);
            let lastIndex = 0;
            parts.forEach((part, index) => {
                fragment.appendChild(document.createTextNode(part));
                if (index < parts.length - 1) {
                    const matchText = text.substring(lastIndex + part.length).match(regex)[0];
                    const mark = document.createElement('mark');
                    mark.textContent = matchText;
                    fragment.appendChild(mark);
                    lastIndex += part.length + matchText.length;
                }
            });
            node.parentNode.replaceChild(fragment, node);
        }
    });
}

// --- 【修改】搜尋與過濾邏輯，加入高亮處理 ---
function filterAndRender() {
    const searchTerm = zhLower(searchInput.value).trim();   // 繁簡通用
    const searchInside = includeAllCheckbox.checked;
    const allCardElements = container.querySelectorAll('.research-card');
    const noResultsMessage = container.querySelector('.no-results');
    let hasResults = false;

    // 步驟 1: 先清除所有舊的高亮
    allCardElements.forEach(card => {
        removeHighlights(card);
    });

    // 如果沒有搜尋關鍵字，則顯示全部並結束函式
    if (!searchTerm) {
        allCardElements.forEach(card => {
            card.style.display = 'block';
        });
        if (noResultsMessage) {
            noResultsMessage.style.display = 'none';
        }
        return; 
    }

    // 步驟 2: 先隱藏所有卡片
    allCardElements.forEach(card => {
        card.style.display = 'none';
    });

    // 步驟 3: 遍歷資料，找出符合條件的項目並顯示、套用高亮
    allResearches.forEach(research => {
        if (!research || !research.title) return;
        let isMatch = false;
        const lowerCaseTitle = zhLower(research.title);

        if (lowerCaseTitle.includes(searchTerm)) {
            isMatch = true;
        } 
        else if (searchInside) {
            isMatch = research.steps.some(step =>
                (step.tasks && step.tasks.some(task =>
                    (task.description && zhLower(task.description).includes(searchTerm)) ||
                    (task.reward && task.reward.text && zhLower(task.reward.text).includes(searchTerm))
                )) ||
                (step.total_rewards && step.total_rewards.some(reward =>
                    (reward.text && zhLower(reward.text).includes(searchTerm))
                ))
            );
        }

        if (isMatch) {
            hasResults = true;
            const safeTitle = CSS.escape(research.title);
            const cardToShow = container.querySelector(`.research-card[data-id="${safeTitle}"]`);
            if (cardToShow) {
                cardToShow.style.display = 'block';
                // 套用高亮
                highlightMatches(cardToShow, searchTerm);
            }
        }
    });

    // 步驟 4: 根據結果決定是否顯示「找不到結果」的訊息
    if (noResultsMessage) {
        noResultsMessage.style.display = hasResults ? 'none' : 'block';
    }
}
    // ================================================================
    // 【優化核心】 1. 修改 generateResearchCards
    // 現在只產生卡片的「外殼」和「標題」，內容是空的。
    // ================================================================
    function generateResearchCards(researches) {
        container.innerHTML = ''; 
        if (researches.length === 0) {
            container.innerHTML = '<div class="no-results">找不到符合條件的調查 😅 <br>試試看別的關鍵字吧！</div>';
            return;
        }
        const fragment = document.createDocumentFragment();

        researches.forEach((research, index) => {
            const card = document.createElement('div');
            card.className = 'research-card';
            card.dataset.id = research.title; 

            // 只產生標題和一個空的內容容器
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

    // ================================================================
    // 【優化核心】 2. 新增 generateDetailsHtml 函式
    // 這個函式負責產生「單一」調查的詳細內容 HTML。
    // ================================================================
    function generateDetailsHtml(research) {
        // 為每個 step 加上一個 header 和一個 content wrapper
        return research.steps.map(step => {
            const tasksHtml = generateListHtml(step.tasks, 'task');
            const totalRewardsHtml = step.total_rewards && step.total_rewards.length > 0
                ? `<div class="total-rewards-container">
                    <h4>🎉 完成階段總獎勵</h4>
                    <ul class="total-rewards-grid">${generateListHtml(step.total_rewards, 'total')}</ul>
                </div>`
                : '';

            // 新增的結構：step-header + step-content
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


    // generateListHtml 函式保持不變
    function generateListHtml(items, type) {
        const placeholderSrc = "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=";
        return items.map(item => {
            let description, rewardText, imageUrls;
            if (type === 'task') {
                description = item.description;
                rewardText = item.reward.text;
                imageUrls = item.reward.image_urls || [];
                const imagesHtml = imageUrls.map(url => `<img src="${placeholderSrc}" data-src="${url}" alt="reward" class="reward-icon lazy-load">`).join('');
                const rewardTextHtml = rewardText ? `<span>(${rewardText})</span>` : '';
                return `<li class="task-item"><span class="task-description">${description}</span><div class="task-reward">${rewardTextHtml}${imagesHtml}</div></li>`;
            } else { 
                description = item.text;
                imageUrls = item.image_url ? [item.image_url] : [];
                const imagesHtml = imageUrls.map(url => `<img src="${placeholderSrc}" data-src="${url}" alt="reward" class="reward-icon lazy-load">`).join('');
                return `<li class="total-reward-item">${imagesHtml}<span class="total-reward-text">${description}</span></li>`;
            }
        }).join('');
    }

    // ================================================================
    // 【優化核心】 3. 大幅修改 addAccordionLogic
    // 現在它會在第一次點擊時才產生內容。
    // ================================================================
function addGlobalClickListener() {
        container.addEventListener('click', (event) => {
            const target = event.target;
            
            // --- 1. 處理【關卡】點擊 (僅在手機版寬度生效) ---
            const stepHeader = target.closest('.step-header');
            if (stepHeader && window.innerWidth < 768) {
                const stepContent = stepHeader.nextElementSibling;
                const researchContent = stepHeader.closest('.research-content');

                stepHeader.classList.toggle('active');
                
                if (stepHeader.classList.contains('active')) {
                    const contentScrollHeight = stepContent.scrollHeight;
                    stepContent.style.maxHeight = contentScrollHeight + "px";
                    if (researchContent) {
                        researchContent.style.maxHeight = (researchContent.scrollHeight + contentScrollHeight + 50) + "px";
                    }
                } else {
                    const contentScrollHeight = stepContent.scrollHeight;
                    stepContent.style.maxHeight = null;
                    if (researchContent) {
                       researchContent.style.maxHeight = (researchContent.scrollHeight - contentScrollHeight + 50) + "px";
                    }
                }
                syncToggleButtonState(stepHeader.closest('.research-card'));
                return;
            }

            // --- 2. 處理【置頂按鈕】點擊 ---
            if (target.closest('.pin-btn')) {
                event.stopPropagation();
                const card = target.closest('.research-card');
                const researchId = card.dataset.id;
                const researchData = allResearches.find(r => r.title === researchId);

                if (researchData) {
                    researchData.isPinned = !researchData.isPinned;
                    card.classList.toggle('is-pinned', researchData.isPinned);
                    reorderAndRenderCards();
                    saveCurrentPinnedState();
                }
                return;
            }

            // --- 3. 處理【卡片標題】點擊 (展開/收合整個調查) ---
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
                        
                        // --- 【修改】首次渲染內容後，立即套用高亮 ---
                        const currentSearchTerm = searchInput.value.toLowerCase().trim();
                        if (currentSearchTerm) {
                            highlightMatches(content, currentSearchTerm);
                        }
                        
                        // ▼▼▼【核心修改】修正「全部展開/收合」按鈕的邏輯 ▼▼▼
                        toggleAllBtn.addEventListener('click', () => {
                            const currentState = toggleAllBtn.dataset.state;
                            const allStepHeaders = content.querySelectorAll('.step-header');
                            const allStepContents = content.querySelectorAll('.step-content');
                            const btnText = toggleAllBtn.querySelector('.btn-text');

                            if (currentState === 'collapsed') {
                                // 直接操作所有關卡的樣式，而不是模擬點擊
                                allStepHeaders.forEach(header => header.classList.add('active'));
                                allStepContents.forEach(stepContent => {
                                    stepContent.style.maxHeight = stepContent.scrollHeight + "px";
                                });
                                btnText.textContent = '全部收合';
                                toggleAllBtn.dataset.state = 'expanded';
                            } else {
                                allStepHeaders.forEach(header => header.classList.remove('active'));
                                allStepContents.forEach(stepContent => {
                                    stepContent.style.maxHeight = null;
                                });
                                btnText.textContent = '全部展開';
                                toggleAllBtn.dataset.state = 'collapsed';
                            }
                            
                            // 延遲一小段時間後，再重新計算並設定父容器的總高度
                            setTimeout(() => {
                                if (content.classList.contains('show')) {
                                   content.style.maxHeight = content.scrollHeight + 50 + "px";
                                }
                            }, 300); // 300毫秒的延遲足以應對CSS動畫
                        });
                        // ▲▲▲ 修改結束 ▲▲▲
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
        });
    }
function saveCurrentPinnedState() {
    const pinnedTitles = allResearches
        .filter(r => r.isPinned)
        .map(r => r.title);
        
    // 【偵錯日誌 6】: 確認此函式被呼叫，並查看準備儲存的內容
    // console.log('📌 偵測到釘選狀態改變，準備呼叫儲存函式。內容:', pinnedTitles);

    saveDataForCurrentUser('specialResearch/pinned', pinnedTitles);
}
export function initializeSpecialResearchApp() {
    container = document.getElementById('special-research-container');
    searchInput = document.getElementById('special-search-input');
    includeAllCheckbox = document.getElementById('search-include-all');
    clearBtn = document.querySelector('#special-research-app .clear-search-btn');

        //【新增 4】: 匯出一個函式讓 main.js 可以呼叫它來讀取資料
    // 這個函式會接收從 Firebase 讀取到的釘選標題陣列

    // Fetch 資料的主流程保持不變
fetch('data/special_research.json')
        .then(response => {
            if (!response.ok) throw new Error('無法載入 JSON 檔案');
            return response.json();
        })
        .then(data => {
            // 【修改】為每筆資料加上 isPinned 屬性
            allResearches = data
                .sort((a, b) => new Date(b.release_date) - new Date(a.release_date))
                .map(research => ({ ...research, isPinned: false })); // 預設都是未置頂

            generateResearchCards(allResearches);
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
            if (window.pendingPinnedTitles) {
                // console.log('💎 發現暫存的釘選資料，立即套用！');
                window.applyPinnedStateToUI(window.pendingPinnedTitles);
                // 用完後清空，避免重複套用
                delete window.pendingPinnedTitles; 
            }
        })
        .catch(error => {
            container.innerHTML = `<div class="no-results" style="color:red;">${error.message}</div>`;
            console.error('讀取資料時發生錯誤:', error);
        });
}