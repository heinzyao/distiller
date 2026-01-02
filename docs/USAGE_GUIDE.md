# Distiller 使用指南

## 快速開始

### 1. 環境準備

```bash
# 克隆專案
git clone <repository-url>
cd distiller

# 建立虛擬環境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安裝依賴
pip install -r requirements.txt
```

### 2. 啟動 Jupyter Notebook

```bash
jupyter notebook
```

---

## 完整工作流程

### 步驟 1：數據爬取

#### 爬取產品數據

打開 `notebooks/crawlers/Distiller_crawler.ipynb`

**配置參數**：
```python
# 爬取設定
NUM_THREADS = 10          # 線程數
START_INDEX = 0           # 起始索引
END_INDEX = 8297          # 結束索引
OUTPUT_FORMAT = 'csv'     # 輸出格式：csv 或 json
```

**執行步驟**：
1. 運行「導入庫」單元格
2. 運行「生成 URL 列表」單元格
3. 運行「多線程爬取」單元格
4. 等待進度條完成
5. 檢查輸出文件：`data/raw/distiller_products_YYYYMMDD.csv`

**預期輸出**：
```
爬取進度: 100%|██████████| 8297/8297 [2:30:15<00:00, 1.09s/it]
成功爬取 8271 個產品
失敗 26 個（已記錄到 errors.log）
```

#### 爬取用戶評論

打開 `notebooks/crawlers/Distiller_user_crawler.ipynb`

**配置參數**：
```python
# 爬取設定
NUM_THREADS = 10
MAX_PAGES_PER_PRODUCT = 100  # 每個產品最多爬取頁數
COMMENTS_PER_PAGE = 10        # 每頁評論數
```

**執行**：運行所有單元格

**預期輸出**：
```
爬取進度: 100%|██████████| 71170/71170 [5:20:30<00:00, 3.7it/s]
成功爬取 711,708 條評論
```

---

### 步驟 2：數據庫操作（可選）

如果使用 MySQL 存儲數據：

#### 2.1 建立資料庫

```bash
mysql -u root -p
```

```sql
CREATE DATABASE Distiller CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE Distiller;

-- 創建產品表
CREATE TABLE products (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255),
    type VARCHAR(100),
    brand_name VARCHAR(255),
    origin VARCHAR(100),
    cost_level INT,
    age VARCHAR(50),
    abv DECIMAL(5,2),
    expert_rating DECIMAL(3,1),
    average_user_rating DECIMAL(3,1),
    user_comments INT,
    description TEXT,
    tasting_notes TEXT,
    reviewer VARCHAR(100),
    flavor_profile JSON
);

-- 創建評論表
CREATE TABLE reviews (
    id INT PRIMARY KEY AUTO_INCREMENT,
    product_name VARCHAR(255),
    user VARCHAR(100),
    user_rating DECIMAL(3,1),
    user_comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 2.2 導入數據

```python
import pandas as pd
import MySQLdb

# 讀取 CSV
df = pd.read_csv('data/raw/distiller_products_20200414.csv')

# 連接資料庫
conn = MySQLdb.connect(
    host='localhost',
    user='root',
    password='your_password',
    database='Distiller'
)

# 導入數據
df.to_sql('products', conn, if_exists='append', index=False)
```

#### 2.3 查詢數據

打開 `notebooks/preprocessing/SQL_query.ipynb`，運行查詢：

```python
# 查詢訓練數據（有風味檔案）
query_train = """
    SELECT * FROM products
    WHERE flavor_profile IS NOT NULL
    AND tasting_notes IS NOT NULL
"""

# 查詢測試數據（無風味檔案）
query_test = """
    SELECT * FROM products
    WHERE flavor_profile IS NULL
    AND tasting_notes IS NOT NULL
    AND expert_rating IS NOT NULL
"""
```

---

### 步驟 3：數據預處理

#### 3.1 處理訓練數據

打開 `notebooks/preprocessing/Train_data_processing.ipynb`

**主要處理步驟**：

1. **讀取原始數據**
```python
import pandas as pd
import json

# 讀取 JSON 或 CSV
with open('data/raw/distiller_products_20200414.json', 'r') as f:
    data = json.load(f)

