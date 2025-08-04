// js/info-hub.js
export function initializeInfoHubApp() {
    const stardustContainer = document.getElementById('stardust-bonus-container');
    // 防止重複初始化
    if (!stardustContainer || stardustContainer.children.length > 0) {
        return;
    }

    // 捕捉時可獲得較多星星沙子的寶可夢資料
    const stardustPokemon = [
        { name: '派拉斯', id: 46, stardust: 500, form: null },
        { name: '派拉斯特', id: 47, stardust: 700, form: null },
        { name: '喵喵', id: 52, stardust: 500, form: null },
        { name: '阿羅拉 喵喵', id: 52, stardust: 750, form: 'ALOLA' },
        { name: '貓老大', id: 53, stardust: 700, form: null },
        { name: '阿羅拉 貓老大', id: 53, stardust: 950, form: 'ALOLA' },
        { name: '大舌貝', id: 90, stardust: 1000, form: null },
        { name: '刺甲貝', id: 91, stardust: 1200, form: null },
        { name: '海星星', id: 120, stardust: 750, form: null },
        { name: '寶石海星', id: 121, stardust: 950, form: null },
        { name: '信使鳥', id: 225, stardust: 500, form: null },
        { name: '蘑蘑菇', id: 285, stardust: 500, form: null },
        { name: '斗笠菇', id: 286, stardust: 700, form: null },
        { name: '勾魂眼', id: 302, stardust: 750, form: null },
        { name: '風鈴鈴', id: 358, stardust: 1000, form: null },
        { name: '三蜜蜂', id: 415, stardust: 750, form: null },
        { name: '蜂女王', id: 416, stardust: 950, form: null },
        { name: '差不多娃娃', id: 531, stardust: 2100, form: null },
        { name: '破破袋', id: 568, stardust: 750, form: null },
        { name: '灰塵山', id: 569, stardust: 950, form: null },
        { name: '哎呀球菇', id: 590, stardust: 500, form: null },
        { name: '敗露球菇', id: 591, stardust: 700, form: null },
        { name: '睡睡菇', id: 755, stardust: 500, form: null },
        { name: '燈罩夜菇', id: 756, stardust: 700, form: null }
    ];

    // 【修正】根據寶可夢 ID 和形態產生圖片 URL
    function getImageUrl(pokemon) {
        const baseUrl = 'https://cdn.jsdelivr.net/gh/PokeMiners/pogo_assets/Images/Pokemon%20-%20256x256/Addressable%20Assets/';
        let fileName = `pm${pokemon.id}`;
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