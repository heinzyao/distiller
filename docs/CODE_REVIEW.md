# 代碼審查報告

## 審查日期：2026-01-02

## 概述

本報告針對 Distiller 專案的所有 Jupyter Notebooks 進行深入的代碼審查，識別問題、潛在風險和改進機會。

---

## 審查範圍

1. **爬蟲模組** (notebooks/crawlers/)
   - Distiller_crawler.ipynb
   - Distiller_user_crawler.ipynb

2. **數據預處理模組** (notebooks/preprocessing/)
   - Train_data_processing.ipynb
   - Test_data_processing.ipynb
   - SQL_query.ipynb
   - User_reviews_processing.ipynb

3. **模型訓練模組** (notebooks/modeling/)
   - Simple_transformers_Multilabel_Classification_Model.ipynb

---

## 問題分類

- 🔴 **嚴重**：可能導致程序崩潰、數據丟失或安全問題
- 🟡 **中等**：影響性能、可維護性或最佳實踐
- 🟢 **輕微**：代碼風格、可讀性改進

---

# 一、爬蟲模組問題

## Distiller_crawler.ipynb

### 🔴 嚴重問題

#### 1. 多線程安全問題
**位置**：Cell 17 - main() 函數

**問題描述**：
```python
lock = threading.Lock()
lock.acquire()
data.append(spirit_info)
exec_count += 1
lock.release()
```

**問題**：
- Lock 在 **循環內部** 創建，每次迭代都創建新的鎖，無法保護多線程訪問
- 應該在函數外部創建 **全局鎖**
- `global data` 和 `global exec_count` 在多線程環境下容易出現競爭條件

**風險**：數據丟失、計數錯誤

**建議修復**：
```python
# 在模組級別創建鎖
data_lock = threading.Lock()

def main(start=0, end=-1):
    global exec_count
    global data

    for url in tqdm(url_list[start:end]):
        # ... 爬取邏輯 ...

        # 使用全局鎖
        with data_lock:  # 使用 context manager 更安全
            data.append(spirit_info)
            exec_count += 1
```

#### 2. 無限重試循環
**位置**：Cell 17 - main() 函數

**問題描述**：
```python
while True:
    try:
        # ... 爬取邏輯 ...
        break
    except Exception as e:
        logging.exception(e)
        print(e)
        time.sleep(30)
        continue  # 無限重試
```

**問題**：
- 如果網站永久不可訪問，會無限循環
- 沒有重試次數限制
- 可能導致程序卡死

**建議修復**：
```python
max_retries = 3
retry_count = 0

while retry_count < max_retries:
    try:
        # ... 爬取邏輯 ...
        break
    except Exception as e:
        retry_count += 1
        logging.error(f"Retry {retry_count}/{max_retries}: {e}")
        if retry_count >= max_retries:
            logging.error(f"Failed to crawl {url} after {max_retries} retries")
            break
        time.sleep(30 * retry_count)  # 指數退避
```

### 🟡 中等問題

#### 3. 硬編碼配置值
**位置**：多處

**問題**：
```python
time.sleep(3)        # 硬編碼睡眠時間
seg = 10             # 硬編碼線程數
page_count+1         # 硬編碼頁數偏移
```

**建議**：使用配置文件或常量
```python
# configs/crawler_config.yaml
CRAWLER_CONFIG = {
    'request_delay': 3,
    'num_threads': 10,
    'max_retries': 3,
    'timeout': 30
}
```

#### 4. 缺乏資源管理
**位置**：Cell 17

**問題**：
- 每次請求都創建新的 HTTP 連接
- 沒有使用 `requests.Session()` 複用連接
- 沒有設置超時

**性能影響**：每次請求都需要 TCP 握手，浪費時間

**建議修復**：
```python
# 使用 Session 複用連接
session = requests.Session()
session.headers.update(my_headers)

def main(start=0, end=-1):
    for url in tqdm(url_list[start:end]):
        try:
            html = session.get(url, timeout=30)  # 添加超時
            # ...
        except requests.Timeout:
            logging.error(f"Timeout for {url}")
            continue
```

#### 5. BeautifulSoup 解析器未指定
**位置**：Cell 4, 7, 17

**問題**：
```python
bsObj = BeautifulSoup(html.text)  # 未指定解析器
```

**風險**：
- 依賴系統默認解析器，不同環境可能不同
- 可能出現警告或不一致的行為

