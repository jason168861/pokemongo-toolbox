export function initializeCpChecker() {
    const searchInput = document.getElementById('cpSearchInput');
    const resultsContainer = document.getElementById('resultsContainer');
    const statusMessage = document.getElementById('statusMessage');
    if (!searchInput) return; // 如果元素不存在，直接返回

    const allPokemonData = POKEMON_CP_DATA;
    if (!allPokemonData || allPokemonData.length === 0) {
        statusMessage.textContent = "錯誤：寶可夢資料未載入。";
        statusMessage.style.color = 'red';
        return;
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
    searchInput.addEventListener('input', (event) => {
        const query = event.target.value.trim().toLowerCase();
        filterResults(query);
    });
    createAllPokemonCards();
}