df = pd.DataFrame(data)
print(f"原始數據：{len(df)} 條")
```

2. **數據篩選**
```python
# 保留同時有 tasting_notes 和 flavor_profile 的數據
df_train = df[
    (df['tasting_notes'].notna()) &
    (df['flavor_profile'].notna())
]
print(f"訓練數據：{len(df_train)} 條")
```

3. **類別整合**
```python
# 定義類別映射
CATEGORY_MAPPING = {
    'Whiskey': ['Bourbon', 'Scotch', 'Irish Whiskey', 'Rye', ...],
    'Brandy': ['Cognac', 'Armagnac', ...],
    # ... 其他類別
}

def map_category(type_str):
    for category, types in CATEGORY_MAPPING.items():
        if type_str in types:
            return category
    return 'Others'

df_train['category'] = df_train['type'].apply(map_category)
```

4. **風味編碼**
```python
# 定義 28 種風味
FLAVORS = [
    'briny', 'chemical', 'bitter', 'juniper', 'hogo', 'nutty',
    'umami', 'neutral', 'rancio', 'roast', 'mineral', 'grain',
    'harsh', 'earthy', 'woody', 'floral', 'fruity', 'full_bodied',
    'herbal', 'oily', 'peaty', 'rich', 'salty', 'smoky',
    'spicy', 'sweet', 'tart', 'vanilla'
]

def discretize(value):
    """將 0-100 的風味值轉換為 0-5 的等級"""
    if value == 0:
        return 0
    elif value <= 20:
        return 1
    elif value <= 40:
        return 2
    elif value <= 60:
        return 3
    elif value <= 80:
        return 4
    else:
        return 5

def encode_flavor_profile(flavor_dict):
    """將風味字典編碼為 Multi-Hot 向量（168 維）"""
    encoded = []
    for flavor in FLAVORS:
        value = flavor_dict.get(flavor, 0)
        level = discretize(value)
        # One-Hot 編碼：[0, 0, 0, 1, 0, 0] 表示等級 3
        one_hot = [1 if i == level else 0 for i in range(6)]
        encoded.extend(one_hot)
    return encoded

# 應用編碼
df_train['labels'] = df_train['flavor_profile'].apply(encode_flavor_profile)
```

5. **生成最終訓練數據**
```python
# 展開標籤列
label_columns = []
for flavor in FLAVORS:
    for level in range(6):
        label_columns.append(f"{flavor}_{level}")

# 創建標籤 DataFrame
labels_df = pd.DataFrame(
    df_train['labels'].tolist(),
    columns=label_columns
)

# 合併
train_final = pd.concat([
    df_train[['id', 'tasting_notes']].reset_index(drop=True),
    labels_df
], axis=1)

# 保存
train_final.to_csv('data/processed/train_data.csv', index=False)
print(f"訓練數據已保存：{train_final.shape}")
# 輸出：訓練數據已保存：(3513, 170)
```

#### 3.2 處理測試數據

打開 `notebooks/preprocessing/Test_data_processing.ipynb`

**步驟**：
1. 篩選有 tasting_notes 但無 flavor_profile 的數據
2. 應用相同的類別整合
3. 保存為 `data/processed/test_data.csv`

```python
df_test = df[
    (df['tasting_notes'].notna()) &
    (df['flavor_profile'].isna()) &
    (df['expert_rating'].notna())
]

df_test['category'] = df_test['type'].apply(map_category)

df_test[['id', 'name', 'category', 'tasting_notes']].to_csv(
    'data/processed/test_data.csv',
    index=False
)
```

#### 3.3 處理用戶評論（可選）

打開 `notebooks/preprocessing/User_reviews_processing.ipynb`

**步驟**：
1. 篩選有效評論（同時有評分和評論內容）
2. 評分轉換（1-5 星 → 0-100 分）
3. 數據探索分析

```python
df_reviews = pd.read_csv('data/raw/distiller_user_reviews_20200414.csv')

# 篩選有效評論
df_valid = df_reviews[
    (df_reviews['user_rating'].notna()) &
    (df_reviews['user_comment'].notna())
]

# 評分轉換
df_valid['rating_scaled'] = (df_valid['user_rating'] - 1) * 25
# 1星 → 0分, 2星 → 25分, 3星 → 50分, 4星 → 75分, 5星 → 100分
```

---

### 步驟 4：模型訓練

打開 `notebooks/modeling/Simple_transformers_Multilabel_Classification_Model.ipynb`

#### 4.1 環境準備

```python
# 安裝 simpletransformers（如果尚未安裝）
!pip install simpletransformers

# 導入庫
from simpletransformers.classification import MultiLabelClassificationModel
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
```

#### 4.2 讀取數據

```python
# 讀取訓練數據
df = pd.read_csv('data/processed/train_data.csv')

