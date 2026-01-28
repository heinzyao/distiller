"""
整合測試 - DistillerScraperV2 (Mock)
使用 Mock HTML 測試爬蟲流程，不需要真實網路連線

注意：這些測試需要導入 DistillerScraperV2，會觸發 selenium/webdriver-manager 導入。
如果 webdriver-manager 初始化緩慢，可以跳過這些測試。
"""

import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# 延遲導入 scraper 以避免在收集階段卡住
@pytest.fixture
def scraper_class():
    """延遲導入 DistillerScraperV2"""
    from distiller_scraper.scraper import DistillerScraperV2

    return DistillerScraperV2


class TestScraperInitialization:
    """測試爬蟲初始化"""

    def test_init_default_values(self, scraper_class):
        """測試預設值初始化"""
        scraper = scraper_class()
        assert scraper.headless is True
        assert scraper.delay_min == 2
        assert scraper.delay_max == 4
        assert scraper.driver is None
        assert scraper.spirits_data == []
        assert scraper.failed_urls == []
        assert scraper.seen_urls == set()

    def test_init_custom_values(self, scraper_class):
        """測試自訂值初始化"""
        scraper = scraper_class(
            headless=False,
            delay_min=1,
            delay_max=3,
        )
        assert scraper.headless is False
        assert scraper.delay_min == 1
        assert scraper.delay_max == 3


class TestExtractSpiritUrls:
    """測試從列表頁提取 URL"""

    def test_extract_urls_success(self, scraper_class, sample_search_results_soup):
        """測試成功提取 URL"""
        scraper = scraper_class()
        urls = scraper.extract_spirit_urls_from_list(sample_search_results_soup)

        assert len(urls) == 4
        assert "https://distiller.com/spirits/highland-park-18" in urls
        assert "https://distiller.com/spirits/macallan-18-sherry-oak" in urls
        assert "https://distiller.com/spirits/lagavulin-16" in urls

    def test_extract_urls_empty_page(self, scraper_class, empty_soup):
        """測試空頁面返回空列表"""
        scraper = scraper_class()
        urls = scraper.extract_spirit_urls_from_list(empty_soup)
        assert urls == []

    def test_extract_urls_relative_to_absolute(
        self, scraper_class, sample_search_results_soup
    ):
        """測試相對路徑轉換為絕對路徑"""
        scraper = scraper_class()
        urls = scraper.extract_spirit_urls_from_list(sample_search_results_soup)

        # 所有 URL 應該是完整的 https URL
        for url in urls:
            assert url.startswith("https://distiller.com")


class TestDataConversion:
    """測試資料轉換功能"""

    def test_to_dataframe_empty(self, scraper_class):
        """測試空資料轉換"""
        scraper = scraper_class()
        df = scraper.to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_to_dataframe_with_data(self, scraper_class):
        """測試有資料時的轉換"""
        scraper = scraper_class()
        scraper.spirits_data = [
            {
                "name": "Highland Park 18 Year",
                "spirit_type": "Single Malt",
                "brand": "Highland Park",
                "country": "Scotland",
                "expert_score": "99",
                "flavor_data": {"smoky": 40, "rich": 80},
            },
            {
                "name": "Macallan 18",
                "spirit_type": "Single Malt",
                "brand": "Macallan",
                "country": "Scotland",
                "expert_score": "97",
                "flavor_data": {"sweet": 70},
            },
        ]

        df = scraper.to_dataframe()
        assert len(df) == 2
        assert "name" in df.columns
        assert "flavor_data" in df.columns
        assert df.iloc[0]["name"] == "Highland Park 18 Year"

    def test_to_dataframe_flavor_json_serialization(self, scraper_class):
        """測試風味資料 JSON 序列化"""
        scraper = scraper_class()
        scraper.spirits_data = [
            {
                "name": "Test Spirit",
                "flavor_data": {"smoky": 40, "rich": 80},
            }
        ]

        df = scraper.to_dataframe()
        flavor_str = df.iloc[0]["flavor_data"]
        # 確認是 JSON 字串
        assert isinstance(flavor_str, str)
        # 確認可以解析回字典
        parsed = json.loads(flavor_str)
        assert parsed["smoky"] == 40


