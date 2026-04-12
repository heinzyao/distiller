#!/usr/bin/env python3
"""
Distiller 爬蟲 V2 執行腳本
用法:
    python run.py [--mode test|medium|full] [--output csv|sqlite|both] [--notify-line]
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# 加入專案路徑
sys.path.insert(0, str(Path(__file__).parent))

# CSV 輸出目錄
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

from distiller_scraper.api_client import DistillerAPIClient
from distiller_scraper.config import ScraperConfig
from distiller_scraper.notify import LineNotifier
from distiller_scraper.scraper import DistillerScraperV2
from distiller_scraper.storage import CSVStorage, SQLiteStorage

logger = logging.getLogger(__name__)


def _should_skip_run(storage) -> tuple[bool, str]:
    if not isinstance(storage, SQLiteStorage):
        return False, ""
    try:
        cutoff = datetime.now() - timedelta(
            hours=ScraperConfig.DUPLICATE_RUN_WINDOW_HOURS
        )
        row = storage.conn.execute(
            "SELECT started_at FROM scrape_runs"
            " WHERE status IN ('completed', 'completed_with_errors')"
            " AND started_at >= ? ORDER BY started_at DESC LIMIT 1",
            (cutoff.isoformat(),),
        ).fetchone()
        if row:
            logger.info(f"Recent successful run found at {row[0]}, skipping")
            return True, str(row[0])
        return False, ""
    except Exception as e:
        logger.warning(f"Duplicate check failed, proceeding: {e}")
        return False, ""  # fail-open


def _use_pagination(args) -> bool:
    return not getattr(args, "no_pagination", False)


def _build_api_client(args) -> "DistillerAPIClient | None":
    if getattr(args, "use_api", False):
        print("API 模式：已啟用（將於爬取前自動探測端點）")
        return DistillerAPIClient()
    return None


def _build_storage(output: str, db_path: str, filename: str):
    """根據 --output 參數建立儲存後端"""
    if output == "sqlite":
        storage = SQLiteStorage(db_path)
        print(f"輸出格式: SQLite ({db_path})")
        return storage, None
    elif output == "both":
        storage = SQLiteStorage(db_path)
        print(f"輸出格式: SQLite ({db_path}) + CSV ({filename})")
        return storage, filename
    else:
        print(f"輸出格式: CSV ({filename})")
        return None, filename


def run_test(output: str = "csv", db_path: str = "distiller.db", args=None):
    """測試爬取 (5 筆)"""
    print("\n" + "=" * 80)
    print("測試模式 - 爬取少量資料驗證功能")
    print("=" * 80 + "\n")

    storage, csv_file = _build_storage(
        output, db_path, str(DATA_DIR / "distiller_test_v2.csv")
    )
    skip, last_run_at = _should_skip_run(storage)
    if skip:
        print("⏭️  Recent successful run found, skipping")
        return True, {"_skipped": True, "_last_run_at": last_run_at}
    scraper = DistillerScraperV2(
        headless=True, storage=storage, api_client=_build_api_client(args)
    )

    run_id = None
    if isinstance(storage, SQLiteStorage):
        run_id = storage.record_scrape_run(categories=["whiskey"], mode="test")

    status = "completed"
    try:
        scrape_ok = scraper.scrape(
            categories=["whiskey"],
            max_per_category=5,
            use_styles=False,
            use_pagination=_use_pagination(args),
        )
        has_errors = len(scraper.failed_urls) > 0 or scraper.page_errors > 0
        if has_errors:
            status = "completed_with_errors"
    except Exception:
        status = "failed"
        raise
    finally:
        if run_id is not None and isinstance(storage, SQLiteStorage):
            storage.finish_scrape_run(
                run_id, len(scraper.spirits_data), len(scraper.failed_urls), status
            )

    if csv_file:
        scraper.save_csv(csv_file)
    if storage:
        storage.close()

    stats = scraper.get_statistics()
    print(f"\n統計:\n{json.dumps(stats, indent=2, ensure_ascii=False)}")
    # scrape_ok=True 表示爬蟲完整執行（無例外）；0 筆新增可能是 DB 已是最新，非失敗
    success = scrape_ok
    return success, stats


def run_medium(output: str = "csv", db_path: str = "distiller.db", args=None):
    """中等規模爬取 (每類別 50 筆，共約 200 筆)"""
    print("\n" + "=" * 80)
    print("中等規模 - 爬取約 200 筆資料")
    print("=" * 80 + "\n")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    storage, csv_file = _build_storage(
        output, db_path, str(DATA_DIR / f"distiller_spirits_{timestamp}.csv")
    )
    skip, last_run_at = _should_skip_run(storage)
    if skip:
        print("⏭️  Recent successful run found, skipping")
        return True, {"_skipped": True, "_last_run_at": last_run_at}
    scraper = DistillerScraperV2(
        headless=True, storage=storage, api_client=_build_api_client(args)
    )

    _medium_categories = ["whiskey", "gin", "rum", "vodka"]
    run_id = None
    if isinstance(storage, SQLiteStorage):
        run_id = storage.record_scrape_run(categories=_medium_categories, mode="medium")

    status = "completed"
    try:
        scrape_ok = scraper.scrape(
            categories=_medium_categories,
            max_per_category=50,
            use_styles=True,
            use_pagination=_use_pagination(args),
        )
        has_errors = len(scraper.failed_urls) > 0 or scraper.page_errors > 0
        if has_errors:
            status = "completed_with_errors"
    except Exception:
        status = "failed"
        raise
    finally:
        if run_id is not None and isinstance(storage, SQLiteStorage):
            storage.finish_scrape_run(
                run_id, len(scraper.spirits_data), len(scraper.failed_urls), status
            )

    if csv_file:
        scraper.save_csv(csv_file)
    if storage:
        storage.close()

    stats = scraper.get_statistics()
    print(f"\n統計:\n{json.dumps(stats, indent=2, ensure_ascii=False)}")
    success = scrape_ok
    return success, stats


def run_full(output: str = "csv", db_path: str = "distiller.db", args=None):
    """完整爬取 (每類別 150 筆，共約 1000+ 筆)"""
    print("\n" + "=" * 80)
    print("完整模式 - 爬取大量資料")
    print("=" * 80 + "\n")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    storage, csv_file = _build_storage(
        output, db_path, str(DATA_DIR / f"distiller_spirits_full_{timestamp}.csv")
    )
    skip, last_run_at = _should_skip_run(storage)
    if skip:
        print("⏭️  Recent successful run found, skipping")
        return True, {"_skipped": True, "_last_run_at": last_run_at}
    scraper = DistillerScraperV2(
        headless=True, storage=storage, api_client=_build_api_client(args)
    )

    _full_categories = [
        "liqueurs-bitters",
        "whiskey",
        "gin",
        "rum",
        "vodka",
        "brandy",
        "tequila-mezcal",
    ]
    run_id = None
    if isinstance(storage, SQLiteStorage):
        run_id = storage.record_scrape_run(categories=_full_categories, mode="full")

    status = "completed"
    try:
        scrape_ok = scraper.scrape(
            categories=_full_categories,
            max_per_category=150,
            use_styles=True,
            use_pagination=_use_pagination(args),
        )
        has_errors = len(scraper.failed_urls) > 0 or scraper.page_errors > 0
        if has_errors:
            status = "completed_with_errors"
    except Exception:
        status = "failed"
        raise
    finally:
        if run_id is not None and isinstance(storage, SQLiteStorage):
            storage.finish_scrape_run(
                run_id, len(scraper.spirits_data), len(scraper.failed_urls), status
            )

    if csv_file:
        scraper.save_csv(csv_file)
    if storage:
        storage.close()

    stats = scraper.get_statistics()
    print(f"\n統計:\n{json.dumps(stats, indent=2, ensure_ascii=False)}")
    success = scrape_ok
    return success, stats


def main():
    parser = argparse.ArgumentParser(description="Distiller.com 爬蟲 V2")
    parser.add_argument(
        "--mode",
        choices=["test", "medium", "full"],
        default="test",
        help="爬取模式: test (5筆), medium (~200筆), full (~1000+筆)",
    )
    parser.add_argument(
        "--output",
        choices=["csv", "sqlite", "both"],
        default="csv",
        help="輸出格式: csv (預設), sqlite, both",
    )
    parser.add_argument(
        "--db-path",
        default="distiller.db",
        help="SQLite 資料庫路徑 (預設: distiller.db)",
    )
    parser.add_argument(
        "--no-pagination",
        action="store_true",
        help="停用分頁模式，改用傳統滾動爬取",
    )
    parser.add_argument(
        "--use-api",
        action="store_true",
        help="啟用 API 模式（自動探測端點，大幅提升爬取速度）",
    )
    parser.add_argument(
        "--notify-line",
        action="store_true",
        help="爬取完成後透過 LINE Messaging API 發送通知",
    )

    args = parser.parse_args()

    print(f"\n開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _run_start = time.time()

    # GCS 下載：爬取前從 GCS 取得最新 DB（僅 sqlite/both 輸出模式且設定了 GCS_BUCKET）
    gcs_bucket = os.getenv("GCS_BUCKET", "")
    if gcs_bucket and args.output in ("sqlite", "both"):
        from distiller_scraper import gcs_storage

        gcs_db_blob = os.getenv("GCS_DB_BLOB", "distiller.db")
        print(f"☁️  從 GCS 下載 DB ({gcs_bucket}/{gcs_db_blob})…")
        gcs_storage.download_db(gcs_bucket, gcs_db_blob, args.db_path)

    _exc: Exception | None = None
    try:
        if args.mode == "test":
            success, stats = run_test(args.output, args.db_path, args)
        elif args.mode == "medium":
            success, stats = run_medium(args.output, args.db_path, args)
        else:
            success, stats = run_full(args.output, args.db_path, args)
    except Exception as e:
        _exc = e
        success, stats = False, {}
        logger.exception("爬蟲執行發生例外")

    duration_secs = int(time.time() - _run_start)
    print(f"\n結束時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # LINE 通知（失敗時自動等待 30 秒重試一次，處理 3AM 暫時性 DNS 問題）
    if args.notify_line:
        skipped = stats.get("_skipped", False)
        notifier = LineNotifier()
        if not notifier.is_configured():
            print(
                "⚠️  LINE 通知未設定（缺少 LINE_CHANNEL_ID、LINE_CHANNEL_SECRET 或 LINE_USER_ID）"
            )
        else:
            clean_stats = {k: v for k, v in stats.items() if not k.startswith("_")}

            def _do_notify() -> bool:
                if skipped:
                    return notifier.notify_skipped(
                        args.mode, stats.get("_last_run_at", "")
                    )
                if success:
                    return notifier.notify_success(
                        args.mode, clean_stats, duration_secs=duration_secs
                    )
                return notifier.notify_failure(
                    args.mode,
                    error=str(_exc) if _exc else "",
                    duration_secs=duration_secs,
                )

            ok = _do_notify()
            if not ok:
                print("⚠️  LINE 通知第一次失敗，30 秒後重試…")
                time.sleep(30)
                ok = _do_notify()
            if skipped:
                label = "LINE 跳過通知已發送"
            elif success:
                label = "LINE 通知已發送"
            else:
                label = "LINE 失敗通知已發送"
            print(f"📱 {label}" if ok else "⚠️  LINE 通知發送失敗（請查看日誌）")

    # GCS 上傳：爬取完成後將更新的 DB 上傳（僅 sqlite/both 輸出模式且設定了 GCS_BUCKET）
    gcs_bucket = os.getenv("GCS_BUCKET", "")
    if gcs_bucket and args.output in ("sqlite", "both"):
        from distiller_scraper import gcs_storage

        gcs_db_blob = os.getenv("GCS_DB_BLOB", "distiller.db")
        print(f"\n☁️  上傳 DB 至 GCS ({gcs_bucket}/{gcs_db_blob})…")
        gcs_storage.upload_db(gcs_bucket, gcs_db_blob, args.db_path)

    if _exc is not None:
        raise _exc
    if success:
        print("\n✅ 爬蟲執行成功！")
    else:
        print("\n❌ 爬蟲執行失敗")
        sys.exit(1)


if __name__ == "__main__":
    main()
