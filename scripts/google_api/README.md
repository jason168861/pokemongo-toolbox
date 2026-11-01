# PogoKit Google API Data Collector

本機用的**唯讀**資料收集程式：AdSense、Search Console、GA4、PageSpeed Insights、CrUX。
部署時整個 `scripts/` 會被刪除，不會上線。設計細節見 `.private/ai_reports/COLLECTOR_DESIGN.md`（私人文件）。

> 本 README、測試與範例設定檔中的帳戶、資源、property ID 一律是假值。真實 ID 只會出現在被 git 忽略的資料目錄。

## 1. 安裝

需要 Python 3.11 與 git。

```powershell
python -m venv .private\venv-google
.private\venv-google\Scripts\python -m pip install -r scripts\google_api\requirements.txt
```

只使用 Google 官方套件：`google-api-python-client`、`google-auth`、`google-auth-oauthlib`（另有它們自動安裝的相依套件）。

## 2. 憑證位置

固定放在 repo 外面：`%LOCALAPPDATA%\PogoKit\google\`

| 檔案 | 用途 |
|---|---|
| `client_secret.json` | OAuth 桌面用戶端（程式只讀取，不複製） |
| `api_key.txt` | PSI、CrUX 用的 API key（只限這兩個 API） |
| `token.json` | 第一次 `auth` 後產生 |

- 可以用 `--cred-dir` 改位置，但如果新位置在 git 工作樹內，`token.json` 必須被 git 忽略，否則程式拒絕執行。
- 程式不會印出、記錄或複製任何憑證內容；所有輸出都經過遮蔽。

## 3. 首次授權（使用者親自執行一次）

```powershell
.private\venv-google\Scripts\python scripts\google_api\collect.py auth
```

- 會開瀏覽器，只申請三個唯讀權限：`adsense.readonly`、`webmasters.readonly`、`analytics.readonly`。
- 授權被撤銷或 token 失效時，其他指令會停止（exit code 3）並提示重新執行 `auth`，**不會自動開瀏覽器**。

## 4. 資料目錄

預設是**主目錄**的 `.private/google_data/`（就算從 worktree 執行也一樣）。也可以用 `--data-dir` 或環境變數 `POGOKIT_DATA_DIR` 指定。

寫入前一定會檢查：
1. 不可以位在 `.private/worktrees/` 底下；
2. `git check-ignore` 確認資料夾內的檔案被忽略；
3. `git ls-files` 確認裡面沒有被追蹤的檔案；
4. 建立資料夾時自動寫入內層 `.gitignore`（內容 `*`），作為第二道保險。

資料夾結構與 CSV 欄位說明會自動寫在資料目錄的 `README.md`。

## 5. 常用指令

以下省略前綴 `.private\venv-google\Scripts\python scripts\google_api\collect.py`。

| 指令 | 說明 |
|---|---|
| `check` | 檢查路徑、git 忽略、憑證檔是否存在、token scope、套件版本（不印內容） |
| `check --online` | 另外做一次 token refresh 與三個 API 的最小呼叫 |
| `discover` | 找出帳戶、資源、property（寫入 `state/inventory.json`） |
| `probe [--source X] [--dataset Y]` | 用最近 7 天試查，記錄可用的指標 |
| `--dry-run backfill` | 只印出預估的 unit／請求數，不發請求、不寫檔（需先 `discover`） |
| `backfill [--source adsense,gsc,ga4] [--dataset ...] [--start YYYY-MM-DD]` | 初次回補（AdSense 3 年、GSC 16 個月、GA4 從 property 建立日）；可以中斷後重跑續接 |
| `update [--source X --refetch-days N]` | 增量更新＋重抓最近資料（GSC 10 天、GA4 7 天、AdSense 本月＋上月且至少 35 天），之後更新快照 |
| `refetch --source X --dataset Y --start A --end B [--accept-empty]` | 強制重抓指定範圍；`--accept-empty` 才允許「之前有資料、這次 0 列」時清除 |
| `snapshot` | AdSense 廣告單元／網址管道／警告／政策問題、GSC sitemap |
| `status [--json] [--rebuild]` | 各資料集狀態；`--rebuild` 從 checkpoints 與 CSV 重建 manifest |
| `compact --source X --dataset Y` | 把日檔／月檔合併成一個 CSV（選用） |
| `psi [--urls F] [--runs N] [--max-tests 60]` | PageSpeed Insights（mobile＋desktop） |
| `crux [--urls F] [--no-history]` | CrUX 目前值＋History（40 期） |
| `inspect-urls --urls F [--max 50]` | 選用：URL Inspection（每日上限 2,000，第一輪不要大量呼叫） |

全域參數：`--max-requests N`、`--max-minutes M`（到上限就在 unit 之間停下，可續跑）、`--force-unlock`、`-v`、`--debug`（只多印出遮蔽過的 traceback）。

### exit code
| 碼 | 意義 |
|---|---|
| 0 | 全部成功 |
| 1 | 有部分 unit 失敗（其他照常完成；見 `status`） |
| 2 | 設定或路徑檢查失敗 |
| 3 | 需要使用者重新執行 `auth` |
| 4 | 配額、斷路器或上限停止（重新執行即可續跑） |
| 5 | 執行鎖被占用 |

## 6. 注意事項

- **PSI 會真的載入頁面**並執行站上的 JS（`js/pageview-counter.js` 寫入公開 Firebase 計數、`js/analytics.js`、AdSense 廣告請求）。不要大量或反覆重測，尤其是有廣告的頁面；`runs` 預設 1，總測試數有 `--max-tests` 上限。
- **只收集本站的資源**：Search Console 只選網域符合 `config/defaults.json` 的 `gsc.site_domain` 的資源（優先 `sc-domain:`），GA4 只選網頁串流網域符合 `ga4.site_domain` 的 property。帳號底下其他網站一律略過並記在 manifest 的 `skipped_scopes`；找不到符合的資源時停止，不會改成收集其他資源。舊網域的歷史資料要用 `--gsc-site` 明確指定，而且需要使用者同意。
- **GA4 不抓含 query string 的頁面維度**（交易清單分享網址的 `?s=` 是分享 id）。唯一例外是 `ga4_date_home_query`，只收首頁（`pagePath = "/"`，EXACT filter）。新增資料集時**不要對 trade-list 或 `/t/` 使用任何含 query 的維度**；程式也會拒絕。
- 頁面維度出現 `?`、`s=` 或 12 位以上數字時，該資料集會停止並記錄（不記錄命中的值），不會寫入 CSV。
  例外：`ga4_date_home_query` 只對 `s=` 與 12 位以上數字**逐列排除**、資料集繼續（所以它是首頁 query 流量的下限估計），
  被排除列的每日合計寫在 `ga4/csv/ga4_quality_dropped_daily.csv`。
- **首頁 query 停損門檻**（`config/defaults.json` 的 `ga4.home_drop_stop`，**按日判斷**，不是整月合計）：
  任何一天排除 > `max_rows`（預設 20）列就停；排除 ≥ `min_rows_for_ratio`（預設 3）列時，再看是否 > 當天總列數 × `max_ratio`（預設 1%）。
  停止時請**先人工確認原因**（例如首頁網址是否開始大量帶分享 id）再決定是否放寬；程式不會自動放寬。
  典型需要調整的情況：流量成長後，偶發的少量命中也開始觸發停損——確認是偶發後，再調高 `min_rows_for_ratio` 或 `max_ratio`。
- 「之前有資料、這次 0 列」預設保留舊資料並記為 `regression_to_empty`；確認後才用 `refetch --accept-empty` 清除。
- 沒有「從 raw 重建 CSV」的指令。CSV 的還原手段是 `csv_backup/`（最近 3 份）或 `refetch`。
- CSV 保留原始值（不加前綴單引號）。`query`、`eventName`、`page` 等文字欄位來自外部；**以 `=`、`+`、`-`、`@` 開頭的值，用 Excel 直接開啟時可能被當成公式執行**。建議用文字編輯器或程式讀取；一定要用試算表時，用「從文字/CSV 匯入」並設成文字欄位。
- 授權時如果沒有勾選全部三個權限，`auth` 會以 exit code 3 結束並提示重新授權。
- 不建立排程、不在背景執行；每個指令跑完就結束。
- 只使用免費 API 與免費配額；請在 Cloud Console 確認 API key 只限 PSI 與 CrUX、專案沒有綁定帳單。

## 7. 設計取捨與已知未實作

**刻意的取捨**
- **GSC 搜尋類型 probe 的結果不沿用**：每種有資料的搜尋類型，probe（整段期間的 date 維度，1 次請求）之後，`gsc_<type>_date` 資料集在回補時會再查一次。這是為了讓 date 資料集也走一般的 unit／checkpoint／CSV 流程；代價是每種類型多 1 次請求。
- **AdSense 截斷記在父 unit 上**：報表被截斷時會把日期範圍對半切開重查到單日，但 checkpoint 只記父 unit（例如整個月），狀態是 `truncated`，並在 `truncated_dates` 列出切到單日後仍被截斷的日期。manifest 的 `truncated_dates` 是各 unit 的彙總，`units.truncated` 是被截斷的 unit 數。已定案且被截斷的 unit 不會自動重抓（同一天再抓還是會截斷），要重抓請用 `refetch`。

**已知未實作**
- raw 寫入中斷時會留下 `*.partial` 檔。`check` 會列出數量，但**不會**針對「超過 1 天的 .partial」發出警告，也不會自動刪除；請人工檢查後刪除。

## 8. 測試（不需要憑證）

```powershell
.private\venv-google\Scripts\python -m unittest discover -s scripts\google_api\tests -t scripts\google_api -v
```

部分測試需要 git（會建立臨時 git repo 驗證 check-ignore）；找不到 git 時會自動略過。
