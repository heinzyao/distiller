# 變更紀錄

本檔案記錄專案的所有重要變更。

## [2.7.0] - 2026-04-12

### 新增
- **雞尾酒推薦系統**（`distiller_scraper/cocktail_db.py`、`distiller_scraper/recommender.py`）
  - 支援 23 款經典雞尾酒：Negroni、Old Fashioned、Martini、Margarita 等
  - 多成分覆蓋：基酒、利口酒、苦艾酒分別推薦
  - 三層推薦模式（dynamic / dynamic_or_static / static_only）
  - 風味向量評分：雞尾酒相似度（60%）+ 用戶偏好（25%）+ 評分（15%）
  - LINE Bot 新指令：`雞尾酒 <名稱> [偏好]`

- **Claude API 個人化推薦說明**（`distiller_scraper/recommender.py`）
  - 設定 `ANTHROPIC_API_KEY` 後自動啟用
  - 以 claude-haiku 為首選烈酒生成品酒師口吻說明（2-3 句，繁體中文）
  - 無 key 或 API 失敗時靜默跳過，不影響主功能
  - Cloud Run 啟用方式：先建立 Secret Manager secret，再手動執行
    ```bash
    echo -n "sk-ant-..." | gcloud secrets create DISTILLER_ANTHROPIC_API_KEY --data-file=- --project=<PROJECT_ID>
    gcloud run services update distiller-bot --region asia-east1 \
      --update-secrets ANTHROPIC_API_KEY=DISTILLER_ANTHROPIC_API_KEY:latest
    ```

- **利口酒子分類爬取**（`distiller_scraper/config.py`）
  - 新增 `LIQUEURS_STYLES`：Bitter / Amaro / Anise / Coffee / Floral / Fruit / Herbal / Chocolate / Dairy 9 個子分類
  - DB 利口酒資料從 8 筆 → 308 筆（含 Campari、Aperol、Amaro Nonino、Luxardo Maraschino）

### 修復
- **`?category=liqueurs-bitters` URL 參數失效**（`distiller_scraper/scraper.py`）
  - distiller.com 已靜默忽略此參數，回傳全站排行榜
  - 修復：改用 `?spirit_style_id=<id>` 子分類精確過濾
- **`run.py` 成功判斷邏輯**：0 筆新增不再誤判為失敗（DB 已是最新屬正常）
- **LINE 失敗通知**：scraper 拋出例外時通知訊息不再被跳過（commit `9bf5447`）

### 資料
- 資料庫總筆數：3,142 筆（+300 利口酒）
- 測試：402 passed（+29 新增 test_recommender.py）

## [2.6.0] - 2026-03-17

### 新增
- **`scroll_page()` 捲動重試機制**：`JavascriptException`（`document.body` 為 null）時自動重試，最多 `MAX_SCROLL_RETRIES`（預設 3）次，每次間隔 1 秒
- **Driver 重啟觸發條件擴充**：`_should_restart()` 新增兩項 JS null 錯誤字串（`Cannot read properties of null`、`null is not an object`），與既有的 `invalid session id` / `session deleted` 並列
- **`_health_check()` 預飛檢測**：`scrape()` 啟動後、類別迴圈前執行健康檢查，載入 BASE_URL 並確認 `document.body.scrollHeight` 可讀；失敗則放棄整次爬取
- **頁面層級重試**：`scrape_category_paginated()` 每頁加入最多 `PAGE_RETRY_COUNT`（預設 2）次重試，最後一次失敗時自動嘗試 driver 重啟
- **`scrape_runs` 執行紀錄**：`run_test` / `run_medium` / `run_full` 皆呼叫 `storage.record_scrape_run()` 與 `storage.finish_scrape_run()`，正確寫入 `status`（`completed` / `completed_with_errors` / `failed`）
- **重複執行防護**：`_should_skip_run(storage)` 於每次 run 函式開頭檢查 20 小時內是否已有成功執行，有則提前返回（fail-open：DB 查詢失敗時不跳過）
- **LINE 失敗通知強化**：`notify_failure()` 新增 `page_errors: int` 與 `error_details: str` 參數，通知訊息顯示頁面錯誤數與錯誤詳情區塊
- **`run_scraper.sh` 遷移至 `uv run`**：移除 venv 啟動邏輯，改為 `uv run python run.py ...`；同時修正 `EXIT_CODE=${PIPESTATUS[0]}` 正確抓取 tee 管線前的退出碼

