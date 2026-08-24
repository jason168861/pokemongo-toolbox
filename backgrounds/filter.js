/* 背卡一覽的搜尋與篩選。
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
    cards.forEach(function (c) { c._q = norm(c.dataset.q); });

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
            if (show) shown++;
        });
        countEl.textContent = shown === total
            ? '共 ' + total + ' 張背卡'
            : '符合的有 ' + shown + ' 張（全部 ' + total + ' 張）';
        emptyEl.hidden = shown !== 0;

        // 搜尋不到東西才回報,而且要等使用者停手（見 js/analytics.js）
        if (window.trackNoResult) window.trackNoResult('bgindex', q.value, shown);
    }

    var t;
    q.addEventListener('input', function () {
        clearTimeout(t);
        t = setTimeout(apply, 120);   // 230 張卡,不需要每個按鍵都重算
    });

    [].forEach.call(document.querySelectorAll('.f'), function (b) {
        b.addEventListener('click', function () {
            document.querySelectorAll('.f').forEach(function (x) { x.classList.remove('on'); });
            b.classList.add('on');
            mode = b.dataset.f;
            apply();
        });
    });

    apply();
})();
