"""
query.py 單元測試
使用記憶體 SQLite 資料庫，不需要真實資料
"""

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from query import (
    _connect,
    _print_table,
    _score_bar,
    _truncate,
    cmd_info,
    cmd_list,
    cmd_search,
    cmd_stats,
    cmd_top,
    cmd_flavors,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path):
    """建立含測試資料的臨時資料庫"""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.executescript("""
        CREATE TABLE spirits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            spirit_type TEXT,
            brand TEXT,
            country TEXT,
            category TEXT,
            badge TEXT,
            age TEXT,
            abv REAL,
            cost_level INTEGER,
            cask_type TEXT,
            expert_score INTEGER,
            community_score REAL,
            review_count INTEGER,
            description TEXT,
            tasting_notes TEXT,
            expert_name TEXT,
            flavor_summary TEXT,
            flavor_data TEXT,
            url TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE flavor_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spirit_id INTEGER NOT NULL,
            flavor_name TEXT NOT NULL,
            flavor_value INTEGER NOT NULL,
            FOREIGN KEY (spirit_id) REFERENCES spirits(id)
        );
        CREATE TABLE scrape_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TIMESTAMP,
            finished_at TIMESTAMP,
            categories TEXT,
            total_scraped INTEGER DEFAULT 0,
            total_failed INTEGER DEFAULT 0,
            mode TEXT,
            status TEXT DEFAULT 'running'
        );
    """)
    # 插入測試資料
    spirits = [
        ("Highland Park 18 Year", "Single Malt", "Highland Park", "Scotland", 99, 4.47, 43.0, 3, "ex-sherry", 3078, "Rich and smoky.", "Honey and smoke.", "https://distiller.com/spirits/hp18"),
        ("Lagavulin 16 Year", "Single Malt", "Lagavulin", "Scotland", 96, 4.35, 43.0, 3, "ex-bourbon", 2500, "Peaty and bold.", "Smoke and ash.", "https://distiller.com/spirits/lag16"),
        ("Hibiki 21 Year", "Blended", "Suntory", "Japan", 99, 4.52, 43.0, 4, None, 900, "Elegant blend.", "Floral and silky.", "https://distiller.com/spirits/hibiki21"),
        ("Monkey 47 Dry Gin", "Modern Gin", "Monkey 47", "Germany", 99, 4.12, 47.0, 3, None, 1763, "Complex gin.", "Juniper and citrus.", "https://distiller.com/spirits/monkey47"),
        ("Tito's Vodka", "Unflavored Vodka", "Tito's", "USA", 78, 3.5, 40.0, 1, None, 500, "Simple vodka.", "Clean and smooth.", "https://distiller.com/spirits/titos"),
    ]
    for s in spirits:
        conn.execute(
            "INSERT INTO spirits (name, spirit_type, brand, country, expert_score, community_score, abv, cost_level, cask_type, review_count, description, tasting_notes, url) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            s,
        )
    # 風味資料
    flavors = [
        (1, "smoky", 40), (1, "sweet", 70), (1, "rich", 80),
        (2, "smoky", 90), (2, "peaty", 80),
        (3, "floral", 60), (3, "sweet", 50),
    ]
    conn.executemany(
        "INSERT INTO flavor_profiles (spirit_id, flavor_name, flavor_value) VALUES (?,?,?)",
        flavors,
    )
    # 爬取記錄
    conn.execute(
        "INSERT INTO scrape_runs (started_at, finished_at, total_scraped, total_failed, status) VALUES ('2026-02-28','2026-02-28',5,0,'completed')"
    )
    conn.commit()
    conn.close()
    return str(db)


class FakeArgs:
    """模擬 argparse namespace"""
    def __init__(self, db, **kwargs):
        self.db = db
        for k, v in kwargs.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# 格式化輔助
# ---------------------------------------------------------------------------

class TestTruncate:
    def test_short_text(self):
        assert _truncate("abc", 10) == "abc"

    def test_exact_width(self):
        assert _truncate("abcde", 5) == "abcde"

    def test_long_text(self):
        assert _truncate("abcdefgh", 5) == "abcd…"

    def test_empty(self):
        assert _truncate("", 5) == ""

    def test_none(self):
        assert _truncate(None, 5) == ""


