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
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

import pandas as pd
from bs4 import BeautifulSoup

from .api_client import DistillerAPIClient
from .config import ScraperConfig
from .selectors import DataExtractor, Selectors
from .storage import StorageBackend

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
        storage: Optional[StorageBackend] = None,
        api_client: Optional[DistillerAPIClient] = None,
    ):
        self.headless = headless
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.storage = storage
        self.api_client = api_client
        self.driver: Optional[Any] = None  # webdriver.Chrome, 延遲導入
        self.spirits_data: List[Dict] = []
        self.failed_urls: List[str] = []
        # 去重：若有 storage 則從 DB 載入已存 URLs
        self.seen_urls: Set[str] = (
            storage.get_existing_urls() if storage else set()
        )

    def start_driver(self) -> bool:
        """啟動 Chrome WebDriver"""
        try:
            # 延遲導入 selenium 相關模組以加速模組載入
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            from selenium.webdriver.chrome.service import Service as ChromeService
            from webdriver_manager.chrome import ChromeDriverManager

            logger.info("正在啟動 Chrome WebDriver...")
            options = ChromeOptions()

            if self.headless:
                options.add_argument("--headless=new")

            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument(f"--window-size={ScraperConfig.WINDOW_SIZE}")
            options.add_argument(f"user-agent={ScraperConfig.USER_AGENT}")

            # 啟用 Performance Logging 以捕獲 XHR 請求（用於 API 探測）
            options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

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

    def capture_xhr_requests(self, url: str, scroll_count: int = 3) -> List[str]:
        """
        瀏覽指定頁面並捕獲滾動觸發的 XHR/Fetch 請求 URL。
        用於探測分頁 API 端點。回傳所有捕獲的請求 URL 列表。
        """
        import json as _json

        try:
            self.driver.get(url)
            time.sleep(ScraperConfig.INITIAL_PAGE_DELAY)

            # 清空現有 performance log
            self.driver.get_log("performance")

            # 滾動觸發可能的 XHR 請求
            for _ in range(scroll_count):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(ScraperConfig.SCROLL_DELAY)

            # 讀取 performance log
            logs = self.driver.get_log("performance")
            xhr_urls = []

            for entry in logs:
                try:
                    msg = _json.loads(entry["message"])["message"]
                    if msg.get("method") != "Network.requestWillBeSent":
                        continue
                    req_url = msg.get("params", {}).get("request", {}).get("url", "")
                    resource_type = msg.get("params", {}).get("type", "")
                    if resource_type in ("XHR", "Fetch") and req_url:
                        xhr_urls.append(req_url)
                except (KeyError, ValueError):
                    continue

            return xhr_urls

        except Exception as e:
            logger.warning(f"捕獲 XHR 請求失敗: {e}")
            return []

    def _get_search_queries(
        self, category: str, use_styles: bool
    ) -> List[tuple]:
        """回傳此類別要查詢的 (base_url, label) 列表"""
        style_map = {
            "whiskey": ScraperConfig.WHISKEY_STYLES,
            "gin":     ScraperConfig.GIN_STYLES,
            "rum":     ScraperConfig.RUM_STYLES,
            "vodka":   ScraperConfig.VODKA_STYLES,
        }
        queries = []
        if use_styles and category in style_map:
            for style_id, style_name in style_map[category]:
                url = (
                    f"https://distiller.com/search"
                    f"?category={category}&spirit_style_id={style_id}&sort=distiller_score"
                )
                queries.append((url, style_name))
        else:
            url = f"https://distiller.com/search?category={category}&sort=distiller_score"
            queries.append((url, category))
        return queries

    def _fetch_spirit_urls_from_page(self, page_url: str) -> List[str]:
        """
        載入搜索結果頁面，完整滾動後回傳所有 spirit URL。
        供分頁與滾動模式共用。
        """
        self.driver.get(page_url)
        time.sleep(ScraperConfig.INITIAL_PAGE_DELAY)
        self.scroll_page()
        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        return self.extract_spirit_urls_from_list(soup)

    def _fetch_spirit_urls(self, base_url: str, page: int) -> List[str]:
        """
        取得指定查詢 + 頁碼的 spirit URL 列表。
        優先使用 API（快速），失敗時 fallback 至 Selenium。
        """
        from urllib.parse import parse_qs, urlparse

        if self.api_client and self.api_client.is_available():
            parsed = urlparse(base_url)
            params = parse_qs(parsed.query, keep_blank_values=True)
            category = params.get("category", [""])[0]
            style_id = params.get("spirit_style_id", [None])[0]

            urls = self.api_client.fetch_search_results(
                category=category, page=page, spirit_style_id=style_id
            )
            if urls is not None:  # [] 代表本頁無結果（合法），None 代表請求異常
                mode = "API"
                logger.info(f"  [{mode}] 第 {page} 頁: {len(urls)} 個連結")
                return urls
            logger.debug("  API 請求失敗，fallback 至 Selenium")

        # Selenium fallback
        page_url = base_url if page == 1 else f"{base_url}&page={page}"
        return self._fetch_spirit_urls_from_page(page_url)

    def discover_api(self, warm_up_category: str = "whiskey") -> bool:
        """
        探測 Distiller.com API 端點。
        載入一個搜索頁面並捕獲 XHR 請求，交給 api_client 分析。
        回傳 API 是否可用。
        若 api_client 未設定，直接回傳 False。
        """
        if not self.api_client:
            return False

        logger.info("=" * 60)
        logger.info("正在探測 API 端點...")
        warm_url = (
            f"https://distiller.com/search"
            f"?category={warm_up_category}&sort=distiller_score"
        )
        xhr_urls = self.capture_xhr_requests(warm_url, scroll_count=2)
        logger.info(f"捕獲 {len(xhr_urls)} 個 XHR 請求")

        result = self.api_client.discover(xhr_urls)

        if result["available"]:
            logger.info(f"✓ API 可用！搜索端點: {result['search_endpoint']}")
            if result.get("detail_endpoint_template"):
                logger.info(f"✓ 詳情端點: {result['detail_endpoint_template']}")
        else:
            logger.info("API 不可用，將使用 Selenium 模式")
        logger.info("=" * 60)

        return result["available"]

    def _scrape_urls(
        self,
        spirit_urls: List[str],
        category: str,
        results: List[Dict],
        max_spirits: int,
    ) -> None:
        """逐一爬取 spirit URL 列表，結果 append 至 results（就地修改）"""
        for spirit_url in spirit_urls:
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

    def scrape_category_paginated(
        self,
        category: str,
        max_spirits: int = None,
        use_styles: bool = False,
    ) -> List[Dict]:
        """
        分頁模式爬取特定類別。
        對每個查詢（category / style）逐頁翻頁，直到：
          - 已達 max_spirits 上限
          - 連續頁面無新 URL（重複比例 >= DUPLICATE_RATIO_THRESHOLD）
          - 頁面完全無結果
          - 達到 MAX_PAGES_PER_QUERY 上限
        若第一頁即判斷分頁無效，自動 fallback 至滾動模式。
        """
        max_spirits = max_spirits or ScraperConfig.MAX_SPIRITS_PER_CATEGORY
        results: List[Dict] = []
        queries = self._get_search_queries(category, use_styles)

        for base_url, label in queries:
            if len(results) >= max_spirits:
                break

            logger.info(f"[分頁] 開始爬取: {label}")
            pagination_works = False  # 確認分頁是否真的有效
            db_urls = self.storage.get_existing_urls() if self.storage else set()

            for page in range(1, ScraperConfig.MAX_PAGES_PER_QUERY + 1):
                if len(results) >= max_spirits:
                    break

                logger.info(f"  第 {page} 頁 ({'API' if self.api_client and self.api_client.is_available() else 'Selenium'})")

                try:
                    urls_on_page = self._fetch_spirit_urls(base_url, page)
                except Exception as e:
                    logger.error(f"  載入第 {page} 頁失敗: {e}")
                    break

                if not urls_on_page:
                    logger.info(f"  第 {page} 頁無結果，停止分頁")
                    break

                # 計算新 URL 數量（未見過的）
                new_urls = [u for u in urls_on_page if u not in self.seen_urls]
                total_on_page = len(urls_on_page)
                duplicate_ratio = 1.0 - (len(new_urls) / total_on_page)

                logger.info(
                    f"  第 {page} 頁找到 {total_on_page} 個連結，"
                    f"新增 {len(new_urls)} 個（重複率 {duplicate_ratio:.0%}）"
                )

                # 判斷分頁是否有效（第二頁起出現新內容 = 分頁有效）
                if page == 2 and len(new_urls) >= ScraperConfig.MIN_NEW_URLS_PER_PAGE:
                    pagination_works = True
                    logger.info("  分頁機制有效，繼續翻頁")

                # 第二頁起若無新 URL，判斷已到結尾
                if page >= 2 and len(new_urls) < ScraperConfig.MIN_NEW_URLS_PER_PAGE:
                    if not pagination_works:
                        # NEW: Check if category is already fully in DB
                        if urls_on_page and self.storage and all(u in db_urls for u in urls_on_page):
                            logger.info("  此類別資料已存在於資料庫，跳過")
                            break
                        
                        logger.info("  分頁無效（第二頁無新內容），切換至滾動模式")
                        # fallback: 重新以 Selenium 滾動模式爬第一頁
                        try:
                            first_page_urls = self._fetch_spirit_urls_from_page(base_url)
                            self._scrape_urls(first_page_urls, category, results, max_spirits)
                        except Exception as e:
                            logger.warning(f"  滾動模式 fallback 失敗: {e}")
                    else:
                        logger.info(f"  第 {page} 頁無新 URL，分頁結束")
                    break

                # 重複率過高也停止
                if page >= 2 and duplicate_ratio >= ScraperConfig.DUPLICATE_RATIO_THRESHOLD:
                    logger.info(f"  重複率 {duplicate_ratio:.0%} 過高，停止分頁")
                    break

                self._scrape_urls(urls_on_page, category, results, max_spirits)

                # 每頁間延遲
                if len(results) < max_spirits:
                    time.sleep(ScraperConfig.SCROLL_DELAY)

            # 查詢間延遲（多風格時）
            if len(queries) > 1 and len(results) < max_spirits:
                time.sleep(ScraperConfig.CATEGORY_DELAY)

        return results

    def scrape_spirit_detail(self, url: str, retry_count: int = 0) -> Optional[Dict]:
        """爬取單個烈酒詳情頁（優先使用 API，失敗則 fallback Selenium）"""
        if url in self.seen_urls:
            logger.debug(f"跳過重複 URL: {url}")
            return None

        # ── API 模式 ────────────────────────────────────────────────
        if self.api_client and self.api_client.is_available():
            api_data = self.api_client.fetch_spirit_detail(url)
            if api_data:
                api_data["url"] = url
                self.seen_urls.add(url)
                if self.storage:
                    self.storage.save_spirit(api_data)
                logger.info(f"✓ [API] 已爬取: {api_data['name']}")
                return api_data
            logger.debug(f"  API 詳情失敗，fallback Selenium: {url}")

        # ── Selenium fallback ────────────────────────────────────────
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

            # 即時寫入 storage
            if self.storage:
                self.storage.save_spirit(data)

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
        use_pagination: bool = None,
    ) -> List[Dict]:
        """
        爬取特定類別的烈酒。
        use_pagination=True（預設）：分頁模式，可爬取遠超滾動上限的資料。
        use_pagination=False：傳統滾動模式（向後相容）。
        """
        max_spirits = max_spirits or ScraperConfig.MAX_SPIRITS_PER_CATEGORY
        if use_pagination is None:
            use_pagination = ScraperConfig.PAGINATION_ENABLED

        if use_pagination:
            return self.scrape_category_paginated(
                category, max_spirits=max_spirits, use_styles=use_styles
            )

        # ── 傳統滾動模式（fallback） ──────────────────────────────────────
        results: List[Dict] = []
        queries = self._get_search_queries(category, use_styles)

        for search_url, label in queries:
            if len(results) >= max_spirits:
                break

            logger.info(f"[滾動] 正在爬取: {label} ({search_url})")
            try:
                urls = self._fetch_spirit_urls_from_page(search_url)
                logger.info(f"在 {label} 中找到 {len(urls)} 個烈酒連結")
                self._scrape_urls(urls, category, results, max_spirits)
            except Exception as e:
                error_msg = str(e)
                if "invalid session id" in error_msg or "session deleted" in error_msg:
                    logger.warning("Session 斷開，嘗試重新連接...")
                    if self.restart_driver():
                        time.sleep(2)
                        continue
                logger.error(f"爬取 {label} 時發生錯誤: {e}")
                continue

            if len(queries) > 1:
                time.sleep(ScraperConfig.CATEGORY_DELAY)

        return results

    def scrape(
        self,
        categories: List[str] = None,
        max_per_category: int = None,
        use_styles: bool = True,
        use_pagination: bool = None,
    ):
        """執行爬蟲"""
        categories = categories or ScraperConfig.CATEGORIES
        max_per_category = max_per_category or ScraperConfig.MAX_SPIRITS_PER_CATEGORY
        if use_pagination is None:
            use_pagination = ScraperConfig.PAGINATION_ENABLED

        start_time = datetime.now()
        logger.info(f"\n{'=' * 80}")
        logger.info(f"開始爬取 - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"類別: {categories}")
        logger.info(f"每類別上限: {max_per_category}")
        logger.info(f"使用風格篩選: {use_styles}")
        logger.info(f"分頁模式: {use_pagination}")
        logger.info(f"{'=' * 80}\n")

        if not self.start_driver():
            return False

        # API 端點探測（若 api_client 已設定）
        if self.api_client:
            self.discover_api(warm_up_category=categories[0])

        try:
            for cat_idx, category in enumerate(categories, 1):
                try:
                    logger.info(f"\n{'=' * 60}")
                    logger.info(f"類別 {cat_idx}/{len(categories)}: {category}")
                    logger.info(f"{'=' * 60}\n")
                    
                    category_results = self.scrape_category(
                        category,
                        max_spirits=max_per_category,
                        use_styles=use_styles,
                        use_pagination=use_pagination,
                    )
                    self.spirits_data.extend(category_results)
                    
                    logger.info(f"類別 {category} 完成: {len(category_results)} 筆")
                    
                    if cat_idx < len(categories):
                        logger.info(f"等待 {ScraperConfig.CATEGORY_DELAY} 秒後繼續...\n")
                        time.sleep(ScraperConfig.CATEGORY_DELAY)
                except Exception as e:
                    logger.error(f"類別 {category} 爬取失敗: {e}")
                    continue
            
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
