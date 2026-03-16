"""
健康檢查方法單元測試
TDD: RED → GREEN → REFACTOR
"""

from unittest.mock import MagicMock, patch

import pytest
from selenium.common.exceptions import JavascriptException, TimeoutException

from distiller_scraper.config import ScraperConfig
from distiller_scraper.scraper import DistillerScraperV2


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_driver():
    driver = MagicMock()
    driver.execute_script.return_value = 1000  # valid scrollHeight
    return driver


@pytest.fixture
def scraper(mock_driver):
    s = DistillerScraperV2(headless=True, delay_min=0, delay_max=0)
    s.driver = mock_driver
    yield s
    # cleanup: no real driver to quit


# ---------------------------------------------------------------------------
# TestHealthCheck
# ---------------------------------------------------------------------------


class TestHealthCheck:
    def test_health_check_passes_on_valid_page(self, scraper, mock_driver):
        """Mock driver returns valid scroll height → _health_check returns True."""
        mock_driver.execute_script.return_value = 1000

        result = scraper._health_check()

        assert result is True

    def test_health_check_fails_on_null_body(self, scraper, mock_driver):
        """Mock driver where execute_script raises JavascriptException → returns False."""
        mock_driver.execute_script.side_effect = JavascriptException(
            "Cannot read properties of null"
        )

        result = scraper._health_check()

        assert result is False

    def test_health_check_fails_on_timeout(self, scraper, mock_driver):
        """Mock driver where get() raises TimeoutException → returns False."""
        mock_driver.get.side_effect = TimeoutException("page load timed out")

        result = scraper._health_check()

        assert result is False

    def test_health_check_blocks_scrape_on_failure(self, scraper):
        """When _health_check() returns False, scrape() returns False without calling scrape_category()."""
        with (
            patch.object(scraper, "start_driver", return_value=True),
            patch.object(scraper, "_health_check", return_value=False),
            patch.object(scraper, "scrape_category") as mock_scrape_category,
        ):
            result = scraper.scrape(
                categories=["whiskey"],
                max_per_category=5,
                use_styles=False,
                use_pagination=False,
            )

        assert result is False
        mock_scrape_category.assert_not_called()

    def test_health_check_uses_config_timeout(self, scraper, mock_driver):
        """Health check uses ScraperConfig.HEALTH_CHECK_TIMEOUT (not a hardcoded value)."""
        called_timeouts = []
        original_set_page_load_timeout = mock_driver.set_page_load_timeout

        def capture_timeout(t):
            called_timeouts.append(t)
            return original_set_page_load_timeout(t)

        mock_driver.set_page_load_timeout.side_effect = capture_timeout

        scraper._health_check()

        # The method must reference ScraperConfig.HEALTH_CHECK_TIMEOUT
        assert ScraperConfig.HEALTH_CHECK_TIMEOUT in called_timeouts, (
            f"Expected HEALTH_CHECK_TIMEOUT={ScraperConfig.HEALTH_CHECK_TIMEOUT} "
            f"to be passed to set_page_load_timeout, got: {called_timeouts}"
        )
