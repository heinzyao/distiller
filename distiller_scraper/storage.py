"""
資料儲存層：抽象化 SQLite 與 CSV 兩種儲存後端。

架構設計（Repository Pattern）
--------------------------------
使用抽象基礎類別 StorageBackend 定義統一介面，
SQLiteStorage 和 CSVStorage 分別實作：

  StorageBackend（ABC）
       ├─ SQLiteStorage  ← 生產環境：支援查詢、去重、提醒、批次更新
       └─ CSVStorage     ← 相容性：向後相容，輕量輸出，適合簡單場景

設計理由：
- DistillerScraperV2 透過 storage 注入後端，不直接依賴 SQLite 或 pandas
  → 爬蟲邏輯與儲存細節解耦，方便測試和替換後端
- SQLiteStorage 在每次 save_spirit 後立即 commit（即時持久化）
  → 爬蟲中途中斷時，已爬取的資料不會遺失
- CSVStorage 在記憶體中累積，呼叫 flush() 才寫入磁碟
  → 適合批次處理，不適合長時間爬取

SQLite Schema 設計要點
-----------------------
- spirits.url 設 UNIQUE：防止重複爬取同一烈酒頁面（url 是天然主鍵）
- flavor_profiles：獨立資料表 + FOREIGN KEY，支援依風味維度查詢
  （如：找出 smoky 分數最高的 10 款威士忌）
- scrape_runs：紀錄每次爬取的元資料，用於稽核與效能分析
- WAL (Write-Ahead Logging)：允許讀寫同時進行，提升並發效能
- PRAGMA foreign_keys = ON：強制執行 FK 約束（SQLite 預設關閉）

欄位轉型輔助函式
----------------
_to_real / _to_int / _to_text：統一處理 "N/A" / "" / None 轉換，
避免在各處重複寫 try/except 的轉型邏輯
"""

import json
import logging
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pandas as pd

from .config import ScraperConfig

logger = logging.getLogger(__name__)

# SQLite schema
_DDL = """
CREATE TABLE IF NOT EXISTS spirits (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    spirit_type    TEXT,
    brand          TEXT,
    country        TEXT,
    category       TEXT,
    badge          TEXT,
    age            TEXT,
    abv            REAL,
    cost_level     INTEGER,
    cask_type      TEXT,
    expert_score   INTEGER,
    community_score REAL,
    review_count   INTEGER,
    description    TEXT,
    tasting_notes  TEXT,
    expert_name    TEXT,
    flavor_summary TEXT,
    flavor_data    TEXT,
    url            TEXT UNIQUE NOT NULL,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS flavor_profiles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    spirit_id     INTEGER NOT NULL,
    flavor_name   TEXT NOT NULL,
    flavor_value  INTEGER NOT NULL,
    FOREIGN KEY (spirit_id) REFERENCES spirits(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at     TIMESTAMP NOT NULL,
    finished_at    TIMESTAMP,
    categories     TEXT,
    total_scraped  INTEGER DEFAULT 0,
    total_failed   INTEGER DEFAULT 0,
    mode           TEXT,
    status         TEXT DEFAULT 'running'
);

CREATE INDEX IF NOT EXISTS idx_spirits_category      ON spirits(category);
CREATE INDEX IF NOT EXISTS idx_spirits_brand         ON spirits(brand);
CREATE INDEX IF NOT EXISTS idx_spirits_country       ON spirits(country);
CREATE INDEX IF NOT EXISTS idx_spirits_expert_score  ON spirits(expert_score);
CREATE INDEX IF NOT EXISTS idx_flavor_spirit         ON flavor_profiles(spirit_id);
CREATE INDEX IF NOT EXISTS idx_flavor_name           ON flavor_profiles(flavor_name);
"""

# 欄位轉型輔助
def _to_real(value: Any) -> Optional[float]:
    if value in (None, "N/A", ""):
        return None
    try:
        return float(str(value).replace("%", "").strip())
    except (ValueError, TypeError):
        return None


def _to_int(value: Any) -> Optional[int]:
    if value in (None, "N/A", ""):
        return None
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def _to_text(value: Any) -> Optional[str]:
    if value in (None, "N/A", ""):
        return None
    return str(value).strip()


class StorageBackend(ABC):
    """儲存後端抽象介面"""

    @abstractmethod
    def save_spirit(self, data: Dict) -> bool:
        """儲存單筆烈酒資料，回傳是否成功"""

    @abstractmethod
    def save_spirits(self, data_list: List[Dict]) -> int:
        """批次儲存多筆資料，回傳成功筆數"""

    @abstractmethod
    def spirit_exists(self, url: str) -> bool:
        """檢查 URL 是否已存在"""

    @abstractmethod
    def get_existing_urls(self) -> Set[str]:
        """取得所有已儲存的 URL"""

    @abstractmethod
    def get_all_spirits(self) -> List[Dict]:
        """取得所有資料"""

    @abstractmethod
    def close(self):
        """關閉連線 / 釋放資源"""


