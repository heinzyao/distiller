# Distiller

從 [Distiller.com](https://distiller.com) 爬取烈酒評論資料的 Python 爬蟲專案。

## 功能特點

- ✅ 支援 Whiskey、Gin、Rum、Vodka 等多類別爬取
- ✅ 提取完整資料：評分、風味圖譜、品飲筆記等
- ✅ Headless Chrome 模式，穩定高效
- ✅ 智能延遲與速率控制

## 專案結構

```
Distiller/
├── distiller_scraper/      # 核心爬蟲模組
│   ├── scraper.py          # 主爬蟲類別
│   ├── selectors.py        # CSS 選擇器
│   └── config.py           # 爬蟲配置
├── run.py                  # 執行入口
├── requirements.txt
├── AGENTS.md               # 多代理協作紀錄
└── CHANGELOG.md            # 變更紀錄
```

## 安裝

```bash
# 建立虛擬環境
python3 -m venv venv
source venv/bin/activate

# 安裝依賴
pip install -r requirements.txt
```

## 執行

```bash
# 測試模式 (少量)
python run.py --test

# 中等規模
python run.py --medium

# 完整爬取
python run.py --full
```

## 資料欄位

| 欄位 | 說明 |
|------|------|
| `name` | 品名 |
| `spirit_type` | 類型 (Single Malt, Bourbon 等) |
| `brand`, `country` | 品牌與產地 |
| `age`, `abv` | 年份與酒精濃度 |
| `expert_score`, `community_score` | 專家/社群評分 |
| `flavor_data` | 風味圖譜 (JSON) |
| `description`, `tasting_notes` | 描述與品飲筆記 |

## 協作說明

本專案由多個 AI 代理協作開發，詳見 [AGENTS.md](AGENTS.md)。

## 注意事項

- Distiller.com 使用 JavaScript 動態載入，需使用 Selenium
- 請遵守網站使用條款，合理控制爬取頻率

## License

MIT
