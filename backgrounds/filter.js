/* 背卡一覽：搜尋、篩選、兩種檢視（背卡／寶可夢）與詳細對話框。
   所有背卡與寶可夢名單都已經在 HTML 裡（給 Google 看得到）；
   「寶可夢」檢視是第一次切過去時，從同一份 DOM 整理出來的，不另外載資料。 */
(function () {
    var q = document.getElementById('q');
    var grid = document.getElementById('grid');
    var mgrid = document.getElementById('mgrid');
    var countEl = document.getElementById('count');
    var emptyEl = document.getElementById('empty');
    if (!grid) return;

    var cards = [].slice.call(grid.querySelectorAll('.bgcard'));
    var total = cards.length;
    var mode = 'all';
    var view = 'bg';

    // 全站共用的繁簡正規化（js/zh-search.js）。沒載到就退回單純小寫。
    var norm = window.zhLower || function (s) { return String(s == null ? '' : s).toLowerCase(); };

    cards.forEach(function (c) {
        c._q = norm(c.dataset.q);
        c._who = c.querySelector('.who');
        c._whoText = c._who ? c._who.textContent : '';
        c._title = c.querySelector('h3').textContent;
        c._nt = norm(c._title);
        c._names = null;
    });

    function okMode(card, shiny) {
        if (mode === 'all') return true;
        if (mode === 'noshiny') return shiny === undefined ? card.dataset.noshiny === '1' : !shiny;
        return card.dataset.kind === mode;
    }

    // 用寶可夢名搜到的背卡，把「符合的寶可夢」換到名單那一行，
    // 不然 150 隻的大背卡只看得到妙蛙種子，不知道為什麼會出現。
    function showWho(c, term) {
        if (!c._who) return;
        var reset = function () { if (c._whoHit) { c._who.textContent = c._whoText; c._whoHit = false; } };
        if (!term || c._nt.indexOf(term) !== -1) return reset();
        if (!c._names) {
            c._names = [].map.call(c.querySelectorAll('.more .mon-name'), function (el) {
                return { t: el.textContent, n: norm(el.textContent) };
            });
        }
        var hit = c._names.filter(function (x) { return x.n.indexOf(term) !== -1; }).map(function (x) { return x.t; });
        if (!hit.length) return reset();
        var b = document.createElement('b');
        b.textContent = '符合：';
        c._who.textContent = '';
        c._who.appendChild(b);
        c._who.appendChild(document.createTextNode(hit.join('、')));
        c._whoHit = true;
    }

    // ---- 寶可夢檢視的資料：從每張卡的名單整理（同一隻同造型只算一次） ----
    var mons = null;
    function buildMons() {
        var map = {}, list = [];
        cards.forEach(function (c) {
            [].forEach.call(c.querySelectorAll('.more li[data-k]'), function (li) {
                var k = li.dataset.k;
                var m = map[k];
                if (!m) {
                    var img = li.querySelector('img');
                    m = map[k] = {
                        k: k, dex: +li.dataset.d,
                        name: li.querySelector('.mon-name').textContent,
                        src: img ? img.getAttribute('src') : '', w: img ? +img.getAttribute('width') : 0, h: img ? +img.getAttribute('height') : 0,
                        bgs: []
                    };
                    m.n = norm(m.name);
                    list.push(m);
                }
                m.bgs.push({ card: c, shiny: li.dataset.s === '1' });
            });
        });
        list.sort(function (a, b) { return a.dex - b.dex || a.name.localeCompare(b.name, 'zh-Hant'); });
        var frag = document.createDocumentFragment();
        list.forEach(function (m) {
            var t = document.createElement('button');
            t.type = 'button';
            t.className = 'mtile';
            var st = document.createElement('div');
            st.className = 'mstage';
            m.bgs.slice(0, 3).forEach(function (x, i) {
                var s = x.card.querySelector('.scene');
                if (!s) return;
                var d = document.createElement('img');
                d.className = 'deck d' + i;
                d.alt = '';
                d.loading = 'lazy';
                d.decoding = 'async';
                d.width = d.height = 220;
                d.src = s.getAttribute('srcset') ? s.getAttribute('srcset').split(' ')[0] : s.getAttribute('src');   // 220px 那張
                st.appendChild(d);
            });
            if (m.src) {
                var im = document.createElement('img');
                im.className = 'mon';
                im.src = m.src; im.alt = ''; im.loading = 'lazy'; im.decoding = 'async';
                im.width = m.w; im.height = m.h;
                st.appendChild(im);
            }
            var cnt = document.createElement('span');
            cnt.className = 'mcount';
            st.appendChild(cnt);
            var cap = document.createElement('span');
            cap.className = 'mcap';
            var nm = document.createElement('span'); nm.className = 'mn'; nm.textContent = m.name;
            var mc = document.createElement('span'); mc.className = 'mc';
            cap.appendChild(nm); cap.appendChild(mc);
            t.appendChild(st); t.appendChild(cap);
            t.addEventListener('click', function () { openMon(m); });
            m.el = t; m.cnt = cnt; m.mc = mc;
            frag.appendChild(t);
        });
        mgrid.appendChild(frag);
        return list;
    }

    function apply() {
        var term = norm(q.value.trim());
        var shown = 0;
        if (view === 'bg') {
            cards.forEach(function (c) {
                var show = okMode(c) && (!term || c._q.indexOf(term) !== -1);
                c.hidden = !show;
                if (show) { shown++; showWho(c, term); }
            });
            countEl.textContent = shown === total ? '共 ' + total + ' 張背卡' : '符合 ' + shown + ' 張・全部 ' + total + ' 張背卡';
        } else {
            mons.forEach(function (m) {
                var hit = 0;
                if (!term || m.n.indexOf(term) !== -1) {
                    m.bgs.forEach(function (x) { if (okMode(x.card, x.shiny)) hit++; });
                }
                m.el.hidden = !hit;
                if (hit) {
                    shown++;
                    m.cnt.textContent = hit;
                    m.mc.textContent = hit + ' 張背卡';
                }
            });
            countEl.textContent = shown === mons.length ? '共 ' + mons.length + ' 種寶可夢（含造型）' : '符合 ' + shown + ' 種・全部 ' + mons.length + ' 種寶可夢';
        }
        emptyEl.hidden = shown !== 0;
        // 搜尋不到東西才回報,而且要等使用者停手（見 js/analytics.js）；兩種檢視分開記
        if (window.trackNoResult) window.trackNoResult(view === 'bg' ? 'bgindex' : 'bgindex_mon', q.value, shown);
    }

    var t;
    q.addEventListener('input', function () { clearTimeout(t); t = setTimeout(apply, 120); });

    var fbtns = [].slice.call(document.querySelectorAll('.f'));
    fbtns.forEach(function (b) {
        b.addEventListener('click', function () {
            fbtns.forEach(function (x) { x.classList.remove('on'); x.setAttribute('aria-pressed', 'false'); });
            b.classList.add('on'); b.setAttribute('aria-pressed', 'true');
            mode = b.dataset.f;
            apply();
        });
    });

    var vbtns = [].slice.call(document.querySelectorAll('.v'));
    function setView(v, fromHash) {
        if (v === view) return;
        view = v;
        if (v === 'mon' && !mons) mons = buildMons();
        vbtns.forEach(function (x) { var on = x.dataset.v === v; x.classList.toggle('on', on); x.setAttribute('aria-selected', on ? 'true' : 'false'); });
        grid.hidden = v !== 'bg';
        mgrid.hidden = v !== 'mon';
        q.placeholder = v === 'bg' ? '搜尋背卡或寶可夢（簡體也可以）' : '搜尋寶可夢，看牠有哪些背卡';
        apply();
        if (!fromHash) {
            try { history.replaceState(null, '', v === 'mon' ? '#pokemon' : location.pathname + location.search); } catch (e) {}
            var top = document.getElementById('all').getBoundingClientRect().top;
            if (top < 0) document.getElementById('all').scrollIntoView();
        }
        if (window.track) window.track('bgindex_view', { view: v });
    }
    vbtns.forEach(function (b) { b.addEventListener('click', function () { setView(b.dataset.v); }); });

    apply();
    if (location.hash === '#pokemon') setView('mon', true);

    // ================= 詳細對話框 =================
    var sheet = document.getElementById('sheet');
    if (!sheet || typeof sheet.showModal !== 'function') {
        document.documentElement.classList.remove('js');   // 不支援 <dialog>：讓 <details> 名單照常顯示
        return;
    }
    var sStage = document.getElementById('sheet-stage');
    var sKind = document.getElementById('sheet-kind');
    var sTitle = document.getElementById('sheet-title');
    var sMeta = document.getElementById('sheet-meta');
    var sList = document.getElementById('sheet-list');
    var sBody = sheet.querySelector('.sheet-body');
    var lastFocus = null;

    function el(tag, cls, text) { var x = document.createElement(tag); if (cls) x.className = cls; if (text != null) x.textContent = text; return x; }
    function cloneImg(img, cls) { var x = img.cloneNode(false); x.removeAttribute('loading'); if (cls) x.className = cls; return x; }

    function show() {
        sBody.scrollTop = 0;
        if (!sheet.open) {
            lastFocus = document.activeElement;
            document.documentElement.classList.add('sheet-lock');
            sheet.showModal();
            sBody.focus({ preventScroll: true });   // 焦點放內容，不要停在關閉鈕上（會出現一圈外框）
        }
    }

    // 背卡：上方大舞台（最多 4 隻），下方全部寶可夢方塊
    function openBg(card) {
        sStage.className = 'sheet-stage';
        sStage.textContent = '';
        var scene = card.querySelector('.scene');
        if (scene) { var sc = cloneImg(scene); sc.sizes = '880px'; sStage.appendChild(sc); }
        var lis = [].slice.call(card.querySelectorAll('.more li'));
        var cast = el('div', 'cast');
        lis.slice(0, 4).forEach(function (li) { var im = li.querySelector('img'); if (im) { var c = cloneImg(im, ''); c.alt = ''; cast.appendChild(c); } });
        cast.className = 'cast c' + Math.min(cast.children.length, 4);
        sStage.appendChild(cast);
        sKind.textContent = (card.querySelector('.kind') || {}).textContent || '';
        sTitle.textContent = card._title;
        sMeta.textContent = card.querySelector('.meta').textContent.replace(/隻寶可夢(?=\S)/, '隻寶可夢・');
        sList.textContent = '';
        var ul = card.querySelector('.more .mons').cloneNode(true);
        [].forEach.call(ul.querySelectorAll('img'), function (im) { im.loading = 'lazy'; });
        sList.appendChild(ul);
        show();
        if (window.track) window.track('bgindex_open', { bg: card._title.slice(0, 80) });
    }

    // 寶可夢：上方是牠站在第一張背卡（模糊）前，下方是牠出現的每張背卡（小舞台，可再點開）
    function openMon(m) {
        sStage.className = 'sheet-stage solo';
        sStage.textContent = '';
        var first = m.bgs[0] && m.bgs[0].card.querySelector('.scene');
        if (first) sStage.appendChild(cloneImg(first));
        var cast = el('div', 'cast c1');
        if (m.src) { var im = el('img'); im.src = m.src; im.alt = ''; im.width = m.w; im.height = m.h; cast.appendChild(im); }
        sStage.appendChild(cast);
        var list = m.bgs.filter(function (x) { return okMode(x.card, x.shiny); });
        sKind.textContent = '#' + m.dex;
        sTitle.textContent = m.name;
        sMeta.textContent = '出現在 ' + list.length + ' 張背卡' + (list.some(function (x) { return !x.shiny; }) ? '・部分尚無異色' : '・都有異色');
        sList.textContent = '';
        var box = el('div', 'bglist');
        list.forEach(function (x) {
            var b = el('button');
            b.type = 'button';
            var st = el('div', 'stage');
            var s = x.card.querySelector('.scene');
            if (s) { var sc = cloneImg(s); sc.loading = 'lazy'; sc.sizes = '160px'; st.appendChild(sc); }
            var c = el('div', 'cast c1');
            if (m.src) { var mi = el('img'); mi.src = m.src; mi.alt = ''; mi.loading = 'lazy'; mi.width = m.w; mi.height = m.h; c.appendChild(mi); }
            st.appendChild(c);
            var bt = el('span', 'bt', x.card._title);
            bt.appendChild(el('small', '', ((x.card.querySelector('.kind') || {}).textContent || '') + (x.shiny ? '' : '・尚無異色')));
            b.appendChild(st); b.appendChild(bt);
            b.addEventListener('click', function () { openBg(x.card); });
            box.appendChild(b);
        });
        sList.appendChild(box);
        show();
        if (window.track) window.track('bgindex_open_mon', { mon: m.name.slice(0, 80) });
    }

    function close() { if (sheet.open) sheet.close(); }
    sheet.addEventListener('close', function () {
        document.documentElement.classList.remove('sheet-lock');
        if (lastFocus && lastFocus.focus) lastFocus.focus({ preventScroll: true });
    });
    sheet.querySelector('.sheet-x').addEventListener('click', close);
    sheet.addEventListener('click', function (e) { if (e.target === sheet) close(); });   // 點外面（backdrop）關閉

    // 整張背卡都可以點；鍵盤使用者靠卡片上的 tabindex + Enter
    cards.forEach(function (c) {
        c.tabIndex = 0;
        c.setAttribute('role', 'button');
        c.setAttribute('aria-label', c._title + '，看全部寶可夢');
    });
    grid.addEventListener('click', function (e) {
        var card = e.target.closest('.bgcard');
        if (!card || e.target.closest('a')) return;
        e.preventDefault();
        openBg(card);
    });
    grid.addEventListener('keydown', function (e) {
        if ((e.key === 'Enter' || e.key === ' ') && e.target.classList.contains('bgcard')) { e.preventDefault(); openBg(e.target); }
    });
})();
