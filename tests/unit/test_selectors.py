"""
單元測試 - CSS 選擇器與資料提取器
測試 DataExtractor 類別的各種提取方法
"""

import json

import pytest
from bs4 import BeautifulSoup

from distiller_scraper.selectors import DataExtractor, Selectors


class TestSelectors:
    """測試 CSS 選擇器常數定義"""

    def test_name_selector_defined(self):
        """確認品名選擇器已定義"""
        assert Selectors.NAME == "h1.secondary-headline.name"
        assert Selectors.NAME_FALLBACK == "h1[itemprop='name']"

    def test_score_selectors_defined(self):
        """確認評分選擇器已定義"""
        assert Selectors.EXPERT_SCORE == "div.distiller-score span"
        assert Selectors.COMMUNITY_SCORE == "span[itemprop='ratingValue']"

    def test_list_selectors_defined(self):
        """確認列表選擇器已定義"""
        assert Selectors.SPIRIT_LIST_ITEM == "ol.spirits li.spirit"


class TestDataExtractorBasic:
    """測試 DataExtractor 基本方法"""

    def test_extract_text_success(self, sample_spirit_detail_soup):
        """測試成功提取文字"""
        result = DataExtractor.extract_text(sample_spirit_detail_soup, Selectors.NAME)
        assert result == "Highland Park 18 Year"

    def test_extract_text_not_found(self, empty_soup):
        """測試找不到元素時返回預設值"""
        result = DataExtractor.extract_text(empty_soup, Selectors.NAME)
        assert result == "N/A"

    def test_extract_text_custom_default(self, empty_soup):
        """測試自訂預設值"""
        result = DataExtractor.extract_text(
            empty_soup, Selectors.NAME, default="Unknown"
        )
        assert result == "Unknown"

    def test_extract_text_multi_first_match(self, sample_spirit_detail_soup):
        """測試多選擇器使用第一個匹配"""
        result = DataExtractor.extract_text_multi(
            sample_spirit_detail_soup,
            [Selectors.NAME, Selectors.NAME_FALLBACK],
        )
        assert result == "Highland Park 18 Year"

    def test_extract_text_multi_fallback(self, empty_soup):
        """測試多選擇器全部失敗時返回預設值"""
        result = DataExtractor.extract_text_multi(
            empty_soup,
            [Selectors.NAME, Selectors.NAME_FALLBACK],
        )
        assert result == "N/A"


class TestDataExtractorSpirit:
    """測試 DataExtractor 烈酒資料提取"""

    def test_extract_spirit_type(self, sample_spirit_detail_soup):
        """測試提取烈酒類型"""
        result = DataExtractor.extract_text(
            sample_spirit_detail_soup, Selectors.SPIRIT_TYPE
        )
        assert result == "Single Malt"

    def test_extract_age(self, sample_spirit_detail_soup):
        """測試提取年份"""
        result = DataExtractor.extract_text(sample_spirit_detail_soup, Selectors.AGE)
        assert result == "18 Year"

    def test_extract_abv(self, sample_spirit_detail_soup):
        """測試提取酒精濃度"""
        result = DataExtractor.extract_text(sample_spirit_detail_soup, Selectors.ABV)
        assert result == "43.0"

    def test_extract_expert_score(self, sample_spirit_detail_soup):
        """測試提取專家評分"""
        result = DataExtractor.extract_text(
            sample_spirit_detail_soup, Selectors.EXPERT_SCORE
        )
        assert result == "99"

    def test_extract_community_score(self, sample_spirit_detail_soup):
        """測試提取社群評分"""
        result = DataExtractor.extract_text(
            sample_spirit_detail_soup, Selectors.COMMUNITY_SCORE
        )
        assert result == "4.47"

    def test_extract_review_count(self, sample_spirit_detail_soup):
        """測試提取評論數量"""
        result = DataExtractor.extract_text(
            sample_spirit_detail_soup, Selectors.REVIEW_COUNT
        )
        assert result == "3076"

    def test_extract_cask_type(self, sample_spirit_detail_soup):
        """測試提取桶型"""
        result = DataExtractor.extract_text(
            sample_spirit_detail_soup, Selectors.CASK_TYPE_VALUE
        )
        assert result == "ex-sherry"


class TestDataExtractorLocation:
    """測試 DataExtractor 產地資訊提取"""

    def test_extract_location_parts_success(self, sample_spirit_detail_soup):
        """測試成功分離品牌與國家"""
        brand, country = DataExtractor.extract_location_parts(sample_spirit_detail_soup)
        assert brand == "Highland Park"
        assert country == "Islands, Scotland"

    def test_extract_location_parts_no_separator(self):
        """測試沒有分隔符時的處理"""
        html = '<p class="ultra-mini-headline location">Scotland</p>'
        soup = BeautifulSoup(html, "html.parser")
        brand, country = DataExtractor.extract_location_parts(soup)
        assert brand == "N/A"
        assert country == "Scotland"

    def test_extract_location_parts_missing(self, empty_soup):
        """測試缺少產地資訊"""
        brand, country = DataExtractor.extract_location_parts(empty_soup)
        assert brand == "N/A"
        assert country == "N/A"


