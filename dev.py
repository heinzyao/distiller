from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService # 導入 EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager # 導入 EdgeChromiumDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time
import re

def scrape_distiller_reviews_edge(output_filename="distiller_reviews_edge.csv"):
    """
    從 Distiller.com 爬取烈酒評論並儲存為 CSV 檔案，使用 Edge 瀏覽器並自動下載驅動程式。

    Args:
        output_filename (str): 輸出 CSV 檔案的名稱。
    """

    options = webdriver.EdgeOptions()
    # 可以選擇性地啟用無頭模式，讓瀏覽器在後台運行
    # options.add_argument("--headless")
    options.add_argument("--start-maximized") # 最大化視窗
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36") # 修改 User-Agent 以匹配 Edge

    print("正在自動下載或檢查 Edge WebDriver...")
    try:
        # 自動下載並啟動 Edge WebDriver
        service = EdgeService(EdgeChromiumDriverManager().install())
        driver = webdriver.Edge(service=service, options=options)
        print("Edge WebDriver 已成功啟動。")
    except Exception as e:
        print(f"無法啟動 Edge WebDriver：{e}")
        print("請確保您的 Edge 瀏覽器已正確安裝且版本為最新。")
        return

    wait = WebDriverWait(driver, 20) # 設定最長等待時間為 20 秒

    base_url = "https://distiller.com/spirits"
    all_reviews_data = []

    try:
        driver.get(base_url)
        print("成功開啟 Distiller.com 網站。")

        # 嘗試點擊接受 Cookie 按鈕（如果存在）
        try:
            # 嘗試使用更通用的 XPath 選擇器來查找接受 Cookie 的按鈕
            # 這裡的 XPath 是試圖匹配包含 "Accept" 或 "Agree" 文本的按鈕或連結
            # 您可能需要根據實際網站的 HTML 結構進行調整
            cookie_accept_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'Agree') or contains(@aria-label, 'Accept')] | //a[contains(@class, 'cookie-consent-button') or contains(@id, 'cookie-accept')]")))
            cookie_accept_button.click()
            print("已點擊接受 Cookie 按鈕。")
            time.sleep(2) # 等待頁面更新
        except Exception as e:
            print(f"未找到或無法點擊 Cookie 按鈕 (或已接受): {e}")

        # 獲取所有烈酒類別的連結
        category_links = []
        try:
            # 等待類別列表載入
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.spirits-category-grid li a")))
            categories_elements = driver.find_elements(By.CSS_SELECTOR, "ul.spirits-category-grid li a")
            for cat_elem in categories_elements:
                link = cat_elem.get_attribute("href")
                if link:
                    category_links.append(link)
            print(f"找到 {len(category_links)} 個烈酒類別。")
        except Exception as e:
            print(f"獲取類別連結時發生錯誤：{e}")
            return

        for category_link in category_links:
            if not category_link:
                continue

            print(f"\n正在處理類別: {category_link}")
            driver.get(category_link)
            time.sleep(3) # 等待頁面載入

            # 模擬滾動以載入更多項目
            last_height = driver.execute_script("return document.body.scrollHeight")
            while True:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3) # 給予足夠時間載入新內容
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
            print("頁面已滾動到底部，嘗試載入所有評論項目。")

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            # 尋找所有烈酒項目的連結
            spirit_items = soup.select("a.spirit-item-card") # 根據實際 HTML 調整選擇器
            
            if not spirit_items:
                print(f"在 {category_link} 中未找到烈酒項目。")
                continue

            for item in spirit_items:
                spirit_url = item.get('href')
                if not spirit_url:
                    continue
                
                # Distiller.com 的 URL 通常是相對路徑，需要拼接
                full_spirit_url = f"https://distiller.com{spirit_url}"
                print(f"正在抓取: {full_spirit_url}")

                try:
                    driver.get(full_spirit_url)
                    # 等待頁面元素載入，例如品名或評分
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.spirit-title"))) # 根據實際 HTML 調整選擇器

                    spirit_soup = BeautifulSoup(driver.page_source, 'html.parser')

                    # 提取品名
                    product_name_elem = spirit_soup.select_one("h1.spirit-title")
                    product_name = product_name_elem.get_text(strip=True) if product_name_elem else "N/A"

                    # 提取類別
                    category_elem = spirit_soup.select_one("span.category-name") # 根據實際 HTML 調整選擇器
                    category = category_elem.get_text(strip=True) if category_elem else "N/A"

                    # 提取產地 (通常在產品資訊中)
                    origin = "N/A"
                    info_blocks = spirit_soup.select("div.spirit-info-block") # 根據實際 HTML 調整選擇器
                    for block in info_blocks:
                        # 檢查文本內容是否包含產地相關關鍵字
                        if "Distillery:" in block.get_text() or "Origin:" in block.get_text() or "Country:" in block.get_text():
                            value_elem = block.select_one("span.value") # 假設值在一個帶有 class="value" 的 span 中
                            if value_elem:
                                origin = value_elem.get_text(strip=True)
                                break
                            else: # 如果沒有明確的 .value class，嘗試從文本中解析
                                text_content = block.get_text(strip=True)
                                match = re.search(r'(Distillery|Origin|Country):\s*(.+)', text_content)
                                if match:
                                    origin = match.group(2).strip()
                                    break


                    # 提取年份 (如果存在)
                    year = "N/A"
                    # 嘗試從產品標題中提取年份（四位數字）
                    title_year_match = re.search(r'(\d{4})', product_name)
                    if title_year_match:
                        year = title_year_match.group(1)
                    else:
                        # 嘗試從其他資訊區塊查找，例如帶有 .year 或相關文字的元素
                        year_elem = spirit_soup.select_one("span.year")
                        if year_elem:
                            year_match = re.search(r'\d{4}', year_elem.get_text(strip=True))
                            if year_match:
                                year = year_match.group(0)
                        else:
                            # 在 info_blocks 中尋找表示年份的關鍵字
                            for block in info_blocks:
                                text_content = block.get_text(strip=True)
                                if "Age:" in text_content or "Vintage:" in text_content or "Year:" in text_content:
                                    year_match = re.search(r'\d{4}', text_content)
                                    if year_match:
                                        year = year_match.group(0)
                                        break

                    # 提取專家評分
                    expert_score = "N/A"
                    expert_score_elem = spirit_soup.select_one("span.official-rating-score") # 根據實際 HTML 調整選擇器
                    if expert_score_elem:
                        expert_score = expert_score_elem.get_text(strip=True)

                    # 提取社群評分
                    community_score = "N/A"
                    # 社群評分可能有多種選擇器，嘗試多個
                    community_score_elem = spirit_soup.select_one("div.community-rating-score span")
                    if community_score_elem:
                        community_score = community_score_elem.get_text(strip=True)
                    elif spirit_soup.select_one("div.community-rating-value"): # 另一種常見類別
                        community_score_elem = spirit_soup.select_one("div.community-rating-value")
                        community_score = community_score_elem.get_text(strip=True)

                    # 提取風味圖譜 (可能需要更複雜的解析)
                    flavor_profile = {}
                    flavor_chart_container = spirit_soup.select_one("div.flavor-wheel") # 假設風味圖譜有一個容器
                    if flavor_chart_container:
                        # 每個風味軸的選擇器需要根據實際頁面結構調整
                        flavor_axes = flavor_chart_container.select("div.flavor-axis") # 或其他類似的類別
                        for axis in flavor_axes:
                            label_elem = axis.select_one("div.axis-label") # 風味標籤
                            
                            if label_elem:
                                label = label_elem.get_text(strip=True)
                                # 嘗試從明確的數值元素獲取
                                value_elem = axis.select_one("div.axis-value")
                                if value_elem:
                                    flavor_profile[label] = value_elem.get_text(strip=True)
                                else:
                                    # 嘗試從 style 屬性中提取寬度作為百分比值 (常用於條形圖)
                                    value_bar = axis.select_one("div.axis-bar") # 假設有一個條形表示數值
                                    if value_bar and 'style' in value_bar.attrs:
                                        style_attr = value_bar['style']
                                        width_match = re.search(r'width:\s*(\d+(\.\d+)?)%', style_attr)
                                        if width_match:
                                            flavor_profile[label] = f"{width_match.group(1)}%"
                                        else:
                                            flavor_profile[label] = "N/A"
                                    else:
                                        flavor_profile[label] = "N/A" # 如果找不到明確的值
                            
                    all_reviews_data.append({
                        "品名": product_name,
                        "類別": category,
                        "產地": origin,
                        "年份": year,
                        "專家評分": expert_score,
                        "社群評分": community_score,
                        "風味圖譜": str(flavor_profile) # 將字典轉換為字串
                    })

                except Exception as e:
                    print(f"抓取 {full_spirit_url} 時發生錯誤：{e}")
                
                time.sleep(2) # 每次抓取一個評論後稍微等待，避免過於頻繁

    except Exception as e:
        print(f"主爬蟲程式發生錯誤：{e}")

    finally:
        driver.quit()
        print("瀏覽器已關閉。")

    # 將資料儲存為 CSV
    if all_reviews_data:
        df = pd.DataFrame(all_reviews_data)
        df.to_csv(output_filename, index=False, encoding='utf-8-sig')
        print(f"所有評論資料已成功儲存到 {output_filename}")
    else:
        print("沒有收集到任何評論資料。")

# --- 執行程式 ---
if __name__ == "__main__":
    scrape_distiller_reviews_edge("distiller_official_reviews_edge.csv")