"""
CSS 選擇器定義
基於 2026-01-27 對 Distiller.com 的實際 HTML 結構分析
已驗證選擇器與實際網站 HTML 匹配
"""

import json
from typing import Optional, Dict, Any


class Selectors:
    """CSS 選擇器 - 用於提取烈酒詳細資訊"""

    # ==================== 烈酒詳情頁面 ====================

    # 品名 (已驗證: <h1 class='secondary-headline name'>Hibiki 21 Year</h1>)
    NAME = "h1.secondary-headline.name"
    NAME_FALLBACK = "h1[itemprop='name']"

    # 類別/風格 (已驗證: <p class='ultra-mini-headline type'>Blended</p>)
    SPIRIT_TYPE = "p.ultra-mini-headline.type"

    # 產地資訊 (已驗證: <p class='ultra-mini-headline location'>Suntory Whisky // Japan</p>)
    LOCATION = "p.ultra-mini-headline.location"

    # 特殊標記 (已驗證: <div class='spirit-badge'>RARE</div>)
    BADGE = "div.spirit-badge"

    # 年份 (已驗證: <li class='detail age'><div class='value'>21 Year</div></li>)
    AGE = "li.detail.age .value"
    AGE_CONTAINER = "li.detail.age"

    # 酒精濃度 (已驗證: <li class='detail abv'><div class='value'>43.0</div></li>)
    ABV = "li.detail.abv .value"
    ABV_CONTAINER = "li.detail.abv"

    # 價格等級 (已驗證: <div class='spirit-cost cost-5'>)
    COST = "div.spirit-cost"
    COST_CONTAINER = "li.detail.cost .value"

    # 風格描述 (已驗證: <li class='detail whiskey-style'>)
    STYLE_LABEL = "li.detail.whiskey-style .label"
    STYLE_VALUE = "li.detail.whiskey-style .value"

    # 桶型 (已驗證: <li class='detail cask-type'>)
    CASK_TYPE_LABEL = "li.detail.cask-type .label"
    CASK_TYPE_VALUE = "li.detail.cask-type .value"

    # ==================== 評分相關 ====================

    # 專家評分 (已驗證: <div class='distiller-score'>Score<span>99</span></div>)
    EXPERT_SCORE = "div.distiller-score span"
    EXPERT_SCORE_CONTAINER = "div.distiller-score"

    # 社群評分 (已驗證: <span itemprop='ratingValue'>4.52</span>)
    COMMUNITY_SCORE = "span[itemprop='ratingValue']"
    COMMUNITY_SCORE_CONTAINER = "div.rating-display.average-user-rating"

    # 評論數量 (已驗證: <span itemprop='ratingCount'>899</span>)
    REVIEW_COUNT = "span[itemprop='ratingCount']"

    # ==================== 描述與風味 ====================

    # 產品描述 (已驗證: <p class='description' itemprop='description'>)
    DESCRIPTION = "p.description[itemprop='description']"
    DESCRIPTION_FIRST = "p.description[itemprop='description_first_half']"
    DESCRIPTION_SECOND = "p.description[itemprop='description_second_half']"

    # 品飲筆記 (已驗證: <blockquote itemprop='reviewBody'>)
    TASTING_NOTES = "blockquote[itemprop='reviewBody']"

    # 專家資訊 (已驗證: <a href='/tasting_table#expert_1' itemprop='author'>)
    EXPERT_NAME = "div.meet-experts a[itemprop='author']"

    # 風味圖譜 (已驗證: <canvas class='js-flavor-profile-chart' data-flavors='{...}'>)
    FLAVOR_CHART = "canvas.js-flavor-profile-chart"
    FLAVOR_HEADLINE = "h3.secondary-headline.flavors"

    # ==================== 搜索結果頁面 ====================

    # 烈酒列表項目 (已驗證: <ol class='spirits'><li class='spirit'>)
    SPIRIT_LIST_ITEM = "ol.spirits li.spirit"
    SPIRIT_LINK = "ol.spirits li.spirit a"

    # 列表中的評分 (已驗證)
    LIST_DISTILLER_SCORE = "div.distiller-score"
    LIST_COMMUNITY_RATING = "div.community-rating"

    # 列表中的名稱 (已驗證: <div class='name'>Monkey 47 Dry Gin</div>)
    LIST_NAME = "h5.name-content .name"
    LIST_ORIGIN = "p.origin"

    # ==================== 其他 ====================

    # 類別選擇按鈕
    CATEGORY_BUTTONS = "ul.spirit-family-select__options button"

    # 篩選表單
    FILTER_FORM = "form.filter"
    STYLE_SELECT = "select[name='spirit_style_id']"
    CATEGORY_SELECT = "select[name='spirit_category_id']"
    COUNTRY_SELECT = "select[name='country_id']"

    # 排序選項
    SORT_SELECT = "select[name='sort']"


