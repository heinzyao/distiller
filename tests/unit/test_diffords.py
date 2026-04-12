"""
Difford's Guide 爬蟲模組單元測試

測試策略：
- 使用真實的 HTML 片段（從實際頁面提取）測試解析邏輯
- DiffordsStorage 使用記憶體 DB（`:memory:`）
- DiffordsGuideScraper 使用 mock requests.Session 避免真實 HTTP 請求
"""

import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from distiller_scraper.diffords_selectors import DiffordsExtractor
from distiller_scraper.diffords_storage import DiffordsStorage
from distiller_scraper.diffords_scraper import (
    DiffordsGuideScraper,
    SitemapEntry,
)

# ── 測試固定資料 ──────────────────────────────────────────────────────

SAMPLE_JSON_LD = {
    "@context": "https://schema.org",
    "@type": "Recipe",
    "name": "Negroni",
    "description": "A classic Italian cocktail.",
    "recipeIngredient": [
        "30 ml Gin",
        "30 ml Red bitter liqueur",
        "30 ml Rosso/sweet vermouth",
    ],
    "recipeInstructions": [
        {"@type": "HowToStep", "name": "STIR", "text": "STIR all ingredients with ice."},
        {"@type": "HowToStep", "name": "STRAIN", "text": "STRAIN into glass."},
    ],
    "keywords": ["Classic/vintage", "Bittersweet (e.g. Negroni)"],
    "aggregateRating": {
        "@type": "aggregateRating",
        "ratingValue": "4.5",
        "ratingCount": "500",
    },
    "nutrition": {"@type": "NutritionInformation", "calories": "200 calories"},
    "totalTime": "PT03M0S",
    "datePublished": "2020-01-01 00:00:00",
    "url": "https://www.diffordsguide.com/cocktails/recipe/1254/negroni",
}

SAMPLE_HTML = f"""
<html><body>
<script type="application/ld+json">{json.dumps(SAMPLE_JSON_LD)}</script>
<h3 class="m-0">Glass:</h3>
<p>Photographed in a Old Fashioned Glass</p>
<h3 class="m-0">Garnish:</h3>
<p>Orange peel twist</p>
<h3 class="m-0">Prepare:</h3>
<p>Chill an Old Fashioned Glass.</p>
<h3 class="m-0">How to make:</h3>
<p>STIR all ingredients with ice. STRAIN into glass.</p>
<h3 class="m-0">Review:</h3>
<p>The iconic Italian aperitivo.</p>
<h3 class="m-0">History:</h3>
<p>Created by Count Negroni in Florence, 1919.</p>
<table class="legacy-ingredients-table">
  <tbody>
    <tr><td>30 ml</td><td>Tanqueray Gin</td></tr>
    <tr><td>30 ml</td><td>Campari</td></tr>
    <tr><td>30 ml</td><td>Martini Rosso</td></tr>
  </tbody>
</table>
<ul><li>16.14% alc./vol. (32.28° proof)</li></ul>
</body></html>
"""

SAMPLE_SITEMAP_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.diffordsguide.com/cocktails/recipe/1/abacaxi-ricaco</loc>
    <lastmod>2024-11-01</lastmod>
  </url>
  <url>
    <loc>https://www.diffordsguide.com/cocktails/recipe/3/abbey</loc>
    <lastmod>2025-01-15</lastmod>
  </url>
  <url>
    <loc>https://www.diffordsguide.com/cocktails/recipe/1254/negroni</loc>
    <lastmod>2026-04-01</lastmod>
  </url>