# 分離文本和標籤
texts = df['tasting_notes'].tolist()
labels = df.iloc[:, 2:].values  # 168 個標籤列

# 創建訓練 DataFrame
train_df = pd.DataFrame({
    'text': texts,
    'labels': list(labels)
})

# 劃分訓練集和驗證集
train_df, eval_df = train_test_split(train_df, test_size=0.2, random_state=42)

print(f"訓練集：{len(train_df)} 條")
print(f"驗證集：{len(eval_df)} 條")
# 輸出：
# 訓練集：2810 條
# 驗證集：703 條
```

#### 4.3 模型配置

```python
# 訓練參數
model_args = {
    'num_train_epochs': 2,
    'train_batch_size': 8,
    'eval_batch_size': 8,
    'learning_rate': 3e-5,
    'max_seq_length': 256,
    'overwrite_output_dir': True,
    'reprocess_input_data': True,
    'evaluate_during_training': True,
    'evaluate_during_training_steps': 100,
    'save_eval_checkpoints': False,
    'save_model_every_epoch': True,
    'use_multiprocessing': False,
    'use_multiprocessing_for_evaluation': False,
    'fp16': True,  # 混合精度訓練（需 GPU）
    'manual_seed': 42
}
```

#### 4.4 初始化模型

```python
# 選擇預訓練模型（三選一）
model = MultiLabelClassificationModel(
    'xlnet',                    # 模型類型
    'xlnet-base-cased',        # 預訓練模型名稱
    num_labels=168,            # 標籤數量
    args=model_args
)

# 其他可選模型：
# - 'bert', 'bert-base-uncased'
# - 'distilbert', 'distilbert-base-uncased'
# - 'roberta', 'distilroberta-base'
```

#### 4.5 訓練模型

```python
# 開始訓練
model.train_model(train_df, eval_df=eval_df)

# 訓練過程輸出示例：
# Epoch 1/2
# Training: 100%|██████████| 352/352 [15:30<00:00, 2.64s/it]
# Evaluating: 100%|██████████| 88/88 [01:20<00:00, 1.10it/s]
# Eval Loss: 0.0352, LRAP: 0.7854
# ...
```

#### 4.6 模型評估

```python
# 在驗證集上評估
result, model_outputs, wrong_predictions = model.eval_model(eval_df)

print("評估結果：")
print(f"F1 Score: {result['f1']:.4f}")
print(f"Precision: {result['precision']:.4f}")
print(f"Recall: {result['recall']:.4f}")
print(f"LRAP: {result['lrap']:.4f}")

# 預期輸出：
# 評估結果：
# F1 Score: 0.5420
# Precision: 0.5660
# Recall: 0.5450
# LRAP: 0.8260
```

#### 4.7 保存模型

```python
# 模型會自動保存到 outputs/ 目錄
# 手動保存到指定位置：
import shutil
shutil.copytree('outputs', 'data/models/xlnet_best')
```

---

### 步驟 5：預測新數據

#### 5.1 讀取測試數據

```python
# 讀取測試數據
test_df = pd.read_csv('data/processed/test_data.csv')
test_texts = test_df['tasting_notes'].tolist()

print(f"測試數據：{len(test_texts)} 條")
# 輸出：測試數據：1289 條
```

#### 5.2 批量預測

```python
# 執行預測
predictions, raw_outputs = model.predict(test_texts)

# predictions: (1289, 168) - 0/1 預測
# raw_outputs: (1289, 168) - 機率值

print(f"預測結果形狀：{predictions.shape}")
print(f"機率輸出形狀：{raw_outputs.shape}")
```

#### 5.3 保存預測結果

```python
# 創建標籤列名
label_columns = []
for flavor in FLAVORS:
    for level in range(6):
        label_columns.append(f"{flavor}_{level}")

# 創建預測 DataFrame
pred_df = pd.DataFrame(raw_outputs, columns=label_columns)
pred_df.insert(0, 'id', test_df['id'])

# 保存
pred_df.to_csv('data/processed/predictions.csv', index=False)
print("預測結果已保存到 data/processed/predictions.csv")
```

#### 5.4 解析預測結果

```python
def decode_predictions(pred_row):
    """將 Multi-Hot 預測解碼為風味字典"""
    flavor_dict = {}
    for i, flavor in enumerate(FLAVORS):
        # 提取該風味的 6 個機率值
        probs = pred_row[i*6:(i+1)*6]
        # 選擇機率最高的等級
        level = np.argmax(probs)
        # 轉換回 0-100 的值
        if level == 0:
            value = 0
        elif level == 1:
            value = 10
        elif level == 2:
            value = 30
        elif level == 3:
            value = 50
        elif level == 4:
            value = 70
        else:
            value = 90
        flavor_dict[flavor] = value
    return flavor_dict

