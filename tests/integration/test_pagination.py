"""
分頁爬取邏輯整合測試
使用 Mock driver，不需要真實網路連線
"""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from bs4 import BeautifulSoup

from distiller_scraper.scraper import DistillerScraperV2
from distiller_scraper.config import ScraperConfig


# ---------------------------------------------------------------------------
# HTML 工廠
# ---------------------------------------------------------------------------

def make_search_html(slugs: list) -> str:
    """建立含指定 spirit slug 的搜索結果 HTML"""
    items = "\n".join(
        f'<li class="spirit"><a href="/spirits/{slug}">Spirit {slug}</a></li>'
        for slug in slugs
    )
    return f"""
    <html><body>
      <ol class="spirits">
        {items}
      </ol>
    </body></html>
    """


def make_spirit_html(name: str) -> str:
    return f"""
    <html><body>
      <h1 class="secondary-headline name">{name}</h1>
      <p class="ultra-mini-headline type">Single Malt</p>
      <p class="ultra-mini-headline location">Distillery // Scotland</p>
      <div class="distiller-score">Score<span>90</span></div>
    </body></html>
    """


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_driver():
    driver = MagicMock()
    driver.execute_script.return_value = 1000  # scrollHeight
    driver.get_log.return_value = []
    return driver


@pytest.fixture
def scraper(mock_driver):
    s = DistillerScraperV2(headless=True, delay_min=0, delay_max=0)
    s.driver = mock_driver
    return s


# ---------------------------------------------------------------------------
# _get_search_queries 測試
# ---------------------------------------------------------------------------

class TestGetSearchQueries:
    def test_no_styles(self, scraper):
        queries = scraper._get_search_queries("whiskey", use_styles=False)
        assert len(queries) == 1
        url, label = queries[0]
        assert "category=whiskey" in url
        assert label == "whiskey"

    def test_whiskey_styles(self, scraper):
        queries = scraper._get_search_queries("whiskey", use_styles=True)
        assert len(queries) == len(ScraperConfig.WHISKEY_STYLES)
        for url, label in queries:
            assert "spirit_style_id=" in url

    def test_gin_styles(self, scraper):
        queries = scraper._get_search_queries("gin", use_styles=True)
        assert len(queries) == len(ScraperConfig.GIN_STYLES)

    def test_rum_styles(self, scraper):
        queries = scraper._get_search_queries("rum", use_styles=True)
        assert len(queries) == len(ScraperConfig.RUM_STYLES)

    def test_vodka_styles(self, scraper):
        queries = scraper._get_search_queries("vodka", use_styles=True)
        assert len(queries) == len(ScraperConfig.VODKA_STYLES)

    def test_unknown_category_with_styles(self, scraper):
        """未知類別 + use_styles=True 應 fallback 至單一基本查詢"""
        queries = scraper._get_search_queries("brandy", use_styles=True)
        assert len(queries) == 1

    def test_url_contains_sort(self, scraper):
        queries = scraper._get_search_queries("gin", use_styles=False)
        assert "sort=distiller_score" in queries[0][0]


# ---------------------------------------------------------------------------
# _fetch_spirit_urls_from_page 測試
# ---------------------------------------------------------------------------

class TestFetchSpiritUrlsFromPage:
    def test_returns_urls(self, scraper, mock_driver):
        mock_driver.page_source = make_search_html(["spirit-a", "spirit-b", "spirit-c"])
        urls = scraper._fetch_spirit_urls_from_page("https://distiller.com/search?category=whiskey")
        assert len(urls) == 3
        assert all("distiller.com/spirits/" in u for u in urls)

    def test_empty_page_returns_empty(self, scraper, mock_driver):
        mock_driver.page_source = make_search_html([])
        urls = scraper._fetch_spirit_urls_from_page("https://distiller.com/search?category=gin")
        assert urls == []

    def test_calls_scroll_page(self, scraper, mock_driver):
        mock_driver.page_source = make_search_html(["a"])
        mock_driver.execute_script.side_effect = [1000, 1000]  # 不增高 → 停止滾動
        with patch.object(scraper, "scroll_page") as mock_scroll:
            scraper._fetch_spirit_urls_from_page("https://distiller.com/search")
            mock_scroll.assert_called_once()


