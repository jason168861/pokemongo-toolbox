// 進頁時就抓住 ?mon= 深連結參數（main.js 稍後會把網址改回 ?tab=cp-checker-app，會清掉它）
const CP_INITIAL_MON = new URLSearchParams(location.search).get('mon');
// 清空搜尋時用的通用 SEO（與 main.js 的 TAB_SEO['cp-checker-app'] 一致）
const CP_SEO_DEFAULT = {
    title: 'IV100 CP 查詢表：15、20、25 等滿 IV CP 速查｜Pokémon Go 工具箱',
    desc: '輸入寶可夢名稱或編號，立即查出 IV 100% 在 15、20、25 等的 CP 數值，快速判斷團體戰捕捉與研究獎勵是否值得。'
};

export function initializeCpChecker() {
    const searchInput = document.getElementById('cpSearchInput');
    const resultsContainer = document.getElementById('resultsContainer');
    const statusMessage = document.getElementById('statusMessage');
    const clearBtn = document.querySelector('#cp-checker-app .clear-search-btn');
    if (!searchInput) return; // 如果元素不存在，直接返回

    const allPokemonData = POKEMON_CP_DATA;
    if (!allPokemonData || allPokemonData.length === 0) {
        statusMessage.textContent = "錯誤：寶可夢資料未載入。";
        statusMessage.style.color = 'red';
        return;
    }

    // 依查詢找出對應寶可夢（編號完全相符 > 名稱完全相符 > 名稱包含）
    function findMon(q) {
        if (!q) return null;
        const s = q.trim().toLowerCase();
        return allPokemonData.find(p => String(p.id) === s)
            || allPokemonData.find(p => p.name.toLowerCase() === s)
            || allPokemonData.find(p => p.name.toLowerCase().includes(s)) || null;
    }
    // 把目前查詢反映到網址列（可分享/可被收錄）並更新標題、描述、canonical
    function syncMonUrlSeo(query) {
        const q = (query || '').trim();
        try {
            const u = new URL(location.href);
            u.searchParams.set('tab', 'cp-checker-app');
            if (q) u.searchParams.set('mon', q); else u.searchParams.delete('mon');
            history.replaceState(history.state, '', u);
        } catch (e) {}
        const canonical = document.querySelector('link[rel="canonical"]');
        const descTag = document.querySelector('meta[name="description"]');
        if (q) {
            const mon = findMon(q);
            const name = mon ? mon.name : q;
            document.title = name + ' IV100 CP 速查（15／20／25 等）｜Pokémon Go 工具箱';
            if (descTag) descTag.setAttribute('content',
                name + ' 的 IV 100% CP 速查：查看 ' + name + ' 在 15、20、25 等的滿 IV CP 數值，快速判斷團體戰捕捉與研究獎勵是否值得。');
            if (canonical) canonical.setAttribute('href',
                location.origin + location.pathname + '?tab=cp-checker-app&mon=' + encodeURIComponent(q));
        } else {
            // 清空 → 還原通用 SEO
            document.title = CP_SEO_DEFAULT.title;
            if (descTag) descTag.setAttribute('content', CP_SEO_DEFAULT.desc);
            if (canonical) canonical.setAttribute('href', location.origin + location.pathname + '?tab=cp-checker-app');
        }
    }

    function createAllPokemonCards() {
        const fragment = document.createDocumentFragment();
        allPokemonData.forEach(pokemon => {
            const pokemonCard = document.createElement('div');
            pokemonCard.className = 'pokemon-card';
            pokemonCard.dataset.name = pokemon.name.toLowerCase();
            pokemonCard.dataset.id = pokemon.id;
            pokemonCard.innerHTML = `
                <img src="${pokemon.imageUrl}" alt="${pokemon.name}" loading="lazy">
                <div class="pokemon-info">
                    <h2>${pokemon.name}</h2>
                    <div class="id">#${pokemon.id}</div>
                    <div class="cp-container">
                        <div class="cp"><span>Lv15 100% </span>${pokemon.cp15}</div>
                        <div class="cp"><span>Lv20 100% </span>${pokemon.cp20}</div>
                        <div class="cp"><span>Lv25 100% </span>${pokemon.cp25}</div>
                    </div>
                </div>`;
            fragment.appendChild(pokemonCard);
        });
        resultsContainer.appendChild(fragment);
        statusMessage.textContent = `資料載入成功！共 ${allPokemonData.length} 筆資料。`;
    }

    function filterResults(query) {
        const allCards = resultsContainer.querySelectorAll('.pokemon-card');
        let foundMatch = false;
        allCards.forEach(card => {
            const pokemonName = card.dataset.name;
            const pokemonId = card.dataset.id;
            const isQueryNumeric = !isNaN(query);
            let isMatch = !query || (isQueryNumeric ? pokemonId===(query) : pokemonName.includes(query));
            card.style.display = isMatch ? 'flex' : 'none';
            if (isMatch) foundMatch = true;
        });
        if (!foundMatch && query) {
                statusMessage.textContent = "找不到符合條件的寶可夢。";
        } else {
                statusMessage.textContent = `資料載入成功！共 ${allPokemonData.length} 筆資料。`;
        }
    }
    searchInput.addEventListener('input', () => {
        const query = searchInput.value.trim().toLowerCase();
        filterResults(query);
        // 根據輸入框是否有值來顯示/隱藏按鈕
        clearBtn.style.display = searchInput.value ? 'block' : 'none';
        syncMonUrlSeo(searchInput.value);   // 網址列/標題隨查詢更新
    });

    clearBtn.addEventListener('click', () => {
        searchInput.value = '';
        filterResults(''); // 傳入空字串來顯示所有結果
        clearBtn.style.display = 'none';
        syncMonUrlSeo('');   // 清掉 ?mon= 並還原通用 SEO
        searchInput.focus();
    });
    searchInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            searchInput.blur();
        }
    });
    searchInput.addEventListener('input', (event) => {
        const query = event.target.value.trim().toLowerCase();
        filterResults(query);
    });
    createAllPokemonCards();

    // 深連結：有人開 ?tab=cp-checker-app&mon=皮卡丘 → 自動填入搜尋框並顯示結果
    if (CP_INITIAL_MON) {
        searchInput.value = CP_INITIAL_MON;
        filterResults(CP_INITIAL_MON.trim().toLowerCase());
        clearBtn.style.display = 'block';
        // 延後執行：main.js 會在 initializeCpChecker 之後才呼叫 applySeo（通用標題），
        // 用 setTimeout 讓「該寶可夢的 SEO」在其之後才設定，才不會被蓋掉。
        setTimeout(() => syncMonUrlSeo(CP_INITIAL_MON), 0);
    }
}