# 示例：解析第一條預測
sample_pred = raw_outputs[0]
flavor_result = decode_predictions(sample_pred)
print("預測的風味檔案：")
for flavor, value in flavor_result.items():
    if value > 0:
        print(f"  {flavor}: {value}")

# 輸出示例：
# 預測的風味檔案：
#   fruity: 70
#   woody: 50
#   smoky: 30
#   sweet: 90
#   vanilla: 50
```

---

## 進階功能

### 單一文本預測

```python
# 自定義品鉴笔记
custom_note = """
Rich and complex with notes of dried fruit, honey, and oak.
The palate is smooth with hints of vanilla, caramel, and a subtle smoky finish.
"""

# 預測
predictions, raw_outputs = model.predict([custom_note])

# 解析結果
flavor_profile = decode_predictions(raw_outputs[0])
print("預測的風味：")
for flavor, value in sorted(flavor_profile.items(), key=lambda x: x[1], reverse=True):
    if value >= 50:  # 只顯示明顯的風味
        print(f"  {flavor}: {value}")
```

### 批量推理優化

```python
# 使用更大的批次大小加速預測
model.args.eval_batch_size = 32

# 批量預測（分批處理）
batch_size = 100
all_predictions = []

for i in range(0, len(test_texts), batch_size):
    batch = test_texts[i:i+batch_size]
    preds, _ = model.predict(batch)
    all_predictions.append(preds)

final_predictions = np.vstack(all_predictions)
```

### 模型比較

```python
# 比較不同預訓練模型的性能
models_to_compare = [
    ('xlnet', 'xlnet-base-cased'),
    ('distilbert', 'distilbert-base-uncased'),
    ('roberta', 'distilroberta-base')
]

results = {}
for model_type, model_name in models_to_compare:
    print(f"\n訓練 {model_name}...")

    model = MultiLabelClassificationModel(
        model_type, model_name,
        num_labels=168,
        args=model_args
    )

    model.train_model(train_df, eval_df=eval_df)
    result, _, _ = model.eval_model(eval_df)

    results[model_name] = result

# 比較結果
import pandas as pd
comparison_df = pd.DataFrame(results).T
print("\n模型性能比較：")
print(comparison_df[['f1', 'precision', 'recall', 'lrap']])
```

---

## 常見問題

### Q1: CUDA Out of Memory 錯誤

**問題**：訓練時出現 GPU 記憶體不足

**解決方案**：
```python
# 減小批次大小
model_args['train_batch_size'] = 4
model_args['eval_batch_size'] = 4

# 或減小最大序列長度
model_args['max_seq_length'] = 128

# 或啟用梯度累積
model_args['gradient_accumulation_steps'] = 2
```

### Q2: 訓練太慢

**解決方案**：
```python
# 使用較小的模型
model = MultiLabelClassificationModel(
    'distilbert',  # 比 BERT 小 40%
    'distilbert-base-uncased',
    num_labels=168
)

# 或減少訓練數據量（快速測試）
train_df_small = train_df.sample(n=500, random_state=42)
```

### Q3: 預測結果全是 0

**可能原因**：
- 模型未充分訓練
- 閾值設置不當

**解決方案**：
```python
# 使用機率輸出而非二元預測
_, raw_outputs = model.predict(test_texts)

# 調整閾值
threshold = 0.3
binary_predictions = (raw_outputs > threshold).astype(int)
```

---

## 下一步

完成基本流程後，可以嘗試：

1. **改進數據質量**
   - 清理噪聲數據
   - 數據增強（同義詞替換、回譯）

2. **優化模型**
   - 嘗試更大的模型（BERT-large, RoBERTa-large）
   - 調整超參數（學習率、批次大小、epochs）
   - 使用預訓練的領域特定模型

3. **特徵工程**
   - 加入額外特徵（價格、產地、年份、ABV）
   - 多模態學習（文本 + 數值特徵）

4. **部署應用**
   - 構建 FastAPI 服務
   - 創建 Web 界面
   - 容器化部署（Docker）

---

**文檔版本**：1.0
**最後更新**：2026-01-02