### 失敗處理常數（`config.py`）
| 常數 | 預設值 | 用途 |
|------|--------|------|
| `MAX_SCROLL_RETRIES` | 3 | scroll_page() 重試上限 |
| `MAX_RESTART_ATTEMPTS` | 2 | 單次爬取 driver 重啟上限 |
| `HEALTH_CHECK_TIMEOUT` | 10 | 健康檢查逾時（秒） |
| `PAGE_RETRY_COUNT` | 2 | 頁面重試次數 |
| `RESTART_TRIGGER_ERRORS` | (list) | 觸發重啟的錯誤字串清單 |
| `DUPLICATE_RUN_WINDOW_HOURS` | 20 | 重複執行檢測窗口（小時） |

### 測試
- **新增 36 個測試**（303 → 339 passed）
- 新增測試模組：`test_scroll_page.py`、`test_restart_driver.py`、`test_health_check.py`、`test_retry_logic.py`、`test_scrape_runs.py`、`test_duplicate_detection.py`
- `test_notify.py` 新增 5 個 `notify_failure()` 擴充測試
- `test_config.py` 新增 6 個失敗處理常數驗證測試

## [2.5.3] - 2026-03-14

### 修復
- **排程腳本 venv 路徑錯誤**：`scripts/run_scraper.sh` 與 `com.distiller.scraper.plist` 的 Python 路徑寫死為 `venv/bin/python`，但專案使用 `uv` 管理的 `.venv`，導致 3/14 排程直接 exit 1、爬蟲未執行、LINE 通知未發送
  - `run_scraper.sh`：`venv/bin/python` → `.venv/bin/python`
  - `com.distiller.scraper.plist` PATH：`venv/bin` → `.venv/bin`
  - 重新載入 launchd 排程（`launchctl unload/load`）
- **LINE 通知 DNS 解析失敗（3/12、3/13）**：確認 LINE 憑證設定正確，手動測試通知發送成功；排程已固定 10:00 執行以規避凌晨 DNS 問題

## [2.5.2] - 2026-03-10

### 修復
- **Chrome 145 renderer timeout**：3/10 凌晨排程 28 次頁面 timeout（0 筆資料）根治
  - 根因：Distiller.com React 應用持續發送背景 XHR，`document.readyState` 永遠不觸發 `load` 事件
  - 新增 `page_load_strategy = 'none'`：不等待 load 事件，以固定延遲（`INITIAL_PAGE_DELAY`）等待 React 渲染
  - 新增反偵測選項：`--disable-blink-features=AutomationControlled`、`excludeSwitches`、`useAutomationExtension=False`
  - User-Agent 更新為 `Chrome/145.0.0.0`（與實際版本一致）
- **詳情頁渲染等待不足**：`scrape_spirit_detail()` 原用 `time.sleep(2)` 等待頁面，`page_load_strategy='none'` 後不足以等 React 水合，改為 `INITIAL_PAGE_DELAY = 5` 秒
- **API 誤識別第三方 URL**：`_extract_json_candidates()` 用字串包含判斷 `BASE_URL in url`，第三方分析工具（Yahoo Analytics）因 query 參數含 `distiller.com` 而通過篩選，所有查詢回傳 0 筆；改為比對 `urlparse(url).netloc == "distiller.com"`

### 驗證
- full mode 正式執行：頁面載入失敗 0 次，4 筆新資料，exit code 0
- medium mode 頁面載入從 60 秒 timeout → ~7 秒正常載入
- **總計：297 個測試全數通過**

## [2.5.1] - 2026-03-09

### 修復
- **分頁 early-stop 邏輯修正**：`scrape_category_paginated` 將「分頁無效」（page 2 回傳與 page 1 相同的 URL）與「URL 已在 DB」（page 2 URL 不同但都在 `seen_urls`）分離判斷
  - 根因：DB 已有 2,796 筆資料時，page 1-2 全在 DB → 誤判分頁無效 → 無法發現 page 3+ 的新酒款
  - 新增 `consecutive_dup_pages` 計數器，連續 N 頁無新 URL 才停止（而非第 1 頁就停）
  - Page 1 無新 URL 時不再提前 break，繼續到 page 2 驗證分頁有效性

