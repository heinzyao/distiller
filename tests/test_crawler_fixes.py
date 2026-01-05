"""
測試修復後的爬蟲代碼

驗證以下修復：
1. ✅ 多線程鎖正確使用
2. ✅ 重試次數限制
3. ✅ 函數正確返回值
4. ✅ 請求超時生效
"""

import sys
import os
import time
import threading
from pathlib import Path

# 添加 src 到路徑
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from distiller.crawler.product_crawler_fixed import (
    crawl_product,
    safe_request,
    data_lock,
    data,
    exec_count
)
from distiller.crawler.review_crawler_fixed import get_user_reviews


def test_1_thread_lock():
    """測試 1：多線程鎖是否正確使用"""
    print("\n" + "=" * 60)
    print("測試 1：多線程鎖")
    print("=" * 60)

    # 導入修復後的模組
    import distiller.crawler.product_crawler_fixed as fixed_crawler

    # 重置數據
    fixed_crawler.data = []
    fixed_crawler.exec_count = 0

    # 測試 URL
    test_urls = [
        'https://distiller.com/spirits/makers-mark-bourbon',
        'https://distiller.com/spirits/tanqueray-london-dry-gin',
    ]

    # 創建多個線程同時寫入
    def worker():
        for url in test_urls:
            fixed_crawler.crawl_product(url)

    threads = []
    num_threads = 3

    print(f"創建 {num_threads} 個線程同時爬取...")

    for i in range(num_threads):
        thread = threading.Thread(target=worker)
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    # 驗證結果
    expected_count = len(test_urls) * num_threads
    actual_count = len(fixed_crawler.data)

    print(f"\n預期數據量: {expected_count}")
    print(f"實際數據量: {actual_count}")
    print(f"計數器值: {fixed_crawler.exec_count}")

    if actual_count == expected_count == fixed_crawler.exec_count:
        print("✅ 測試通過：沒有數據丟失，鎖正確工作！")
        return True
    else:
        print(f"❌ 測試失敗：數據不一致")
        return False


def test_2_retry_limit():
    """測試 2：重試次數限制"""
    print("\n" + "=" * 60)
    print("測試 2：重試次數限制")
    print("=" * 60)

    # 測試一個不存在的 URL
    bad_url = "https://distiller.com/spirits/this-does-not-exist-123456789"

    print(f"測試 URL: {bad_url}")
    print("預期：最多重試 3 次後放棄\n")

    start_time = time.time()
    response = safe_request(bad_url)
    elapsed_time = time.time() - start_time

    print(f"\n請求結果: {response}")
    print(f"耗時: {elapsed_time:.2f} 秒")

    # 應該在合理時間內失敗（不會無限重試）
    if response is None and elapsed_time < 120:  # 應該在 2 分鐘內結束
        print("✅ 測試通過：正確放棄重試！")
        return True
    else:
        print("❌ 測試失敗：可能無限重試或未正確處理")
        return False


def test_3_function_return_value():
    """測試 3：函數返回值"""
    print("\n" + "=" * 60)
    print("測試 3：函數返回值")
    print("=" * 60)

    test_urls = [
        'https://distiller.com/spirits/makers-mark-bourbon',
    ]

    print(f"調用 get_user_reviews({test_urls})...")

    result = get_user_reviews(test_urls, 0, 1)

    print(f"\n返回值類型: {type(result)}")
    print(f"返回值長度: {len(result) if isinstance(result, list) else 'N/A'}")

    if isinstance(result, list):
        print(f"返回值內容樣本: {result[:2] if result else '[]'}")
        print("✅ 測試通過：函數正確返回列表！")
        return True
    else:
        print(f"❌ 測試失敗：返回值是 {type(result)}，應該是 list")
        return False


def test_4_request_timeout():
    """測試 4：請求超時"""
    print("\n" + "=" * 60)
    print("測試 4：請求超時")
    print("=" * 60)

    # 使用一個會延遲響應的測試服務
    delay_url = "https://httpbin.org/delay/5"  # 延遲 5 秒

    print("測試 4a：超時設置為 2 秒（應該超時）")
    start_time = time.time()
    response = safe_request(delay_url, timeout=2)
    elapsed = time.time() - start_time

    print(f"耗時: {elapsed:.2f} 秒")
    if response is None and elapsed < 3:
        print("✅ 正確超時")
        test_4a = True
    else:
        print("❌ 未正確超時")
        test_4a = False

    print("\n測試 4b：超時設置為 10 秒（應該成功）")
    start_time = time.time()
    response = safe_request(delay_url, timeout=10)
    elapsed = time.time() - start_time

    print(f"耗時: {elapsed:.2f} 秒")
    if response is not None and 5 <= elapsed <= 7:
        print("✅ 請求成功，耗時合理")
        test_4b = True
    else:
        print("❌ 請求異常")
        test_4b = False

    if test_4a and test_4b:
        print("\n✅ 測試通過：超時設置正確工作！")
        return True
    else:
        print("\n❌ 測試部分失敗")
        return False


def run_all_tests():
    """運行所有測試"""
    print("\n")
    print("=" * 60)
    print("   修復代碼測試套件")
    print("=" * 60)

    tests = [
        ("多線程鎖", test_1_thread_lock),
        ("重試次數限制", test_2_retry_limit),
        ("函數返回值", test_3_function_return_value),
        ("請求超時", test_4_request_timeout),
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"\n❌ 測試 '{test_name}' 發生異常: {e}")
            results[test_name] = False

    # 打印總結
    print("\n")
    print("=" * 60)
    print("   測試總結")
    print("=" * 60)

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ 通過" if result else "❌ 失敗"
        print(f"{test_name:20s} {status}")

    print("\n" + "=" * 60)
    print(f"總計: {passed}/{total} 測試通過")
    print("=" * 60)

    if passed == total:
        print("\n🎉 所有測試通過！修復成功！")
    else:
        print(f"\n⚠️  有 {total - passed} 個測試失敗，需要進一步檢查")

    return passed == total


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
