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

    // ---- 全等級 CP 表 ----------------------------------------------------
    // 每個 ?mon= 網址原本只有三個數字（Lv15/20/25）跟其他頁不同，1076 個網址有 94% 內容重複，
    // Google 會判成重複網頁而不收錄。這張表讓每一頁都有上百個屬於自己的數字。
    // CP = max(10, floor((atk+IV) × √(def+IV) × √(sta+IV) × CPM² / 10))
    const CPM = (typeof CP_MULTIPLIER !== 'undefined') ? CP_MULTIPLIER : null;
    const MAX_LEVEL = 50, BEST_BUDDY_LEVEL = 51;
    // 這三個等級的意義沿用頁面上方圖例的說法
    const KEY_LEVELS = {
        15: '🔬 田野調查 · 🤝 小隊合作',
        20: '⚔️ 團體戰（無天氣加成）· 🥚 孵化的蛋',
        25: '☀️ 團體戰（天氣加成）'
    };
    function cpAt(p, level, iv) {
        const m = CPM[level - 1];
        return Math.max(10, Math.floor((p.atk + iv) * Math.sqrt(p.def + iv) * Math.sqrt(p.sta + iv) * m * m / 10));
    }
    // 只在「編號或名稱完全相符」或「篩選後只剩一隻」時才出表，
    // 否則打一個字就跳出某一隻的完整表格會很怪。
    function resolveOne(query, visibleIdx) {
        const s = (query || '').trim().toLowerCase();
        if (s) {
            const hit = allPokemonData.find(p => String(p.id) === s)
                     || allPokemonData.find(p => p.name.toLowerCase() === s)
                     || allPokemonData.find(p => (p.alt || '').toLowerCase() === s);
            if (hit) return hit;
        }
        return visibleIdx.length === 1 ? allPokemonData[visibleIdx[0]] : null;
    }
    function renderLevelTable(p) {
        const box = document.getElementById('cpLevelTable');
        if (!box) return;
        if (!p || !CPM || p.atk === undefined) { box.innerHTML = ''; box.hidden = true; return; }
        let rows = '';
        for (let L = 1; L <= BEST_BUDDY_LEVEL; L++) {
            const note = L === BEST_BUDDY_LEVEL ? '⭐ 最佳夥伴加成' : (KEY_LEVELS[L] || '');
            rows += `<tr class="${KEY_LEVELS[L] ? 'key-lv' : ''}${L === BEST_BUDDY_LEVEL ? ' bb-lv' : ''}">`
                  + `<th scope="row">Lv${L}</th>`
                  + `<td class="cp-max">${cpAt(p, L, 15)}</td>`
                  + `<td class="cp-min">${cpAt(p, L, 0)}</td>`
                  + `<td class="lv-note">${note}</td></tr>`;
        }
        box.innerHTML = `
            <h2>${p.name} 全等級 CP 對照表（Lv1～Lv${MAX_LEVEL}）</h2>
            <p class="lv-table-intro">
                ${p.name}（#${p.id}）的基礎數值為 攻擊 ${p.atk}／防禦 ${p.def}／耐力 ${p.sta}。
                下表列出 ${p.name} 在每個等級的 CP：<strong>100% IV</strong>（15／15／15）是該等級的 CP 上限，
                <strong>0% IV</strong>（0／0／0）是下限。抓到的 ${p.name} 若 CP 剛好等於 100% 欄的數字，
                就代表牠是滿 IV；落在兩欄之間則可用來反推 IV 範圍。
            </p>
            <div class="lv-table-wrap">
              <table class="lv-table">
                <caption>${p.name} 各等級 CP（100% IV / 0% IV）</caption>
                <thead><tr><th scope="col">等級</th><th scope="col">100% IV</th><th scope="col">0% IV</th><th scope="col">說明</th></tr></thead>
                <tbody>${rows}</tbody>
              </table>
            </div>
            <p class="lv-table-foot">
                Lv${BEST_BUDDY_LEVEL} 為最佳夥伴狀態下的等級上限；一般強化上限為 Lv${MAX_LEVEL}。
                CP 由 ${p.name} 的基礎數值與各等級的 CP 倍率計算，資料來源為 Pokémon GO GAME_MASTER。
            </p>`;
        box.hidden = false;
    }

    // 依查詢找出對應寶可夢（編號完全相符 > 名稱完全相符 > 名稱包含）
    function findMon(q) {
        if (!q) return null;
        const s = q.trim().toLowerCase();
        return allPokemonData.find(p => String(p.id) === s)
            || allPokemonData.find(p => p.name.toLowerCase() === s)
            || allPokemonData.find(p => (p.alt || '').toLowerCase() === s)   // 改名前的舊 ?mon= 連結
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
        const h1 = document.querySelector('#cp-checker-app h1');   // h1 也要跟著換,否則整站 1076 個網址共用同一個標題
        if (q) {
            const mon = findMon(q);
            const name = mon ? mon.name : q;
            document.title = name + ' IV100 CP 速查｜Lv1-50 全等級 CP 表｜Pokémon Go 工具箱';
            if (descTag) descTag.setAttribute('content',
                name + ' 的 IV 100% CP 速查與 Lv1～50 全等級 CP 對照表：查看 ' + name
                + ' 在 15、20、25 等的滿 IV CP，以及每個等級的 CP 上下限（100% / 0% IV），快速判斷團體戰捕捉與研究獎勵是否值得。');
            if (canonical) canonical.setAttribute('href',
                location.origin + location.pathname + '?tab=cp-checker-app&mon=' + encodeURIComponent(q));
            if (h1) h1.textContent = name + ' IV100 CP 查詢';
        } else {
            if (h1) h1.textContent = 'IV100 CP 查詢';
            // 清空 → 還原通用 SEO
            document.title = CP_SEO_DEFAULT.title;
            if (descTag) descTag.setAttribute('content', CP_SEO_DEFAULT.desc);
            if (canonical) canonical.setAttribute('href', location.origin + location.pathname + '?tab=cp-checker-app');
        }
    }

    function createAllPokemonCards() {
        const fragment = document.createDocumentFragment();
        allPokemonData.forEach((pokemon, i) => {
            const pokemonCard = document.createElement('div');
            pokemonCard.className = 'pokemon-card';
            pokemonCard.dataset.name = pokemon.name.toLowerCase();
            pokemonCard.dataset.alt = (pokemon.alt || '').toLowerCase();   // 改名前的舊名（?mon= 舊連結用）
            pokemonCard.dataset.id = pokemon.id;
            pokemonCard.dataset.idx = i;   // 對回 allPokemonData（同 dex 的地區形態 id 會重複，不能用 id 反查）
            pokemonCard.innerHTML = `
                <img src="${pokemon.imageUrl}" alt="${pokemon.name}" loading="lazy">
                <div class="pokemon-info">
                    <h2>${pokemon.name}</h2>
                    <div class="id">#${pokemon.id}</div>
                    <div class="cp-container">
                        <div class="cp lv15"><span>Lv15 100% </span>${pokemon.cp15}</div>
                        <div class="cp lv20"><span>Lv20 100% </span>${pokemon.cp20}</div>
                        <div class="cp lv25"><span>Lv25 100% </span>${pokemon.cp25}</div>
                    </div>
                </div>`;
            fragment.appendChild(pokemonCard);
        });
        resultsContainer.appendChild(fragment);
        statusMessage.textContent = `資料載入成功！共 ${allPokemonData.length} 筆資料。`;
    }

    function filterResults(query) {
        const allCards = resultsContainer.querySelectorAll('.pokemon-card');
        const visibleIdx = [];
        allCards.forEach(card => {
            const pokemonName = card.dataset.name;
            const pokemonAlt = card.dataset.alt;
            const pokemonId = card.dataset.id;
            const isQueryNumeric = !isNaN(query);
            // 也比對舊名：名稱從英文改成中文之前的 ?mon= 連結（Flabebe、Farfetch'd…）還要能開
            let isMatch = !query || (isQueryNumeric ? pokemonId===(query)
                                                    : (pokemonName.includes(query) || (!!pokemonAlt && pokemonAlt.includes(query))));
            card.style.display = isMatch ? 'flex' : 'none';
            if (isMatch) visibleIdx.push(+card.dataset.idx);
        });
        if (!visibleIdx.length && query) {
                statusMessage.textContent = "找不到符合條件的寶可夢。";
        } else {
                statusMessage.textContent = `資料載入成功！共 ${allPokemonData.length} 筆資料。`;
        }
        // 鎖定到單一寶可夢時，補上牠的全等級 CP 表（這是每個 ?mon= 網址的主要獨立內容）
        renderLevelTable(resolveOne(query, visibleIdx));
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