### 新增
- **`MAX_CONSECUTIVE_DUP_PAGES = 3`** 常數（`config.py`），控制連續無新 URL 頁面的容忍上限
- **4 個分頁測試**（`test_pagination.py`）：跨頁續爬、連續 dup 停止、計數器重置、已知 URL 跳過
- **總計：297 個測試全數通過**

### 變更
- 重寫 `scrape_category_paginated` 分頁迴圈（lines 335-412）
- 重新命名 `test_high_duplicate_ratio_stops_pagination` → `test_broken_pagination_with_known_urls_skips`

## [2.5.0] - 2026-03-08

### 修復
- **排程假警報修正**：`run.py` 成功判斷從 `len(spirits_data) > 0` 改為 `scrape_ok and (有資料 or 無錯誤)`，避免 DB 已滿時 clean dedup 被誤判為失敗（3/7 排程失敗根因）
- **Chrome/chromedriver 版本不匹配**：移除 `webdriver-manager`，改用 Selenium 內建 Selenium Manager 自動解析相容的 Chrome + chromedriver（3/8 全部 timeout 根因）

### 新增
- **`page_errors` 計數器**：`DistillerScraperV2` 新增頁面載入失敗計數，三處 catch point（分頁載入、滾動 fallback、category 級錯誤）累加
- `get_statistics()` 和完成日誌均納入 `page_errors` 輸出

### 變更
- 移除 `webdriver-manager` 依賴（`pyproject.toml` 和 `requirements.txt`）
- `start_driver()` 簡化為 `webdriver.Chrome(options=options)`，不再需要 `ChromeService` 和 `ChromeDriverManager`
- 三個 run function（`run_test`、`run_medium`、`run_full`）統一採用新成功判斷邏輯
- **總計：294 個測試全數通過**

## [2.4.2] - 2026-03-02

### 改善
- **LINE 訊息排版美化**：全面提升回覆訊息的視覺層次與閱讀體驗
  - `fmt_top`：Top 3 使用獎牌 emoji（🥇🥈🥉），粗線分隔標題
  - `fmt_search` / `fmt_list`：加入分數 bar 圖、分隔線，格式統一
  - `fmt_info`：粗線標題分隔、區塊空行、風味圖譜加入百分比標示
  - `fmt_stats`：區塊化佈局，類型與產地分節顯示
  - `fmt_flavors`：統一排行榜格式，Bar 圖加入百分比
  - `fmt_help`：指令分組（🔎 搜尋與瀏覽 / 📊 統計與風味 / ❓ 其他）
  - `notify_success` / `notify_failure`：加入時間戳、分隔線、類別分布 bar 圖
- 設計原則：純文字訊息、4900 字元限制意識、不改動任何邏輯或 API 行為

### 變更
- `pyproject.toml` 版本號從 `2.3.0` 更新至 `2.4.2`（補齊落後的版本同步）
- 測試同步更新：2 個格式相關斷言調整，**80 個測試全數通過**

## [2.4.1] - 2026-03-02

### 文件
- **README.md**：新增「排程與去重機制」章節，說明每日排程如何透過五層機制避免重複爬取
- **AGENTS.md**：記錄排程去重分析工作與文件更新

## [2.4.0] - 2026-03-02

### 修復
- **LINE Bot 7 個靜默失敗點全面修復**：Bot 完全不回覆問題根治
  - 簽名驗證失敗日誌加入來源 IP
  - JSON 解析失敗時記錄 WARNING
  - `_reply()` 改為回傳 `bool`（成功 True、失敗 False），記錄失敗詳情
  - DB 不存在時記錄 WARNING
- **`_reply()` 非 200 / 網路錯誤**：回傳 `False` 並記錄 `resp.text[:200]` 或例外訊息
- **爬蟲分頁容錯修復**：3 個連鎖崩潰 Bug 根治
  - Bug 3：DB 已有資料時 100% 重複率誤判「分頁無效」→ 快照 DB URL，全部重複時優雅跳過並 break
  - Bug 1：未保護的滾動 fallback → try/except 包裝，Selenium timeout 不再崩潰整支程式
  - Bug 2：單一類別失敗拖垮全部 → try/except 移至迴圈內部，實現 per-category 錯誤隔離

