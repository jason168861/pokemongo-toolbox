/* 全站瀏覽計數 —— 把這一次載入加進 Firebase 的 pageviews/total。

   ⚠ 首頁不要載這支。index.html 裡有另一份計數器（用 Firebase SDK 的
     runTransaction，而且還負責把數字顯示出來），兩邊都跑會讓首頁被算兩次。
     這支只負責「加一」，不顯示任何東西。

   為什麼不用 Firebase SDK：
     cp/ 底下那些是輕量的 SEO 落地頁，為了一個計數器多背 100KB 的 SDK
     不划算。改用 REST + ETag 做 compare-and-swap，純 fetch，零依賴。

   為什麼要 compare-and-swap：
     REST 沒有原子性的「加一」。所以先讀值與 ETag，再用 if-match 寫回；
     期間有別人寫過的話 ETag 會對不上，Firebase 回 412，重讀重試。
     （已驗證：if-match 正確 → 200、錯誤 → 412，CORS 也有開放 ETag
      與 if-match，見 Access-Control-Expose-Headers / Allow-Headers。）

   失敗就算了：少算一次瀏覽無所謂，絕對不能影響頁面本身。
*/
(function () {
    var cfg = window.firebaseConfig;
    var base = cfg && cfg.databaseURL;
    if (!base) return;                       // config.js 沒載到（本機開發）→ 靜默停用

    var URL_ = base.replace(/\/+$/, '') + '/pageviews/total.json';

    function bump(triesLeft) {
        if (triesLeft <= 0) return;          // 撞太多次就放棄，不要無限重試
        fetch(URL_, { headers: { 'X-Firebase-ETag': 'true' } })
            .then(function (res) {
                var etag = res.headers.get('ETag');
                return res.json().then(function (v) {
                    return { etag: etag, n: typeof v === 'number' ? v : 0 };
                });
            })
            .then(function (cur) {
                if (!cur.etag) return;       // 讀不到 ETag 就沒辦法安全地加一
                return fetch(URL_, {
                    method: 'PUT',
                    headers: { 'if-match': cur.etag, 'Content-Type': 'application/json' },
                    body: String(cur.n + 1)
                }).then(function (res) {
                    // 412 = 這中間有人寫過了，重讀最新值再試
                    if (res.status === 412) bump(triesLeft - 1);
                });
            })
            .catch(function () { /* 計數器壞掉不能影響頁面 */ });
    }

    // 等頁面載完再送，不要跟首屏搶頻寬（尤其 cp/ 是要跑 SEO 分數的頁面）
    function start() { setTimeout(function () { bump(3); }, 400); }
    if (document.readyState === 'complete') start();
    else window.addEventListener('load', start);
})();
