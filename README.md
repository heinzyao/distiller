# Distiller 酒類風味預測專案

## 專案簡介

這是一個端到端的機器學習專案，旨在從 [Distiller.com](https://distiller.com) 網站爬取酒類產品數據，並使用自然語言處理（NLP）技術，根據品鉴笔记（tasting notes）文本自動預測酒類的風味檔案（flavor profile）。

本專案涵蓋了完整的數據科學流程：
- 🕷️ **數據爬取**：從網站爬取 8,000+ 酒類產品和 700,000+ 用戶評論
- 🔧 **數據處理**：清洗、整合、特徵工程
- 🤖 **模型訓練**：使用 Transformer 模型進行多標籤分類
- 📊 **預測應用**：為未標註的酒類產品生成風味預測

## 專案結構

```
distiller/
├── data/                           # 數據目錄
│   ├── raw/                       # 原始爬取數據
│   ├── processed/                 # 處理後的訓練/測試數據
│   └── models/                    # 訓練好的模型檔案
│
├── notebooks/                      # Jupyter Notebooks
│   ├── crawlers/                  # 爬蟲腳本
│   │   ├── Distiller_crawler.ipynb              # 產品數據爬蟲
│   │   └── Distiller_user_crawler.ipynb         # 用戶評論爬蟲
│   │
│   ├── preprocessing/             # 數據預處理
│   │   ├── SQL_query.ipynb                      # 數據庫查詢
│   │   ├── Train_data_processing.ipynb          # 訓練數據處理
│   │   ├── Test_data_processing.ipynb           # 測試數據處理
│   │   └── User_reviews_processing.ipynb        # 用戶評論處理
│   │
│   └── modeling/                  # 模型訓練與預測
│       └── Simple_transformers_Multilabel_Classification_Model.ipynb
│
├── src/                           # 源代碼模組（未來擴展）
│   └── distiller/
│
├── configs/                       # 配置檔案
├── tests/                         # 測試檔案
├── docs/                          # 文檔
│
├── requirements.txt               # Python 依賴套件
├── setup.py                       # 安裝配置
├── .gitignore                     # Git 忽略檔案
└── README.md                      # 本說明文件
```

## 數據概覽

### 爬取數據統計
- **酒類產品**：8,271 個
- **用戶評論**：711,708 條（有效評論 151,387 條）
- **訓練數據**：3,513 個產品（有品鉴笔记和風味檔案）
- **測試數據**：1,289 個產品（僅有品鉴笔记）

### 酒類分類（7 大類）
| 類別 | 英文名稱 | 數量（訓練集） |
|------|----------|----------------|
| 威士忌 | Whiskey | 最多 |
| 白蘭地 | Brandy | - |
| 朗姆酒 | Rum | - |
| 琴酒 | Gin | - |
| 伏特加 | Vodka | - |
| 龍舌蘭 | Tequila | - |
| 利口酒/苦酒 | Liqueurs/Bitters | - |

### 風味標籤（28 種，每種 0-5 級）
```
briny, chemical, bitter, juniper, hogo, nutty, umami, neutral,
rancio, roast, mineral, grain, harsh, earthy, woody, floral,
fruity, full_bodied, herbal, oily, peaty, rich, salty, smoky,
spicy, sweet, tart, vanilla
```

**總標籤數**：28 種風味 × 6 個等級 = **168 個多標籤分類**

## 安裝與環境設定

### 1. 克隆專案
```bash
git clone <repository-url>
cd distiller
```

### 2. 建立虛擬環境
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

### 3. 安裝依賴
```bash
pip install -r requirements.txt
```

### 4. 設定資料庫（選用）
如果需要使用 MySQL 數據庫存儲數據：
```bash
# 創建資料庫
mysql -u root -p
CREATE DATABASE Distiller;
```

## 使用指南

### 工作流程

#### 步驟 1：數據爬取
```bash
# 啟動 Jupyter Notebook
jupyter notebook

# 執行爬蟲 notebooks
1. notebooks/crawlers/Distiller_crawler.ipynb          # 爬取產品數據
2. notebooks/crawlers/Distiller_user_crawler.ipynb     # 爬取用戶評論
```

**輸出**：
- `data/raw/distiller_products_*.csv` - 產品數據
- `data/raw/distiller_user_reviews_*.csv` - 用戶評論

#### 步驟 2：數據處理
```bash
# 執行預處理 notebooks
1. notebooks/preprocessing/SQL_query.ipynb              # 從資料庫提取數據
2. notebooks/preprocessing/Train_data_processing.ipynb  # 處理訓練數據
3. notebooks/preprocessing/Test_data_processing.ipynb   # 處理測試數據
4. notebooks/preprocessing/User_reviews_processing.ipynb # 處理用戶評論
```

**輸出**：
- `data/processed/train_data.csv` - 訓練數據（3,513 條，170 列）
- `data/processed/test_data.csv` - 測試數據（1,289 條，4 列）

#### 步驟 3：模型訓練與預測
```bash
# 執行模型 notebook
notebooks/modeling/Simple_transformers_Multilabel_Classification_Model.ipynb
```

**模型配置**：
- 預訓練模型：XLNet / DistilBERT / RoBERTa
- 批次大小：8
- 學習率：3e-5
- 訓練輪數：2 epochs
- 最大序列長度：256

**性能指標**：
- F1 Score: 0.542 (weighted)
- Precision: 0.566
- Recall: 0.545
- LRAP: 0.826

**輸出**：
- `data/models/` - 訓練好的模型檔案
- `data/processed/predictions.csv` - 測試數據預測結果

## 技術棧

### 爬蟲技術
- `requests` - HTTP 請求
- `BeautifulSoup` - HTML 解析
- `threading` - 多線程加速
- `tqdm` - 進度條

### 數據處理
- `pandas` - 數據處理
- `numpy` - 數值計算
- `MySQLdb` - MySQL 連接

### 機器學習
- `simpletransformers` - Transformer 模型封裝
- `transformers` - Hugging Face Transformers
- `torch` - PyTorch 深度學習框架
- `scikit-learn` - 機器學習工具

### 開發工具
- `jupyter` - 交互式開發環境
- `pandas-profiling` - 數據分析報告

## 主要功能

### 1. 數據爬取
- 支持多線程並行爬取（10 個線程）
- 自動處理分頁和錯誤重試
- 導出 CSV 和 JSON 格式

### 2. 數據預處理
- 75 種酒類整合為 7 大類
- 風味值標準化（0-100 轉換為 0-5 級）
- Multi-Hot Encoding（168 維特徵向量）

### 3. 模型訓練
- 支持多種預訓練模型切換
- 自動數據劃分（80% 訓練，20% 驗證）
- GPU 加速訓練

### 4. 預測與應用
- 批量預測未標註產品的風味檔案
- 支持自定義輸入文本預測

## 應用場景

1. **自動化風味標註**：為新產品或未標註產品生成風味檔案
2. **推薦系統**：基於風味相似度推薦酒類產品
3. **用戶偏好分析**：分析用戶評論與風味偏好的關聯
4. **產品開發**：輔助酒廠理解市場對不同風味的需求

## 未來改進

- [ ] 將 Notebook 代碼模組化為 Python 腳本
- [ ] 添加 API 服務供外部調用
- [ ] 改進模型架構（嘗試更大的模型）
- [ ] 加入更多特徵（價格、產地、年份等）
- [ ] 建立前端界面
- [ ] 添加單元測試

## 注意事項

### 爬蟲使用
- 請遵守網站的 `robots.txt` 規範
- 建議設置適當的請求間隔，避免過度請求
- 爬取的數據僅供學術研究使用

### 數據隱私
- 不要將爬取的原始數據提交到公開倉庫
- `data/` 目錄已在 `.gitignore` 中排除

### GPU 使用
- 模型訓練建議使用 GPU 加速
- 如無 GPU，可減小批次大小或使用 CPU 訓練（較慢）

## 授權

本專案僅供學術研究和學習使用。

## 貢獻

歡迎提交 Issue 和 Pull Request！

## 聯絡方式

如有問題或建議，請通過 Issue 聯繫。

---

**最後更新**：2026-01-02