### 新增
- **OAuth Token 快取**（`_get_cached_token()`）：23 小時 TTL，60 秒安全邊際自動更新，避免每次回覆重新取得 Token
- **`GET /health` 端點**：回傳 `{"status": "ok", "db_exists": bool, "token_cached": bool}`
- **Webhook 驗證 Probe 支援**：LINE 空事件陣列驗證請求直接回 200，不做簽名檢查
- **啟動環境變數驗證**：`__main__` 缺少 `LINE_CHANNEL_SECRET` / `LINE_CHANNEL_ID` 時 `sys.exit(1)`
- **17 個新單元測試**（TestTokenCache、TestHealthCheck、TestWebhookVerificationProbe、TestReplyReturnValue、TestDbMissingLog）
- **`tests/unit/conftest.py`**：autouse fixture 隔離各測試的 token 快取狀態

### 變更
- `scripts/run_bot.sh`：從 `venv/bin/python` 遷移至 `uv run python bot.py`
- `com.distiller.bot.plist`：PATH 新增 `/Users/Henry/.local/bin`（uv 所在路徑）
- **總計：259 個單元測試全數通過**（原 242 個 + 17 個新增）
## [2.3.1] - 2026-03-01

### 修復
- **`run.py` LINE 通知誤報**：`notify_success()` / `notify_failure()` 回傳 `False` 時仍印出「已發送」的 bug，現改為正確檢查回傳值
- **`notify.py` 空字串憑證回退 bug**：`channel_id="" ` 時 `or` 運算子會錯誤回退至環境變數，改用 `is not None` 判斷，確保測試中傳入空字串有效
- **`test_notify.py` 5 個測試失敗**：上述 `notify.py` 修正後，所有 277 個測試全數通過

### 新增
- **LINE 通知自動重試**：通知失敗時等待 30 秒後自動重試一次，處理凌晨排程時暫時性 DNS 解析失敗的問題
- **`scripts/run_bot.sh`**：LINE Bot 啟動腳本（載入 `.env`、呼叫 `bot.py`）
- **`com.distiller.bot.plist`**：LINE Bot 的 macOS launchd 服務設定（`KeepAlive = true`，需手動安裝）

## [2.3.0] - 2026-02-28

### 新增
- **LINE Messaging API 通知** (`distiller_scraper/notify.py`)
  - `LineNotifier` 類別，透過 Channel ID + Secret 動態取得短期 Access Token
  - 與 music-collector 共用同一組 LINE Bot 憑證
  - `notify_success()` / `notify_failure()` 格式化爬取結果通知
  - 爬取完成或失敗時自動推播至 LINE
- **排程自動化** (`com.distiller.scraper.plist` + `scripts/run_scraper.sh`)
  - macOS launchd 排程，每日凌晨 3:00 自動執行完整爬取
  - Shell 腳本含日誌記錄、macOS 通知、自動載入 `.env`
- **新增 CLI 旗標**：`--notify-line`（爬取完成後發送 LINE 通知）
- **新增 22 個測試**（`tests/unit/test_notify.py`），總計 214 個
- 新增 `.env.example` 記錄所需環境變數

### 變更
- `run_*()` 函式回傳 `(bool, dict)` 以便傳遞統計資料至通知模組
- `.gitignore` 新增 `logs/` 目錄

## [2.2.0] - 2026-02-27

### 新增
- **SQLite 儲存後端** (`distiller_scraper/storage.py`)
  - `StorageBackend` 抽象基底類別，提供可插拔的儲存介面
  - `SQLiteStorage`：WAL 模式，包含 `spirits` + `flavor_profiles` + `scrape_runs` 三張表
  - `CSVStorage`：向下相容的 CSV 輸出封裝
  - 支援 Upsert（依 URL 去重）
- **分頁爬取** 以擴大資料量
  - `SearchURLBuilder.build_search_url()` 新增 `page` 參數
  - 新增爬蟲方法：`_get_search_queries()`、`_fetch_spirit_urls_from_page()`、`scrape_category_paginated()`
  - 智慧停止條件：頁面空白 / 新 URL 數不足 / 重複率過高
  - 在 `config.py` 新增分頁常數（`MAX_PAGES_PER_QUERY`、`DUPLICATE_RATIO_THRESHOLD` 等）
- **API 端點探索** (`distiller_scraper/api_client.py`)
  - `DistillerAPIClient`：雙重探索策略（Chrome XHR 擷取 + 候選路徑探測）
  - 三層備援架構：API（快速）→ Selenium（可靠），同時適用搜尋列表與詳情爬取
  - `discover_api()` 在爬取前自動探測端點
