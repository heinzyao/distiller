"""
Distiller.com 爬蟲模組
改進版本 - 修復 CSS 選擇器與分頁功能
"""

from .scraper import DistillerScraperV2
from .config import ScraperConfig
from .selectors import Selectors

__version__ = "2.0.0"
__all__ = ["DistillerScraperV2", "ScraperConfig", "Selectors"]
