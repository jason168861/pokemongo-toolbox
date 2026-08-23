/* 使用行為分析(GA4)。全站共用這一支,事件定義集中在這裡。

   ⚠ 開始收資料前要先填 GA_ID(GA4 後台 → 管理 → 資料串流 → 網頁 → 「評估 ID」,
      長得像 G-XXXXXXXXXX)。沒填就整支停用,不會載入任何外部腳本、也不會報錯。
      評估 ID 不是機密 —— 它本來就會出現在網頁原始碼裡,寫死沒問題。

   ⚠ 絕對不要送出去的東西:訓練家代碼、卡片備註、分享連結的 ?s= id。
      那些是使用者的個資 / 私人內容。track() 有一層 clean() 擋掉數字串,
      但真正的防線是「呼叫端不要把那些欄位傳進來」。
*/
window.GA_ID = 'G-TXSLDX2J4X';   // GA4「pogokit」資源的評估 ID

(function () {
  const ID = window.GA_ID;
  if (!ID || !/^G-[A-Z0-9]+$/i.test(ID)) {           // 沒設定 → 靜默停用
    window.track = function () {};
    return;
  }

  const s = document.createElement('script');
  s.async = true;
  s.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(ID);
  document.head.appendChild(s);

  window.dataLayer = window.dataLayer || [];
  function gtag() { dataLayer.push(arguments); }
  window.gtag = gtag;
  gtag('js', new Date());
  gtag('config', ID);

  /* 送出前的清洗:
     - 疑似訓練家代碼(連續 8 碼以上數字,允許中間有空白/連字號)→ 整個丟掉
     - 字串一律截短,避免有人把一整段文字貼進搜尋框
     - 只收字串與數字,其他型別忽略 */
  const CODE = /\d[\d\s-]{6,}\d/;
  function clean(v) {
    if (typeof v === 'number') return v;
    if (typeof v !== 'string') return undefined;
    const t = v.trim();
    if (!t || CODE.test(t)) return undefined;
    return t.slice(0, 80);
  }

  window.track = function (name, params) {
    try {
      const out = {};
      for (const k in (params || {})) {
        const v = clean(params[k]);
        if (v !== undefined) out[k] = v;
      }
      gtag('event', name, out);
    } catch (e) { /* 分析壞掉不能影響功能 */ }
  };
})();

/* 搜尋框用:只有「打完字而且找不到東西」才回報。
   這是整套裡最有價值的事件 —— 使用者打了什麼卻找不到,直接回頭補 data/aliases.json。
   逐個按鍵都送的話,「噴火龍」會變成「噴」「噴火」「噴火龍」三筆垃圾,所以要等他停手。 */
window.trackNoResult = (function () {
  let timer = null, last = '';
  return function (where, query, count) {
    clearTimeout(timer);
    const q = String(query || '').trim();
    if (count > 0 || q.length < 2 || q === last) return;
    timer = setTimeout(function () {
      last = q;
      window.track('search_no_result', { where: where, term: q });
    }, 1200);          // 停手 1.2 秒才算「打完了」
  };
})();
