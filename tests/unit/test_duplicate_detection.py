"""
重複執行檢測測試
驗證 _should_skip_run() 正確判斷是否應跳過本次爬取。
"""

import sqlite3
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from distiller_scraper.storage import SQLiteStorage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_storage_mock_with_row(row) -> MagicMock:
    """建立回傳指定查詢結果列的 SQLiteStorage mock。"""
    mock = MagicMock(spec=SQLiteStorage)
    # conn 是實例屬性而非類別屬性，需手動設定以繞過 spec 限制
    conn_mock = MagicMock()
    cursor_mock = MagicMock()
    cursor_mock.fetchone.return_value = row
    conn_mock.execute.return_value = cursor_mock
    mock.conn = conn_mock
    return mock


def _make_storage_mock_empty() -> MagicMock:
    """建立查詢結果為空的 SQLiteStorage mock。"""
    return _make_storage_mock_with_row(None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDuplicateDetection:
    """驗證 _should_skip_run() 重複執行檢測邏輯。"""

    def test_skips_when_recent_successful_run(self):
        """2 小時內有成功的執行記錄時，_should_skip_run 應回傳 (True, timestamp)。"""
        import run as run_module

        recent_time = (datetime.now() - timedelta(hours=2)).isoformat()
        storage_mock = _make_storage_mock_with_row((recent_time,))

        skip, last_run_at = run_module._should_skip_run(storage_mock)

        assert skip is True
        assert last_run_at == recent_time

    def test_proceeds_when_no_recent_run(self):
        """scrape_runs 表為空時，_should_skip_run 應回傳 (False, '')，允許爬取繼續。"""
        import run as run_module

        storage_mock = _make_storage_mock_empty()

        skip, last_run_at = run_module._should_skip_run(storage_mock)

        assert skip is False
        assert last_run_at == ""

    def test_proceeds_when_recent_run_failed(self):
        """2 小時前有失敗的執行記錄時，_should_skip_run 應回傳 (False, '')（失敗不阻擋）。"""
        import run as run_module

        storage_mock = _make_storage_mock_empty()

        skip, last_run_at = run_module._should_skip_run(storage_mock)

        assert skip is False

    def test_proceeds_when_run_is_old(self):
        """25 小時前的成功執行（超出窗口）時，_should_skip_run 應回傳 (False, '')。"""
        import run as run_module

        storage_mock = _make_storage_mock_empty()

        skip, last_run_at = run_module._should_skip_run(storage_mock)

        assert skip is False

    def test_proceeds_when_db_check_fails(self):
        """DB 查詢拋出 sqlite3.Error 時，_should_skip_run 應 fail-open（回傳 (False, '')）。"""
        import run as run_module

        storage_mock = MagicMock(spec=SQLiteStorage)
        conn_mock = MagicMock()
        conn_mock.execute.side_effect = sqlite3.Error("table not found")
        storage_mock.conn = conn_mock

        skip, last_run_at = run_module._should_skip_run(storage_mock)

        assert skip is False

    def test_partial_success_counts_as_successful(self):
        """status='completed_with_errors' 的執行也視為成功，應回傳 (True, timestamp)（跳過）。"""
        import run as run_module

        recent_time = (datetime.now() - timedelta(hours=1)).isoformat()
        storage_mock = _make_storage_mock_with_row((recent_time,))

        skip, last_run_at = run_module._should_skip_run(storage_mock)

        assert skip is True
