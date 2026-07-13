// ============================================================================
// 全寶可夢圖鑑（Grid 圖鑑牆）
// 讀 data/pokedex_manifest.json（由 scripts/build_pokedex_manifest.py 產生），
// 圖片走 jsDelivr CDN（見 manifest.imageBase）。縮圖用原生 loading="lazy" 懶載入，
// 點一格開彈窗看該隻的所有變體（造型／服裝／異色）。
// 由 main.js 在切到此分頁時呼叫 initializeDexApp() 延遲初始化。
// ============================================================================

// 18 屬性：英文代碼 → [中文, 官方色]
const TYPES = {
  normal: ['一般', '#9099a1'], fire: ['火', '#ff9d55'], water: ['水', '#4d90d5'],
  electric: ['電', '#f3d23b'], grass: ['草', '#63bc5a'], ice: ['冰', '#73cec0'],
  fighting: ['格鬥', '#ce4069'], poison: ['毒', '#ab6ac8'], ground: ['地面', '#d97845'],
  flying: ['飛行', '#8fa8dd'], psychic: ['超能力', '#f97176'], bug: ['蟲', '#90c12c'],
  rock: ['岩石', '#c7b78b'], ghost: ['幽靈', '#5269ad'], dragon: ['龍', '#0b6dc3'],
  dark: ['惡', '#5a5366'], steel: ['鋼', '#5a8ea2'], fairy: ['妖精', '#ec8fe6']
};
const GEN_NAMES = { 1: '關都', 2: '城都', 3: '豐緣', 4: '神奧', 5: '合眾', 6: '卡洛斯', 7: '阿羅拉', 8: '伽勒爾', 9: '帕底亞' };

let dexInited = false;

export function initializeDexApp() {
  if (dexInited) return;
  dexInited = true;

  const grid = document.getElementById('dexGrid');
  const statusEl = document.getElementById('dexStatus');
  const searchInput = document.getElementById('dexSearch');
  const shinyToggle = document.getElementById('dexShinyToggle');
  const genSelect = document.getElementById('dexGen');
  const typeSelect = document.getElementById('dexType');
  const chips = document.querySelectorAll('#dex-app .dex-chip');
  const modal = document.getElementById('dexModal');
  const modalBody = document.getElementById('dexModalBody');
  const modalClose = document.getElementById('dexModalClose');

  // 填入世代（1–9）與屬性下拉選項
  for (let g = 1; g <= 9; g++) {
    genSelect.insertAdjacentHTML('beforeend',
      `<option value="${g}">第 ${g} 世代・${GEN_NAMES[g]}</option>`);
  }
  Object.entries(TYPES).forEach(([code, [zh]]) => {
    typeSelect.insertAdjacentHTML('beforeend', `<option value="${code}">${zh}</option>`);
  });

  let pokemon = null;
  let imageBase = '';
  let filter = 'all';
  let query = '';
  let gen = '';
  let type = '';
  let showShiny = false;

  fetch('data/pokedex_manifest.json')
    .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(data => {
      pokemon = data.pokemon;
      imageBase = data.imageBase;
      statusEl.textContent = `共 ${data.count} 隻寶可夢、${data.variantCount} 種樣式`;
      render();
    })
    .catch(e => { statusEl.textContent = '圖鑑載入失敗：' + e.message; });

  const imgUrl = file => imageBase + file;

  // 代表變體：一般樣式（非造型、非服裝、非異色）；找不到就取第一個
  const baseVariant = p =>
    p.variants.find(v => !v.form && !v.costume && !v.shiny) || p.variants[0];
  const baseShinyVariant = p =>
    p.variants.find(v => !v.form && !v.costume && v.shiny);

  function matches(p) {
    if (filter === 'shiny' && !p.hasShiny) return false;
    if (filter === 'mega' && !p.hasMega) return false;
    if (filter === 'costume' && !p.hasCostume) return false;
    if (gen && p.gen !== parseInt(gen, 10)) return false;
    if (type && !(p.types || []).includes(type)) return false;
    if (query) {
      const q = query.toLowerCase();
      const byNum = /^\d+$/.test(q) && p.dex === parseInt(q, 10);
      if (!byNum && !p.name.toLowerCase().includes(q)) return false;
    }
    return true;
  }

  const padNo = dex => '#' + String(dex).padStart(4, '0');
  const typeBadges = types => (types || []).map(t => {
    const [zh, color] = TYPES[t] || [t, '#888'];
    return `<span class="dex-type" style="background:${color}">${zh}</span>`;
  }).join('');

  function render() {
    if (!pokemon) return;
    const list = pokemon.filter(matches);
    const frag = document.createDocumentFragment();
    list.forEach(p => {
      const shinyVar = showShiny && baseShinyVariant(p);
      const file = shinyVar ? shinyVar.file : baseVariant(p).file;
      const cell = document.createElement('button');
      cell.className = 'dex-cell';
      cell.type = 'button';
      cell.innerHTML =
        `<img class="dex-cell-img" src="${imgUrl(file)}" alt="${p.name}" loading="lazy" decoding="async">` +
        `<span class="dex-cell-no">${padNo(p.dex)}</span>` +
        `<span class="dex-cell-name">${p.name}</span>` +
        (p.hasShiny ? '<span class="dex-cell-badge" title="有異色">✨</span>' : '');
      cell.addEventListener('click', () => openModal(p));
      frag.appendChild(cell);
    });
    grid.replaceChildren(frag);
    statusEl.textContent = list.length
      ? `顯示 ${list.length} 隻` : '找不到符合的寶可夢';
  }

  function openModal(p) {
    const vars = p.variants.map(v =>
      `<figure class="dex-var${v.shiny ? ' is-shiny' : ''}">
         <img src="${imgUrl(v.file)}" alt="${p.name} ${v.label}" loading="lazy" decoding="async">
         <figcaption>${v.label}${v.shiny ? ' ✨' : ''}</figcaption>
       </figure>`).join('');
    modalBody.innerHTML =
      `<div class="dex-modal-head">
         <span class="dex-modal-no">${padNo(p.dex)}</span>
         <h2>${p.name}</h2>
         <span class="dex-modal-types">${typeBadges(p.types)}</span>
         <span class="dex-modal-count">第 ${p.gen} 世代・${p.variants.length} 種樣式</span>
       </div>
       <div class="dex-var-grid">${vars}</div>`;
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
  }
  function closeModal() {
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
  }

  modalClose.addEventListener('click', closeModal);
  modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && modal.classList.contains('open')) closeModal();
  });

  let searchTimer = null;
  searchInput.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { query = searchInput.value.trim(); render(); }, 200);
  });
  shinyToggle.addEventListener('change', () => { showShiny = shinyToggle.checked; render(); });
  genSelect.addEventListener('change', () => { gen = genSelect.value; render(); });
  typeSelect.addEventListener('change', () => { type = typeSelect.value; render(); });
  chips.forEach(c => c.addEventListener('click', () => {
    chips.forEach(x => x.classList.remove('active'));
    c.classList.add('active');
    filter = c.dataset.filter;
    render();
  }));
}
