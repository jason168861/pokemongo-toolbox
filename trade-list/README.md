# 寶可夢 GO 交易清單產生器

瀏覽所有寶可夢組合(異色 / 型態 / 造型 / 公母 / 極巨化 / 超極巨化 / 活動背卡),
分成「想要」與「可換」兩欄,匯出成一張可分享的圖片。支援 7 種語言。

## 檔案
- `index.html` — 前端(優先讀 `data/*.local.json`;沒有才退回遠端網址)
- `build_data.py` — 重建來源資料
- `fetch_assets.py` — 把用到的圖存到 `assets/`,並產出 `*.local.json`(本機路徑版)
- `preview.py` — 本機預覽(關快取,改完重新整理就生效)
- `data/` — 資料 JSON
- `assets/img/` — 寶可夢 sprite(`pm*` 來自 PokeMiners、`wiki_*` 見下方「造型」說明)
- `assets/bg/` — 背卡圖
- `assets/badge_*.png` — 極巨化 / 超極巨化徽章

## 需求
```bash
pip install cloudscraper Pillow
```

## 本機預覽
```bash
python preview.py          # 自動開 http://127.0.0.1:8797
python preview.py --lan    # 同網段的手機也能連
python preview.py -p 9000  # 換埠號
```
改完 `index.html` 或 `data/*.json` 直接重新整理即可 —— `preview.py` 一律送 `no-store`,
不會像 `python -m http.server` 那樣吃到瀏覽器快取。

## 更新流程(有新活動 / 新寶可夢時)
```bash
python update.py            # pull PokeMiners → build_data → fetch_assets
python update.py --commit   # 跑完順便 commit / push
```
拆開跑也可以:
```bash
cd /path/to/pogo_assets && git pull   # 1) sprite 與各語言名稱來源
python build_data.py                  # 2) 重建 data/*.json
python fetch_assets.py                # 3) 下載圖片 + 產生縮圖
python preview.py                     # 4) 本機確認後再 commit
```
`build_data.py` 需要 `POGO_ASSETS` 指到本機的 PokeMiners clone
(預設與 repo 同層,或設環境變數覆寫)。實際只會用到兩個子目錄:
`Images/Pokemon - 256x256/Addressable Assets` 與 `Texts/Latest APK/JSON`。

## 資料來源

感謝以下社群專案與 wiki:

| 內容 | 來源 |
|------|------|
| 寶可夢 sprite(型態 / 造型 / 公母 / 異色 / 超極巨化) | [PokeMiners/pogo_assets](https://github.com/PokeMiners/pogo_assets) |
| 各語言名稱 | PokeMiners GAME_MASTER i18n |
| 哪些 form 屬於「造型」 | GAME_MASTER `formSettings.isCostume` |
| 可否極巨化 | [Bulbapedia](https://bulbapedia.bulbagarden.net/) `Dynamax (GO)` |
| 背卡 + 可用寶可夢(含異色 / 極巨化 / 暗影,進化型明列) | Bulbapedia `Background (GO)` |
| 背卡補充(Bulbapedia 未收錄的卡或物種) | [Pokémon GO Wiki (Fandom)](https://pokemongo.fandom.com/) `Backgrounds` |

兩個 wiki 都是透過官方 `api.php` 讀取,並在批次之間節流。
Bulbapedia 的 API 需要 `cloudscraper` 才能正常連線。

## 背卡上的「造型」怎麼決定 sprite

wiki 用的是自家代號(Bulbapedia `0025Willow`、Fandom `ci=Pikachu willow`),
與 PokeMiners 的造型代碼(`SPRING_2023_MYSTIC`…)沒有官方對照表。
`build_data.py` 走三層,對不到就往下掉:

1. **型態** `resolve_suffix` / `resolve_form` → `128PA`→`PALDEA_AQUA`、`888C`→`CROWNED_SWORD`
2. **本機造型** `resolve_costume` → `Jan2020`→`JAN_2020_NOEVOLVE`、`Mystic`→`SPRING_2023_MYSTIC`
   只在「該 dex 唯一命中」時採用,寧可不對也不亂對
3. **wiki 原圖** → `File:GO0025Willow.png`(Bulbapedia)/ `File:Pikachu willow.png`(Fandom)
   兩邊都是 256×256、就是 wiki 頁面上顯示的那張,必定存在;
   `fetch_assets.py` 會存成 `assets/img/wiki_*.png`

第三層讓覆蓋率達到 100% 且不需維護對照表 —— wiki 頁面能顯示的造型,這裡就抓得到。

跑 `build_data.py` 結尾會印**健檢**:MSP 標籤總數 vs 解析數、三層各命中幾筆、
對不到的後綴清單。來源哪天改格式,這裡會立刻現形。

## 圖片顯示

sprite 四周常有一圈透明 padding。前端會掃描出主體的 bounding box,
水平置中、垂直靠下擺放,放大上限 `MAXUP`(見 `index.html`)以避免小圖被放大到模糊。
網格用 128px WebP 縮圖,匯出 PNG 時改用 256px 原圖重畫。

## 授權與聲明

程式碼為個人非商業用途的同好作品。
寶可夢、Pokémon GO 及相關圖像之著作權屬 Nintendo / Creatures Inc. /
GAME FREAK inc. / Niantic, Inc. 所有,本專案與上述公司無任何關聯。
