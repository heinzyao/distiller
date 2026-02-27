"""
StorageBackend 單元測試
使用 SQLite in-memory 資料庫，不依賴真實檔案
"""

import json

import pytest

from distiller_scraper.storage import CSVStorage, SQLiteStorage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    """每個測試用獨立的 in-memory SQLite"""
    storage = SQLiteStorage(":memory:")
    yield storage
    storage.close()


@pytest.fixture
def sample_spirit():
    return {
        "name": "Highland Park 18 Year",
        "spirit_type": "Single Malt",
        "brand": "Highland Park",
        "country": "Scotland",
        "category": "whiskey",
        "badge": "N/A",
        "age": "18 Year",
        "abv": "43.0",
        "cost_level": "4",
        "cask_type": "N/A",
        "expert_score": "99",
        "community_score": "4.47",
        "review_count": "512",
        "description": "A complex whisky with heather honey notes.",
        "tasting_notes": "Rich and smoky.",
        "expert_name": "Jonah",
        "flavor_summary": "Smoky & Sweet",
        "flavor_data": {"smoky": 40, "sweet": 35, "spicy": 25},
        "url": "https://distiller.com/spirits/highland-park-18",
    }


@pytest.fixture
def csv_storage(tmp_path):
    return CSVStorage(str(tmp_path / "test.csv"))


# ---------------------------------------------------------------------------
# SQLiteStorage 測試
# ---------------------------------------------------------------------------