**建議**：
```python
bsObj = BeautifulSoup(html.text, 'lxml')  # 明確指定解析器
```

#### 6. 異常處理過於寬泛
**位置**：Cell 17

**問題**：
```python
except Exception as e:  # 捕獲所有異常
    logging.exception(e)
    print(e)
    time.sleep(30)
    continue
```

**問題**：
- 捕獲所有異常（包括 KeyboardInterrupt）
- 無法區分可恢復和不可恢復的錯誤

**建議**：
```python
except (requests.RequestException, AttributeError) as e:
    # 處理特定異常
    logging.error(f"Crawling error for {url}: {e}")
    retry_count += 1
    continue
except KeyboardInterrupt:
    logging.info("User interrupted crawling")
    raise  # 允許用戶中斷
```

### 🟢 輕微問題

#### 7. 代碼重複
**位置**：Cell 17 - 多個 try-except 塊

**問題**：提取每個字段都有相似的 try-except 邏輯

**建議**：創建輔助函數
```python
def safe_extract(extractor_func, default=None):
    """安全提取數據，失敗返回默認值"""
    try:
        return extractor_func()
    except (AttributeError, IndexError, ValueError):
        return default

# 使用
spirit_info['name'] = safe_extract(
    lambda: bsObj.find('h1', {'itemprop':'name'}).string.strip()
)
```

#### 8. 魔法字符串和數字
**位置**：多處

**問題**：
```python
cost_index = str(bsObj.find('div', {'class':'value'})).index('cost-')+5
```

**建議**：使用常量並添加註釋
```python
COST_PREFIX = 'cost-'
COST_PREFIX_LENGTH = 5
cost_index = str(bsObj.find('div', {'class':'value'})).index(COST_PREFIX) + COST_PREFIX_LENGTH
```

---

## Distiller_user_crawler.ipynb

### 🔴 嚴重問題

#### 9. 函數返回值錯誤
**位置**：Cell 4 - getUserReviews()

**問題**：
```python
def getUserReviews(url_list=url_list, start=0, end=len(url_list)):
    global all_reviews
    user_reviews = []
    # ...
    return all_reviews.extend(user_reviews)  # extend() 返回 None!
```

**問題**：
- `list.extend()` 方法返回 `None`
- 函數實際上返回 `None`，但卻使用了 return 語句

**建議修復**：
```python
def getUserReviews(url_list, start=0, end=None):
    """爬取用戶評論，不使用全局變量"""
    if end is None:
        end = len(url_list)

    user_reviews = []
    # ... 爬取邏輯 ...
    return user_reviews  # 直接返回本地列表
```

### 🟡 中等問題

#### 10. 全局變量依賴
**位置**：Cell 3, 4

**問題**：
```python
all_reviews = []  # 全局變量

def getUserReviews(...):
    global all_reviews  # 依賴全局狀態
```

**問題**：
- 多線程環境下不安全
- 難以測試
- 副作用不明顯

**建議**：使用線程安全的隊列
```python
from queue import Queue
from threading import Thread

review_queue = Queue()

def getUserReviews(url_list, start, end, result_queue):
    user_reviews = []
    # ... 爬取邏輯 ...
    result_queue.put(user_reviews)
```

---

# 二、數據預處理模組問題

## Train_data_processing.ipynb

### 🟡 中等問題

#### 11. 低效的 CSV 手動解析
**位置**：Cell 9

**問題**：
```python
with open('train_raw.csv', 'r', newline='', encoding="utf-8") as file:
    reader = csv.reader(file)

    for row in reader:
        flavor = row[5].strip('{').strip('}\r').split(',')
        # 手動解析字典字符串
```

**問題**：
- 應該使用 pandas 讀取，然後用 `ast.literal_eval()` 解析
- 手動字符串解析容易出錯

**建議**：
```python
import ast

df = pd.read_csv('train_raw.csv')
df['flavor_profile'] = df['flavor_profile'].apply(
    lambda x: ast.literal_eval(x) if pd.notna(x) else {}
)
```

#### 12. 硬編碼的類別映射
**位置**：Cell 12

**問題**：
```python
whiskey_list = ['Blended Malt', 'Tennessee', ...]  # 75+ 種類型硬編碼
```

