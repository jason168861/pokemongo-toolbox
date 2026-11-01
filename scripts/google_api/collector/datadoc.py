"""資料目錄的 README.md（資料字典與口徑提醒）。每次執行時若內容不同就更新。"""

DATA_README = """# PogoKit Google 資料（私人、不進 git）

這個資料夾由 `scripts/google_api/collect.py` 產生。內容一律被 git 忽略（本資料夾的 `.gitignore` 是 `*`）。
**不要把這裡的檔案貼進報告、訊息或 repo。**

## 結構
- `manifest.json`：各資料集的狀態、涵蓋日期、列數、已知限制、完整性統計。
- `collection_log.jsonl`：每次執行的事件（已遮蔽）。
- `state/`：checkpoints（續跑用）、inventory（帳戶／資源／property）、probe（可用指標）、執行鎖。
- `<來源>/raw/`：原始 API 回應（gzip，不覆蓋）。**raw 可能含使用者輸入的長數字（例如疑似訓練家代碼）或分享 id，
  請勿公開、複製或貼進報告與訊息；分析一律讀 CSV。** 不要修改 raw 的內容；真的要清除時由使用者決定，以刪除整個檔案的方式處理。讀法：
  `python -c "import gzip,json,sys;print(json.dumps(json.load(gzip.open(sys.argv[1])),ensure_ascii=False,indent=1))" <檔案>`
- `<來源>/csv/<資料集>/`：正規化 CSV。逐日資料集是 `<YYYY-MM>/<YYYY-MM-DD>.csv`，其餘是 `<YYYY-MM>.csv`。
- `<來源>/csv_backup/`：CSV 被替換前的版本（每個檔案保留最近 3 份）。
- `<來源>/compact/`：`compact` 指令產生的合併檔（衍生檔，以日檔／月檔為準）。
- `<來源>/snapshots/`：清單類資料（廣告單元、sitemap…）的快照。

## ⚠ 不要直接用 Excel 開啟含文字欄位的 CSV
`query`（Search Console 搜尋字詞）、`eventName`（GA4 事件名稱）、`page`、`pagePath`、`landingPage`、
`sessionSourceMedium`、AdSense 的 `page_url` 等文字欄位，內容來自外部（任何人都能搜尋任何字、帶任何參數）。
**以 `=`、`+`、`-`、`@` 開頭的值，用 Excel 或其他試算表軟體直接開啟時可能被當成公式執行**（CSV 公式注入）。
CSV 刻意**保留原始值、不加前綴單引號**，以確保程式與 AI 讀取時資料完整。
建議改用文字編輯器或程式（Python 的 csv 模組、pandas）讀取；一定要用試算表時，請用「資料 → 從文字/CSV 匯入」並把這些欄位設成文字。

## CSV 共通欄位
- `date`：日期（時區見 `tz` 欄）；`scope_id`：帳戶／資源／property；`is_final`：是否已定案（false 是暫定，之後會重抓）；`fetched_at`：抓取時間（UTC）。
- 指標欄位固定是該資料集的完整候選清單；API 不支援的指標留空（見 manifest 的 metrics_available）。

## GA4 品質檔
- `ga4/csv/ga4_quality.csv`：**每個 unit（通常是一個月）一列**。欄位：dataset、scope_id、unit_start、unit_end、rows（寫入的列數）、
  other_rows／other_share（`(other)` 列）、data_loss_from_other_row、subject_to_thresholding、sampling、
  dropped_rows_by_rule（首頁 query 逐列排除的 {規則: 列數}，JSON）。
- `ga4/csv/ga4_quality_dropped_daily.csv`：**每天一列**，只有 `ga4_date_home_query` 有。欄位：dataset、scope_id、date、
  total_rows（當天排除前的總列數）、dropped_rows（當天排除的列數）、被排除列的 screenPageViews／eventCount／userEngagementDuration 合計。
  不含任何維度值。用途：對帳「home_query 和 ga4_date_page 首頁的差距有多少來自排除」。
- 兩個檔的關係：ga4_quality 的 dropped_rows_by_rule 是該 unit 的規則別合計；dropped_daily 是同一批排除列依日期拆開、附上指標合計。
  不可加總的指標（totalUsers、activeUsers）沒有合計。

## 首頁 query 停損門檻（`config/defaults.json` 的 `ga4.home_drop_stop`）
- **按日判斷**（不是整個月合計）：任何一天排除 > `max_rows`（預設 20）列就停；排除 ≥ `min_rows_for_ratio`（預設 3）列時，
  再看是否 > 當天總列數 × `max_ratio`（預設 1%）。
- 停止時資料集不寫入 CSV，manifest 會記 `stopped_reason`。**請先人工確認原因再決定是否放寬**（例如首頁網址是否開始大量帶分享 id）；
  程式不會自動放寬門檻。
- 什麼時候該調：流量成長後，偶發的少量命中也可能因為「≥ 3 列」而觸發比例停損；確認是偶發而不是網站行為改變後，
  才調高 `min_rows_for_ratio` 或 `max_ratio`。

## 口徑提醒（分析時必讀）
- 時區不同：Search Console 是美國太平洋時間；AdSense、GA4 是各自帳戶／property 的時區。**不同時區的日期不可直接 join 後加總。**
- **AdSense 分析本站請用 `*_site` 版本**：同一個 AdSense 帳戶底下可能有多個網站。`adsense_date`、`adsense_date_country`、
  `adsense_date_platform`、`adsense_date_adunit`、`adsense_date_adformat`、`adsense_date_placement` 是**帳戶層級資料**
  （整個帳戶的加總，某個日期之前含其他網站；各網域有資料的期間見 manifest 的 `account_domains` 與 known_limits，取自實際資料），
  保留供稽核。它們各有一個只含本站的版本 `<名稱>_site`（例如 `adsense_date_site`），網域取自設定 `adsense.site_domain`，
  以 `filters=DOMAIN_NAME==<網域>` 在 API 端篩選；如果 API 不接受 filter，會改用「維度加 DOMAIN_NAME、下載後篩選」，
  manifest 的 `site_method`（filter／dimension）會註明實際用了哪一種。
  `adsense_date_urlchannel` 沒有 `_site` 版本，分析本站時請以 `adsense_date_domain` 的 `domain_name` 對照各網域期間。
  `adsense_date_domain`、`adsense_date_pageurl` 本身就能區分網域／網址。
- AdSense 預估收益會在月結與無效流量調整後修正；AdSense 的「網頁瀏覽」≠ GA4 的 screenPageViews。
- GA4 的 totalUsers、activeUsers、newUsers、engagementRate、averageSessionDuration 跨日或跨維度加總沒有意義。
- GA4 一般資料集只用 pagePath／landingPage（不含 query）；`ga4_date_home_query` 只收首頁（pagePath = "/"），
  而且命中分享 id 或 12 位以上數字的列會被逐列排除，所以它是首頁 query 流量的**下限估計**；
  被排除部分的每日合計見 `ga4/csv/ga4_quality_dropped_daily.csv`。
- Search Console 的 query 清單不完整（匿名查詢），落差見 `search_console/csv/gsc_quality_<type>/`。
- CrUX 是 28 天滾動平均；History 各期互相重疊，不能當成每日或每週的獨立數據。`status=no_data` 表示沒有資料，不是 0。
- PSI 測試會真的載入頁面（含 GA4、Firebase 計數、廣告請求）；分析流量時可用 `psi_runs.csv` 的 fetch_time 對照排除。
"""
