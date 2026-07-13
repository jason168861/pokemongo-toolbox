// ============================================================================
// 全寶可夢圖鑑（Grid 圖鑑牆）
// 讀 data/pokedex_manifest.json（由 scripts/build_pokedex_manifest.py 產生），
// 圖片走 jsDelivr CDN（見 manifest.imageBase）。縮圖用原生 loading="lazy" 懶載入，
// 點一格開彈窗看該隻的所有變體（造型／服裝／異色）。
// 由 main.js 在切到此分頁時呼叫 initializeDexApp() 延遲初始化。
// ============================================================================

let dexInited = false;

export function initializeDexApp() {
  if (dexInited) return;
  dexInited = true;

  const grid = document.getElementById('dexGrid');
  const statusEl = document.getElementById('dexStatus');
  const searchInput = document.getElementById('dexSearch');
  const shinyToggle = document.getElementById('dexShinyToggle');
  const chips = document.querySelectorAll('#dex-app .dex-chip');
  const modal = document.getElementById('dexModal');
  const modalBody = document.getElementById('dexModalBody');
  const modalClose = document.getElementById('dexModalClose');

  let pokemon = null;
  let imageBase = '';
  let filter = 'all';
  let query = '';
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
    if (query) {
      const q = query.toLowerCase();
      const byNum = /^\d+$/.test(q) && p.dex === parseInt(q, 10);
      if (!byNum && !p.name.toLowerCase().includes(q)) return false;
    }
    return true;
  }

  const padNo = dex => '#' + String(dex).padStart(4, '0');

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
         <span class="dex-modal-count">${p.variants.length} 種樣式</span>
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
  chips.forEach(c => c.addEventListener('click', () => {
    chips.forEach(x => x.classList.remove('active'));
    c.classList.add('active');
    filter = c.dataset.filter;
    render();
  }));
}