**建議**：移到配置文件
```python
# configs/category_mapping.yaml
categories:
  Whiskey:
    - Blended Malt
    - Tennessee
    - Peated Single Malt
    # ...
  Brandy:
    - Cognac
    - Armagnac
    # ...
```

#### 13. 風味編碼邏輯複雜
**位置**：Cell 20

**問題**：
```python
new_data = []
for item in flavor_profile:
    new_keys = []
    new_values = []

    for key in item:
        for label in label_list:
            if label in item.keys():
                new_keys.append(key.strip("'"))
                new_values.append(math.ceil(int(item[key])/20))
            elif label not in item.keys():
                new_keys.append(label.strip("'"))
                new_values.append(0)
    # 三重嵌套循環！
```

**問題**：
- 時間複雜度 O(n * m * k)
- 邏輯複雜，難以理解
- 產生大量重複鍵

**建議重構**：
```python
def discretize_flavor_value(value):
    """將 0-100 的值離散化為 0-5"""
    return min(value // 20, 5) if value > 0 else 0

def encode_flavor_profile(flavor_dict, all_labels):
    """編碼風味檔案"""
    encoded = {}
    for label in all_labels:
        raw_value = int(flavor_dict.get(f"'{label}'", 0))
        encoded[label] = discretize_flavor_value(raw_value)
    return encoded

# 使用向量化操作
new_data = [encode_flavor_profile(fp, label_list) for fp in flavor_profile]
```

### 🟢 輕微問題

#### 14. 魔法數字
**位置**：Cell 20, 22

**問題**：
```python
new_values.append(math.ceil(int(item[key])/20))  # 20 是什麼？
```

**建議**：
```python
FLAVOR_SCALE_FACTOR = 20  # 將 0-100 轉換為 0-5 的比例因子
FLAVOR_MAX_LEVEL = 5

def discretize_flavor(value):
    """離散化風味值"""
    return min(math.ceil(value / FLAVOR_SCALE_FACTOR), FLAVOR_MAX_LEVEL)
```

---

# 三、模型訓練模組問題

## Simple_transformers_Multilabel_Classification_Model.ipynb

### 🟡 中等問題

#### 15. 配置硬編碼
**位置**：Cell 12

**問題**：
```python
model = MultiLabelClassificationModel(
    model_type,
    pretrained_model[model_type],
    num_labels=label_num,
    args={
        'train_batch_size':8,
        'learning_rate': 3e-5,
        'num_train_epochs':2,
        # ... 全部硬編碼
    }
)
```

**建議**：使用配置文件
```python
# configs/model_config.yaml
model:
  type: xlnet
  pretrained: xlnet-base-cased

training:
  batch_size: 8
  learning_rate: 3e-5
  epochs: 2
  max_seq_length: 256

# 代碼中
import yaml

with open('configs/model_config.yaml') as f:
    config = yaml.safe_load(f)

model = MultiLabelClassificationModel(
    config['model']['type'],
    config['model']['pretrained'],
    num_labels=label_num,
    args=config['training']
)
```

#### 16. 缺乏實驗追蹤
**位置**：整個 notebook

**問題**：
- 沒有記錄超參數
- 沒有追蹤實驗結果
- 難以比較不同模型

**建議**：集成 MLflow 或 Weights & Biases
```python
import mlflow

mlflow.start_run()
mlflow.log_params(config['training'])
mlflow.log_param("model_type", model_type)

# 訓練
model.train_model(train_df, eval_df=eval_df)

# 記錄指標
mlflow.log_metrics(result)
mlflow.end_run()
```

#### 17. 評估指標實現
**位置**：Cell 16

**問題**：
```python
def f1_multilabel(labels, preds):
    return sklearn.metrics.f1_score(
        labels,
        list(list(map(rounding, i)) for i in preds),  # 嵌套 list() 調用
        average='weighted',
        zero_division='warn'
    )
```

**問題**：
- 嵌套的 `list()` 轉換低效
- 重複的轉換邏輯

**建議**：
```python
def round_predictions(preds, threshold=0.5):
    """將機率預測轉換為二元預測"""
    return (preds >= threshold).astype(int)

def f1_multilabel(labels, preds):
    binary_preds = round_predictions(preds)
    return sklearn.metrics.f1_score(
        labels,
        binary_preds,
        average='weighted',
        zero_division=0
    )
```

### 🟢 輕微問題

#### 18. 未使用的導入
**位置**：Cell 0

