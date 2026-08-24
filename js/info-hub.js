// js/info-hub.js
//
// 名單本身在 data/stardust_bonus.json —— 獨立的 /stardust/ 頁面
// （scripts/build_stardust_page.py）讀的是同一份，兩邊不要各留一份。
export async function initializeInfoHubApp() {
    const stardustContainer = document.getElementById('stardust-bonus-container');
    // 防止重複初始化
    if (!stardustContainer || stardustContainer.children.length > 0) {
        return;
    }

    let stardustPokemon;
    try {
        const res = await fetch('data/stardust_bonus.json');
        stardustPokemon = (await res.json()).pokemon;
    } catch (e) {
        stardustContainer.innerHTML = '<p>資料載入失敗，請稍後再試。</p>';
        return;
    }

    // 【修正】根據寶可夢 ID 和形態產生圖片 URL
    function getImageUrl(pokemon) {
        const baseUrl = 'https://cdn.jsdelivr.net/gh/PokeMiners/pogo_assets/Images/Pokemon%20-%20256x256/Addressable%20Assets/';
        let fileName = `pm${pokemon.dex}`;
        if (pokemon.form) {
            fileName += `.f${pokemon.form}`;
        }
        fileName += '.icon.png';
        // 【錯誤修正】確保回傳完整的 URL
        return baseUrl + fileName;
    }

    // 遍歷資料並建立卡片
    stardustPokemon.forEach(pokemon => {
        const card = document.createElement('div');
        card.className = 'stardust-card';

        const imageUrl = getImageUrl(pokemon);

        card.innerHTML = `
            <img src="${imageUrl}" alt="${pokemon.name}" loading="lazy">
            <div class="pokemon-name">${pokemon.name}</div>
            <div class="stardust-amount">${pokemon.stardust.toLocaleString()}</div>
        `;
        stardustContainer.appendChild(card);
    });
}