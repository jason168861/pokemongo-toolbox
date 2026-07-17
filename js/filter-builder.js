// 篩選指令產生器：多組設定 → 組出遊戲內搜尋框可貼上的篩選指令
// 儲存：一律寫 localStorage；已登入時另外同步到 Firebase users/{uid}/filterBuilder/sets
import { saveDataForCurrentUser } from './main.js';

const IMG = 'img/';
const LS = 'filterBuilderSets';
const CLOUD_PATH = 'filterBuilder/sets';

/* ---------- 資料定義（要增刪項目/改字改這裡就好） ---------- */
const GROUPS = [
  { title: '狀態', items: [
    { term:'異色', label:'異色', desc:'色違寶可夢', img:['shiny.svg'] },
    { term:'亮晶晶', label:'亮晶晶（幸運）', desc:'透過交換獲得、升等花費減半的幸運寶可夢', img:['ui_bg_lucky_pokemon.png'] },
    { term:'暗影', label:'暗影', desc:'從火箭隊手中救出、尚未淨化', img:['ic_shadow.png'] },
    { term:'淨化', label:'淨化', desc:'已淨化的前暗影寶可夢', img:['ic_purified.png'] },
    { term:'交換', label:'交換', desc:'從好友交換得到的', img:['pogo_trading_icon.png'] },
    { term:'特殊', label:'特殊（造型）', desc:'穿戴特殊裝扮，例如戴帽子的皮卡丘', img:['trim/pm25.cSINNOH_2020_NOEVOLVE.g2.icon.png'] },
    { term:'孵化', label:'孵化', desc:'從蛋孵出來的', img:['Egg_A.png'] },
    { term:'只限蛋', label:'只限蛋（寶寶）', desc:'寶寶／幼年型態（如波克比、皮丘）', img:['trim/pokemon_icon_172_00.png'] },
    { term:'糖果XL', label:'糖果XL', desc:'曾使用 XL 糖果升過等', img:['RareXLCandy_PSD.png'] },
    { term:'防禦者', label:'防禦者', desc:'目前正在道館防守中', img:['ic_defend.png'] },
    { term:'背卡', label:'背卡', desc:'擁有特殊活動背景卡', img:['GO_Dark_Skies_background.png'] },
    { term:'極巨化', label:'極巨化', desc:'可進行極巨化', img:['badge_dynamax.png'] },
    { term:'超極巨化', label:'超極巨化', desc:'可進行超極巨化', img:['badge_gigantamax.png'] },
    { term:'冒險效果', label:'冒險效果', desc:'擁有冒險效果的寶可夢（如起源帝牙盧卡、起源帕路奇亞、蒼響等）', img:['trim/pm483.fORIGIN.icon.png','trim/pm484.fORIGIN.icon.png'] },
  ]},
  { title: '稀有度', items: [
    { term:'傳說的寶可夢', label:'傳說', desc:'神獸（傳說寶可夢）', img:['ic_Legendary_small.png'], dark:true },
    { term:'幻', label:'幻', desc:'幻之寶可夢（如夢幻、時拉比）', img:['trim/pm151.icon.png'] },
    { term:'究極異獸', label:'究極異獸', desc:'Ultra Beast', img:['raid_ultra_icon.png'] },
  ]},
  { title: '可進化狀態', items: [
    { term:'進化', label:'可進化', desc:'目前糖果足夠、可以進化', img:['trim/pm2.icon.png'] },
    { term:'超級進化', label:'可超級進化', desc:'目前可以 Mega 超級進化', img:['tx_raid_coin_mega.png'] },
    { term:'交換進化', label:'交換進化', desc:'交換後可免糖果直接進化', img:['trim/pm64.icon.png','trim/pm67.icon.png','trim/pm93.icon.png'] },
    { term:'道具', label:'道具進化', desc:'需要進化道具才能進化', img:['Bag_King_Rock_Sprite.png','Bag_Sun_Stone_Sprite.png'] },
    { term:'未登錄', label:'未登錄', desc:'進化後可解鎖新的圖鑑登錄', img:['trim/pokemon_icon_003_00.png'], sil:true },
  ]},
  { title: '獲得來源（限 2020/11 後）', items: [
    { term:'調查', label:'田野調查', desc:'田野調查任務獎勵', img:['TodayView_Icon_Research.png'], dark:true },
    { term:'火箭隊', label:'火箭隊', desc:'擊敗火箭隊獲得', img:['teamrocket_r_full.png'] },
    { term:'Snapshot', label:'Snapshot', desc:'AR 拍照時亂入捕捉的', img:['tx_ar_photo_tut_pika.png'] },
  ]},
  { title: '招式', items: [
    { term:'@天氣', label:'@ 天氣加成', desc:'招式當前受天氣加成', img:['ic_partly_cloudy_night.png'] },
    { term:'@特別', label:'@ 絕版招式', desc:'擁有絕版／傳承招式（社群日等）', img:[] },
  ]},
];
const GENDERS = [['雄性','♂ 雄性'],['雌性','♀ 雌性'],['性別不明','⚲ 性別不明']];
const TYPES = [['一般','NORMAL'],['火','FIRE'],['水','WATER'],['電','ELECTRIC'],['草','GRASS'],['冰','ICE'],
  ['格鬥','FIGHTING'],['毒','POISON'],['地面','GROUND'],['飛行','FLYING'],['超能力','PSYCHIC'],['蟲','BUG'],
  ['岩石','ROCK'],['幽靈','GHOST'],['龍','DRAGON'],['惡','DARK'],['鋼','STEEL'],['妖精','FAIRY']];
