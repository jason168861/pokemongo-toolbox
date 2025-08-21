// js/pvp-ranker.js

export function initializePvpRanker() {
    // 防止重複初始化
    const container = document.getElementById('pvp-ranker-app');
    if (container.dataset.initialized) return;
    container.dataset.initialized = 'true';

    // 檢查必要的數據是否已載入
    if (typeof POKEDEX === 'undefined' || typeof POKEMON_RANKINGS_1500 === 'undefined') {
        console.error("PvP Ranker: POKEDEX 或排名數據尚未載入。");
        container.innerHTML = '<h1>數據載入失敗</h1><p>請檢查 data/pokemon_data_and_rankings.js 是否存在且格式正確。</p>';
        return;
    }

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

    function handleCalculate() {
        updateCurrentCpDisplay(); 

        const pokemonName = pokemonInput.value;
        if (!pokemonName) { // 如果沒有寶可夢名稱，則不進行計算
            resultsContainer.innerHTML = '';
            resultsContainer.classList.add('hidden');
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
            return;
        }
        
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
                        warningText = `<p class="over-limit-warning">進化後CP約為 ${evolvedCp}，將超過限制</p>`;
                    }
                } else {
                    const currentAtk = pokemon.stats.atk + userIvs.atk;
                    const currentDef = pokemon.stats.def + userIvs.def;
                    const currentSta = pokemon.stats.sta + userIvs.sta;
                    const currentCP = getCP(currentAtk, currentDef, currentSta, currentLevel);

                    if (currentCP > league.cp && league.cp !== 10000) { 
                        isOverLimit = true;
                        warningText = `<p class="over-limit-warning">目前CP ${currentCP} 已超過限制</p>`;
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
                
                const leagueCardHTML = generateLeagueCardHTML(league, userPokemonRankInfo, rankOneSpread, isOverLimit, warningText, rankingInfoFromDataFile);
                leagueCardsContainer.innerHTML += leagueCardHTML;
            });

            if (leagueCardsContainer.innerHTML !== '') {
                familyResultContainer.appendChild(leagueCardsContainer);
                resultsContainer.appendChild(familyResultContainer);
            }
        });
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
                        <span class="move-type-label">一般</span>
                        <span class="move-name ${fastMoveClass}">${rankingInfoFromDataFile.fastMove}${fastMoveSymbol}</span>
                    </div>
                    <div class="moveset-line">
                        <span class="move-type-label">特殊</span>
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
                        <span class="rank-label">您的排名</span>
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
                     <p class="no-rank">您的IV組合不在此聯盟排名內。</p>
                </div>
               `;
        }

        const rankOneResultHTML = rankOneInfo ? `
            <div class="rank-details rank-one">
                <p class="rank-line">
                    <span class="rank-label">第一名 IV</span>
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
        const query = pokemonInput.value.toLowerCase();
        if (query.length < 1) {
            // 當輸入為空時，顯示所有寶可夢（或一個預設列表）
            updateSearchSuggestions(POKEDEX);
        } else {
            const matchedPokemons = POKEDEX.filter(p => 
                p.name.toLowerCase().includes(query) ||
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

        const handleInteraction = (e) => {
            e.preventDefault();
            const rect = slider.getBoundingClientRect();
            // 兼容滑鼠和觸控事件
            const x = (e.clientX || e.touches[0].clientX) - rect.left;
            let percentage = x / rect.width;
            percentage = Math.max(0, Math.min(1, percentage)); // 確保比例在 0 和 1 之間
            const value = Math.round(percentage * 15);

            if (correspondingSelect.value != value) {
                correspondingSelect.value = value;
                // 手動觸發 change 事件，來執行 handleCalculate 和更新滑桿
                correspondingSelect.dispatchEvent(new Event('change'));
            }
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

         // 觸控事件
        slider.addEventListener('touchstart', (e) => {
            isDragging = true;
            handleInteraction(e);
        });

        slider.addEventListener('touchmove', (e) => {
            if (isDragging) {
                handleInteraction(e);
            }
        });

        slider.addEventListener('touchend', () => {
            isDragging = false;
        });
    });
    
    // --- 初始設定 ---
    populateIVSelects();
    // 【新增】初始化滑桿的顯示狀態
    updateSliderDisplay('atk', atkSelect.value);
    updateSliderDisplay('def', defSelect.value);
    updateSliderDisplay('hp', hpSelect.value);
}