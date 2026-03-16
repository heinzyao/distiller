"""
爬蟲配置檔：集中管理 Distiller.com 爬蟲的所有可調參數。

設計理由
--------
使用類別常數而非 dataclass/Pydantic Settings，原因：
- 爬蟲參數在執行期間不需要動態修改（非 mutable state）
- 類別存取語法（ScraperConfig.MAX_SPIRITS_PER_CATEGORY）比 settings.xxx 更明確
- 不需要型別驗證或環境變數注入，純粹是工程調參

延遲設定的設計邏輯
------------------
- DELAY_MIN / DELAY_MAX：每筆詳情爬取之間的隨機延遲，模擬人類行為，降低被封鎖風險
- SCROLL_DELAY：頁面滾動後的等待時間，給予 JavaScript lazy-loading 完成的時間
- INITIAL_PAGE_DELAY：頁面初次載入後的等待，確保 React/Next.js 完成水合（hydration）
- CATEGORY_DELAY：類別間的延遲，讓伺服器有恢復時間，也避免連續請求觸發速率限制

分頁停止條件（三道防線）
------------------------
1. DUPLICATE_RATIO_THRESHOLD（0.8）：若一頁中 80% 以上是已知 URL → 接近資料邊界
2. MAX_CONSECUTIVE_DUP_PAGES（3）：連續 3 頁完全沒有新 URL → 確定到達邊界
3. MAX_PAGES_PER_QUERY（50）：硬上限，防止無限翻頁（異常情況的安全閥）

風格 ID 的來源
--------------
WHISKEY_STYLES / GIN_STYLES 等清單中的 ID 是從 Distiller.com 的 HTML
`<select name='spirit_style_id'>` 元素提取。每個 ID 對應一個烈酒子風格，
透過多個風格 ID 分頁查詢，可收錄到遠超單一分類查詢上限的烈酒數量。
"""


class ScraperConfig:
    """爬蟲設定：所有可調參數的集中管理。"""

    # ── 瀏覽器設定 ──
    HEADLESS = True             # 無頭模式：不顯示瀏覽器視窗（生產環境建議 True）
    WINDOW_SIZE = "1920,1080"   # 視窗尺寸：影響頁面 layout 與元素可見性
    PAGE_LOAD_TIMEOUT = 60      # 頁面載入逾時（秒），Distiller 部分頁面較慢
    ELEMENT_WAIT_TIMEOUT = 30   # 等待元素出現的逾時（秒），用於 Selenium WebDriverWait

    # ── 延遲設定（秒）──
    # 延遲的設計理由：模擬人類瀏覽行為，降低被網站封鎖的機率
    DELAY_MIN = 2               # 爬取間隨機延遲下限（秒）
    DELAY_MAX = 4               # 爬取間隨機延遲上限（秒）
    CATEGORY_DELAY = 8          # 類別切換時的等待時間（讓伺服器有恢復時間）
    SCROLL_DELAY = 2            # 頁面滾動後的等待時間（等 JavaScript lazy-load 完成）
    INITIAL_PAGE_DELAY = 5      # 頁面初次載入後的等待（等 React hydration 完成）

    # ── 爬取上限 ──
    MAX_SPIRITS_PER_CATEGORY = 150  # 每類別最多爬取的烈酒數量
    MAX_SCROLL_ATTEMPTS = 15        # 滾動模式下最多滾動次數（避免無限滾動）
    MAX_RETRIES = 3                 # 單一 URL 的最大重試次數（應對 session 斷開）

    # ── 分頁設定 ──
    PAGINATION_ENABLED = True       # 預設啟用分頁模式（比滾動模式可爬取更多資料）
    MAX_PAGES_PER_QUERY = 50        # 單一查詢最多翻頁數（安全閥，防無限翻頁）
    PAGE_PARAM = "page"             # URL 分頁參數名稱（?page=N）
    # 停止分頁的判斷條件（三道防線）
    MIN_NEW_URLS_PER_PAGE = 2       # 每頁至少需取得此數量的新 URL（否則意義不大）
    DUPLICATE_RATIO_THRESHOLD = 0.8 # 重複 URL 比例超過此值時停止（接近資料邊界）
    MAX_CONSECUTIVE_DUP_PAGES = 3   # 連續 N 頁全為已知 URL 時停止分頁（確定到達邊界）

    # 類別列表
    CATEGORIES = [
        "whiskey",
        "gin",
        "rum",
        "vodka",
        "brandy",
        "tequila-mezcal",
        "liqueurs-bitters",
    ]

    # 風格 ID (用於篩選以獲取更多結果)
    # 從網站 HTML 提取的主要風格 ID
    WHISKEY_STYLES = [
        ("1", "Single Malt"),
        ("2", "Blended"),
        ("3", "Blended Malt"),
        ("11", "Bourbon"),
        ("10", "Rye"),
        ("21", "Tennessee Whiskey"),
        ("30", "Canadian"),
        ("33", "American Single Malt"),
        ("26", "Single Pot Still"),
    ]

    GIN_STYLES = [
        ("105", "London Dry Gin"),
        ("108", "Modern Gin"),
        ("106", "Navy-Strength Gin"),
        ("107", "Barrel-Aged Gin"),
        ("110", "Old Tom Gin"),
        ("118", "Flavored Gin"),
    ]

    RUM_STYLES = [
        ("56", "Silver Rum"),
        ("57", "Gold Rum"),
        ("58", "Dark Rum"),
        ("59", "Aged Rum"),
        ("60", "Spiced Rum"),
        ("61", "Navy Rum"),
        ("62", "Flavored Rum"),
    ]

    VODKA_STYLES = [
        ("123", "Unflavored Vodka"),
        ("104", "Flavored Vodka"),
        ("124", "Barrel-Aged Vodka"),
    ]

    # 主要國家 ID
    TOP_COUNTRIES = [
        ("1", "Scotland"),
        ("3", "USA"),
        ("5", "Ireland"),
        ("2", "Japan"),
        ("8", "France"),
        ("60", "Germany"),
        ("35", "Jamaica"),
        ("38", "Mexico"),
    ]

    # ── 失敗處理與回復 (Failure Handling & Recovery) ──
    MAX_SCROLL_RETRIES = 3          # scroll_page() 遇到 null body 時的最大重試次數
    MAX_RESTART_ATTEMPTS = 2        # 單次爬取中 driver 重啟的最大次數（超過則放棄）
    HEALTH_CHECK_TIMEOUT = 10       # 健康檢查頁面載入逾時（秒）
    PAGE_RETRY_COUNT = 2            # 單一頁面失敗時的重試次數
    RESTART_TRIGGER_ERRORS = [      # 觸發 driver 重啟的錯誤字串（任一子字串匹配即觸發）
        "invalid session id",       # Selenium session 過期
        "session deleted",          # Chrome 主動斷開 session
        "Cannot read properties of null",  # JS null body (document.body 為 null)
        "null is not an object",    # Safari 風格 JS null 錯誤（防禦性）
    ]
    DUPLICATE_RUN_WINDOW_HOURS = 20 # 重複執行檢測窗口（小時），窗口內有成功執行則跳過

    # User-Agent
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    )

    # 輸出設定
    OUTPUT_ENCODING = "utf-8-sig"
    LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
