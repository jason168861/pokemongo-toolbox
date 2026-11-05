/* 背卡一覽的搜尋、篩選與「完整名單」對話框。
   卡片全部都已經在 HTML 裡（給 Google 看得到），這裡只負責顯示/隱藏。 */
(function () {
    var q = document.getElementById('q');
    var grid = document.getElementById('grid');
    var countEl = document.getElementById('count');
    var emptyEl = document.getElementById('empty');
    if (!grid) return;

    var cards = [].slice.call(grid.querySelectorAll('.bgcard'));
    var total = cards.length;
    var mode = 'all';

    // 全站共用的繁簡正規化（js/zh-search.js）。沒載到就退回單純小寫。
    var norm = window.zhLower || function (s) { return String(s == null ? '' : s).toLowerCase(); };

    // data-q 是產生頁面時就寫好的（背卡名 + 全部寶可夢中文名），
    // 但它是繁體，所以這裡先轉一次存起來，之後每次搜尋就不用重算。
    cards.forEach(function (c) {
        c._q = norm(c.dataset.q);
        c._who = c.querySelector('.who');
        c._whoText = c._who ? c._who.textContent : '';
        c._title = norm(c.querySelector('h3').textContent);
        c._names = null;   // 第一次用寶可夢名搜尋時才建
    });

    // 用寶可夢名搜到的卡片，把「符合的寶可夢」換到名單那一行最前面，
    // 不然 150 隻的大背卡只看得到妙蛙種子，不知道為什麼會出現。
    function showWho(c, term) {
        if (!c._who) return;
        if (!term || c._title.indexOf(term) !== -1) {
            if (c._whoHit) { c._who.textContent = c._whoText; c._whoHit = false; }
            return;
        }
        if (!c._names) {
            c._names = [].map.call(c.querySelectorAll('.more .mon-name'), function (el) {
                return { t: el.textContent, n: norm(el.textContent) };
            });
        }
        var hit = c._names.filter(function (x) { return x.n.indexOf(term) !== -1; }).map(function (x) { return x.t; });
        if (!hit.length) { if (c._whoHit) { c._who.textContent = c._whoText; c._whoHit = false; } return; }
        var b = document.createElement('b');
        b.textContent = '符合：';
        c._who.textContent = '';
        c._who.appendChild(b);
        c._who.appendChild(document.createTextNode(hit.join('、')));
        c._whoHit = true;
    }

    function apply() {
        var term = norm(q.value.trim());
        var shown = 0;
        cards.forEach(function (c) {
            var okMode =
                mode === 'all' ? true :
                mode === 'noshiny' ? c.dataset.noshiny === '1' :
                c.dataset.kind === mode;
            var okTerm = !term || c._q.indexOf(term) !== -1;
            var show = okMode && okTerm;
            c.hidden = !show;
            if (show) { shown++; showWho(c, term); }
        });
        countEl.textContent = shown === total
            ? '共 ' + total + ' 張背卡'
            : '符合 ' + shown + ' 張・全部 ' + total + ' 張';
        emptyEl.hidden = shown !== 0;

        // 搜尋不到東西才回報,而且要等使用者停手（見 js/analytics.js）
        if (window.trackNoResult) window.trackNoResult('bgindex', q.value, shown);
    }

    var t;
    q.addEventListener('input', function () {
        clearTimeout(t);
        t = setTimeout(apply, 120);   // 兩百多張卡,不需要每個按鍵都重算
    });

    var btns = [].slice.call(document.querySelectorAll('.f'));
    btns.forEach(function (b) {
        b.addEventListener('click', function () {
            btns.forEach(function (x) { x.classList.remove('on'); x.setAttribute('aria-pressed', 'false'); });
            b.classList.add('on');
            b.setAttribute('aria-pressed', 'true');
            mode = b.dataset.f;
            apply();
        });
    });

    apply();

    // ---- 完整名單對話框 ----
    // 名單本來就在每張卡的 <details> 裡；有 <dialog> 支援時，點卡片改用對話框顯示同一份內容，
    // 不支援的舊瀏覽器就維持 <details> 在卡片裡展開。
    var sheet = document.getElementById('sheet');
    if (!sheet || typeof sheet.showModal !== 'function') return;
    var sImg = document.getElementById('sheet-img');
    var sKind = document.getElementById('sheet-kind');
    var sTitle = document.getElementById('sheet-title');
    var sMeta = document.getElementById('sheet-meta');
    var sList = document.getElementById('sheet-list');
    var lastCard = null;

    function open(card) {
        var img = card.querySelector('.bgshot img');
        var list = card.querySelector('.more .mons');
        sImg.src = img ? img.currentSrc || img.src : '';
        sImg.alt = img ? img.alt : '';
        sKind.textContent = (card.querySelector('.kind') || {}).textContent || '';
        sTitle.textContent = card.querySelector('h3').textContent;
        sMeta.textContent = card.querySelector('.meta').textContent;
        sList.innerHTML = list ? list.innerHTML : '';   // 同一份頁面內產生的內容，非使用者輸入
        sList.scrollTop = 0;
        lastCard = card;
        document.documentElement.classList.add('sheet-lock');
        sheet.showModal();
        sheet.querySelector('.sheet-body').scrollTop = 0;
        if (window.track) window.track('bgindex_open', { bg: sTitle.textContent.slice(0, 80) });
    }
    function close() { if (sheet.open) sheet.close(); }

    sheet.addEventListener('close', function () {
        document.documentElement.classList.remove('sheet-lock');
        if (lastCard) { var s = lastCard.querySelector('summary'); if (s) s.focus({ preventScroll: true }); }
    });
    sheet.querySelector('.sheet-x').addEventListener('click', close);
    // 點對話框外面（backdrop）關閉
    sheet.addEventListener('click', function (e) { if (e.target === sheet) close(); });

    grid.addEventListener('click', function (e) {
        var card = e.target.closest('.bgcard');
        if (!card) return;
        if (e.target.closest('a')) return;
        e.preventDefault();   // 攔下 <summary> 的展開
        open(card);
    });
    // 卡片本身可用鍵盤：<summary> 已經可以 focus，Enter/Space 會觸發 click
})();
