#!/usr/bin/env python3
"""
一次性補充爬取 liqueurs-bitters 類別
用法:
    uv run python scripts/supplement_liqueurs.py [--db distiller.db] [--max 300]
"""
import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from distiller_scraper.scraper import DistillerScraperV2
from distiller_scraper.storage import SQLiteStorage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main():
    parser = argparse.ArgumentParser(description="補充爬取 liqueurs-bitters 類別")
    parser.add_argument("--db", default="distiller.db", help="SQLite 資料庫路徑")
    parser.add_argument("--max", type=int, default=300, help="最多爬取筆數")
    parser.add_argument(
        "--no-pagination",
        action="store_true",
        help="停用分頁模式，改用傳統滾動爬取",
    )
    args = parser.parse_args()

    print(f"\n補充爬取 liqueurs-bitters → {args.db}（上限 {args.max} 筆）\n")

    storage = SQLiteStorage(args.db)
    run_id = storage.record_scrape_run(
        categories=["liqueurs-bitters"], mode="supplement"
    )

    scraper = DistillerScraperV2(headless=True, storage=storage)
    status = "completed"
    try:
        scraper.scrape(
            categories=["liqueurs-bitters"],
            max_per_category=args.max,
            use_styles=True,
            use_pagination=not args.no_pagination,
        )
        if scraper.failed_urls or scraper.page_errors:
            status = "completed_with_errors"
    except Exception:
        status = "failed"
        raise
    finally:
        storage.finish_scrape_run(
            run_id,
            len(scraper.spirits_data),
            len(scraper.failed_urls),
            status,
        )

    stats = scraper.get_statistics()
    print(f"\n統計:\n{json.dumps(stats, indent=2, ensure_ascii=False)}")
    storage.close()


if __name__ == "__main__":
    main()
