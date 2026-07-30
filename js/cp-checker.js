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

    // ---- 站內連結 --------------------------------------------------------
    // Search Console 對每個 ?mon= 網址都報「參照網頁：未偵測到任何參照網頁」。
    // 1079 個網址只出現在 sitemap、站內沒有任何 <a> 指過去,Google 的檢索與
    // 重新評估優先度都會很低（尤其這些頁彼此還有四成內容重複）。
    // 下面讓卡片標題和「相關寶可夢」都變成真正的 <a href>,同時攔截點擊,
    // 使用者體驗維持原本的即時篩選、不整頁重載。
    // sitemap 是用 Python 的 quote() 產生的，會把 !'()* 也編碼成 %XX，
    // 但 encodeURIComponent 會原樣保留它們。有 100 多個形態名帶括號，
    // 不統一的話「sitemap 裡的網址」和「站內連結／canonical」會長得不一樣。
    const monParam = n => encodeURIComponent(n)
        .replace(/[!'()*]/g, c => '%' + c.charCodeAt(0).toString(16).toUpperCase());
    const monHref = n => location.pathname + '?tab=cp-checker-app&mon=' + monParam(n);
    const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const monLink = n => `<a class="mon-link" href="${monHref(n)}">${esc(n)}</a>`;

    const MON_NAMES = new Set(allPokemonData.map(p => p.name));   // 只連到真的有頁面的名字
    const BY_DEX = new Map();          // 圖鑑編號 → 該編號底下的名稱（含各地區形態）
    allPokemonData.forEach(p => {
        if (!BY_DEX.has(p.id)) BY_DEX.set(p.id, []);
        BY_DEX.get(p.id).push(p.name);
    });
    const MAX_DEX = Math.max(...BY_DEX.keys());

    // POKEDEX 來自 data/pokemon_data_and_rankings.js,有 family.id / family.stage,
    // 是現成的進化鏈資料。它是 defer 載入且排在 main.js 之前,所以這裡讀得到；
    // 萬一讀不到就只降級成「圖鑑相鄰」,不會壞掉。
    const FAMILY = (() => {
        if (typeof POKEDEX === 'undefined' || !Array.isArray(POKEDEX)) return null;
        const of = new Map(), members = new Map();
        POKEDEX.forEach(d => {
            const fid = d.family && d.family.id;
            if (!fid || !d.name) return;
            if (!of.has(d.name)) of.set(d.name, fid);
            if (!members.has(fid)) members.set(fid, []);
            members.get(fid).push({ name: d.name, stage: d.family.stage || 0, dex: d.dexNumber || 0 });
        });
        return { of, members };
    })();

    function relatedHtml(p) {
        const parts = [];

        // 1) 同編號的其他形態（阿羅拉／伽勒爾／闇黑…）
        const forms = (BY_DEX.get(p.id) || []).filter(n => n !== p.name);
        if (forms.length) {
            parts.push(`<p><strong>${esc(p.name)} 的其他形態：</strong>${forms.map(monLink).join('、')}</p>`);
        }

        // 2) 進化家族。POKEDEX 的家族成員有些沒有 CP 頁面（造型皮卡丘、Mega 等）,
        //    先過濾掉才不會連到不存在的網址。自己這一隻保留但不做成連結。
        if (FAMILY) {
            const fid = FAMILY.of.get(p.name);
            const seen = new Set();
            const chain = (fid ? FAMILY.members.get(fid) || [] : [])
                .filter(m => (m.name === p.name || MON_NAMES.has(m.name))
                          && !seen.has(m.name) && seen.add(m.name))
                .sort((a, b) => a.stage - b.stage || a.dex - b.dex);
            if (chain.length > 1) {
                parts.push(`<p><strong>${esc(p.name)} 的進化家族：</strong>`
                    + chain.map(m => m.name === p.name
                        ? `<strong class="mon-cur">${esc(m.name)}</strong>` : monLink(m.name)).join(' → ')
                    + '</p>');
            }
        }

        // 3) 圖鑑編號相鄰。這條讓 1079 個網址串成一條完整的鏈——Google 只要爬到
        //    其中任何一頁,就能沿著前後一路走完全部,不必依賴 sitemap。
        const nb = [];
        for (let d = p.id - 1; d >= 1; d--) { const a = BY_DEX.get(d); if (a) { nb.push('上一隻 #' + d + ' ' + monLink(a[0])); break; } }
        for (let d = p.id + 1; d <= MAX_DEX; d++) { const a = BY_DEX.get(d); if (a) { nb.push('下一隻 #' + d + ' ' + monLink(a[0])); break; } }
        if (nb.length) parts.push(`<p><strong>圖鑑相鄰：</strong>${nb.join('　·　')}</p>`);

        if (!parts.length) return '';
        return `<nav class="mon-related" aria-label="相關寶可夢">
                  <h2>與 ${esc(p.name)} 相關的寶可夢</h2>${parts.join('')}
                </nav>`;
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
            </p>
            ${relatedHtml(p)}`;
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
            // 不能直接把 u 交給 replaceState。URLSearchParams 是用
            // application/x-www-form-urlencoded 序列化的，空白會變成 '+'，
            // 但 sitemap 和 canonical 用的是 %20。93 個帶空白的形態名
            // （「椰蛋樹 (阿羅拉形態)」之類）會因此在載入時被改寫網址，
            // Googlebot 看到請求網址 ≠ 渲染後網址 → 判定「頁面會重新導向」。
            // 所以自己組 query string，用跟 canonical 同一套編碼。
            const qs = Array.from(u.searchParams)
                .map(([k, v]) => monParam(k) + '=' + monParam(v)).join('&');
            history.replaceState(history.state, '', u.pathname + (qs ? '?' + qs : '') + u.hash);
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
                location.origin + monHref(q));   // 用同一個編碼規則，才跟 sitemap 完全一致
            if (h1) h1.textContent = name + ' IV100 CP 查詢';
        } else {
            if (h1) h1.textContent = 'IV100 CP 查詢';
            // 清空 → 還原通用 SEO
            document.title = CP_SEO_DEFAULT.title;
            if (descTag) descTag.setAttribute('content', CP_SEO_DEFAULT.desc);
            if (canonical) canonical.setAttribute('href', location.origin + location.pathname + '?tab=cp-checker-app');
        }
    }

    // ---- 卡片清單：深連結時只放需要的那幾張 --------------------------------
    // 原本不管什麼網址都把 1079 張卡片全部塞進 DOM，只用 display:none 藏起來。
    // 但 Google 判定重複看的是「轉譯後的 HTML」，隱藏元素照樣算進去——量過
    // ?mon= 頁面有 99.1% 的 HTML（93 萬字元）跟其他 1078 頁一模一樣，只有
    // 0.89% 是自己的。轟擂金剛猩那頁就是這樣被 Google 覆寫 canonical、
    // 判成「重複網頁」的。
    //
    // 所以：進來時網址帶 ?mon= 就只建立符合的那幾張卡片（Googlebot 不會打字，
    // 看到的就是這個精簡版）；使用者一碰搜尋框才把全部補上。
    // ?tab=cp-checker-app（沒有 mon）仍然建立全部 1079 張 —— 那頁是站內連結
    // 的樞紐，1079 個 <a> 要留在那裡。
    let builtAll = false;

    function matchesQuery(p, query) {
        if (!query) return true;
        return !isNaN(query) ? String(p.id) === query
                             : (p.name.toLowerCase().includes(query)
                                || (p.alt || '').toLowerCase().includes(query));
    }

    function buildCards(indices) {
        const fragment = document.createDocumentFragment();
        indices.forEach(i => {
            const pokemon = allPokemonData[i];
            const pokemonCard = document.createElement('div');
            pokemonCard.className = 'pokemon-card';
            pokemonCard.dataset.name = pokemon.name.toLowerCase();
            pokemonCard.dataset.alt = (pokemon.alt || '').toLowerCase();   // 改名前的舊名（?mon= 舊連結用）
            pokemonCard.dataset.id = pokemon.id;
            pokemonCard.dataset.idx = i;   // 對回 allPokemonData（同 dex 的地區形態 id 會重複，不能用 id 反查）
            pokemonCard.innerHTML = `
                <img src="${pokemon.imageUrl}" alt="${pokemon.name}" loading="lazy">
                <div class="pokemon-info">
                    <h2><a class="mon-link" href="${monHref(pokemon.name)}">${esc(pokemon.name)}</a></h2>
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

    // 使用者要自己搜尋了 → 把剩下的卡片補齊。只做一次。
    function ensureAllCards() {
        if (builtAll) return;
        builtAll = true;
        resultsContainer.textContent = '';
        buildCards(allPokemonData.map((_, i) => i));
    }

    // 只建立符合這個查詢的卡片（深連結進來、或點站內連結時用）
    function showOnly(query) {
        const q = (query || '').trim().toLowerCase();
        resultsContainer.textContent = '';
        buildCards(allPokemonData.reduce((acc, p, i) => {
            if (matchesQuery(p, q)) acc.push(i);
            return acc;
        }, []));
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
    // focus 就先把卡片補齊：使用者打第一個字之前就備好，感覺不到延遲
    searchInput.addEventListener('focus', ensureAllCards);
    searchInput.addEventListener('input', () => {
        ensureAllCards();   // 深連結進來時 DOM 裡只有幾張卡，要先補齊才能搜尋
        const query = searchInput.value.trim().toLowerCase();
        filterResults(query);
        // 根據輸入框是否有值來顯示/隱藏按鈕
        clearBtn.style.display = searchInput.value ? 'block' : 'none';
        syncMonUrlSeo(searchInput.value);   // 網址列/標題隨查詢更新
    });

    clearBtn.addEventListener('click', () => {
        searchInput.value = '';
        ensureAllCards();
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
    // 網址帶 ?mon= → 只建立那幾張卡（Googlebot 看到的就是這個精簡版）；
    // 沒帶 → 建立全部 1079 張，這頁是站內連結的樞紐。
    if (CP_INITIAL_MON) showOnly(CP_INITIAL_MON); else ensureAllCards();

    // 站內連結（卡片標題、相關寶可夢）點下去：走原本的即時篩選，不整頁重載。
    // href 仍然是真的網址，所以 Google 照樣把它當連結、使用者也能用中鍵開新分頁。
    function onMonLinkClick(event) {
        if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        const a = event.target.closest && event.target.closest('a.mon-link');
        if (!a) return;
        const raw = (a.getAttribute('href') || '').split('mon=')[1];
        if (!raw) return;
        event.preventDefault();
        const name = decodeURIComponent(raw);
        searchInput.value = name;
        // 還沒展開全部時就只換成目標那幾張卡，維持精簡的 DOM；
        // 展開過了就照原本的篩選走。
        if (!builtAll) showOnly(name);
        filterResults(name.trim().toLowerCase());
        clearBtn.style.display = 'block';
        syncMonUrlSeo(name);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    resultsContainer.addEventListener('click', onMonLinkClick);
    const cpLevelTableBox = document.getElementById('cpLevelTable');
    if (cpLevelTableBox) cpLevelTableBox.addEventListener('click', onMonLinkClick);

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
