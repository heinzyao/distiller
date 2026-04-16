"""
run.py LINE 通知整合單元測試

涵蓋 main() 在 --notify-line 旗標下的情境：
  1. 爬取成功   → notify_success 呼叫
  2. 爬取失敗   → notify_failure 呼叫
以及旗標缺席、LINE 未設定、發送失敗重試等情境。
"""

import sys
from unittest.mock import MagicMock, call, patch

import pytest

from distiller_scraper.notify import LineNotifier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_notifier_mock(is_configured=True, send_results=None):
    """建立 LineNotifier spec mock，並設定 send_results 串列決定每次呼叫回傳值。"""
    mock = MagicMock(spec=LineNotifier)
    mock.is_configured.return_value = is_configured
    if send_results is None:
        send_results = [True]

    # 這裡直接設定高階方法的回傳值序列。
    mock.notify_success.side_effect = send_results
    mock.notify_failure.side_effect = send_results
    return mock


def _run_main(monkeypatch, extra_argv=None, run_fn_return=None):
    """
    執行 main()，並回傳 (sys_exit_called, exit_code)。
    extra_argv: list of str to append after default argv
    run_fn_return: (success, stats) tuple returned by run_test mock
    """
    base_argv = ["run.py", "--mode", "test", "--output", "csv"]
    argv = base_argv + (extra_argv or [])
    monkeypatch.setattr("sys.argv", argv)

    if run_fn_return is None:
        run_fn_return = (True, {})

    exit_code_holder = []

    def fake_exit(code=0):
        exit_code_holder.append(code)
        raise SystemExit(code)

    import run as run_module

    with (
        patch.object(run_module, "run_test", return_value=run_fn_return),
        patch.object(run_module, "run_medium", return_value=run_fn_return),
        patch.object(run_module, "run_full", return_value=run_fn_return),
    ):
        try:
            run_module.main()
        except SystemExit as exc:
            exit_code_holder.append(exc.code)

    return exit_code_holder


# ---------------------------------------------------------------------------
# TestMainNotify
# ---------------------------------------------------------------------------


