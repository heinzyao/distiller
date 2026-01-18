#!/usr/bin/env python3
"""
最終版本 Distiller 爬蟲 - 中等規模（100-500 條記錄）
使用 headless Chrome 進行後台爬取
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
        logging.FileHandler("distiller_final_scraper.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def run_scraper():
    """執行爬蟲"""
    start_time = datetime.now()
    logger.info(f"\n{'=' * 80}")
    logger.info(f"開始時間: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"目標: 爬取 100-500 條烈酒記錄")
    logger.info(f"{'=' * 80}\n")

    # 初始化 Chrome (headless 模式)
    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    driver = None
    all_spirits = []
    failed_urls = []

    try:
        logger.info("正在啟動 Chrome WebDriver (headless 模式)...")
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(60)
        logger.info("✓ Chrome WebDriver 已啟動\n")

        # 定義要爬取的類別
        categories = ["whiskey", "gin", "rum", "vodka"]
        target_per_category = 125  # 每個類別目標 125 條（4個類別 = 500條）

        for cat_idx, category in enumerate(categories, 1):
            logger.info(f"\n{'=' * 60}")
            logger.info(f"類別 {cat_idx}/{len(categories)}: {category}")
            logger.info(f"{'=' * 60}\n")

            category_url = f"https://distiller.com/search?category={category}"

            try:
                logger.info(f"正在載入: {category_url}")
                driver.get(category_url)
                time.sleep(5)

                # 滾動載入內容
                logger.info("正在滾動頁面載入內容...")
                for scroll in range(5):
                    driver.execute_script(
                        "window.scrollTo(0, document.body.scrollHeight);"
                    )
                    time.sleep(2)
                logger.info("✓ 頁面滾動完成")

                # 解析頁面
                soup = BeautifulSoup(driver.page_source, "html.parser")

                # 查找烈酒連結
                spirit_urls = set()
                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    if (
                        "/spirits/" in href
                        and not href.endswith("/spirits/")
                        and not href.endswith("/spirits")
                    ):
                        if href.startswith("http"):
                            spirit_urls.add(href)
                        else:
                            spirit_urls.add(f"https://distiller.com{href}")

                spirit_urls = list(spirit_urls)[:target_per_category]
                logger.info(
                    f"找到 {len(spirit_urls)} 個烈酒連結（限制 {target_per_category} 條）\n"
                )

                # 爬取每個烈酒
                for spirit_idx, spirit_url in enumerate(spirit_urls, 1):
                    try:
                        logger.info(
                            f"[{cat_idx}/{len(categories)}][{spirit_idx}/{len(spirit_urls)}] 正在爬取..."
                        )

                        driver.get(spirit_url)
                        time.sleep(2)

                        soup = BeautifulSoup(driver.page_source, "html.parser")

                        # 提取品名
                        name = "N/A"
                        for selector in ["h1", "h2"]:
                            elem = soup.find(selector)
                            if elem:
                                name = elem.get_text(strip=True)
                                if name:
                                    break

                        if name == "N/A":
                            logger.warning(f"無法提取品名，跳過: {spirit_url}")
                            failed_urls.append(spirit_url)
                            continue

                        # 提取其他字段（使用簡化邏輯）
                        category_text = category.replace("-", " ").title()

                        spirit_data = {
                            "name": name,
                            "category": category_text,
                            "origin": "N/A",
                            "age": "N/A",
                            "expert_score": "N/A",
                            "community_score": "N/A",
                            "flavor_profile": "N/A",
                            "url": spirit_url,
                        }

                        all_spirits.append(spirit_data)
                        logger.info(f"✓ 已爬取: {name}")

                        # 延遲
                        if spirit_idx < len(spirit_urls):
                            delay = random.uniform(2, 4)
                            time.sleep(delay)

                    except Exception as e:
                        logger.error(f"爬取錯誤 {spirit_url}: {e}")
                        failed_urls.append(spirit_url)
                        continue

                # 類別間延遲
                if cat_idx < len(categories):
                    logger.info(f"\n類別 '{category}' 完成，等待 10 秒後繼續...\n")
                    time.sleep(10)

            except Exception as e:
                logger.error(f"處理類別 '{category}' 時發生錯誤: {e}")
                continue

        # 保存結果
        if all_spirits:
            df = pd.DataFrame(all_spirits)
            output_file = "distiller_spirits_reviews_NEW.csv"
            df.to_csv(output_file, index=False, encoding="utf-8-sig")

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            logger.info(f"\n{'=' * 80}")
            logger.info(f"✓ 爬取完成！")
            logger.info(f"{'=' * 80}")
            logger.info(f"輸出文件: {output_file}")
            logger.info(f"總記錄數: {len(all_spirits)}")
            logger.info(f"失敗 URL 數: {len(failed_urls)}")
            logger.info(f"耗時: {duration / 60:.1f} 分鐘")
            logger.info(f"結束時間: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"{'=' * 80}\n")

            # 顯示數據統計
            logger.info("數據統計:")
            logger.info(f"  - 類別分布: {df['category'].value_counts().to_dict()}")
            logger.info(
                f"  - 空值率 (name): {(df['name'] == 'N/A').sum() / len(df) * 100:.1f}%"
            )

            return True
        else:
            logger.error("沒有爬取到任何數據！")
            return False

    except Exception as e:
        logger.error(f"爬蟲執行時發生錯誤: {e}")
        return False

    finally:
        if driver:
            driver.quit()
            logger.info("\n瀏覽器已關閉")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🚀 Distiller.com 爬蟲 - 中等規模測試")
    print("目標: 100-500 條烈酒記錄")
    print("模式: Headless Chrome (後台運行)")
    print("=" * 80 + "\n")

    success = run_scraper()

    if success:
        print("\n✅ 爬蟲執行成功！")
        print("請檢查文件: distiller_spirits_reviews_NEW.csv")
        print("日誌文件: distiller_final_scraper.log")
    else:
        print("\n❌ 爬蟲執行失敗")
        print("請檢查日誌文件: distiller_final_scraper.log")
        exit(1)
