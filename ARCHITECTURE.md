# Distiller 專案架構說明

## 目錄
- [概述](#概述)
- [專案結構](#專案結構)
- [數據流程](#數據流程)
- [技術架構](#技術架構)
- [模組說明](#模組說明)
- [數據格式](#數據格式)
- [模型架構](#模型架構)

---

## 概述

本專案是一個端到端的機器學習管道（ML Pipeline），從數據爬取到模型部署的完整流程：

```
網站爬蟲 → 數據存儲 → 數據處理 → 特徵工程 → 模型訓練 → 預測輸出
```

**核心問題**：給定一段酒類品鉴笔记文本，預測其 28 種風味的強度等級（0-5 級）

**解決方案**：使用預訓練的 Transformer 模型進行多標籤文本分類

---

## 專案結構

```
distiller/
│
├── data/                           # 數據層
│   ├── raw/                       # 原始數據（爬取結果）
│   │   ├── distiller_products_YYYYMMDD.csv
│   │   ├── distiller_products_YYYYMMDD.json
│   │   └── distiller_user_reviews_YYYYMMDD.csv
│   │
│   ├── processed/                 # 處理後的數據
│   │   ├── train_data.csv        # 訓練數據（3,513 × 170）
│   │   ├── test_data.csv         # 測試數據（1,289 × 4）
│   │   └── predictions.csv        # 預測結果
│   │
│   └── models/                    # 模型檔案
│       ├── best_model/            # 最佳模型檢查點
│       ├── outputs/               # 訓練輸出
│       └── runs/                  # TensorBoard 日誌
│
├── notebooks/                      # 應用層
│   ├── crawlers/                  # 數據採集
│   │   ├── Distiller_crawler.ipynb
│   │   └── Distiller_user_crawler.ipynb
│   │
│   ├── preprocessing/             # 數據預處理
│   │   ├── SQL_query.ipynb
│   │   ├── Train_data_processing.ipynb
│   │   ├── Test_data_processing.ipynb
│   │   └── User_reviews_processing.ipynb
│   │
│   └── modeling/                  # 模型訓練
│       └── Simple_transformers_Multilabel_Classification_Model.ipynb
│
├── src/                           # 代碼層（未來擴展）
│   └── distiller/
│       ├── __init__.py
│       ├── crawler/               # 爬蟲模組
│       ├── preprocessing/         # 預處理模組
│       ├── models/                # 模型定義
│       └── utils/                 # 工具函數
│
├── configs/                       # 配置層
│   ├── crawler_config.yaml       # 爬蟲配置
│   ├── model_config.yaml         # 模型配置
│   └── data_config.yaml          # 數據配置
│
├── tests/                         # 測試層
│   ├── test_crawler.py
│   ├── test_preprocessing.py
│   └── test_model.py
│
└── docs/                          # 文檔層
    ├── API.md                    # API 文檔
    ├── DATA_SCHEMA.md            # 數據結構說明
    └── DEVELOPMENT.md            # 開發指南
```

---

## 數據流程

### 階段 1：數據採集（Data Acquisition）

```
┌─────────────────────────────────────────────────────────┐
│  Distiller.com 網站                                      │
└────────────────┬────────────────────────────────────────┘
                 │
                 ├─► Distiller_crawler.ipynb
                 │   ├─ 爬取 8,271 個產品
                 │   ├─ 多線程加速（10 threads）
                 │   └─ 輸出：distiller_products_*.csv/json
                 │
                 └─► Distiller_user_crawler.ipynb
                     ├─ 爬取 711,708 條評論
                     ├─ 自動分頁處理
                     └─ 輸出：distiller_user_reviews_*.csv
```

**關鍵技術**：
- `requests` + `BeautifulSoup` 解析 HTML
- `threading.Thread` 多線程並行
- `tqdm` 進度監控
- 錯誤處理與重試機制

### 階段 2：數據存儲（Data Storage）

```
┌────────────────┐
│  CSV/JSON      │ ──┐
└────────────────┘   │
                     ├──► MySQL 數據庫（可選）
┌────────────────┐   │    ├─ 產品表（products）
│  MySQL DB      │ ──┘    ├─ 評論表（reviews）
└────────────────┘        └─ 風味表（flavor_profiles）
```

**數據庫設計**（可選）：
- `products` 表：id, name, type, brand, origin, abv, rating, description, tasting_notes
- `reviews` 表：id, product_id, user, rating, comment, date
- `flavor_profiles` 表：id, product_id, flavor_name, flavor_value

### 階段 3：數據預處理（Data Preprocessing）

```
原始數據（8,271 條）
    │
    ├─► SQL_query.ipynb
    │   ├─ 查詢有 flavor_profile 的數據 → 3,451 條
    │   └─ 查詢有 tasting_notes 的數據 → 1,267 條
    │
    ├─► Train_data_processing.ipynb
    │   ├─ 數據清洗：移除缺失值
    │   ├─ 類別整合：75 類 → 7 大類
    │   ├─ 風味編碼：
    │   │   ├─ 原始值：0-100（連續值）
    │   │   ├─ 分級：0-5（6 個等級）
    │   │   └─ Multi-Hot：28 × 6 = 168 個二元特徵
    │   └─ 輸出：train_data.csv（3,513 × 170）
    │
    ├─► Test_data_processing.ipynb
    │   ├─ 相同的類別整合
    │   └─ 輸出：test_data.csv（1,289 × 4）
    │
    └─► User_reviews_processing.ipynb
        ├─ 評分轉換：1-5 星 → 0-100 分
        └─ 輸出：有效評論 151,387 條
```

**關鍵處理邏輯**：

#### 類別整合邏輯
```python
類別映射 = {
    'Whiskey': ['Bourbon', 'Scotch', 'Irish Whiskey', 'Japanese Whisky', ...],
    'Brandy': ['Cognac', 'Armagnac', 'Pisco', ...],
    'Rum': ['White Rum', 'Dark Rum', 'Spiced Rum', ...],
    'Gin': ['London Dry Gin', 'Plymouth Gin', ...],
    'Vodka': ['Vodka', 'Flavored Vodka', ...],
    'Tequila': ['Blanco', 'Reposado', 'Añejo', ...],
    'Liqueurs/Bitters': ['Amaretto', 'Triple Sec', ...]
}
```

#### 風味編碼邏輯
```python
# 原始風味值（0-100）
flavor_profile = {
    'fruity': 75,
    'smoky': 20,
    'sweet': 85
}

# 分級轉換（0-5）
def discretize(value):
    if value == 0: return 0
    elif value <= 20: return 1
    elif value <= 40: return 2
    elif value <= 60: return 3
    elif value <= 80: return 4
    else: return 5

# Multi-Hot 編碼
# fruity_0, fruity_1, ..., fruity_5 = [0, 0, 0, 0, 1, 0]
# smoky_0, smoky_1, ..., smoky_5 = [0, 1, 0, 0, 0, 0]
```

### 階段 4：模型訓練（Model Training）

```
train_data.csv（3,513 × 170）
    │
    ├─► 數據劃分
    │   ├─ 訓練集：80%（2,810 條）
    │   └─ 驗證集：20%（703 條）
    │
    ├─► Simple Transformers 框架
    │   ├─ 預訓練模型選擇：
    │   │   ├─ XLNet-base-cased
    │   │   ├─ DistilBERT-base-uncased
    │   │   └─ DistilRoBERTa-base
    │   │
    │   ├─ 訓練配置：
    │   │   ├─ batch_size: 8
    │   │   ├─ learning_rate: 3e-5
    │   │   ├─ num_epochs: 2
    │   │   ├─ max_seq_length: 256
    │   │   └─ num_labels: 168
    │   │
    │   └─ 訓練過程：
    │       ├─ Token 化輸入文本
    │       ├─ 前向傳播 → 損失計算
    │       ├─ 反向傳播 → 梯度更新
    │       └─ 驗證集評估
    │
    └─► 模型評估
        ├─ F1 Score: 0.542
        ├─ Precision: 0.566
        ├─ Recall: 0.545
        └─ LRAP: 0.826
```

### 階段 5：預測與輸出（Prediction & Output）

```
test_data.csv（1,289 × 4）
    │
    ├─► 加載訓練好的模型
    │
    ├─► 批量預測
    │   ├─ 輸入：tasting_notes 文本
    │   └─ 輸出：168 個標籤的機率值
    │
    └─► 後處理
        ├─ 機率值 → 0/1 預測（閾值 0.5）
        ├─ Multi-Hot → 風味等級解碼
        └─ 輸出：predictions.csv
```

---

## 技術架構

### 爬蟲架構

```python
┌──────────────────────────────────────────┐
│  Crawler Manager                          │
│  ├─ URL Queue（待爬取 URL 隊列）          │
│  ├─ Thread Pool（10 個工作線程）         │
│  ├─ Result Buffer（結果緩衝區）          │
│  └─ Error Handler（錯誤處理）            │
└──────────────────────────────────────────┘
           │
           ├─► Thread 1 ──► Request → Parse → Save
           ├─► Thread 2 ──► Request → Parse → Save
           ├─► ...
           └─► Thread 10 ─► Request → Parse → Save
```

**關鍵模組**：
- `URLGenerator`：生成爬取 URL
- `HTMLParser`：解析 HTML 提取數據
- `DataSaver`：保存為 CSV/JSON
- `RateLimiter`：請求速率限制

### 數據處理架構

```python
┌────────────────────────────────────────────────┐
│  Data Pipeline                                  │
│                                                 │
│  Raw Data                                       │
│     │                                           │
│     ├─► Cleaner（清洗）                         │
│     │   ├─ 移除缺失值                           │
│     │   ├─ 去重                                 │
│     │   └─ 格式標準化                           │
│     │                                           │
│     ├─► Transformer（轉換）                     │
│     │   ├─ 類別整合                             │
│     │   ├─ 風味編碼                             │
│     │   └─ 特徵工程                             │
│     │                                           │
│     └─► Validator（驗證）                       │
│         ├─ 數據類型檢查                         │
│         ├─ 範圍檢查                             │
│         └─ 完整性檢查                           │
│                                                 │
│  Processed Data                                 │
└────────────────────────────────────────────────┘
```

### 模型架構

```
┌─────────────────────────────────────────────────────┐
│  Multi-Label Classification Model                   │
│                                                      │
│  Input: "Rich fruity notes with smoky finish..."    │
│     │                                                │
│     ├─► Tokenizer（分詞器）                          │
│     │   └─ [CLS] rich fruity notes ... [SEP]        │
│     │                                                │
│     ├─► Transformer Encoder（編碼器）               │
│     │   ├─ Self-Attention Layers                    │
│     │   ├─ Feed-Forward Networks                    │
│     │   └─ Layer Normalization                      │
│     │                                                │
│     ├─► Pooling Layer（池化層）                     │
│     │   └─ 提取 [CLS] token 表示                    │
│     │                                                │
│     └─► Classification Head（分類頭）               │
│         ├─ Linear(768 → 168)                        │
│         └─ Sigmoid Activation                       │
│                                                      │
│  Output: [0.2, 0.8, 0.1, ..., 0.9]（168 個機率值）  │
└─────────────────────────────────────────────────────┘
```

**模型細節**：
- **輸入層**：最大序列長度 256 tokens
- **編碼器**：12 層 Transformer（XLNet/BERT 變體）
- **隱藏層維度**：768
- **注意力頭數**：12
- **輸出層**：168 個獨立的二元分類器
- **損失函數**：Binary Cross-Entropy Loss
- **優化器**：AdamW（weight decay = 0.01）

---

## 模組說明

### 1. Distiller_crawler.ipynb

**功能**：爬取 Distiller.com 產品數據

**核心函數**：
```python
def crawl_product(url):
    """爬取單個產品頁面"""
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    product = {
        'name': extract_name(soup),
        'type': extract_type(soup),
        'tasting_notes': extract_tasting_notes(soup),
        'flavor_profile': extract_flavor_profile(soup)
    }
    return product

def multi_thread_crawl(urls, num_threads=10):
    """多線程爬取"""
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        results = list(tqdm(executor.map(crawl_product, urls)))
    return results
```

**輸出格式**：
- CSV：每行一個產品，列為屬性
- JSON：產品列表，每個產品為字典

### 2. Train_data_processing.ipynb

**功能**：訓練數據預處理與特徵工程

**核心轉換**：
```python
# 風味編碼
def encode_flavor_profile(flavor_dict):
    """將風味字典編碼為 Multi-Hot 向量"""
    encoded = []
    for flavor in FLAVOR_LIST:
        value = flavor_dict.get(flavor, 0)
        level = discretize(value)  # 0-100 → 0-5
        one_hot = [1 if i == level else 0 for i in range(6)]
        encoded.extend(one_hot)
    return encoded  # 長度 168

# 類別整合
def map_category(original_type):
    """將 75 種酒類映射到 7 大類"""
    for category, types in CATEGORY_MAPPING.items():
        if original_type in types:
            return category
    return 'Others'
```

### 3. Simple_transformers_Multilabel_Classification_Model.ipynb

**功能**：模型訓練與預測

**核心代碼**：
```python
from simpletransformers.classification import MultiLabelClassificationModel

# 初始化模型
model = MultiLabelClassificationModel(
    'xlnet',
    'xlnet-base-cased',
    num_labels=168,
    args={
        'train_batch_size': 8,
        'eval_batch_size': 8,
        'num_train_epochs': 2,
        'learning_rate': 3e-5,
        'max_seq_length': 256
    }
)

# 訓練
model.train_model(train_df)

# 預測
predictions, raw_outputs = model.predict(test_texts)
```

---

## 數據格式

### train_data.csv（170 列）

| 列名 | 類型 | 說明 |
|------|------|------|
| id | int | 產品 ID |
| tasting_notes | str | 品鉴笔记文本（輸入特徵） |
| fruity_0 | int | fruity 風味等級 0（0/1） |
| fruity_1 | int | fruity 風味等級 1（0/1） |
| ... | ... | ... |
| vanilla_5 | int | vanilla 風味等級 5（0/1） |

**範例行**：
```csv
id,tasting_notes,fruity_0,fruity_1,...,vanilla_5
1234,"Rich and complex with notes of dried fruit...",0,0,0,0,1,0,...,1
```

### test_data.csv（4 列）

| 列名 | 類型 | 說明 |
|------|------|------|
| id | int | 產品 ID |
| name | str | 產品名稱 |
| category | str | 酒類類別（7 大類） |
| tasting_notes | str | 品鉴笔记文本 |

### predictions.csv（輸出）

| 列名 | 類型 | 說明 |
|------|------|------|
| id | int | 產品 ID |
| fruity_0 | float | fruity 等級 0 機率 |
| ... | ... | ... |
| vanilla_5 | float | vanilla 等級 5 機率 |

---

## 模型架構

### 損失函數

```python
# Binary Cross-Entropy Loss（每個標籤獨立計算）
def multi_label_loss(predictions, labels):
    """
    predictions: (batch_size, 168)，機率值 [0, 1]
    labels: (batch_size, 168)，真實標籤 {0, 1}
    """
    loss = -torch.mean(
        labels * torch.log(predictions + 1e-10) +
        (1 - labels) * torch.log(1 - predictions + 1e-10)
    )
    return loss
```

### 評估指標

**1. F1 Score（加權）**
```python
from sklearn.metrics import f1_score

f1 = f1_score(y_true, y_pred, average='weighted')
```

**2. Label Ranking Average Precision（LRAP）**
```python
from sklearn.metrics import label_ranking_average_precision_score

lrap = label_ranking_average_precision_score(y_true, y_pred_proba)
```

---

## 性能優化

### 爬蟲優化
- **多線程並行**：10 個線程同時爬取
- **請求池複用**：使用 `requests.Session()`
- **斷點續爬**：保存進度，支持中斷恢復

### 訓練優化
- **混合精度訓練**：使用 FP16 加速（需 GPU）
- **梯度累積**：小批次累積等效大批次
- **學習率調度**：Warmup + Linear Decay

### 預測優化
- **批量預測**：一次預測多個樣本
- **模型量化**：減小模型大小（INT8）
- **GPU 加速**：使用 CUDA 加速推理

---

## 擴展方向

### 1. 模組化重構
將 Notebook 轉換為可復用的 Python 模組：
```
src/distiller/
├── crawler/
│   ├── spider.py          # 爬蟲邏輯
│   └── parser.py          # HTML 解析
├── preprocessing/
│   ├── cleaner.py         # 數據清洗
│   └── encoder.py         # 特徵編碼
└── models/
    ├── trainer.py         # 訓練邏輯
    └── predictor.py       # 預測邏輯
```

### 2. API 服務
使用 FastAPI 提供預測服務：
```python
from fastapi import FastAPI

app = FastAPI()

@app.post("/predict")
def predict_flavor(tasting_notes: str):
    predictions = model.predict([tasting_notes])
    return {"flavor_profile": decode_predictions(predictions)}
```

### 3. 前端界面
使用 Streamlit/Gradio 構建交互界面：
```python
import streamlit as st

st.title("酒類風味預測系統")
notes = st.text_area("輸入品鉴笔记：")
if st.button("預測"):
    result = predict_flavor(notes)
    st.write(result)
```

---

**文檔版本**：1.0
**最後更新**：2026-01-02
