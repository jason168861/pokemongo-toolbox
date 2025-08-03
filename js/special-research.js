// js/special-research.js (優化後版本)

export function initializeSpecialResearchApp() {
    let allResearches = [];
    const container = document.getElementById('special-research-container');
    const searchInput = document.getElementById('special-search-input');
    const includeAllCheckbox = document.getElementById('search-include-all');
    const clearBtn = document.querySelector('#special-research-app .clear-search-btn');

    // Debounce 函式保持不變
    function debounce(func, delay) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), delay);
        };
    }

    // 搜尋與過濾邏輯保持不變
    function filterAndRender() {
        const searchTerm = searchInput.value.toLowerCase().trim();
        const searchInside = includeAllCheckbox.checked;
        let hasResults = false;
        const allCards = container.querySelectorAll('.research-card');

        allCards.forEach(card => {
            const research = allResearches[card.dataset.index];
            let isMatch = false;

            if (!searchTerm) {
                isMatch = true;
            } else {
                const lowerCaseTitle = research.title.toLowerCase();
                if (lowerCaseTitle.includes(searchTerm)) {
                    isMatch = true;
                } else if (searchInside) {
                    isMatch = research.steps.some(step => 
                        step.tasks.some(task =>
                            task.description.toLowerCase().includes(searchTerm) ||
                            (task.reward.text && task.reward.text.toLowerCase().includes(searchTerm))
                        ) || (step.total_rewards && step.total_rewards.some(reward =>
                            reward.text && reward.text.toLowerCase().includes(searchTerm)
                        ))
                    );
                }
            }
            
            card.style.display = isMatch ? 'block' : 'none';
            if (isMatch) hasResults = true;
        });

        const noResultsMessage = container.querySelector('.no-results');
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
            card.dataset.index = index; // 儲存資料索引，非常重要！

            // 只產生標題和一個空的內容容器
            card.innerHTML = `
                <div class="research-title">
                    <div class="research-title-block">
                        <span class="research-title-text">${research.title}</span>
                        <span class="research-date">發布日期: ${research.release_date || 'N/A'}</span>
                    </div>
                    <span class="icon">+</span>
                </div>
                <div class="research-content">
                    </div>
            `;
            fragment.appendChild(card);
        });

        const noResultsDiv = document.createElement('div');
        noResultsDiv.className = 'no-results';
        noResultsDiv.textContent = '找不到符合條件的調查 😅 試試看別的關鍵字吧！';
        noResultsDiv.style.display = 'none';
        fragment.appendChild(noResultsDiv);
        
        container.appendChild(fragment);
        addAccordionLogic(); // 綁定點擊事件
    }

    // ================================================================
    // 【優化核心】 2. 新增 generateDetailsHtml 函式
    // 這個函式負責產生「單一」調查的詳細內容 HTML。
    // ================================================================
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
                    <h3>${step.step_title}</h3>
                    <ul>${tasksHtml}</ul>
                    ${totalRewardsHtml}
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
    function addAccordionLogic() {
        const titles = document.querySelectorAll('#special-research-app .research-title');

        titles.forEach(title => {
            title.addEventListener('click', () => {
                const card = title.closest('.research-card');
                const content = card.querySelector('.research-content');

                // 檢查是否為第一次點擊 (如果內容尚未被渲染)
                if (!card.dataset.detailsRendered) {
                    const researchIndex = parseInt(card.dataset.index, 10);
                    const researchData = allResearches[researchIndex];
                    
                    // 產生詳細內容的 HTML 並填入
                    content.innerHTML = generateDetailsHtml(researchData);
                    
                    // 標記為已渲染，避免重複產生
                    card.dataset.detailsRendered = 'true';
                }

                // --- 以下是原本的展開/收合邏輯 ---
                const isActive = title.classList.contains('active');
                title.classList.toggle('active', !isActive);
                
                if (!isActive) {
                    content.classList.add('show');
                    content.style.maxHeight = content.scrollHeight + 50 + "px";

                    // 觸發圖片懶加載
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
                }
            });
        });
    }

    // Fetch 資料的主流程保持不變
    fetch('data/special_research.json')
        .then(response => {
            if (!response.ok) throw new Error('無法載入 JSON 檔案');
            return response.json();
        })
        .then(data => {
            allResearches = data.sort((a, b) => new Date(b.release_date) - new Date(a.release_date));
            generateResearchCards(allResearches);
            includeAllCheckbox.addEventListener('change', debounce(filterAndRender, 200));
            searchInput.addEventListener('input', debounce(filterAndRender, 300));
            searchInput.addEventListener('input', () => {
                // 如果 input 內有值，就顯示按鈕；否則隱藏
                clearBtn.style.display = searchInput.value ? 'block' : 'none';
            });
            
            // 【新增】叉叉按鈕的點擊事件
            clearBtn.addEventListener('click', () => {
                // 1. 清空搜尋框
                searchInput.value = '';
            
                // 2. 隱藏叉叉按鈕
                clearBtn.style.display = 'none';
            
                // 3. 觸發一次搜尋，讓列表恢復原狀
                filterAndRender();
            
                // 4. (可選) 讓使用者可以繼續輸入
                searchInput.focus();
            });
        })
        .catch(error => {
            container.innerHTML = `<div class="no-results" style="color:red;">${error.message}</div>`;
            console.error('讀取資料時發生錯誤:', error);
        });
}