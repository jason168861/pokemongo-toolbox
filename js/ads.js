/* Manual AdSense placement settings.
 * Create a responsive Display ad unit in AdSense and paste its slot number here.
 * Leave empty to keep ad containers completely hidden until the unit is ready.
 */
(function () {
    'use strict';

    const PUBLISHER_ID = 'ca-pub-8866689605007086';
    const AD_SLOT_ID = '2584052803';

    // 有些頁面在 HTML 裡預留了廣告框（aside.site-ad[data-ad-reserved]，樣式在 css/main.css），
    // 位置就在下面「表頭之後」的同一處。
    const reserved = document.querySelector('aside.site-ad[data-ad-reserved]');

    if (!AD_SLOT_ID) {
        if (reserved) reserved.remove();   // 沒有廣告單元時，預留的空框也不要顯示
        return;
    }

    // 和 css/main.css 的「廣告框」區段相同；沒載 main.css 的頁面靠這裡。改尺寸時兩邊要一起改。
    const style = document.createElement('style');
    style.textContent = [
        '.site-ad{box-sizing:border-box;width:min(100% - 32px,1100px);min-height:120px;margin:28px auto 32px;padding:8px 0;text-align:center}',
        '.site-ad-label{display:block;margin:0 0 6px;color:#7b8190;font:11px/1.3 system-ui,sans-serif;letter-spacing:.04em}',
        '.site-ad ins{display:block;min-height:100px;overflow:hidden}',
        '@media(max-width:600px){.site-ad{width:calc(100% - 24px);min-height:100px;margin:20px auto 24px}.site-ad ins{min-height:80px}}'
    ].join('\n');
    document.head.appendChild(style);

    const INS = '<ins class="adsbygoogle" style="display:block" data-ad-client="' + PUBLISHER_ID +
        '" data-ad-slot="' + AD_SLOT_ID + '" data-ad-format="auto" data-full-width-responsive="true"></ins>';

    // 「廣告」標籤跟著頁面語言（交易清單有 7 種語言；其他頁面都是繁中 → 一律「廣告」）。
    // 交易清單切換語言時也會呼叫 window.pkAdLabel 更新標籤。
    const AD_LABELS = { zh: '廣告', ja: '広告', ko: '광고', fr: 'Publicité', de: 'Anzeige', es: 'Publicidad', en: 'Advertisement' };
    window.pkAdLabel = function (lang) {
        return AD_LABELS[String(lang || '').slice(0, 2).toLowerCase()] || AD_LABELS.zh;
    };
    const label = window.pkAdLabel(document.documentElement.lang);

    const ad = document.createElement('aside');
    ad.className = 'site-ad';
    ad.setAttribute('aria-label', label);
    ad.innerHTML = '<span class="site-ad-label">' + label + '</span>' + INS;

    const pageHeader = document.querySelector('body > header, .site-header-main, .topbar, .ed-topbar');
    const breadcrumb = document.querySelector('.wrap > .crumb');
    if (reserved) {
        // 已預留：把佔位的 .site-ad-ph 換成廣告（兩者高度相同），不插入新元素，整頁不會被往下推
        const ph = reserved.querySelector('.site-ad-ph');
        if (ph) ph.outerHTML = INS;
        else reserved.insertAdjacentHTML('beforeend', INS);
        reserved.removeAttribute('data-ad-reserved');   // 解除 main.css 的 visibility:hidden
    } else if (pageHeader) {
        pageHeader.insertAdjacentElement('afterend', ad);
    } else if (breadcrumb) {
        breadcrumb.insertAdjacentElement('afterend', ad);
    } else if (document.body.firstElementChild) {
        document.body.insertBefore(ad, document.body.firstElementChild);
    } else {
        document.body.appendChild(ad);
    }

    try {
        (window.adsbygoogle = window.adsbygoogle || []).push({});
    } catch (error) {
        // Ad blockers and unavailable ad inventory should not affect the tool.
    }
}());
