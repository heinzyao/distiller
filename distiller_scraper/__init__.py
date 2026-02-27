"""
Distiller.com 爬蟲模組
改進版本 - 修復 CSS 選擇器與分頁功能
"""

__version__ = "2.2.0"
__all__ = [
    "DistillerScraperV2", "ScraperConfig", "Selectors",
    "SQLiteStorage", "CSVStorage", "DistillerAPIClient",
]


def __getattr__(name):
    """延遲導入以避免在測試時載入 selenium 等重型依賴"""
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
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
