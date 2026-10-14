/* Manual AdSense placement settings.
 * Create a responsive Display ad unit in AdSense and paste its slot number here.
 * Leave empty to keep ad containers completely hidden until the unit is ready.
 */
(function () {
    'use strict';

    const PUBLISHER_ID = 'ca-pub-8866689605007086';
    const AD_SLOT_ID = '';

    if (!AD_SLOT_ID) return;

    const style = document.createElement('style');
    style.textContent = [
        '.site-ad{box-sizing:border-box;width:min(100% - 32px,1100px);min-height:120px;margin:28px auto 32px;padding:8px 0;text-align:center}',
        '.site-ad-label{display:block;margin:0 0 6px;color:#7b8190;font:11px/1.3 system-ui,sans-serif;letter-spacing:.04em}',
        '.site-ad ins{display:block;min-height:100px;overflow:hidden}',
        '@media(max-width:600px){.site-ad{width:calc(100% - 24px);min-height:100px;margin:20px auto 24px}.site-ad ins{min-height:80px}}'
    ].join('\n');
    document.head.appendChild(style);

    const ad = document.createElement('aside');
    ad.className = 'site-ad';
    ad.setAttribute('aria-label', '廣告');
    ad.innerHTML = '<span class="site-ad-label">廣告</span>' +
        '<ins class="adsbygoogle" style="display:block" data-ad-client="' + PUBLISHER_ID +
        '" data-ad-slot="' + AD_SLOT_ID + '" data-ad-format="auto" data-full-width-responsive="true"></ins>';

    const isTradeList = /\/trade-list(?:\/|$)/.test(window.location.pathname);
    const tradeListHeader = isTradeList ? document.querySelector('body > header') : null;
    const footer = document.querySelector('.site-footer');
    if (tradeListHeader) {
        tradeListHeader.insertAdjacentElement('afterend', ad);
    } else if (footer && footer.parentNode) {
        footer.parentNode.insertBefore(ad, footer);
    } else {
        document.body.appendChild(ad);
    }

    try {
        (window.adsbygoogle = window.adsbygoogle || []).push({});
    } catch (error) {
        // Ad blockers and unavailable ad inventory should not affect the tool.
    }
}());
