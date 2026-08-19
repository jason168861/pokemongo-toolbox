# 寶可夢 GO 交易清單產生器

瀏覽所有寶可夢組合(異色 / 型態 / 造型 / 公母 / 極巨化 / 超極巨化 / 活動背卡),
分成「想要」與「可換」兩欄,匯出成一張可分享的圖片(38 種底圖樣式)。支援 7 種語言。

## 檔案
- `index.html` — 前端(優先讀 `data/*.local.json`;沒有才退回遠端網址)
- `alias-editor.html` — 搜尋別名的建檔介面(產出 `data/aliases.json`,見下方「搜尋別名」)
- `build_data.py` — 重建來源資料
- `fetch_assets.py` — 把用到的圖存到 `assets/`,並產出 `*.local.json`(本機路徑版)
- `preview.py` — 本機預覽(關快取,改完重新整理就生效)
- `data/` — 資料 JSON
- `assets/img/` — 寶可夢 sprite(`pm*` 來自 PokeMiners、`wiki_*` 見下方「造型」說明)
- `assets/bg/` — 背卡圖
- `assets/badge_*.png` — 極巨化 / 超極巨化徽章
- `assets/type/`、`assets/team/` — 匯出圖樣式用的官方屬性徽章 / 屬性場景 / 隊徽

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

## 搜尋別名

搜尋框比對的是**七種語言的官方名稱**,但社群講的常常是別的詞:舊譯名(乘龍 / 3D龍 / 比雕)、
造型俗稱(萬聖節、聖誕)、背卡的中文地名(台南、寶可夢中心)、一次要看一整組(三神鳥、關東御三家)。
這些對照表放在 `data/aliases.json`,搜尋時與官方名稱一起比對;檔案不存在就靜默跳過,搜尋退回原本行為。

因為是子字串比對,**簡稱不必建檔** —— 打「班」本來就找得到「班基拉斯」。
要建的只有「字面上完全對不到」的詞。

```jsonc
{"kind":"mon", "terms":["乘龍"],   "targets":["131"],              "note":"舊譯名"}
{"kind":"form","terms":["萬聖節"], "targets":["HALLOWEEN_2017", …]}          // 型態 / 造型代碼
{"kind":"bg",  "terms":["台南"],   "targets":["GO Tainan background.png", …]} // 背卡 image_name
```

一個 `terms` 可以配多個 `targets`(= 群組別名),一筆一行方便看 git diff。
三個搜尋框(選取網格、自由搭配的寶可夢與背卡)走的是同一套比對。

### 建檔介面

```bash
python preview.py       # → http://127.0.0.1:8797/alias-editor.html
```

左邊照「寶可夢 / 型態造型 / 背卡」三個分頁挑目標(有圖、可搜尋、可複選),右邊打別名按 Enter 就建好。
選多個目標再加詞就是群組別名。另外兩個分頁:**別名總表**可直接改詞/備註、刪整組、合併重複;
**測試搜尋**用與 `index.html` 相同的邏輯,打一個詞立刻看會篩出什麼,建完馬上驗收。

按「儲存」會 POST 回 `preview.py`,直接覆寫 `data/aliases.json`(舊檔留成 `.bak`)。
`preview.py` 只接受本機來的請求、只准寫這一個檔、JSON 壞掉就不寫。
用 `file://` 開或在線上開時寫不了檔,會自動退回「下載檔案」讓你自己覆蓋。
編到一半沒存會留在 localStorage,下次開自動問要不要接著編;<kbd>Ctrl</kbd>+<kbd>Z</kbd> 復原、<kbd>Ctrl</kbd>+<kbd>S</kbd> 儲存。

`build_data.py` / `fetch_assets.py` **不會碰** `aliases.json` —— 它是純手工維護的,更新資料不會蓋掉。

## 資料來源

感謝以下社群專案與 wiki:

