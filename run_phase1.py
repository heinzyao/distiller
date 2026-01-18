#!/usr/bin/env python3
"""
Phase 1 測試腳本 - 小規模可行性測試
"""

import sys

sys.path.insert(0, "/Users/Henry/Desktop/Project/Distiller")

from distiller_scraper_improved import run_phase1_test
import logging

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🚀 開始 Phase 1: 小規模可行性測試")
    print("目標: 爬取 5-10 條烈酒記錄以驗證爬蟲功能")
    print("=" * 80 + "\n")

    scraper, success = run_phase1_test()

    if success:
        print("\n✅ Phase 1 測試成功完成！")
        print("請檢查 distiller_phase1_test.csv 文件")
        print("日誌已保存到 distiller_scraper.log")
    else:
        print("\n❌ Phase 1 測試失敗")
        print("請檢查 distiller_scraper.log 以了解詳細信息")
        sys.exit(1)
