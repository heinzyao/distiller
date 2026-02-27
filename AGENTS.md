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
cd /Users/Henry/Desktop/Project/Distiller

# 啟用虛擬環境
source venv/bin/activate

# 安裝依賴
pip install -r requirements.txt

# 執行爬蟲 (測試模式)
python run.py --test

# 執行爬蟲 (完整模式)
python run.py
```

**核心檔案說明**：
| 檔案 | 說明 |
|------|------|
| `distiller_scraper/scraper.py` | 主爬蟲類別 `DistillerScraperV2`（含分頁、API 整合） |
| `distiller_scraper/selectors.py` | CSS 選擇器定義、`SearchURLBuilder` |
| `distiller_scraper/config.py` | 爬蟲配置（含分頁常數） |
| `distiller_scraper/storage.py` | 儲存後端（SQLiteStorage, CSVStorage） |
| `distiller_scraper/api_client.py` | API 端點探索客戶端 |
| `run.py` | 執行入口（支援 --output, --db-path, --no-pagination, --use-api） |

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
   │   └── api_client.py      # API 端點探索客戶端
   ├── tests/
   │   ├── unit/              # 單元測試（無網路/瀏覽器）
   │   └── integration/       # 整合測試（Mock driver）
   ├── run.py                 # 執行入口
   ├── requirements.txt
   └── data/                  # CSV 輸出
   ```

2. **關鍵類別**：
   - `DistillerScraperV2`: 主爬蟲，支援 headless Chrome、分頁、API 整合
   - `DistillerAPIClient`: 自動探索 API 端點，API-first 搜尋與詳情
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

---

*最後更新：2026-02-27 by Claude Code*
