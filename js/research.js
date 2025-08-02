export function initializeResearchApp() {
    const researchAppContainer = document.getElementById('research-app');
    // 防止重複初始化
    if (!researchAppContainer || researchAppContainer.dataset.initialized === 'true') {
        return;
    }

    const container = document.getElementById('research-container');
    const toggles = researchAppContainer.querySelectorAll('input[name="reward-toggle"]');

    function simpleHash(str) { let hash = 0; for (let i = 0; i < str.length; i++) { const char = str.charCodeAt(i); hash = (hash << 5) - hash + char; hash |= 0; } return Math.abs(hash); }
    function generateCategoryColors(categoryName) { const hash = simpleHash(categoryName); const hue = hash % 360; return { mainColor: `hsl(${hue}, 65%, 50%)`, lightColor: `hsl(${hue}, 80%, 94%)` }; }

    function createRewardBubble(reward) {
        const bubble = document.createElement('div');
        bubble.className = `reward-bubble ${reward.isFeatured ? 'featured' : ''}`;
        bubble.innerHTML = `
            <img src="${reward.imageUrl}" alt="${reward.name}">
            ${reward.isShiny ? `<img class="shiny-icon" src="https://leekduck.com/assets/img/icons/shiny-icon.png">` : ''}
            ${reward.quantity ? `<div class="quantity">${reward.quantity}</div>` : ''}
        `;
        return bubble;
    }

    function createRewardDetailRow(reward) {
        const row = document.createElement('div');
        row.className = `reward-detail-row ${reward.isFeatured ? 'featured' : ''}`;
        const hasPokemonIcon = reward.pokemonIconUrl;
        let rewardHTML = '';
        if (reward.type === 'encounter') {
            rewardHTML = `
                <div class="reward-bubble" >
                    <img src="${reward.imageUrl}" alt="${reward.name}">
                    ${reward.isShiny ? `<img class="shiny-icon" src="https://leekduck.com/assets/img/icons/shiny-icon.png">` : ''}
                </div>
                <div class="reward-details">
                    <span class="reward-name">${reward.name}</span>
                    <div class="cp-values">
                        <span class="max-cp"><div>Max CP</div>${reward.maxCp}</span>
                        <span class="min-cp"><div>Min CP</div>${reward.minCp}</span>
                    </div>
                </div>`;
        } else {
            rewardHTML = `
                <div class="reward-bubble" style="background-color: #e0f3ff;">
                    <img src="${reward.imageUrl}" alt="${reward.name}">
                    ${hasPokemonIcon ? `<div class="pokemon-on-energy"><img src="${reward.pokemonIconUrl}" alt=""></div>` : ''}
                </div>
                <div class="reward-details">
                    <span class="reward-name">${reward.name}</span>
                </div>`;
        }
        row.innerHTML = rewardHTML;
        return row;
    }

    function addAccordionListeners() {
        const allTaskHeaders = container.querySelectorAll('.task-header');
        allTaskHeaders.forEach(header => {
            header.addEventListener('click', () => {
                header.parentElement.classList.toggle('active');
            });
        });
    }

    function renderData(data) {
        const leftColumn = document.getElementById('left-column');
        const rightColumn = document.getElementById('right-column');
        if (!data || !data.length || !leftColumn || !rightColumn) return;
        leftColumn.innerHTML = '';
        rightColumn.innerHTML = '';
        data.forEach((category, index) => {
            const categoryDiv = document.createElement('div');
            categoryDiv.className = 'task-category';
            const { mainColor, lightColor } = generateCategoryColors(category.category);
            categoryDiv.style.setProperty('--category-main-color', mainColor);
            categoryDiv.style.setProperty('--category-bg-color', lightColor);
            const categoryTitle = document.createElement('h2');
            categoryTitle.textContent = category.category;
            categoryDiv.appendChild(categoryTitle);

            category.tasks.forEach(task => {
                if (task.rewards.length === 0) return;
                const taskItemDiv = document.createElement('div');
                taskItemDiv.className = 'task-item';
                if (!task.rewards.some(r => r.isFeatured)) {
                    taskItemDiv.classList.add('has-no-featured-rewards');
                }
                const taskHeader = document.createElement('div');
                taskHeader.className = 'task-header';
                taskHeader.innerHTML = `<span class="task-text">${task.description}</span>`;
                const rewardPreview = document.createElement('div');
                rewardPreview.className = 'reward-preview';
                task.rewards.forEach(reward => {
                    rewardPreview.appendChild(createRewardBubble(reward));
                });
                rewardPreview.innerHTML += '<span class="expand-arrow">▼</span>';
                taskHeader.appendChild(rewardPreview);
                
                const detailsContainer = document.createElement('div');
                detailsContainer.className = 'reward-details-container';
                const detailsContent = document.createElement('div');
                detailsContent.className = 'possible-rewards-content';
                task.rewards.forEach(reward => {
                    detailsContent.appendChild(createRewardDetailRow(reward));
                });
                detailsContainer.appendChild(detailsContent);

                taskItemDiv.appendChild(taskHeader);
                taskItemDiv.appendChild(detailsContainer);
                categoryDiv.appendChild(taskItemDiv);
            });

            if (index % 2 === 0) { leftColumn.appendChild(categoryDiv); } 
            else { rightColumn.appendChild(categoryDiv); }
        });
        addAccordionListeners();
    }
    
    function setupFilters() {
            toggles.forEach(toggle => {
                toggle.addEventListener('change', (event) => {
                    container.classList.toggle('hide-items', event.target.id === 'less-option');
                });
            });
            const initiallyChecked = researchAppContainer.querySelector('input[name="reward-toggle"]:checked');
            if (initiallyChecked) {
                container.classList.toggle('hide-items', initiallyChecked.id === 'less-option');
            }
    }

    fetch('data/research.json')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            renderData(data);
            setupFilters();
            researchAppContainer.dataset.initialized = 'true'; // 標記為已初始化
        })
        .catch(error => {
            console.error('載入田野調查資料時發生錯誤:', error);
            container.innerHTML = '<p style="text-align: center; color: red;">載入資料失敗，請檢查 `research.json` 檔案是否存在且格式正確。</p>';
        });
}
