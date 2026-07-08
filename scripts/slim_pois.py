"""從完整備份產生「精簡格式」的地點檔給網頁載入，讓檔案盡量小。

輸入：../pois_full_backup.geojson（完整資料，含 poiId / status / 各類型）
輸出：data/pois.geojson（精簡格式，覆蓋）

精簡格式（不是標準 GeoJSON，體積小很多；map-app.js 會辨識並解析）：
{
  "fmt": "compact-poi-1",
  "scale": 100000,                       // 座標 = 整數 / scale
  "stops":   [[lngI, latI, "名稱"], ...], // 啟用中的補給站
  "gyms":    [[lngI, latI, "名稱"], ...], // 啟用中的道館
  "stops_i": [[lngI, latI, "名稱"], ...], // 未啟用補給站
  "gyms_i":  [[lngI, latI, "名稱"], ...]  // 未啟用道館
}
節省來源：不再每點重複 GeoJSON 結構、type 用分組表示、status 用 active/inactive
分開表示、座標用整數（去掉小數點與多餘位數）。
"""
import json, os

SRC = os.path.join('..', 'pois_full_backup.geojson')
DST = os.path.join('data', 'pois.geojson')
SCALE = 100000  # 5 位小數，約 1 公尺

data = json.load(open(SRC, encoding='utf-8'))
buckets = {'stops': [], 'gyms': [], 'stops_i': [], 'gyms_i': []}

for f in data.get('features', []):
    p = f.get('properties', {})
    t = p.get('type')
    if t == 'POKESTOP':
        key = 'stops'
    elif t == 'GYM':
        key = 'gyms'
    else:
        continue  # 略過 POWERSPOT 等地圖不顯示的類型
    if p.get('status') and p['status'] != 'ACTIVE':
        key += '_i'
    lng, lat = f['geometry']['coordinates'][:2]
    buckets[key].append([round(lng * SCALE), round(lat * SCALE), p.get('title', '')])

out = {'fmt': 'compact-poi-1', 'scale': SCALE}
out.update(buckets)
json.dump(out, open(DST, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

total = sum(len(v) for v in buckets.values())
print(f'輸出 {total} 點 → {DST}')
print(f'  啟用: 補給站 {len(buckets["stops"])} / 道館 {len(buckets["gyms"])}')
print(f'  未啟用: 補給站 {len(buckets["stops_i"])} / 道館 {len(buckets["gyms_i"])}')
print(f'  檔案大小: {os.path.getsize(DST) / 1024 / 1024:.1f} MB')