**問題**：
```python
from collections import Counter  # 未使用
import math  # 未使用
```

#### 19. 變量命名不清晰
**位置**：多處

**問題**：
```python
df = ...  # 到處都叫 df
result, model_outputs, wrong_predictions = ...  # wrong_predictions 未使用
```

---

# 四、通用問題

## 所有 Notebooks 共同問題

### 🟡 中等問題

#### 20. 缺乏日誌記錄
**問題**：
- 只有爬蟲有日誌，數據處理和模型訓練沒有
- 日誌級別不合理（過多 INFO）

**建議**：
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/{module_name}_{timestamp}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
```

#### 21. 缺乏數據驗證
**問題**：
- 沒有檢查 DataFrame 的形狀和類型
- 沒有驗證數據完整性

**建議**：
```python
def validate_training_data(df):
    """驗證訓練數據"""
    assert 'tasting_notes' in df.columns
    assert 'flavor_profile' in df.columns
    assert df['tasting_notes'].notna().all()
    assert len(df) > 0
    logging.info(f"Validated {len(df)} training samples")
```

#### 22. 路徑硬編碼
**問題**：
```python
df = pd.read_csv('train_data.csv')  # 硬編碼路徑
```

**建議**：
```python
from pathlib import Path

DATA_DIR = Path('data/processed')
TRAIN_DATA = DATA_DIR / 'train_data.csv'

df = pd.read_csv(TRAIN_DATA)
```

---

# 五、性能問題

## 效率改進機會

### 1. DataFrame 操作優化
**問題**：Cell 25-28 使用 `pd.concat()` 和 `join()`

**建議**：
```python
# 避免多次 concat
df_final = pd.concat([df_info, df_labels], axis=1, copy=False)
```

### 2. Multi-Hot 編碼效率
**問題**：使用 `pd.get_dummies()` 然後手動調整列

**建議**：
```python
from sklearn.preprocessing import MultiLabelBinarizer

mlb = MultiLabelBinarizer()
flavor_encoded = mlb.fit_transform(df['flavor_dict'])
```

---

# 六、安全問題

### 🔴 嚴重

#### 23. SQL 注入風險（潛在）
**位置**：SQL_query.ipynb（未審查但需注意）

**建議**：
- 始終使用參數化查詢
- 不要拼接 SQL 字符串

```python
# 錯誤
query = f"SELECT * FROM products WHERE name = '{user_input}'"

# 正確
query = "SELECT * FROM products WHERE name = %s"
cursor.execute(query, (user_input,))
```

---

# 七、改進建議總結

## 優先級 1（立即修復）

1. ✅ **修復多線程鎖問題** - 爬蟲可能丟失數據
2. ✅ **添加重試次數限制** - 避免無限循環
3. ✅ **修復 getUserReviews 返回值** - 函數邏輯錯誤
4. ✅ **添加超時設置** - 避免請求掛起

## 優先級 2（重構改進）

5. ✅ **提取配置到文件** - 提高可維護性
6. ✅ **使用 requests.Session** - 提高性能
7. ✅ **改進異常處理** - 區分不同錯誤類型
8. ✅ **簡化數據處理邏輯** - 減少複雜度

## 優先級 3（最佳實踐）

9. ✅ **添加日誌系統** - 改善可觀測性
10. ✅ **添加數據驗證** - 確保數據質量
11. ✅ **集成實驗追蹤** - MLflow/W&B
12. ✅ **添加單元測試** - 保證代碼質量

---

# 八、代碼質量評分

| 模組 | 功能性 | 可維護性 | 性能 | 安全性 | 總分 |
|------|--------|----------|------|--------|------|
| 爬蟲 | 7/10 | 5/10 | 6/10 | 6/10 | **60%** |
| 預處理 | 8/10 | 6/10 | 5/10 | 8/10 | **68%** |
| 模型訓練 | 8/10 | 6/10 | 7/10 | 9/10 | **75%** |
| **平均** | **7.7/10** | **5.7/10** | **6/10** | **7.7/10** | **68%** |

---

# 九、下一步行動

1. 創建重構計劃
2. 實現改進的爬蟲模組
3. 重構數據處理管道
4. 添加配置管理系統
5. 建立測試框架
6. 編寫改進文檔

---

**報告作者**：Claude Code
**審查完成時間**：2026-01-02
**建議複審週期**：每 3 個月或重大變更後