class DataExtractor:
    """從 BeautifulSoup 解析結果中提取資料的輔助類別"""

    @staticmethod
    def extract_text(soup, selector: str, default: str = "N/A") -> str:
        """提取元素的文字內容"""
        elem = soup.select_one(selector)
        if elem:
            text = elem.get_text(strip=True)
            return text if text else default
        return default

    @staticmethod
    def extract_text_multi(soup, selectors: list, default: str = "N/A") -> str:
        """嘗試多個選擇器，返回第一個成功的結果"""
        for selector in selectors:
            result = DataExtractor.extract_text(soup, selector, "")
            if result:
                return result
        return default

    @staticmethod
    def extract_attribute(soup, selector: str, attr: str, default: str = "N/A") -> str:
        """提取元素的屬性值"""
        elem = soup.select_one(selector)
        if elem and attr in elem.attrs:
            return elem[attr]
        return default

    @staticmethod
    def extract_flavor_profile(soup) -> Dict[str, Any]:
        """提取風味圖譜資料 (從 data-flavors 屬性)"""
        elem = soup.select_one(Selectors.FLAVOR_CHART)
        if elem and "data-flavors" in elem.attrs:
            try:
                return json.loads(elem["data-flavors"])
            except json.JSONDecodeError:
                pass
        return {}

    @staticmethod
    def extract_location_parts(soup) -> tuple:
        """從 location 字串提取品牌和國家"""
        location_text = DataExtractor.extract_text(soup, Selectors.LOCATION)
        if location_text and "//" in location_text:
            parts = location_text.split("//")
            brand = parts[0].strip() if len(parts) > 0 else "N/A"
            country = parts[1].strip() if len(parts) > 1 else "N/A"
            return brand, country
        return "N/A", location_text if location_text != "N/A" else "N/A"

    @staticmethod
    def extract_cost_level(soup) -> str:
        """提取價格等級 (1-5)"""
        elem = soup.select_one(Selectors.COST)
        if elem:
            classes = elem.get("class", [])
            for cls in classes:
                if cls.startswith("cost-"):
                    try:
                        return cls.replace("cost-", "")
                    except ValueError:
                        pass
        return "N/A"

    @staticmethod
    def extract_spirit_details(soup) -> dict:
        """提取烈酒完整詳細資料"""
        # 提取品牌和國家
        brand, country = DataExtractor.extract_location_parts(soup)

        # 提取風味資料
        flavor_data = DataExtractor.extract_flavor_profile(soup)
        flavor_summary = DataExtractor.extract_text(soup, Selectors.FLAVOR_HEADLINE)

        return {
            "name": DataExtractor.extract_text_multi(
                soup, [Selectors.NAME, Selectors.NAME_FALLBACK]
            ),
            "spirit_type": DataExtractor.extract_text(soup, Selectors.SPIRIT_TYPE),
            "brand": brand,
            "country": country,
            "badge": DataExtractor.extract_text(soup, Selectors.BADGE),
            "age": DataExtractor.extract_text(soup, Selectors.AGE),
            "abv": DataExtractor.extract_text(soup, Selectors.ABV),
            "cost_level": DataExtractor.extract_cost_level(soup),
            "cask_type": DataExtractor.extract_text(soup, Selectors.CASK_TYPE_VALUE),
            "expert_score": DataExtractor.extract_text(soup, Selectors.EXPERT_SCORE),
            "community_score": DataExtractor.extract_text(
                soup, Selectors.COMMUNITY_SCORE
            ),
            "review_count": DataExtractor.extract_text(soup, Selectors.REVIEW_COUNT),
            "description": DataExtractor.extract_text_multi(
                soup,
                [
                    Selectors.DESCRIPTION,
                    Selectors.DESCRIPTION_FIRST,
                ],
            ),
            "tasting_notes": DataExtractor.extract_text(soup, Selectors.TASTING_NOTES),
            "expert_name": DataExtractor.extract_text(soup, Selectors.EXPERT_NAME),
            "flavor_summary": flavor_summary,
            "flavor_data": flavor_data,
        }

    @staticmethod
    def extract_list_item(item_soup) -> dict:
        """從搜索結果列表項目中提取資料"""
        link = item_soup.select_one("a")
        href = link.get("href", "") if link else ""

        return {
            "name": DataExtractor.extract_text(item_soup, Selectors.LIST_NAME),
            "url": f"https://distiller.com{href}" if href.startswith("/") else href,
            "distiller_score": DataExtractor.extract_text(
                item_soup, Selectors.LIST_DISTILLER_SCORE
            ),
            "community_rating": DataExtractor.extract_text(
                item_soup, Selectors.LIST_COMMUNITY_RATING
            ),
            "origin": DataExtractor.extract_text(item_soup, Selectors.LIST_ORIGIN),
        }


class SearchURLBuilder:
    """搜索 URL 構建器"""

    BASE_URL = "https://distiller.com"
    SEARCH_URL = "https://distiller.com/search"
    SPIRIT_URL_PREFIX = "https://distiller.com/spirits/"

    @classmethod
    def build_search_url(
        cls,
        category: str = None,
        spirit_style_id: str = None,
        country_id: str = None,
        cost_bracket: str = None,
        sort: str = "distiller_score",
        term: str = None,
    ) -> str:
        """構建搜索 URL"""
        params = []

        if category:
            params.append(f"category={category}")
        if spirit_style_id:
            params.append(f"spirit_style_id={spirit_style_id}")
        if country_id:
            params.append(f"country_id={country_id}")
        if cost_bracket:
            params.append(f"cost_bracket={cost_bracket}")
        if sort:
            params.append(f"sort={sort}")
        if term:
            params.append(f"term={term}")

        if params:
            return f"{cls.SEARCH_URL}?{'&'.join(params)}"
        return cls.SEARCH_URL

    @classmethod
    def spirit_url(cls, slug: str) -> str:
        """構建烈酒詳情頁 URL"""
        if slug.startswith("http"):
            return slug
        if slug.startswith("/"):
            return f"{cls.BASE_URL}{slug}"
        return f"{cls.SPIRIT_URL_PREFIX}{slug}"
