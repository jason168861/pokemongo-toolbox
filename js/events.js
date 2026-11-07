// 活動頁互動（頁面內容由 scripts/build_event_pages.py 預先產生在 HTML 裡，這支只做補強）：
// 倒數與狀態、時間軸「現在」標記、目錄黏在表頭下並高亮、異色切換、分享。
(function () {
  'use strict';

  // data-start="2026-11-21T14:00"：活動是「當地時間」，所以用裝置時區解讀（不要用 Date.parse，會被當 UTC）
  function local(s) {
    var m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(s || '');
    return m ? new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]) : null;
  }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function span(ms) {
    var s = Math.max(0, Math.floor(ms / 1000)), d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600),
        m = Math.floor(s % 3600 / 60), sec = s % 60;
    if (d >= 1) return d + '<i>天</i>' + h + '<i>時</i>' + pad(m) + '<i>分</i>';
    return h + '<i>時</i>' + pad(m) + '<i>分</i>' + pad(sec) + '<i>秒</i>';
  }

  function daily(spec, now) {
    var m = /^(\d{2}):(\d{2})-(\d{2}):(\d{2})$/.exec(spec || '');
    if (!m) return null;
    var d = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return { a: new Date(d.getTime() + (+m[1] * 60 + +m[2]) * 60000), b: new Date(d.getTime() + (+m[3] * 60 + +m[4]) * 60000) };
  }

  var evs = [].slice.call(document.querySelectorAll('[data-ev]'));
  function tick() {
    var now = new Date();
    evs.forEach(function (el) {
      var s = local(el.dataset.start), e = local(el.dataset.end), x = local(el.dataset.ext) || e;
      if (!s || !e) return;
      var pill = el.querySelector('[data-pill]'), count = el.querySelector('[data-count]');
      var st, txt, c = '';
      var dw = daily(el.dataset.daily, now);   // 多天活動、每天固定時段（例：10:00-18:00）
      if (now < s) { st = ''; txt = '即將開始'; c = '還有 ' + span(s - now); }
      else if (dw && now < e && now < dw.a) { st = ''; txt = '今天稍後開始'; c = '還有 ' + span(dw.a - now); }
      else if (dw && now < e && now >= dw.b) {
        var next = new Date(dw.a.getTime() + 86400000);
        if (next < e) { st = ''; txt = '今日時段結束'; c = '明天開始還有 ' + span(next - now); }
        else { st = 'is-ended'; txt = '已結束'; }
      }
      else if (now < e) { st = 'is-live'; txt = '進行中'; c = (dw ? '今天時段還有 ' + span(dw.b - now) : '距離結束 ' + span(e - now)); }
      else if (now < x) { st = 'is-ext'; txt = '延長加成中'; c = '延長加成還有 ' + span(x - now); }
      else { st = 'is-ended'; txt = '已結束'; c = ''; }
      if (pill) { pill.className = 'ev-pill ' + st; pill.textContent = txt; }
      if (count) count.innerHTML = c;
      if (el.classList.contains('ev-card')) el.classList.toggle('is-ended', st === 'is-ended');
    });
    // 時段棲息地：活動當天標出現在這個小時
    var hrs = document.querySelector('[data-hours]'), main = document.querySelector('.ev-hero [data-ev]');
    if (hrs && main) {
      var s0 = local(main.dataset.start), e0 = local(main.dataset.end);
      var onDay = s0 && e0 && now >= new Date(s0.getFullYear(), s0.getMonth(), s0.getDate()) && now <= e0;
      [].forEach.call(hrs.children, function (li) {
        var h = parseInt(li.dataset.hour, 10);
        li.classList.toggle('is-now', !!onDay && now.getHours() === h);
        li.classList.toggle('is-past', !!onDay && now.getHours() > h);
      });
    }
    var tl = document.querySelector('[data-tl]');
    if (tl) {
      var a = local(tl.dataset.start), b = local(tl.dataset.end), mark = tl.querySelector('[data-now]');
      if (a && b && mark) {
        var inside = now >= a && now <= b;
        mark.hidden = !inside;
        if (inside) mark.style.left = ((now - a) / (b - a) * 100).toFixed(2) + '%';
      }
    }
  }
  if (evs.length) { tick(); setInterval(tick, 1000); }

  // 表頭是 sticky（css/main.css），目錄要貼在它下面
  var hdr = document.querySelector('.site-header-main');
  function setHdr() { if (hdr) document.documentElement.style.setProperty('--hdr', hdr.offsetHeight + 'px'); }
  setHdr(); window.addEventListener('resize', setHdr);

  // 目錄高亮
  var links = [].slice.call(document.querySelectorAll('.ev-toc a'));
  if (links.length && 'IntersectionObserver' in window) {
    var byId = {};
    links.forEach(function (a) { byId[a.getAttribute('href').slice(1)] = a; });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        links.forEach(function (a) { a.classList.remove('is-on'); });
        var a = byId[en.target.id];
        if (a) { a.classList.add('is-on'); a.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' }); }
      });
    }, { rootMargin: '-35% 0px -60% 0px' });
    Object.keys(byId).forEach(function (id) { var s = document.getElementById(id); if (s) io.observe(s); });
  }

  // 異色切換（每個區塊各自一顆）
  [].forEach.call(document.querySelectorAll('[data-shiny]'), function (tg) {
    tg.addEventListener('click', function () {
      var on = tg.getAttribute('aria-pressed') !== 'true';
      tg.setAttribute('aria-pressed', on ? 'true' : 'false');
      tg.closest('.ev-sec').classList.toggle('is-shiny', on);
      tg.querySelector('span').textContent = on ? '顯示一般' : '顯示異色';
      if (window.track) window.track('event_action', { action: on ? 'shiny_on' : 'shiny_off' });
    });
  });

  // 分享：手機用系統分享，桌機複製網址
  var toast = document.querySelector('.ev-toast'), tt;
  function say(msg) {
    if (!toast) return;
    toast.textContent = msg; toast.hidden = false;
    clearTimeout(tt); tt = setTimeout(function () { toast.hidden = true; }, 2200);
  }
  var sh = document.querySelector('[data-share]');
  if (sh) sh.addEventListener('click', function () {
    var url = location.href.split('#')[0], title = document.title;
    if (window.track) window.track('event_action', { action: 'share' });
    if (navigator.share) { navigator.share({ title: title, url: url }).catch(function () {}); return; }
    if (navigator.clipboard) navigator.clipboard.writeText(url).then(function () { say('已複製網址'); }, function () { say(url); });
    else say(url);
  });
  var cal = document.querySelector('[data-track="calendar"]');
  if (cal) cal.addEventListener('click', function () { if (window.track) window.track('event_action', { action: 'calendar' }); });
})();
