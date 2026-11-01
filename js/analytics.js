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

  /* 同意聲明模式(Consent Mode)的預設值。
     ⚠ 一定要在 config 之前送出,否則第一個 pageview 已經帶著 cookie 出去了。

     只對 EEA + 英國 + 瑞士預設「拒絕」——GA4 在這個狀態下不寫 cookie,改送不含識別碼的
     訊號。沒列到的地區(台灣、日本、美國…)維持預設的「允許」,不影響主要客群的數字。
     使用者在同意橫幅按下之後,CMP 會再送一次 'update' 把狀態改掉。
     wait_for_update:給 CMP 500ms 的時間先表態,免得搶在它前面就用預設值送出。

     橫幅本身不在這裡 —— 是 AdSense →「隱私權與訊息」建立的 Funding Choices,
     發布後會自動注入並負責送 update。這裡只負責「在它出現之前不要亂寫 cookie」。 */
  var EEA = ['AT','BE','BG','HR','CY','CZ','DK','EE','FI','FR','DE','GR','HU','IS','IE','IT',
             'LV','LI','LT','LU','MT','NL','NO','PL','PT','RO','SK','SI','ES','SE','GB','CH'];
  gtag('consent', 'default', {
    ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied',
    analytics_storage: 'denied',
    region: EEA, wait_for_update: 500
  });

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

  /* 慢互動歸因(INP 診斷用)。
     CrUX 只說手機 INP 偏高,看不出是哪個按鈕慢。這裡在頁面被隱藏(切 App、關分頁、換頁)時,
     把這段期間「最慢的一次互動」送成 slow_interaction 事件;只有 ≥ 200ms(INP「需要改善」門檻)才送。
     送出的只有:互動類型、目標元素的「標籤 + id 或第一個 class」(寫在程式碼裡的名稱)、
     三段耗時、互動當時頁面是否還在載入。不送元素裡的文字、輸入值或任何使用者輸入的內容。
     只有支援 Event Timing API 的瀏覽器(Chromium 系)會有資料,其他瀏覽器什麼都不做。 */
  try {
    if (!window.PerformanceObserver ||
        (PerformanceObserver.supportedEntryTypes || []).indexOf('event') < 0) return;
    const SLOW = 200;
    const desc = function (el) {
      if (!el || el.nodeType !== 1) return '';
      let d = el.tagName.toLowerCase();
      if (el.id) d += '#' + el.id;
      else if (typeof el.className === 'string' && el.className.trim()) d += '.' + el.className.trim().split(/\s+/)[0];
      return d;
    };
    // 互動後元素常被重繪移除(entry.target 會變 null),所以事件當下先記下描述,
    // 再用 event.timeStamp(= entry.startTime)對回去。只留最近幾筆。
    const recent = [];
    const remember = function (ev) {
      recent.push([ev.timeStamp, desc(ev.target)]);
      if (recent.length > 20) recent.shift();
    };
    ['pointerdown', 'pointerup', 'click', 'keydown', 'keyup'].forEach(function (t) {
      addEventListener(t, remember, { capture: true, passive: true });
    });
    const lookup = function (t) {
      for (let i = recent.length - 1; i >= 0; i--) if (Math.abs(recent[i][0] - t) < 1) return recent[i][1];
      return '';
    };

    // 目前最慢的一次互動。一次點擊會有 pointerdown / pointerup / click 好幾筆 entry
    // (同一個 interactionId),要合併起來算,不然耗時會被算在第一筆 pointerdown 上。
    let worst = null;
    new PerformanceObserver(function (list) {
      list.getEntries().forEach(function (e) {
        if (!e.interactionId || e.duration < SLOW) return;
        let w = worst && worst.id === e.interactionId ? worst : null;
        if (!w) {
          if (worst && e.duration <= worst.dur) return;
          w = { id: e.interactionId, start: e.startTime, dur: 0, ps: Infinity, pe: 0, proc: 0, pmax: -1, type: '', target: '' };
        }
        const p = e.processingEnd - e.processingStart;
        w.start = Math.min(w.start, e.startTime);
        w.dur = Math.max(w.dur, e.duration);
        w.ps = Math.min(w.ps, e.processingStart);
        w.pe = Math.max(w.pe, e.processingEnd);
        w.proc += p;
        if (p > w.pmax) { w.pmax = p; w.type = e.name; }   // 類型以「處理最久」的那個事件為準
        w.target = w.target || desc(e.target) || lookup(e.startTime);
        worst = w;
      });
    }).observe({ type: 'event', durationThreshold: SLOW, buffered: true });

    const flush = function () {
      if (!worst) return;
      const w = worst; worst = null;     // 送過就清掉;回到頁面後再有更慢的互動會另外送一筆
      const nav = performance.getEntriesByType('navigation')[0];
      window.track('slow_interaction', {
        value: Math.round(w.dur),
        interaction_type: w.type,
        interaction_target: w.target || '(unknown)',
        input_delay: Math.max(0, Math.round(w.ps - w.start)),
        processing_time: Math.round(w.proc),
        presentation_delay: Math.max(0, Math.round(w.start + w.dur - w.pe)),
        load_state: nav && nav.loadEventEnd && w.start > nav.loadEventEnd ? 'after_load' : 'during_load'
      });
    };
    addEventListener('visibilitychange', function () { if (document.visibilityState === 'hidden') flush(); });
    addEventListener('pagehide', flush);
  } catch (e) { /* 量測壞掉不能影響功能 */ }
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
