export function initializeSpecialResearchApp() {
    let allResearches = [];
    const container = document.getElementById('special-research-container');
    const searchInput = document.getElementById('special-search-input');
    const includeAllCheckbox = document.getElementById('search-include-all');

    // 【優化1：Debounce 函式】
    // 目的：防止函式被過於頻繁地呼叫。它會確保在使用者停止輸入一段時間後，才執行真正的搜尋函式。
    function debounce(func, delay) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), delay);
        };
    }

    // 真正的搜尋與過濾邏輯
    function filterAndRender() {
        const searchTerm = searchInput.value.toLowerCase().trim();
        const searchInside = includeAllCheckbox.checked;
        let hasResults = false;

        // 【優化2：不再重新生成HTML，而是切換顯示/隱藏】
        // 我們遍歷所有已存在的卡片元素
        const allCards = container.querySelectorAll('.research-card');

        allCards.forEach(card => {
            const research = allResearches[card.dataset.index]; // 從卡片上預存的索引取得原始資料
            let isMatch = false;

            if (!searchTerm) {
                isMatch = true; // 如果搜尋框是空的，顯示所有項目
            } else {
                const lowerCaseTitle = research.title.toLowerCase();
                if (lowerCaseTitle.includes(searchTerm)) {
                    isMatch = true;
                } else if (searchInside) {
                    // 深入搜尋的邏輯保持不變
                    isMatch = research.steps.some(step => {
                        const taskMatch = step.tasks.some(task =>
                            task.description.toLowerCase().includes(searchTerm) ||
                            (task.reward.text && task.reward.text.toLowerCase().includes(searchTerm))
                        );
                        if (taskMatch) return true;

                        if (step.total_rewards) {
                            return step.total_rewards.some(reward =>
                                reward.text && reward.text.toLowerCase().includes(searchTerm)
                            );
                        }
                        return false;
                    });
                }
            }
            
            // 根據是否匹配，切換卡片的顯示狀態
            if (isMatch) {
                card.style.display = 'block';
                hasResults = true;
            } else {
                card.style.display = 'none';
            }
        });

        // 處理「找不到結果」的提示
        const noResultsMessage = container.querySelector('.no-results');
        if (noResultsMessage) {
            noResultsMessage.style.display = hasResults ? 'none' : 'block';
        }
    }

    fetch('data/special_research.json')
        .then(response => {
            if (!response.ok) {
                throw new Error('無法載入 JSON 檔案，請確認檔案名稱和路徑是否正確。');
            }
            return response.json();
        })
        .then(data => {
            allResearches = data.sort((a, b) => new Date(b.release_date) - new Date(a.release_date));
            
            // 【優化3：頁面載入時，一次性生成所有卡片】
            // 先將所有卡片渲染到畫面上，但之後只會控制它們的顯示或隱藏
            generateResearchCards(allResearches);

            // 當 checkbox 狀態改變時，也使用 debounce 來觸發搜尋，避免連續點擊造成卡頓
            includeAllCheckbox.addEventListener('change', debounce(filterAndRender, 200));

            // 將 'input' 事件的監聽器，用 debounce 包起來，延遲 300 毫秒執行
            searchInput.addEventListener('input', debounce(filterAndRender, 300));
            
            // 頁面載入後，顯示所有資料
            filterAndRender();
        })
        .catch(error => {
            container.innerHTML = `<div class="no-results" style="color:red;">${error.message}</div>`;
            console.error('讀取資料時發生錯誤:', error);
        });

    // ▼▼▼ 您原本的所有 helper functions (generateResearchCards, generateListHtml, addAccordionLogic) 也要一併複製到這裡 ▼▼▼
    // 【重要修改】generateResearchCards 現在只在初始時被呼叫一次
    function generateResearchCards(researches) {
        container.innerHTML = ''; // 清空容器，準備生成

        if (researches.length === 0) {
            container.innerHTML = '<div class="no-results">找不到符合條件的調查 😅 <br>試試看別的關鍵字吧！</div>';
            return;
        }

        const fragment = document.createDocumentFragment(); // 使用文檔碎片提高效能

        researches.forEach((research, index) => {
            const card = document.createElement('div');
            card.className = 'research-card';
            card.dataset.index = index; // 【關鍵】將原始資料的索引存起來，方便之後回溯

            const stepsHtml = research.steps.map(step => {
                const tasksHtml = generateListHtml(step.tasks, 'task');
                const totalRewardsHtml = step.total_rewards && step.total_rewards.length > 0
                    ? `<div class="total-rewards-container">
                           <h4>🎉 完成階段總獎勵</h4>
                           <ul class="total-rewards-grid">${generateListHtml(step.total_rewards, 'total')}</ul>
                       </div>`
                    : '';

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
            
            fragment.appendChild(card);
        });

        // 加上一個固定的「無結果」提示元素，之後用JS控制其顯示/隱藏
        const noResultsDiv = document.createElement('div');
        noResultsDiv.className = 'no-results';
        noResultsDiv.textContent = '找不到符合條件的調查 😅 試試看別的關鍵字吧！';
        noResultsDiv.style.display = 'none'; // 預設隱藏
        fragment.appendChild(noResultsDiv);
        
        container.appendChild(fragment); // 一次性將所有元素加入DOM
        
        addAccordionLogic(); // 手風琴效果的監聽器也只需要設定一次
    }

    // generateListHtml 函式維持不變
    function generateListHtml(items, type) {
        // ... 此函式內容完全不變，請保留您原本的程式碼 ...
        const placeholderSrc = "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=";

        return items.map(item => {
            let description, rewardText, imageUrls;

            if (type === 'task') {
                description = item.description;
                rewardText = item.reward.text;
                imageUrls = item.reward.image_urls || [];
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

            } else { 
                description = item.text;
                imageUrls = item.image_url ? [item.image_url] : [];
                const imagesHtml = imageUrls.map(url => `<img src="${placeholderSrc}" data-src="${url}" alt="reward" class="reward-icon lazy-load">`).join('');

                return `
                    <li class="total-reward-item">
                        ${imagesHtml}
                        <span class="total-reward-text">${description}</span>
                    </li>`;
            }
        }).join('');
    }

    // addAccordionLogic 函式維持不變
    function addAccordionLogic() {
        // ... 此函式內容完全不變，請保留您原本的程式碼 ...
        const titles = document.querySelectorAll('.research-title');

        titles.forEach(title => {
            title.addEventListener('click', () => {
                const isActive = title.classList.contains('active');
                title.classList.toggle('active', !isActive);
                const content = title.nextElementSibling;

                if (!isActive) {
                    content.classList.add('show');
                    content.style.maxHeight = content.scrollHeight + 50 + "px";

                    const imagesToLoad = content.querySelectorAll('img.lazy-load');
                    imagesToLoad.forEach(img => {
                        img.src = img.dataset.src;
                        img.classList.remove('lazy-load');
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