class TestMainNotify:
    """main() 在 --notify-line 下的各情境測試。"""

    def test_scrape_success_calls_notify_success(self, monkeypatch, capsys):
        """正常爬取成功：應呼叫 notify_success。"""
        mock_notifier = _make_notifier_mock(is_configured=True, send_results=[True])
        stats = {"總記錄數": 5, "失敗 URL 數": 0}

        import run as run_module

        monkeypatch.setattr(
            "sys.argv", ["run.py", "--mode", "test", "--output", "csv", "--notify-line"]
        )

        with (
            patch.object(run_module, "run_test", return_value=(True, stats)),
            patch.object(run_module, "LineNotifier", return_value=mock_notifier),
            patch.object(run_module.time, "sleep"),
        ):
            run_module.main()

        mock_notifier.notify_success.assert_called_once()
        call_args = mock_notifier.notify_success.call_args
        assert call_args[0][0] == "test"
        assert call_args[0][1] == stats
        mock_notifier.notify_failure.assert_not_called()

    def test_scrape_failure_calls_notify_failure(self, monkeypatch, capsys):
        """run_test 回傳 success=False：應呼叫 notify_failure。"""
        mock_notifier = _make_notifier_mock(is_configured=True, send_results=[True])

        import run as run_module

        monkeypatch.setattr(
            "sys.argv", ["run.py", "--mode", "test", "--output", "csv", "--notify-line"]
        )

        with (
            patch.object(run_module, "run_test", return_value=(False, {})),
            patch.object(run_module, "LineNotifier", return_value=mock_notifier),
            patch.object(run_module.time, "sleep"),
        ):
            try:
                run_module.main()
            except SystemExit:
                pass

        mock_notifier.notify_failure.assert_called_once()
        assert mock_notifier.notify_failure.call_args[0][0] == "test"
        mock_notifier.notify_success.assert_not_called()

    def test_health_check_failure_calls_notify_failure(self, monkeypatch, capsys):
        """健康檢查失敗（success=False, stats={}）：應呼叫 notify_failure。"""
        mock_notifier = _make_notifier_mock(is_configured=True, send_results=[True])

        import run as run_module

        monkeypatch.setattr(
            "sys.argv", ["run.py", "--mode", "test", "--output", "csv", "--notify-line"]
        )

        with (
            patch.object(
                run_module, "run_test", return_value=(False, {"health_check": False})
            ),
            patch.object(run_module, "LineNotifier", return_value=mock_notifier),
            patch.object(run_module.time, "sleep"),
        ):
            try:
                run_module.main()
            except SystemExit:
                pass

        mock_notifier.notify_failure.assert_called_once()
        mock_notifier.notify_success.assert_not_called()

    def test_no_notify_flag_skips_line_notification(self, monkeypatch):
        """未傳 --notify-line 時，LineNotifier 不應被建立或呼叫。"""
        import run as run_module

        monkeypatch.setattr("sys.argv", ["run.py", "--mode", "test", "--output", "csv"])

        with (
            patch.object(run_module, "run_test", return_value=(True, {})),
            patch.object(run_module, "LineNotifier") as mock_cls,
        ):
            run_module.main()

        mock_cls.assert_not_called()

    def test_line_not_configured_prints_warning(self, monkeypatch, capsys):
        """LINE 憑證未設定時，應印出警告訊息，不呼叫 notify_success/notify_failure。"""
        mock_notifier = _make_notifier_mock(is_configured=False)

        import run as run_module

        monkeypatch.setattr(
            "sys.argv", ["run.py", "--mode", "test", "--output", "csv", "--notify-line"]
        )

        with (
            patch.object(run_module, "run_test", return_value=(True, {})),
            patch.object(run_module, "LineNotifier", return_value=mock_notifier),
        ):
            run_module.main()

        mock_notifier.notify_success.assert_not_called()
        mock_notifier.notify_failure.assert_not_called()
        out = capsys.readouterr().out
        assert "LINE 通知未設定" in out

    def test_line_send_fails_first_then_retries(self, monkeypatch, capsys):
        """第一次發送失敗 → 等待 30 秒 → 重試（send_results=[False, True]）。"""
        mock_notifier = _make_notifier_mock(
            is_configured=True, send_results=[False, True]
        )

        import run as run_module

        monkeypatch.setattr(
            "sys.argv", ["run.py", "--mode", "test", "--output", "csv", "--notify-line"]
        )

        sleep_calls = []

        def fake_sleep(secs):
            sleep_calls.append(secs)

        with (
            patch.object(run_module, "run_test", return_value=(True, {})),
            patch.object(run_module, "LineNotifier", return_value=mock_notifier),
            patch.object(run_module.time, "sleep", side_effect=fake_sleep),
        ):
            run_module.main()

        # sleep 應該被呼叫一次，且間隔 30 秒
        assert sleep_calls == [30]
        # notify_success 應被呼叫兩次
        assert mock_notifier.notify_success.call_count == 2

    def test_retry_success_prints_sent_label(self, monkeypatch, capsys):
        """重試成功後，輸出應包含「已發送」而非「失敗」。"""
        mock_notifier = _make_notifier_mock(
            is_configured=True, send_results=[False, True]
        )

        import run as run_module

        monkeypatch.setattr(
            "sys.argv", ["run.py", "--mode", "test", "--output", "csv", "--notify-line"]
        )

        with (
            patch.object(run_module, "run_test", return_value=(True, {})),
            patch.object(run_module, "LineNotifier", return_value=mock_notifier),
            patch.object(run_module.time, "sleep"),
        ):
            run_module.main()

        out = capsys.readouterr().out
        assert "已發送" in out
        assert "LINE 通知發送失敗" not in out

    def test_retry_still_fails_prints_failure_label(self, monkeypatch, capsys):
        """兩次都失敗時，應印出發送失敗警告。"""
        mock_notifier = _make_notifier_mock(
            is_configured=True, send_results=[False, False]
        )

        import run as run_module

        monkeypatch.setattr(
            "sys.argv", ["run.py", "--mode", "test", "--output", "csv", "--notify-line"]
        )

        with (
            patch.object(run_module, "run_test", return_value=(True, {})),
            patch.object(run_module, "LineNotifier", return_value=mock_notifier),
            patch.object(run_module.time, "sleep"),
        ):
            run_module.main()

        out = capsys.readouterr().out
        assert "LINE 通知發送失敗" in out

    def test_line_failure_does_not_change_exit_code(self, monkeypatch):
        """LINE 通知失敗不應影響爬蟲的退出碼（成功爬取 = exit 0）。"""
        mock_notifier = _make_notifier_mock(
            is_configured=True, send_results=[False, False]
        )

        import run as run_module

        monkeypatch.setattr(
            "sys.argv", ["run.py", "--mode", "test", "--output", "csv", "--notify-line"]
        )

        exit_called = []

        with (
            patch.object(run_module, "run_test", return_value=(True, {})),
            patch.object(run_module, "LineNotifier", return_value=mock_notifier),
            patch.object(run_module.time, "sleep"),
            patch.object(sys, "exit", side_effect=lambda c: exit_called.append(c)),
        ):
            run_module.main()

        # sys.exit 不應被呼叫（成功不呼叫 sys.exit）
        assert exit_called == []

