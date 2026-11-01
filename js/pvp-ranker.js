// js/pvp-ranker.js

// 介面文字：中文頁直接用這裡的預設值；/<lang>/pvp-ranker/ 會在載入前設定 window.PVP_I18N 覆蓋
// （同時把 POKEDEX／排名資料裡的寶可夢、招式名稱換成該語言，見 scripts/build_pvp_i18n.py）
const T = Object.assign({
    loadErrLog: 'PvP Ranker: POKEDEX 或排名數據尚未載入。',
    loadErrHtml: '<h1>數據載入失敗</h1><p>請檢查 data/pokemon_data_and_rankings.js 是否存在且格式正確。</p>',
    evoOver: '進化後CP約為 {cp}，將超過限制',
    nowOver: '目前CP {cp} 已超過限制',
    over: '超過上限', unranked: '不在排名內',
    fast: '一般', charged: '特殊', yourRank: '您的排名',
    noRank: '您的IV組合不在此聯盟排名內。', topIv: '第一名 IV',
    defaultMon: '妙蛙種子'
}, (typeof window !== 'undefined' && window.PVP_I18N) || {});
const tf = (s, v) => s.replace(/\{(\w+)\}/g, (_, k) => v[k]);

export function initializePvpRanker() {
    // 防止重複初始化
    const container = document.getElementById('pvp-ranker-app');
    if (container.dataset.initialized) return;
    container.dataset.initialized = 'true';

    // 檢查必要的數據是否已載入
    if (typeof POKEDEX === 'undefined' || typeof POKEMON_RANKINGS_1500 === 'undefined') {
        console.error(T.loadErrLog);
        container.innerHTML = T.loadErrHtml;
        return;
    }

    // 條件面板的收合／拖曳（原本寫在首頁 index.html，拆頁後沒有帶過來）
    initControlsPanel();

    const pokemonInput = document.getElementById('pokemon-input');
    const searchResultsContainer = document.getElementById('search-results');
    const atkSelect = document.getElementById('atk-iv');
    const defSelect = document.getElementById('def-iv');
    const hpSelect = document.getElementById('hp-iv');
    const resultsContainer = document.getElementById('results-container');
    const clearBtn = document.getElementById('clear-btn');
    
    const currentLevelSlider = document.getElementById('current-level');
    const currentLevelValue = document.getElementById('current-level-value');
    const currentCpDisplay = document.getElementById('current-cp-display');
    
    // 【新增】獲取所有滑桿元素
    const ivSliders = document.querySelectorAll('.iv-slider');

    let selectedIndex = -1;

    const RANKINGS_DATA = {
        1500: POKEMON_RANKINGS_1500,
        2500: POKEMON_RANKINGS_2500,
        10000: POKEMON_RANKINGS_10000
    };

    function populateIVSelects() {
        const selects = [atkSelect, defSelect, hpSelect];
        selects.forEach(select => {
            select.innerHTML = ''; 
            for (let i = 0; i <= 15; i++) {
                const option = document.createElement('option');
                option.value = i;
                option.textContent = i;
                select.appendChild(option);
            }
        });
        // --- [修正] 確保預設IV值被設定 ---
        atkSelect.value = '0';
        defSelect.value = '15';
        hpSelect.value = '15';
    }

    // 【新增】更新滑桿視覺顯示的函式
    function updateSliderDisplay(ivType, value) {
        const progressBar = document.getElementById(`${ivType}-progress`);
        if (progressBar) {
            const percentage = (parseInt(value, 10) / 15) * 100;
            progressBar.style.width = `${percentage}%`;
        }
    }
    
    function updateCurrentCpDisplay() {
        const pokemonName = pokemonInput.value;
        const initialPokemon = POKEDEX.find(p => p.name.toLowerCase() === pokemonName.toLowerCase());

        if (!initialPokemon) {
            currentCpDisplay.textContent = '-';
            return;
        }

        const userIvs = {
            atk: parseInt(atkSelect.value, 10),
            def: parseInt(defSelect.value, 10),
            sta: parseInt(hpSelect.value, 10),
        };
        const currentLevel = parseFloat(currentLevelSlider.value);

        const totalAtk = initialPokemon.stats.atk + userIvs.atk;
        const totalDef = initialPokemon.stats.def + userIvs.def;
        const totalSta = initialPokemon.stats.sta + userIvs.sta;

        const currentCP = getCP(totalAtk, totalDef, totalSta, currentLevel);
        currentCpDisplay.textContent = currentCP;
    }


    function updateSearchSuggestions(pokemonList) {
        searchResultsContainer.innerHTML = '';
        selectedIndex = -1;

        pokemonList.forEach(pokemon => {
            const item = document.createElement('div');
            item.className = 'search-item';
            const imageUrl = POKEMON_IMAGES[pokemon.id] || ''; 
            
            item.innerHTML = `
                <img src="${imageUrl}" alt="${pokemon.name}" class="search-item-img">
                <span>#${pokemon.dexNumber} ${pokemon.name}</span>
            `;

            item.addEventListener('click', () => {
                pokemonInput.value = pokemon.name; 
                pokemonInput.dispatchEvent(new Event('input', { bubbles: true })); 
                searchResultsContainer.innerHTML = ''; 
                handleCalculate();
            });
            searchResultsContainer.appendChild(item);
        });
    }

    // ---- 即時排名摘要（只在手機顯示，CSS 控制）----
    // 手機上面板排在內容流中，調完 IV 後結果在面板下方、要往下捲才看得到。
    // 在面板底部固定放三格（超級／高級／大師）顯示「使用者選的那一隻」的排名，
    // 改 IV 時不用離開面板就看得到結果變化。進化型的結果仍看下方完整卡片。
    // 每格的狀態和結果卡片一致（generateLeagueCardHTML）：
    //   #名次 / 超過上限 / 不在排名內 / —（沒有排名資料，卡片也不會出現）
    // 結構寫死在 HTML（格數永遠不變，避免版面跳動），這裡只改 textContent。
    // 刻意不設 aria-live：拖滑桿時會連續播報。
    const quickSummary = document.getElementById('pvp-quick-summary');
    const QS_LEAGUES = [1500, 2500, 10000];   // 小小盃（500）沒有排名資料，不顯示
    let qsHasData = false;
    function setTextIfChanged(el, text) {
        if (!el || el.textContent === text) return false;
        el.textContent = text;
        return true;
    }
    // ranks：{1500: '#87', 2500: '超過上限', ...}；null = 空狀態
    function renderQuickSummary(ranks) {
        if (!quickSummary) return;
        const emptyEl = quickSummary.querySelector('.pvp-qs-empty');
        const cellsEl = quickSummary.querySelector('.pvp-qs-cells');
        const moreBtn = quickSummary.querySelector('.pvp-qs-more');
        const hasData = !!ranks;
        if (emptyEl && emptyEl.hidden !== hasData) emptyEl.hidden = hasData;
        if (cellsEl && cellsEl.hidden !== !hasData) cellsEl.hidden = !hasData;
        let changed = false;
        if (hasData && cellsEl) {
            QS_LEAGUES.forEach(cp => {
                const v = cellsEl.querySelector(`[data-cp="${cp}"] .pvp-qs-value`);
                if (setTextIfChanged(v, ranks[cp] || '—')) changed = true;
            });
        }
        // 「查看完整結果」：結果區沒東西時隱藏（用 visibility 保留高度，避免版面跳動）
        if (moreBtn) {
            const showMore = hasData && !resultsContainer.classList.contains('hidden')
                             && resultsContainer.childElementCount > 0;
            moreBtn.classList.toggle('is-invisible', !showMore);
            moreBtn.disabled = !showMore;
        }
        // 數字變了就閃一下底色（從空狀態第一次填入時不閃）；prefers-reduced-motion 時 CSS 不播
        if (changed && qsHasData) {
            quickSummary.classList.remove('is-updated');
            void quickSummary.offsetWidth;   // 重新觸發 animation
            quickSummary.classList.add('is-updated');
        }
        qsHasData = hasData;
    }
    if (quickSummary) {
        const moreBtn = quickSummary.querySelector('.pvp-qs-more');
        if (moreBtn) moreBtn.addEventListener('click', () => {
            // 不用 <a href="#...">：網址不加 hash；scroll-margin-top 讓結果頂端不貼著畫面邊緣
            resultsContainer.scrollIntoView({ block: 'start' });
        });
    }

    function handleCalculate() {
        updateCurrentCpDisplay();

        const pokemonName = pokemonInput.value;
        if (!pokemonName) { // 如果沒有寶可夢名稱，則不進行計算
            resultsContainer.innerHTML = '';
            resultsContainer.classList.add('hidden');
            renderQuickSummary(null);
            return;
        }

        const userIvs = {
            atk: parseInt(atkSelect.value, 10),
            def: parseInt(defSelect.value, 10),
            sta: parseInt(hpSelect.value, 10),
        };
        const currentLevel = parseFloat(currentLevelSlider.value);

        const initialPokemon = POKEDEX.find(p => p.name.toLowerCase() === pokemonName.toLowerCase());
        
        if (!initialPokemon) {
            resultsContainer.innerHTML = '';
            resultsContainer.classList.add('hidden');
            renderQuickSummary(null);
            return;
        }
        const quickRanks = {};   // 摘要用：只收使用者選的那一隻（非進化型）的結果

        const initialStage = initialPokemon.family.stage;
        const familyId = initialPokemon.family.id;
        const evolutionFamily = POKEDEX.filter(p => p.family.id === familyId);
        evolutionFamily.sort((a, b) => a.family.stage - b.family.stage); 
        const filteredFamily = evolutionFamily.filter(p => p.family.stage >= initialStage);

        resultsContainer.innerHTML = '';
        resultsContainer.classList.remove('hidden');

        filteredFamily.forEach(pokemon => {
            const familyResultContainer = document.createElement('div');
            familyResultContainer.className = 'pokemon-family-result';
            
            const imageUrl = POKEMON_IMAGES[pokemon.id] || '';
            familyResultContainer.innerHTML = `
                <h2>
                    <img src="${imageUrl}" alt="${pokemon.name}" class="pokemon-result-img">
                    ${pokemon.name}
                </h2>
            `;

            const leagueCardsContainer = document.createElement('div');
            leagueCardsContainer.className = 'league-cards-container';
            
            LEAGUES.forEach(league => {
                const leagueRankings = RANKINGS_DATA[league.cp];
                if (!leagueRankings) return;

                const rankingInfoFromDataFile = leagueRankings.find(p => p.name === pokemon.name);

                let isOverLimit = false;
                let warningText = ''; 
                const isEvolution = pokemon.id !== initialPokemon.id;

                if (isEvolution) {
                    const evolvedAtk = pokemon.stats.atk + userIvs.atk;
                    const evolvedDef = pokemon.stats.def + userIvs.def;
                    const evolvedSta = pokemon.stats.sta + userIvs.sta;
                    const evolvedCp = getCP(evolvedAtk, evolvedDef, evolvedSta, currentLevel);
                    
                    if (evolvedCp > league.cp && league.cp !== 10000) {
                        isOverLimit = true;
                        warningText = `<p class="over-limit-warning">${tf(T.evoOver, { cp: evolvedCp })}</p>`;
                    }
                } else {
                    const currentAtk = pokemon.stats.atk + userIvs.atk;
                    const currentDef = pokemon.stats.def + userIvs.def;
                    const currentSta = pokemon.stats.sta + userIvs.sta;
                    const currentCP = getCP(currentAtk, currentDef, currentSta, currentLevel);

                    if (currentCP > league.cp && league.cp !== 10000) { 
                        isOverLimit = true;
                        warningText = `<p class="over-limit-warning">${tf(T.nowOver, { cp: currentCP })}</p>`;
                    }
                }

                const allRankedSpreads = generateRankedSpreads(pokemon, 0, league.cp, 51, 1, 'product');
                if (allRankedSpreads.length === 0) return;

                const rankOneSpread = allRankedSpreads[0];
                const userPokemonRankInfo = allRankedSpreads.find(spread => 
                    spread.ivs.atk === userIvs.atk &&
                    spread.ivs.def === userIvs.def &&
                    spread.ivs.sta === userIvs.sta
                );
                // 摘要：判斷順序與 generateLeagueCardHTML 相同（超過上限 > 有排名 > 不在排名內）
                if (!isEvolution) {
                    quickRanks[league.cp] = isOverLimit ? T.over
                        : userPokemonRankInfo ? '#' + userPokemonRankInfo.rank
                        : T.unranked;
                }

                const leagueCardHTML = generateLeagueCardHTML(league, userPokemonRankInfo, rankOneSpread, isOverLimit, warningText, rankingInfoFromDataFile);
                leagueCardsContainer.innerHTML += leagueCardHTML;
            });

            if (leagueCardsContainer.innerHTML !== '') {
                familyResultContainer.appendChild(leagueCardsContainer);
                resultsContainer.appendChild(familyResultContainer);
            }
        });
        renderQuickSummary(quickRanks);   // 沒寫到的聯盟（allRankedSpreads 為空而提早 return）顯示「—」
    }

function generateLeagueCardHTML(league, userRankInfo, rankOneInfo, isOverLimit, warningText, rankingInfoFromDataFile) { 
        let movesetHTML = '';
        if (rankingInfoFromDataFile && !isOverLimit) {
            // 【修改開始】在這裡加入 Elite Move 的判斷邏輯
            
            // 判斷一般招式
            const fastMoveClass = rankingInfoFromDataFile.isEliteFast ? 'elite-move' : '';
            const fastMoveSymbol = rankingInfoFromDataFile.isEliteFast ? ' ✨' : '';

            // 判斷第一個特殊招式
            const cm1Class = rankingInfoFromDataFile.isEliteCharged1 ? 'elite-move' : '';
            const cm1Symbol = rankingInfoFromDataFile.isEliteCharged1 ? ' ✨' : '';

            // 判斷第二個特殊招式 (如果存在)
            let cm2HTML = '';
            if (rankingInfoFromDataFile.chargedMove2) {
                const cm2Class = rankingInfoFromDataFile.isEliteCharged2 ? 'elite-move' : '';
                const cm2Symbol = rankingInfoFromDataFile.isEliteCharged2 ? ' ✨' : '';
                cm2HTML = `<span class="move-name ${cm2Class}">${rankingInfoFromDataFile.chargedMove2}${cm2Symbol}</span>`;
            }

            movesetHTML = `
                <div class="moveset-details">
                    <div class="moveset-line">
                        <span class="move-type-label">${T.fast}</span>
                        <span class="move-name ${fastMoveClass}">${rankingInfoFromDataFile.fastMove}${fastMoveSymbol}</span>
                    </div>
                    <div class="moveset-line">
                        <span class="move-type-label">${T.charged}</span>
                        <div class="charged-move-list">
                            <span class="move-name ${cm1Class}">${rankingInfoFromDataFile.chargedMove1}${cm1Symbol}</span>
                            ${cm2HTML}
                        </div>
                    </div>
                </div>
            `;
            // 【修改結束】
        }
        
        let userResultHTML = '';
        if (isOverLimit) {
            userResultHTML = warningText;
        } else if (userRankInfo) {
            userResultHTML = `
                <div class="rank-details your-rank">
                    <p class="rank-line">
                        <span class="rank-label">${T.yourRank}</span>
                        <span class="rank">#${userRankInfo.rank}</span>
                    </p>
                    <p class="details-line">
                        <span>IV: ${userRankInfo.ivs.atk}/${userRankInfo.ivs.def}/${userRankInfo.ivs.sta}</span>
                        <span>Lvl ${userRankInfo.level}</span>
                    </p>
                    <p class="details-line">
                        <span class="cp">CP ${userRankInfo.cp}</span>
                    </p>
                </div>
            `;
        } else {
             userResultHTML = `
                <div class="rank-details your-rank">
                     <p class="no-rank">${T.noRank}</p>
                </div>
               `;
        }

        const rankOneResultHTML = rankOneInfo ? `
            <div class="rank-details rank-one">
                <p class="rank-line">
                    <span class="rank-label">${T.topIv}</span>
                    <span class="iv-details">${rankOneInfo.ivs.atk}/${rankOneInfo.ivs.def}/${rankOneInfo.ivs.sta}</span>
                </p>
            </div>
        ` : '';
        
    return `
        <div class="result-card ${isOverLimit ? 'dimmed' : ''}">
            <div class="card-content">
                <h2>
                    <img src="${league.icon}" class="league-icon-header" alt="${league.name}">
                    ${league.name}
                </h2>
                ${userResultHTML}
                ${movesetHTML}
                ${rankOneResultHTML}
            </div>
        </div>
    `;
    }
    
    // --- [修正] 還原原始的搜尋建議邏輯 ---
    function showSuggestions() {
        const query = zhLower(pokemonInput.value);   // 繁簡通用
        if (query.length < 1) {
            // 當輸入為空時，顯示所有寶可夢（或一個預設列表）
            updateSearchSuggestions(POKEDEX);
        } else {
            const matchedPokemons = POKEDEX.filter(p => 
                zhLower(p.name).includes(query) ||
                p.id.toLowerCase().includes(query) ||
                p.dexNumber.toString() === query ||
                (p.aliases && p.aliases.includes(query))
            ).slice(0, 1000); // 限制數量以提高性能
            updateSearchSuggestions(matchedPokemons);
        }
    }

    // --- 事件監聽器 ---

    currentLevelSlider.addEventListener('input', () => {
        currentLevelValue.textContent = currentLevelSlider.value;
        handleCalculate();
    });
    
    pokemonInput.addEventListener('input', () => {
        if (pokemonInput.value.length > 0) {
            clearBtn.classList.remove('hidden');
        } else {
            clearBtn.classList.add('hidden');
            resultsContainer.classList.add('hidden');
            currentCpDisplay.textContent = '-';
            renderQuickSummary(null);   // 清空輸入框不會呼叫 handleCalculate，這裡自己回到空狀態
        }
        showSuggestions(); 
    });
    
    clearBtn.addEventListener('click', () => {
        pokemonInput.value = '';
        pokemonInput.dispatchEvent(new Event('input', { bubbles: true })); 
        pokemonInput.focus();
    });

    pokemonInput.addEventListener('keydown', (e) => {
        const items = searchResultsContainer.querySelectorAll('.search-item');
        if (items.length === 0) return;

        // --- [修正] 確保鍵盤導航時樣式正確 ---
        items.forEach(item => item.classList.remove('selected'));
        
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            selectedIndex = (selectedIndex + 1) % items.length;
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            selectedIndex = (selectedIndex - 1 + items.length) % items.length;
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (selectedIndex > -1) {
                items[selectedIndex].click();
            } else if (items.length > 0) { // 如果沒有手動選擇，就選第一個
                items[0].click();
            }
        } else if (e.key === 'Escape') {
            searchResultsContainer.innerHTML = '';
        }

        if (selectedIndex > -1) {
            items[selectedIndex].classList.add('selected');
            items[selectedIndex].scrollIntoView({ block: 'nearest' });
        }
    });

    // --- [修正] 還原點擊輸入框時顯示建議列表的功能 ---
    pokemonInput.addEventListener('click', function() {
        showSuggestions();
    });

    pokemonInput.addEventListener('focus', function() {
        this.select();
        showSuggestions(); // 在 focus 時也顯示建議
    });

    // --- [修正] 還原 blur 事件，這是讓點擊選擇有效的關鍵 ---
    pokemonInput.addEventListener('blur', () => {
        // 延遲一點時間再隱藏，確保點擊事件可以被觸發
        setTimeout(() => {
            // 檢查當前焦點是否在搜尋項目上，如果不是才關閉
            if (!document.activeElement || !document.activeElement.classList.contains('search-item')) {
                 // searchResultsContainer.innerHTML = ''; // 這裡先不清空，讓使用者可以看到他選了什麼
            }
        }, 150);
    });

    // --- [修正] 點擊頁面其他地方時，關閉搜尋結果 ---
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-container')) {
            searchResultsContainer.innerHTML = '';
        }
    });
    
    // 【修改】為下拉選單加上監聽，使其能同步更新滑桿
    atkSelect.addEventListener('change', () => {
        handleCalculate();
        updateSliderDisplay('atk', atkSelect.value);
    });
    defSelect.addEventListener('change', () => {
        handleCalculate();
        updateSliderDisplay('def', defSelect.value);
    });
    hpSelect.addEventListener('change', () => {
        handleCalculate();
        updateSliderDisplay('hp', hpSelect.value);
    });

    // 【新增】為所有滑桿添加互動事件監聽
    ivSliders.forEach(slider => {
        const ivType = slider.dataset.iv;
        const correspondingSelect = document.getElementById(`${ivType}-iv`);
        let isDragging = false;

        // 依手指／滑鼠的 X 座標設定 IV。
        // 原本寫 (e.clientX || e.touches[0].clientX)：clientX 剛好是 0 時會被當成沒有值，
        // 滑鼠事件沒有 touches 就丟錯。現在滑鼠與觸控各自把座標傳進來。
        const setFromClientX = (clientX) => {
            const rect = slider.getBoundingClientRect();
            const x = clientX - rect.left;
            let percentage = x / rect.width;
            percentage = Math.max(0, Math.min(1, percentage)); // 確保比例在 0 和 1 之間
            const value = Math.round(percentage * 15);

            if (correspondingSelect.value != value) {
                correspondingSelect.value = value;
                // 手動觸發 change 事件，來執行 handleCalculate 和更新滑桿
                correspondingSelect.dispatchEvent(new Event('change'));
            }
        };
        // 滑鼠用（行為與原本相同）
        const handleInteraction = (e) => {
            e.preventDefault();
            setFromClientX(e.clientX);
        };

        // 滑鼠事件
        slider.addEventListener('mousedown', (e) => {
            isDragging = true;
            handleInteraction(e);
        });

        slider.addEventListener('mousemove', (e) => {
            if (isDragging) {
                handleInteraction(e);
            }
        });

        // 在整個視窗監聽 mouseup，避免滑鼠移出滑桿範圍時失效
        window.addEventListener('mouseup', () => {
            isDragging = false;
        });

        // ---- 觸控事件 ----
        // 原本 touchstart 就 preventDefault 並改值：手機上手指剛好從滑桿上開始往上下滑，
        // 頁面捲不動、IV 還被改掉。改成先判斷方向：
        //   水平先超過 8px（且大於垂直）→ 拖曳，之後才 preventDefault 並改值；
        //   垂直先超過 8px → 放棄，交給頁面捲動；
        //   都沒超過就放開 → 視為輕點，用放開的位置設值。
        // 手機 CSS 另有 .iv-slider{touch-action:pan-y}，讓瀏覽器不搶水平方向。
        const TOUCH_SLOP = 8;
        let touchStartX = 0, touchStartY = 0;
        let touchMode = null;   // null = 還沒判斷方向、'drag' = 拖曳中、'ignore' = 交給頁面
        slider.addEventListener('touchstart', (e) => {
            if (e.touches.length !== 1) { touchMode = 'ignore'; return; }   // 多指（縮放）不處理
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
            touchMode = null;
        }, { passive: true });

        slider.addEventListener('touchmove', (e) => {
            if (touchMode === 'ignore') return;
            const t = e.touches[0];
            if (!t) return;
            if (touchMode === null) {
                const adx = Math.abs(t.clientX - touchStartX);
                const ady = Math.abs(t.clientY - touchStartY);
                // 瀏覽器已經開始捲動時 touchmove 不可取消（cancelable=false），這時也只能放棄
                if (adx > TOUCH_SLOP && adx > ady && e.cancelable) {
                    touchMode = 'drag';
                } else if (ady > TOUCH_SLOP || adx > TOUCH_SLOP) {
                    touchMode = 'ignore';
                    return;
                } else {
                    return;   // 還在誤差範圍內，先不決定
                }
            }
            if (e.cancelable) e.preventDefault();
            setFromClientX(t.clientX);
        }, { passive: false });

        slider.addEventListener('touchend', (e) => {
            if (touchMode === null) {   // 沒移動超過誤差 → 輕點
                const t = e.changedTouches[0];
                if (t) {
                    // 擋掉輕點後瀏覽器補發的 mousedown/click，免得滑鼠的處理再跑一次
                    if (e.cancelable) e.preventDefault();
                    setFromClientX(t.clientX);
                }
            }
            touchMode = 'ignore';
        });
        slider.addEventListener('touchcancel', () => { touchMode = 'ignore'; });
    });
    
    // --- 初始設定 ---
    populateIVSelects();
    // 【新增】初始化滑桿的顯示狀態
    updateSliderDisplay('atk', atkSelect.value);
    updateSliderDisplay('def', defSelect.value);
    updateSliderDisplay('hp', hpSelect.value);

    // 預設帶入妙蛙種子並直接計算：讓新用戶一進來就看到結果長什麼樣子，
    // 而不是面對一片空白不知道要做什麼
    const defaultPokemon = POKEDEX.find(p => p.name === T.defaultMon) || POKEDEX.find(p => p.dexNumber === 1);
    // HTML 先以 .is-loading 預留預設結果的高度（避免 CLS），算完就解除（計算出錯也要解除）；
    // 萬一找不到預設寶可夢，回到原本「隱藏、空白」的狀態。
    try {
        if (defaultPokemon) {
            pokemonInput.value = defaultPokemon.name;
            clearBtn.classList.remove('hidden');
            handleCalculate();
        }
    } finally {
        resultsContainer.classList.remove('is-loading');
        if (!defaultPokemon) resultsContainer.classList.add('hidden');
    }
}

