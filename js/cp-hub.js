// 各語言 IV100 CP 列表頁（/<lang>/cp/）的搜尋。
// 沒輸入時顯示人氣寶可夢；輸入後改搜全部寶可夢與型態（all.json，第一次互動時才載入）。
// 有靜態頁的連過去，沒有的直接顯示 Lv15／20／25 的 100% CP。
// 介面文字在頁面上的 #hubL（站內寫死的字串）；寶可夢名稱來自 all.json（官方文字），一律轉義後才放進 innerHTML。
(function () {
  var q = document.getElementById('hubq'), res = document.getElementById('res'), msg = document.getElementById('resmsg'),
      pop = document.getElementById('popwrap'), lab = document.getElementById('hubL');
  if (!q || !res || !msg || !pop || !lab) return;
  var L = JSON.parse(lab.textContent), D = null, loading = null, MAX = 40;
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; });
  }
  function load() {
    if (D) return Promise.resolve(D);
    if (!loading) loading = fetch('all.json').then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (j) { D = j; return j; })
      .catch(function (e) { loading = null; throw e; });   // 失敗就清掉，下次輸入會重試
    return loading;
  }
  function cp(lv, v) { return esc(L.lv) + lv + ' ' + esc(L.cp) + ' ' + v; }
  function render() {
    var v = q.value.trim().toLowerCase();
    if (!v) { res.hidden = true; msg.hidden = true; pop.hidden = false; return; }
    load().then(function (rows) {
      if (q.value.trim().toLowerCase() !== v) return;   // 載入期間又改了字
      // 列：[名稱, 圖鑑編號, Lv15, Lv20, Lv25, Lv40, Lv50, slug, 圖檔, 英文名]
      var hit = rows.filter(function (r) { return String(r[1]) === v || r[0].toLowerCase().indexOf(v) >= 0 || r[9].indexOf(v) >= 0; });
      pop.hidden = true;
      res.hidden = !hit.length;
      msg.hidden = hit.length > 0 && hit.length <= MAX;
      msg.textContent = hit.length ? L.more.replace('{n}', MAX) : L.none;
      res.innerHTML = hit.slice(0, MAX).map(function (r) {
        var img = '<img src="' + esc(L.img + r[8]) + '" alt="" width="48" height="48" loading="lazy">';
        if (r[7]) return '<a href="' + esc(r[7]) + '/">' + img + '<span>' + esc(r[0]) + '<small>' + cp(20, r[3]) + '</small></span></a>';
        return '<div>' + img + '<span>' + esc(r[0]) + ' <small>#' + r[1] + ' · ' + cp(15, r[2]) + ' · ' + cp(20, r[3]) + ' · ' + cp(25, r[4]) + '</small></span></div>';
      }).join('');
    }).catch(function () { res.hidden = true; pop.hidden = false; msg.hidden = false; msg.textContent = L.err || L.none; });
  }
  q.addEventListener('input', render);
  q.addEventListener('focus', function () { load().catch(function () {}); }, { once: true });
})();
