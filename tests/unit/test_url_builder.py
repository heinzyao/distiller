"""
單元測試 - SearchURLBuilder
測試 URL 構建器的各種參數組合
"""

import pytest

from distiller_scraper.selectors import SearchURLBuilder


class TestSearchURLBuilder:
    """測試 SearchURLBuilder 類別"""

    def test_base_url(self):
        """確認基礎 URL 定義"""
        assert SearchURLBuilder.BASE_URL == "https://distiller.com"
        assert SearchURLBuilder.SEARCH_URL == "https://distiller.com/search"

    def test_build_search_url_no_params(self):
        """測試無參數時返回基礎搜索 URL（預設有 sort）"""
        result = SearchURLBuilder.build_search_url()
        # 預設會加入 sort=distiller_score
        assert result == "https://distiller.com/search?sort=distiller_score"

    def test_build_search_url_category_only(self):
        """測試只有類別參數"""
        result = SearchURLBuilder.build_search_url(category="whiskey")
        assert "category=whiskey" in result
        assert "sort=distiller_score" in result

    def test_build_search_url_with_style(self):
        """測試類別與風格參數"""
        result = SearchURLBuilder.build_search_url(
            category="whiskey",
            spirit_style_id="1",
        )
        assert "category=whiskey" in result
        assert "spirit_style_id=1" in result

    def test_build_search_url_with_country(self):
        """測試包含國家參數"""
        result = SearchURLBuilder.build_search_url(
            category="whiskey",
            country_id="1",
        )
        assert "country_id=1" in result

    def test_build_search_url_with_cost(self):
        """測試包含價格區間參數"""
        result = SearchURLBuilder.build_search_url(
            category="whiskey",
            cost_bracket="3",
        )
        assert "cost_bracket=3" in result

    def test_build_search_url_custom_sort(self):
        """測試自訂排序"""
        result = SearchURLBuilder.build_search_url(
            category="whiskey",
            sort="community_rating",
        )
        assert "sort=community_rating" in result

    def test_build_search_url_with_term(self):
        """測試包含搜索詞"""
        result = SearchURLBuilder.build_search_url(term="highland")
        assert "term=highland" in result

    def test_build_search_url_all_params(self):
        """測試所有參數組合"""
        result = SearchURLBuilder.build_search_url(
            category="whiskey",
            spirit_style_id="1",
            country_id="1",
            cost_bracket="4",
            sort="distiller_score",
            term="highland",
        )
        assert result.startswith("https://distiller.com/search?")
        assert "category=whiskey" in result
        assert "spirit_style_id=1" in result
        assert "country_id=1" in result
        assert "cost_bracket=4" in result
        assert "sort=distiller_score" in result
        assert "term=highland" in result

    def test_build_search_url_no_sort(self):
        """測試不包含排序參數"""
        result = SearchURLBuilder.build_search_url(
            category="whiskey",
            sort=None,
        )
        assert "sort" not in result

    def test_build_search_url_page_1_omitted(self):
        """page=1 不應出現在 URL 中（避免影響部分網站）"""
        result = SearchURLBuilder.build_search_url(category="whiskey", page=1)
        assert "page=" not in result

    def test_build_search_url_page_2(self):
        """page=2 應正確附加"""
        result = SearchURLBuilder.build_search_url(category="whiskey", page=2)
        assert "page=2" in result

    def test_build_search_url_page_10(self):
        """大頁碼應正確附加"""
        result = SearchURLBuilder.build_search_url(category="gin", page=10)
        assert "page=10" in result
        assert "category=gin" in result

    def test_build_search_url_page_with_style(self):
        """分頁 + 風格篩選"""
        result = SearchURLBuilder.build_search_url(
            category="whiskey",
            spirit_style_id="1",
            page=3,
        )
        assert "spirit_style_id=1" in result
        assert "page=3" in result


class TestSpiritURL:
    """測試 spirit_url 方法"""

    def test_spirit_url_slug_only(self):
        """測試只有 slug"""
        result = SearchURLBuilder.spirit_url("highland-park-18")
        assert result == "https://distiller.com/spirits/highland-park-18"

    def test_spirit_url_with_leading_slash(self):
        """測試以斜線開頭的路徑"""
        result = SearchURLBuilder.spirit_url("/spirits/highland-park-18")
        assert result == "https://distiller.com/spirits/highland-park-18"

    def test_spirit_url_full_url(self):
        """測試已經是完整 URL"""
        full_url = "https://distiller.com/spirits/highland-park-18"
        result = SearchURLBuilder.spirit_url(full_url)
        assert result == full_url

    def test_spirit_url_http_url(self):
        """測試 HTTP URL（不常見但可能）"""
        http_url = "http://distiller.com/spirits/highland-park-18"
        result = SearchURLBuilder.spirit_url(http_url)
        assert result == http_url


class TestURLFormats:
    """測試各類別的 URL 格式"""

    @pytest.mark.parametrize(
        "category",
        [
            "whiskey",
            "gin",
            "rum",
            "vodka",
            "brandy",
            "tequila-mezcal",
            "liqueurs-bitters",
        ],
    )
    def test_category_urls(self, category):
        """測試各類別 URL 格式正確"""
        result = SearchURLBuilder.build_search_url(category=category)
        assert f"category={category}" in result
        assert result.startswith("https://distiller.com/search?")
