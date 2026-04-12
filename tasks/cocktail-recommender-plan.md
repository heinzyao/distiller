# 雞尾酒烈酒推薦系統 — 規劃與進度

> 最後更新：2026-03-31

## 一、背景與目標

### 動機

Distiller 專案每日從 distiller.com 爬取烈酒評測資料（目前 2,840 筆），並透過 LINE Bot 提供查詢服務。本功能擴充旨在運用既有的結構化資料（風味向量 × 30 維、品酒師文字描述、評分等），提供以下新服務：

**「根據用戶的品味偏好，為指定的經典雞尾酒推薦最適合的每一款用料（基酒 + 利口酒 + 修飾酒）」**

### 設計原則

- **多成分覆蓋**：推薦範圍包含基酒、利口酒（Triple Sec、Amaro）、苦艾酒（Vermouth），而非僅限基酒
- **三層推薦模式**：
  - `dynamic`：DB 資料充足，完整個人化推薦
  - `dynamic_or_static`：優先 DB，資料不足時退回靜態知識庫
  - `static_only`：果汁、苦精等永遠使用固定推薦
- **不依賴外部雞尾酒資料庫爬取**：避免 Difford's Guide 等商業網站的法律風險，改用手工整理的 30 款知識庫 + thecocktaildb.com 免費 API（必要時）

---

## 二、架構說明

```
用戶 LINE 訊息
  「雞尾酒 Negroni 我喜歡草本苦味」
        │
        ▼
  bot.py parse_command()
  → command="cocktail", args=["Negroni", "我喜歡草本苦味"]
        │
        ▼
  fmt_cocktail(db_path, "Negroni", "我喜歡草本苦味")
        │
        ├── cocktail_db.get_cocktail("Negroni")
        │   → 取得 Negroni 的成分定義
        │   → 3 個成分：琴酒 / 苦味利口酒 / 甜型苦艾酒
        │
        ├── _parse_flavor_prefs("我喜歡草本苦味")
        │   → {"herbal": 80, "bitter": 75, "juniper": 60}
        │
        └── CocktailRecommender.recommend()
            ├── 針對每個成分 _fetch_candidates()
            │   └── SQLite：spirit_type IN (...) + flavor_profiles
            ├── _score_candidates()
            │   └── 0.45 × cocktail_flavor_sim
            │     + 0.30 × user_flavor_sim     （有偏好時）
            │     + 0.15 × expert_score
            │     + 0.10 × community_score
            │     × abv_penalty
            └── format_recommendation()
                → LINE 文字訊息
```

### 評分權重

| 權重 | 說明 | 無用戶偏好時 |
|------|------|------------|
| 0.45 | 與雞尾酒理想風味的相似度 | → 0.75 |
| 0.30 | 與用戶個人偏好的相似度 | → 0（略去） |
| 0.15 | 專家評分（歸一化） | 不變 |
| 0.10 | 社群評分（歸一化） | 不變 |
| × | ABV 懲罰因子（偏離建議範圍越遠越低） | 不變 |

---

## 三、已完成項目

### 3.1 系統穩定性修復（先前工作）

- [x] **LINE 通知 bug**：scraper 拋出例外時失敗通知被跳過，已修復（commit `9bf5447`）
- [x] **Cloud Run OOM 修復**：Chrome 146 在 2Gi 容器中記憶體溢出，升級至 4Gi（`gcloud run jobs update --memory=4Gi`）
- [x] **靜默失敗根因確認**：第一次 task 失敗（tab crashed）→ Cloud Run 自動重試 → `_should_skip_run()` 偵測到 `completed_with_errors` 跳過 → 顯示假成功

### 3.2 雞尾酒推薦功能（本次實作）

| 編號 | 檔案 | 說明 | 狀態 |
|------|------|------|------|
| T1 | `run.py` | `liqueurs-bitters` 移至 `_full_categories` 第一位 | ✅ 完成 |
| T2 | `scripts/supplement_liqueurs.py` | 一次性補充爬取利口酒類別的腳本 | ✅ 完成 |
| T3 | `distiller_scraper/cocktail_db.py` | 23 款經典雞尾酒知識庫 | ✅ 完成 |
| T4 | `distiller_scraper/recommender.py` | 風味向量推薦引擎 | ✅ 完成 |
| T5 | `bot.py` | 新增 LINE 指令：`雞尾酒 <名稱> [偏好]` | ✅ 完成 |