class TestSQLiteStorageSchema:
    def test_tables_created(self, db):
        tables = {r[0] for r in db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert {"spirits", "flavor_profiles", "scrape_runs"}.issubset(tables)

    def test_indexes_created(self, db):
        indexes = {r[0] for r in db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()}
        assert "idx_spirits_category" in indexes
        assert "idx_spirits_expert_score" in indexes


class TestSQLiteStorageSaveSpirit:
    def test_save_spirit_success(self, db, sample_spirit):
        assert db.save_spirit(sample_spirit) is True
        assert db.count() == 1

    def test_save_spirit_deduplication(self, db, sample_spirit):
        db.save_spirit(sample_spirit)
        db.save_spirit(sample_spirit)  # 同 URL，應 upsert 而非重複
        assert db.count() == 1

    def test_save_spirit_upsert_updates_fields(self, db, sample_spirit):
        db.save_spirit(sample_spirit)
        updated = {**sample_spirit, "expert_score": "100"}
        db.save_spirit(updated)
        row = db.conn.execute("SELECT expert_score FROM spirits").fetchone()
        assert row[0] == 100

    def test_save_spirit_type_conversion(self, db, sample_spirit):
        db.save_spirit(sample_spirit)
        row = db.conn.execute("SELECT abv, expert_score, community_score, review_count FROM spirits").fetchone()
        assert row["abv"] == 43.0
        assert row["expert_score"] == 99
        assert row["community_score"] == pytest.approx(4.47)
        assert row["review_count"] == 512

    def test_save_spirit_na_becomes_null(self, db, sample_spirit):
        spirit = {**sample_spirit, "age": "N/A", "cask_type": ""}
        db.save_spirit(spirit)
        row = db.conn.execute("SELECT age, cask_type FROM spirits").fetchone()
        assert row["age"] is None
        assert row["cask_type"] is None

    def test_save_spirit_flavor_profiles(self, db, sample_spirit):
        db.save_spirit(sample_spirit)
        spirit_id = db.conn.execute("SELECT id FROM spirits").fetchone()[0]
        flavors = db.conn.execute(
            "SELECT flavor_name, flavor_value FROM flavor_profiles WHERE spirit_id = ?",
            (spirit_id,)
        ).fetchall()
        flavor_dict = {r[0]: r[1] for r in flavors}
        assert flavor_dict == {"smoky": 40, "sweet": 35, "spicy": 25}

    def test_save_spirit_flavor_data_stored_as_json(self, db, sample_spirit):
        db.save_spirit(sample_spirit)
        row = db.conn.execute("SELECT flavor_data FROM spirits").fetchone()
        parsed = json.loads(row[0])
        assert parsed["smoky"] == 40

    def test_save_spirit_without_flavor_data(self, db, sample_spirit):
        spirit = {**sample_spirit, "flavor_data": {}}
        assert db.save_spirit(spirit) is True

    def test_save_spirit_with_dict_flavor_data(self, db, sample_spirit):
        spirit = {**sample_spirit, "flavor_data": {"peaty": 60}}
        db.save_spirit(spirit)
        flavors = db.conn.execute("SELECT flavor_name FROM flavor_profiles").fetchall()
        assert len(flavors) == 1


class TestSQLiteStorageSaveSpirits:
    def test_save_multiple_spirits(self, db, sample_spirit):
        spirits = [
            {**sample_spirit, "url": "https://distiller.com/spirits/a", "name": "Spirit A"},
            {**sample_spirit, "url": "https://distiller.com/spirits/b", "name": "Spirit B"},
        ]
        count = db.save_spirits(spirits)
        assert count == 2
        assert db.count() == 2

    def test_save_spirits_deduplication(self, db, sample_spirit):
        spirits = [sample_spirit, sample_spirit]
        count = db.save_spirits(spirits)
        # upsert: 兩次都成功，但 DB 只有 1 筆
        assert count == 2
        assert db.count() == 1


class TestSQLiteStorageQuery:
    def test_spirit_exists_true(self, db, sample_spirit):
        db.save_spirit(sample_spirit)
        assert db.spirit_exists(sample_spirit["url"]) is True

    def test_spirit_exists_false(self, db):
        assert db.spirit_exists("https://distiller.com/spirits/nonexistent") is False

    def test_get_existing_urls(self, db, sample_spirit):
        db.save_spirit(sample_spirit)
        urls = db.get_existing_urls()
        assert sample_spirit["url"] in urls

    def test_get_all_spirits(self, db, sample_spirit):
        db.save_spirit(sample_spirit)
        all_data = db.get_all_spirits()
        assert len(all_data) == 1
        assert all_data[0]["name"] == "Highland Park 18 Year"

    def test_query_by_category(self, db, sample_spirit):
        db.save_spirit(sample_spirit)
        results = db.query_spirits(category="whiskey")
        assert len(results) == 1
        results_empty = db.query_spirits(category="gin")
        assert len(results_empty) == 0

    def test_query_by_min_score(self, db, sample_spirit):
        db.save_spirit(sample_spirit)
        results = db.query_spirits(min_score=95)
        assert len(results) == 1
        results_empty = db.query_spirits(min_score=100)
        assert len(results_empty) == 0

    def test_query_with_limit(self, db, sample_spirit):
        spirits = [
            {**sample_spirit, "url": f"https://distiller.com/spirits/{i}", "name": f"Spirit {i}"}
            for i in range(5)
        ]
        db.save_spirits(spirits)
        results = db.query_spirits(limit=3)
        assert len(results) == 3


class TestSQLiteStorageScrapeRuns:
    def test_record_and_finish_scrape_run(self, db):
        from datetime import datetime
        run_id = db.record_scrape_run(
            categories=["whiskey", "gin"],
            mode="test",
            started_at=datetime(2026, 1, 27, 10, 0, 0),
        )
        assert run_id > 0

        db.finish_scrape_run(run_id, total_scraped=5, total_failed=0)
        row = db.conn.execute(
            "SELECT status, total_scraped FROM scrape_runs WHERE id = ?", (run_id,)
        ).fetchone()
        assert row["status"] == "completed"
        assert row["total_scraped"] == 5


class TestSQLiteStorageExport:
    def test_to_dataframe(self, db, sample_spirit):
        db.save_spirit(sample_spirit)
        df = db.to_dataframe()
        assert len(df) == 1
        assert df.iloc[0]["name"] == "Highland Park 18 Year"

    def test_export_csv(self, db, sample_spirit, tmp_path):
        db.save_spirit(sample_spirit)
        out = str(tmp_path / "export.csv")
        assert db.export_csv(out) is True
        import pandas as pd
        df = pd.read_csv(out)
        assert len(df) == 1


# ---------------------------------------------------------------------------
# CSVStorage 測試
# ---------------------------------------------------------------------------

class TestCSVStorage:
    def test_save_spirit(self, csv_storage, sample_spirit):
        assert csv_storage.save_spirit(sample_spirit) is True
        assert len(csv_storage.get_all_spirits()) == 1

    def test_no_duplicate(self, csv_storage, sample_spirit):
        csv_storage.save_spirit(sample_spirit)
        result = csv_storage.save_spirit(sample_spirit)
        assert result is False
        assert len(csv_storage.get_all_spirits()) == 1

    def test_spirit_exists(self, csv_storage, sample_spirit):
        csv_storage.save_spirit(sample_spirit)
        assert csv_storage.spirit_exists(sample_spirit["url"]) is True
        assert csv_storage.spirit_exists("https://other.com") is False

    def test_get_existing_urls(self, csv_storage, sample_spirit):
        csv_storage.save_spirit(sample_spirit)
        assert sample_spirit["url"] in csv_storage.get_existing_urls()

    def test_flush_creates_file(self, csv_storage, sample_spirit):
        csv_storage.save_spirit(sample_spirit)
        assert csv_storage.flush() is True
        import os
        assert os.path.exists(csv_storage.filename)

    def test_flush_empty_returns_false(self, csv_storage):
        assert csv_storage.flush() is False

    def test_save_spirits(self, csv_storage, sample_spirit):
        spirits = [
            {**sample_spirit, "url": "https://distiller.com/spirits/x"},
            {**sample_spirit, "url": "https://distiller.com/spirits/y"},
        ]
        count = csv_storage.save_spirits(spirits)
        assert count == 2
