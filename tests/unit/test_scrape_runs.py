"""
scrape_runs 整合測試
驗證 run.py 在每次爬取時正確呼叫 record_scrape_run() 與 finish_scrape_run()
"""

from unittest.mock import MagicMock, patch

import pytest

from distiller_scraper.storage import SQLiteStorage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sqlite_mock(run_id: int = 42) -> MagicMock:
    """建立 SQLiteStorage mock，record_scrape_run 回傳指定 run_id。"""
    mock = MagicMock(spec=SQLiteStorage)
    mock.record_scrape_run.return_value = run_id
    return mock


def _make_scraper_mock(
    spirits: int = 3, failed: int = 0, page_errors: int = 0
) -> MagicMock:
    """建立 DistillerScraperV2 mock，預設爬取成功。"""
    mock = MagicMock()
    mock.scrape.return_value = True
    mock.spirits_data = [object()] * spirits
    mock.failed_urls = [object()] * failed
    mock.page_errors = page_errors
    mock.get_statistics.return_value = {}
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestScrapeRuns:
    """驗證 run.py 三個 run function 的 scrape_run 追蹤邏輯。"""

    # ------------------------------------------------------------------
    # Test 1: record_scrape_run 在爬取開始時被呼叫
    # ------------------------------------------------------------------

    def test_scrape_run_recorded_on_start(self):
        """SQLiteStorage 時，run_test 應呼叫 record_scrape_run(categories, mode)。"""
        import run as run_module

        storage_mock = _make_sqlite_mock(run_id=10)
        scraper_mock = _make_scraper_mock()

        with (
            patch.object(
                run_module, "_build_storage", return_value=(storage_mock, None)
            ),
            patch.object(run_module, "_build_api_client", return_value=None),
            patch("run.DistillerScraperV2", return_value=scraper_mock),
        ):
            run_module.run_test(output="sqlite", db_path=":memory:")

        storage_mock.record_scrape_run.assert_called_once()
        call_kwargs = storage_mock.record_scrape_run.call_args
        # categories 應包含 "whiskey"，mode 應為 "test"
        categories = call_kwargs.kwargs.get("categories") or call_kwargs.args[0]
        mode = call_kwargs.kwargs.get("mode") or call_kwargs.args[1]
        assert "whiskey" in categories
        assert mode == "test"

    # ------------------------------------------------------------------
    # Test 2: finish_scrape_run 在成功時以 status='completed' 呼叫
    # ------------------------------------------------------------------

    def test_scrape_run_finished_on_success(self):
        """爬取成功且無錯誤時，finish_scrape_run 應以 status='completed' 呼叫。"""
        import run as run_module

        storage_mock = _make_sqlite_mock(run_id=42)
        scraper_mock = _make_scraper_mock(spirits=5, failed=0, page_errors=0)

        with (
            patch.object(
                run_module, "_build_storage", return_value=(storage_mock, None)
            ),
            patch.object(run_module, "_build_api_client", return_value=None),
            patch("run.DistillerScraperV2", return_value=scraper_mock),
        ):
            run_module.run_test(output="sqlite", db_path=":memory:")

        storage_mock.finish_scrape_run.assert_called_once()
        call_args = storage_mock.finish_scrape_run.call_args
        # finish_scrape_run(run_id, total_scraped, total_failed, status)
        kwargs = call_args.kwargs
        args = call_args.args
        run_id = kwargs.get("run_id") if "run_id" in kwargs else args[0]
        total_scraped = (
            kwargs.get("total_scraped") if "total_scraped" in kwargs else args[1]
        )
        total_failed = (
            kwargs.get("total_failed") if "total_failed" in kwargs else args[2]
        )
        status = (
            kwargs.get("status")
            if "status" in kwargs
            else (args[3] if len(args) > 3 else None)
        )

        assert run_id == 42
        assert total_scraped == 5
        assert total_failed == 0
        assert status == "completed"

    # ------------------------------------------------------------------
    # Test 3: finish_scrape_run 在例外時以 status='failed' 呼叫
    # ------------------------------------------------------------------

    def test_scrape_run_finished_on_failure(self):
        """scraper.scrape() 拋出例外時，finish_scrape_run 應以 status='failed' 呼叫。"""
        import run as run_module

        storage_mock = _make_sqlite_mock(run_id=99)
        scraper_mock = _make_scraper_mock()
        scraper_mock.scrape.side_effect = RuntimeError("Selenium crash")

        with (
            patch.object(
                run_module, "_build_storage", return_value=(storage_mock, None)
            ),
            patch.object(run_module, "_build_api_client", return_value=None),
            patch("run.DistillerScraperV2", return_value=scraper_mock),
        ):
            try:
                run_module.run_test(output="sqlite", db_path=":memory:")
            except RuntimeError:
                pass  # 例外向上傳播是允許的

        storage_mock.finish_scrape_run.assert_called_once()
        call_args = storage_mock.finish_scrape_run.call_args
        kwargs = call_args.kwargs
        args = call_args.args
        status = (
            kwargs.get("status")
            if "status" in kwargs
            else (args[3] if len(args) > 3 else None)
        )
        assert status == "failed"

    # ------------------------------------------------------------------
    # Test 4: finish_scrape_run 在部分成功時以 status='completed_with_errors' 呼叫
    # ------------------------------------------------------------------

    def test_scrape_run_finished_on_partial_success(self):
        """有 failed_urls 時，finish_scrape_run 應以 status='completed_with_errors' 呼叫。"""
        import run as run_module

        storage_mock = _make_sqlite_mock(run_id=7)
        scraper_mock = _make_scraper_mock(spirits=3, failed=2, page_errors=0)

        with (
            patch.object(
                run_module, "_build_storage", return_value=(storage_mock, None)
            ),
            patch.object(run_module, "_build_api_client", return_value=None),
            patch("run.DistillerScraperV2", return_value=scraper_mock),
        ):
            run_module.run_test(output="sqlite", db_path=":memory:")

        storage_mock.finish_scrape_run.assert_called_once()
        call_args = storage_mock.finish_scrape_run.call_args
        kwargs = call_args.kwargs
        args = call_args.args
        status = (
            kwargs.get("status")
            if "status" in kwargs
            else (args[3] if len(args) > 3 else None)
        )
        assert status == "completed_with_errors"

    # ------------------------------------------------------------------
    # Test 5: finish_scrape_run 即使 LINE 通知失敗也必定被呼叫
    # ------------------------------------------------------------------

    def test_scrape_run_recorded_even_if_notification_fails(self):
        """LINE 通知發送失敗時，finish_scrape_run 仍應被呼叫（via try/finally）。"""
        import run as run_module

        storage_mock = _make_sqlite_mock(run_id=55)
        scraper_mock = _make_scraper_mock(spirits=2, failed=0, page_errors=0)

        # 模擬 save_csv 或後處理拋出例外（LINE 通知在 main() 層），
        # 實際在 run_test 內部，透過讓 scraper.get_statistics() 拋例外來模擬
        # 但更準確的是：在 run_test 結束後 finish_scrape_run 應已被呼叫，
        # 不管後續 notify 階段是否失敗。
        # 這裡我們驗證：即使 scraper.save_csv 拋例外，finish_scrape_run 仍被呼叫。
        scraper_mock.save_csv = MagicMock(side_effect=OSError("disk full"))

        with (
            patch.object(
                run_module, "_build_storage", return_value=(storage_mock, "out.csv")
            ),
            patch.object(run_module, "_build_api_client", return_value=None),
            patch("run.DistillerScraperV2", return_value=scraper_mock),
        ):
            try:
                run_module.run_test(output="both", db_path=":memory:")
            except Exception:
                pass

        # finish_scrape_run 必定被呼叫（try/finally 保證）
        storage_mock.finish_scrape_run.assert_called_once()
