/* =============================================================================
 * 社群日 / 經典社群日 頁面渲染引擎
 * -----------------------------------------------------------------------------
 * 這支檔案「不用編輯」。每個月要新增社群日頁面時，只要複製 events/_template/
 * 資料夾、改裡面 index.html 最上方的 EVENT 設定物件即可（其餘全由這支渲染）。
 *
 * 運作方式：頁面把設定放在 window.CD_EVENT，載入這支後自動渲染到 #cd-root。
 * 沒填的欄位（空字串 / 空陣列）對應的區塊會自動隱藏，不會留下空殼。
 *
 * 哪些欄位可以直接寫 HTML（例如要加 <b>、<a>、換行 <br>）：
 *   tagline、bonuses[].text、featuredMove.pve/pvp、evolution[].bestPve/bestPvp/note、
 *   shinyNote、verdict.summary、fieldResearch[].reward、faq[].a、
 *   customSections[].html、bonusWindowNote。
 *   其餘欄位（名稱、日期等）當純文字處理，寫 HTML 會原樣顯示。
 * ========================================================================== */
(function () {
  'use strict';

  /* 屬性對應主題色（決定 hero 的漸層底色）。key 用英文小寫，設定裡 types 也用英文。 */
  var TYPE_COLORS = {
    normal: '#9a9a80', fire: '#ee8130', water: '#5a90f0', electric: '#eab308',
    grass: '#5cae4c', ice: '#57c4c4', fighting: '#c22e28', poison: '#a33ea1',
    ground: '#c99a3e', flying: '#8b7be8', psychic: '#f95587', bug: '#8fa018',
    rock: '#9c8a2e', ghost: '#6a558f', dragon: '#6f35fc', dark: '#5a4a3f',
    steel: '#8a8aa8', fairy: '#d685ad'
  };
  var TYPE_ZH = {
    normal: '一般', fire: '火', water: '水', electric: '電', grass: '草', ice: '冰',
    fighting: '格鬥', poison: '毒', ground: '地面', flying: '飛行', psychic: '超能力',
    bug: '蟲', rock: '岩石', ghost: '幽靈', dragon: '龍', dark: '惡', steel: '鋼', fairy: '妖精'
  };

  /* ---- 小工具 ------------------------------------------------------------ */
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
  function has(v) {                         // 判斷欄位有沒有填
    if (v == null) return false;
    if (Array.isArray(v)) return v.length > 0;
    if (typeof v === 'object') return Object.keys(v).length > 0;
    return String(v).trim() !== '';
  }
  function el(html) {
    var d = document.createElement('div');
    d.innerHTML = html.trim();
    return d.firstElementChild;
  }
  // Pokéball 佔位圖：沒填圖片網址時顯示，不會破版
  var PLACEHOLDER =
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ccircle cx='50' cy='50' r='46' fill='%23fff' stroke='%23222' stroke-width='4'/%3E%3Cpath d='M4 50h30a16 16 0 0 1 32 0h30' fill='none' stroke='%23222' stroke-width='4'/%3E%3Cpath d='M4 50a46 46 0 0 1 92 0z' fill='%23e8483f' stroke='%23222' stroke-width='4'/%3E%3Ccircle cx='50' cy='50' r='12' fill='%23fff' stroke='%23222' stroke-width='4'/%3E%3C/svg%3E";
  function imgTag(src, alt, cls) {
    var s = has(src) ? esc(src) : PLACEHOLDER;
    return '<img class="' + (cls || '') + '" src="' + s + '" alt="' + esc(alt) + '" ' +
      'loading="lazy" onerror="this.onerror=null;this.src=\'' + PLACEHOLDER + '\'">';
  }
  // 純圖片（沒填就不輸出任何東西，用於獎勵縮圖等）
  function thumb(src, alt, cls) {
    if (!has(src)) return '';
    return '<img class="' + (cls || '') + '" src="' + esc(src) + '" alt="' + esc(alt || '') + '" ' +
      'loading="lazy" onerror="this.style.display=\'none\'">';
  }
  // IV100 CP 徽章（研究獎勵通常是 15 等）
  function cpBadge(cp, lv) {
    if (!has(cp)) return '';
    return '<em class="cd-cp">100% CP ' + esc(cp) + '<span>Lv' + (lv || 15) + '</span></em>';
  }
  // 獎勵項目：可以是字串，或 { text, img, cp15 } 物件
  function rewardLi(r) {
    if (r == null) return '';
    if (typeof r === 'string') return '<li>' + esc(r) + '</li>';
    return '<li class="cd-rw">' + thumb(r.img, r.text, 'cd-rw-img') +
      '<span class="cd-rw-tx">' + esc(r.text || '') + '</span>' + cpBadge(r.cp15, 15) + '</li>';
  }

  /* ---- 主題色 ------------------------------------------------------------ */
  function themeVars(types) {
    var t = (types || []).map(function (x) { return String(x).toLowerCase(); });
    var c1 = TYPE_COLORS[t[0]] || '#e0276c';
    var c2 = TYPE_COLORS[t[1]] || c1;
    return { c1: c1, c2: c2, types: t };
  }

  /* ---- 日期 / 倒數 -------------------------------------------------------- */
  function buildTimes(ev) {
    if (!has(ev.date)) return null;
    var p = ev.date.split('-');
    var y = +p[0], m = +p[1], d = +p[2];
    var sh = ev.startHour == null ? 14 : +ev.startHour;
    var eh = ev.endHour == null ? 17 : +ev.endHour;
    // 用當地時間建立（社群日是「玩家當地時間」14:00–17:00）
    return {
      start: new Date(y, m - 1, d, sh, 0, 0),
      end: new Date(y, m - 1, d, eh, 0, 0),
      sh: sh, eh: eh
    };
  }
  var WEEK = ['日', '一', '二', '三', '四', '五', '六'];
  function fmtDate(dt) {
    return dt.getFullYear() + ' 年 ' + (dt.getMonth() + 1) + ' 月 ' + dt.getDate() +
      ' 日（週' + WEEK[dt.getDay()] + '）';
  }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function fmtHM(h) { return pad(h) + ':00'; }

  /* ---- 各區塊 ------------------------------------------------------------ */
  function section(id, title, bodyHtml, sub) {
    return '<section class="cd-sec" id="' + id + '">' +
      '<div class="cd-sec-head"><h2>' + esc(title) + '</h2>' +
      (sub ? '<p class="cd-sec-sub">' + esc(sub) + '</p>' : '') + '</div>' +
      bodyHtml + '</section>';
  }

  function renderHero(ev, T, times) {
    var typeChips = (T.types || []).map(function (t) {
      return '<span class="cd-type cd-type-' + t + '">' + esc(TYPE_ZH[t] || t) + '</span>';
    }).join('');

    var dateChips = '';
    if (times) {
      dateChips =
        '<div class="cd-chips">' +
          '<span class="cd-chip"><span class="cd-chip-k">日期</span>' + esc(fmtDate(times.start)) + '</span>' +
          '<span class="cd-chip"><span class="cd-chip-k">時間</span>' + fmtHM(times.sh) + '–' + fmtHM(times.eh) + '（當地時間）</span>' +
        '</div>';
    }

    var shinyBtn = has(ev.shinyImg)
      ? '<button type="button" class="cd-shiny-toggle" aria-pressed="false">✨ 看異色</button>' : '';

    var hasArt = has(ev.img) || has(ev.shinyImg);
    var artBlock = hasArt
      ? '<div class="cd-hero-art">' +
          imgTag(ev.img, ev.pokemon, 'cd-art-main') +
          (has(ev.shinyImg) ? imgTag(ev.shinyImg, ev.pokemon + ' 異色', 'cd-art-shiny') : '') +
          shinyBtn +
        '</div>'
      : '';

    return '' +
    '<header class="cd-hero">' +
      '<div class="cd-hero-bg" aria-hidden="true"></div>' +
      '<div class="cd-hero-inner' + (hasArt ? '' : ' cd-hero-inner--solo') + '">' +
        '<div class="cd-hero-copy">' +
          '<div class="cd-badges">' +
            '<span class="cd-kind">' + esc(ev.kind || '社群日') + '</span>' + typeChips +
          '</div>' +
          '<h1 class="cd-title">' +
            (has(ev.heading)
              ? esc(ev.heading)
              : esc(ev.pokemon || '主打寶可夢') +
                (has(ev.pokemonEn) ? ' <span class="cd-title-en">' + esc(ev.pokemonEn) + '</span>' : '')) +
          '</h1>' +
          (has(ev.tagline) ? '<p class="cd-tagline">' + ev.tagline + '</p>' : '') +
          dateChips +
          '<div class="cd-status" id="cd-status"></div>' +
          '<div class="cd-countdown" id="cd-countdown" hidden></div>' +
        '</div>' +
        artBlock +
      '</div>' +
    '</header>';
  }

  // 活動主視覺 / 橫幅圖（放最上方，例如官方的社群日宣傳圖）
  function renderBanner(ev) {
    if (!has(ev.bannerImg)) return '';
    return '<div class="cd-banner"><img src="' + esc(ev.bannerImg) + '" alt="' +
      esc((ev.pokemon || '') + ' ' + (ev.kind || '社群日')) +
      '" onerror="this.parentNode.style.display=\'none\'"></div>';
  }

  function renderBonuses(ev) {
    if (!has(ev.bonuses)) return '';
    var items = ev.bonuses.map(function (b) {
      var ic = has(b.img)
        ? '<span class="cd-bonus-ic cd-bonus-img">' + thumb(b.img, '', '') + '</span>'
        : '<span class="cd-bonus-ic">' + esc(b.icon || '🎁') + '</span>';
      return '<li class="cd-bonus">' + ic +
        '<span class="cd-bonus-tx">' + (b.text || '') + '</span></li>';
    }).join('');
    var note = has(ev.bonusWindowNote)
      ? '<p class="cd-note">⏰ ' + ev.bonusWindowNote + '</p>' : '';
    return section('bonuses', '活動加成', '<ul class="cd-bonus-grid">' + items + '</ul>' + note);
  }

  // 特色招式前的圖示：自訂圖片（例：屬性圖示）> emoji > 預設 ⚡
  function moveIcon(m) {
    if (has(m.iconImg)) return '<img class="cd-move-ic" src="' + esc(m.iconImg) + '" alt="" onerror="this.style.display=\'none\'">';
    return '<span class="cd-move-ic-emoji">' + esc(has(m.icon) ? m.icon : '⚡') + '</span>';
  }
  function renderMove(ev) {
    var m = ev.featuredMove;
    if (!has(m) || !has(m.name)) return '';
    var rows = '';
    if (has(m.when)) rows += '<p class="cd-move-when">🕑 ' + esc(m.when) + '</p>';
    var cols = '';
    if (has(m.pve)) cols += '<div class="cd-move-col"><h4>PvE（打王 / 道館）</h4><p>' + m.pve + '</p></div>';
    if (has(m.pvp)) cols += '<div class="cd-move-col"><h4>PvP（對戰聯盟）</h4><p>' + m.pvp + '</p></div>';
    var body =
      '<div class="cd-move-card">' +
        '<div class="cd-move-name">' + moveIcon(m) + esc(m.name) + '</div>' +
        rows +
        (cols ? '<div class="cd-move-cols">' + cols + '</div>' : '') +
      '</div>';
    return section('move', '特色招式', body, '進化後才能學到的專屬招式，錯過只能等再次舉辦或使用招式升級道具。');
  }

  function renderEvolution(ev) {
    if (!has(ev.evolution)) return '';
    var cards = ev.evolution.map(function (p, i) {
      var arrow = i > 0 ? '<div class="cd-evo-arrow" aria-hidden="true">▶</div>' : '';
      var moves = '';
      if (has(p.bestPve) || has(p.bestPvp)) {
        moves = '<div class="cd-evo-moves">' +
          (has(p.bestPve) ? '<div class="cd-evo-move"><span class="cd-tag cd-tag-pve">PvE</span>' + p.bestPve + '</div>' : '') +
          (has(p.bestPvp) ? '<div class="cd-evo-move"><span class="cd-tag cd-tag-pvp">PvP</span>' + p.bestPvp + '</div>' : '') +
          '</div>';
      }
      var note = has(p.note) ? '<p class="cd-evo-note">' + p.note + '</p>' : '';
      return arrow +
        '<div class="cd-evo-card">' +
          '<div class="cd-evo-pic">' + imgTag(p.img, p.name, '') + '</div>' +
          '<div class="cd-evo-name">' + esc(p.name || '') + '</div>' +
          note + moves +
        '</div>';
    }).join('');
    return section('evolution', '進化與推薦招式',
      '<div class="cd-evo-row">' + cards + '</div>',
      '想確認自己抓到的個體值好不好，可搭配下方的「個體值 / CP 工具」。');
  }

  function renderShiny(ev) {
    if (!has(ev.shinyNote)) return '';
    var pic = has(ev.shinyImg)
      ? '<div class="cd-shiny-pic">' + imgTag(ev.shinyImg, (ev.pokemon || '') + ' 異色', '') + '</div>' : '';
    return section('shiny', '異色情報',
      '<div class="cd-shiny-box">' + pic + '<div class="cd-shiny-tx">' + ev.shinyNote + '</div></div>');
  }

  // 一顆獎勵：縮圖 + 文字 + CP 徽章（給任務對應獎勵 / 階段獎勵共用）
  function rewardChip(rw, cls) {
    if (typeof rw === 'string') rw = { text: rw };
    return '<span class="' + (cls || 'cd-sr-chip') + '">' + thumb(rw.img, rw.text, 'cd-rw-img') +
      '<span class="cd-rw-tx">' + esc(rw.text || '') + '</span>' + cpBadge(rw.cp15, 15) + '</span>';
  }
  function renderSpecialResearch(ev) {
    var r = ev.specialResearch;
    if (!has(r) || (!has(r.name) && !has(r.steps))) return '';
    var head = has(r.name) ? '<div class="cd-sr-head"><span class="cd-sr-name">📜 ' + esc(r.name) + '</span>' +
      (has(r.price) ? '<span class="cd-sr-price">' + esc(r.price) + '</span>' : '') + '</div>' : '';
    var steps = '';
    if (has(r.steps)) {
      steps = r.steps.map(function (s, i) {
        // 任務 → 對應獎勵（一一對應）
        var taskRows = (s.tasks || []).map(function (t) {
          if (typeof t === 'string') t = { text: t };
          var rw = has(t.reward)
            ? rewardChip(t.reward, 'cd-sr-trw')
            : '<span class="cd-sr-trw cd-sr-trw-none">—</span>';
          return '<div class="cd-sr-task">' +
            '<span class="cd-sr-tk">' + esc(t.text || '') + '</span>' +
            '<span class="cd-sr-arrow" aria-hidden="true">→</span>' + rw + '</div>';
        }).join('');
        // 階段全破獎勵（stepRewards，相容舊的 rewards）
        var stepRw = has(s.stepRewards) ? s.stepRewards : (has(s.rewards) ? s.rewards : []);
        var stepRwHtml = has(stepRw)
          ? '<div class="cd-sr-steprw"><span class="cd-sr-steprw-lb">🎁 階段全破獎勵</span>' +
              '<span class="cd-sr-steprw-list">' + stepRw.map(function (rw) { return rewardChip(rw); }).join('') + '</span></div>'
          : '';
        return '<details class="cd-sr-step"' + (i === 0 ? ' open' : '') + '>' +
          '<summary>' + esc(s.title || ('第 ' + (i + 1) + ' 階段')) + '</summary>' +
          '<div class="cd-sr-body2">' +
            (taskRows ? '<div class="cd-sr-tasklist">' + taskRows + '</div>' : '') +
            stepRwHtml +
          '</div></details>';
      }).join('');
    }
    var note = has(r.note) ? '<p class="cd-note">' + r.note + '</p>' : '';
    return section('special-research', '限定特殊調查',
      '<div class="cd-sr">' + head + steps + note + '</div>');
  }

  function renderFieldResearch(ev) {
    if (!has(ev.fieldResearch)) return '';
    var rows = ev.fieldResearch.map(function (f) {
      var reward = '<div class="cd-fr-rw">' + thumb(f.img, f.reward, 'cd-rw-img') +
        '<span class="cd-rw-tx">' + (f.reward || '') + '</span>' + cpBadge(f.cp15, 15) + '</div>';
      return '<tr><td class="cd-fr-task">' + esc(f.task || '') + '</td>' +
        '<td class="cd-fr-reward">' + reward + '</td></tr>';
    }).join('');
    return section('field-research', '活動限定田野調查',
      '<div class="cd-table-wrap"><table class="cd-table"><thead><tr><th>任務</th><th>獎勵</th></tr></thead>' +
      '<tbody>' + rows + '</tbody></table></div>',
      '獎勵寶可夢為 15 等，捕捉畫面看到的 CP 剛好等於下表數字時就是 100% 個體值。');
  }

  function renderVerdict(ev) {
    var v = ev.verdict;
    if (!has(v) || (!has(v.summary) && !has(v.rating))) return '';
    var rating = has(v.rating) ? '<span class="cd-verdict-rating">' + esc(v.rating) + '</span>' : '';
    var forWho = has(v.forWho) ? '<p class="cd-verdict-for"><b>適合誰：</b>' + v.forWho + '</p>' : '';
    var body = '<div class="cd-verdict">' +
      '<div class="cd-verdict-top">💡 <b>編者觀點</b>' + rating + '</div>' +
      (has(v.summary) ? '<div class="cd-verdict-sum">' + v.summary + '</div>' : '') +
      forWho +
      '<p class="cd-verdict-disc">以上為個人整理與建議，僅供參考，實際內容以遊戲內為準。</p>' +
    '</div>';
    return section('verdict', '值不值得肝？', body);
  }

  // 「任務挑戰」區塊（例如收集挑戰 Collection Challenge）：標題 + 任務清單 + 完成獎勵
  function renderChallenge(c) {
    var intro = has(c.intro) ? '<p class="cd-ch-intro">' + c.intro + '</p>' : '';
    var tasks = has(c.tasks) ? '<ul class="cd-ch-tasks">' + c.tasks.map(function (t) {
      if (typeof t === 'string') t = { text: t };
      return '<li>' + thumb(t.img, t.text, 'cd-rw-img') +
        '<span class="cd-rw-tx">' + esc(t.text || '') + '</span>' + cpBadge(t.cp15, 15) + '</li>';
    }).join('') + '</ul>' : '';
    var rewards = has(c.rewards)
      ? '<div class="cd-sr-steprw"><span class="cd-sr-steprw-lb">🎁 完成獎勵</span>' +
          '<span class="cd-sr-steprw-list">' + c.rewards.map(function (r) { return rewardChip(r); }).join('') + '</span></div>'
      : '';
    return intro + tasks + rewards;
  }
  function renderCustom(ev) {
    if (!has(ev.customSections)) return '';
    return ev.customSections.map(function (c, i) {
      var body = (c.type === 'challenge')
        ? '<div class="cd-custom cd-challenge">' + renderChallenge(c) + '</div>'
        : '<div class="cd-custom">' + (c.html || '') + '</div>';
      return section('custom-' + i, c.title || '補充', body);
    }).join('');
  }

  function renderFaq(ev) {
    if (!has(ev.faq)) return '';
    var items = ev.faq.map(function (f) {
      return '<details class="cd-faq-item"><summary>' + esc(f.q || '') + '</summary>' +
        '<div class="cd-faq-a">' + (f.a || '') + '</div></details>';
    }).join('');
    return section('faq', '常見問題', '<div class="cd-faq">' + items + '</div>');
  }

  // 站內工具導流：每個社群日頁都用得到，寫死在引擎裡（不必每個月重填）
  function renderTools() {
    return section('tools', '搭配這些工具用',
      '<div class="cd-tools">' +
        '<a class="cd-tool" href="../../?tab=cp-checker-app"><span>💯</span><b>IV100 CP 查詢</b>' +
          '<i>抓到後對一下 CP，就知道是不是滿個體值。</i></a>' +
        '<a class="cd-tool" href="../../pvp-ranker/"><span>🏆</span><b>PvP IV 排名</b>' +
          '<i>對戰聯盟要的個體跟打王不同，這裡查最佳 IV。</i></a>' +
        '<a class="cd-tool" href="../../id-selector/"><span>🔢</span><b>編號篩選器</b>' +
          '<i>活動後要整理 / 篩選寶可夢時很方便。</i></a>' +
      '</div>');
  }

  function renderSources(ev) {
    if (!has(ev.sources)) return '';
    var links = ev.sources.map(function (s) {
      return '<a href="' + esc(s.url) + '" target="_blank" rel="noopener noreferrer">' + esc(s.label || s.url) + '</a>';
    }).join('、');
    return '<p class="src-note">資料來源：' + links + '</p>';
  }

  /* ---- 倒數計時 ----------------------------------------------------------- */
  function startCountdown(times) {
    var statusEl = document.getElementById('cd-status');
    var cdEl = document.getElementById('cd-countdown');
    if (!statusEl || !times) return;

    function box(n, label) {
      return '<div class="cd-cd-box"><span class="cd-cd-num">' + pad(n) + '</span>' +
        '<span class="cd-cd-lb">' + label + '</span></div>';
    }
    function tick() {
      var now = new Date();
      var target, phaseClass, label;
      if (now < times.start) { target = times.start; phaseClass = 'soon'; label = '距離開始還有'; }
      else if (now < times.end) { target = times.end; phaseClass = 'live'; label = '活動進行中，結束倒數'; }
      else {
        statusEl.className = 'cd-status ended';
        statusEl.innerHTML = '<span class="cd-dot"></span>活動已結束';
        cdEl.hidden = true;
        clearInterval(timer);
        return;
      }
      statusEl.className = 'cd-status ' + phaseClass;
      statusEl.innerHTML = '<span class="cd-dot"></span>' +
        (phaseClass === 'live' ? '進行中' : '即將開始') +
        '<span class="cd-status-lb">' + label + '</span>';
      var diff = Math.max(0, Math.floor((target - now) / 1000));
      var d = Math.floor(diff / 86400);
      var h = Math.floor((diff % 86400) / 3600);
      var mi = Math.floor((diff % 3600) / 60);
      var s = diff % 60;
      cdEl.hidden = false;
      cdEl.innerHTML = (d > 0 ? box(d, '天') : '') + box(h, '時') + box(mi, '分') + box(s, '秒');
    }
    tick();
    var timer = setInterval(tick, 1000);
  }

  /* ---- 異色切換 ----------------------------------------------------------- */
  function wireShinyToggle() {
    var btn = document.querySelector('.cd-shiny-toggle');
    var art = document.querySelector('.cd-hero-art');
    if (!btn || !art) return;
    btn.addEventListener('click', function () {
      var on = art.classList.toggle('show-shiny');
      btn.setAttribute('aria-pressed', String(on));
      btn.textContent = on ? '↩ 看一般色' : '✨ 看異色';
    });
  }

  /* ---- 進入點 ------------------------------------------------------------- */
  function render(ev, mountSel) {
    var root = document.querySelector(mountSel || '#cd-root');
    if (!root) return;
    var T = themeVars(ev.types);
    var times = buildTimes(ev);

    root.style.setProperty('--cd-c1', T.c1);
    root.style.setProperty('--cd-c2', T.c2);

    root.innerHTML =
      renderBanner(ev) +
      renderHero(ev, T, times) +
      '<div class="cd-body">' +
        renderBonuses(ev) +
        renderMove(ev) +
        renderEvolution(ev) +
        renderShiny(ev) +
        renderSpecialResearch(ev) +
        renderFieldResearch(ev) +
        renderVerdict(ev) +
        renderCustom(ev) +
        renderFaq(ev) +
        renderTools() +
        renderSources(ev) +
      '</div>';

    startCountdown(times);
    wireShinyToggle();
    var yr = document.getElementById('copyright-year');
    if (yr) yr.textContent = new Date().getFullYear();
  }

  // 給頁面呼叫，或設定好 window.CD_EVENT 後自動渲染
  window.renderCommunityDay = render;
  function auto() { if (window.CD_EVENT) render(window.CD_EVENT, '#cd-root'); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', auto);
  else auto();
}());
