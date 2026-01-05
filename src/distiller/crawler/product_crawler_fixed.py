"""
修復後的 Distiller 產品爬蟲

修復內容：
1. ✅ 修復多線程鎖錯誤 - 使用全局鎖
2. ✅ 修復無限重試循環 - 添加重試次數限制
3. ✅ 添加請求超時 - 所有請求都有 30 秒超時
4. ✅ 指定 BeautifulSoup 解析器 - 使用 lxml
5. ✅ 改進異常處理 - 區分不同錯誤類型
"""

import requests
import re
import time
import math
import threading
import logging
from typing import List, Dict, Any
from tqdm import tqdm
from bs4 import BeautifulSoup

# =====================================
# 全局變量和鎖（修復問題 1）
# =====================================
data = []
exec_count = 0
data_lock = threading.Lock()  # ✅ 全局鎖，所有線程共用

# =====================================
# 配置
# =====================================
CONFIG = {
    'timeout': 30,          # 請求超時（秒）
    'delay': 3,             # 請求延遲（秒）
    'max_retries': 3,       # 最大重試次數
    'backoff_factor': 1,    # 退避因子
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36",
    "Connection": "keep-alive",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.8"
}

# =====================================
# 日誌設置
# =====================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/crawler_fixed.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def safe_request(url: str, max_retries: int = None, timeout: int = None) -> requests.Response:
    """
    安全的 HTTP 請求（修復問題 2 和 4）

    Args:
        url: 請求 URL
        max_retries: 最大重試次數
        timeout: 超時時間（秒）

    Returns:
        Response 對象，失敗返回 None
    """
    if max_retries is None:
        max_retries = CONFIG['max_retries']
    if timeout is None:
        timeout = CONFIG['timeout']

    retry_count = 0

    # ✅ 修復問題 2：限制重試次數
    while retry_count < max_retries:
        try:
            # ✅ 修復問題 4：添加超時
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            return response

        except requests.Timeout:
            retry_count += 1
            logger.warning(f"Timeout for {url}, retry {retry_count}/{max_retries}")

            if retry_count >= max_retries:
                logger.error(f"Failed after {max_retries} timeouts: {url}")
                return None

            # ✅ 指數退避
            wait_time = CONFIG['delay'] * (retry_count * CONFIG['backoff_factor'])
            time.sleep(wait_time)

        except requests.HTTPError as e:
            status_code = e.response.status_code

            # 4xx 錯誤通常不需要重試
            if 400 <= status_code < 500:
                logger.error(f"HTTP {status_code} for {url}")
                return None

            # 5xx 錯誤可以重試
            retry_count += 1
            logger.warning(f"HTTP {status_code} for {url}, retry {retry_count}/{max_retries}")

            if retry_count >= max_retries:
                logger.error(f"Failed after {max_retries} HTTP errors: {url}")
                return None

            time.sleep(CONFIG['delay'])

        except requests.RequestException as e:
            logger.error(f"Request error for {url}: {e}")
            return None

        except KeyboardInterrupt:
            logger.info("User interrupted crawling")
            raise

    return None