**測試狀態**：373 passed，0 failures（2026-03-31）

### 3.3 支援的雞尾酒清單（23 款）

| 類型 | 酒款 |
|------|------|
| 琴酒基底 | Negroni、Martini、Gimlet、Last Word、French 75、Singapore Sling |
| 威士忌基底 | Old Fashioned、Manhattan、Whiskey Sour、Sazerac、Penicillin、Paper Plane |
| 蘭姆基底 | Daiquiri、Mojito、Dark & Stormy |
| 伏特加基底 | Cosmopolitan、Moscow Mule、Espresso Martini |
| 龍舌蘭基底 | Margarita、Paloma |
| 白蘭地基底 | Sidecar、Pisco Sour |
| 利口酒主角 | Aperol Spritz |

---

## 四、待辦項目

### ✅ TODO-1 + TODO-2：利口酒資料補充（已完成，2026-04-12）

**根本原因**：`?category=liqueurs-bitters` URL 參數被 distiller.com 靜默忽略，回傳全站排行榜而非利口酒分類。已修復為使用 `spirit_style_id` 子分類 ID（如 `?spirit_style_id=140` for Bitter Liqueurs）。

**成果**：新增 300 筆利口酒資料，關鍵品牌全數收錄：

| 品牌 | 評分 | 狀態 |
|------|------|------|
| Campari | 90 | ✅ |
| Aperol | 92 | ✅ |
| Amaro Nonino Quintessentia | 90 | ✅ |
| Luxardo Maraschino Liqueur | 92 | ✅ |
| Grand Marnier | 88 | ✅ |
| Pierre Ferrand Dry Curaçao | 96 | ✅（原已收錄）|

**注意**：Cointreau、Sweet/Dry Vermouth 主流品牌在 distiller.com 上無評測資料（非台灣/獨立評分網站收錄範圍），仍走 static fallback，屬正常預期。

---

### 🟠 中優先 — 功能增強

#### TODO-3：自然語言偏好解析強化

**現況**：`_parse_flavor_prefs()` 使用關鍵字比對，中文偏好有效，但英文偏好覆蓋有限。

**改善方向**：
```python
# 目前：僅關鍵字比對
"我喜歡煙燻泥煤風格" → {"smoky": 80, "peaty": 85}

# 未來：加入更多語意對應
"像 Islay 風格"      → {"smoky": 80, "peaty": 85, "salty": 50, "earthy": 40}
"類似 Highland Park" → 查詢 DB 中 Highland Park 的風味向量作為參考
"不要太甜"           → {"sweet": 10}  # 反向偏好
```

**或**：接入 Claude API，讓 LLM 直接將偏好文字轉換為風味向量（成本：~0.001 USD / 次）。

---

#### TODO-4：以 Claude API 生成個人化推薦說明

**現況**：推薦輸出為結構化文字，列出品名 + 評分 + 風味摘要。

**目標**：加入 Claude API 生成層，輸出品酒師口吻的個人化說明。

**預期輸出範例**：
```
⭐ Tanqueray Bloomsbury Gin
   評分 91 | 47.3% | $$

   為何適合 Negroni？
   Bloomsbury 系列以馬鞭草和菩提花為核心，帶來細膩花草香
   氣，在 Campari 的苦橙骨架中扮演清新的對位角色。47.3%
   的高酒精度確保了攪拌稀釋後仍保有充足結構感。
```

**實作位置**：`distiller_scraper/recommender.py` 中新增 `generate_explanation()` 函式，調用 `anthropic.messages.create()`。

**依賴**：`anthropic` 套件已在環境中可用。

---

#### TODO-5：新增雞尾酒（擴充知識庫）

目前支援 23 款，建議補充：

