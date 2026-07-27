# 寶可夢 GO 交易清單產生器

全部圖片自我託管(不盜連別人),資料可自動更新。

## 檔案
- `index.html` — 前端(優先讀 `data/*.local.json` 本機圖;沒有才退回遠端)
- `build_data.py` — 重建來源資料(遠端 URL 版)
- `fetch_assets.py` — 把用到的圖下載到 `assets/`,並產出 `*.local.json`(本機路徑版)
- `preview.py` — 本機預覽(關快取,改完重新整理就生效)
- `data/` — 資料 JSON
- `assets/img/` — 寶可夢 sprite(`pm*` 來自 PokeMiners、`wiki_*` 是對不到本機檔時的 wiki 造型原圖)
- `assets/bg/` — 背卡圖
- `assets/badge_*.png` — 極巨化/超極巨化徽章

## 跑起來(本機預覽,不用 push)
```bash
python preview.py          # 自動開 http://127.0.0.1:8797
python preview.py --lan    # 手機也能連
python preview.py -p 9000  # 換埠號
```
改完 `index.html` 或 `data/*.json` 直接重新整理即可 —— `preview.py` 一律送 `no-store`,
不會像 `python -m http.server` 那樣吃到瀏覽器快取。

## 更新流程(有新活動/新寶可夢時)
```bash
# 1) 先更新你的 PokeMiners clone(sprite 與中文名來源)
cd /path/to/pogo_assets && git pull

# 2) 重建來源資料(抓最新 GAME_MASTER + Fandom 背卡)
cd 回本資料夾
python build_data.py

# 3) 下載新圖到本機(已存在的 sprite 會跳過;背卡一律重抓最新藝術圖)
python fetch_assets.py

# 4) 先本機看過再決定要不要 commit
python preview.py
```
以上四步 `python update.py` 會做前三步(`--commit` 可順便 commit/push)。

## 資料來源
| 內容 | 來源 |
|------|------|
| 寶可夢 sprite（造形/服裝/公母/異色/超極巨化） | PokeMiners `pogo_assets` |
| 中文名 | PokeMiners GAME_MASTER 繁中 i18n |
| 哪些 form 其實是「造型」 | GAME_MASTER `formSettings.isCostume` |
| 可否極巨化 | Bulbapedia `Dynamax (GO)` |
| 背卡 + 可用寶可夢（每隻直接帶 異色/極巨化/暗影，進化型明列） | **Bulbapedia** `Background (GO)` |
| 背卡補充（Bulbapedia 整張缺、或整隻沒提到的） | Fandom `Backgrounds` |

### 背卡上的「造型」怎麼決定 sprite
wiki 寫的是自家代號(Bulbapedia `0025Willow`、Fandom `ci=Pikachu willow`),跟 PokeMiners 的
造型代碼(`SPRING_2023_MYSTIC`…)沒有官方對照表。`build_data.py` 走三層,對不到就往下掉:

1. **型態** `resolve_suffix` / `resolve_form` → `128PA`→`PALDEA_AQUA`、`888C`→`CROWNED_SWORD`
2. **本機造型** `resolve_costume` → `Jan2020`→`JAN_2020_NOEVOLVE`、`Mystic`→`SPRING_2023_MYSTIC`
   只在「全 dex 唯一命中」時採用,寧可不對也不亂對
3. **wiki 原圖** → `File:GO0025Willow.png`(Bulbapedia)/ `File:Pikachu willow.png`(Fandom)
   兩邊都是 256×256、就是頁面上顯示的那張,必定存在。`fetch_assets.py` 會下載成
   `assets/img/wiki_*.png` 一併自我託管

跑 `build_data.py` 結尾會印**健檢**:MSP 標籤總數 vs 解析數、三層各命中幾筆、對不到的後綴清單。
來源哪天改格式,這裡會立刻現形。

> Bulbapedia 在 Cloudflare 後面,`build_data.py` 用 `cloudscraper` 取其 API(`pip install cloudscraper`);
> 背卡圖床 archives.bulbagarden.net 可直接下載。改用 Bulbapedia 的好處:每張背卡的**異色/極巨化資格**都標明、進化型明列、更新更快。

## 注意
- 圖片版權屬 Niantic / 任天堂 / 寶可夢公司。個人/非商業 fan 用途通常被容忍;公開發佈請加免責聲明,商業化有風險。
- `build_data.py` 內的 `POGO_ASSETS` 需指到你的 pogo_assets clone(或設環境變數 `POGO_ASSETS`)。
