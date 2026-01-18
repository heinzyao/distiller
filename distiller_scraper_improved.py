#!/usr/bin/env python3
"""
Distiller.com 改進版爬蟲
- 支持自適應速率限制
- 改進的錯誤處理和重試機制
- 詳細的日誌記錄
- 支持多種 CSS 選擇器 fallback
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
from urllib.parse import urljoin
import logging
from datetime import datetime

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("distiller_scraper.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class DistillerScraperImproved:
    def __init__(self, initial_delay_min=2, initial_delay_max=5):
        self.base_url = "https://distiller.com"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        self.spirits_data = []
        self.delay_min = initial_delay_min
        self.delay_max = initial_delay_max
        self.consecutive_429 = 0
        self.consecutive_200 = 0
        self.failed_urls = []

    def adjust_delay(self, status_code):
        """自適應調整請求延遲"""
        if status_code == 429:
            self.consecutive_429 += 1
            self.consecutive_200 = 0
            if self.consecutive_429 >= 3:
                self.delay_min = min(self.delay_min + 5, 30)
                self.delay_max = min(self.delay_max + 10, 60)
                logger.warning(
                    f"速率限制觸發！調整延遲到 {self.delay_min}-{self.delay_max} 秒"
                )
                self.consecutive_429 = 0
        elif status_code == 200:
            self.consecutive_200 += 1
            self.consecutive_429 = 0
            if self.consecutive_200 >= 10 and self.delay_min > 2:
                self.delay_min = max(self.delay_min - 1, 2)
                self.delay_max = max(self.delay_max - 2, 5)
                logger.info(
                    f"速率穩定，適度減少延遲到 {self.delay_min}-{self.delay_max} 秒"
                )
                self.consecutive_200 = 0

    def make_request(self, url, max_retries=3):
        """發送請求並處理錯誤"""
        for attempt in range(max_retries):
            try:
                logger.info(f"請求: {url} (嘗試 {attempt + 1}/{max_retries})")
                response = self.session.get(url, timeout=30)
                self.adjust_delay(response.status_code)

                if response.status_code == 429:
                    wait_time = (2**attempt) * 30  # 指數退避
                    logger.warning(f"遇到速率限制，等待 {wait_time} 秒...")
                    time.sleep(wait_time)
                    continue
                elif response.status_code == 403:
                    logger.error(f"訪問被拒絕 (403): {url}")
                    return None
                elif response.status_code == 404:
                    logger.warning(f"頁面不存在 (404): {url}")
                    return None
                elif response.status_code == 200:
                    return response
                else:
                    logger.warning(f"非預期狀態碼 {response.status_code}: {url}")
                    time.sleep(5)
                    continue

            except requests.exceptions.RequestException as e:
                logger.error(f"請求錯誤: {e}")
                if attempt < max_retries - 1:
                    time.sleep(10)
                    continue
                else:
                    return None

        self.failed_urls.append(url)
        return None

    def get_category_urls(self):
        """獲取所有烈酒類別的 URL"""
        categories = [
            "whiskey",
            "tequila-mezcal",
            "rum",
            "brandy",
            "gin",
            "vodka",
            "liqueurs-bitters",
        ]
        return [f"{self.base_url}/search?category={cat}" for cat in categories]

    def extract_with_fallback(self, soup, selectors, attribute="text"):
        """使用多個選擇器嘗試提取數據"""
        for selector in selectors:
            try:
                if isinstance(selector, tuple):
                    # (tag, attrs) 格式
                    elem = soup.find(selector[0], selector[1])
                else:
                    # CSS selector 格式
                    elem = soup.select_one(selector)

                if elem:
                    if attribute == "text":
                        return elem.get_text(strip=True)
                    else:
                        return elem.get(attribute)
            except Exception as e:
                continue
        return "N/A"

    def scrape_spirit_page(self, spirit_url):
        """爬取單個烈酒頁面的詳細資訊"""
        response = self.make_request(spirit_url)
        if not response:
            return None

        try:
            soup = BeautifulSoup(response.content, "html.parser")

            # 提取品名 - 多個選擇器嘗試
            name = self.extract_with_fallback(
                soup,
                [
                    "h1",
                    ("h1", {"class": "spirit-name"}),
                    ("h1", {"class": "product-name"}),
                    ("h2", {"class": "spirit-title"}),
                    '[data-testid="spirit-name"]',
                    ".spirit-header h1",
                    ".product-title",
                ],
            )

            # 如果無法獲取品名，這條記錄無效
            if name == "N/A":
                logger.warning(f"無法提取品名: {spirit_url}")
                return None

            # 提取類別
            category = self.extract_with_fallback(
                soup,
                [
                    ("span", {"class": "category"}),
                    ("div", {"class": "spirit-type"}),
                    ("span", {"class": "spirit-category"}),
                    ".breadcrumb .active",
                    '[itemprop="category"]',
                ],
            )

            # 提取產地
            origin = self.extract_with_fallback(
                soup,
                [
                    ("span", {"class": "origin"}),
                    ("div", {"class": "location"}),
                    ("span", {"class": "distillery-location"}),
                    '[itemprop="location"]',
                    ".origin-info",
                ],
            )

            # 提取年份
            age = self.extract_with_fallback(
                soup,
                [
                    ("span", {"class": "age"}),
                    ("div", {"class": "age-statement"}),
                    ("span", {"data-age": True}),
                    ".age-info",
                ],
            )

            # 提取專家評分
            expert_score = self.extract_with_fallback(
                soup,
                [
                    ("div", {"class": "expert-score"}),
                    ("span", {"class": "distiller-score"}),
                    ("div", {"class": "rating-score"}),
                    "[data-expert-score]",
                    ".expert-rating",
                ],
            )

            # 提取社群評分
            community_score = self.extract_with_fallback(
                soup,
                [
                    ("div", {"class": "user-rating"}),
                    ("span", {"class": "community-score"}),
                    ("div", {"class": "user-score"}),
                    "[data-community-score]",
                    ".community-rating",
                ],
            )

            # 提取風味圖譜
            flavor_elems = (
                soup.find_all("span", class_="flavor-tag")
                or soup.find_all("div", class_="flavor")
                or soup.select(".flavor-profile .tag")
            )

            flavors = [
                elem.get_text(strip=True)
                for elem in flavor_elems
                if elem.get_text(strip=True)
            ]
            flavor_profile = ", ".join(flavors) if flavors else "N/A"

            spirit_data = {
                "name": name,
                "category": category,
                "origin": origin,
                "age": age,
                "expert_score": expert_score,
                "community_score": community_score,
                "flavor_profile": flavor_profile,
                "url": spirit_url,
            }

            logger.info(f"✓ 成功爬取: {name}")
            return spirit_data

        except Exception as e:
            logger.error(f"解析頁面時發生錯誤 {spirit_url}: {e}")
            return None

    def scrape_category(self, category_url, max_pages=None, max_spirits=None):
        """爬取特定類別的烈酒"""
        page = 1
        spirits_count = 0

        while True:
            if max_pages and page > max_pages:
                logger.info(f"達到最大頁數限制 ({max_pages})")
                break

            url = f"{category_url}&page={page}"
            response = self.make_request(url)

            if not response:
                logger.warning(f"無法獲取頁面: {url}")
                break

            soup = BeautifulSoup(response.content, "html.parser")

            # 尋找烈酒連結 - 多種模式嘗試
            spirit_links = set()

            # 模式 1: 直接查找包含 /spirits/ 的連結
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if (
                    "/spirits/" in href
                    and not href.endswith("/spirits/")
                    and not href.endswith("/spirits")
                ):
                    full_url = urljoin(self.base_url, href)
                    spirit_links.add(full_url)

            # 模式 2: 查找特定的卡片或項目
            for selector in [
                ".spirit-card a",
                ".product-card a",
                ".spirit-item a",
                "article a",
            ]:
                for link in soup.select(selector):
                    href = link.get("href")
                    if href and "/spirits/" in href:
                        full_url = urljoin(self.base_url, href)
                        spirit_links.add(full_url)

            if not spirit_links:
                logger.info(f"在 {url} 中未找到更多烈酒連結，停止該類別爬取")
                break

            logger.info(f"在第 {page} 頁找到 {len(spirit_links)} 個烈酒連結")

            for spirit_url in spirit_links:
                if max_spirits and spirits_count >= max_spirits:
                    logger.info(f"達到最大烈酒數量限制 ({max_spirits})")
                    return

                spirit_data = self.scrape_spirit_page(spirit_url)
                if spirit_data:
                    self.spirits_data.append(spirit_data)
                    spirits_count += 1
                    logger.info(f"進度: {spirits_count} 條記錄已爬取")

                # 隨機延遲
                delay = random.uniform(self.delay_min, self.delay_max)
                logger.debug(f"等待 {delay:.2f} 秒...")
                time.sleep(delay)

            page += 1

    def scrape_limited(self, max_spirits_per_category=None, categories_limit=None):
        """限制爬取範圍的方法"""
        category_urls = self.get_category_urls()

        if categories_limit:
            category_urls = category_urls[:categories_limit]

        for i, category_url in enumerate(category_urls):
            logger.info(f"\n{'=' * 60}")
            logger.info(f"正在處理類別 {i + 1}/{len(category_urls)}: {category_url}")
            logger.info(f"{'=' * 60}\n")

            self.scrape_category(category_url, max_spirits=max_spirits_per_category)

            # 類別間延遲
            if i < len(category_urls) - 1:
                delay = random.uniform(5, 10)
                logger.info(f"類別間等待 {delay:.2f} 秒...\n")
                time.sleep(delay)

    def save_to_csv(self, filename="distiller_spirits.csv"):
        """將資料儲存為 CSV 檔案"""
        if not self.spirits_data:
            logger.warning("沒有資料可儲存")
            return False

        try:
            df = pd.DataFrame(self.spirits_data)
            df.to_csv(filename, index=False, encoding="utf-8-sig")
            logger.info(f"\n{'=' * 60}")
            logger.info(f"✓ 資料已儲存至 {filename}")
            logger.info(f"✓ 總共 {len(self.spirits_data)} 條記錄")
            logger.info(f"{'=' * 60}\n")
            return True
        except Exception as e:
            logger.error(f"儲存 CSV 時發生錯誤: {e}")
            return False

    def get_statistics(self):
        """獲取爬蟲統計信息"""
        if not self.spirits_data:
            return "無數據"

        df = pd.DataFrame(self.spirits_data)
        stats = {
            "總記錄數": len(df),
            "失敗 URL 數": len(self.failed_urls),
            "各欄位空值率": {
                col: f"{(df[col] == 'N/A').sum() / len(df) * 100:.1f}%"
                for col in df.columns
                if col != "url"
            },
            "類別分布": df["category"].value_counts().to_dict()
            if "category" in df.columns
            else {},
        }
        return stats


def run_phase1_test():
    """Phase 1: 小規模可行性測試"""
    logger.info("\n" + "=" * 80)
    logger.info("開始 Phase 1: 小規模可行性測試 (目標: 5-10 條記錄)")
    logger.info("=" * 80 + "\n")

    scraper = DistillerScraperImproved(initial_delay_min=3, initial_delay_max=5)

    # 只爬取一個類別，限制最多 10 條記錄
    scraper.scrape_limited(max_spirits_per_category=10, categories_limit=1)

    # 保存結果
    success = scraper.save_to_csv("distiller_phase1_test.csv")

    # 顯示統計
    if success:
        stats = scraper.get_statistics()
        logger.info("\nPhase 1 統計結果:")
        logger.info(f"總記錄數: {stats['總記錄數']}")
        logger.info(f"失敗 URL 數: {stats['失敗 URL 數']}")
        logger.info(f"空值率: {stats['各欄位空值率']}")

    return scraper, success


def run_phase2_test():
    """Phase 2: 中等規模測試"""
    logger.info("\n" + "=" * 80)
    logger.info("開始 Phase 2: 中等規模測試 (目標: 100-500 條記錄)")
    logger.info("=" * 80 + "\n")

    scraper = DistillerScraperImproved(initial_delay_min=3, initial_delay_max=5)

    # 爬取 3-4 個類別，每個類別約 50-150 條記錄
    scraper.scrape_limited(max_spirits_per_category=150, categories_limit=4)

    # 保存結果
    success = scraper.save_to_csv("distiller_phase2_test.csv")

    # 顯示統計
    if success:
        stats = scraper.get_statistics()
        logger.info("\nPhase 2 統計結果:")
        logger.info(f"總記錄數: {stats['總記錄數']}")
        logger.info(f"失敗 URL 數: {stats['失敗 URL 數']}")
        logger.info(f"類別分布: {stats['類別分布']}")
        logger.info(f"空值率: {stats['各欄位空值率']}")

    return scraper, success


def run_full_scraper():
    """Phase 3: 完整爬蟲運行"""
    logger.info("\n" + "=" * 80)
    logger.info("開始 Phase 3: 完整爬蟲運行 (目標: 100-500 條記錄)")
    logger.info("=" * 80 + "\n")

    scraper = DistillerScraperImproved(initial_delay_min=3, initial_delay_max=5)

    # 中等規模：限制總記錄數在 100-500 之間
    scraper.scrape_limited(max_spirits_per_category=100, categories_limit=7)

    # 保存結果
    success = scraper.save_to_csv("distiller_spirits_reviews_NEW.csv")

    # 顯示統計
    if success:
        stats = scraper.get_statistics()
        logger.info("\n最終統計結果:")
        logger.info(f"總記錄數: {stats['總記錄數']}")
        logger.info(f"失敗 URL 數: {stats['失敗 URL 數']}")
        logger.info(f"類別分布: {stats['類別分布']}")
        logger.info(f"空值率: {stats['各欄位空值率']}")

        if scraper.failed_urls:
            logger.warning(f"\n失敗的 URLs ({len(scraper.failed_urls)}):")
            for url in scraper.failed_urls[:10]:
                logger.warning(f"  - {url}")

    return scraper, success


if __name__ == "__main__":
    logger.info(f"\n開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 根據需要執行不同的 phase
    # 測試時可以逐個執行，確認後再運行完整版本

    # Phase 1: 小規模測試
    # scraper, success = run_phase1_test()

    # Phase 2: 中等規模測試
    # scraper, success = run_phase2_test()

    # Phase 3: 完整運行
    scraper, success = run_full_scraper()

    logger.info(f"\n結束時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
