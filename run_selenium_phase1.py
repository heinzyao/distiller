#!/usr/bin/env python3
"""
Phase 1 Selenium 測試腳本
"""

import sys

sys.path.insert(0, "/Users/Henry/Desktop/Project/Distiller")

from distiller_selenium_scraper import run_phase1_selenium_test

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🚀 開始 Phase 1 Selenium 測試")
    print("目標: 爬取 5-10 條烈酒記錄以驗證 Selenium 爬蟲功能")
    print("注意: Chrome 瀏覽器窗口將會打開")
    print("=" * 80 + "\n")

    scraper, success = run_phase1_selenium_test()

    if success:
        print("\n✅ Phase 1 Selenium 測試成功完成！")
        print("請檢查 distiller_selenium_phase1.csv 文件")
        print("日誌已保存到 distiller_selenium_scraper.log")
    else:
        print("\n❌ Phase 1 Selenium 測試失敗")
        print("請檢查 distiller_selenium_scraper.log 以了解詳細信息")
        sys.exit(1)