class TestScoreBar:
    def test_full_score(self):
        assert _score_bar(100) == "██████████"

    def test_half_score(self):
        assert _score_bar(50) == "█████░░░░░"

    def test_none_score(self):
        assert _score_bar(None) == ""


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------

class TestCmdList:
    def test_default_list(self, db_path, capsys):
        args = FakeArgs(db_path, type=None, country=None, brand=None, min_score=None, max_score=None, sort="expert_score", asc=False, limit=20)
        cmd_list(args)
        out = capsys.readouterr().out
        assert "Highland Park" in out
        assert "共 5 筆" in out

    def test_filter_by_country(self, db_path, capsys):
        args = FakeArgs(db_path, type=None, country="Japan", brand=None, min_score=None, max_score=None, sort="expert_score", asc=False, limit=20)
        cmd_list(args)
        out = capsys.readouterr().out
        assert "Hibiki" in out
        assert "共 1 筆" in out

    def test_filter_by_min_score(self, db_path, capsys):
        args = FakeArgs(db_path, type=None, country=None, brand=None, min_score=99, max_score=None, sort="expert_score", asc=False, limit=20)
        cmd_list(args)
        out = capsys.readouterr().out
        assert "共 3 筆" in out

    def test_filter_by_type(self, db_path, capsys):
        args = FakeArgs(db_path, type="Single Malt", country=None, brand=None, min_score=None, max_score=None, sort="expert_score", asc=False, limit=20)
        cmd_list(args)
        out = capsys.readouterr().out
        assert "Highland Park" in out
        assert "Lagavulin" in out


class TestCmdSearch:
    def test_search_by_name(self, db_path, capsys):
        args = FakeArgs(db_path, keyword="Highland", limit=20)
        cmd_search(args)
        out = capsys.readouterr().out
        assert "Highland Park" in out
        assert "找到 1 筆" in out

    def test_search_by_brand(self, db_path, capsys):
        args = FakeArgs(db_path, keyword="Suntory", limit=20)
        cmd_search(args)
        out = capsys.readouterr().out
        assert "Hibiki" in out

    def test_search_no_results(self, db_path, capsys):
        args = FakeArgs(db_path, keyword="zzzznotexist", limit=20)
        cmd_search(args)
        out = capsys.readouterr().out
        assert "找到 0 筆" in out


class TestCmdTop:
    def test_top_3(self, db_path, capsys):
        args = FakeArgs(db_path, n=3)
        cmd_top(args)
        out = capsys.readouterr().out
        assert "#1" in out
        assert "#3" in out
        assert "Top 3" in out


class TestCmdInfo:
    def test_info_found(self, db_path, capsys):
        args = FakeArgs(db_path, name="Highland Park")
        cmd_info(args)
        out = capsys.readouterr().out
        assert "Highland Park 18 Year" in out
        assert "Single Malt" in out
        assert "ex-sherry" in out
        assert "smoky" in out  # 風味
        assert "rich" in out

    def test_info_not_found(self, db_path, capsys):
        args = FakeArgs(db_path, name="zzzznotexist")
        cmd_info(args)
        out = capsys.readouterr().out
        assert "找不到" in out


class TestCmdStats:
    def test_stats_output(self, db_path, capsys):
        args = FakeArgs(db_path)
        cmd_stats(args)
        out = capsys.readouterr().out
        assert "總筆數：5" in out
        assert "類型分布" in out
        assert "產地分布" in out
        assert "評分分布" in out
        assert "爬取記錄" in out


class TestCmdFlavors:
    def test_flavors_overview(self, db_path, capsys):
        args = FakeArgs(db_path, name=None, min_value=0, limit=15)
        cmd_flavors(args)
        out = capsys.readouterr().out
        assert "風味維度統計" in out
        assert "smoky" in out

    def test_flavors_by_name(self, db_path, capsys):
        args = FakeArgs(db_path, name="smoky", min_value=50, limit=15)
        cmd_flavors(args)
        out = capsys.readouterr().out
        assert "Lagavulin" in out
        assert "風味「smoky」" in out


class TestConnect:
    def test_missing_db(self):
        with pytest.raises(SystemExit):
            _connect("/nonexistent/path.db")