const IVDETAIL = [{term:'攻擊',label:'攻擊'},{term:'防禦',label:'防禦'},{term:'HP',label:'HP'}];
const RANGES = [
  { key:'cp',   prefix:'cp',   label:'CP',       desc:'戰鬥力，例：cp2000-3000', min:10 },
  { key:'hp',   prefix:'hp',   label:'HP',       desc:'血量，例：hp200-', min:1 },
  { key:'year', prefix:'年',   label:'捕獲年份', desc:'例：年2016；只填「從」＝該年之後', min:2016, max:2099 },
  { key:'day',  prefix:'日數', label:'捕獲天數', desc:'日數0＝24小時內、日數365-＝一年前', min:0 },
  { key:'dist', prefix:'距離', label:'距離(km)', desc:'距離100-＝100公里外', min:0 },
  { key:'buddy',prefix:'夥伴', label:'夥伴等級', desc:'0–5', min:0, max:5 },
  { key:'mega', prefix:'超級', label:'超級等級', desc:'1–3', min:1, max:3 },
];
const SEG = [['any','任意'],['include','要'],['exclude','不要']];

/* ---------- 狀態 ---------- */
let sets = [], activeId = null, dragId = null, cloudTimer = null;
const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
const $ = s => document.querySelector(s);
const el = (t, c, h) => { const e = document.createElement(t); if (c) e.className = c; if (h != null) e.innerHTML = h; return e; };

function newState() {
  const s = { nums:'', gender:'', flag:{}, types:[], stars:[], iv:{}, ranges:{}, move:'' };
  GROUPS.forEach(g => g.items.forEach(i => s.flag[i.term] = 'any'));
  IVDETAIL.forEach(d => s.iv[d.term] = { a:'', b:'' });
  RANGES.forEach(r => s.ranges[r.key] = { a:'', b:'' });
  return s;
}
// 讀舊資料時用預設補齊 → 日後新增篩選項目也不會壞掉
function normalize(st) {
  const d = newState(), o = { ...d, ...(st || {}) };
  o.flag = { ...d.flag, ...((st && st.flag) || {}) };
  o.iv = { ...d.iv };
  IVDETAIL.forEach(x => { const v = st && st.iv && st.iv[x.term]; if (v) o.iv[x.term] = { a:v.a||'', b:v.b||'' }; });
  o.ranges = { ...d.ranges };
  RANGES.forEach(r => { const v = st && st.ranges && st.ranges[r.key]; if (v) o.ranges[r.key] = { a:v.a||'', b:v.b||'' }; });
  o.types = Array.isArray(o.types) ? o.types : [];
  o.stars = Array.isArray(o.stars) ? o.stars : [];
  return o;
}
function nextName() { const taken = new Set(sets.map(s => s.name)); let n = 1;
  while (taken.has('組合 ' + n)) n++; return '組合 ' + n; }