| 酒款 | 基底 | 原因 |
|------|------|------|
| Aviation | 琴酒 | 含 Crème de Violette，特殊利口酒推薦機會 |
| Vieux Carré | 裸麥 + 干邑 | 多基酒混合，測試複雜成分推薦 |
| Jungle Bird | 蘭姆 | 含 Campari，與 Negroni 互補 |
| Amaretto Sour | Amaretto | 利口酒為主角的案例 |
| B&B | 干邑 + Bénédictine | 測試草本利口酒推薦 |
| Tommy's Margarita | 龍舌蘭 | 無橙味利口酒的 Margarita 變體 |

---

### 🟡 低優先 — 優化與維護

#### TODO-6：RAG / 語意搜尋層（選配）

**現況**：推薦基於結構化風味向量（cosine similarity），無法理解「像 Bruichladdich 那種風格」這類參照型描述。

**方案**：
- 使用 `sentence-transformers` (all-MiniLM-L6-v2，本地，免費) 對 `description + tasting_notes` 建立 embedding
- 新增 `spirit_embeddings` 資料表儲存 384 維向量
- 用戶偏好文字 → embed → cosine similarity → 與風味向量評分加權融合

**估計工作量**：2–3 天（建立索引腳本 + 修改推薦引擎）

---

#### TODO-7：推薦品質評估機制

建立簡易的人工評分記錄，追蹤推薦品質：

```sql
CREATE TABLE recommendation_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cocktail TEXT NOT NULL,
    spirit_recommended TEXT NOT NULL,
    user_pref_text TEXT,
    rating INTEGER,  -- 1-5
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

可透過 LINE Bot 以「評分 <1-5>」指令收集上一次推薦的回饋。

---

#### TODO-8：deploy.yml 記憶體設定同步

**問題**：GitHub Actions 的 `deploy.yml` 中仍寫 `--memory 2Gi`，下次自動部署會覆蓋已手動升級的 4Gi 設定。

**修改位置**：`.github/workflows/deploy.yml` 第 57 行
```yaml
# 將 --memory 2Gi 改為
--memory 4Gi \
```

---

## 五、已知限制與缺口

| 項目 | 說明 | 對應 TODO |
|------|------|-----------|
| liqueurs-bitters 資料稀少 | 目前僅 8 筆，Campari / Cointreau 缺失 | TODO-1, 2 |
| `category` 欄位空白 | spirits 資料表的 category 欄幾乎全空，推薦改用 URL 路徑過濾 | 已繞過（recommender.py） |
| 自然語言偏好覆蓋有限 | 僅支援約 25 個中文關鍵字 | TODO-3, 4 |
| ABV 缺失值 | 部分烈酒 ABV 為 NULL，ABV 懲罰因子不生效 | 可接受，低優先 |
| 英文多字雞尾酒名稱 | `cocktail Old Fashioned` 需 fallback 邏輯（已實作） | ✅ 已處理 |

---

## 六、執行指令速查

```bash
# 補充爬取 liqueurs-bitters
uv run python scripts/supplement_liqueurs.py

# 驗證補爬結果
sqlite3 distiller.db "SELECT spirit_type, COUNT(*) FROM spirits GROUP BY spirit_type ORDER BY COUNT(*) DESC LIMIT 20;"

# 本地測試推薦引擎
uv run python -c "
from distiller_scraper.recommender import CocktailRecommender, format_recommendation
with CocktailRecommender('distiller.db') as rec:
    result = rec.recommend('negroni', user_flavor_prefs={'herbal': 80})
print(format_recommendation(result))
"

# 執行全套測試
uv run pytest tests/ -q

# 觸發 Cloud Run 補爬（利口酒現排第一位）
gcloud run jobs execute distiller-scraper --region=asia-east1 --project=amateur-intelligence-service
```

---

## 七、優先序總覽

```
立即   TODO-1  ✅ 執行 supplement_liqueurs.py 補充爬取（300 筆，2026-04-12）
       TODO-2  ✅ 驗證關鍵利口酒品牌覆蓋率（Campari/Aperol/Nonino/Luxardo 全數收錄）
       TODO-8  ✅ deploy.yml 記憶體 2Gi → 4Gi（commit c75a30d）

短期   TODO-3  自然語言偏好解析強化
       TODO-4  Claude API 個人化推薦說明
       TODO-5  新增 6 款雞尾酒

長期   TODO-6  RAG 語意搜尋層
       TODO-7  推薦品質評估機制
```
