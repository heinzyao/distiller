# 多代理協作紀錄 (Multi-Agent Collaboration Log)

本專案由多個 AI 代理協作開發與維護。本文件記錄工作歷史與協作指南。

---

## 📋 專案概述

**Distiller** 是一個從 [Distiller.com](https://distiller.com) 爬取烈酒評論資料的 Python 爬蟲專案。

| 項目 | 說明 |
|------|------|
| **語言** | Python 3.9+ |
| **核心模組** | `distiller_scraper/` |
| **爬蟲引擎** | Selenium (Chrome WebDriver, headless) |
| **資料處理** | BeautifulSoup4, Pandas |

---

## 🤖 代理協作歷史

### 2026-03-10 | Claude Code

**工作內容**：
1. **Chrome 145 renderer timeout 修復**
   - 根因：Distiller.com React 應用持續發送背景 XHR 請求，導致 `document.readyState` 永遠不觸發 `load` 事件 → Selenium 等待 60 秒後 timeout
   - 症狀：3/10 凌晨排程 28 次 "Timed out receiving message from renderer"，0 筆資料
   - **Fix 1**：`page_load_strategy = "none"` — 不等待 load 事件，改以固定延遲（`INITIAL_PAGE_DELAY`）等待 React 渲染完成
   - **Fix 2**：新增反偵測選項（`--disable-blink-features=AutomationControlled`、`excludeSwitches`、`useAutomationExtension=False`），避免被反爬蟲機制封鎖
   - **Fix 3**：User-Agent 更新為 `Chrome/145.0.0.0`，與實際版本一致

2. **詳情頁渲染等待不足修復**
   - 根因：`scrape_spirit_detail()` 使用 `time.sleep(2)`，`page_load_strategy='none'` 後不足以等待 React 水合
   - Fix：改為 `INITIAL_PAGE_DELAY = 5` 秒，與其他頁面一致

3. **API 誤識別第三方 URL 修復**
   - 根因：`_extract_json_candidates()` 用 `BASE_URL in url` 字串判斷，Yahoo Analytics 等第三方工具的 URL 因 query 參數含 `distiller.com` 而通過篩選 → 所有查詢回傳 0 筆 → Selenium fallback 被跳過
   - Fix：改為 `urlparse(url).netloc == "distiller.com"`，確保只採用正確網域

4. **正式執行驗證**
   - full mode：頁面載入失敗 0 次，4 筆新資料，exit code 0，耗時 21 分鐘
   - 297 個測試全數通過

**主要變更**：
- 修改 `distiller_scraper/scraper.py`（`page_load_strategy='none'`、反偵測選項、詳情頁延遲修正）
- 修改 `distiller_scraper/config.py`（User-Agent 更新為 Chrome/145）
- 修改 `distiller_scraper/api_client.py`（netloc 網域篩選）
- **總計：297 個測試全數通過**

**Commits**：`d97641d`、`7cb7ae1`、`2866ab6`

---

### 2026-03-09 | OpenCode Sisyphus

**工作內容**：
1. **分頁 early-stop 邏輯修正**
   - 根因：`scrape_category_paginated` 將「分頁無效」（page 2 回傳與 page 1 相同的 URL）與「URL 已在 DB 中」（page 2 URL 不同但都在 `seen_urls`）混為一談
   - DB 已有 2,796 筆資料時，page 1-2 URL 全在 DB → 誤判分頁無效 → 無法發現 page 3+ 的新酒款
   - **Fix**：重寫 `scrape_category_paginated` 分頁迴圈（lines 335-412）
     - 分離「分頁是否有效」（page 2 URL set ≠ page 1 URL set）與「是否有新 URL」兩個判斷
     - 新增 `consecutive_dup_pages` 計數器：連續 N 頁無新 URL 才停止（而非第 1 頁就停）
     - `config.py` 新增 `MAX_CONSECUTIVE_DUP_PAGES = 3` 常數
     - Page 1 無新 URL 時不再提前 break，繼續到 page 2 驗證分頁有效性

2. **測試更新**
   - 重新命名 `test_high_duplicate_ratio_stops_pagination` → `test_broken_pagination_with_known_urls_skips`（反映新邏輯路徑）
   - 新增 `test_continues_past_duplicate_pages`：驗證跨過已知頁面後能爬取新頁面
   - 新增 `test_stops_after_consecutive_dup_pages`：驗證連續 N 頁無新 URL 後停止
   - 新增 `test_resets_consecutive_dup_on_new_urls`：驗證中間出現新 URL 重置計數器
   - 所有 3 個新測試加入 `time.sleep` mock 避免延遲

**主要變更**：
- 修改 `distiller_scraper/config.py`（新增 `MAX_CONSECUTIVE_DUP_PAGES = 3`）
- 修改 `distiller_scraper/scraper.py`（重寫 `scrape_category_paginated` 分頁迴圈）
- 修改 `tests/integration/test_pagination.py`（更新 1 個測試 + 新增 3 個測試，共 21 個）
- **總計：297 個測試全數通過**

---

### 2026-03-08 | OpenCode Sisyphus

**工作內容**：
1. **排程失敗根因分析（3/7 & 3/8）**
   - 3/7：DB 已有全部資料，7 個類別全數 dedup → `spirits_data` 為空 → `run.py` 誤判為失敗（假警報）
   - 3/8：Chrome 自動更新至 `145.0.7632.160`，但 chromedriver 最新僅 `.117` → 版本不匹配 → 所有頁面 timeout

2. **Fix 1：修正 `run.py` 成功判斷邏輯**
   - 原邏輯 `len(spirits_data) > 0` 在 clean dedup 場景下誤判失敗
   - 新邏輯：`scrape_ok and (有資料 or 無錯誤)`，允許「0 筆新資料但無異常」= 成功
   - 新增 `has_errors` 檢查（`failed_urls` + `page_errors`）
   - 三個 run function（`run_test`、`run_medium`、`run_full`）統一修正

3. **Fix 2：新增 `page_errors` 頁面錯誤計數器**
   - `DistillerScraperV2.__init__` 新增 `self.page_errors: int = 0`
   - 三處 catch point 累加：分頁載入失敗、滾動 fallback 失敗、category 級錯誤
   - `get_statistics()` 與完成日誌均納入 `page_errors` 輸出

4. **Fix 3：移除 `webdriver-manager`，改用 Selenium Manager**
   - Selenium 4.6+ 內建 Selenium Manager 自動解析 Chrome + chromedriver 版本相容性
   - 移除 `ChromeDriverManager().install()` 與 `ChromeService`
   - `start_driver()` 簡化為 `webdriver.Chrome(options=options)`
   - 從 `pyproject.toml` 和 `requirements.txt` 移除 `webdriver-manager` 依賴

**主要變更**：
- 修改 `run.py`（成功判斷邏輯修正，3 處）
- 修改 `distiller_scraper/scraper.py`（`page_errors` 計數器 + Selenium Manager 遷移）
- 修改 `pyproject.toml`（移除 `webdriver-manager`）
- 修改 `requirements.txt`（移除 `webdriver-manager`）
- **總計：294 個測試全數通過**

---

### 2026-03-02 | OpenCode Atlas Orchestrator (Session 2)

**工作內容**：
1. **LINE Bot 全面容錯強化：7 個靜默失敗點修復 + 基礎設施遷移**
   - 根因分析：Bot 對每則訊息重新取得 OAuth Token（2秒逾時風險）、空事件陣列觸發 400、`_reply()` 回傳 None 無法知曉失敗
   - **Failure Point 1**：簽名驗證失敗日誌加入來源 IP
   - **Failure Point 2**：JSON 解析失敗記錄 WARNING
   - **Failure Point 4**：OAuth Token 改用快取（23小時 TTL，60秒安全邊際），避免每次請求重取
   - **Failure Point 5**：DB 不存在時記錄 WARNING
   - **Failure Point 6 & 7**：`_reply()` 改為回傳 `bool`（成功 True，失敗 False），記錄回應內容
   - **Webhook 驗證 Probe**：空事件陣列（LINE 驗證請求）直接回 200，不做簽名檢查
   - **Health Check**：新增 `GET /health` 端點，回傳 `{status, db_exists, token_cached}`
   - **啟動驗證**：`__main__` 新增環境變數檢查，缺少憑證時 `sys.exit(1)`
   - **基礎設施**：`run_bot.sh` 從 `venv/bin/python` 遷移至 `uv run`；`com.distiller.bot.plist` PATH 更新加入 `/Users/Henry/.local/bin`

2. **新增 17 個單元測試**
   - TestTokenCache（6 個）：首次取得、快取命中、過期重取、即將過期重取、失敗不填快取、成功後快取驗證
   - TestHealthCheck（5 個）：200 回應、必要欄位、DB 存在、token 未快取、token 已快取
   - TestWebhookVerificationProbe（2 個）：無簽名空事件回 200、格式錯誤 JSON 回 200
   - TestReplyReturnValue（3 個）：HTTP 200 回 True、非 200 回 False、網路錯誤回 False
   - TestDbMissingLog（1 個）：DB 不存在時記錄警告
   - 新增 `tests/unit/conftest.py`：autouse fixture 清除測試間 token 快取狀態

**主要變更**：
- 修改 `bot.py`（+180/-42 行，外科手術式強化）
- 修改 `scripts/run_bot.sh`（uv 遷移）
- 修改 `com.distiller.bot.plist`（PATH 更新）
- 修改 `tests/unit/test_bot.py`（+17 個測試）
- 新增 `tests/unit/conftest.py`（快取隔離 fixture）
- **總計：259 個單元測試全數通過**

**Commit**：`ab40caf`

---

### 2026-03-02 | OpenCode Sisyphus (Session 3)

**工作內容**：
1. **排程去重機制完整分析**
   - 追蹤每日排程（`run_scraper.sh` → `run.py --mode full --output both --use-api`）的完整執行路徑
   - 確認五層去重機制：`seen_urls` 預載、逐筆跳過、整類跳過、重複率閾值、SQLite upsert
   - 確認 CSV 輸出僅在單次執行內去重（每次獨立檔案），SQLite 為跨執行唯一去重來源
   - 結論：每日排程可有效避免重複爬取，已在 DB 中的類別會被快速跳過

2. **文件更新**
   - `README.md`：新增「排程與去重機制」章節，含五層去重機制對照表
   - `CHANGELOG.md`：新增 v2.4.1 文件更新紀錄
   - `AGENTS.md`：記錄本次分析工作
   - 提交 `.sisyphus/` 工作階段產出物（上一 session 遺留）

**主要變更**：
- 修改 `README.md`（新增排程去重章節）
- 修改 `CHANGELOG.md`（新增 v2.4.1）
- 修改 `AGENTS.md`（新增本次工作紀錄）

**Commit**：`chore(sisyphus)` + `docs`

---

### 2026-03-02 | OpenCode Atlas Orchestrator

**工作內容**：
1. **爬蟲容錯修復：3 個連鎖崩潰 Bug**
   - 根因分析：DB 已有資料 → 100% 重複率 → 誤判「分頁無效」→ 未受保護的滾動 fallback → Selenium timeout → 未捕捉例外 → 整個爬蟲崩潰
   - **Bug 3 修復**：在分頁迴圈前快照 DB URL (`db_urls`)，若所有 URL 已在 DB 中則優雅跳過並 break，不觸發滾動 fallback
   - **Bug 1 修復**：以 try/except 包裝滾動 fallback (`_fetch_spirit_urls_from_page` + `_scrape_urls`)，timeout 不再崩潰
   - **Bug 2 修復**：將 try/except 移至 for 迴圈內部，實現 per-category 錯誤隔離，單一類別失敗不影響後續類別

2. **全面驗證**
   - 單元測試 242/242 全數通過
   - Live medium run 確認：9 個子類別優雅跳過（顯示「此類別資料已存在於資料庫，跳過」），whiskey/gin 兩大類別均正常執行，無崩潰
   - Commit `e3d737d`：`fix(scraper): prevent crash on pagination fallback with existing DB data`

**主要變更**：
- 修改 `distiller_scraper/scraper.py`（+37/-24 行，3 個外科手術式修復）
- **總計：242 個單元測試全數通過**

**Commit**：`e3d737d`

---

### 2026-03-01 | Claude Code

**工作內容**：
1. **問題診斷：排程 LINE 通知失敗**
   - 確認 launchd 排程正常運作（`runs = 2`，exit code 0，Feb 28 & Mar 1 均有執行）
   - 診斷根因：凌晨 3:52 `api.line.me` DNS 解析失敗（暫時性網路問題），但 `run.py` 仍誤印「📱 LINE 通知已發送」
   - 修復 `run.py`：正確檢查 `notify_success()` / `notify_failure()` 回傳值
   - 新增 30 秒自動重試機制，處理凌晨暫時性 DNS 問題

2. **問題診斷：無法透過 LINE 查詢**
   - 確認 `bot.py` 已在 port 8000 運行、ngrok tunnel 已啟動
   - 確認 `load_dotenv()` 修復已生效（webhook 簽名驗證回應 HTTP 200）
   - 問題根因：ngrok 每次重啟 URL 不同，LINE Developers Console Webhook URL 需手動更新

3. **修復 `notify.py` 空字串憑證 bug**
   - `channel_id=""` 時 `or` 運算子回退至 `os.getenv()`，導致 5 個測試失敗
   - 改用 `channel_id if channel_id is not None else os.getenv(...)` 修正
   - 測試全數恢復通過（277/277）

4. **新增 LINE Bot 服務化設施**
   - `scripts/run_bot.sh`：載入 `.env` 並啟動 `bot.py`
   - `com.distiller.bot.plist`：launchd 服務設定（KeepAlive，供日後安裝用）

**主要變更**：
- 修改 `run.py`（通知回傳值檢查、30 秒重試、import time）
- 修改 `distiller_scraper/notify.py`（`is not None` 憑證判斷）
- 新增 `scripts/run_bot.sh`（Bot 啟動腳本）
- 新增 `com.distiller.bot.plist`（Bot launchd 設定）
- **總計：277 個測試全數通過**

---

### 2026-02-28 | Claude Code

**工作內容**：
1. **LINE Messaging API 通知**
   - 新增 `distiller_scraper/notify.py`，實作 `LineNotifier` 類別
   - 使用 Channel ID + Secret 動態取得短期 Access Token（與 music-collector 共用憑證）
   - `notify_success()` / `notify_failure()` 格式化爬取結果推播至 LINE
   - `run.py` 新增 `--notify-line` CLI 旗標
   - 新增 `tests/unit/test_notify.py`（22 個測試）

2. **排程自動化**
   - 新增 `com.distiller.scraper.plist`（macOS launchd，每日凌晨 3:00 執行）
   - 新增 `scripts/run_scraper.sh`（完整模式爬取，含日誌、macOS 通知、LINE 通知）
   - Shell 腳本自動載入 `.env` 環境變數

3. **文件翻譯與整理**
   - CHANGELOG.md 全文翻譯為繁體中文
   - README.md 全面改寫：新增完整 CLI 參數表、架構說明、儲存後端比較
   - 清理專案中過期的 CSV 測試輸出與日誌檔案

**主要變更**：
- 新增 `distiller_scraper/notify.py`（LINE 通知模組）
- 新增 `com.distiller.scraper.plist`（launchd 排程）
- 新增 `scripts/run_scraper.sh`（排程執行腳本）
- 新增 `.env.example`（環境變數範本）
- 修改 `run.py`（新增 `--notify-line`、`run_*()` 回傳 `(bool, dict)`）
- 修改 `distiller_scraper/__init__.py`（新增 `LineNotifier` 延遲導入）
- 修改 `scripts/run_scraper.sh`（載入 `.env`、加入 `--notify-line`）
- 新增 `tests/unit/test_notify.py`（22 測試）
- **總計：214 個測試全數通過**

**Commits**：`b2cf8cf`, `6c07deb`, `6514a2a`, `91faaf9`

---

### 2026-02-27 | Claude Code

**工作內容**：
1. **Phase 1 - 資料庫儲存支援**
   - 新增 `distiller_scraper/storage.py`，實作 `StorageBackend` ABC、`SQLiteStorage`、`CSVStorage`
   - SQLite schema：`spirits` 主表、`flavor_profiles` 正規化副表、`scrape_runs` 執行記錄表（WAL 模式）
   - 修復 Python 3.12 sqlite3 upsert 問題：`ON CONFLICT DO UPDATE` 導致 `cursor.lastrowid` 回傳錯誤值，改用明確的 SELECT → INSERT/UPDATE 流程
   - 整合 `storage` 參數至 `DistillerScraperV2`，支援 `--output csv|sqlite|both` 與 `--db-path` CLI 旗標
   - 新增 `tests/unit/test_storage.py`（30 個測試）

2. **Phase 2 - 分頁爬取**
   - 在 `config.py` 新增分頁常數：`PAGINATION_ENABLED`, `MAX_PAGES_PER_QUERY`, `MIN_NEW_URLS_PER_PAGE`, `DUPLICATE_RATIO_THRESHOLD`
   - 在 `SearchURLBuilder.build_search_url()` 加入 `page` 參數（page=1 省略，≥2 附加 `&page=N`）
   - 新增 scraper 方法：`_get_search_queries()`, `_fetch_spirit_urls_from_page()`, `_scrape_urls()`, `scrape_category_paginated()`
   - 三段式停止條件：頁面空白 / 新 URL 數過少 / 重複率過高
   - 新增 `--no-pagination` CLI 旗標（預設啟用分頁）
   - 新增 `tests/integration/test_pagination.py`（22 個測試）

3. **Phase 3 - API 端點探索**
   - 新增 `distiller_scraper/api_client.py`，實作 `DistillerAPIClient`
   - 雙重探索策略：Chrome Performance Log XHR 擷取 → 候選路徑探測（`/search.json`, `/api/v1/spirits/search` 等）
   - 三層備援架構：API（最快）→ Selenium（可靠）同時適用搜尋列表與詳情爬取
   - 新增 `scraper.discover_api()` 在爬取前自動探測；新增 `--use-api` CLI 旗標
   - 新增 `tests/unit/test_api_client.py`（42 個測試）

**主要變更**：
- 新增 `distiller_scraper/storage.py`（儲存抽象層）
- 新增 `distiller_scraper/api_client.py`（API 探索客戶端）
- 修改 `distiller_scraper/scraper.py`（分頁、API 整合、XHR 擷取）
- 修改 `distiller_scraper/config.py`（分頁常數）
- 修改 `distiller_scraper/selectors.py`（`build_search_url` page 參數）
- 修改 `distiller_scraper/__init__.py`（版本 2.2.0，新增延遲導入）
- 修改 `run.py`（新增 `--output`, `--db-path`, `--no-pagination`, `--use-api` 旗標）
- 新增 `tests/unit/test_storage.py`（30 測試）
- 新增 `tests/unit/test_api_client.py`（42 測試）
- 新增 `tests/integration/test_pagination.py`（22 測試）
- 修改 `tests/unit/test_url_builder.py`（加入 4 個分頁測試）
- **總計：192 個測試全數通過**（含先前 94 個）

**Commit**：`ae6a958`

---

### 2026-01-28 | OpenCode Agent

**工作內容**：
1. 實作完整自動化測試框架 (pytest)
2. 建立測試目錄結構與 fixtures
3. 撰寫單元測試 (30+ 測試案例)
   - `test_selectors.py`: DataExtractor 各方法測試
   - `test_url_builder.py`: SearchURLBuilder 測試
   - `test_config.py`: ScraperConfig 驗證測試
4. 撰寫整合測試 (Mock-based)
   - `test_scraper_mock.py`: 使用 Mock HTML 測試爬蟲流程
5. 撰寫端到端測試
   - `test_scraper_live.py`: 實際連線測試（標記為 slow/network）
6. 建立 GitHub Actions CI/CD workflow
7. 更新專案紀錄

**主要變更**：
- 新增 `tests/` 目錄（6 個測試模組）
- 新增 `pytest.ini` 配置
- 新增 `.github/workflows/test.yml` CI/CD
- 更新 `requirements.txt`（加入 pytest）
- 更新 `CHANGELOG.md`, `AGENTS.md`

**測試執行方式**：
```bash
# 執行單元測試與整合測試（預設，快速）
pytest

# 執行所有測試（包含 E2E，較慢）
pytest -m ""

# 只執行單元測試
pytest tests/unit

# 只執行整合測試
pytest tests/integration

# 執行 E2E 測試（需要網路）
pytest tests/e2e -m "slow or network"
```

---

### 2026-01-27 ~ 2026-01-28 | Antigravity Agent

**工作內容**：
1. 專案結構分析與理解
2. 專案檔案清理與整理
   - 移除冗餘開發腳本 (`dev.py`, `dev.ipynb` 等)
   - 整合執行入口為 `run.py`
3. 建立多代理協作文件 (`AGENTS.md`)
4. 更新專案說明文件
5. 推送至 GitHub

**主要變更**：
- 刪除 8 個冗餘檔案
- 重新命名 `run_scraper_v2.py` → `run.py`
- 新增 `AGENTS.md`, `CHANGELOG.md`
- 更新 `README.md`, `.gitignore`

---

## 🔧 協作者指南

### Antigravity Agent

**優勢**：
- 複雜任務規劃與執行
- 瀏覽器自動化測試
- 專案結構分析

**使用提示**：
- 可直接執行 shell 命令
- 支援多檔案編輯與重構
- 適合大規模專案整理

---

### OpenCode Agent

**優勢**：
- 快速程式碼編輯
- 終端機互動操作
- Git 版本控制

**接手指南**：
```bash
# 專案根目錄
cd /Users/Henry/Project/Distiller

# 啟用虛擬環境
source venv/bin/activate

# 安裝依賴
pip install -r requirements.txt

# 執行爬蟲（測試模式）
python run.py --mode test

# 執行爬蟲（完整模式）
python run.py --mode full
```

**核心檔案說明**：
| 檔案 | 說明 |
|------|------|
| `distiller_scraper/scraper.py` | 主爬蟲類別 `DistillerScraperV2`（含分頁、API 整合） |
| `distiller_scraper/selectors.py` | CSS 選擇器定義、`SearchURLBuilder` |
| `distiller_scraper/config.py` | 爬蟲配置（含分頁常數） |
| `distiller_scraper/storage.py` | 儲存後端（SQLiteStorage, CSVStorage） |
| `distiller_scraper/api_client.py` | API 端點探索客戶端 |
| `distiller_scraper/notify.py` | LINE 通知模組（LineNotifier） |
| `run.py` | 執行入口（支援 --output, --db-path, --no-pagination, --use-api, --notify-line） |
| `bot.py` | LINE Bot（Flask webhook，port 8000，簽名驗證 + 查詢回覆） |
| `query.py` | CLI 查詢工具（list / search / top / info / stats / flavors / export） |
| `scripts/run_scraper.sh` | 排程執行腳本（每日凌晨 3:00） |
| `scripts/run_bot.sh` | Bot 啟動腳本（供 launchd 使用） |

---

### Claude Code

**優勢**：
- 深度程式碼理解
- 複雜邏輯重構
- 文件撰寫

**接手指南**：

1. **理解專案結構**：
   ```
   Distiller/
   ├── distiller_scraper/     # 核心模組
   │   ├── scraper.py         # 主爬蟲 (DistillerScraperV2)
   │   ├── selectors.py       # CSS 選擇器 & SearchURLBuilder
   │   ├── config.py          # 爬蟲配置（含分頁常數）
   │   ├── storage.py         # 儲存後端 (SQLiteStorage, CSVStorage)
   │   ├── api_client.py      # API 端點探索客戶端
   │   └── notify.py          # LINE 通知模組 (LineNotifier)
   ├── scripts/
   │   ├── run_scraper.sh     # 排程執行腳本（爬蟲，每日凌晨 3:00）
   │   └── run_bot.sh         # Bot 啟動腳本（載入 .env 後執行 bot.py）
   ├── tests/
   │   ├── unit/              # 單元測試（無網路/瀏覽器）
   │   └── integration/       # 整合測試（Mock driver）
   ├── run.py                 # 執行入口
   ├── bot.py                 # LINE Bot（Flask webhook，port 8000）
   ├── query.py               # CLI 查詢工具（sqlite3 直查）
   ├── .env                   # 環境變數（LINE 憑證，不進版控）
   ├── com.distiller.scraper.plist  # launchd 排程設定（爬蟲）
   └── com.distiller.bot.plist      # launchd 服務設定（Bot，需手動安裝）
   ```

2. **關鍵類別**：
   - `DistillerScraperV2`: 主爬蟲，支援 headless Chrome、分頁、API 整合
   - `DistillerAPIClient`: 自動探索 API 端點，API-first 搜尋與詳情
   - `LineNotifier`: LINE 推播通知（Channel ID + Secret OAuth 流程）
   - `SQLiteStorage` / `CSVStorage`: 儲存後端（共同繼承 `StorageBackend` ABC）
   - `DataExtractor`: 資料提取輔助類別
   - `SearchURLBuilder`: URL 建構器（支援 `page` 參數）

3. **常用執行方式**：
   ```bash
   # 測試模式（5 筆，CSV 輸出）
   python run.py --mode test

   # 中等規模（~200 筆，SQLite 輸出，啟用 API 模式）
   python run.py --mode medium --output sqlite --use-api

   # 完整爬取（1000+ 筆，CSV+SQLite 雙輸出）
   python run.py --mode full --output both --db-path spirits.db

   # 停用分頁，使用舊式滾動爬取
   python run.py --mode test --no-pagination

   # 啟用 LINE 通知
   python run.py --mode full --notify-line
   ```

4. **擴展建議**：
   - 新增類別：修改 `config.py` 中的 `CATEGORIES`
   - 新增欄位：更新 `selectors.py` 中的選擇器
   - 調整速率：修改 `config.py` 中的延遲設定
   - 調整分頁行為：修改 `config.py` 中的 `MAX_PAGES_PER_QUERY` 等常數

---

## 📊 資料欄位說明

爬取的烈酒資料包含以下欄位：

| 欄位 | 說明 | 範例 |
|------|------|------|
| `name` | 品名 | Highland Park 18 Year |
| `spirit_type` | 類型 | Single Malt |
| `brand` | 品牌 | Highland Park |
| `country` | 產地 | Scotland |
| `age` | 年份 | 18 Year |
| `abv` | 酒精濃度 | 43.0 |
| `expert_score` | 專家評分 | 99 |
| `community_score` | 社群評分 | 4.47 |
| `flavor_data` | 風味圖譜 (JSON) | {"smoky": 40, ...} |

---

## 📝 待辦事項

- [x] 加入自動化測試 (pytest) ✅ 2026-01-28
- [x] 實作分頁爬取以擴大資料量 ✅ 2026-02-27
- [x] 探索 API 端點提高效率 ✅ 2026-02-27
- [x] 加入資料庫儲存支援 ✅ 2026-02-27
- [x] LINE 通知與排程自動化 ✅ 2026-02-28
- [x] LINE Bot（webhook 查詢）與 CLI 查詢工具 ✅ 2026-02-28
- [x] 通知可靠性修復（重試、回傳值檢查）✅ 2026-03-01
- [x] 爬蟲容錯修復（分頁 fallback 崩潰、per-category 錯誤隔離）✅ 2026-03-02
- [x] 排程失敗根因修復（false failure + Chrome 版本不匹配 + page_errors 計數）✅ 2026-03-08
- [x] 分頁 early-stop 邏輯修正（consecutive dup pages + 分離分頁有效性判斷）✅ 2026-03-09
- [x] Chrome 145 renderer timeout 修復（page_load_strategy='none' + 反偵測 + User-Agent）✅ 2026-03-10
- [x] 詳情頁渲染等待不足修復（2s → INITIAL_PAGE_DELAY）✅ 2026-03-10
- [x] API 誤識別第三方 URL 修復（netloc 網域篩選）✅ 2026-03-10

---

*最後更新：2026-03-11 by Claude Code*
