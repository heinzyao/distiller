#!/usr/bin/env python3
"""
Distiller.com 爬蟲 V2
改進版本 - 基於 2026-01-27 驗證的 CSS 選擇器
支援：
- 正確的 CSS 選擇器提取完整資料
- 去重處理
- 分頁與風格篩選擴大爬取範圍
- 詳細的風味圖譜提取
"""

import json
import logging
import random
import time
from datetime import datetime
from typing import Dict, List, Optional, Set

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from .config import ScraperConfig
from .selectors import DataExtractor, Selectors

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("distiller_scraper_v2.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class DistillerScraperV2:
    """改進版 Distiller.com 爬蟲"""

    def __init__(
        self,
        headless: bool = True,
        delay_min: float = 2,
        delay_max: float = 4,
    ):
        self.headless = headless
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.driver: Optional[webdriver.Chrome] = None
        self.spirits_data: List[Dict] = []
        self.failed_urls: List[str] = []
        self.seen_urls: Set[str] = set()  # 去重用

    def start_driver(self) -> bool:
        """啟動 Chrome WebDriver"""
        try:
            logger.info("正在啟動 Chrome WebDriver...")
            options = ChromeOptions()

            if self.headless:
                options.add_argument("--headless=new")

            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument(f"--window-size={ScraperConfig.WINDOW_SIZE}")
            options.add_argument(f"user-agent={ScraperConfig.USER_AGENT}")

            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(ScraperConfig.PAGE_LOAD_TIMEOUT)

            logger.info("✓ Chrome WebDriver 已啟動")
            return True

        except Exception as e:
            logger.error(f"無法啟動 Chrome WebDriver: {e}")
            return False

    def close_driver(self):
        """關閉瀏覽器"""
        if self.driver:
            self.driver.quit()
            logger.info("瀏覽器已關閉")

    def random_delay(self, min_sec: float = None, max_sec: float = None):
        """隨機延遲"""
        min_sec = min_sec or self.delay_min
        max_sec = max_sec or self.delay_max
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    def scroll_page(self, max_scrolls: int = None):
        """滾動頁面載入更多內容"""
        max_scrolls = max_scrolls or ScraperConfig.MAX_SCROLL_ATTEMPTS
        last_height = self.driver.execute_script("return document.body.scrollHeight")

        for i in range(max_scrolls):
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            time.sleep(ScraperConfig.SCROLL_DELAY)

            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                logger.debug(f"滾動完成，共 {i + 1} 次")
                break
            last_height = new_height

    def extract_spirit_urls_from_list(self, soup: BeautifulSoup) -> List[str]:
        """從搜索結果頁面提取烈酒 URL"""
        urls = []
        items = soup.select(Selectors.SPIRIT_LIST_ITEM)

        for item in items:
            link = item.select_one("a")
            if link and link.get("href"):
                href = link["href"]
                if "/spirits/" in href:
                    full_url = (
                        f"https://distiller.com{href}" if href.startswith("/") else href
                    )
                    urls.append(full_url)

        return urls

    def restart_driver(self) -> bool:
        """重新啟動 Chrome WebDriver (用於 session 恢復)"""
        try:
            logger.info("正在重新啟動 Chrome WebDriver...")
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            time.sleep(2)
            return self.start_driver()
        except Exception as e:
            logger.error(f"重新啟動 WebDriver 失敗: {e}")
            return False

    def scrape_spirit_detail(self, url: str, retry_count: int = 0) -> Optional[Dict]:
        """爬取單個烈酒詳情頁"""
        if url in self.seen_urls:
            logger.debug(f"跳過重複 URL: {url}")
            return None

        max_retries = 3

        try:
            self.driver.get(url)
            time.sleep(2)  # 等待頁面載入

            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            # 使用 DataExtractor 提取完整資料
            data = DataExtractor.extract_spirit_details(soup)

            # 驗證必要欄位
            if data["name"] == "N/A" or not data["name"]:
                logger.warning(f"無法提取品名: {url}")
                self.failed_urls.append(url)
                return None

            # 添加 URL
            data["url"] = url

            # 標記為已處理
            self.seen_urls.add(url)

            logger.info(f"✓ 已爬取: {data['name']}")
            return data

        except Exception as e:
            error_msg = str(e)
            # 檢查是否為 session 斷開錯誤
            if "invalid session id" in error_msg or "session deleted" in error_msg:
                if retry_count < max_retries:
                    logger.warning(
                        f"Session 斷開，嘗試重新連接 (第 {retry_count + 1} 次)..."
                    )
                    if self.restart_driver():
                        time.sleep(2)
                        return self.scrape_spirit_detail(url, retry_count + 1)
                logger.error(f"重試 {max_retries} 次後仍失敗: {url}")
            else:
                logger.error(f"爬取錯誤 {url}: {e}")
            self.failed_urls.append(url)
            return None

    def scrape_category(
        self,
        category: str,
        max_spirits: int = None,
        use_styles: bool = False,
    ) -> List[Dict]:
        """爬取特定類別的烈酒"""
        max_spirits = max_spirits or ScraperConfig.MAX_SPIRITS_PER_CATEGORY
        results = []

        # 決定要使用的 URL 列表
        urls_to_scrape = []

        if use_styles and category == "whiskey":
            # 使用風格篩選來獲取更多結果
            for style_id, style_name in ScraperConfig.WHISKEY_STYLES:
                search_url = f"https://distiller.com/search?category={category}&spirit_style_id={style_id}&sort=distiller_score"
                urls_to_scrape.append((search_url, style_name))
        elif use_styles and category == "gin":
            for style_id, style_name in ScraperConfig.GIN_STYLES:
                search_url = f"https://distiller.com/search?category={category}&spirit_style_id={style_id}&sort=distiller_score"
                urls_to_scrape.append((search_url, style_name))
        elif use_styles and category == "rum":
            for style_id, style_name in ScraperConfig.RUM_STYLES:
                search_url = f"https://distiller.com/search?category={category}&spirit_style_id={style_id}&sort=distiller_score"
                urls_to_scrape.append((search_url, style_name))
        elif use_styles and category == "vodka":
            for style_id, style_name in ScraperConfig.VODKA_STYLES:
                search_url = f"https://distiller.com/search?category={category}&spirit_style_id={style_id}&sort=distiller_score"
                urls_to_scrape.append((search_url, style_name))
        else:
            # 基本搜索
            search_url = (
                f"https://distiller.com/search?category={category}&sort=distiller_score"
            )
            urls_to_scrape.append((search_url, category))

        for search_url, label in urls_to_scrape:
            if len(results) >= max_spirits:
                break

            logger.info(f"正在爬取: {label} ({search_url})")

            try:
                self.driver.get(search_url)
                time.sleep(ScraperConfig.INITIAL_PAGE_DELAY)

                # 滾動載入更多
                self.scroll_page()

                # 解析頁面
                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                spirit_urls = self.extract_spirit_urls_from_list(soup)

                logger.info(f"在 {label} 中找到 {len(spirit_urls)} 個烈酒連結")

                # 爬取每個烈酒詳情
                for i, spirit_url in enumerate(spirit_urls):
                    if len(results) >= max_spirits:
                        break

                    if spirit_url in self.seen_urls:
                        continue

                    logger.info(f"[{len(results) + 1}/{max_spirits}] 正在爬取詳情...")

                    spirit_data = self.scrape_spirit_detail(spirit_url)
                    if spirit_data:
                        spirit_data["category"] = category
                        results.append(spirit_data)

                    self.random_delay()

            except Exception as e:
                error_msg = str(e)
                # 檢查是否為 session 斷開錯誤
                if "invalid session id" in error_msg or "session deleted" in error_msg:
                    logger.warning(f"Session 斷開，嘗試重新連接...")
                    if self.restart_driver():
                        time.sleep(2)
                        # 重試當前風格
                        continue
                logger.error(f"爬取 {label} 時發生錯誤: {e}")
                continue

            # 類別間延遲
            if len(urls_to_scrape) > 1:
                time.sleep(ScraperConfig.CATEGORY_DELAY)

        return results

    def scrape(
        self,
        categories: List[str] = None,
        max_per_category: int = None,
        use_styles: bool = True,
    ):
        """執行爬蟲"""
        categories = categories or ScraperConfig.CATEGORIES
        max_per_category = max_per_category or ScraperConfig.MAX_SPIRITS_PER_CATEGORY

        start_time = datetime.now()
        logger.info(f"\n{'=' * 80}")
        logger.info(f"開始爬取 - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"類別: {categories}")
        logger.info(f"每類別上限: {max_per_category}")
        logger.info(f"使用風格篩選: {use_styles}")
        logger.info(f"{'=' * 80}\n")

        if not self.start_driver():
            return False

        try:
            for cat_idx, category in enumerate(categories, 1):
                logger.info(f"\n{'=' * 60}")
                logger.info(f"類別 {cat_idx}/{len(categories)}: {category}")
                logger.info(f"{'=' * 60}\n")

                category_results = self.scrape_category(
                    category,
                    max_spirits=max_per_category,
                    use_styles=use_styles,
                )
                self.spirits_data.extend(category_results)

                logger.info(f"類別 {category} 完成: {len(category_results)} 筆")

                if cat_idx < len(categories):
                    logger.info(f"等待 {ScraperConfig.CATEGORY_DELAY} 秒後繼續...\n")
                    time.sleep(ScraperConfig.CATEGORY_DELAY)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            logger.info(f"\n{'=' * 80}")
            logger.info(f"爬取完成！")
            logger.info(f"總筆數: {len(self.spirits_data)}")
            logger.info(f"失敗 URL 數: {len(self.failed_urls)}")
            logger.info(f"耗時: {duration / 60:.1f} 分鐘")
            logger.info(f"{'=' * 80}\n")

            return True

        except Exception as e:
            logger.error(f"爬蟲執行時發生錯誤: {e}")
            return False

        finally:
            self.close_driver()

    def to_dataframe(self) -> pd.DataFrame:
        """將資料轉換為 DataFrame"""
        if not self.spirits_data:
            return pd.DataFrame()

        # 展開 flavor_data 為字串
        df_data = []
        for item in self.spirits_data:
            row = item.copy()
            if "flavor_data" in row and isinstance(row["flavor_data"], dict):
                row["flavor_data"] = json.dumps(row["flavor_data"])
            df_data.append(row)

        return pd.DataFrame(df_data)

    def save_csv(self, filename: str = "distiller_spirits_v2.csv") -> bool:
        """儲存為 CSV"""
        if not self.spirits_data:
            logger.warning("沒有資料可儲存")
            return False

        try:
            df = self.to_dataframe()
            df.to_csv(filename, index=False, encoding=ScraperConfig.OUTPUT_ENCODING)
            logger.info(f"✓ 資料已儲存至 {filename}")
            logger.info(f"✓ 總共 {len(df)} 條記錄")
            return True

        except Exception as e:
            logger.error(f"儲存 CSV 時發生錯誤: {e}")
            return False

    def get_statistics(self) -> Dict:
        """獲取統計資訊"""
        if not self.spirits_data:
            return {"總記錄數": 0}

        df = self.to_dataframe()

        # 計算各欄位的有效率
        field_stats = {}
        for col in df.columns:
            if col in ["url", "flavor_data"]:
                continue
            valid_count = (
                (df[col] != "N/A") & (df[col] != "") & (df[col].notna())
            ).sum()
            field_stats[col] = (
                f"{valid_count}/{len(df)} ({valid_count / len(df) * 100:.1f}%)"
            )

        return {
            "總記錄數": len(df),
            "失敗 URL 數": len(self.failed_urls),
            "類別分布": df["category"].value_counts().to_dict()
            if "category" in df.columns
            else {},
            "欄位有效率": field_stats,
        }


def run_test_scrape():
    """測試爬取 (少量)"""
    scraper = DistillerScraperV2(headless=True)

    scraper.scrape(
        categories=["whiskey"],
        max_per_category=5,
        use_styles=False,
    )

    scraper.save_csv("distiller_test_v2.csv")
    stats = scraper.get_statistics()
    logger.info(f"\n統計:\n{json.dumps(stats, indent=2, ensure_ascii=False)}")


def run_medium_scrape():
    """中等規模爬取"""
    scraper = DistillerScraperV2(headless=True)

    scraper.scrape(
        categories=["whiskey", "gin", "rum", "vodka"],
        max_per_category=50,
        use_styles=True,
    )

    scraper.save_csv("distiller_spirits_v2.csv")
    stats = scraper.get_statistics()
    logger.info(f"\n統計:\n{json.dumps(stats, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    run_test_scrape()