- **新增 CLI 旗標**：`--output csv|sqlite|both`、`--db-path`、`--no-pagination`、`--use-api`
- **新增 98 個測試**（總計：192 個）
  - `tests/unit/test_storage.py`（30 個測試）
  - `tests/unit/test_api_client.py`（42 個測試）
  - `tests/integration/test_pagination.py`（22 個測試）
  - `tests/unit/test_url_builder.py` 新增 4 個分頁測試

### 變更
- `DistillerScraperV2` 新增 `storage` 與 `api_client` 參數
- `scrape()` 與 `scrape_category()` 新增 `use_pagination` 參數
- Chrome 選項加入 Performance Logging 以擷取 XHR 請求
- 版本號升至 2.2.0

### 修復
- Python 3.12 sqlite3 的 `cursor.lastrowid` 在 `ON CONFLICT DO UPDATE` 後回傳錯誤值；改用明確的 SELECT → INSERT/UPDATE 流程

## [1.1.1] - 2026-01-28

### 修復
- macOS 上 Selenium 4.40+ 的 import timeout 問題
- 固定 selenium 版本為 `>=4.20.0,<4.30.0` 以確保匯入穩定
- 新增 `lxml` 至依賴以提升 BeautifulSoup 效能

### 變更
- 重建虛擬環境，使用相容的依賴版本
- 全部 98 個測試通過（81 個單元測試 + 17 個整合測試）

## [1.1.0] - 2026-01-28

### 新增
- 完整自動化測試框架（pytest）
  - `DataExtractor`、`SearchURLBuilder`、`ScraperConfig` 單元測試
  - 使用 Mock HTML 的整合測試（不需網路）
  - 端到端測試：實際連線爬取（標記為 `slow`/`network`）
- 測試 fixtures：用於一致性測試的 HTML 範例檔案
- `pytest.ini` 配置，含自訂標記
- GitHub Actions CI/CD workflow（`.github/workflows/test.yml`）
  - 在 push/PR 時執行單元測試與整合測試
  - 在 main 分支上可選執行 E2E 測試

### 變更
- 更新 `requirements.txt`，加入 pytest 相關依賴

### 新增檔案
- `tests/` 目錄與完整測試套件
- `tests/conftest.py` — pytest fixtures
- `tests/fixtures/` — HTML 範例檔案
- `tests/unit/test_selectors.py` — 30+ 個單元測試
- `tests/unit/test_url_builder.py` — URL 建構器測試
- `tests/unit/test_config.py` — 配置驗證測試
- `tests/integration/test_scraper_mock.py` — 基於 Mock 的整合測試
- `tests/e2e/test_scraper_live.py` — 實際連線測試
- `.github/workflows/test.yml` — CI/CD workflow

## [1.0.0] - 2026-01-28

### 新增
- 多代理協作文件（`AGENTS.md`）
- 本變更紀錄檔案

### 變更
- 重新整理專案結構，提升清晰度
- 重新命名 `run_scraper_v2.py` 為 `run.py` 作為統一入口
- 更新 `README.md`，反映新專案結構
- 更新 `.gitignore`，排除虛擬環境與資料檔案

### 移除
- `dev.py` — 原始 Edge 版本爬蟲（已整合至模組）
- `dev.ipynb` — 探索用 notebook（已整合至模組）
- `distiller_scraper_improved.py` — 已整合至模組
- `distiller_selenium_scraper.py` — 已整合至模組
- `run_final_scraper.py` — 已由 `run.py` 取代
- `run_phase1.py` — 測試腳本（不再需要）
- `run_selenium_phase1.py` — 測試腳本（不再需要）
- `TESTING_REPORT.md` — 已過時，內容整合至 README
- 測試用 CSV 檔案

## [0.2.0] - 2026-01-27

### 新增
- `distiller_scraper/` 模組與 V2 爬蟲
- 驗證 CSS 選擇器對應當前 Distiller.com 網頁結構
- 風味圖譜提取（JSON 格式）
- 支援多類別與多風格的烈酒爬取

### 變更
- 從 Edge 切換至 Chrome WebDriver，提升相容性
- 改善速率控制與錯誤處理

## [0.1.0] - 2026-01-18

### 新增
- 初版 Selenium 爬蟲實作
- 基本 CSV 匯出功能
- 測試報告