# ---------------------------------------------------------------------------
# scrape_category_paginated 測試
# ---------------------------------------------------------------------------

class TestScrapeCategoryPaginated:

    def _setup_pages(self, scraper, mock_driver, pages_data: dict):
        """
        pages_data: {page_url: [slug_list]}
        設定 driver 在 get(url) 後回傳對應的 page_source。
        """
        def side_effect_get(url):
            mock_driver._current_url = url

        def side_effect_page_source():
            url = mock_driver._current_url
            slugs = pages_data.get(url, [])
            return make_search_html(slugs)

        mock_driver.get.side_effect = side_effect_get
        type(mock_driver).page_source = PropertyMock(side_effect=side_effect_page_source)

    def test_single_page_result(self, scraper, mock_driver):
        """只有第一頁有結果、第二頁空 → 只爬一頁"""
        base = "https://distiller.com/search?category=whiskey&sort=distiller_score"
        page2 = base + "&page=2"
        pages = {
            base:  ["spirit-1", "spirit-2", "spirit-3"],
            page2: [],
        }
        self._setup_pages(scraper, mock_driver, pages)

        with patch.object(scraper, "scrape_spirit_detail") as mock_detail:
            mock_detail.side_effect = lambda url, **kw: {
                "name": url.split("/")[-1],
                "url": url,
                "spirit_type": "N/A",
                "brand": "N/A",
                "country": "N/A",
            }
            results = scraper.scrape_category_paginated(
                "whiskey", max_spirits=10, use_styles=False
            )

        assert len(results) == 3

    def test_two_pages(self, scraper, mock_driver):
        """第二頁有新內容 → 繼續爬、第三頁空停止"""
        base  = "https://distiller.com/search?category=whiskey&sort=distiller_score"
        page2 = base + "&page=2"
        page3 = base + "&page=3"
        pages = {
            base:  ["spirit-1", "spirit-2", "spirit-3"],
            page2: ["spirit-4", "spirit-5", "spirit-6"],
            page3: [],
        }
        self._setup_pages(scraper, mock_driver, pages)

        with patch.object(scraper, "scrape_spirit_detail") as mock_detail:
            mock_detail.side_effect = lambda url, **kw: {
                "name": url.split("/")[-1],
                "url": url,
                "spirit_type": "N/A",
                "brand": "N/A",
                "country": "N/A",
            }
            results = scraper.scrape_category_paginated(
                "whiskey", max_spirits=20, use_styles=False
            )

        assert len(results) == 6

    def test_respects_max_spirits(self, scraper, mock_driver):
        """達到 max_spirits 後停止"""
        base  = "https://distiller.com/search?category=whiskey&sort=distiller_score"
        page2 = base + "&page=2"
        pages = {
            base:  ["spirit-1", "spirit-2", "spirit-3"],
            page2: ["spirit-4", "spirit-5", "spirit-6"],
        }
        self._setup_pages(scraper, mock_driver, pages)

        with patch.object(scraper, "scrape_spirit_detail") as mock_detail:
            mock_detail.side_effect = lambda url, **kw: {
                "name": url.split("/")[-1],
                "url": url,
                "spirit_type": "N/A",
                "brand": "N/A",
                "country": "N/A",
            }
            results = scraper.scrape_category_paginated(
                "whiskey", max_spirits=4, use_styles=False
            )

        assert len(results) <= 4

    def test_broken_pagination_with_known_urls_skips(self, scraper, mock_driver):
        """第二頁與第一頁完全相同且全在 seen_urls → 分頁無效，跳過"""
        base  = "https://distiller.com/search?category=whiskey&sort=distiller_score"
        page2 = base + "&page=2"
        pages = {
            base:  ["spirit-1", "spirit-2", "spirit-3", "spirit-4"],
            # 4 個 URL 全與第一頁相同 → 分頁無效
            page2: ["spirit-1", "spirit-2", "spirit-3", "spirit-4"],
        }
        self._setup_pages(scraper, mock_driver, pages)
        # 預先加入 seen_urls 模擬已爬完
        scraper.seen_urls = {
            f"https://distiller.com/spirits/spirit-{i}" for i in range(1, 5)
        }

        with patch.object(scraper, "scrape_spirit_detail") as mock_detail:
            mock_detail.return_value = None
            results = scraper.scrape_category_paginated(
                "whiskey", max_spirits=50, use_styles=False
            )

        # 分頁無效 + 全在 seen_urls → 跳過，不爬任何詳情
        assert mock_detail.call_count == 0

    def test_continues_past_duplicate_pages(self, scraper, mock_driver, mocker):
        """頁 1-2 全在 seen_urls 但 URL 不同 → 分頁有效 → 繼續到第 3 頁找到新 URL"""
        mocker.patch("time.sleep")
        base  = "https://distiller.com/search?category=whiskey&sort=distiller_score"
        page2 = base + "&page=2"
        page3 = base + "&page=3"
        page4 = base + "&page=4"
        pages = {
            base:  ["spirit-1", "spirit-2"],   # 已知
            page2: ["spirit-3", "spirit-4"],   # 已知但不同 → pagination_works=True
            page3: ["spirit-5", "spirit-6"],   # 新 URL！
            page4: [],
        }
        self._setup_pages(scraper, mock_driver, pages)
        # 頁 1-2 的 URL 已在 seen_urls
        scraper.seen_urls = {
            f"https://distiller.com/spirits/spirit-{i}" for i in range(1, 5)
        }

        with patch.object(scraper, "scrape_spirit_detail") as mock_detail:
            mock_detail.side_effect = lambda url, **kw: {
                "name": url.split("/")[-1],
                "url": url,
                "spirit_type": "N/A",
                "brand": "N/A",
                "country": "N/A",
            }
            results = scraper.scrape_category_paginated(
                "whiskey", max_spirits=50, use_styles=False
            )

        # 應該到第 3 頁並爬取 spirit-5, spirit-6
        assert len(results) >= 2
        result_urls = [r["url"] for r in results]
        assert "https://distiller.com/spirits/spirit-5" in result_urls
        assert "https://distiller.com/spirits/spirit-6" in result_urls

    def test_stops_after_consecutive_dup_pages(self, scraper, mock_driver, mocker):
        """連續 MAX_CONSECUTIVE_DUP_PAGES 頁全為已知 URL → 停止"""
        mocker.patch("time.sleep")
        base  = "https://distiller.com/search?category=whiskey&sort=distiller_score"
        # 建立 6 頁：頁 1-2 不同(確認分頁有效)，頁 3-5 全已知 → 觸發停止
        pages = {}
        pages[base] = ["spirit-1", "spirit-2"]
        for p in range(2, 7):
            url = base + f"&page={p}"
            pages[url] = [f"spirit-{p*2-1}", f"spirit-{p*2}"]
        self._setup_pages(scraper, mock_driver, pages)

        # 全部 URL 都已在 seen_urls
        scraper.seen_urls = {
            f"https://distiller.com/spirits/spirit-{i}" for i in range(1, 13)
        }

        with patch.object(scraper, "scrape_spirit_detail") as mock_detail:
            mock_detail.return_value = None
            results = scraper.scrape_category_paginated(
                "whiskey", max_spirits=50, use_styles=False
            )

        # 分頁有效但連續 3 頁（頁 2-4）無新 URL → 停止
        # 不應爬到第 6 頁
        assert mock_detail.call_count == 0

    def test_resets_consecutive_dup_on_new_urls(self, scraper, mock_driver, mocker):
        """
        頁 1-2 已知 → consecutive=1
        頁 3 有新 URL → consecutive 重置為 0
        頁 4-6 已知 → consecutive 累積到 3 → 停止
        """
        mocker.patch("time.sleep")
        base  = "https://distiller.com/search?category=whiskey&sort=distiller_score"
        pages = {}
        pages[base] = ["spirit-1", "spirit-2"]
        pages[base + "&page=2"] = ["spirit-3", "spirit-4"]      # 已知, pagination_works=True, consec=1
        pages[base + "&page=3"] = ["spirit-new-1", "spirit-new-2"]  # 新！ consec=0
        pages[base + "&page=4"] = ["spirit-5", "spirit-6"]      # 已知, consec=1
        pages[base + "&page=5"] = ["spirit-7", "spirit-8"]      # 已知, consec=2
        pages[base + "&page=6"] = ["spirit-9", "spirit-10"]     # 已知, consec=3 → 停止
        pages[base + "&page=7"] = ["spirit-11", "spirit-12"]    # 不應到達
        self._setup_pages(scraper, mock_driver, pages)

        # 除了 spirit-new-1, spirit-new-2 之外全已知
        scraper.seen_urls = {
            f"https://distiller.com/spirits/spirit-{i}" for i in range(1, 13)
        }

        with patch.object(scraper, "scrape_spirit_detail") as mock_detail:
            mock_detail.side_effect = lambda url, **kw: {
                "name": url.split("/")[-1],
                "url": url,
                "spirit_type": "N/A",
                "brand": "N/A",
                "country": "N/A",
            }
            results = scraper.scrape_category_paginated(
                "whiskey", max_spirits=50, use_styles=False
            )

        # 頁 3 的新 URL 應被爬取
        result_names = [r["name"] for r in results]
        assert "spirit-new-1" in result_names or "spirit-new-2" in result_names
        # 頁 7 不應被到達（consecutive_dup 在頁 6 達到 3）
        called_urls = [call.args[0] for call in mock_detail.call_args_list]
        assert "https://distiller.com/spirits/spirit-11" not in called_urls

    def test_skips_seen_urls(self, scraper, mock_driver):
        """已在 seen_urls 的 URL 不重複爬取"""
        base = "https://distiller.com/search?category=gin&sort=distiller_score"
        pages = {base: ["spirit-1", "spirit-2"]}
        self._setup_pages(scraper, mock_driver, pages)
        scraper.seen_urls.add("https://distiller.com/spirits/spirit-1")

        with patch.object(scraper, "scrape_spirit_detail") as mock_detail:
            mock_detail.side_effect = lambda url, **kw: {
                "name": "Spirit 2", "url": url,
                "spirit_type": "N/A", "brand": "N/A", "country": "N/A",
            }
            results = scraper.scrape_category_paginated(
                "gin", max_spirits=10, use_styles=False
            )

        # spirit-1 被跳過，只爬 spirit-2
        called_urls = [call.args[0] for call in mock_detail.call_args_list]
        assert "https://distiller.com/spirits/spirit-1" not in called_urls
        assert "https://distiller.com/spirits/spirit-2" in called_urls


# ---------------------------------------------------------------------------
# scrape_category 路由測試
# ---------------------------------------------------------------------------

class TestScrapeCategoryRouting:
    def test_uses_paginated_by_default(self, scraper):
        with patch.object(scraper, "scrape_category_paginated", return_value=[]) as mock_pag:
            scraper.scrape_category("whiskey", use_pagination=True)
            mock_pag.assert_called_once()

    def test_uses_scroll_when_disabled(self, scraper, mock_driver):
        mock_driver.page_source = make_search_html([])
        with patch.object(scraper, "scrape_category_paginated") as mock_pag:
            scraper.scrape_category("whiskey", use_pagination=False)
            mock_pag.assert_not_called()

    def test_pagination_flag_from_config(self, scraper):
        """use_pagination=None 時應讀取 ScraperConfig.PAGINATION_ENABLED"""
        with patch.object(scraper, "scrape_category_paginated", return_value=[]) as mock_pag:
            with patch.object(ScraperConfig, "PAGINATION_ENABLED", True):
                scraper.scrape_category("whiskey", use_pagination=None)
                mock_pag.assert_called_once()
