"""
端到端測試 - DistillerScraperV2 (Live)
實際連線到 Distiller.com 進行小規模爬取測試

注意：
- 這些測試需要網路連線
- 這些測試較慢，標記為 @pytest.mark.slow 和 @pytest.mark.network
- 預設情況下 CI 可能會跳過這些測試
"""

import pytest

from distiller_scraper.scraper import DistillerScraperV2
from distiller_scraper.selectors import SearchURLBuilder


@pytest.mark.slow
@pytest.mark.network
class TestLiveWebDriver:
    """測試實際 WebDriver 啟動"""

    def test_start_and_close_driver(self):
        """測試啟動和關閉 WebDriver"""
        scraper = DistillerScraperV2(headless=True)

        # 啟動 driver
        result = scraper.start_driver()
        assert result is True
        assert scraper.driver is not None

        # 關閉 driver
        scraper.close_driver()
        # driver 應該已被 quit，但屬性可能仍存在


@pytest.mark.slow
@pytest.mark.network
class TestLiveScraping:
    """測試實際爬取功能"""

    @pytest.fixture
    def scraper(self):
        """建立爬蟲實例"""
        scraper = DistillerScraperV2(headless=True, delay_min=2, delay_max=3)
        yield scraper
        # 清理
        if scraper.driver:
            scraper.close_driver()

    def test_scrape_single_spirit(self, scraper):
        """測試爬取單個烈酒詳情"""
        # 啟動 driver
        assert scraper.start_driver() is True

        # 爬取一個已知的烈酒頁面
        url = "https://distiller.com/spirits/highland-park-18"
        result = scraper.scrape_spirit_detail(url)

        # 驗證結果
        assert result is not None
        assert result["name"] != "N/A"
        assert result["url"] == url

        # 確認基本欄位存在
        assert "spirit_type" in result
        assert "brand" in result
        assert "country" in result

    def test_scrape_search_results_page(self, scraper):
        """測試爬取搜尋結果頁"""
        assert scraper.start_driver() is True

        # 載入搜尋頁面
        search_url = SearchURLBuilder.build_search_url(
            category="whiskey",
            sort="distiller_score",
        )

        scraper.driver.get(search_url)

        # 等待頁面載入
        import time

        time.sleep(3)

        # 解析頁面
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(scraper.driver.page_source, "html.parser")

        # 提取 URL
        urls = scraper.extract_spirit_urls_from_list(soup)

        # 應該找到至少一些結果
        assert len(urls) > 0
        # 所有 URL 應該是有效的 Distiller URL
        for url in urls:
            assert "distiller.com/spirits/" in url


@pytest.mark.slow
@pytest.mark.network
class TestLiveMiniScrape:
    """測試小規模完整爬取流程"""

    def test_mini_scrape_whiskey(self):
        """測試爬取少量威士忌資料"""
        scraper = DistillerScraperV2(headless=True)

        try:
            # 只爬取 2 筆
            scraper.scrape(
                categories=["whiskey"],
                max_per_category=2,
                use_styles=False,
            )

            # 驗證結果
            assert len(scraper.spirits_data) > 0
            assert len(scraper.spirits_data) <= 2

            # 驗證資料完整性
            for spirit in scraper.spirits_data:
                assert spirit["name"] != "N/A"
                assert "url" in spirit
                assert spirit["category"] == "whiskey"

        finally:
            scraper.close_driver()

    def test_mini_scrape_data_quality(self):
        """測試爬取資料品質"""
        scraper = DistillerScraperV2(headless=True)

        try:
            scraper.scrape(
                categories=["whiskey"],
                max_per_category=1,
                use_styles=False,
            )

            if scraper.spirits_data:
                spirit = scraper.spirits_data[0]

                # 驗證必要欄位
                required_fields = [
                    "name",
                    "spirit_type",
                    "brand",
                    "country",
                    "url",
                    "category",
                ]
                for field in required_fields:
                    assert field in spirit, f"Missing field: {field}"

                # 驗證風味資料格式
                if "flavor_data" in spirit and spirit["flavor_data"]:
                    assert isinstance(spirit["flavor_data"], dict)

        finally:
            scraper.close_driver()


@pytest.mark.slow
@pytest.mark.network
class TestLiveStatistics:
    """測試實際爬取後的統計"""

    def test_statistics_after_scrape(self):
        """測試爬取後的統計功能"""
        scraper = DistillerScraperV2(headless=True)

        try:
            scraper.scrape(
                categories=["whiskey"],
                max_per_category=2,
                use_styles=False,
            )

            stats = scraper.get_statistics()

            assert "總記錄數" in stats
            assert stats["總記錄數"] >= 0
            assert "失敗 URL 數" in stats
            assert "類別分布" in stats
            assert "欄位有效率" in stats

        finally:
            scraper.close_driver()
