"""
pytest 共用 fixtures 與配置
"""

import os
import sys
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

# 加入專案路徑
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_spirit_detail_html() -> str:
    """載入烈酒詳情頁 HTML 範本"""
    html_path = FIXTURES_DIR / "sample_spirit_detail.html"
    return html_path.read_text(encoding="utf-8")


@pytest.fixture
def sample_spirit_detail_soup(sample_spirit_detail_html) -> BeautifulSoup:
    """解析烈酒詳情頁為 BeautifulSoup 物件"""
    return BeautifulSoup(sample_spirit_detail_html, "html.parser")


@pytest.fixture
def sample_search_results_html() -> str:
    """載入搜尋結果頁 HTML 範本"""
    html_path = FIXTURES_DIR / "sample_search_results.html"
    return html_path.read_text(encoding="utf-8")


@pytest.fixture
def sample_search_results_soup(sample_search_results_html) -> BeautifulSoup:
    """解析搜尋結果頁為 BeautifulSoup 物件"""
    return BeautifulSoup(sample_search_results_html, "html.parser")


@pytest.fixture
def empty_soup() -> BeautifulSoup:
    """空白 HTML 用於測試預設值"""
    return BeautifulSoup("<html><body></body></html>", "html.parser")


@pytest.fixture
def partial_spirit_soup() -> BeautifulSoup:
    """部分資料的烈酒頁面，用於測試缺失欄位處理"""
    html = """
    <html>
    <body>
        <h1 class="secondary-headline name">Test Spirit</h1>
        <p class="ultra-mini-headline type">Bourbon</p>
        <!-- 缺少 location, age, abv 等欄位 -->
        <div class="distiller-score">Score<span>85</span></div>
    </body>
    </html>
    """
    return BeautifulSoup(html, "html.parser")
