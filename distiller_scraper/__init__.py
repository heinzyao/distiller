"""
Distiller.com 爬蟲模組（V2.3.0）：烈酒評分資料擷取與查詢工具。

延遲導入（Lazy Import）設計
----------------------------
此模組使用 __getattr__ 實作延遲導入，而非一般的頂層 import。

設計理由：
- DistillerScraperV2 依賴 selenium 和 playwright，這兩個套件體積較大
  且需要瀏覽器環境（Docker 容器或本機 Chrome）
- 在執行測試（pytest）、使用 bot.py 查詢功能、或 import 僅使用
  StorageBackend / DistillerAPIClient 的場景下，不需要載入 selenium
- 延遲導入確保 `import distiller_scraper` 本身不會觸發 selenium 初始化
  → 測試速度更快，也避免在無瀏覽器環境中的 ImportError

使用方式：
    # 只需要儲存後端時（無需瀏覽器）
    from distiller_scraper import SQLiteStorage

    # 需要爬蟲時（會觸發 selenium 導入）
    from distiller_scraper import DistillerScraperV2
"""

__version__ = "2.4.0"
__all__ = [
    "DistillerScraperV2", "ScraperConfig", "Selectors",
    "SQLiteStorage", "CSVStorage", "DistillerAPIClient",
    "LineNotifier",
    "DiffordsGuideScraper", "DiffordsStorage", "DiffordsExtractor",
]


def __getattr__(name):
    """延遲導入機制：只在實際存取特定屬性時才載入對應模組。

    Python 在名稱未在模組 namespace 中找到時，會呼叫模組的 __getattr__
    這允許我們實作「按需載入」，避免在 import 時就載入所有重型依賴。
    """
    if name == "DistillerScraperV2":
        from .scraper import DistillerScraperV2
        return DistillerScraperV2
    elif name == "ScraperConfig":
        from .config import ScraperConfig
        return ScraperConfig
    elif name == "Selectors":
        from .selectors import Selectors
        return Selectors
    elif name == "SQLiteStorage":
        from .storage import SQLiteStorage
        return SQLiteStorage
    elif name == "CSVStorage":
        from .storage import CSVStorage
        return CSVStorage
    elif name == "DistillerAPIClient":
        from .api_client import DistillerAPIClient
        return DistillerAPIClient
    elif name == "LineNotifier":
        from .notify import LineNotifier
        return LineNotifier
    elif name == "DiffordsGuideScraper":
        from .diffords_scraper import DiffordsGuideScraper
        return DiffordsGuideScraper
    elif name == "DiffordsStorage":
        from .diffords_storage import DiffordsStorage
        return DiffordsStorage
    elif name == "DiffordsExtractor":
        from .diffords_selectors import DiffordsExtractor
        return DiffordsExtractor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
