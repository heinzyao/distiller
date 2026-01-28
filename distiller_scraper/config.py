"""
爬蟲配置檔
"""


class ScraperConfig:
    """爬蟲設定"""

    # 瀏覽器設定
    HEADLESS = True
    WINDOW_SIZE = "1920,1080"
    PAGE_LOAD_TIMEOUT = 60
    ELEMENT_WAIT_TIMEOUT = 30

    # 延遲設定 (秒)
    DELAY_MIN = 2
    DELAY_MAX = 4
    CATEGORY_DELAY = 8
    SCROLL_DELAY = 2
    INITIAL_PAGE_DELAY = 5

    # 爬取設定
    MAX_SPIRITS_PER_CATEGORY = 150
    MAX_SCROLL_ATTEMPTS = 15
    MAX_RETRIES = 3

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

    # User-Agent
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    # 輸出設定
    OUTPUT_ENCODING = "utf-8-sig"
    LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
