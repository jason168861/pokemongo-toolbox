export function initializeRaidsApp() {
    // 透過檢查第一個容器來防止重複初始化
    const checkContainer = document.getElementById('raid-tier-1');
    if (!checkContainer || checkContainer.innerHTML !== '') return;

    fetch('data/raids.json')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => { // ✨ 1. 將變數名稱改為 data
            // ✨ 2. 讀取更新日期並更新 HTML
            const lastUpdatedDate = data.lastUpdated;
            const dateElement = document.querySelector('#raids-app .page-date');
            if (dateElement) {
                dateElement.textContent = `最後更新：${lastUpdatedDate}`;
            }

            // ✨ 3. 從 data.bosses 取得頭目列表
            const raidBosses = data.bosses;

            // 處理每個頭目
            raidBosses.forEach(boss => {
                // 將 Tier 字串轉換為對應的容器 ID (例如 "Tier 1" -> "raid-tier-1", "Mega" -> "raid-mega")
                const containerId = `raid-${boss.tier.toLowerCase().replace(' ', '-')}`;
                const container = document.getElementById(containerId);

                if (container) {
                    const card = document.createElement('div');
                    card.className = 'raid-card';

                    // 如果可以成為異色，則顯示異色圖示
                    const shinyIconHtml = boss.canBeShiny ? `<img class="shiny-icon" src="https://leekduck.com/assets/img/icons/shiny-icon.png" alt="可為異色"/>` : '';

                    // 產生屬性圖示的 HTML
                    const typesHtml = boss.types.map(type =>
                        `<img src="${type.image}" alt="${type.name}" class="type-icon">`
                    ).join('');

                    // 產生天氣加成圖示的 HTML
                    const weatherHtml = boss.boostedWeather.map(weather =>
                        `<img src="${weather.image}" alt="${weather.name}" class="weather-icon">`
                    ).join('');
                    
                    // 組合完整的卡片 HTML
                    card.innerHTML = `
                        <div class="raid-card-header">
                            <div class="raid-pokemon-image-wrapper tier-${boss.tier.replace('Tier ', '')}">
                                <img src="${boss.image}" alt="${boss.name}" class="raid-pokemon-image" loading="lazy">
                            </div>
                            ${shinyIconHtml}
                        </div>
                        <div class="raid-card-body">
                            <h3 class="pokemon-name">${boss.name}</h3>
                            <div class="pokemon-types">${typesHtml}</div>
                            <div class="combat-power-section">
                                <div class="cp-info">
                                    <span>CP</span>
                                    <p>${boss.combatPower.normal.min} - ${boss.combatPower.normal.max}</p>
                                </div>
                                <div class="cp-info boosted">
                                    <span>
                                        <span class="weather-boost-arrow"></span>
                                        CP
                                    </span>
                                    <p>${boss.combatPower.boosted.min} - ${boss.combatPower.boosted.max}</p>
                                </div>
                            </div>
                            <div class="boosted-weather-section">
                                <strong>天氣加成:</strong>
                                <div class="weather-icons-wrapper">${weatherHtml}</div>
                            </div>
                        </div>
                    `;
                    container.appendChild(card);
                }
            });
        })
        .catch(error => {
            console.error('讀取 raids.json 時發生錯誤:', error);
            // 發生錯誤時，也可以更新 UI 提示使用者
            const dateElement = document.querySelector('#raids-app .page-date');
            if (dateElement) {
                dateElement.textContent = `資料載入失敗`;
            }
        });
}