"""
修復後的 Distiller 用戶評論爬蟲

修復內容：
1. ✅ 修復函數返回值錯誤 - 返回列表而不是 None
2. ✅ 移除全局變量依賴 - 使用本地變量和返回值
3. ✅ 添加請求超時 - 所有請求都有 30 秒超時
4. ✅ 指定 BeautifulSoup 解析器 - 使用 lxml
5. ✅ 改進錯誤處理
"""

import requests
import re
import time
import math
import logging
from typing import List, Dict, Any
from tqdm import tqdm
from bs4 import BeautifulSoup
from queue import Queue
from threading import Thread

# =====================================
# 配置
# =====================================
CONFIG = {
    'timeout': 30,
    'delay': 1,
    'max_retries': 3,
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_2) AppleWebKit/537.36",
    "Connection": "keep-alive",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.8"
}

# =====================================
# 日誌設置
# =====================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/review_crawler_fixed.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def safe_request(url: str, timeout: int = None) -> requests.Response:
    """
    安全的 HTTP 請求

    Args:
        url: 請求 URL
        timeout: 超時時間

    Returns:
        Response 對象，失敗返回 None
    """
    if timeout is None:
        timeout = CONFIG['timeout']

    try:
        # ✅ 添加超時
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        return response
    except requests.Timeout:
        logger.error(f"Timeout for {url}")
        return None
    except requests.RequestException as e:
        logger.error(f"Request error for {url}: {e}")
        return None


def get_user_reviews(url_list: List[str], start: int = 0, end: int = None) -> List[Dict[str, Any]]:
    """
    爬取用戶評論（修復後的版本）

    ✅ 修復問題 3：返回列表而不是 None
    ✅ 不使用全局變量

    Args:
        url_list: URL 列表
        start: 起始索引
        end: 結束索引

    Returns:
        用戶評論列表
    """
    if end is None:
        end = len(url_list)

    user_reviews = []  # ✅ 使用本地變量

    for url in tqdm(url_list[start:end], desc=f"Reviews {start}-{end}"):
        try:
            # 獲取第一頁以確定總頁數
            first_page_url = f'{url}/tastes/?page=1'
            response = safe_request(first_page_url)

            if response is None:
                continue

            # ✅ 指定解析器
            soup = BeautifulSoup(response.text, 'lxml')

            # 獲取總頁數
            try:
                pagination_text = soup.find('span', {'class': 'pagination-control__description'}).string.strip()
                total_reviews = int(pagination_text.split(' ')[3])
                page_count = math.ceil(total_reviews / 10)
            except (AttributeError, ValueError, IndexError):
                page_count = 1

            # 爬取所有頁面
            for page in range(1, page_count + 1):
                page_url = f'{url}/tastes/?page={page}'

                # ✅ 添加超時
                response = safe_request(page_url)

                if response is None:
                    continue

                soup = BeautifulSoup(response.text, 'lxml')

                try:
                    # 提取產品名稱
                    product_elem = soup.find('h1', {'itemprop': 'name'})
                    product_name = product_elem.string.strip() if product_elem else None

                    # 提取用戶名
                    users = soup.find_all('h3', {'class': 'mini-headline name username truncate-line'})

                    # 提取評分
                    user_ratings = soup.find_all('div', {'class': 'rating-display__value'})

                    # 提取評論
                    user_comments = soup.find_all('div', {'class': 'body'})

                    # 組合數據
                    for index, user in enumerate(users):
                        user_review = {
                            'product': None,
                            'user': None,
                            'user_rating': None,
                            'user_comment': None
                        }

                        try:
                            user_review['product'] = product_name
                        except:
                            pass

                        try:
                            user_review['user'] = user.string.strip()
                        except:
                            pass

                        try:
                            user_review['user_rating'] = float(user_ratings[index].string)
                        except (IndexError, ValueError):
                            pass

                        try:
                            comment_text = user_comments[index].string
                            if comment_text:
                                # 移除換行符
                                user_review['user_comment'] = re.sub('[\r\n]', '', comment_text.strip())
                        except (IndexError, AttributeError):
                            pass

                        user_reviews.append(user_review)

                except Exception as e:
                    logger.exception(f"Error parsing page {page} of {url}: {e}")
                    continue

            # 請求延遲
            time.sleep(CONFIG['delay'])

        except KeyboardInterrupt:
            logger.info("User interrupted crawling")
            raise

        except Exception as e:
            logger.exception(f"Error processing {url}: {e}")
            continue

    return user_reviews  # ✅ 返回本地列表


def crawl_reviews_multi_threaded(url_list: List[str], num_threads: int = 10) -> List[Dict[str, Any]]:
    """
    多線程爬取評論（修復後的版本）

    ✅ 使用 Queue 收集結果，不依賴全局變量

    Args:
        url_list: URL 列表
        num_threads: 線程數

    Returns:
        所有評論列表
    """
    result_queue = Queue()  # ✅ 線程安全的隊列

    def worker(urls: List[str], start: int, end: int, queue: Queue):
        """工作線程函數"""
        reviews = get_user_reviews(urls, start, end)
        queue.put(reviews)

    # 分割 URL 列表
    chunk_size = len(url_list) // num_threads
    threads = []

    for i in range(num_threads):
        start = i * chunk_size
        end = (i + 1) * chunk_size if i < num_threads - 1 else len(url_list)

        thread = Thread(target=worker, args=(url_list, start, end, result_queue))
        threads.append(thread)
        thread.start()
        logger.info(f"Started thread {i + 1}/{num_threads} for URLs {start}-{end}")

    # 等待所有線程完成
    for i, thread in enumerate(threads):
        thread.join()
        logger.info(f"Thread {i + 1}/{num_threads} finished")

    # 收集所有結果
    all_reviews = []
    while not result_queue.empty():
        reviews = result_queue.get()
        all_reviews.extend(reviews)

    logger.info(f"Total reviews crawled: {len(all_reviews)}")

    return all_reviews


if __name__ == '__main__':
    # 測試用例
    test_urls = [
        'https://distiller.com/spirits/makers-mark-bourbon',
        'https://distiller.com/spirits/glenlivet-12-year',
    ]

    logger.info("Testing review crawler fixes...")

    # 測試單線程
    logger.info("Test: Single-threaded review crawling")
    reviews = get_user_reviews(test_urls, 0, len(test_urls))

    print(f"\n✅ Successfully crawled {len(reviews)} reviews")
    if reviews:
        print(f"✅ Sample review: {reviews[0]}")
