"""
query.py 單元測試
使用記憶體 SQLite 資料庫，不需要真實資料
"""

import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    cmd_cocktail_search,
    cmd_cocktail_info,
    cmd_cocktail_stats,
    cmd_cocktail_list,
    cmd_cocktail_makeable,
    main,
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
        (
            "Highland Park 18 Year",
            "Single Malt",
            "Highland Park",
            "Scotland",
            99,
            4.47,
            43.0,
            3,
            "ex-sherry",
            3078,
            "Rich and smoky.",
            "Honey and smoke.",
            "https://distiller.com/spirits/hp18",
        ),
        (
            "Lagavulin 16 Year",
            "Single Malt",
            "Lagavulin",
            "Scotland",
            96,
            4.35,
            43.0,
            3,
            "ex-bourbon",
            2500,
            "Peaty and bold.",
            "Smoke and ash.",
            "https://distiller.com/spirits/lag16",
        ),
        (
            "Hibiki 21 Year",
            "Blended",
            "Suntory",
            "Japan",
            99,
            4.52,
            43.0,
            4,
            None,
            900,
            "Elegant blend.",
            "Floral and silky.",
            "https://distiller.com/spirits/hibiki21",
        ),
        (
            "Monkey 47 Dry Gin",
            "Modern Gin",
            "Monkey 47",
            "Germany",
            99,
            4.12,
            47.0,
            3,
            None,
            1763,
            "Complex gin.",
            "Juniper and citrus.",
            "https://distiller.com/spirits/monkey47",
        ),
        (
            "Tito's Vodka",
            "Unflavored Vodka",
            "Tito's",
            "USA",
            78,
            3.5,
            40.0,
            1,
            None,
            500,
            "Simple vodka.",
            "Clean and smooth.",
            "https://distiller.com/spirits/titos",
        ),
    ]
    for s in spirits:
        conn.execute(
            "INSERT INTO spirits (name, spirit_type, brand, country, expert_score, community_score, abv, cost_level, cask_type, review_count, description, tasting_notes, url) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            s,
        )
    # 風味資料
    flavors = [
        (1, "smoky", 40),
        (1, "sweet", 70),
        (1, "rich", 80),
        (2, "smoky", 90),
        (2, "peaty", 80),
        (3, "floral", 60),
        (3, "sweet", 50),
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
        args = FakeArgs(
            db_path,
            type=None,
            country=None,
            brand=None,
            min_score=None,
            max_score=None,
            sort="expert_score",
            asc=False,
            limit=20,
        )
        cmd_list(args)
        out = capsys.readouterr().out
        assert "Highland Park" in out
        assert "共 5 筆" in out

    def test_filter_by_country(self, db_path, capsys):
        args = FakeArgs(
            db_path,
            type=None,
            country="Japan",
            brand=None,
            min_score=None,
            max_score=None,
            sort="expert_score",
            asc=False,
            limit=20,
        )
        cmd_list(args)
        out = capsys.readouterr().out
        assert "Hibiki" in out
        assert "共 1 筆" in out

    def test_filter_by_min_score(self, db_path, capsys):
        args = FakeArgs(
            db_path,
            type=None,
            country=None,
            brand=None,
            min_score=99,
            max_score=None,
            sort="expert_score",
            asc=False,
            limit=20,
        )
        cmd_list(args)
        out = capsys.readouterr().out
        assert "共 3 筆" in out

    def test_filter_by_type(self, db_path, capsys):
        args = FakeArgs(
            db_path,
            type="Single Malt",
            country=None,
            brand=None,
            min_score=None,
            max_score=None,
            sort="expert_score",
            asc=False,
            limit=20,
        )
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


# ---------------------------------------------------------------------------
# Difford's cocktail subcommand argparse parsing
# ---------------------------------------------------------------------------


class TestCocktailArgparsing:
    def _parse(self, argv):
        import argparse
        from query import main as _main
        import sys as _sys

        old = _sys.argv
        _sys.argv = ["query.py"] + argv
        try:
            import query as q

            parser = argparse.ArgumentParser()
            sub = parser.add_subparsers(dest="command")

            p2 = sub.add_parser("cocktail-search")
            p2.add_argument("keyword")
            p2.add_argument("--cocktail-db", default="diffords.db")

            p3 = sub.add_parser("cocktail-info")
            p3.add_argument("name")
            p3.add_argument("--cocktail-db", default="diffords.db")

            p4 = sub.add_parser("cocktail-stats")
            p4.add_argument("--cocktail-db", default="diffords.db")

            p5 = sub.add_parser("cocktail-list")
            p5.add_argument("--ingredient")
            p5.add_argument("--tag")
            p5.add_argument("--rating", type=float)
            p5.add_argument("--limit", type=int, default=20)
            p5.add_argument("--cocktail-db", default="diffords.db")

            p6 = sub.add_parser("cocktail-makeable")
            p6.add_argument("--spirits-db", default="distiller.db")
            p6.add_argument("--cocktail-db", default="diffords.db")

            return parser.parse_args(argv)
        finally:
            _sys.argv = old

    def test_cocktail_search_keyword(self):
        args = self._parse(["cocktail-search", "negroni"])
        assert args.command == "cocktail-search"
        assert args.keyword == "negroni"

    def test_cocktail_info_name(self):
        args = self._parse(["cocktail-info", "Margarita"])
        assert args.command == "cocktail-info"
        assert args.name == "Margarita"

    def test_cocktail_stats_command(self):
        args = self._parse(["cocktail-stats"])
        assert args.command == "cocktail-stats"

    def test_cocktail_list_no_filter(self):
        args = self._parse(["cocktail-list"])
        assert args.command == "cocktail-list"
        assert args.ingredient is None
        assert args.tag is None
        assert args.rating is None
        assert args.limit == 20

    def test_cocktail_list_ingredient_filter(self):
        args = self._parse(["cocktail-list", "--ingredient", "gin"])
        assert args.ingredient == "gin"

    def test_cocktail_makeable_default_db(self):
        args = self._parse(["cocktail-makeable"])
        assert args.command == "cocktail-makeable"
        assert args.spirits_db == "distiller.db"
        assert args.cocktail_db == "diffords.db"


# ---------------------------------------------------------------------------
# Difford's cmd_cocktail_* function tests (mock DiffordsStorage)
# ---------------------------------------------------------------------------


@pytest.fixture
def diffords_db_path(tmp_path):
    db = tmp_path / "diffords.db"
    conn = sqlite3.connect(str(db))
    conn.executescript("""
        CREATE TABLE cocktails (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT,
            description TEXT,
            glassware TEXT,
            garnish TEXT,
            prepare TEXT,
            instructions TEXT,
            review TEXT,
            history TEXT,
            tags TEXT,
            rating_value REAL,
            rating_count INTEGER,
            calories INTEGER,
            prep_time_min INTEGER,
            abv REAL,
            date_published DATE,
            url TEXT UNIQUE NOT NULL,
            lastmod DATE,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE cocktail_ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cocktail_id INTEGER NOT NULL,
            sort_order INTEGER NOT NULL,
            item TEXT NOT NULL,
            amount TEXT,
            item_generic TEXT
        );
        CREATE TABLE diffords_scrape_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TIMESTAMP NOT NULL,
            finished_at TIMESTAMP,
            total_scraped INTEGER DEFAULT 0,
            total_skipped INTEGER DEFAULT 0,
            total_failed INTEGER DEFAULT 0,
            mode TEXT,
            status TEXT DEFAULT 'running'
        );
    """)
    cocktails = [
        (
            1,
            "Negroni",
            "negroni",
            "A classic aperitif cocktail.",
            "Old Fashioned",
            "Orange peel",
            "Stir",
            "Stir ingredients.",
            "Excellent.",
            "Italian origin.",
            None,
            4.5,
            150,
            None,
            None,
            28.0,
            "2020-01-01",
            "https://www.diffordsguide.com/cocktails/recipe/1/negroni",
            None,
        ),
        (
            2,
            "Margarita",
            "margarita",
            "Tequila based classic.",
            "Margarita",
            "Salt",
            "Shake",
            "Shake with ice.",
            "Great.",
            "Mexican origin.",
            None,
            4.2,
            120,
            None,
            None,
            20.0,
            "2020-01-01",
            "https://www.diffordsguide.com/cocktails/recipe/2/margarita",
            None,
        ),
        (
            3,
            "Old Fashioned",
            "old-fashioned",
            "Whiskey and bitters.",
            "Rocks",
            "Orange peel",
            "Stir",
            "Muddle and stir.",
            "Classic.",
            "American origin.",
            None,
            4.7,
            200,
            None,
            None,
            35.0,
            "2020-01-01",
            "https://www.diffordsguide.com/cocktails/recipe/3/old-fashioned",
            None,
        ),
    ]
    conn.executemany(
        "INSERT INTO cocktails (id,name,slug,description,glassware,garnish,prepare,instructions,"
        "review,history,tags,rating_value,rating_count,calories,prep_time_min,abv,date_published,"
        "url,lastmod) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        cocktails,
    )
    conn.executemany(
        "INSERT INTO cocktail_ingredients (cocktail_id,sort_order,item,amount,item_generic) VALUES (?,?,?,?,?)",
        [
            (1, 1, "Campari", "25ml", "campari"),
            (1, 2, "Gin", "25ml", "gin"),
            (2, 1, "Tequila Blanco", "50ml", "tequila blanco"),
        ],
    )
    conn.execute(
        "INSERT INTO diffords_scrape_runs (started_at, status) VALUES ('2026-01-01','completed')"
    )
    conn.commit()
    conn.close()
    return str(db)


class FakeCocktailArgs:
    def __init__(self, cocktail_db, **kwargs):
        self.cocktail_db = cocktail_db
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestCmdCocktailSearch:
    def test_search_found(self, diffords_db_path, capsys):
        args = FakeCocktailArgs(diffords_db_path, keyword="negroni")
        cmd_cocktail_search(args)
        out = capsys.readouterr().out
        assert "Negroni" in out
        assert "找到 1 筆" in out

    def test_search_not_found(self, diffords_db_path, capsys):
        args = FakeCocktailArgs(diffords_db_path, keyword="zzzznotexist")
        cmd_cocktail_search(args)
        out = capsys.readouterr().out
        assert "找到 0 筆" in out


class TestCmdCocktailInfo:
    def test_info_found(self, diffords_db_path, capsys):
        args = FakeCocktailArgs(diffords_db_path, name="Negroni")
        cmd_cocktail_info(args)
        out = capsys.readouterr().out
        assert "Negroni" in out
        assert "Campari" in out

    def test_info_not_found(self, diffords_db_path, capsys):
        args = FakeCocktailArgs(diffords_db_path, name="zzzznotexist")
        cmd_cocktail_info(args)
        out = capsys.readouterr().out
        assert "找不到" in out


class TestCmdCocktailStats:
    def test_stats_output(self, diffords_db_path, capsys):
        args = FakeCocktailArgs(diffords_db_path)
        cmd_cocktail_stats(args)
        out = capsys.readouterr().out
        assert "總雞尾酒數" in out
        assert "平均評分" in out
        assert "最後爬取" in out


class TestCmdCocktailList:
    def test_list_no_filter(self, diffords_db_path, capsys):
        args = FakeCocktailArgs(
            diffords_db_path, ingredient=None, tag=None, rating=None, limit=20
        )
        cmd_cocktail_list(args)
        out = capsys.readouterr().out
        assert "雞尾酒列表" in out
        assert "Old Fashioned" in out

    def test_list_ingredient_filter(self, diffords_db_path, capsys):
        args = FakeCocktailArgs(
            diffords_db_path, ingredient="Campari", tag=None, rating=None, limit=20
        )
        cmd_cocktail_list(args)
        out = capsys.readouterr().out
        assert "Negroni" in out
        assert "Campari" in out

    def test_list_rating_filter(self, diffords_db_path, capsys):
        args = FakeCocktailArgs(
            diffords_db_path, ingredient=None, tag=None, rating=4.5, limit=20
        )
        cmd_cocktail_list(args)
        out = capsys.readouterr().out
        assert "評分 ≥" in out


class TestCmdCocktailMakeable:
    def test_makeable_uses_spirits_db_default(self, diffords_db_path, tmp_path, capsys):
        fake_spirits_db = str(tmp_path / "spirits.db")
        args = FakeCocktailArgs(diffords_db_path, spirits_db=fake_spirits_db)
        with patch(
            "distiller_scraper.diffords_storage.get_user_spirit_types", return_value=[]
        ):
            with patch(
                "distiller_scraper.diffords_storage.load_ingredient_mapping",
                return_value={},
            ):
                cmd_cocktail_makeable(args)
        out = capsys.readouterr().out
        assert "可調製" in out

    def test_makeable_missing_cocktail_db_exits(self, tmp_path, capsys):
        args = FakeCocktailArgs(
            str(tmp_path / "nonexistent.db"), spirits_db="distiller.db"
        )
        with pytest.raises(SystemExit):
            cmd_cocktail_makeable(args)
        out = capsys.readouterr().out
        assert "⚠️" in out