</urlset>
"""


# ── DiffordsExtractor 測試 ────────────────────────────────────────────

class TestDiffordsExtractor:

    def test_extract_json_ld(self):
        ld = DiffordsExtractor.extract_json_ld(SAMPLE_HTML)
        assert ld is not None
        assert ld["@type"] == "Recipe"
        assert ld["name"] == "Negroni"

    def test_extract_json_ld_missing(self):
        assert DiffordsExtractor.extract_json_ld("<html><body></body></html>") is None

    def test_extract_json_ld_non_recipe(self):
        html = '<script type="application/ld+json">{"@type": "Person"}</script>'
        assert DiffordsExtractor.extract_json_ld(html) is None

    def test_extract_all_basic_fields(self):
        data = DiffordsExtractor.extract_all(SAMPLE_HTML)
        assert data is not None
        assert data["name"] == "Negroni"
        assert data["rating_value"] == 4.5
        assert data["rating_count"] == 500
        assert data["calories"] == 200
        assert data["prep_time_minutes"] == 3

    def test_extract_all_html_fields(self):
        data = DiffordsExtractor.extract_all(SAMPLE_HTML)
        assert data["glassware"] == "Old Fashioned Glass"  # 移除 "Photographed in a " 前綴
        assert data["garnish"] == "Orange peel twist"
        assert data["review"] == "The iconic Italian aperitivo."
        assert data["history"] == "Created by Count Negroni in Florence, 1919."

    def test_extract_all_tags(self):
        data = DiffordsExtractor.extract_all(SAMPLE_HTML)
        assert "Classic/vintage" in data["tags"]
        assert "Bittersweet (e.g. Negroni)" in data["tags"]

    def test_extract_ingredients_json_ld(self):
        ings = DiffordsExtractor.parse_ingredients_json_ld([
            "30 ml Gin",
            "30 ml Red bitter liqueur",
            "30 ml Rosso/sweet vermouth",
        ])
        assert len(ings) == 3
        assert ings[0]["amount"] == "30 ml"
        assert ings[0]["item"] == "Gin"
        assert ings[1]["sort_order"] == 2

    def test_extract_ingredients_json_ld_no_unit(self):
        ings = DiffordsExtractor.parse_ingredients_json_ld(["Orange peel"])
        assert len(ings) == 1
        assert ings[0]["item"] == "Orange peel"
        assert ings[0]["amount"] == ""

    def test_extract_ingredients_html(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(SAMPLE_HTML, "html.parser")
        ings = DiffordsExtractor.extract_ingredients_html(soup)
        assert len(ings) == 3
        assert ings[0]["amount"] == "30 ml"
        assert ings[0]["item"] == "Tanqueray Gin"
        assert ings[2]["item"] == "Martini Rosso"

    def test_extract_abv(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(SAMPLE_HTML, "html.parser")
        abv = DiffordsExtractor.extract_abv(soup)
        assert abv == 16.14

    def test_extract_prep_time_minutes(self):
        assert DiffordsExtractor.extract_prep_time_minutes({"totalTime": "PT03M0S"}) == 3
        assert DiffordsExtractor.extract_prep_time_minutes({"totalTime": "PT1H30M"}) == 90
        assert DiffordsExtractor.extract_prep_time_minutes({}) is None

    def test_extract_calories(self):
        assert DiffordsExtractor.extract_calories(
            {"nutrition": {"calories": "200 calories"}}
        ) == 200
        assert DiffordsExtractor.extract_calories({}) is None


# ── DiffordsStorage 測試 ─────────────────────────────────────────────

@pytest.fixture
def storage(tmp_path):
    db = DiffordsStorage(str(tmp_path / "test.db"))
    yield db
    db.close()


SAMPLE_COCKTAIL = {
    "url": "https://www.diffordsguide.com/cocktails/recipe/1254/negroni",
    "lastmod": "2026-04-01",
    "name": "Negroni",
    "description": "A classic Italian cocktail.",
    "glassware": "Old Fashioned Glass",
    "garnish": "Orange peel twist",
    "prepare": "Chill glass.",
    "instructions": "STIR all ingredients with ice.",
    "review": "The iconic Italian aperitivo.",
    "history": "Created by Count Negroni in Florence, 1919.",
    "tags": ["Classic/vintage", "Bittersweet"],
    "rating_value": 4.5,
    "rating_count": 500,
    "calories": 200,
    "prep_time_minutes": 3,
    "abv": 16.14,
    "date_published": "2020-01-01",
    "ingredients_html": [
        {"sort_order": 1, "amount": "30 ml", "item": "Tanqueray Gin"},
        {"sort_order": 2, "amount": "30 ml", "item": "Campari"},
        {"sort_order": 3, "amount": "30 ml", "item": "Martini Rosso"},
    ],
    "ingredients_generic": [
        {"sort_order": 1, "amount": "30 ml", "item": "Gin"},
        {"sort_order": 2, "amount": "30 ml", "item": "Red bitter liqueur"},
        {"sort_order": 3, "amount": "30 ml", "item": "Rosso/sweet vermouth"},
    ],
}


class TestDiffordsStorage:

    def test_save_and_retrieve(self, storage):
        assert storage.save_cocktail(SAMPLE_COCKTAIL)
        result = storage.get_cocktail_by_name("Negroni")
        assert result is not None
        assert result["name"] == "Negroni"
        assert result["rating_value"] == 4.5
        assert result["glassware"] == "Old Fashioned Glass"

    def test_ingredients_saved(self, storage):
        storage.save_cocktail(SAMPLE_COCKTAIL)
        result = storage.get_cocktail_by_name("Negroni")
        assert len(result["ingredients"]) == 3
        assert result["ingredients"][0]["item"] == "Tanqueray Gin"
        assert result["ingredients"][0]["item_generic"] == "Gin"

    def test_upsert_updates_existing(self, storage):
        storage.save_cocktail(SAMPLE_COCKTAIL)
        updated = {**SAMPLE_COCKTAIL, "rating_value": 4.8, "rating_count": 600}
        storage.save_cocktail(updated)
        result = storage.get_cocktail_by_name("Negroni")
        assert result["rating_value"] == 4.8
        assert result["rating_count"] == 600

    def test_upsert_preserves_id(self, storage):
        storage.save_cocktail(SAMPLE_COCKTAIL)
        r1 = storage.get_cocktail_by_name("Negroni")
        storage.save_cocktail(SAMPLE_COCKTAIL)
        r2 = storage.get_cocktail_by_name("Negroni")
        assert r1["id"] == r2["id"]

    def test_tags_deserialized(self, storage):
        storage.save_cocktail(SAMPLE_COCKTAIL)
        result = storage.get_cocktail_by_name("Negroni")
        tags = result["tags"]
        assert isinstance(tags, list)
        assert "Classic/vintage" in tags

    def test_get_existing_urls(self, storage):
        storage.save_cocktail(SAMPLE_COCKTAIL)
        urls = storage.get_existing_urls()
        assert SAMPLE_COCKTAIL["url"] in urls

    def test_get_url_lastmod_map(self, storage):
        storage.save_cocktail(SAMPLE_COCKTAIL)
        lm = storage.get_url_lastmod_map()
        assert lm[SAMPLE_COCKTAIL["url"]] == "2026-04-01"

    def test_search_cocktails(self, storage):
        storage.save_cocktail(SAMPLE_COCKTAIL)
        results = storage.search_cocktails("Negr")
        assert len(results) == 1
        assert results[0]["name"] == "Negroni"

    def test_search_cocktails_no_match(self, storage):
        storage.save_cocktail(SAMPLE_COCKTAIL)
        results = storage.search_cocktails("XYZ_NOT_EXIST")
        assert results == []

    def test_get_top_rated(self, storage):
        storage.save_cocktail(SAMPLE_COCKTAIL)
        results = storage.get_top_rated(limit=5)
        assert len(results) == 1

    def test_scrape_run_lifecycle(self, storage):
        run_id = storage.record_scrape_run("incremental")
        assert run_id > 0
        storage.finish_scrape_run(run_id, 10, 50, 2, "completed")
        last = storage.get_last_successful_run()
        assert last is not None

    def test_should_skip_run_no_history(self, storage):
        skip, _ = storage.should_skip_run()
        assert not skip

    def test_should_skip_run_recent(self, storage):
        run_id = storage.record_scrape_run("incremental")
        storage.finish_scrape_run(run_id, 10, 0, 0, "completed")
        skip, last = storage.should_skip_run(window_hours=168)
        assert skip
        assert last != ""

    def test_get_stats(self, storage):
        storage.save_cocktail(SAMPLE_COCKTAIL)
        stats = storage.get_stats()
        assert stats["總雞尾酒數"] == 1
        assert stats["平均評分"] == 4.5

    def test_ingredients_updated_on_upsert(self, storage):
        storage.save_cocktail(SAMPLE_COCKTAIL)
        # 更新食材
        updated = {
            **SAMPLE_COCKTAIL,
            "ingredients_html": [
                {"sort_order": 1, "amount": "45 ml", "item": "Beefeater Gin"},
            ],
            "ingredients_generic": [
                {"sort_order": 1, "amount": "45 ml", "item": "Gin"},
            ],
        }
        storage.save_cocktail(updated)
        result = storage.get_cocktail_by_name("Negroni")
        assert len(result["ingredients"]) == 1
        assert result["ingredients"][0]["item"] == "Beefeater Gin"
        assert result["ingredients"][0]["amount"] == "45 ml"


# ── DiffordsGuideScraper 測試 ─────────────────────────────────────────

class TestDiffordsGuideScraper:

    def test_parse_sitemap(self, tmp_path):
        with patch("distiller_scraper.diffords_scraper._build_session") as mock_sess_fn:
            mock_session = MagicMock()
            mock_resp = MagicMock()
            mock_resp.content = SAMPLE_SITEMAP_XML
            mock_resp.raise_for_status = MagicMock()
            mock_session.get.return_value = mock_resp
            mock_sess_fn.return_value = mock_session

            scraper = DiffordsGuideScraper()
            entries = scraper.parse_sitemap()

        assert len(entries) == 3
        assert entries[0].cocktail_id == 1
        assert entries[0].slug == "abacaxi-ricaco"
        assert entries[2].url == "https://www.diffordsguide.com/cocktails/recipe/1254/negroni"
        assert entries[2].lastmod == "2026-04-01"

    def test_should_skip_new_url(self, tmp_path):
        scraper = DiffordsGuideScraper()
        entry = SitemapEntry(1, "test", "https://example.com/1", "2026-01-01")
        assert not scraper._should_skip(entry, incremental=True)

    def test_should_skip_existing_same_lastmod(self):
        scraper = DiffordsGuideScraper()
        url = "https://example.com/1"
        scraper.seen_urls.add(url)
        scraper.lastmod_map[url] = "2026-01-01"
        entry = SitemapEntry(1, "test", url, "2026-01-01")
        assert scraper._should_skip(entry, incremental=True)

    def test_should_not_skip_newer_lastmod(self):
        scraper = DiffordsGuideScraper()
        url = "https://example.com/1"
        scraper.seen_urls.add(url)
        scraper.lastmod_map[url] = "2025-01-01"
        entry = SitemapEntry(1, "test", url, "2026-04-01")
        assert not scraper._should_skip(entry, incremental=True)

    def test_should_not_skip_when_not_incremental(self):
        scraper = DiffordsGuideScraper()
        url = "https://example.com/1"
        scraper.seen_urls.add(url)
        scraper.lastmod_map[url] = "2026-04-01"
        entry = SitemapEntry(1, "test", url, "2026-04-01")
        assert not scraper._should_skip(entry, incremental=False)

    def test_scrape_test_mode(self, tmp_path):
        storage = DiffordsStorage(str(tmp_path / "test.db"))

        with patch("distiller_scraper.diffords_scraper._build_session") as mock_sess_fn:
            mock_session = MagicMock()
            mock_sitemap_resp = MagicMock()
            mock_sitemap_resp.content = SAMPLE_SITEMAP_XML
            mock_sitemap_resp.raise_for_status = MagicMock()

            mock_page_resp = MagicMock()
            mock_page_resp.text = SAMPLE_HTML
            mock_page_resp.raise_for_status = MagicMock()

            mock_session.get.side_effect = [mock_sitemap_resp] + [mock_page_resp] * 10
            mock_sess_fn.return_value = mock_session

            with patch("time.sleep"):  # 跳過延遲
                scraper = DiffordsGuideScraper(storage=storage)
                ok = scraper.scrape(max_recipes=2, incremental=False)

        assert ok
        assert scraper.stats.scraped == 2
        storage.close()

    def test_fetch_recipe_failure(self):
        import requests as req
        scraper = DiffordsGuideScraper()
        with patch.object(scraper.session, "get", side_effect=req.RequestException("Network error")):
            result = scraper._fetch_recipe("https://example.com/fail")
        assert result is None

    def test_get_statistics(self):
        scraper = DiffordsGuideScraper()
        scraper.stats.scraped = 10
        scraper.stats.skipped = 50
        scraper.stats.failed = 2
        stats = scraper.get_statistics()
        assert stats["爬取新增"] == 10
        assert stats["跳過（已是最新）"] == 50
        assert stats["失敗"] == 2
