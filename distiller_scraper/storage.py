"""
資料儲存層 - 支援 CSV 和 SQLite
使用 Repository Pattern 抽象儲存細節
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
    """SQLite 儲存後端"""

    def __init__(self, db_path: str = "distiller.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
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
        """INSERT 或 UPDATE，回傳 spirit id（始終透過 SELECT 確保正確性）"""
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
        """將 flavor_data dict 寫入 flavor_profiles 表"""
        if not isinstance(flavor_data, dict) or not flavor_data:
            return
        cursor.execute(
            "DELETE FROM flavor_profiles WHERE spirit_id = ?", (spirit_id,)
        )
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
