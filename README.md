# Distiller

從 [Distiller.com](https://distiller.com) 爬取烈酒評論資料的 Python 爬蟲專案。

## 功能特點

- 支援 Whiskey、Gin、Rum、Vodka、Brandy、Tequila/Mezcal、Liqueurs 等多類別爬取
- 提取完整資料：評分、風味圖譜、品飲筆記等
- Headless Chrome 模式，穩定高效
- 智能分頁爬取，自動偵測停止條件
- API 端點自動探索，大幅提升爬取速度
- 多儲存後端：CSV / SQLite / 雙輸出
- 297 個自動化測試，GitHub Actions CI/CD

## 專案結構

```
distiller/
├── distiller_scraper/         # 核心爬蟲模組
│   ├── scraper.py             # 主爬蟲類別 DistillerScraperV2
│   ├── selectors.py           # CSS 選擇器 & SearchURLBuilder
│   ├── config.py              # 爬蟲配置（含分頁常數）
│   ├── storage.py             # 儲存後端 (SQLiteStorage, CSVStorage)
│   └── api_client.py          # API 端點探索客戶端
├── data/                      # CSV 輸出集中處（自動建立）
├── bot.py                     # LINE Bot（Flask webhook，port 8000）
├── query.py                   # CLI 查詢工具
├── scripts/
│   ├── run_scraper.sh         # 排程爬取腳本
│   └── run_bot.sh             # Bot 啟動腳本（launchd 用）
├── AGENTS.md                  # 多代理協作紀錄
└── CHANGELOG.md               # 變更紀錄
```

## 安裝

```bash
uv sync
```

## 執行

```bash
# 測試模式（5 筆，快速驗證）
python run.py --mode test

# 中等規模（~200 筆，4 個類別）
python run.py --mode medium

# 完整爬取（1000+ 筆，7 個類別）
python run.py --mode full
```

### 輸出格式

```bash
# CSV 輸出（預設），檔案儲存於 data/ 目錄
python run.py --mode test

# SQLite 輸出
python run.py --mode medium --output sqlite --db-path spirits.db

# CSV + SQLite 雙輸出，CSV 儲存於 data/
python run.py --mode full --output both
```

### 進階選項

```bash
# 啟用 API 模式（自動探測端點，速度更快）
python run.py --mode medium --use-api

# 停用分頁，改用傳統滾動爬取
python run.py --mode test --no-pagination

# 組合使用
python run.py --mode full --output both --db-path spirits.db --use-api
```

### 完整 CLI 參數

| 參數 | 說明 | 預設值 |
|------|------|--------|
| `--mode` | 爬取模式：`test` (5 筆) / `medium` (~200 筆) / `full` (1000+ 筆) | `test` |
| `--output` | 輸出格式：`csv` / `sqlite` / `both` | `csv` |
| `--db-path` | SQLite 資料庫路徑 | `distiller.db` |
| `--no-pagination` | 停用分頁模式，改用傳統滾動爬取 | 啟用分頁 |
| `--use-api` | 啟用 API 模式（自動探測端點） | 停用 |

## LINE Bot

`bot.py` 是一個 Flask Webhook 服務（port 8000），接收 LINE 訊息並查詢烈酒資料庫回覆。

```bash
# 啟動 Bot
uv run python bot.py

# 健康檢查
curl http://localhost:8000/health
```

支援指令：`top`、`搜尋`、`詳情`、`統計`、`風味`、`列表`、`說明`

## 測試

```bash
# 執行單元測試與整合測試（預設，快速）
uv run pytest

# 只執行單元測試
uv run pytest tests/unit

# 只執行整合測試
uv run pytest tests/integration

# 執行所有測試（包含 E2E，需要網路與 Chrome）
uv run pytest -m ""

# 查看覆蓋率
uv run pytest -v
```

## 資料欄位

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
| `flavor_data` | 風味圖譜 (JSON) | `{"smoky": 40, "sweet": 35}` |
| `description` | 描述 | Rich and complex. |
| `tasting_notes` | 品飲筆記 | Honey and smoke. |

## 架構說明

### 爬取流程

```
scrape() 啟動
  ├─ start_driver()         啟動 Headless Chrome
  ├─ discover_api()         [可選] 自動探測 API 端點
  └─ scrape_category()      每個類別
       ├─ 分頁模式 (預設)
       │    ├─ _get_search_queries()           產生搜尋 URL
       │    ├─ _fetch_spirit_urls()             API 或 Selenium 取得列表
       │    └─ scrape_spirit_detail()           API 或 Selenium 取得詳情
       └─ 滾動模式 (--no-pagination)
            ├─ scroll_and_collect()             無限滾動收集 URL
            └─ scrape_spirit_detail()           逐筆爬取詳情
```

### 三層備援機制

當啟用 `--use-api` 時，系統自動嘗試：

1. **API 模式**（最快）：直接呼叫 JSON API 端點
2. **Selenium 模式**（可靠）：透過瀏覽器自動化爬取

API 端點探索流程：
- 擷取 Chrome Performance Log 中的 XHR 請求
- 分析候選路徑（`/search.json`, `/api/v1/spirits/search` 等）
- 自動驗證端點是否回傳有效 JSON

### 儲存後端

| 後端 | 適用場景 |
|------|----------|
| `CSVStorage` | 快速匯出、資料分析 |
| `SQLiteStorage` | 去重（upsert）、關聯查詢、持久化儲存 |

SQLite schema 包含：
- `spirits` 主表（所有欄位 + 時間戳）
- `flavor_profiles` 副表（正規化風味資料）
- `scrape_runs` 執行記錄表

### 排程與去重機制

每日凌晨 3:00 由 launchd 排程執行完整爬取（`--mode full --output both --use-api`）。
系統透過五層去重機制確保不會重複爬取已有資料：

| 層級 | 機制 | 說明 |
|------|------|------|
| 1 | `seen_urls` 預載 | 啟動時從 SQLite 載入所有已存 URL 至記憶體 |
| 2 | 逐筆跳過 | 爬取詳情前檢查 `seen_urls`，已存在則跳過（不發 HTTP 請求）|
| 3 | 整類跳過 | 若某頁所有 URL 皆已在 DB 中，整個類別直接跳過 |
| 4 | 重複率閾值 | 第 2 頁起重複率 ≥ 80% 時自動停止分頁 |
| 5 | SQLite upsert | URL 為 `UNIQUE` 欄位，重複寫入時更新而非新增 |

> **注意**：CSV 輸出為每次執行獨立檔案，儲存於 `data/` 目錄，僅在單次執行內去重。SQLite 為跨執行的唯一去重來源。

## 協作說明

本專案由多個 AI 代理協作開發，詳見 [AGENTS.md](AGENTS.md)。

## 注意事項

- Distiller.com 使用 JavaScript 動態載入，需使用 Selenium
- 請遵守網站使用條款，合理控制爬取頻率
- 需要 Chrome 瀏覽器（webdriver-manager 會自動管理 ChromeDriver）

## 授權條款

MIT
