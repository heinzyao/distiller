#!/usr/bin/env python3
"""
Distiller.com Selenium 爬蟲 (Chrome 版本 - macOS 相容)
由於 Distiller.com 使用 JavaScript 動態載入內容，必須使用 Selenium
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import logging
from datetime import datetime

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("distiller_selenium_scraper.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class DistillerSeleniumScraper:
    def __init__(self, headless=False, delay_min=3, delay_max=5):
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.spirits_data = []
        self.failed_urls = []
        self.driver = None
        self.headless = headless

    def start_driver(self):
        """啟動 Chrome 瀏覽器"""
        try:
            logger.info("正在初始化 Chrome WebDriver...")

            options = ChromeOptions()
            if self.headless:
                options.add_argument("--headless=new")
            options.add_argument("--start-maximized")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument(
                "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            # 自動下載並啟動 Chrome WebDriver
            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(60)  # 增加頁面載入超時時間
            self.wait = WebDriverWait(self.driver, 30)  # 增加元素等待時間

            logger.info("✓ Chrome WebDriver 已成功啟動")
            return True

        except Exception as e:
            logger.error(f"無法啟動 Chrome WebDriver: {e}")
            logger.info("提示: 請確保 Chrome 瀏覽器已安裝")
            return False

    def close_driver(self):
        """關閉瀏覽器"""
        if self.driver:
            self.driver.quit()
            logger.info("瀏覽器已關閉")

    def handle_cookie_banner(self):
        """處理 Cookie 同意橫幅"""
        try:
            # 嘗試多種可能的 Cookie 按鈕選擇器
            cookie_selectors = [
                "//button[contains(text(), 'Accept')]",
                "//button[contains(text(), 'Agree')]",
                "//button[contains(@aria-label, 'Accept')]",
                "//a[contains(@class, 'cookie-accept')]",
                "//button[@id='cookie-accept']",
            ]

            for selector in cookie_selectors:
                try:
                    button = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    button.click()
                    logger.info("✓ 已接受 Cookie")
                    time.sleep(2)
                    return
                except:
                    continue

            logger.info("未找到 Cookie 按鈕（可能已接受或不存在）")
        except Exception as e:
            logger.debug(f"處理 Cookie 時發生錯誤: {e}")

    def scroll_to_load_all(self):
        """滾動頁面以載入所有內容"""
        logger.info("正在滾動頁面以載入更多內容...")
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        max_scrolls = 10

        while scroll_attempts < max_scrolls:
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            time.sleep(3)

            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                logger.info("✓ 已到達頁面底部")
                break

            last_height = new_height
            scroll_attempts += 1
            logger.debug(f"滾動嘗試 {scroll_attempts}/{max_scrolls}")

    def extract_spirit_data(self, spirit_url):
        """提取單個烈酒的數據"""
        try:
            logger.info(f"正在抓取: {spirit_url}")
            self.driver.get(spirit_url)

            # 等待頁面載入
            time.sleep(3)

            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            # 提取品名
            name = "N/A"
            for selector in ["h1", "h1.spirit-name", "h2.product-title"]:
                elem = soup.select_one(selector)
                if elem:
                    name = elem.get_text(strip=True)
                    if name and name != "N/A":
                        break

            if name == "N/A":
                logger.warning(f"無法提取品名: {spirit_url}")
                return None

            # 提取類別
            category = "N/A"
            for selector in [".category", ".spirit-category", ".breadcrumb li"]:
                elem = soup.select_one(selector)
                if elem:
                    category = elem.get_text(strip=True)
                    if category and category != "N/A":
                        break

            # 提取產地
            origin = "N/A"
            for keyword in ["Distillery:", "Origin:", "Country:", "Region:"]:
                elements = soup.find_all(text=lambda text: text and keyword in text)
                for elem in elements:
                    parent = elem.parent
                    if parent:
                        text = parent.get_text(strip=True)
                        if ":" in text:
                            origin = text.split(":", 1)[1].strip()
                            break
                if origin != "N/A":
                    break

            # 提取年份/陳年
            age = "N/A"
            for keyword in ["Age:", "Years:", "Aged:"]:
                elements = soup.find_all(text=lambda text: text and keyword in text)
                for elem in elements:
                    parent = elem.parent
                    if parent:
                        text = parent.get_text(strip=True)
                        if ":" in text:
                            age = text.split(":", 1)[1].strip()
                            break
                if age != "N/A":
                    break

            # 提取評分
            expert_score = "N/A"
            community_score = "N/A"

            # 嘗試提取評分（多種方式）
            for selector in [".rating", ".score", ".expert-score", "[data-score]"]:
                elem = soup.select_one(selector)
                if elem:
                    score_text = elem.get_text(strip=True)
                    if "expert" in selector.lower() or "official" in selector.lower():
                        expert_score = score_text
                    elif "community" in selector.lower() or "user" in selector.lower():
                        community_score = score_text

            # 提取風味標籤
            flavor_elems = soup.select(".flavor-tag, .tag, .flavor-note")
            flavors = [
                elem.get_text(strip=True)
                for elem in flavor_elems
                if elem.get_text(strip=True)
            ]
            flavor_profile = (
                ", ".join(flavors[:10]) if flavors else "N/A"
            )  # 限制最多10個風味

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

            logger.info(f"✓ 成功抓取: {name}")
            return spirit_data

        except Exception as e:
            logger.error(f"提取數據時發生錯誤 {spirit_url}: {e}")
            self.failed_urls.append(spirit_url)
            return None

    def scrape_category(self, category_url, max_spirits=None):
        """爬取特定類別的烈酒"""
        try:
            logger.info(f"\n{'=' * 60}")
            logger.info(f"正在處理類別: {category_url}")
            logger.info(f"{'=' * 60}")

            logger.info(f"正在載入頁面: {category_url}")
            self.driver.get(category_url)
            time.sleep(5)  # 增加初始等待時間

            logger.info("頁面已載入，嘗試處理 Cookie...")
            # 處理 Cookie
            self.handle_cookie_banner()

            # 滾動載入內容
            self.scroll_to_load_all()

            # 獲取頁面 HTML
            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            # 尋找烈酒連結
            spirit_urls = set()

            # 多種模式尋找連結
            for link in soup.find_all("a", href=True):
                href = link["href"]
                # 尋找包含 /spirits/ 的連結，但排除類別頁面
                if (
                    "/spirits/" in href
                    and not href.endswith("/spirits/")
                    and not href.endswith("/spirits")
                ):
                    if href.startswith("http"):
                        spirit_urls.add(href)
                    else:
                        spirit_urls.add(f"https://distiller.com{href}")

            logger.info(f"找到 {len(spirit_urls)} 個烈酒連結")

            if not spirit_urls:
                logger.warning("未找到任何烈酒連結")
                return

            # 限制爬取數量
            if max_spirits:
                spirit_urls = list(spirit_urls)[:max_spirits]
                logger.info(f"限制爬取數量為 {max_spirits} 條")

            # 爬取每個烈酒
            for i, spirit_url in enumerate(spirit_urls, 1):
                logger.info(f"\n進度: {i}/{len(spirit_urls)}")

                spirit_data = self.extract_spirit_data(spirit_url)
                if spirit_data:
                    self.spirits_data.append(spirit_data)

                # 隨機延遲
                if i < len(spirit_urls):
                    delay = random.uniform(self.delay_min, self.delay_max)
                    logger.debug(f"等待 {delay:.2f} 秒...")
                    time.sleep(delay)

        except Exception as e:
            logger.error(f"爬取類別時發生錯誤: {e}")

    def scrape_limited(self, categories_limit=1, max_spirits_per_category=10):
        """限制範圍的爬取"""
        categories = [
            "whiskey",
            "gin",
            "rum",
            "vodka",
            "tequila-mezcal",
            "brandy",
            "liqueurs-bitters",
        ]

        if categories_limit:
            categories = categories[:categories_limit]

        for i, category in enumerate(categories, 1):
            logger.info(f"\n\n{'=' * 80}")
            logger.info(f"類別 {i}/{len(categories)}: {category}")
            logger.info(f"{'=' * 80}\n")

            category_url = f"https://distiller.com/search?category={category}"
            self.scrape_category(category_url, max_spirits=max_spirits_per_category)

            # 類別間延遲
            if i < len(categories):
                logger.info(f"\n類別間等待...")
                time.sleep(random.uniform(5, 10))

    def save_to_csv(self, filename="distiller_selenium_output.csv"):
        """保存為 CSV"""
        if not self.spirits_data:
            logger.warning("沒有數據可保存")
            return False

        try:
            df = pd.DataFrame(self.spirits_data)
            df.to_csv(filename, index=False, encoding="utf-8-sig")
            logger.info(f"\n{'=' * 60}")
            logger.info(f"✓ 數據已保存至 {filename}")
            logger.info(f"✓ 總共 {len(self.spirits_data)} 條記錄")
            logger.info(f"{'=' * 60}\n")
            return True
        except Exception as e:
            logger.error(f"保存 CSV 時發生錯誤: {e}")
            return False

    def get_statistics(self):
        """獲取統計信息"""
        if not self.spirits_data:
            return None

        df = pd.DataFrame(self.spirits_data)
        stats = {
            "總記錄數": len(df),
            "失敗 URL 數": len(self.failed_urls),
            "各欄位空值率": {
                col: f"{(df[col] == 'N/A').sum() / len(df) * 100:.1f}%"
                for col in df.columns
                if col != "url"
            },
        }
        return stats


def run_phase1_selenium_test():
    """Phase 1 Selenium 測試"""
    logger.info("\n" + "=" * 80)
    logger.info("開始 Phase 1 Selenium 測試 (目標: 5-10 條記錄)")
    logger.info("=" * 80 + "\n")

    scraper = DistillerSeleniumScraper(headless=False, delay_min=3, delay_max=5)

    if not scraper.start_driver():
        return None, False

    try:
        # 只爬取一個類別，最多 10 條記錄
        scraper.scrape_limited(categories_limit=1, max_spirits_per_category=10)

        # 保存結果
        success = scraper.save_to_csv("distiller_selenium_phase1.csv")

        # 顯示統計
        if success:
            stats = scraper.get_statistics()
            if stats:
                logger.info("\nPhase 1 Selenium 統計結果:")
                logger.info(f"總記錄數: {stats['總記錄數']}")
                logger.info(f"失敗 URL 數: {stats['失敗 URL 數']}")
                logger.info(f"空值率: {stats['各欄位空值率']}")

        return scraper, success

    finally:
        scraper.close_driver()


def run_medium_scale_test():
    """中等規模測試 (100-500 條記錄)"""
    logger.info("\n" + "=" * 80)
    logger.info("開始中等規模 Selenium 測試 (目標: 100-500 條記錄)")
    logger.info("=" * 80 + "\n")

    scraper = DistillerSeleniumScraper(headless=False, delay_min=3, delay_max=5)

    if not scraper.start_driver():
        return None, False

    try:
        # 爬取 3-4 個類別，每個類別約 50-150 條
        scraper.scrape_limited(categories_limit=4, max_spirits_per_category=150)

        # 保存結果
        success = scraper.save_to_csv("distiller_spirits_reviews_NEW.csv")

        # 顯示統計
        if success:
            stats = scraper.get_statistics()
            if stats:
                logger.info("\n最終統計結果:")
                logger.info(f"總記錄數: {stats['總記錄數']}")
                logger.info(f"失敗 URL 數: {stats['失敗 URL 數']}")
                logger.info(f"空值率: {stats['各欄位空值率']}")

        return scraper, success

    finally:
        scraper.close_driver()


if __name__ == "__main__":
    logger.info(f"\n開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Phase 1 測試
    # scraper, success = run_phase1_selenium_test()

    # 中等規模測試
    scraper, success = run_medium_scale_test()

    logger.info(f"\n結束時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
