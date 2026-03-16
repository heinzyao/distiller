from unittest.mock import MagicMock, patch

import logging

import pytest
from selenium.common.exceptions import JavascriptException
from selenium.webdriver.remote.webdriver import WebDriver

from distiller_scraper.config import ScraperConfig
from distiller_scraper.scraper import DistillerScraperV2


@pytest.fixture
def mock_driver():
    driver = MagicMock(spec=WebDriver)
    driver.execute_script.return_value = 1000
    return driver


@pytest.fixture
def scraper(mock_driver):
    s = DistillerScraperV2(headless=True, delay_min=0, delay_max=0)
    s.driver = mock_driver
    return s


class TestScrollPage:
    def _make_execute_script(self, outcomes):
        heights = iter(outcomes)

        def _execute_script(script):
            if script == "return document.body.scrollHeight":
                value = next(heights)
                if isinstance(value, Exception):
                    raise value
                return value
            return None

        return _execute_script

    def test_scroll_page_handles_null_body(self, scraper, mock_driver, caplog):
        mock_driver.execute_script.side_effect = JavascriptException(
            "Cannot read properties of null (reading 'scrollHeight')"
        )

        with patch("time.sleep"):
            with caplog.at_level(logging.WARNING, logger="distiller_scraper.scraper"):
                scraper.scroll_page()

        assert any("scrollHeight" in record.message for record in caplog.records)

    def test_scroll_page_retries_on_null_body(self, scraper, mock_driver):
        mock_driver.execute_script.side_effect = self._make_execute_script(
            [
                JavascriptException(
                    "Cannot read properties of null (reading 'scrollHeight')"
                ),
                JavascriptException(
                    "Cannot read properties of null (reading 'scrollHeight')"
                ),
                1000,
                1000,
            ]
        )

        with patch("time.sleep"):
            scraper.scroll_page()

        assert scraper.page_errors == 0

    def test_scroll_page_gives_up_after_max_retries(self, scraper, mock_driver, caplog):
        mock_driver.execute_script.side_effect = JavascriptException(
            "Cannot read properties of null (reading 'scrollHeight')"
        )

        with patch("time.sleep"):
            with caplog.at_level(logging.ERROR, logger="distiller_scraper.scraper"):
                scraper.scroll_page()

        height_calls = [
            call
            for call in mock_driver.execute_script.call_args_list
            if call.args and call.args[0] == "return document.body.scrollHeight"
        ]
        assert len(height_calls) == ScraperConfig.MAX_SCROLL_RETRIES
        assert scraper.page_errors == 1
        assert any("scrollHeight" in record.message for record in caplog.records)

    def test_scroll_page_normal_operation_unchanged(self, scraper, mock_driver):
        mock_driver.execute_script.side_effect = self._make_execute_script(
            [1000, 2000, 2000]
        )

        with patch("time.sleep"):
            scraper.scroll_page()

        assert scraper.page_errors == 0
