# 寶可夢 GO 交易清單產生器

全部圖片自我託管(不盜連別人),資料可自動更新。

## 檔案
- `index.html` — 前端(優先讀 `data/*.local.json` 本機圖;沒有才退回遠端)
- `build_data.py` — 重建來源資料(遠端 URL 版)
- `fetch_assets.py` — 把用到的圖下載到 `assets/`,並產出 `*.local.json`(本機路徑版)
- `data/` — 資料 JSON
- `assets/img/` — 寶可夢 sprite(來自 PokeMiners)
- `assets/bg/` — 背卡圖(來自 Fandom)
- `assets/badge_*.png` — 極巨化/超極巨化徽章

## 跑起來
```bash
python -m http.server 8797
# 開 http://localhost:8797
```

## 更新流程(有新活動/新寶可夢時)
```bash
# 1) 先更新你的 PokeMiners clone(sprite 與中文名來源)
cd /path/to/pogo_assets && git pull

# 2) 重建來源資料(抓最新 GAME_MASTER + Fandom 背卡)
cd 回本資料夾
python build_data.py

# 3) 下載新圖到本機(已存在的 sprite 會跳過;背卡一律重抓最新藝術圖)
python fetch_assets.py
```
跑完 `index.html` 就會顯示最新內容,且全部用本機圖。

## 資料來源
| 內容 | 來源 |
|------|------|
| 寶可夢 sprite（造形/服裝/公母/異色/超極巨化） | PokeMiners `pogo_assets` |
| 中文名 | PokeMiners GAME_MASTER 繁中 i18n |
| 可否極巨化（sprite 網格用） | GAME_MASTER `breadTierGroup` |
| 背卡 + 可用寶可夢（每隻直接帶 異色/極巨化/暗影，進化型明列） | **Bulbapedia** `Background (GO)` |

> Bulbapedia 在 Cloudflare 後面,`build_data.py` 用 `cloudscraper` 取其 API(`pip install cloudscraper`);
> 背卡圖床 archives.bulbagarden.net 可直接下載。改用 Bulbapedia 的好處:每張背卡的**異色/極巨化資格**都標明、進化型明列、更新更快。

## 注意
- 圖片版權屬 Niantic / 任天堂 / 寶可夢公司。個人/非商業 fan 用途通常被容忍;公開發佈請加免責聲明,商業化有風險。
- `build_data.py` 內的 `POGO_ASSETS` 需指到你的 pogo_assets clone(或設環境變數 `POGO_ASSETS`)。