function uniqueName(base) { const taken = new Set(sets.map(s => s.name));
  if (!taken.has(base)) return base;
  let i = 2; while (taken.has(base + ' ' + i)) i++; return base + ' ' + i; }
function newSet(name) { return { id: uid(), name: name || nextName(), state: newState() }; }
function cur() { return sets.find(s => s.id === activeId) || sets[0]; }

function saveLocal() { try { localStorage.setItem(LS, JSON.stringify({ sets, activeId })); } catch (e) {} }
function saveCloud() {   // 未登入時 saveDataForCurrentUser 會自動略過
  clearTimeout(cloudTimer);
  cloudTimer = setTimeout(() => saveDataForCurrentUser(CLOUD_PATH, { sets, activeId }), 800);
}
function save() { saveLocal(); saveCloud(); }

function adopt(data) {   // 把一份 {sets, activeId} 套用進來
  if (!data || !Array.isArray(data.sets) || !data.sets.length) return false;
  sets = data.sets.map(s => ({ id: s.id || uid(), name: s.name || '組合', state: normalize(s.state) }));
  activeId = (data.activeId && sets.some(s => s.id === data.activeId)) ? data.activeId : sets[0].id;
  return true;
}
function loadLocal() {
  try { if (adopt(JSON.parse(localStorage.getItem(LS) || 'null'))) return; } catch (e) {}
  sets = [newSet('組合 1')]; activeId = sets[0].id;
}

/* ---------- 產生指令 ---------- */
function rangeTerm(prefix, a, b) {
  a = (a || '').trim(); b = (b || '').trim();
  if (a && b) return a === b ? prefix + a : prefix + a + '-' + b;
  if (a) return prefix + a + '-';
  if (b) return prefix + '-' + b;
  return '';
}
// IV 細項：數字在前、屬性字在後（同遊戲的 4攻擊）；兩邊不同＝範圍 2-4攻擊
function statTerm(word, a, b) {
  a = (a || ''); b = (b || '');
  if (a !== '' && b !== '') { const lo = Math.min(+a, +b), hi = Math.max(+a, +b); return (lo === hi ? lo : lo + '-' + hi) + word; }
  if (a !== '') return a + word;
  if (b !== '') return b + word;
  return '';
}
// 純函式：由一份 state 產生完整指令（組合列也直接拿去顯示／複製）
function strOf(st) {
  const parts = [];
  const nums = (st.nums || '').split(/[,\s]+/).filter(Boolean).join(',');
  if (nums) parts.push(nums);
  if (st.gender) parts.push(st.gender);
  GROUPS.forEach(g => g.items.forEach(i => {
    const v = st.flag[i.term];
    if (v === 'include') parts.push(i.term);
    else if (v === 'exclude') parts.push('!' + i.term);
  }));
  if (st.types.length) parts.push(TYPES.map(t => t[0]).filter(n => st.types.includes(n)).join(','));
  if (st.stars.length) parts.push([...st.stars].sort().map(n => n + '*').join(','));
  IVDETAIL.forEach(d => { const t = statTerm(d.term, st.iv[d.term].a, st.iv[d.term].b); if (t) parts.push(t); });
  RANGES.forEach(r => { const t = rangeTerm(r.prefix, st.ranges[r.key].a, st.ranges[r.key].b); if (t) parts.push(t); });
  if (st.move) parts.push('@' + st.move.replace(/^@/, ''));
  return parts.join('&');
}