// ==================== 查詢條件浮動面板：收合、展開、拖曳 ====================
// 這段原本是首頁 index.html 底部的 inline script（針對 #pvp-controls）。
// build_tool_pages.py 拆頁時只擷取了 #pvp-ranker-app 區塊，handler 沒跟過來，
// 獨立頁的「−」與「⚙ 調整條件」因此都沒有作用。放在模組裡，
// build_tool_pages.py 的 sync()（只換表頭頁尾）不會覆蓋掉它。
// 不記住收合狀態（原版也沒有）。
function initControlsPanel() {
    const panel = document.getElementById('pvp-controls');
    const closeBtn = document.getElementById('pvp-controls-close');
    const toggleBtn = document.getElementById('pvp-controls-toggle');
    if (!panel || !closeBtn || !toggleBtn) return;
    const header = panel.querySelector('.controls-header');

    const EDGE = 4;   // 至少留一點邊，避免整個拖出去抓不回來
    // 只有浮動（position:fixed）時才拖曳／夾回畫面。手機版若改成排進內容流（static），
    // 這裡自動停用，也不會寫入 inline 的 left/top。
    const isFloating = () => getComputedStyle(panel).position === 'fixed';

    // 可視範圍用 documentElement.clientWidth/Height：桌機的 innerWidth 含垂直捲軸，
    // 用它的話面板右緣會被夾到捲軸底下。
    function clampPos(left, top) {
        const vw = document.documentElement.clientWidth || window.innerWidth;
        const vh = document.documentElement.clientHeight || window.innerHeight;
        const maxLeft = vw - panel.offsetWidth - EDGE;
        const maxTop = vh - (header ? header.offsetHeight : 0) - EDGE;
        return {
            left: Math.max(EDGE, Math.min(left, maxLeft)),
            top: Math.max(EDGE, Math.min(top, maxTop))
        };
    }

    // 拖曳過（有 inline left/top）的面板，在縮窗、轉向、重新展開後可能落到畫面外，
    // 把它夾回來。沒拖曳過的面板仍由 CSS 的 top/right 錨定，不去動它。
    // 從 static（手機寬）回到 fixed（桌機寬）時也會觸發 resize，留著的 left/top 會在這裡重新夾回。
    function clampIntoView() {
        if (!isFloating() || panel.classList.contains('collapsed')) return;
        if (!panel.style.left && !panel.style.top) return;
        const rect = panel.getBoundingClientRect();
        const p = clampPos(rect.left, rect.top);
        if (p.left !== rect.left) panel.style.left = p.left + 'px';
        if (p.top !== rect.top) panel.style.top = p.top + 'px';
    }

    function openPanel() {
        panel.classList.remove('collapsed');
        toggleBtn.classList.add('hidden');
        clampIntoView();
    }
    function closePanel() {
        panel.classList.add('collapsed');
        toggleBtn.classList.remove('hidden');
    }
    closeBtn.addEventListener('click', closePanel);
    toggleBtn.addEventListener('click', openPanel);

    // 預設展開，讓搜尋框一進來就看得到；收合後改用右下浮動鈕重新開啟
    openPanel();

    // ---- 不要蓋住廣告 ----
    // 桌機的面板固定在右上角，和表頭下方的廣告框左右重疊時會蓋住廣告右側。
    // 還沒拖曳過的面板，在廣告框還在畫面上時往下讓開；捲到廣告離開畫面後回到原位。
    // 用 CSS 變數 --pvp-shift（transform），不改 top，所以不會產生版面位移。
    const ad = document.querySelector('.site-ad');
    const BASE_TOP = parseFloat(getComputedStyle(panel).top) || 76;
    function avoidAd() {
        if (!ad || !isFloating() || panel.style.top) { panel.style.removeProperty('--pvp-shift'); return; }
        const a = ad.getBoundingClientRect();
        const vw = document.documentElement.clientWidth || window.innerWidth;
        const panelLeft = vw - 16 - panel.offsetWidth;
        const overlapX = a.right > panelLeft && a.left < vw - 16 && a.height > 0;
        const shift = overlapX ? Math.max(0, Math.round(a.bottom + 12 - BASE_TOP)) : 0;
        if (panel.style.getPropertyValue('--pvp-shift') !== shift + 'px') panel.style.setProperty('--pvp-shift', shift + 'px');
    }
    let adRaf = 0;
    const scheduleAvoid = () => { if (!adRaf) adRaf = requestAnimationFrame(() => { adRaf = 0; avoidAd(); }); };
    avoidAd();
    window.addEventListener('scroll', scheduleAvoid, { passive: true });
    window.addEventListener('resize', scheduleAvoid);
    if (ad && 'ResizeObserver' in window) new ResizeObserver(scheduleAvoid).observe(ad);   // 廣告填入後高度會變

    let resizeRaf = 0;
    window.addEventListener('resize', () => {
        if (resizeRaf) return;
        resizeRaf = requestAnimationFrame(() => { resizeRaf = 0; clampIntoView(); });
    });

    // ---- 拖曳：抓標題列移動面板位置 ----
    if (!header) return;
    let dragging = false, startX = 0, startY = 0, startLeft = 0, startTop = 0;

    header.addEventListener('pointerdown', (e) => {
        if (e.pointerType === 'mouse' && e.button !== 0) return;   // 只有滑鼠左鍵能拖曳
        if (e.target.closest('#pvp-controls-close')) return;   // 在「−」上按下不拖曳
        if (!isFloating()) return;
        dragging = true;
        const rect = panel.getBoundingClientRect();
        // 改成用 left/top 定位（原本靠 right 錨定）
        panel.style.left = rect.left + 'px';
        panel.style.top = rect.top + 'px';
        panel.style.right = 'auto';
        panel.style.removeProperty('--pvp-shift');   // rect 已含讓開的位移，改用 inline top 之後就不需要了
        startX = e.clientX; startY = e.clientY;
        startLeft = rect.left; startTop = rect.top;
        header.setPointerCapture(e.pointerId);
        e.preventDefault();
    });

    header.addEventListener('pointermove', (e) => {
        if (!dragging) return;
        const p = clampPos(startLeft + (e.clientX - startX), startTop + (e.clientY - startY));
        panel.style.left = p.left + 'px';
        panel.style.top = p.top + 'px';
    });

    function endDrag(e) {
        if (!dragging) return;
        dragging = false;
        try { header.releasePointerCapture(e.pointerId); } catch (err) {}
    }
    header.addEventListener('pointerup', endDrag);
    header.addEventListener('pointercancel', endDrag);
}