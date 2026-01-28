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

# 加入專案路徑
sys.path.insert(0, "/Users/Henry/Desktop/Project/Distiller")

from distiller_scraper.scraper import DistillerScraperV2


def run_test():
    """測試爬取 (5 筆)"""
    print("\n" + "=" * 80)
    print("🧪 測試模式 - 爬取少量資料驗證功能")
    print("=" * 80 + "\n")

    scraper = DistillerScraperV2(headless=True)

    scraper.scrape(
        categories=["whiskey"],
        max_per_category=5,
        use_styles=False,
    )

    scraper.save_csv("distiller_test_v2.csv")
    stats = scraper.get_statistics()
    print(f"\n統計:\n{json.dumps(stats, indent=2, ensure_ascii=False)}")

    return len(scraper.spirits_data) > 0


def run_medium():
    """中等規模爬取 (每類別 50 筆，共約 200 筆)"""
    print("\n" + "=" * 80)
    print("📊 中等規模 - 爬取約 200 筆資料")
    print("=" * 80 + "\n")

    scraper = DistillerScraperV2(headless=True)

    scraper.scrape(
        categories=["whiskey", "gin", "rum", "vodka"],
        max_per_category=50,
        use_styles=True,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"distiller_spirits_{timestamp}.csv"
    scraper.save_csv(filename)

    stats = scraper.get_statistics()
    print(f"\n統計:\n{json.dumps(stats, indent=2, ensure_ascii=False)}")

    return len(scraper.spirits_data) > 0


def run_full():
    """完整爬取 (每類別 150 筆，共約 1000+ 筆)"""
    print("\n" + "=" * 80)
    print("🚀 完整模式 - 爬取大量資料")
    print("=" * 80 + "\n")

    scraper = DistillerScraperV2(headless=True)

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
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"distiller_spirits_full_{timestamp}.csv"
    scraper.save_csv(filename)

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

    args = parser.parse_args()

    print(f"\n開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if args.mode == "test":
        success = run_test()
    elif args.mode == "medium":
        success = run_medium()
    else:
        success = run_full()

    print(f"\n結束時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if success:
        print("\n✅ 爬蟲執行成功！")
    else:
        print("\n❌ 爬蟲執行失敗")
        sys.exit(1)


if __name__ == "__main__":
    main()