class TestDataExtractorFlavor:
    """測試 DataExtractor 風味圖譜提取"""

    def test_extract_flavor_profile_success(self, sample_spirit_detail_soup):
        """測試成功提取風味資料"""
        result = DataExtractor.extract_flavor_profile(sample_spirit_detail_soup)
        assert isinstance(result, dict)
        assert result["smoky"] == 40
        assert result["rich"] == 80
        assert result["fruity"] == 70
        assert len(result) == 14  # 14 種風味屬性

    def test_extract_flavor_profile_missing(self, empty_soup):
        """測試缺少風味資料時返回空字典"""
        result = DataExtractor.extract_flavor_profile(empty_soup)
        assert result == {}

    def test_extract_flavor_profile_invalid_json(self):
        """測試無效 JSON 時返回空字典"""
        html = '<canvas class="js-flavor-profile-chart" data-flavors="invalid json"></canvas>'
        soup = BeautifulSoup(html, "html.parser")
        result = DataExtractor.extract_flavor_profile(soup)
        assert result == {}


class TestDataExtractorCost:
    """測試 DataExtractor 價格等級提取"""

    def test_extract_cost_level_success(self, sample_spirit_detail_soup):
        """測試成功提取價格等級"""
        result = DataExtractor.extract_cost_level(sample_spirit_detail_soup)
        assert result == "4"

    def test_extract_cost_level_missing(self, empty_soup):
        """測試缺少價格資訊"""
        result = DataExtractor.extract_cost_level(empty_soup)
        assert result == "N/A"

    @pytest.mark.parametrize(
        "cost_class,expected",
        [
            ("cost-1", "1"),
            ("cost-2", "2"),
            ("cost-3", "3"),
            ("cost-4", "4"),
            ("cost-5", "5"),
        ],
    )
    def test_extract_cost_level_various(self, cost_class, expected):
        """測試各種價格等級"""
        html = f'<div class="spirit-cost {cost_class}"></div>'
        soup = BeautifulSoup(html, "html.parser")
        result = DataExtractor.extract_cost_level(soup)
        assert result == expected


class TestDataExtractorFullDetails:
    """測試 DataExtractor 完整資料提取"""

    def test_extract_spirit_details_complete(self, sample_spirit_detail_soup):
        """測試提取完整烈酒詳情"""
        result = DataExtractor.extract_spirit_details(sample_spirit_detail_soup)

        assert result["name"] == "Highland Park 18 Year"
        assert result["spirit_type"] == "Single Malt"
        assert result["brand"] == "Highland Park"
        assert result["country"] == "Islands, Scotland"
        assert result["badge"] == "RARE"
        assert result["age"] == "18 Year"
        assert result["abv"] == "43.0"
        assert result["cost_level"] == "4"
        assert result["cask_type"] == "ex-sherry"
        assert result["expert_score"] == "99"
        assert result["community_score"] == "4.47"
        assert result["review_count"] == "3076"
        assert "lightly-peated single malt" in result["description"]
        assert "sweet smoke" in result["tasting_notes"]
        assert result["expert_name"] == "Stephanie Moreno"
        assert result["flavor_summary"] == "Rich & Fruity"
        assert isinstance(result["flavor_data"], dict)
        assert result["flavor_data"]["smoky"] == 40

    def test_extract_spirit_details_partial(self, partial_spirit_soup):
        """測試部分資料的處理"""
        result = DataExtractor.extract_spirit_details(partial_spirit_soup)

        assert result["name"] == "Test Spirit"
        assert result["spirit_type"] == "Bourbon"
        assert result["expert_score"] == "85"
        # 缺失欄位應為 N/A
        assert result["age"] == "N/A"
        assert result["abv"] == "N/A"
        assert result["brand"] == "N/A"

    def test_extract_spirit_details_empty(self, empty_soup):
        """測試空白頁面"""
        result = DataExtractor.extract_spirit_details(empty_soup)

        assert result["name"] == "N/A"
        assert result["spirit_type"] == "N/A"
        assert result["flavor_data"] == {}


class TestDataExtractorListItem:
    """測試 DataExtractor 列表項目提取"""

    def test_extract_list_item(self, sample_search_results_soup):
        """測試提取列表項目"""
        items = sample_search_results_soup.select(Selectors.SPIRIT_LIST_ITEM)
        assert len(items) == 4

        # 測試第一個項目
        result = DataExtractor.extract_list_item(items[0])
        assert result["name"] == "Highland Park 18 Year"
        assert result["url"] == "https://distiller.com/spirits/highland-park-18"
        assert result["origin"] == "Islands, Scotland"

    def test_extract_list_item_absolute_url(self, sample_search_results_soup):
        """測試已是絕對 URL 的項目"""
        items = sample_search_results_soup.select(Selectors.SPIRIT_LIST_ITEM)
        # 第四個項目使用絕對 URL
        result = DataExtractor.extract_list_item(items[3])
        assert result["url"] == "https://distiller.com/spirits/lagavulin-16"
