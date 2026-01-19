# Distiller

Distiller 是一個用來爬取 Distiller.com 烈酒資料的專案，包含原始爬蟲、改進版 Selenium 爬蟲與測試報告。

## 專案結構

- `dev.py`: 原始 Selenium 爬蟲（Edge 版本，Windows 參考）
- `dev.ipynb`: requests 版本的探索性 Notebook
- `distiller_selenium_scraper.py`: Selenium 爬蟲框架（Chrome 相容）
- `run_final_scraper.py`: 中等規模爬蟲（headless Chrome）
- `distiller_scraper_improved.py`: requests 改進版（僅供參考）
- `distiller_spirits_reviews.csv`: 既有資料集
- `TESTING_REPORT.md`: 測試報告

## 安裝

```bash
pip install -r requirements.txt
pip install selenium webdriver-manager beautifulsoup4
```

## 執行爬蟲

```bash
python3 run_final_scraper.py
```

輸出：`distiller_spirits_reviews_NEW.csv`

## 測試說明

完整測試與分析請參考 `TESTING_REPORT.md`。

## 注意事項

- Distiller.com 使用 JavaScript 動態載入，requests 版本無法獲取完整資料。
- 若要擴大爬取範圍，需進一步研究分頁或 API。