class SQLiteStorage(StorageBackend):
    """SQLite 儲存後端：生產環境推薦，支援查詢、更新、風味關聯查詢。

    連線設定說明：
    - row_factory = sqlite3.Row：讓查詢結果支援欄位名稱存取（dict-like）
    - PRAGMA foreign_keys = ON：SQLite 預設不強制 FK，需明確啟用
    - PRAGMA journal_mode = WAL：Write-Ahead Logging，允許讀寫同時進行
      （比預設的 DELETE journal 在並發場景更穩定）
    """

    def __init__(self, db_path: str = "distiller.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")   # 強制 FK 約束
        self.conn.execute("PRAGMA journal_mode = WAL")  # 讀寫分離，提升並發效能
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(_DDL)
        self.conn.commit()

    # ------------------------------------------------------------------
    # 私有輔助
    # ------------------------------------------------------------------

    def _prepare_row(self, data: Dict) -> Dict:
        """將爬蟲資料轉換為資料庫欄位格式"""
        flavor_raw = data.get("flavor_data", {})
        flavor_json = (
            json.dumps(flavor_raw, ensure_ascii=False)
            if isinstance(flavor_raw, dict)
            else (flavor_raw or None)
        )
        return {
            "name":            _to_text(data.get("name")),
            "spirit_type":     _to_text(data.get("spirit_type")),
            "brand":           _to_text(data.get("brand")),
            "country":         _to_text(data.get("country")),
            "category":        _to_text(data.get("category")),
            "badge":           _to_text(data.get("badge")),
            "age":             _to_text(data.get("age")),
            "abv":             _to_real(data.get("abv")),
            "cost_level":      _to_int(data.get("cost_level")),
            "cask_type":       _to_text(data.get("cask_type")),
            "expert_score":    _to_int(data.get("expert_score")),
            "community_score": _to_real(data.get("community_score")),
            "review_count":    _to_int(data.get("review_count")),
            "description":     _to_text(data.get("description")),
            "tasting_notes":   _to_text(data.get("tasting_notes")),
            "expert_name":     _to_text(data.get("expert_name")),
            "flavor_summary":  _to_text(data.get("flavor_summary")),
            "flavor_data":     flavor_json,
            "url":             data.get("url", ""),
        }

    def _upsert(self, cursor: sqlite3.Cursor, row: Dict) -> int:
        """INSERT 或 UPDATE，回傳 spirit id。

        設計理由——為何不用 INSERT OR REPLACE？
        - INSERT OR REPLACE 會刪除舊紀錄再插入，spirit_id 會改變
          → flavor_profiles 的 FOREIGN KEY 會 CASCADE DELETE，風味資料遺失
        - 改用 SELECT 判斷 + 手動 UPDATE/INSERT，確保 id 不變且 FK 安全

        spirit_id 的取得策略：
        - 更新已存在的紀錄時：從 SELECT 結果取得原始 id
        - 新插入的紀錄：從 cursor.lastrowid 取得自動遞增的 id
        """
        existing = cursor.execute(
            "SELECT id FROM spirits WHERE url = ?", (row["url"],)
        ).fetchone()

        if existing:
            spirit_id = existing[0]
            cursor.execute(
                """
                UPDATE spirits SET
                    name = :name, spirit_type = :spirit_type, brand = :brand,
                    country = :country, category = :category, badge = :badge,
                    age = :age, abv = :abv, cost_level = :cost_level,
                    cask_type = :cask_type, expert_score = :expert_score,
                    community_score = :community_score, review_count = :review_count,
                    description = :description, tasting_notes = :tasting_notes,
                    expert_name = :expert_name, flavor_summary = :flavor_summary,
                    flavor_data = :flavor_data, updated_at = CURRENT_TIMESTAMP
                WHERE url = :url
                """,
                row,
            )
        else:
            cursor.execute(
                """
                INSERT INTO spirits
                    (name, spirit_type, brand, country, category, badge, age, abv,
                     cost_level, cask_type, expert_score, community_score, review_count,
                     description, tasting_notes, expert_name, flavor_summary, flavor_data, url)
                VALUES
                    (:name, :spirit_type, :brand, :country, :category, :badge, :age, :abv,
                     :cost_level, :cask_type, :expert_score, :community_score, :review_count,
                     :description, :tasting_notes, :expert_name, :flavor_summary, :flavor_data, :url)
                """,
                row,
            )
            spirit_id = cursor.lastrowid

        return spirit_id

    def _save_flavors(self, cursor: sqlite3.Cursor, spirit_id: int, flavor_data: Any):
        """將 flavor_data dict 寫入 flavor_profiles 資料表。

        設計理由——先 DELETE 再 INSERT：
        - 更新場景下，風味資料可能新增或移除維度（如網站改版）
        - 逐一比對新舊差異比較複雜，直接刪除再批次插入更簡單可靠
        - executemany 批次插入效率遠高於逐筆 execute
        """
        if not isinstance(flavor_data, dict) or not flavor_data:
            return
        # 先刪除此 spirit 的舊風味資料（更新時確保資料一致）
        cursor.execute(
            "DELETE FROM flavor_profiles WHERE spirit_id = ?", (spirit_id,)
        )
        # 批次插入新風味資料
        cursor.executemany(
            "INSERT INTO flavor_profiles (spirit_id, flavor_name, flavor_value) VALUES (?, ?, ?)",
            [(spirit_id, k, v) for k, v in flavor_data.items()],
        )

    # ------------------------------------------------------------------
    # 公開 API
    # ------------------------------------------------------------------

    def save_spirit(self, data: Dict) -> bool:
        try:
            row = self._prepare_row(data)
            with self.conn:
                cur = self.conn.cursor()
                spirit_id = self._upsert(cur, row)
                self._save_flavors(cur, spirit_id, data.get("flavor_data", {}))
            return True
        except Exception as e:
            logger.error(f"SQLiteStorage.save_spirit 失敗: {e}")
            return False

    def save_spirits(self, data_list: List[Dict]) -> int:
        """批次儲存，每筆獨立 commit 以允許部分失敗"""
        success = 0
        for data in data_list:
            if self.save_spirit(data):
                success += 1
        return success

    def spirit_exists(self, url: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM spirits WHERE url = ? LIMIT 1", (url,)
        )
        return cur.fetchone() is not None

    def get_existing_urls(self) -> Set[str]:
        rows = self.conn.execute("SELECT url FROM spirits").fetchall()
        return {r[0] for r in rows}

    def get_all_spirits(self) -> List[Dict]:
        rows = self.conn.execute("SELECT * FROM spirits ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def query_spirits(
        self,
        category: str = None,
        min_score: int = None,
        country: str = None,
        limit: int = None,
    ) -> List[Dict]:
        """條件查詢"""
        conditions, params = [], []
        if category:
            conditions.append("category = ?")
            params.append(category)
        if min_score is not None:
            conditions.append("expert_score >= ?")
            params.append(min_score)
        if country:
            conditions.append("country = ?")
            params.append(country)

        sql = "SELECT * FROM spirits"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY expert_score DESC NULLS LAST"
        if limit:
            sql += f" LIMIT {int(limit)}"

        rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def record_scrape_run(
        self,
        categories: List[str],
        mode: str,
        started_at: datetime = None,
    ) -> int:
        """建立爬取批次記錄，回傳 run_id"""
        started_at = started_at or datetime.now()
        cur = self.conn.execute(
            """
            INSERT INTO scrape_runs (started_at, categories, mode)
            VALUES (?, ?, ?)
            """,
            (started_at.isoformat(), json.dumps(categories), mode),
        )
        self.conn.commit()
        return cur.lastrowid

    def finish_scrape_run(
        self, run_id: int, total_scraped: int, total_failed: int, status: str = "completed"
    ):
        self.conn.execute(
            """
            UPDATE scrape_runs
            SET finished_at = CURRENT_TIMESTAMP,
                total_scraped = ?,
                total_failed = ?,
                status = ?
            WHERE id = ?
            """,
            (total_scraped, total_failed, status, run_id),
        )
        self.conn.commit()

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM spirits").fetchone()[0]

    def to_dataframe(self) -> "pd.DataFrame":
        return pd.read_sql_query("SELECT * FROM spirits", self.conn)

    def export_csv(self, filename: str) -> bool:
        try:
            df = self.to_dataframe()
            df.to_csv(filename, index=False, encoding=ScraperConfig.OUTPUT_ENCODING)
            logger.info(f"✓ 已匯出 {len(df)} 筆資料至 {filename}")
            return True
        except Exception as e:
            logger.error(f"匯出 CSV 失敗: {e}")
            return False

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None


