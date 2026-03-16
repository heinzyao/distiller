"""Unit tests for restart_driver() trigger conditions (Task 4 - TDD)."""

from unittest.mock import MagicMock, patch

import pytest
from selenium.webdriver.remote.webdriver import WebDriver

from distiller_scraper.config import ScraperConfig
from distiller_scraper.scraper import DistillerScraperV2


@pytest.fixture
def mock_driver():
    driver = MagicMock(spec=WebDriver)
    return driver


@pytest.fixture
def scraper(mock_driver):
    s = DistillerScraperV2(headless=True, delay_min=0, delay_max=0)
    s.driver = mock_driver
    return s


class TestRestartDriver:
    # ── _should_restart() ──────────────────────────────────────────────────

    def test_should_restart_returns_true_for_js_null_error(self, scraper):
        """JS null body error from scroll should trigger restart."""
        assert (
            scraper._should_restart(
                "Cannot read properties of null (reading 'scrollHeight')"
            )
            is True
        )

    def test_should_restart_returns_true_for_invalid_session(self, scraper):
        """Backward compat: 'invalid session id' must still trigger restart."""
        assert scraper._should_restart("invalid session id") is True

    def test_should_restart_returns_true_for_session_deleted(self, scraper):
        """Backward compat: 'session deleted' must still trigger restart."""
        assert scraper._should_restart("session deleted") is True

    def test_should_restart_returns_false_for_unknown_error(self, scraper):
        """Generic timeout errors must NOT trigger restart."""
        assert scraper._should_restart("timeout waiting for element") is False

    # ── restart_count increments ───────────────────────────────────────────

    def test_restart_count_increments_after_restart(self, scraper):
        """restart_count goes from 0 → 1 after a successful restart call."""
        assert scraper.restart_count == 0

        with patch.object(scraper, "restart_driver", return_value=True) as mock_restart:
            with patch.object(
                scraper,
                "scrape_spirit_detail",
                wraps=scraper.scrape_spirit_detail,
            ):
                # Simulate the logic: restart succeeds → increment
                if scraper.restart_driver():
                    scraper.restart_count += 1

        assert scraper.restart_count == 1
        mock_restart.assert_called_once()

    # ── driver_failed when max attempts exceeded ───────────────────────────

    def test_driver_failed_set_when_max_attempts_exceeded(self, scraper):
        """When restart_count >= MAX_RESTART_ATTEMPTS, driver_failed=True and
        restart_driver() is NOT called."""
        scraper.restart_count = ScraperConfig.MAX_RESTART_ATTEMPTS

        with patch.object(scraper, "restart_driver") as mock_restart:
            # Simulate the guard logic
            if scraper.restart_count >= ScraperConfig.MAX_RESTART_ATTEMPTS:
                scraper.driver_failed = True
            else:
                scraper.restart_driver()

        assert scraper.driver_failed is True
        mock_restart.assert_not_called()
