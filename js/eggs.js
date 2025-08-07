export function initializeEggsApp() {
    // 檢查第一個容器，防止重複初始化
    const checkContainer = document.getElementById('egg-list-2km');
    if (!checkContainer || checkContainer.innerHTML !== '') return;

    fetch('data/eggs.json')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => { // ✨ 1. 將變數名稱改為 data
            // ✨ 2. 讀取更新日期並更新 HTML
            const lastUpdatedDate = data.lastUpdated;
            const dateElement = document.querySelector('#eggs-app .page-date');
            if (dateElement) {
                dateElement.textContent = `最後更新：${lastUpdatedDate}`;
            }

            // ✨ 3. 從 data.pokemon 取得寶可夢列表
            const allPokemon = data.pokemon; 
            allPokemon.forEach(pokemon => {
                let containerId = `egg-list-${pokemon.eggDistance}km`;
                
                if (pokemon.source === 'adventure_sync') {
                    containerId += '-sync';
                } else if (pokemon.source === 'route_gift') {
                    containerId += '-route';
                }
                
                const container = document.getElementById(containerId);

                if (!container) {
                    console.warn(`找不到 ID 為 ${containerId} 的容器，跳過寶可夢: ${pokemon.name}`);
                    return;
                }
                
                const listItem = document.createElement('li');
                listItem.className = 'egg-list-item';
                
                const shinyIconHtml = pokemon.isShiny ? `<img class="shiny-icon" src="https://leekduck.com/assets/img/icons/shiny-icon.png" alt="shiny"/>` : '';
                
                listItem.innerHTML = `
                    <div class="egg-list-img egg${pokemon.eggDistance}km">
                        <img src="${pokemon.imageUrl}" alt="${pokemon.name}" loading="lazy"/>
                    </div>
                    ${shinyIconHtml}
                    <span class="hatch-pkmn">${pokemon.name}</span><br/>
                    <div class="font-size-smaller">
                        <span class="font-size-x-small">CP </span>${pokemon.cpRange || 'N/A'}
                    </div>`;
                container.appendChild(listItem);
            });
        })
        .catch(error => {
            console.error('Error loading eggs.json:', error);
            // 發生錯誤時，也可以更新 UI 提示使用者
            const dateElement = document.querySelector('#eggs-app .page-date');
            if (dateElement) {
                dateElement.textContent = `資料載入失敗`;
            }
        });
}