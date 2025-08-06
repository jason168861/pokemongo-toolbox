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
        .then(allPokemon => {
            allPokemon.forEach(pokemon => {
                // --- 【修改點】動態決定容器 ID ---
                let containerId = `egg-list-${pokemon.eggDistance}km`;
                
                if (pokemon.source === 'adventure_sync') {
                    containerId += '-sync';
                } else if (pokemon.source === 'route_gift') {
                    containerId += '-route';
                }
                
                const container = document.getElementById(containerId);
                // --- 修改結束 ---

                if (!container) {
                    console.warn(`找不到 ID 為 ${containerId} 的容器，跳過寶可夢: ${pokemon.name}`);
                    return; // 如果找不到對應的容器，就跳過此寶可夢
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
        .catch(error => console.error('Error loading data.json:', error));
}
