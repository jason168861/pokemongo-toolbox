export function initializeSpecialResearchApp() {
    let allResearches = []; 
    // 【修改】使用新的 ID
    const container = document.getElementById('special-research-container');
    const searchInput = document.getElementById('special-search-input');

    // 這邊的 fetch 和後續所有函式 (generateResearchCards, etc.) 都從您的新檔案複製過來
    fetch('data/special_research.json')
        .then(response => {
            if (!response.ok) {
                throw new Error('無法載入 JSON 檔案，請確認檔案名稱和路徑是否正確。');
            }
            return response.json();
        })
        .then(data => {
            allResearches = data.sort((a, b) => new Date(b.release_date) - new Date(a.release_date));
            generateResearchCards(allResearches);

            searchInput.addEventListener('input', (event) => {
                const searchTerm = event.target.value.toLowerCase().trim();
                const filteredResearches = allResearches.filter(research => 
                    research.title.toLowerCase().includes(searchTerm)
                );
                generateResearchCards(filteredResearches);
            });
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
return items.map(item => {
                let description, rewardText, imageUrls;

                if (type === 'task') {
                    description = item.description;
                    rewardText = item.reward.text;
                    imageUrls = item.reward.image_urls || [];
                    const imagesHtml = imageUrls.map(url => `<img src="${url}" alt="reward" class="reward-icon">`).join('');
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
                    const imagesHtml = imageUrls.map(url => `<img src="${url}" alt="reward" class="reward-icon">`).join('');
                    
                    // 產生給網格佈局使用的 HTML
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
                    } else {
                        content.style.maxHeight = null;
                        content.classList.remove('show');
                    }
                });
            });
    }
}