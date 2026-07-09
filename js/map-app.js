// ============================================================================
// 補給站/道館地圖：動態 S2 網格 + POI 顯示 + 地點搜尋 + 可拖曳小人
// 由 main.js 在切到此分頁時呼叫 initializeMapApp() 進行延遲初始化。
// 依賴全域的 Leaflet (L) 與 s2geometry (S2)，兩者在 index.html 以 <script> 載入。
// ============================================================================

let mapInited = false;

export function initializeMapApp() {
  if (mapInited) return;      // 只初始化一次
  mapInited = true;

  // -------------------------------------------------------------------------
  // 基本地圖
  // -------------------------------------------------------------------------
  // zoomSnap 0.25：讓「雙擊後滑動縮放」手勢能有平滑的中間縮放級距
  const map = L.map('s2map', { worldCopyJump: true, zoomSnap: 0.25 }).setView([25.0, 121.5], 12);

  // ---------------------------------------------------------------------------
  // 「快速點兩下，第二下按住上下滑動」單指縮放手勢（Google Maps 慣例）。
  // Leaflet 沒有內建這個手勢，這裡自行實作：
  //   第二下按住 → 下滑放大、上滑縮小；若沒有滑動就當作一般雙擊放大一級。
  // ---------------------------------------------------------------------------
  (function enableDoubleTapDragZoom() {
    var container = map.getContainer();
    var lastTapTime = 0, lastTapX = 0, lastTapY = 0;
    var active = false, moved = false, startY = 0, startZoom = 0, tapPoint = null;

    container.addEventListener('touchstart', function (e) {
      if (e.touches.length !== 1) { active = false; return; }
      var t = e.touches[0], now = Date.now();
      var isDoubleTap = (now - lastTapTime) < 300 &&
        Math.abs(t.clientX - lastTapX) < 40 && Math.abs(t.clientY - lastTapY) < 40;
      lastTapTime = now; lastTapX = t.clientX; lastTapY = t.clientY;
      if (!isDoubleTap) return;

      // 進入拖曳縮放模式：接管觸控（也擋掉瀏覽器合成的 dblclick，避免原生雙擊縮放重複觸發）
      e.preventDefault();
      cancelPendingClick();   // 第一下排入的「延遲放座標點」也一併取消
      active = true; moved = false;
      startY = t.clientY;
      startZoom = map.getZoom();
      var rect = container.getBoundingClientRect();
      tapPoint = L.point(t.clientX - rect.left, t.clientY - rect.top);
      map.dragging.disable();          // 滑動期間不要平移地圖
    }, { passive: false });

    container.addEventListener('touchmove', function (e) {
      if (!active) return;
      e.preventDefault();
      var dy = e.touches[0].clientY - startY;
      if (Math.abs(dy) > 8) moved = true;
      // 每滑 120px 縮放一級：下滑放大、上滑縮小（同 Google Maps）
      map.setZoom(startZoom + dy / 120, { animate: false });
    }, { passive: false });

    function endGesture() {
      if (!active) return;
      active = false;
      map.dragging.enable();
      // 沒有滑動 → 視為一般雙擊：以點擊處為中心放大一級
      if (!moved) map.setZoomAround(tapPoint, Math.round(startZoom) + 1);
    }
    container.addEventListener('touchend', endGesture);
    container.addEventListener('touchcancel', endGesture);
  })();

  // 因為分頁一開始是隱藏的，切過來時容器尺寸才確定，需重新計算一次
  setTimeout(function () { map.invalidateSize(); }, 120);

  var baseLayers = {
    '街道圖 (OSM)': L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors', maxZoom: 24, maxNativeZoom: 19
    }),
    '衛星影像': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      attribution: 'Tiles &copy; Esri', maxZoom: 24, maxNativeZoom: 19
    }),
    '衛星+街名': L.layerGroup([
      L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 24, maxNativeZoom: 19, attribution: 'Tiles &copy; Esri' }),
      L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 24, maxNativeZoom: 19 })
    ]),
    '淺色簡潔': L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap, &copy; CARTO', maxZoom: 24, maxNativeZoom: 20, subdomains: 'abcd'
    }),
    '深色': L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap, &copy; CARTO', maxZoom: 24, maxNativeZoom: 20, subdomains: 'abcd'
    }),
    '地形圖': L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenTopoMap (CC-BY-SA)', maxZoom: 24, maxNativeZoom: 17
    })
  };
  baseLayers['街道圖 (OSM)'].addTo(map);
  // 收合成小圖示（滑過或點擊才展開），避免展開的清單擋住面板
  L.control.layers(baseLayers, null, { position: 'topright', collapsed: true }).addTo(map);

  // -------------------------------------------------------------------------
  // Level 選單
  // -------------------------------------------------------------------------
  var LEVELS = [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20];
  var LEVEL_NOTE = { 14: '（PoGo 道館網格）', 17: '（PoGo 補給站網格）' };
  var lvlSelect = document.getElementById('lvl');
  LEVELS.forEach(function (l) {
    var opt = document.createElement('option');
    opt.value = l;
    opt.textContent = 'L' + l + (LEVEL_NOTE[l] || '');
    if (l === 17) opt.selected = true;
    lvlSelect.appendChild(opt);
  });

  var statusEl = document.getElementById('mapStatus');
  function setStatus(msg, warn) {
    if (statusEl) {
      statusEl.textContent = msg;
      statusEl.className = warn ? 'status warn' : 'status';
    } else if (warn) {
      console.warn('[map] ' + msg);
    }
  }

  // -------------------------------------------------------------------------
  // 動態網格：flood-fill 找出畫面內的 S2 cells
  // -------------------------------------------------------------------------
  var gridLayer = L.layerGroup().addTo(map);
  var MAX_CELLS = 8000, MAX_ITER = 40000;

  function currentLevel() { return parseInt(lvlSelect.value, 10); }
  function gridEnabled() { return document.getElementById('gridOn').checked; }

  function cornersToBBox(corners) {
    var latMin = Infinity, latMax = -Infinity, lngMin = Infinity, lngMax = -Infinity;
    for (var i = 0; i < corners.length; i++) {
      var c = corners[i];
      if (c.lat < latMin) latMin = c.lat;
      if (c.lat > latMax) latMax = c.lat;
      if (c.lng < lngMin) lngMin = c.lng;
      if (c.lng > lngMax) lngMax = c.lng;
    }
    return { latMin: latMin, latMax: latMax, lngMin: lngMin, lngMax: lngMax };
  }

  function drawGrid() {
    gridLayer.clearLayers();
    if (!gridEnabled()) { setStatus('網格已隱藏'); return; }

    var level = currentLevel();
    var b = map.getBounds().pad(0.15);
    var vLatMin = b.getSouth(), vLatMax = b.getNorth();
    var vLngMin = b.getWest(),  vLngMax = b.getEast();
    var center = map.getCenter();

    var start;
    try {
      start = S2.S2Cell.FromLatLng({ lat: center.lat, lng: center.lng }, level);
    } catch (e) { setStatus('此位置無法計算網格', true); return; }

    var stack = [start], seen = {}, cells = [], iter = 0;
    while (stack.length && iter < MAX_ITER) {
      iter++;
      var cell = stack.pop();
      var key = cell.toHilbertQuadkey();
      if (seen[key]) continue;
      seen[key] = true;

      var corners = cell.getCornerLatLngs();
      var bb = cornersToBBox(corners);
      var overlap = bb.latMin <= vLatMax && bb.latMax >= vLatMin &&
                    bb.lngMin <= vLngMax && bb.lngMax >= vLngMin;
      if (!overlap) continue;

      cells.push(corners);
      if (cells.length > MAX_CELLS) {
        setStatus('L' + level + ' 網格太密（畫面內超過 ' + MAX_CELLS +
                  ' 格），請放大地圖或選更高的 Level', true);
        return;
      }
      var nb = cell.getNeighbors();
      for (var i = 0; i < nb.length; i++) {
        if (!seen[nb[i].toHilbertQuadkey()]) stack.push(nb[i]);
      }
    }

    cells.forEach(function (corners) {
      var latlngs = corners.map(function (c) { return [c.lat, c.lng]; });
      L.polygon(latlngs, { color: '#e53e3e', weight: 1, opacity: 0.9, fill: false, interactive: false })
        .addTo(gridLayer);
    });
    setStatus('L' + level + '：畫面內 ' + cells.length + ' 格');
  }

  var redrawTimer = null;
  function scheduleRedraw() {
    if (redrawTimer) clearTimeout(redrawTimer);
    redrawTimer = setTimeout(function () {
      drawGrid();
      if (poiData.length) renderPois();
    }, 120);
  }
  map.on('moveend zoomend', scheduleRedraw);
  lvlSelect.addEventListener('change', drawGrid);
  document.getElementById('gridOn').addEventListener('change', drawGrid);

  // -------------------------------------------------------------------------
  // 座標讀值 + 點擊放點
  // -------------------------------------------------------------------------
  var coordbox = document.getElementById('coordbox');
  map.on('mousemove', function (e) {
    coordbox.textContent = '緯度 ' + e.latlng.lat.toFixed(6) + ', 經度 ' + e.latlng.lng.toFixed(6);
  });
  var clickMarker = null;
  var COORD_MIN_ZOOM = 13;   // 縮太小時（找大範圍位置階段）點地圖不放座標點
  var clickTimer = null;

  function placeClickMarker(latlng) {
    if (clickMarker) map.removeLayer(clickMarker);
    clickMarker = L.circleMarker(latlng, {
      radius: 5, color: '#ff0000', weight: 2, fillColor: '#ffff00', fillOpacity: 1
    }).addTo(map);
    clickMarker.bindPopup(
      "<div style='font:14px monospace;'><b>緯度:</b> " + latlng.lat.toFixed(6) +
      "<br><b>經度:</b> " + latlng.lng.toFixed(6) + "</div>"
    ).openPopup();
  }
  function cancelPendingClick() {
    if (clickTimer) { clearTimeout(clickTimer); clickTimer = null; }
  }
  // 延遲 330ms 再放座標點：若期間出現第二下點擊（雙擊縮放手勢）或地圖開始
  // 縮放/平移，就取消本次放點，避免手機「快速點兩下縮放」被第一下攔截。
  map.on('click', function (e) {
    if (map.getZoom() < COORD_MIN_ZOOM) return;
    cancelPendingClick();
    clickTimer = setTimeout(function () {
      clickTimer = null;
      placeClickMarker(e.latlng);
    }, 330);
  });
  map.on('dblclick zoomstart movestart', cancelPendingClick);

  // -------------------------------------------------------------------------
  // 定位：用瀏覽器 Geolocation 找目前位置
  // -------------------------------------------------------------------------
  var locateEl = null;
  function locateMe() {
    if (!navigator.geolocation) { setStatus('此裝置/瀏覽器不支援定位', true); return; }
    setStatus('定位中…');
    if (locateEl) locateEl.classList.add('locating');
    navigator.geolocation.getCurrentPosition(function (pos) {
      var lat = pos.coords.latitude, lng = pos.coords.longitude, acc = pos.coords.accuracy;
      // 把定位到的位置直接當成「人物」放上去（含 40 / 80 公尺範圍圈）
      placePerson(L.latLng(lat, lng));
      map.flyTo([lat, lng], Math.max(map.getZoom(), 17));
      setStatus('已定位並放置人物（誤差約 ' + Math.round(acc) + ' 公尺）');
      if (locateEl) locateEl.classList.remove('locating');
    }, function (err) {
      var msg = err.code === 1 ? '你拒絕了定位權限' :
                err.code === 3 ? '定位逾時，請再試一次' : '定位失敗';
      setStatus(msg, true);
      if (locateEl) locateEl.classList.remove('locating');
    }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 });
  }

  // 定位控制項：放在縮放鈕正下方（topleft），用熟悉的定位圖標
  var LocateControl = L.Control.extend({
    options: { position: 'topleft' },
    onAdd: function () {
      var container = L.DomUtil.create('div', 'leaflet-bar locate-control');
      var link = L.DomUtil.create('a', '', container);
      link.href = '#';
      link.title = '定位到我的位置';
      link.setAttribute('role', 'button');
      link.setAttribute('aria-label', '定位到我的位置');
      link.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">' +
        '<path d="M12 8c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4zm8.94 3c-.46-4.17' +
        '-3.77-7.48-7.94-7.94V1h-2v2.06C6.83 3.52 3.52 6.83 3.06 11H1v2h2.06c.46 4.17 3.77 7.48 ' +
        '7.94 7.94V23h2v-2.06c4.17-.46 7.48-3.77 7.94-7.94H23v-2h-2.06zM12 19c-3.87 0-7-3.13-7-7s3.13' +
        '-7 7-7 7 3.13 7 7-3.13 7-7 7z"/></svg>';
      locateEl = container;
      L.DomEvent.on(link, 'click', function (e) { L.DomEvent.stop(e); locateMe(); });
      L.DomEvent.disableClickPropagation(container);
      return container;
    }
  });
  map.addControl(new LocateControl());

  // 面板開關鈕（只在手機顯示，見 CSS）：手機上控制面板預設收合，點 ⚙️ 展開
  var PanelToggle = L.Control.extend({
    options: { position: 'topleft' },
    onAdd: function () {
      var container = L.DomUtil.create('div', 'leaflet-bar panel-toggle-control');
      var link = L.DomUtil.create('a', '', container);
      link.href = '#';
      link.title = '顯示/隱藏地圖設定';
      link.setAttribute('role', 'button');
      link.setAttribute('aria-expanded', 'false');
      link.textContent = '⚙️';
      L.DomEvent.on(link, 'click', function (e) {
        L.DomEvent.stop(e);
        var open = document.getElementById('map-app').classList.toggle('panel-open');
        link.setAttribute('aria-expanded', String(open));
        container.classList.toggle('is-open', open);
      });
      L.DomEvent.disableClickPropagation(container);
      return container;
    }
  });
  map.addControl(new PanelToggle());

  // -------------------------------------------------------------------------
  // 讓 .map-topbar 當作「中間欄」：兩側各自避開 Leaflet 控制項
  //   左：縮放 + 定位鈕；右：「選擇地圖」圖層清單（含滑過/點擊展開後的寬度）
  // 以 ResizeObserver 監看兩側叢集寬度變化（展開/收合會即時觸發），
  // 動態寫入 CSS 變數 --topbar-left / --topbar-right，避免搜尋框擋住圖層鈕。
  // -------------------------------------------------------------------------
  (function layoutTopbarAsMiddleColumn() {
    var wrap = map.getContainer().closest('.map-app-wrap');
    if (!wrap) return;
    var topbar = wrap.querySelector('.map-topbar');
    var leftCtl = wrap.querySelector('.leaflet-top.leaflet-left');
    var rightCtl = wrap.querySelector('.leaflet-top.leaflet-right');
    if (!topbar || !leftCtl || !rightCtl) return;

    var GAP = 8; // 中間欄與兩側控制項之間的呼吸間距
    function update() {
      // offsetWidth 已含 Leaflet 控制項的外邊距（貼齊視窗邊緣的 10px）
      topbar.style.setProperty('--topbar-left', (leftCtl.offsetWidth + GAP) + 'px');
      topbar.style.setProperty('--topbar-right', (rightCtl.offsetWidth + GAP) + 'px');
    }

    update();
    if (typeof ResizeObserver !== 'undefined') {
      var ro = new ResizeObserver(update);
      ro.observe(leftCtl);
      ro.observe(rightCtl);
    }
    window.addEventListener('resize', update);
    // 分頁由隱藏切為顯示、地圖尺寸重算後，寬度才穩定，再補算一次
    setTimeout(update, 150);
  })();

  // -------------------------------------------------------------------------
  // 地點搜尋（有 Google key 用 Google Places，否則用 Nominatim）
  // key 由 build 時注入 window.MAPS_API_KEY，不寫在原始碼裡
  // -------------------------------------------------------------------------
  var searchInput = document.getElementById('mapSearchInput');
  var searchBtn = document.getElementById('mapSearchBtn');
  var searchResults = document.getElementById('mapSearchResults');
  var searchMarker = null;
  var GKEY = (window.MAPS_API_KEY || '').trim();

  function showResults(html) { searchResults.innerHTML = html; searchResults.style.display = 'block'; }

  function renderList(list) {
    if (!list.length) { showResults("<div class='empty'>找不到結果</div>"); return; }
    var html = list.map(function (item, i) {
      return "<div data-i='" + i + "'><b>" + item.name + "</b>" +
             (item.address ? "<br><span style='color:#666'>" + item.address + "</span>" : "") + "</div>";
    }).join('');
    showResults(html);
    searchResults.querySelectorAll('div[data-i]').forEach(function (el) {
      el.addEventListener('click', function () {
        gotoResult(list[parseInt(el.getAttribute('data-i'), 10)]);
      });
    });
  }

  function doSearch() {
    var q = searchInput.value.trim();
    if (!q) return;
    showResults("<div class='empty'>搜尋中…</div>");
    if (GKEY) googleSearch(q); else nominatimSearch(q);
  }

  function googleSearch(q) {
    var c = map.getCenter();
    fetch('https://places.googleapis.com/v1/places:searchText', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': GKEY,
        'X-Goog-FieldMask': 'places.displayName,places.formattedAddress,places.location'
      },
      body: JSON.stringify({
        textQuery: q, languageCode: 'zh-TW', maxResultCount: 8,
        locationBias: { circle: { center: { latitude: c.lat, longitude: c.lng }, radius: 50000 } }
      })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) { showResults("<div class='empty'>Google 錯誤：" + data.error.message + "</div>"); return; }
        renderList((data.places || []).map(function (p) {
          return { name: p.displayName ? p.displayName.text : '(無名稱)',
                   address: p.formattedAddress || '',
                   lat: p.location.latitude, lng: p.location.longitude };
        }));
      })
      .catch(function (e) { showResults("<div class='empty'>搜尋失敗：" + e.message + "</div>"); });
  }

  function nominatimSearch(q) {
    var c = map.getCenter();
    var url = 'https://nominatim.openstreetmap.org/search?format=jsonv2&limit=6' +
              '&accept-language=zh-TW&q=' + encodeURIComponent(q) +
              '&viewbox=' + (c.lng - 0.5) + ',' + (c.lat + 0.5) + ',' + (c.lng + 0.5) + ',' + (c.lat - 0.5);
    fetch(url, { headers: { 'Accept': 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (arr) {
        renderList((arr || []).map(function (item) {
          return { name: item.name || item.display_name, address: item.display_name,
                   lat: parseFloat(item.lat), lng: parseFloat(item.lon) };
        }));
      })
      .catch(function (e) { showResults("<div class='empty'>搜尋失敗：" + e.message + "</div>"); });
  }

  function gotoResult(item) {
    map.flyTo([item.lat, item.lng], Math.max(map.getZoom(), 16));
    if (searchMarker) map.removeLayer(searchMarker);
    searchMarker = L.marker([item.lat, item.lng]).addTo(map)
      .bindPopup("<b>" + item.name + "</b>" + (item.address ? "<br>" + item.address : "") +
                 "<br><span style='font:12px monospace;'>" + item.lat.toFixed(6) + ', ' + item.lng.toFixed(6) + "</span>")
      .openPopup();
    searchResults.style.display = 'none';
  }

  searchBtn.addEventListener('click', doSearch);
  searchInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') doSearch(); });
  document.addEventListener('click', function (e) {
    if (!e.target.closest('#map-app .searchbox')) searchResults.style.display = 'none';
  });

  // -------------------------------------------------------------------------
  // 地點（補給站 / 道館）：自動讀取 data/pois.geojson，只畫畫面內的點
  // -------------------------------------------------------------------------
  var POI_STYLE = {
    POKESTOP: { color: '#2b6cb0', fill: '#4299e1', label: '補給站' },
    GYM:      { color: '#c53030', fill: '#fc8181', label: '道館' }
  };
  // tolerance：在每個點外圍多加 12px 的點擊容錯圈，避免「一點點沒點準」就落到地圖上
  // 變成放座標點，而不是選到補給站/道館（不影響點的視覺大小）。
  var poiCanvas = L.canvas({ padding: 0.5, tolerance: 12 });
  var poiLayer = L.layerGroup().addTo(map);
  var poiData = [];
  var POI_MIN_ZOOM = 13;

  function activeTypes() {
    var s = {};
    document.querySelectorAll('#map-app .poiFilter').forEach(function (cb) { s[cb.value] = cb.checked; });
    return s;
  }

  function renderPois() {
    poiLayer.clearLayers();
    if (!poiData.length) return;
    if (map.getZoom() < POI_MIN_ZOOM) {
      setStatus('地圖太小，已暫時隱藏 ' + poiData.length + ' 個地點（放大到 z' + POI_MIN_ZOOM + '↑ 顯示）');
      return;
    }
    var types = activeTypes();
    var b = map.getBounds().pad(0.2);
    var vLatMin = b.getSouth(), vLatMax = b.getNorth();
    var vLngMin = b.getWest(),  vLngMax = b.getEast();
    // 遠看時點太密會蓋住地圖、找不到位置：縮小時改畫「空心圈」（只留外框），
    // 放大到 z16 以上恢復原本的實心樣式。
    var hollow = map.getZoom() < 16;
    var rScale = hollow ? 0.8 : 1;
    var shown = 0, hidden = 0;
    poiData.forEach(function (f) {
      var t = f.properties.type;
      if (!types[t]) return;
      var lng = f.geometry.coordinates[0], lat = f.geometry.coordinates[1];
      if (lat < vLatMin || lat > vLatMax || lng < vLngMin || lng > vLngMax) { hidden++; return; }
      var st = POI_STYLE[t] || { color: '#333', fill: '#999', label: t };
      var inactive = f.properties.status && f.properties.status !== 'ACTIVE';
      var m = L.circleMarker([lat, lng], {
        renderer: poiCanvas, radius: (t === 'GYM' ? 7 : 5) * rScale,
        color: st.color, weight: 2,
        // 空心模式下用外框深淺區分「未啟用」；實心模式維持原本的淡填色
        opacity: inactive && hollow ? 0.35 : 1,
        fillColor: st.fill, fillOpacity: hollow ? 0 : (inactive ? 0.25 : 0.9)
      });
      m.bindPopup(
        "<div style='font:13px system-ui;'><b>" + (f.properties.title || '(無名稱)') + "</b><br>" +
        "類型: " + st.label + (inactive ? '（未啟用）' : '') + "<br>" +
        "<span style='font-family:monospace;'>" + lat.toFixed(6) + ', ' + lng.toFixed(6) + "</span></div>"
      );
      m.addTo(poiLayer);
      shown++;
    });
    setStatus('畫面內 ' + shown + ' 個地點（共載入 ' + poiData.length + '，畫面外 ' + hidden + ' 未畫）');
  }

  document.querySelectorAll('#map-app .poiFilter').forEach(function (cb) {
    cb.addEventListener('change', renderPois);
  });

  // 把精簡格式 (compact-poi-1) 展開成內部使用的 feature 陣列
  function compactToFeatures(data) {
    var scale = data.scale || 100000;
    var feats = [];
    function add(arr, type, active) {
      (arr || []).forEach(function (e) {
        feats.push({
          geometry: { coordinates: [e[0] / scale, e[1] / scale] },
          properties: { title: e[2] || '', type: type, status: active ? 'ACTIVE' : 'INACTIVE' }
        });
      });
    }
    add(data.stops, 'POKESTOP', true);
    add(data.gyms, 'GYM', true);
    add(data.stops_i, 'POKESTOP', false);
    add(data.gyms_i, 'GYM', false);
    return feats;
  }

  // 自動載入 data/pois.geojson
  setStatus('正在載入地點資料…');
  fetch('data/pois.geojson')
    .then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function (data) {
      if (data && data.fmt === 'compact-poi-1') {
        poiData = compactToFeatures(data);                 // 精簡格式
      } else if (data && data.type === 'FeatureCollection') {
        poiData = data.features || [];                     // 標準 GeoJSON（相容舊檔）
      } else {
        poiData = Array.isArray(data) ? data : [];
      }
      setStatus('已載入 ' + poiData.length + ' 個地點，放大地圖即可顯示');
      drawGrid();
      renderPois();
    })
    .catch(function (e) {
      setStatus('地點資料載入失敗：' + e.message + '（data/pois.geojson）', true);
      drawGrid();
    });

  // -------------------------------------------------------------------------
  // 🏆 排名統計：找出 80m / 40m 圓能覆蓋最多道館/補給站的位置
  // 理論：最佳圓心必為「某點本身」或「某兩點 r-圓的交點」（max covering disk）。
  // 21 萬點的資料量：等距投影成公尺 → 網格索引 → 單點先算一輪取得剪枝門檻 →
  // 只對「有機會進榜」的點對算交點，並分段讓出主執行緒避免卡住 UI。
  // -------------------------------------------------------------------------
  var RANK_MODES = {
    gym80:  { r: 80, filter: function (f) { return f.properties.type === 'GYM'; } },
    all80:  { r: 80, filter: function () { return true; } },
    stop40: { r: 40, filter: function (f) { return f.properties.type === 'POKESTOP'; } }
  };
  var RANK_TOP_N = 30;
  var rankCache = {};
  var rankBusy = false;

  function yieldToUI() { return new Promise(function (res) { setTimeout(res, 0); }); }

  function computeTopSpots(feats, radius, onProgress) {
    return (async function () {
      var n = feats.length;
      var M_LAT = 110574, M_LNG = 111320;
      var xs = new Float64Array(n), ys = new Float64Array(n);
      var latSum = 0, i;
      for (i = 0; i < n; i++) latSum += feats[i].geometry.coordinates[1];
      var cosLat = Math.cos((latSum / Math.max(1, n)) * Math.PI / 180);
      for (i = 0; i < n; i++) {
        xs[i] = feats[i].geometry.coordinates[0] * M_LNG * cosLat;
        ys[i] = feats[i].geometry.coordinates[1] * M_LAT;
      }

      // 網格索引（格邊長 = r）
      var cell = radius, KEY = 4194304;
      var grid = new Map();
      for (i = 0; i < n; i++) {
        var k = Math.floor(xs[i] / cell) * KEY + Math.floor(ys[i] / cell);
        var arr = grid.get(k);
        if (arr) arr.push(i); else grid.set(k, [i]);
      }
      var EPS = 1e-6;
      function countAt(x, y, r) {
        var r2 = r * r + EPS, kmax = Math.ceil(r / cell) + 1;
        var cx = Math.floor(x / cell), cy = Math.floor(y / cell), c = 0;
        for (var gx = cx - kmax; gx <= cx + kmax; gx++)
          for (var gy = cy - kmax; gy <= cy + kmax; gy++) {
            var lst = grid.get(gx * KEY + gy);
            if (!lst) continue;
            for (var q = 0; q < lst.length; q++) {
              var dx = xs[lst[q]] - x, dy = ys[lst[q]] - y;
              if (dx * dx + dy * dy <= r2) c++;
            }
          }
        return c;
      }
      function nearestTitle(x, y, r) {
        var best = '', bd = Infinity, kmax = Math.ceil(r / cell) + 1;
        var cx = Math.floor(x / cell), cy = Math.floor(y / cell);
        for (var gx = cx - kmax; gx <= cx + kmax; gx++)
          for (var gy = cy - kmax; gy <= cy + kmax; gy++) {
            var lst = grid.get(gx * KEY + gy);
            if (!lst) continue;
            for (var q = 0; q < lst.length; q++) {
              var j = lst[q], dx = xs[j] - x, dy = ys[j] - y, d2 = dx * dx + dy * dy;
              if (d2 < bd) { bd = d2; best = feats[j].properties.title || ''; }
            }
          }
        return best;
      }

      // 第一階段：以每個點自身為圓心數覆蓋，並算 2r 內鄰居數（給剪枝上界用）
      var cntR = new Int32Array(n), cnt2r = new Int32Array(n);
      for (i = 0; i < n; i++) {
        cntR[i] = countAt(xs[i], ys[i], radius);
        cnt2r[i] = countAt(xs[i], ys[i], radius * 2);
        if ((i & 8191) === 0) { onProgress('1/2 掃描各點', i, n); await yieldToUI(); }
      }

      // 剪枝門檻：單點候選第 300 名的覆蓋數。交點候選蓋到的點必在其父點 2r 內，
      // 所以 cnt2r 是上界——低於門檻的點對不可能進榜，直接跳過。
      var sortedCnt = Array.from(cntR).sort(function (a, b) { return b - a; });
      var TH = Math.max(2, sortedCnt[Math.min(300, n - 1)] || 2);
      var cand = [];
      for (i = 0; i < n; i++) if (cntR[i] >= TH) cand.push({ x: xs[i], y: ys[i], c: cntR[i] });

      // 第二階段：對距離 ≤ 2r 且可能進榜的點對，計算兩個 r-圓交點並數覆蓋
      var r2x4 = 4 * radius * radius + EPS;
      for (i = 0; i < n; i++) {
        if (cnt2r[i] >= TH) {
          var cx = Math.floor(xs[i] / cell), cy = Math.floor(ys[i] / cell);
          for (var gx = cx - 3; gx <= cx + 3; gx++)
            for (var gy = cy - 3; gy <= cy + 3; gy++) {
              var lst = grid.get(gx * KEY + gy);
              if (!lst) continue;
              for (var q = 0; q < lst.length; q++) {
                var j = lst[q];
                if (j <= i || cnt2r[j] < TH) continue;
                var dx = xs[j] - xs[i], dy = ys[j] - ys[i], d2 = dx * dx + dy * dy;
                if (d2 > r2x4 || d2 < EPS) continue;
                var d = Math.sqrt(d2);
                var mx = (xs[i] + xs[j]) / 2, my = (ys[i] + ys[j]) / 2;
                var h = Math.sqrt(Math.max(0, radius * radius - d2 / 4));
                var ux = -dy / d * h, uy = dx / d * h;
                var c1 = countAt(mx + ux, my + uy, radius);
                if (c1 >= TH) cand.push({ x: mx + ux, y: my + uy, c: c1 });
                var c2 = countAt(mx - ux, my - uy, radius);
                if (c2 >= TH) cand.push({ x: mx - ux, y: my - uy, c: c2 });
              }
            }
        }
        if ((i & 4095) === 0) { onProgress('2/2 計算交點', i, n); await yieldToUI(); }
      }

      // 由高到低排序，並抑制彼此距離 < r 的重複熱點，取前 N 名
      cand.sort(function (a, b) { return b.c - a.c; });
      var picked = [], sep2 = radius * radius;
      for (i = 0; i < cand.length && picked.length < RANK_TOP_N; i++) {
        var ok = true;
        for (var p = 0; p < picked.length; p++) {
          var ddx = cand[i].x - picked[p].x, ddy = cand[i].y - picked[p].y;
          if (ddx * ddx + ddy * ddy < sep2) { ok = false; break; }
        }
        if (ok) picked.push(cand[i]);
      }
      return picked.map(function (s) {
        return {
          lat: s.y / M_LAT, lng: s.x / (M_LNG * cosLat),
          count: s.c, near: nearestTitle(s.x, s.y, radius)
        };
      });
    })();
  }

  // ---- 排名 UI ----
  var rankBtn = document.getElementById('rankBtn');
  var rankbox = document.getElementById('rankbox');
  var rankListEl = document.getElementById('rankList');
  var rankMode = 'gym80';

  function rankMsg(text) {
    rankListEl.innerHTML = '';
    var div = document.createElement('div');
    div.className = 'empty';
    div.textContent = text;
    rankListEl.appendChild(div);
  }

  function renderRankList(list) {
    rankListEl.innerHTML = '';
    if (!list.length) { rankMsg('沒有結果'); return; }
    list.forEach(function (s, idx) {
      var row = document.createElement('div');
      row.className = 'row';
      var no = document.createElement('span');
      no.className = 'rank-no'; no.textContent = idx + 1;
      var cnt = document.createElement('span');
      cnt.className = 'rank-cnt'; cnt.textContent = s.count + ' 個';
      var near = document.createElement('span');
      near.className = 'rank-near';
      near.textContent = s.near ? '近 ' + s.near : s.lat.toFixed(5) + ', ' + s.lng.toFixed(5);
      row.appendChild(no); row.appendChild(cnt); row.appendChild(near);
      // 一鍵查看：放置人物（自帶 40/80m 範圍圈）並飛過去
      row.addEventListener('click', function () {
        placePerson(L.latLng(s.lat, s.lng));
        map.flyTo([s.lat, s.lng], 17);
      });
      rankListEl.appendChild(row);
    });
  }

  function setRankTab(mode) {
    rankbox.querySelectorAll('.rank-tabs [data-mode]').forEach(function (b) {
      b.classList.toggle('active', b.dataset.mode === mode);
    });
  }

  async function showRank(mode) {
    rankMode = mode;
    setRankTab(mode);
    if (rankCache[mode]) { renderRankList(rankCache[mode]); return; }
    if (!poiData.length) { rankMsg('地點資料尚未載入，請稍候'); return; }
    if (rankBusy) { rankMsg('另一項排名計算中，請稍候…'); return; }
    rankBusy = true;
    rankMsg('計算中…');
    var cfg = RANK_MODES[mode];
    var feats = poiData.filter(function (f) {
      return f.properties.status === 'ACTIVE' && cfg.filter(f);
    });
    try {
      var res = await computeTopSpots(feats, cfg.r, function (stage, done, total) {
        rankMsg('計算中（' + stage + ' ' + Math.round(done / total * 100) + '%）…');
      });
      rankCache[mode] = res;
      if (rankMode === mode) renderRankList(res);
    } finally {
      rankBusy = false;
    }
  }

  rankBtn.addEventListener('click', function () {
    var show = rankbox.style.display === 'none';
    rankbox.style.display = show ? 'block' : 'none';
    if (show) showRank(rankMode);
  });
  rankbox.querySelector('.rank-close').addEventListener('click', function () {
    rankbox.style.display = 'none';
  });
  rankbox.querySelectorAll('.rank-tabs [data-mode]').forEach(function (b) {
    b.addEventListener('click', function () { showRank(b.dataset.mode); });
  });

  // -------------------------------------------------------------------------
  // Pegman 小人：拖到地圖才放置
  // -------------------------------------------------------------------------
  var personMarker = null, personCircle = null, personCircle40 = null;
  var personRadius = 80;     // 外圈：80 公尺
  var personRadius40 = 40;   // 內圈：40 公尺
  var personIcon = L.divIcon({
    html: "<div style='font-size:28px; line-height:28px;'>🧍</div>",
    className: 'person-marker-icon', iconSize: [30, 30], iconAnchor: [15, 28]
  });

  function updatePersonPopup() {
    if (!personMarker) return;
    var ll = personMarker.getLatLng();
    personMarker.bindPopup(
      "<div style='font:14px monospace;'><b>人物位置</b><br>緯度: " + ll.lat.toFixed(6) +
      "<br>經度: " + ll.lng.toFixed(6) +
      "<br>範圍半徑: " + personRadius40 + " / " + personRadius + " 公尺</div>"
    );
  }
  function placePerson(latlng) {
    if (!personMarker) {
      personMarker = L.marker(latlng, { icon: personIcon, draggable: true, title: '拖曳我來移動' }).addTo(map);
      // 外圈 80m（interactive:false：純視覺參考，讓點擊穿透到底下的補給站/道館）
      personCircle = L.circle(latlng, {
        radius: personRadius, color: '#2b6cb0', weight: 2, fillColor: '#4299e1', fillOpacity: 0.12,
        interactive: false
      }).addTo(map);
      // 內圈 40m
      personCircle40 = L.circle(latlng, {
        radius: personRadius40, color: '#dd6b20', weight: 2, fillColor: '#f6ad55', fillOpacity: 0.18,
        interactive: false
      }).addTo(map);
      personMarker.on('drag', function (e) {
        var p = e.target.getLatLng();
        personCircle.setLatLng(p);
        personCircle40.setLatLng(p);
      });
      personMarker.on('dragend', function () { updatePersonPopup(); });
      pegReset.style.display = 'block';
      pegIcon.style.opacity = '0.35';
    } else {
      personMarker.setLatLng(latlng);
      personCircle.setLatLng(latlng);
      personCircle40.setLatLng(latlng);
    }
    updatePersonPopup();
  }
  function removePerson() {
    if (personMarker) { map.removeLayer(personMarker); personMarker = null; }
    if (personCircle) { map.removeLayer(personCircle); personCircle = null; }
    if (personCircle40) { map.removeLayer(personCircle40); personCircle40 = null; }
    pegReset.style.display = 'none';
    pegIcon.style.opacity = '1';
  }

  var PegControl = L.Control.extend({
    options: { position: 'bottomright' },
    onAdd: function () {
      var div = L.DomUtil.create('div', 'pegman-control');
      div.innerHTML =
        '<div class="peg" title="拖到地圖上放置人物">🧍</div>' +
        '<div class="hint">拖到地圖</div>' +
        '<div class="reset">移除人物</div>';
      L.DomEvent.disableClickPropagation(div);
      return div;
    }
  });
  map.addControl(new PegControl());

  var pegIcon = document.querySelector('#map-app .pegman-control .peg');
  var pegReset = document.querySelector('#map-app .pegman-control .reset');
  pegReset.addEventListener('click', removePerson);

  // 自訂拖曳（Pointer Events）：取代 HTML5 drag-and-drop。
  // iOS 上原生 DnD 要長按才會啟動，改用 pointer 事件即可「一按就拖」，
  // 滑鼠與觸控都走同一套邏輯。setPointerCapture 讓手指離開圖示後仍持續收到事件。
  var mapEl = document.getElementById('s2map');
  var pegGhost = null;
  function movePegGhost(e) {
    pegGhost.style.left = e.clientX + 'px';
    pegGhost.style.top = e.clientY + 'px';
  }
  function removePegGhost() {
    if (pegGhost) { pegGhost.remove(); pegGhost = null; }
  }
  pegIcon.addEventListener('pointerdown', function (e) {
    e.preventDefault();   // 避免觸發文字選取/系統手勢
    pegIcon.setPointerCapture(e.pointerId);
    pegGhost = document.createElement('div');
    pegGhost.textContent = '🧍';
    // 跟著手指走的殘影；translate 讓人物腳底對準指尖上方一點，不被手指遮住
    pegGhost.style.cssText =
      'position:fixed; z-index:9999; font-size:34px; line-height:34px;' +
      'pointer-events:none; transform:translate(-50%, -100%);';
    movePegGhost(e);
    document.body.appendChild(pegGhost);
  });
  pegIcon.addEventListener('pointermove', function (e) {
    if (pegGhost) movePegGhost(e);
  });
  pegIcon.addEventListener('pointerup', function (e) {
    if (!pegGhost) return;
    removePegGhost();
    var rect = mapEl.getBoundingClientRect();
    var x = e.clientX - rect.left, y = e.clientY - rect.top;
    // 放開位置在地圖範圍內才放置人物（在控制盒上放開視為取消）
    if (x >= 0 && y >= 0 && x <= rect.width && y <= rect.height) {
      placePerson(map.containerPointToLatLng(L.point(x, y)));
    }
  });
  pegIcon.addEventListener('pointercancel', removePegGhost);
}
