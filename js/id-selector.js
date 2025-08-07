export function initializeIdSelector() {
    const pokemonContainer = document.getElementById('pokemon-container');
    if (!pokemonContainer || pokemonContainer.innerHTML !== '') return; // 防止重複初始化

    const POKEMON_COUNT = 1025;
    const selectedIdsOutput = document.getElementById('selected-ids');
    const searchInput = document.getElementById('idSearchInput');
    const clearBtn = document.querySelector('#id-selector-app .clear-search-btn');

    const startersButton = document.getElementById('select-starters');
    const pseudosButton = document.getElementById('select-pseudos');
    const evolvedButton = document.getElementById('select-evolved');
    const clearButton = document.getElementById('clear-all');
    const includeStarterEvolutionsCheckbox = document.getElementById('include-starter-evolutions');
    const includePseudoEvolutionsCheckbox = document.getElementById('include-pseudo-evolutions');
    const selectAllShownButton = document.getElementById('select-all-shown');
    const showAllButton = document.getElementById('show-all');
    const megaButton = document.getElementById('select-mega');
    const includeMegaEvolutionsCheckbox = document.getElementById('include-mega-evolutions');
    const copyButton = document.getElementById('copy-button');
    
    let selectedPokemon = new Set();
    const STARTER_FAMILIES_IDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 152, 153, 154, 155, 156, 157, 158, 159, 160, 252, 253, 254, 255, 256, 257, 258, 259, 260, 387, 388, 389, 390, 391, 392, 393, 394, 395, 495, 496, 497, 498, 499, 500, 501, 502, 503, 650, 651, 652, 653, 654, 655, 656, 657, 658, 722, 723, 724, 725, 726, 727, 728, 729, 730, 810, 811, 812, 813, 814, 815, 816, 817, 818, 906, 907, 908, 909, 910, 911, 912, 913, 914];
    const STARTERS_BASE_IDS = [1, 4, 7, 152, 155, 158, 252, 255, 258, 387, 390, 393, 495, 498, 501, 650, 653, 656, 722, 725, 728, 810, 813, 816, 906, 909, 912];
    const PSEUDO_FAMILIES_IDS = [147, 148, 149, 246, 247, 248, 371, 372, 373, 374, 375, 376, 443, 444, 445, 633, 634, 635, 704, 705, 706, 782, 783, 784, 885, 886, 887, 996, 997, 998];
    const PSEUDOS_BASE_IDS = [147, 246, 371, 374, 443, 633, 704, 782, 885, 996];
    const MEGA_EVO_FAMILY_IDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 13, 14, 15, 16, 17, 18, 63, 64, 65, 79, 80, 92, 93, 94, 95, 115, 123, 127, 129, 130, 142, 150, 179, 180, 181, 208, 212, 214, 228, 229, 246, 247, 248, 252, 253, 254, 255, 256, 257, 258, 259, 260, 280, 281, 282, 302, 303, 304, 305, 306, 307, 308, 309, 310, 318, 319, 322, 323, 333, 334, 353, 354, 359, 361, 362, 371, 372, 373, 374, 375, 376, 380, 381, 382, 383, 384, 427, 428, 443, 444, 445, 447, 448, 459, 460, 475, 531, 719].sort((a, b) => a - b);
    const MEGA_EVO_BASE_IDS = [3, 6, 9, 15, 18, 65, 80, 94, 115, 127, 130, 142, 150, 181, 208, 212, 214, 229, 248, 254, 257, 260, 282, 302, 303, 306, 308, 310, 319, 323, 334, 354, 359, 362, 373, 376, 380, 381, 382, 383, 384, 428, 445, 448, 460, 475, 531, 719].sort((a, b) => a - b);
    const BASE_FORM_IDS = new Set([1, 4, 7, 10, 13, 16, 19, 21, 23, 25, 27, 29, 32, 35, 37, 39, 41, 43, 46, 48, 50, 52, 54, 56, 58, 60, 63, 66, 69, 72, 74, 77, 79, 81, 83, 84, 86, 88, 90, 92, 95, 96, 98, 100, 102, 104, 106, 107, 108, 109, 111, 113, 114, 115, 116, 118, 120, 122, 123, 124, 125, 126, 127, 128, 129, 131, 132, 133, 137, 138, 140, 142, 143, 144, 145, 146, 147, 150, 151, 152, 155, 158, 161, 163, 165, 167, 170, 172, 173, 174, 175, 177, 179, 183, 185, 187, 190, 191, 193, 194, 198, 200, 201, 202, 203, 204, 206, 207, 209, 211, 213, 214, 215, 216, 218, 220, 222, 223, 225, 226, 227, 228, 231, 234, 235, 236, 238, 239, 240, 241, 242, 243, 244, 245, 246, 249, 250, 251, 252, 255, 258, 261, 263, 265, 270, 273, 276, 278, 280, 283, 285, 287, 290, 293, 296, 298, 299, 300, 302, 303, 304, 307, 309, 311, 312, 313, 314, 315, 316, 318, 320, 322, 324, 325, 327, 328, 331, 333, 335, 336, 337, 338, 339, 341, 343, 345, 347, 349, 351, 352, 353, 355, 357, 358, 359, 360, 361, 363, 366, 369, 370, 371, 374, 377, 378, 379, 380, 381, 382, 383, 384, 385, 386, 387, 390, 393, 396, 399, 401, 403, 406, 408, 410, 412, 415, 417, 418, 420, 422, 424, 425, 427, 431, 433, 434, 436, 438, 439, 440, 441, 442, 443, 446, 447, 449, 451, 453, 455, 456, 458, 459, 480, 481, 482, 483, 484, 485, 486, 487, 488, 489, 491, 492, 493, 494, 495, 498, 501, 504, 506, 509, 511, 513, 515, 517, 519, 522, 524, 527, 529, 531, 532, 535, 538, 539, 540, 543, 546, 548, 550, 551, 554, 556, 557, 559, 561, 562, 564, 566, 568, 570, 572, 574, 577, 580, 582, 585, 587, 588, 590, 592, 594, 595, 597, 599, 602, 605, 607, 610, 613, 615, 616, 618, 619, 621, 622, 624, 626, 627, 629, 631, 632, 633, 636, 638, 639, 640, 641, 642, 643, 644, 645, 646, 647, 648, 649, 650, 653, 656, 659, 661, 664, 667, 669, 672, 674, 676, 677, 679, 682, 684, 686, 688, 690, 692, 694, 696, 698, 701, 702, 703, 704, 707, 708, 710, 712, 714, 716, 717, 718, 719, 720, 721, 722, 725, 728, 731, 734, 736, 739, 741, 742, 744, 746, 747, 749, 751, 753, 755, 757, 759, 761, 764, 765, 766, 767, 769, 771, 772, 773, 774, 775, 776, 777, 778, 779, 781, 782, 785, 786, 787, 788, 789, 791, 792, 793, 794, 795, 796, 797, 798, 799, 800, 801, 802, 803, 804, 805, 806, 807, 808, 809, 810, 813, 816, 819, 821, 824, 827, 829, 831, 833, 835, 837, 840, 843, 845, 846, 848, 850, 852, 854, 856, 859, 862, 863, 864, 865, 866, 867, 868, 869, 870, 871, 872, 874, 875, 876, 877, 878, 880, 881, 882, 883, 884, 885, 888, 889, 890, 891, 892, 893, 894, 895, 896, 897, 898, 899, 900, 901, 902, 903, 904, 905, 906, 909, 912, 915, 917, 919, 921, 924, 926, 928, 931, 932, 934, 935, 938, 940, 942, 944, 946, 948, 950, 951, 953, 955, 957, 960, 962, 965, 967, 968, 969, 971, 973, 976, 978, 980, 981, 982, 983, 984, 985, 986, 987, 988, 989, 990, 991, 992, 993, 994, 995, 996, 999, 1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009, 1010, 1011, 1012, 1014, 1016, 1017, 1018, 1020, 1021, 1022, 1023, 1024, 1025]);

    function triggerSave() {
        // 將 Set 轉換為 Array，因為 Firebase 不支援 Set
        const idsToSave = Array.from(selectedPokemon).sort((a, b) => a - b);
        // 呼叫 main.js 提供的全域函式來儲存
        saveDataForCurrentUser('idSelector/selected', idsToSave);
    }

    const fragment = document.createDocumentFragment();
    for (let i = 1; i <= POKEMON_COUNT; i++) {
        const pokemonId = i;
        const pokemonName = POKEMON_NAMES[pokemonId - 1] || `Pokemon #${pokemonId}`;
        const card = document.createElement('div');
        card.className = 'pokemon-card';
        card.dataset.id = pokemonId;
        card.dataset.name = pokemonName;
        card.innerHTML = `<img src="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${pokemonId}.png" alt="${pokemonName}" loading="lazy"><span class="pokemon-name">${pokemonName}</span>`;
        card.addEventListener('click', handlePokemonClick);
        fragment.appendChild(card);
    }
    pokemonContainer.appendChild(fragment);
    
    // --- Helper Functions ---
    function updateOutput() {
        const sortedIds = Array.from(selectedPokemon).sort((a, b) => a - b);
        selectedIdsOutput.textContent = sortedIds.join(',');
    }

    function handlePokemonClick(event) {
        const card = event.currentTarget;
        const pokemonId = parseInt(card.dataset.id, 10);
        if (selectedPokemon.has(pokemonId)) {
            selectedPokemon.delete(pokemonId);
            card.classList.remove('selected');
        } else {
            selectedPokemon.add(pokemonId);
            card.classList.add('selected');
        }
        updateOutput();
        triggerSave();
    }
    
    function handleSearch() {
        selectAllShownButton.style.display = 'none';
        const rawInput = searchInput.value.toLowerCase();
        const searchTerms = rawInput.split(',').map(term => term.trim()).filter(term => term.length > 0);
        const allPokemonCards = pokemonContainer.querySelectorAll('.pokemon-card');
        
        allPokemonCards.forEach(card => {
            if (searchTerms.length === 0) {
                card.style.display = 'flex';
                return;
            }
            const pokemonId = card.dataset.id;
            const pokemonName = card.dataset.name.toLowerCase();
            const isMatch = searchTerms.some(term => isNaN(term) ? pokemonName.includes(term) : pokemonId === term);
            card.style.display = isMatch ? 'flex' : 'none';
        });
    }

    function batchSelect(idList) {
        idList.forEach(id => {
            selectedPokemon.add(id);
            const cardElement = document.querySelector(`#id-selector-app .pokemon-card[data-id='${id}']`);
            if (cardElement) cardElement.classList.add('selected');
        });
        updateOutput();
        triggerSave();
    }

    function selectEvolvedForms() {
        const evolvedIds = [];
        for (let i = 1; i <= POKEMON_COUNT; i++) {
            if (!BASE_FORM_IDS.has(i)) {
                evolvedIds.push(i);
            }
        }
        batchSelect(evolvedIds);
    }

    function clearAllSelections(shouldSave = true) {
        selectedPokemon.clear();
        document.querySelectorAll('#id-selector-app .pokemon-card.selected').forEach(card => card.classList.remove('selected'));
        updateOutput();
        if (shouldSave) {
            triggerSave();
        }
    }
    function loadSelectedPokemon(idsToSelect) {
        if (!Array.isArray(idsToSelect)) return;

        // 1. 先清除現有選擇，但不觸發儲存
        clearAllSelections(false);

        // 2. 根據傳入的 ID 列表，設定 Set 並更新 UI
        idsToSelect.forEach(id => {
            selectedPokemon.add(id);
            const cardElement = document.querySelector(`#id-selector-app .pokemon-card[data-id='${id}']`);
            if (cardElement) {
                cardElement.classList.add('selected');
            }
        });

        // 3. 更新顯示的 ID 字串
        updateOutput();
    }
    function filterAndDisplay(idsToFilter) {
        searchInput.value = '';
        const allPokemonCards = pokemonContainer.querySelectorAll('.pokemon-card');
        allPokemonCards.forEach(card => {
            const pokemonId = parseInt(card.dataset.id, 10);
            card.style.display = idsToFilter.includes(pokemonId) ? 'flex' : 'none';
        });
        selectAllShownButton.style.display = 'inline-block';
    }
    
    // --- Event Listeners ---
    searchInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            searchInput.blur();
        }
    });
    startersButton.addEventListener('click', () => filterAndDisplay(includeStarterEvolutionsCheckbox.checked ? STARTER_FAMILIES_IDS : STARTERS_BASE_IDS));
    pseudosButton.addEventListener('click', () => filterAndDisplay(includePseudoEvolutionsCheckbox.checked ? PSEUDO_FAMILIES_IDS : PSEUDOS_BASE_IDS));
    megaButton.addEventListener('click', () => filterAndDisplay(includeMegaEvolutionsCheckbox.checked ? MEGA_EVO_FAMILY_IDS : MEGA_EVO_BASE_IDS));
    evolvedButton.addEventListener('click', selectEvolvedForms);
    clearButton.addEventListener('click', clearAllSelections);
    
    showAllButton.addEventListener('click', () => {
        searchInput.value = '';
        handleSearch();
    });
    searchInput.addEventListener('input', () => {
        handleSearch(); // 每次輸入都觸發搜尋
        // 根據輸入框是否有值來顯示/隱藏按鈕
        clearBtn.style.display = searchInput.value ? 'block' : 'none';
    });
    
    clearBtn.addEventListener('click', () => {
        searchInput.value = '';
        handleSearch(); // 傳入空字串來顯示所有結果
        clearBtn.style.display = 'none';
        searchInput.focus();
    });

    copyButton.addEventListener('click', () => {
        const textToCopy = selectedIdsOutput.textContent;
        if (!textToCopy) return;
        navigator.clipboard.writeText(textToCopy).then(() => {
            copyButton.textContent = '已複製!';
            copyButton.classList.add('copied');
            setTimeout(() => { 
                copyButton.textContent = '複製'; 
                copyButton.classList.remove('copied');
            }, 2000);
        });
    });

    selectAllShownButton.addEventListener('click', () => {
        const visibleCards = document.querySelectorAll('#id-selector-app .pokemon-card');
        const idsToSelect = [];
        visibleCards.forEach(card => {
            if (card.style.display !== 'none') {
                idsToSelect.push(parseInt(card.dataset.id, 10));
            }
        });
        batchSelect(idsToSelect);
    });
    window.loadIdSelectorState = loadSelectedPokemon;
    // 提供一個只清除畫面但不儲存的函式給登出時使用
    window.clearIdSelectorState = () => clearAllSelections(false); 

    // --- 【新增】初始化完成後，檢查是否有待處理的資料需要載入 ---
    if (window.pendingSelectedIds && window.pendingSelectedIds.length > 0) {
        loadSelectedPokemon(window.pendingSelectedIds);
        window.pendingSelectedIds = null; // 載入後清除暫存
    }
}