def extract_spirit_info(url: str) -> Dict[str, Any]:
    """
    從 URL 提取酒類資訊

    Args:
        url: 產品頁面 URL

    Returns:
        酒類資訊字典，失敗返回 None
    """
    response = safe_request(url)
    if response is None:
        return None

    try:
        # ✅ 指定解析器
        soup = BeautifulSoup(response.text, 'lxml')

        spirit_info = {
            'name': '',
            'type': '',
            'brand_name': '',
            'origin': '',
            'cost_level': 0,
            'age': 0,
            'abv': 0,
            'expert_rating': 0,
            'average_user_rating': 0,
            'user_comments': 0,
            'description': '',
            'tasting_notes': '',
            'reviewer': '',
            'flavor_profile': '',
        }

        # 提取各個欄位
        try:
            spirit_info['name'] = soup.find('h1', {'itemprop': 'name'}).string.strip()
        except AttributeError:
            logger.warning(f"Missing name for {url}")

        try:
            spirit_info['type'] = soup.find('h2', {'class': 'ultra-mini-headline type'}).string.strip()
        except AttributeError:
            logger.warning(f"Missing type for {url}")

        try:
            brand_info = soup.find('h2', {'itemprop': 'brand_name'}).string.strip()
            parts = brand_info.split(' // ')
            spirit_info['brand_name'] = parts[0]
            spirit_info['origin'] = parts[1] if len(parts) > 1 else brand_info
        except (AttributeError, IndexError):
            pass

        try:
            cost_str = str(soup.find('div', {'class': 'value'}))
            cost_index = cost_str.index('cost-') + 5
            spirit_info['cost_level'] = int(cost_str[cost_index])
        except (ValueError, AttributeError):
            pass

        try:
            age_text = soup.find('li', class_='detail age').getText().strip().split(' ')[-1]
            spirit_info['age'] = int(age_text)
        except (AttributeError, ValueError):
            spirit_info['age'] = None

        try:
            abv = soup.find('li', class_='detail abv').getText()[5:].strip()
            if abv.replace('.', '').isnumeric():
                spirit_info['abv'] = float(abv)
            else:
                spirit_info['abv'] = abv
        except (AttributeError, ValueError):
            spirit_info['abv'] = None

        try:
            rating_str = str(soup.find('span', {'class': 'expert-rating'}))
            rating_index = rating_str.index('>') + 2
            spirit_info['expert_rating'] = int(rating_str[rating_index:rating_index+2])
        except (ValueError, AttributeError):
            spirit_info['expert_rating'] = None

        try:
            rating_value = soup.find('span', {'itemprop': 'ratingValue'}).string
            spirit_info['average_user_rating'] = round(float(rating_value) * 20, 2)
        except (AttributeError, ValueError):
            spirit_info['average_user_rating'] = None

        try:
            count_text = soup.find(('a', 'span'), {'class': 'count'}).string
            spirit_info['user_comments'] = int(count_text)
        except (AttributeError, ValueError):
            spirit_info['user_comments'] = 0

        try:
            spirit_info['description'] = soup.find('p', {'itemprop': 'description'}).string
        except AttributeError:
            spirit_info['description'] = None

        try:
            notes = soup.find('p', {'itemprop': 'reviewBody'}).string
            spirit_info['tasting_notes'] = notes.strip('"') if notes else None
        except AttributeError:
            spirit_info['tasting_notes'] = None

        try:
            spirit_info['reviewer'] = soup.find('a', {'itemprop': 'author'}).string.strip()
        except AttributeError:
            spirit_info['reviewer'] = None

        # 提取 flavor profile
        try:
            flavor_canvas = soup.find('canvas', {'class': 'js-flavor-profile-chart'})
            if flavor_canvas:
                flavor_data = str(flavor_canvas)
                raw_text = flavor_data.split('{')[1].split('}')[0]

                # 解析風味數據
                flavor_pairs = []
                word = ''
                for letter in raw_text:
                    if letter.isalpha() or letter == '_':
                        word += letter
                    elif letter.isnumeric():
                        word += letter
                    else:
                        if word:
                            flavor_pairs.append(word)
                        word = ''

                if word:
                    flavor_pairs.append(word)

                # 轉換為字典
                flavor_profile = {}
                for i in range(0, len(flavor_pairs), 2):
                    if i + 1 < len(flavor_pairs):
                        flavor_name = flavor_pairs[i]
                        flavor_value = int(flavor_pairs[i + 1].strip())
                        flavor_profile[flavor_name] = flavor_value

                spirit_info['flavor_profile'] = flavor_profile
        except (AttributeError, ValueError, IndexError) as e:
            spirit_info['flavor_profile'] = None
            logger.debug(f"No flavor profile for {url}: {e}")

        return spirit_info

    except Exception as e:
        logger.error(f"Error parsing {url}: {e}")
        return None


def crawl_product(url: str) -> bool:
    """
    爬取單個產品並添加到全局數據列表

    Args:
        url: 產品 URL

    Returns:
        成功返回 True，失敗返回 False
    """
    global exec_count, data

    spirit_info = extract_spirit_info(url)

    if spirit_info is None:
        return False

    # 請求延遲
    time.sleep(CONFIG['delay'])

    # ✅ 修復問題 1：使用全局鎖保護共享資源
    with data_lock:
        data.append(spirit_info)
        exec_count += 1
        current_count = exec_count

    # 日誌（在鎖外執行）
    if current_count % 10 == 0:
        logger.info(f'Parsed {current_count} products')

    return True


def main(url_list: List[str], start: int = 0, end: int = None) -> None:
    """
    主爬取函數（修復後的版本）

    Args:
        url_list: URL 列表
        start: 起始索引
        end: 結束索引
    """
    if end is None:
        end = len(url_list)

    urls_to_crawl = url_list[start:end]

    logger.info(f"Starting to crawl {len(urls_to_crawl)} URLs (from {start} to {end})")

    for url in tqdm(urls_to_crawl, desc=f"Thread {start}-{end}"):
        try:
            crawl_product(url)
        except KeyboardInterrupt:
            logger.info("Crawling interrupted by user")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error for {url}: {e}")
            continue

    logger.info(f"Finished crawling URLs {start} to {end}")


def crawl_multi_threaded(url_list: List[str], num_threads: int = 10) -> List[Dict[str, Any]]:
    """
    多線程爬取（修復後的版本）

    Args:
        url_list: URL 列表
        num_threads: 線程數

    Returns:
        爬取的數據列表
    """
    global data, exec_count

    # 重置全局變量
    data = []
    exec_count = 0

    # 分割 URL 列表
    chunk_size = len(url_list) // num_threads
    threads = []

    for i in range(num_threads):
        start = i * chunk_size
        end = (i + 1) * chunk_size if i < num_threads - 1 else len(url_list)

        thread = threading.Thread(target=main, args=(url_list, start, end))
        threads.append(thread)
        thread.start()
        logger.info(f"Started thread {i + 1}/{num_threads} for URLs {start}-{end}")

    # 等待所有線程完成
    for i, thread in enumerate(threads):
        thread.join()
        logger.info(f"Thread {i + 1}/{num_threads} finished")

    logger.info(f"All threads finished. Total products crawled: {len(data)}")

    return data


if __name__ == '__main__':
    # 測試用例
    test_urls = [
        'https://distiller.com/spirits/makers-mark-bourbon',
        'https://distiller.com/spirits/glenlivet-12-year',
        'https://distiller.com/spirits/tanqueray-london-dry-gin',
    ]

    logger.info("Testing crawler fixes...")

    # 測試單線程
    logger.info("Test 1: Single-threaded crawling")
    main(test_urls, 0, len(test_urls))

    print(f"\n✅ Successfully crawled {len(data)} products")
    print(f"✅ Products: {[d.get('name', 'Unknown') for d in data]}")
