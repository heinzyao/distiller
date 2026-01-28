"""
單元測試 - ScraperConfig
測試爬蟲配置常數
"""

import pytest

from distiller_scraper.config import ScraperConfig


class TestScraperConfigBrowser:
    """測試瀏覽器相關配置"""

    def test_headless_default(self):
        """確認預設為 headless 模式"""
        assert ScraperConfig.HEADLESS is True

    def test_window_size_format(self):
        """確認視窗大小格式正確"""
        assert "," in ScraperConfig.WINDOW_SIZE
        width, height = ScraperConfig.WINDOW_SIZE.split(",")
        assert width.isdigit()
        assert height.isdigit()

    def test_timeouts_positive(self):
        """確認超時設定為正數"""
        assert ScraperConfig.PAGE_LOAD_TIMEOUT > 0
        assert ScraperConfig.ELEMENT_WAIT_TIMEOUT > 0


class TestScraperConfigDelays:
    """測試延遲相關配置"""

    def test_delay_range_valid(self):
        """確認延遲範圍有效"""
        assert ScraperConfig.DELAY_MIN > 0
        assert ScraperConfig.DELAY_MAX > ScraperConfig.DELAY_MIN

    def test_category_delay_reasonable(self):
        """確認類別間延遲合理"""
        assert ScraperConfig.CATEGORY_DELAY >= 5

    def test_scroll_delay_positive(self):
        """確認滾動延遲為正數"""
        assert ScraperConfig.SCROLL_DELAY > 0

    def test_initial_page_delay_positive(self):
        """確認初始頁面延遲為正數"""
        assert ScraperConfig.INITIAL_PAGE_DELAY > 0


class TestScraperConfigLimits:
    """測試爬取限制配置"""

    def test_max_spirits_positive(self):
        """確認最大爬取數為正數"""
        assert ScraperConfig.MAX_SPIRITS_PER_CATEGORY > 0

    def test_max_scroll_attempts_positive(self):
        """確認最大滾動次數為正數"""
        assert ScraperConfig.MAX_SCROLL_ATTEMPTS > 0

    def test_max_retries_positive(self):
        """確認最大重試次數為正數"""
        assert ScraperConfig.MAX_RETRIES > 0


class TestScraperConfigCategories:
    """測試類別配置"""

    def test_categories_not_empty(self):
        """確認類別列表不為空"""
        assert len(ScraperConfig.CATEGORIES) > 0

    def test_categories_are_strings(self):
        """確認類別都是字串"""
        for category in ScraperConfig.CATEGORIES:
            assert isinstance(category, str)
            assert len(category) > 0

    @pytest.mark.parametrize(
        "expected_category",
        [
            "whiskey",
            "gin",
            "rum",
            "vodka",
        ],
    )
    def test_essential_categories_present(self, expected_category):
        """確認必要類別存在"""
        assert expected_category in ScraperConfig.CATEGORIES


class TestScraperConfigStyles:
    """測試風格配置"""

    def test_whiskey_styles_format(self):
        """確認威士忌風格格式正確"""
        assert len(ScraperConfig.WHISKEY_STYLES) > 0
        for style_id, style_name in ScraperConfig.WHISKEY_STYLES:
            assert isinstance(style_id, str)
            assert isinstance(style_name, str)
            assert style_id.isdigit()

    def test_gin_styles_format(self):
        """確認琴酒風格格式正確"""
        assert len(ScraperConfig.GIN_STYLES) > 0
        for style_id, style_name in ScraperConfig.GIN_STYLES:
            assert isinstance(style_id, str)
            assert isinstance(style_name, str)

    def test_rum_styles_format(self):
        """確認蘭姆酒風格格式正確"""
        assert len(ScraperConfig.RUM_STYLES) > 0
        for style_id, style_name in ScraperConfig.RUM_STYLES:
            assert isinstance(style_id, str)
            assert isinstance(style_name, str)

    def test_vodka_styles_format(self):
        """確認伏特加風格格式正確"""
        assert len(ScraperConfig.VODKA_STYLES) > 0
        for style_id, style_name in ScraperConfig.VODKA_STYLES:
            assert isinstance(style_id, str)
            assert isinstance(style_name, str)


class TestScraperConfigCountries:
    """測試國家配置"""

    def test_countries_format(self):
        """確認國家格式正確"""
        assert len(ScraperConfig.TOP_COUNTRIES) > 0
        for country_id, country_name in ScraperConfig.TOP_COUNTRIES:
            assert isinstance(country_id, str)
            assert isinstance(country_name, str)
            assert country_id.isdigit()

    @pytest.mark.parametrize(
        "expected_country",
        [
            "Scotland",
            "USA",
            "Japan",
            "Ireland",
        ],
    )
    def test_major_countries_present(self, expected_country):
        """確認主要產地國家存在"""
        countries = [name for _, name in ScraperConfig.TOP_COUNTRIES]
        assert expected_country in countries


class TestScraperConfigOutput:
    """測試輸出配置"""

    def test_user_agent_defined(self):
        """確認 User-Agent 已定義"""
        assert len(ScraperConfig.USER_AGENT) > 0
        assert "Mozilla" in ScraperConfig.USER_AGENT

    def test_output_encoding(self):
        """確認輸出編碼"""
        assert ScraperConfig.OUTPUT_ENCODING in ["utf-8", "utf-8-sig"]
