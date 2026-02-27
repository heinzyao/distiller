# 變更紀錄

本檔案記錄專案的所有重要變更。

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
