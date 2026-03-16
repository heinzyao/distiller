from unittest.mock import MagicMock

import pytest

from distiller_scraper.scraper import DistillerScraperV2


@pytest.fixture
def mock_driver():
    driver = MagicMock()
    driver.execute_script.return_value = 1000
    driver.get_log.return_value = []
    return driver


@pytest.fixture
def scraper(mock_driver):
    s = DistillerScraperV2(headless=True, delay_min=0, delay_max=0)
    s.driver = mock_driver
    return s


class TestRetryLogic:
    def test_page_retry_on_scroll_failure(self, scraper, mocker):
        mocker.patch("time.sleep")
        fetch = mocker.patch.object(
            scraper,
            "_fetch_spirit_urls",
            side_effect=[Exception("scroll failed"), ["u1", "u2"]],
        )
        mock_scrape = mocker.patch.object(
            scraper,
            "_scrape_urls",
            side_effect=lambda urls, category, results, max_spirits: results.extend(
                [{}, {}]
            ),
        )

        scraper.scrape_category_paginated("whiskey", max_spirits=2, use_styles=False)

        assert fetch.call_count == 2
        mock_scrape.assert_called_once()

    def test_page_retry_triggers_driver_restart(self, scraper, mocker):
        mocker.patch("time.sleep")
        fetch = mocker.patch.object(
            scraper,
            "_fetch_spirit_urls",
            side_effect=[
                Exception("invalid session id"),
                Exception("invalid session id"),
                [],
            ],
        )
        mocker.patch.object(scraper, "_scrape_urls")
        mocker.patch.object(scraper, "_should_restart", return_value=True)
        restart = mocker.patch.object(scraper, "restart_driver", return_value=True)

        scraper.scrape_category_paginated("whiskey", max_spirits=10, use_styles=False)

        assert restart.called
        assert fetch.call_count >= 2

    def test_page_retry_skips_after_max_retries(self, scraper, mocker):
        mocker.patch("time.sleep")
        mocker.patch.object(
            scraper,
            "_fetch_spirit_urls",
            side_effect=[Exception("boom"), Exception("boom")],
        )
        mocker.patch.object(scraper, "_should_restart", return_value=False)

        scraper.scrape_category_paginated("whiskey", max_spirits=10, use_styles=False)

        assert scraper.page_errors == 1

    def test_page_retry_doesnt_retry_on_clean_empty(self, scraper, mocker):
        mocker.patch("time.sleep")
        fetch = mocker.patch.object(scraper, "_fetch_spirit_urls", return_value=[])

        scraper.scrape_category_paginated("whiskey", max_spirits=10, use_styles=False)

        assert fetch.call_count == 1

    def test_page_retry_with_driver_failed_flag(self, scraper, mocker):
        mocker.patch("time.sleep")
        scraper.driver_failed = True
        fetch = mocker.patch.object(
            scraper,
            "_fetch_spirit_urls",
            side_effect=[Exception("scroll failed")],
        )

        scraper.scrape_category_paginated("whiskey", max_spirits=10, use_styles=False)

        assert fetch.call_count == 0
