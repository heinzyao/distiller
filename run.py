#!/usr/bin/env python3
"""
Distiller 爬蟲 V2 執行腳本
用法:
    python run_scraper_v2.py [--test|--medium|--full]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# 加入專案路徑
sys.path.insert(0, str(Path(__file__).parent))

from distiller_scraper.api_client import DistillerAPIClient
from distiller_scraper.scraper import DistillerScraperV2
from distiller_scraper.storage import CSVStorage, SQLiteStorage


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

    storage, csv_file = _build_storage(output, db_path, "distiller_test_v2.csv")
    scraper = DistillerScraperV2(headless=True, storage=storage, api_client=_build_api_client(args))

    scraper.scrape(
        categories=["whiskey"],
        max_per_category=5,
        use_styles=False,
        use_pagination=_use_pagination(args),
    )

    if csv_file:
        scraper.save_csv(csv_file)
    if storage:
        storage.close()

    stats = scraper.get_statistics()
    print(f"\n統計:\n{json.dumps(stats, indent=2, ensure_ascii=False)}")
    return len(scraper.spirits_data) > 0


def run_medium(output: str = "csv", db_path: str = "distiller.db", args=None):
    """中等規模爬取 (每類別 50 筆，共約 200 筆)"""
    print("\n" + "=" * 80)
    print("中等規模 - 爬取約 200 筆資料")
    print("=" * 80 + "\n")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    storage, csv_file = _build_storage(
        output, db_path, f"distiller_spirits_{timestamp}.csv"
    )
    scraper = DistillerScraperV2(headless=True, storage=storage, api_client=_build_api_client(args))

    scraper.scrape(
        categories=["whiskey", "gin", "rum", "vodka"],
        max_per_category=50,
        use_styles=True,
        use_pagination=_use_pagination(args),
    )

    if csv_file:
        scraper.save_csv(csv_file)
    if storage:
        storage.close()

    stats = scraper.get_statistics()
    print(f"\n統計:\n{json.dumps(stats, indent=2, ensure_ascii=False)}")
    return len(scraper.spirits_data) > 0


def run_full(output: str = "csv", db_path: str = "distiller.db", args=None):
    """完整爬取 (每類別 150 筆，共約 1000+ 筆)"""
    print("\n" + "=" * 80)
    print("完整模式 - 爬取大量資料")
    print("=" * 80 + "\n")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    storage, csv_file = _build_storage(
        output, db_path, f"distiller_spirits_full_{timestamp}.csv"
    )
    scraper = DistillerScraperV2(headless=True, storage=storage, api_client=_build_api_client(args))

    scraper.scrape(
        categories=[
            "whiskey",
            "gin",
            "rum",
            "vodka",
            "brandy",
            "tequila-mezcal",
            "liqueurs-bitters",
        ],
        max_per_category=150,
        use_styles=True,
        use_pagination=_use_pagination(args),
    )

    if csv_file:
        scraper.save_csv(csv_file)
    if storage:
        storage.close()

    stats = scraper.get_statistics()
    print(f"\n統計:\n{json.dumps(stats, indent=2, ensure_ascii=False)}")
    return len(scraper.spirits_data) > 0


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

    args = parser.parse_args()

    print(f"\n開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if args.mode == "test":
        success = run_test(args.output, args.db_path, args)
    elif args.mode == "medium":
        success = run_medium(args.output, args.db_path, args)
    else:
        success = run_full(args.output, args.db_path, args)

    print(f"\n結束時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if success:
        print("\n✅ 爬蟲執行成功！")
    else:
        print("\n❌ 爬蟲執行失敗")
        sys.exit(1)


if __name__ == "__main__":
    main()