class CSVStorage(StorageBackend):
    """CSV 儲存後端（向後相容）"""

    def __init__(self, filename: str = "distiller_spirits.csv"):
        self.filename = filename
        self._data: List[Dict] = []
        self._urls: Set[str] = set()

    def save_spirit(self, data: Dict) -> bool:
        url = data.get("url", "")
        if url in self._urls:
            return False
        self._data.append(data)
        self._urls.add(url)
        return True

    def save_spirits(self, data_list: List[Dict]) -> int:
        return sum(self.save_spirit(d) for d in data_list)

    def spirit_exists(self, url: str) -> bool:
        return url in self._urls

    def get_existing_urls(self) -> Set[str]:
        return set(self._urls)

    def get_all_spirits(self) -> List[Dict]:
        return list(self._data)

    def flush(self) -> bool:
        """將快取資料寫入 CSV"""
        if not self._data:
            logger.warning("CSVStorage: 沒有資料可儲存")
            return False
        try:
            df_data = []
            for item in self._data:
                row = item.copy()
                if isinstance(row.get("flavor_data"), dict):
                    row["flavor_data"] = json.dumps(row["flavor_data"], ensure_ascii=False)
                df_data.append(row)
            pd.DataFrame(df_data).to_csv(
                self.filename, index=False, encoding=ScraperConfig.OUTPUT_ENCODING
            )
            logger.info(f"✓ 已儲存 {len(df_data)} 筆資料至 {self.filename}")
            return True
        except Exception as e:
            logger.error(f"CSVStorage.flush 失敗: {e}")
            return False

    def close(self):
        pass