/* ---------- 小工具 ---------- */
function toast(msg, err) {
  const t = $('#fb-toast'); if (!t) return;
  t.textContent = msg; t.classList.toggle('fb-err', !!err);
  t.classList.add('fb-show'); setTimeout(() => t.classList.remove('fb-show'), 1600);
}
async function copyStr(str, okMsg) {
  try { await navigator.clipboard.writeText(str); toast(okMsg); }
  catch (e) { window.prompt('複製這段指令：', str); }
}

/* ---------- 組合列（含拖曳排序） ---------- */
function clearIns() {
  document.querySelectorAll('#filter-builder .fb-setchip.fb-insb, #filter-builder .fb-setchip.fb-insa')
    .forEach(x => x.classList.remove('fb-insb', 'fb-insa'));
}
function moveSet(id, to) {
  const from = sets.findIndex(s => s.id === id); if (from < 0) return;
  const [m] = sets.splice(from, 1);
  if (to > from) to--;
  sets.splice(Math.max(0, Math.min(to, sets.length)), 0, m);
  dragId = null; save(); renderSets();
}
function renderSets() {
  const bar = $('#fb-setbar'); if (!bar) return;
  bar.innerHTML = '';
  sets.forEach((s, idx) => {
    const cmd = strOf(s.state);
    const chip = el('div', 'fb-setchip' + (s.id === activeId ? ' fb-on' : ''));
    chip.draggable = true;
    chip.title = '可拖曳調整順序';
    const nm = el('span', 'fb-nm', s.name);
    nm.title = cmd || '（這組還沒有任何條件）';
    nm.onclick = () => { activeId = s.id; save(); renderSets(); renderAll(); build(); };
    const cp = el('button', 'fb-cp', '📋'); cp.title = '直接複製此組指令';
    cp.onclick = e => { e.stopPropagation();
      if (!cmd) { toast('這組還沒有任何條件', true); return; }
      copyStr(cmd, '已複製「' + s.name + '」'); };
    chip.ondragstart = e => { dragId = s.id; chip.classList.add('fb-dragging');
      e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', s.id); };
    chip.ondragend = () => { dragId = null; clearIns();
      document.querySelectorAll('#filter-builder .fb-setchip.fb-dragging').forEach(x => x.classList.remove('fb-dragging')); };
    chip.ondragover = e => { if (!dragId || dragId === s.id) return; e.preventDefault();
      const r = chip.getBoundingClientRect(), after = (e.clientX - r.left) > r.width / 2;
      clearIns(); chip.classList.add(after ? 'fb-insa' : 'fb-insb'); };
    chip.ondrop = e => { if (!dragId || dragId === s.id) return; e.preventDefault(); e.stopPropagation();
      const r = chip.getBoundingClientRect(), after = (e.clientX - r.left) > r.width / 2;
      clearIns(); moveSet(dragId, idx + (after ? 1 : 0)); };
    chip.appendChild(nm); chip.appendChild(cp); bar.appendChild(chip);
  });
  bar.ondragover = e => { if (dragId) e.preventDefault(); };
  bar.ondrop = e => { if (dragId && e.target === bar) { e.preventDefault(); clearIns(); moveSet(dragId, sets.length); } };
}

/* ---------- 依目前組合重繪所有控制項 ---------- */
function renderAll() {
  const st = cur().state;
  $('#fb-nums').value = st.nums || '';
  const root = $('#fb-sections'); root.innerHTML = '';

  GROUPS.forEach(g => {
    const card = el('div', 'fb-card'); card.appendChild(el('div', 'fb-h2', g.title));
    g.items.forEach(it => {
      const row = el('div', 'fb-frow'); row.title = '指令詞：' + it.term;
      const imgs = it.img || [];
      const ic = el('span', 'fb-ficon' + (imgs.length > 1 ? ' fb-multi' : ''));
      imgs.forEach(src => {
        const im = el('img'); im.src = IMG + src; im.alt = ''; im.loading = 'lazy';
        if (it.sil) im.classList.add('fb-sil');
        if (it.dark) im.classList.add('fb-dark');
        ic.appendChild(im);
      });
      row.appendChild(ic);
      row.appendChild(el('span', 'fb-fname', `${it.label}<small>${it.desc}</small>`));
      const seg = el('div', 'fb-seg');
      SEG.forEach(([sv, txt]) => {
        const b = el('button', null, txt); b.dataset.state = sv; b.type = 'button';
        if (st.flag[it.term] === sv) b.classList.add('fb-on');
        b.onclick = () => { st.flag[it.term] = sv;
          seg.querySelectorAll('button').forEach(x => x.classList.toggle('fb-on', x.dataset.state === sv)); build(); };
        seg.appendChild(b);
      });
      row.appendChild(seg); card.appendChild(row);
    });
    root.appendChild(card);
  });

  { // 性別
    const card = el('div', 'fb-card');
    card.appendChild(el('div', 'fb-h2', '性別'));
    card.appendChild(el('p', 'fb-cardhint', '只會選一種。'));
    const chips = el('div', 'fb-chips');
    [['', '任意'], ...GENDERS].forEach(([val, txt]) => {
      const c = el('div', 'fb-chip', txt); if (st.gender === val) c.classList.add('fb-on');
      c.onclick = () => { st.gender = val;
        chips.querySelectorAll('.fb-chip').forEach(x => x.classList.remove('fb-on')); c.classList.add('fb-on'); build(); };
      chips.appendChild(c);
    });
    card.appendChild(chips); root.appendChild(card);
  }

  { // 屬性
    const card = el('div', 'fb-card');
    card.appendChild(el('div', 'fb-h2', '屬性 <span class="fb-tag">複選＝任一符合</span>'));
    const chips = el('div', 'fb-chips');
    TYPES.forEach(([name, code]) => {
      const c = el('div', 'fb-chip', `<img src="${IMG}type/POKEMON_TYPE_${code}.png" alt="" loading="lazy">${name}`);
      if (st.types.includes(name)) c.classList.add('fb-on');
      c.onclick = () => { const i = st.types.indexOf(name);
        if (i >= 0) { st.types.splice(i, 1); c.classList.remove('fb-on'); } else { st.types.push(name); c.classList.add('fb-on'); }
        build(); };
      chips.appendChild(c);
    });
    card.appendChild(chips); root.appendChild(card);
  }

  { // 評價星級
    const card = el('div', 'fb-card');
    card.appendChild(el('div', 'fb-h2', '評價星級 <span class="fb-tag">複選＝任一符合</span>'));
    const chips = el('div', 'fb-chips');
    [0, 1, 2, 3, 4].forEach(n => {
      const c = el('div', 'fb-chip', n + '★'); if (st.stars.includes(n)) c.classList.add('fb-on');
      c.onclick = () => { const i = st.stars.indexOf(n);
        if (i >= 0) { st.stars.splice(i, 1); c.classList.remove('fb-on'); } else { st.stars.push(n); c.classList.add('fb-on'); }
        build(); };
      chips.appendChild(c);
    });
    card.appendChild(chips);
    card.appendChild(el('p', 'fb-hint', '4★＝100%(滿三圍) · 3★＝82–98% · 2★＝66–80% · 1★＝51–64% · 0★＝0–49%'));
    root.appendChild(card);
  }

  { // IV 細項
    const card = el('div', 'fb-card');
    card.appendChild(el('div', 'fb-h2', 'IV 細項 <span class="fb-tag">攻/防/HP 可選範圍</span>'));
    card.appendChild(el('p', 'fb-cardhint', '數字 0–4 對應 IV：0＝0、1＝1–5、2＝6–10、3＝11–14、4＝15。「從/到」相同或只選一邊＝單一值，兩邊不同＝範圍（例 2–4）。三者皆 4 即完美 IV。'));
    const grid = el('div', 'fb-grid');
    const mkSel = v => { const s = el('select');
      s.innerHTML = '<option value="">任意</option>' + [0,1,2,3,4].map(n => `<option value="${n}">${n}</option>`).join('');
      s.value = v || ''; return s; };
    IVDETAIL.forEach(d => {
      const f = el('div', 'fb-field'); f.appendChild(el('label', null, d.label));
      const sa = mkSel(st.iv[d.term].a), sb = mkSel(st.iv[d.term].b);
      sa.onchange = () => { st.iv[d.term].a = sa.value; build(); };
      sb.onchange = () => { st.iv[d.term].b = sb.value; build(); };
      f.appendChild(sa); f.appendChild(el('span', null, '–')); f.appendChild(sb);
      grid.appendChild(f);
    });
    card.appendChild(grid); root.appendChild(card);
  }

  { // 數值範圍
    const card = el('div', 'fb-card');
    card.appendChild(el('div', 'fb-h2', '數值範圍 <span class="fb-tag">選填</span>'));
    RANGES.forEach(r => {
      const row = el('div', 'fb-rangerow');
      row.appendChild(el('span', 'fb-rlabel', `${r.label}<small>${r.desc}</small>`));
      const a = el('input', 'fb-rin'); a.type = 'number'; a.placeholder = '從'; a.value = st.ranges[r.key].a;
      const b = el('input', 'fb-rin'); b.type = 'number'; b.placeholder = '到'; b.value = st.ranges[r.key].b;
      if (r.min != null) { a.min = r.min; b.min = r.min; }
      if (r.max != null) { a.max = r.max; b.max = r.max; }
      a.oninput = () => { st.ranges[r.key].a = a.value; build(); };
      b.oninput = () => { st.ranges[r.key].b = b.value; build(); };
      row.appendChild(a); row.appendChild(el('span', null, '–')); row.appendChild(b);
      card.appendChild(row);
    });
    root.appendChild(card);
  }

  { // 指定招式
    const card = el('div', 'fb-card');
    card.appendChild(el('div', 'fb-h2', '指定招式 <span class="fb-tag">選填</span>'));
    card.appendChild(el('p', 'fb-cardhint', '輸入招式名會加上 <code>@</code>，例：輸入「破壞光線」→ <code>@破壞光線</code>。'));
    const inp = el('input', 'fb-rin'); inp.style.width = '100%';
    inp.placeholder = '招式名稱，例：破壞光線'; inp.value = st.move || '';
    inp.oninput = () => { st.move = inp.value.trim(); build(); };
    card.appendChild(inp); root.appendChild(card);
  }
}

/* ---------- 預覽 ---------- */
function build() {
  const str = strOf(cur().state);
  const pv = $('#fb-preview');
  if (str) pv.textContent = str;
  else pv.innerHTML = '<span class="fb-ph">在上方選擇條件，這裡會即時產生指令…</span>';
  $('#fb-count').textContent = str ? str.length + ' 字' : '';
  save(); renderSets();
  return str;
}

/* ---------- 進入點 ---------- */
export function initializeFilterBuilder() {
  const root = document.getElementById('fb-sections');
  if (!root) return;

  loadLocal();

  // 編號輸入 / 匯入
  const nums = $('#fb-nums');
  nums.oninput = () => { const v = nums.value.replace(/[^0-9,\-\s]/g, '');
    nums.value = v; cur().state.nums = v; build(); };
  $('#fb-clearNums').onclick = () => { nums.value = ''; cur().state.nums = ''; build(); };
  $('#fb-importNums').onclick = async () => {
    const setNums = v => { nums.value = v; cur().state.nums = v; build(); };
    // 1) 同頁編號篩選器目前的即時選取
    const live = document.getElementById('selected-ids');
    if (live && live.textContent.trim()) { setNums(live.textContent.trim()); toast('已帶入編號篩選器目前的選取'); return; }
    // 2) 已登入但還沒開過那個分頁 → 用雲端讀回來的暫存
    if (Array.isArray(window.pendingSelectedIds) && window.pendingSelectedIds.length) {
      setNums([...window.pendingSelectedIds].sort((a, b) => a - b).join(',')); toast('已帶入你儲存的編號選取'); return;
    }
    // 3) 都沒有 → 退回讀剪貼簿
    try {
      const txt = (await navigator.clipboard.readText() || '').replace(/[^0-9,\-\s]/g, '').trim();
      if (!txt) { toast('編號篩選器目前沒有勾選任何寶可夢', true); return; }
      setNums(txt.split(/[,\s]+/).filter(Boolean).join(',')); toast('已從剪貼簿帶入編號');
    } catch (e) { toast('編號篩選器目前沒有勾選任何寶可夢', true); }
  };

  // 前往編號篩選器分頁：直接點主導覽對應的按鈕，交給 main.js 的 SPA 切換邏輯處理
  const goto = $('#fb-gotoIds');
  if (goto) goto.onclick = () => {
    const tab = document.querySelector('.tab-button[data-target="id-selector-app"]');
    if (tab) { tab.click(); window.scrollTo({ top: 0, behavior: 'smooth' }); }
    else window.location.href = '?tab=id-selector-app';
  };

  // 組合管理
  $('#fb-addSet').onclick = () => { const s = newSet(); sets.push(s); activeId = s.id;
    save(); renderSets(); renderAll(); build(); toast('已新增「' + s.name + '」'); };
  $('#fb-renameSet').onclick = () => { const s = cur(); const n = window.prompt('組合名稱：', s.name);
    if (n === null) return; s.name = n.trim() || s.name; save(); renderSets(); };
  $('#fb-dupSet').onclick = () => { const s = cur();
    const c = { id: uid(), name: uniqueName(s.name + ' 複本'), state: JSON.parse(JSON.stringify(s.state)) };
    sets.splice(sets.indexOf(s) + 1, 0, c); activeId = c.id;
    save(); renderSets(); renderAll(); build(); toast('已複製為「' + c.name + '」'); };
  $('#fb-delSet').onclick = () => {
    if (sets.length <= 1) { toast('至少要保留一組', true); return; }
    const s = cur(); if (!confirm('確定刪除「' + s.name + '」？')) return;
    sets = sets.filter(x => x.id !== s.id); activeId = sets[0].id;
    save(); renderSets(); renderAll(); build(); toast('已刪除');
  };
  $('#fb-delAllSets').onclick = () => {
    if (!confirm('確定刪除全部 ' + sets.length + ' 組篩選組合？\n此動作無法復原。')) return;
    sets = [newSet('組合 1')]; activeId = sets[0].id;   // 一律保留一組空白的，介面才有東西可編輯
    save(); renderSets(); renderAll(); build(); toast('已刪除全部組合');
  };

  // 複製 / 重設
  $('#fb-copyBtn').onclick = () => { const str = strOf(cur().state);
    if (!str) { toast('目前沒有任何條件', true); return; }
    copyStr(str, '已複製到剪貼簿'); };
  $('#fb-resetAll').onclick = () => { const s = cur();
    if (!confirm('清空「' + s.name + '」的所有條件？')) return;
    s.state = newState(); save(); renderAll(); build(); toast('已重設此組');
  };

  // 給 main.js 在登入後呼叫（雲端資料覆蓋本機）
  window.loadFilterBuilderState = (data) => {
    if (adopt(data)) { saveLocal(); renderSets(); renderAll(); build(); }
    else { saveCloud(); }   // 雲端還沒有 → 把目前本機的組合推上去
  };

  renderSets(); renderAll(); build();

  // 若登入資料比本模組先到（使用者尚未點開此分頁），這裡補套用
  if (window.pendingFilterBuilder) {
    window.loadFilterBuilderState(window.pendingFilterBuilder);
    window.pendingFilterBuilder = null;
  }
}
