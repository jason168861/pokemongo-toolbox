export function initializeSpecialResearchApp() {
    let allResearches = [];
    const container = document.getElementById('special-research-container');
    const searchInput = document.getElementById('special-search-input');
    // 【修改1】獲取新增的核取方塊元素
    const includeAllCheckbox = document.getElementById('search-include-all');

    // 重新觸發搜尋的函式，方便重複呼叫
    const triggerSearch = () => {
        const event = new Event('input', { bubbles: true, cancelable: true });
        searchInput.dispatchEvent(event);
    };

    // 【修改2】為核取方塊加上事件監聽，當它被點擊時，重新觸發一次搜尋
    includeAllCheckbox.addEventListener('change', triggerSearch);


    fetch('data/special_research.json')
        .then(response => {
            if (!response.ok) {
                throw new Error('無法載入 JSON 檔案，請確認檔案名稱和路徑是否正確。');
            }
            return response.json();
        })
        .then(data => {
            allResearches = data.sort((a, b) => new Date(b.release_date) - new Date(a.release_date));
            
            // 【修改3】修改主要的搜尋事件監聽器
            searchInput.addEventListener('input', (event) => {
                const searchTerm = event.target.value.toLowerCase().trim();
                // 獲取核取方塊當前的狀態
                const searchInside = includeAllCheckbox.checked;

                const filteredResearches = allResearches.filter(research => {
                    // 如果搜尋詞是空的，直接顯示所有項目
                    if (!searchTerm) return true;

                    const lowerCaseTitle = research.title.toLowerCase();
                    // 預設先搜尋標題
                    if (lowerCaseTitle.includes(searchTerm)) {
                        return true;
                    }

                    // 如果使用者沒有勾選深入搜尋，且標題不符，則直接排除
                    if (!searchInside) {
                        return false;
                    }
                    
                    // 如果勾選了深入搜尋，則繼續往下檢查所有步驟 (steps)
                    // 使用 .some()，只要有一個符合條件就會回傳 true，效能較好
                    return research.steps.some(step => {
                        // 檢查步驟中的每一個任務 (tasks)
                        const taskMatch = step.tasks.some(task => 
                            task.description.toLowerCase().includes(searchTerm) ||
                            (task.reward.text && task.reward.text.toLowerCase().includes(searchTerm))
                        );

                        if (taskMatch) return true;

                        // 檢查完成該步驟的總獎勵 (total_rewards)
                        if (step.total_rewards) {
                            return step.total_rewards.some(reward =>
                                reward.text && reward.text.toLowerCase().includes(searchTerm)
                            );
                        }

                        return false;
                    });
                });
                
                generateResearchCards(filteredResearches);
            });
            searchInput.addEventListener('keydown', (event) => {
                if (event.key === 'Enter') {
                    event.preventDefault(); // 防止任何預設行為
                    searchInput.blur();     // 讓輸入框失去焦點
                }
            });
            // 頁面載入後先執行一次，顯示所有資料
            triggerSearch();
        })
        .catch(error => {
            container.innerHTML = `<div class="no-results" style="color:red;">${error.message}</div>`;
            console.error('讀取資料時發生錯誤:', error);
        });
    // ▼▼▼ 您原本的所有 helper functions (generateResearchCards, generateListHtml, addAccordionLogic) 也要一併複製到這裡 ▼▼▼
    function generateResearchCards(researches) {
        // 【修改】使用新的 ID
        const container = document.getElementById('special-research-container');
            container.innerHTML = ''; 

            if (researches.length === 0) {
                container.innerHTML = '<div class="no-results">找不到符合條件的調查 😅 <br>試試看別的關鍵字吧！</div>';
                return;
            }

            researches.forEach(research => {
                const card = document.createElement('div');
                card.className = 'research-card';
                
                const stepsHtml = research.steps.map(step => {
                    const tasksHtml = generateListHtml(step.tasks, 'task');
                    // ▼▼▼【緊湊佈局修改 3】為總獎勵加上新的 class ▼▼▼
                    const totalRewardsHtml = step.total_rewards && step.total_rewards.length > 0
                        ? `<div class="total-rewards-container">
                               <h4>🎉 完成階段總獎勵</h4>
                               <ul class="total-rewards-grid">${generateListHtml(step.total_rewards, 'total')}</ul>
                           </div>`
                        : '';
                    // ▲▲▲

                    return `
                        <div class="step">
                            <h3>${step.step_title}</h3>
                            <ul>${tasksHtml}</ul>
                            ${totalRewardsHtml}
                        </div>
                    `;
                }).join('');

                card.innerHTML = `
                    <div class="research-title">
                        <div class="research-title-block">
                            <span class="research-title-text">${research.title}</span>
                            <span class="research-date">發布日期: ${research.release_date || 'N/A'}</span>
                        </div>
                        <span class="icon">+</span>
                    </div>
                    <div class="research-content">
                        ${stepsHtml}
                    </div>
                `;
                
                container.appendChild(card);
            });
            
            addAccordionLogic();
    }

    function generateListHtml(items, type) {
        const placeholderSrc = "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="; // 1x1 透明 GIF

        return items.map(item => {
            let description, rewardText, imageUrls;

            if (type === 'task') {
                description = item.description;
                rewardText = item.reward.text;
                imageUrls = item.reward.image_urls || [];
                // 【修改處】將 src 改為 data-src，並新增 class="lazy-load"
                const imagesHtml = imageUrls.map(url => `<img src="${placeholderSrc}" data-src="${url}" alt="reward" class="reward-icon lazy-load">`).join('');
                const rewardTextHtml = rewardText ? `<span>(${rewardText})</span>` : '';

                return `
                    <li class="task-item">
                        <span class="task-description">${description}</span>
                        <div class="task-reward">
                            ${rewardTextHtml}
                            ${imagesHtml}
                        </div>
                    </li>`;

            } else { // type === 'total'
                description = item.text;
                imageUrls = item.image_url ? [item.image_url] : [];
                 // 【修改處】將 src 改為 data-src，並新增 class="lazy-load"
                const imagesHtml = imageUrls.map(url => `<img src="${placeholderSrc}" data-src="${url}" alt="reward" class="reward-icon lazy-load">`).join('');

                return `
                    <li class="total-reward-item">
                        ${imagesHtml}
                        <span class="total-reward-text">${description}</span>
                    </li>`;
            }
        }).join('');
    }

    function addAccordionLogic() {
        const titles = document.querySelectorAll('.research-title');

        titles.forEach(title => {
            title.addEventListener('click', () => {
                const isActive = title.classList.contains('active');
                title.classList.toggle('active', !isActive);
                const content = title.nextElementSibling;

                if (!isActive) {
                    content.classList.add('show');
                    content.style.maxHeight = content.scrollHeight + 50 + "px";

                    // 【新增邏輯】當卡片展開時，載入內部的圖片
                    const imagesToLoad = content.querySelectorAll('img.lazy-load');
                    imagesToLoad.forEach(img => {
                        img.src = img.dataset.src; // 將 data-src 的值賦給 src
                        img.classList.remove('lazy-load'); // 移除 class，避免重複處理
                        // 可以選擇性地加上載入完成的事件處理，例如加上淡入效果
                        img.onload = () => {
                            img.style.opacity = '1';
                        };
                    });

                } else {
                    content.style.maxHeight = null;
                    content.classList.remove('show');
                }
            });
        });
    }
}