class TestStatistics:
    """測試統計功能"""

    def test_get_statistics_empty(self, scraper_class):
        """測試空資料統計"""
        scraper = scraper_class()
        stats = scraper.get_statistics()
        assert stats["總記錄數"] == 0

    def test_get_statistics_with_data(self, scraper_class):
        """測試有資料時的統計"""
        scraper = scraper_class()
        scraper.spirits_data = [
            {"name": "Spirit 1", "category": "whiskey", "expert_score": "99"},
            {"name": "Spirit 2", "category": "whiskey", "expert_score": "95"},
            {"name": "Spirit 3", "category": "gin", "expert_score": "N/A"},
        ]
        scraper.failed_urls = ["http://example.com/failed"]

        stats = scraper.get_statistics()
        assert stats["總記錄數"] == 3
        assert stats["失敗 URL 數"] == 1
        assert "類別分布" in stats
        assert stats["類別分布"]["whiskey"] == 2
        assert stats["類別分布"]["gin"] == 1


class TestDeduplication:
    """測試去重功能"""

    def test_seen_urls_tracking(self, scraper_class):
        """測試 URL 追蹤"""
        scraper = scraper_class()
        assert len(scraper.seen_urls) == 0

        scraper.seen_urls.add("https://distiller.com/spirits/test-1")
        scraper.seen_urls.add("https://distiller.com/spirits/test-2")

        assert len(scraper.seen_urls) == 2
        assert "https://distiller.com/spirits/test-1" in scraper.seen_urls


class TestScrapeSpirit:
    """測試爬取單個烈酒（使用 Mock）"""

    def test_scrape_spirit_skips_seen_url(self, scraper_class):
        """測試跳過已爬取的 URL"""
        scraper = scraper_class()
        scraper.seen_urls.add("https://distiller.com/spirits/test")

        result = scraper.scrape_spirit_detail("https://distiller.com/spirits/test")
        assert result is None

    def test_scrape_with_mock_driver(self, scraper_class, sample_spirit_detail_html):
        """測試使用 Mock driver 爬取"""
        scraper = scraper_class()

        # Mock driver
        mock_driver = MagicMock()
        mock_driver.page_source = sample_spirit_detail_html
        scraper.driver = mock_driver

        result = scraper.scrape_spirit_detail(
            "https://distiller.com/spirits/highland-park-18"
        )

        assert result is not None
        assert result["name"] == "Highland Park 18 Year"
        assert result["spirit_type"] == "Single Malt"
        assert result["expert_score"] == "99"
        assert result["url"] == "https://distiller.com/spirits/highland-park-18"

        # 確認 URL 已加入 seen_urls
        assert "https://distiller.com/spirits/highland-park-18" in scraper.seen_urls


class TestCSVSave:
    """測試 CSV 儲存功能"""

    def test_save_csv_no_data(self, scraper_class, tmp_path):
        """測試無資料時不儲存"""
        scraper = scraper_class()
        result = scraper.save_csv(str(tmp_path / "test.csv"))
        assert result is False

    def test_save_csv_success(self, scraper_class, tmp_path):
        """測試成功儲存 CSV"""
        scraper = scraper_class()
        scraper.spirits_data = [
            {
                "name": "Test Spirit",
                "spirit_type": "Single Malt",
                "brand": "Test Brand",
                "country": "Scotland",
                "expert_score": "95",
                "flavor_data": {"smoky": 40},
            }
        ]

        csv_path = tmp_path / "test_output.csv"
        result = scraper.save_csv(str(csv_path))

        assert result is True
        assert csv_path.exists()

        # 驗證 CSV 內容
        df = pd.read_csv(csv_path)
        assert len(df) == 1
        assert df.iloc[0]["name"] == "Test Spirit"


class TestRandomDelay:
    """測試隨機延遲功能"""

    @patch("time.sleep")
    def test_random_delay_uses_defaults(self, mock_sleep, scraper_class):
        """測試使用預設延遲範圍"""
        scraper = scraper_class(delay_min=2, delay_max=4)
        scraper.random_delay()

        mock_sleep.assert_called_once()
        delay = mock_sleep.call_args[0][0]
        assert 2 <= delay <= 4

    @patch("time.sleep")
    def test_random_delay_custom_range(self, mock_sleep, scraper_class):
        """測試自訂延遲範圍"""
        scraper = scraper_class()
        scraper.random_delay(min_sec=1, max_sec=2)

        mock_sleep.assert_called_once()
        delay = mock_sleep.call_args[0][0]
        assert 1 <= delay <= 2
