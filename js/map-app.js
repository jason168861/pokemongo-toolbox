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
  const map = L.map('s2map', { worldCopyJump: true }).setView([25.0, 121.5], 12);

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
  // 手機收合成小圖示（點了才展開），桌面直接攤開清單
  var isMobile = window.matchMedia('(max-width: 768px)').matches;
  L.control.layers(baseLayers, null, { position: 'topright', collapsed: isMobile }).addTo(map);

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
  map.on('click', function (e) {
    if (clickMarker) map.removeLayer(clickMarker);
    clickMarker = L.circleMarker(e.latlng, {
      radius: 5, color: '#ff0000', weight: 2, fillColor: '#ffff00', fillOpacity: 1
    }).addTo(map);
    clickMarker.bindPopup(
      "<div style='font:14px monospace;'><b>緯度:</b> " + e.latlng.lat.toFixed(6) +
      "<br><b>經度:</b> " + e.latlng.lng.toFixed(6) + "</div>"
    ).openPopup();
  });

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
  var poiCanvas = L.canvas({ padding: 0.5 });
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
    var shown = 0, hidden = 0;
    poiData.forEach(function (f) {
      var t = f.properties.type;
      if (!types[t]) return;
      var lng = f.geometry.coordinates[0], lat = f.geometry.coordinates[1];
      if (lat < vLatMin || lat > vLatMax || lng < vLngMin || lng > vLngMax) { hidden++; return; }
      var st = POI_STYLE[t] || { color: '#333', fill: '#999', label: t };
      var inactive = f.properties.status && f.properties.status !== 'ACTIVE';
      var m = L.circleMarker([lat, lng], {
        renderer: poiCanvas, radius: t === 'GYM' ? 7 : 5,
        color: st.color, weight: 2, fillColor: st.fill, fillOpacity: inactive ? 0.25 : 0.9
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
      // 外圈 80m
      personCircle = L.circle(latlng, {
        radius: personRadius, color: '#2b6cb0', weight: 2, fillColor: '#4299e1', fillOpacity: 0.12
      }).addTo(map);
      // 內圈 40m
      personCircle40 = L.circle(latlng, {
        radius: personRadius40, color: '#dd6b20', weight: 2, fillColor: '#f6ad55', fillOpacity: 0.18
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
        '<div class="peg" draggable="true" title="拖到地圖上放置人物">🧍</div>' +
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

  pegIcon.addEventListener('dragstart', function (e) {
    e.dataTransfer.setData('text/plain', 'peg');
    e.dataTransfer.effectAllowed = 'copy';
  });
  var mapEl = document.getElementById('s2map');
  mapEl.addEventListener('dragover', function (e) { e.preventDefault(); });
  mapEl.addEventListener('drop', function (e) {
    e.preventDefault();
    var rect = mapEl.getBoundingClientRect();
    var pt = L.point(e.clientX - rect.left, e.clientY - rect.top);
    placePerson(map.containerPointToLatLng(pt));
  });
}