| 內容 | 來源 |
|------|------|
| 寶可夢 sprite(型態 / 造型 / 公母 / 異色 / 超極巨化) | [PokeMiners/pogo_assets](https://github.com/PokeMiners/pogo_assets) |
| 各語言名稱 | PokeMiners GAME_MASTER i18n |
| 哪些 form 屬於「造型」 | GAME_MASTER `formSettings.isCostume` |
| 可否極巨化 | [Bulbapedia](https://bulbapedia.bulbagarden.net/) `Dynamax (GO)` |
| 背卡 + 可用寶可夢(含異色 / 極巨化 / 暗影,進化型明列) | Bulbapedia `Background (GO)` |
| 屬性徽章 / 屬性場景 / 隊徽(匯出圖樣式用) | PokeMiners `Images/Badges/Types`、`Images/Type Backgrounds`、`Images/Pokestops and Gyms` |
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

## 匯出圖樣式(skin)

製圖畫面下方的「圖片風格」有 38 種底圖,分五類:
**經典**(6,原本的主題配色)/ **漸層**(6)/ **科技**(5)/ **屬性**(18 種寶可夢屬性)/ **隊伍**(3)。

介面主題(`THEME`,頁首的「風格」下拉)與匯出圖樣式(`SKIN`)是**兩個獨立的設定**,
分別存在 `bgtoolTheme` 與 `bgtoolSkin` —— 所以可以用淺色介面做一張火屬性的深色圖。
頁首的下拉會同時換掉兩者(維持原本一個下拉換全部的手感);製圖畫面的選擇器只換匯出圖。

一個 skin = 原本的配色欄位(`panel` / `cardbg` / `line` / `title` / `sec1` / `sec2` / `fly` / `foot`)
加上底圖規格,全部定義在 `index.html` 的 `SKINS`:

| 欄位 | 說明 |
|------|------|
| `grad` + `angle` | 多色停漸層;角度用 CSS 慣例(180 = 由上而下,預設) |
| `blobs` | `[x, y, r, 色]` 光暈。單位一律是**圖寬**(連 `y` 也是)→ 清單長短不影響頂部構圖 |
| `fx` | 圖樣,可給一個或一陣列。`grid` `scan` `diag` `dots` `hex` `waves` `rays` `circuit` `cracks` `bokeh` `particles`(`particles` 再以 `shape` 選 `star`/`flake`/`spark`/`leaf`/`bubble`/`ring`/`bit`/`shard`/`ember`) |
| `banner` + `bannerOp` | 頁首橫幅圖(官方屬性場景),鋪滿頂部 0.34 個圖寬,下緣淡出接回漸層 |
| `mark` | 浮水印(官方屬性徽章 / 隊徽):`{src, op, size, x, y, rot, tile, tsize, n, seed}`。`tile` 有值就再沿整張圖散落小的,長清單往下捲才不會只有頂部有裝飾 |
| `vig` | 暗角強度 0~1 |
| `shadow` | 預設文字(標題 / CAN FLY / 區塊標籤)要不要加陰影;新樣式一律開,底圖有花紋時純色字才不會被吃掉 |

### 官方素材

屬性與隊伍樣式用的是遊戲本身的圖,由 `fetch_assets.py` 的 `make_style_assets()`
從本機 PokeMiners clone(`POGO_ASSETS`)轉存成小 WebP,共 39 檔約 270KB:

| 來源 | 產出 | 用途 |
|------|------|------|
| `Images/Badges/Types/Badge_18..35.png` | `assets/type/badge_<屬性>.webp` | 屬性徽章 → 浮水印 + 選擇器縮圖的識別圖示 |
| `Images/Type Backgrounds/details_type_bg_*.png` | `assets/type/bg_<屬性>.webp` | 屬性場景 → 頁首橫幅 |
| `Images/Pokestops and Gyms/team_{blue,red,yellow}.png` | `assets/team/{mystic,valor,instinct}.webp` | 隊徽 → 浮水印 |

徽章檔名是 GAME_MASTER 的 badge enum(`BADGE_TYPE_NORMAL`=18 … `BADGE_TYPE_FAIRY`=35),
`TYPE_ORDER` 就是照這個順序對應的 —— 來源哪天插新檔進去,這裡要跟著改。

前端只在選到該樣式時才下載對應的圖(選擇器也只預載「目前展開的那一類」)。
`paintBackdrop` 是同步的,所以 `drawBaseTo` 會先 `await preloadSkin(T)` 把圖抓進快取,
再由 `imgNow()` 同步取用 —— 少了這步,浮水印在預覽看得到、匯出時卻會漏掉。

⚠ 加新樣式時,底圖的每一筆都必須只由**版面座標**決定。匯出走分塊路徑時,
每一塊會各自呼叫一次 `paintBackdrop`,只要摻進 `Math.random()` 或看 canvas 尺寸,
接縫處的花紋就會對不起來 —— 所以隨機類圖樣一律用 `seedRand(帶號)`,
種子只能來自「第幾個帶狀區塊 / 第幾格」這種絕對位置。
尺寸則一律以 `U = W/1000` 為單位,換每排數量時花紋粗細才會等比例跟著走。

經典六款直接沿用 `THEMES[].exp`,不經過底圖引擎的任何新欄位 → 舊使用者存過的圖不會變樣。

## 圖片顯示

sprite 四周常有一圈透明 padding。前端會掃描出主體的 bounding box,
水平置中、垂直靠下擺放,放大上限 `MAXUP`(見 `index.html`)以避免小圖被放大到模糊。
網格用 128px WebP 縮圖,匯出 PNG 時改用 256px 原圖重畫。

## 授權與聲明

程式碼為個人非商業用途的同好作品。
寶可夢、Pokémon GO 及相關圖像之著作權屬 Nintendo / Creatures Inc. /
GAME FREAK inc. / Niantic, Inc. 所有,本專案與上述公司無任何關聯。
