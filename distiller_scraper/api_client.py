"""
Distiller.com 直接 HTTP API 客戶端：嘗試繞過 Selenium 渲染，直接呼叫後端 JSON API。

設計理由——為何需要 API 探測？
Selenium 爬取每頁需要 5-10 秒（瀏覽器啟動 + 頁面渲染 + JavaScript 執行）。
若 Distiller.com 有開放的 JSON API 端點，直接 HTTP 請求只需 0.5-1 秒，
速度提升約 10 倍，且更穩定（不受 Chrome 崩潰影響）。

探測策略（兩階段）
------------------
1. XHR 分析（動態探測）：
   利用 scraper.capture_xhr_requests() 捕獲瀏覽器載入頁面時發送的 XHR 請求，
   過濾出可能是 JSON API 的 URL（排除靜態資源），逐一測試可用性

2. 候選路徑測試（靜態探測）：
   嘗試常見的 Rails .json 慣例（/search.json, /spirits/{slug}.json）
   和 REST API 路徑（/api/v1/spirits/search），適用於 XHR 分析未找到端點的情況

回傳值約定
----------
- fetch_search_results()：[] 表示「本頁無結果」（合法），None 表示「請求失敗」
  → 呼叫端可區分「已到資料末尾」與「需要 fallback 至 Selenium」

- fetch_spirit_detail()：None 表示 API 不可用或解析失敗
  → 呼叫端 fallback 至 Selenium 爬取詳情頁

_map_search_response / _map_detail_response 的設計
---------------------------------------------------
API 回應格式不固定（list、{spirits:[...]}, {data:{...}} 等）
用防禦性解析策略，逐一嘗試已知格式，確保回應格式變更時不會直接崩潰
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urljoin, urlparse

import requests

from .config import ScraperConfig

logger = logging.getLogger(__name__)


class DistillerAPIClient:
    """Distiller.com 直接 HTTP API 客戶端"""

    BASE_URL = "https://distiller.com"

    # 依優先順序嘗試的搜索端點候選路徑
    SEARCH_CANDIDATES = [
        "/search.json",
        "/api/v1/spirits/search",
        "/api/v1/search",
        "/api/spirits",
        "/spirits.json",
    ]

    # 詳情端點候選路徑（{slug} 佔位符）
    DETAIL_CANDIDATES = [
        "/spirits/{slug}.json",
        "/api/v1/spirits/{slug}",
        "/api/spirits/{slug}",
    ]

    # 探測時使用的測試 slug（高知名度烈酒，大機率存在）
    _TEST_SLUG = "highland-park-12-year"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": ScraperConfig.USER_AGENT,
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "en-US,en;q=0.9",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": self.BASE_URL,
            }
        )
        self.search_endpoint: Optional[str] = None
        self.detail_endpoint_template: Optional[str] = None
        self._available = False
        self._discovered = False

    # ------------------------------------------------------------------
    # 公開屬性
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """API 是否已探測到可用端點"""
        return self._available

    # ------------------------------------------------------------------
    # 探測
    # ------------------------------------------------------------------

    def discover(self, xhr_urls: List[str] = None) -> Dict:
        """
        探測可用的 API 端點。

        參數：
            xhr_urls: 由 scraper.capture_xhr_requests() 取得的 XHR URL 列表，
                      可為 None（略過 XHR 分析，直接嘗試候選路徑）。

        回傳探測結果摘要：
            {
                "search_endpoint": str | None,
                "detail_endpoint_template": str | None,
                "xhr_candidates": [...],
                "available": bool,
            }
        """
        result: Dict[str, Any] = {
            "search_endpoint": None,
            "detail_endpoint_template": None,
            "xhr_candidates": [],
            "available": False,
        }

        # 1. 分析 XHR 捕獲
        if xhr_urls:
            candidates = self._extract_json_candidates(xhr_urls)
            result["xhr_candidates"] = candidates
            logger.info(f"從 XHR 捕獲中篩選出 {len(candidates)} 個 API 候選")
            for url in candidates:
                if self._test_search_endpoint(url):
                    self.search_endpoint = url
                    result["search_endpoint"] = url
                    logger.info(f"✓ 找到搜索端點（XHR）: {url}")
                    break

        # 2. 嘗試已知候選路徑
        if not self.search_endpoint:
            for path in self.SEARCH_CANDIDATES:
                url = urljoin(self.BASE_URL, path)
                if self._test_search_endpoint(url):
                    self.search_endpoint = url
                    result["search_endpoint"] = url
                    logger.info(f"✓ 找到搜索端點（候選）: {url}")
                    break

        if not self.search_endpoint:
            logger.info("未找到可用的搜索端點")

        # 3. 探測詳情端點
        for template in self.DETAIL_CANDIDATES:
            test_url = urljoin(
                self.BASE_URL, template.replace("{slug}", self._TEST_SLUG)
            )
            if self._test_detail_endpoint(test_url):
                self.detail_endpoint_template = urljoin(self.BASE_URL, template)
                result["detail_endpoint_template"] = template
                logger.info(f"✓ 找到詳情端點: {template}")
                break

        # 搜索端點是核心功能，以其可用性決定整體 API 是否可用
        self._available = self.search_endpoint is not None
        result["available"] = self._available
        self._discovered = True
        return result

    # ------------------------------------------------------------------
    # 公開查詢方法
    # ------------------------------------------------------------------

    def fetch_search_results(
        self,
        category: str,
        page: int = 1,
        spirit_style_id: str = None,
        sort: str = "distiller_score",
    ) -> List[str]:
        """
        透過 API 取得搜索結果的 spirit URL 列表。
        回傳 []（而非 None）代表「本頁無結果」，None 代表「API 請求失敗」。
        """
        if not self.search_endpoint:
            return []

        params: Dict[str, Any] = {"category": category, "sort": sort}
        if spirit_style_id:
            params["spirit_style_id"] = spirit_style_id
        if page > 1:
            params["page"] = page

        resp = self._probe(self.search_endpoint, params=params)
        if resp is None:
            return []

        try:
            return self._map_search_response(resp.json())
        except Exception as e:
            logger.warning(f"解析搜索 API 回應失敗: {e}")
            return []

    def fetch_spirit_detail(self, url: str) -> Optional[Dict]:
        """
        透過 API 取得烈酒詳情。
        回傳與 DataExtractor.extract_spirit_details() 相容的 dict，
        或 None（API 不可用 / 請求失敗）。
        """
        if not self.detail_endpoint_template:
            return None

        slug = self._url_to_slug(url)
        if not slug:
            return None

        api_url = self.detail_endpoint_template.replace("{slug}", slug)
        resp = self._probe(api_url)
        if resp is None:
            return None

        try:
            return self._map_detail_response(resp.json(), url)
        except Exception as e:
            logger.warning(f"解析詳情 API 回應失敗 ({url}): {e}")
            return None

    # ------------------------------------------------------------------
    # 私有輔助
    # ------------------------------------------------------------------

    def _probe(
        self,
        url: str,
        params: Dict = None,
        timeout: int = 10,
    ) -> Optional[requests.Response]:
        """發送 GET 請求，200 且可解析為 JSON 則回傳 response，否則 None"""
        try:
            resp = self.session.get(url, params=params, timeout=timeout)
            if resp.status_code == 200 and self._is_json(resp):
                return resp
            logger.debug(f"  探測失敗 (HTTP {resp.status_code}): {url}")
        except requests.RequestException as e:
            logger.debug(f"  探測異常: {url} → {e}")
        return None

    def _is_json(self, resp: requests.Response) -> bool:
        """判斷回應是否為 JSON"""
        if "json" in resp.headers.get("Content-Type", ""):
            return True
        try:
            resp.json()
            return True
        except (ValueError, requests.exceptions.JSONDecodeError):
            return False

    def _test_search_endpoint(self, url: str) -> bool:
        resp = self._probe(
            url, params={"category": "whiskey", "sort": "distiller_score"}
        )
        return resp is not None

    def _test_detail_endpoint(self, url: str) -> bool:
        return self._probe(url) is not None

    def _extract_json_candidates(self, xhr_urls: List[str]) -> List[str]:
        """從 XHR URL 列表中篩選可能是 JSON API 的候選，並去重排序"""
        seen, candidates = set(), []
        for url in xhr_urls:
            parsed = urlparse(url)
            # 只接受 distiller.com 網域（排除第三方分析工具把 distiller.com 當 query 參數帶入）
            if parsed.netloc != "distiller.com":
                continue
            # 排除靜態資源
            if any(
                parsed.path.endswith(ext)
                for ext in (".js", ".css", ".png", ".jpg", ".svg", ".woff", ".woff2", ".ico")
            ):
                continue
            key = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if key not in seen:
                seen.add(key)
                candidates.append(url)
        # 含 /api/ 或 .json 的排在前面
        return sorted(
            candidates,
            key=lambda u: (0 if ("/api/" in u or ".json" in u) else 1),
        )

    def _url_to_slug(self, url: str) -> Optional[str]:
        """從 spirit URL 提取 slug（/spirits/<slug>）"""
        match = re.search(r"/spirits/([^/?#]+)", url)
        return match.group(1) if match else None

    def _map_search_response(self, data: Any) -> List[str]:
        """
        將 API 搜索回應映射為 spirit URL 列表。
        支援常見 JSON 結構：list、{spirits:[...]}, {results:[...]}, {data:[...]} 等。
        """
        spirits: Optional[list] = None

        if isinstance(data, list):
            spirits = data
        elif isinstance(data, dict):
            for key in ("spirits", "results", "data", "items", "records"):
                if key in data and isinstance(data[key], list):
                    spirits = data[key]
                    break

        if not spirits:
            return []

        urls = []
        for item in spirits:
            if not isinstance(item, dict):
                continue
            # 嘗試直接取得 URL
            url = item.get("url") or item.get("href") or item.get("link")
            if url:
                if url.startswith("/"):
                    url = f"{self.BASE_URL}{url}"
                urls.append(url)
                continue
            # 嘗試從 slug 建構 URL
            slug = item.get("slug") or item.get("id")
            if slug:
                urls.append(f"{self.BASE_URL}/spirits/{slug}")

        return urls

    def _map_detail_response(self, data: Any, original_url: str) -> Optional[Dict]:
        """
        將 API 詳情回應映射為與 DataExtractor.extract_spirit_details() 相容的格式。
        支援 {spirit: {...}}, {data: {...}}, 或頂層 dict。
        """
        if not isinstance(data, dict):
            return None

        # 展開包裝
        if "spirit" in data and isinstance(data["spirit"], dict):
            data = data["spirit"]
        elif "data" in data and isinstance(data["data"], dict):
            data = data["data"]

        # brand / country 可能在巢狀欄位
        brand = (
            data.get("brand")
            or data.get("distillery")
            or data.get("brand_name")
            or "N/A"
        )
        country = data.get("country") or data.get("country_name") or "N/A"

        # flavor_data 可能是 dict 或 list[{name, value}]
        flavor_raw = data.get("flavor_profile") or data.get("flavors") or {}
        if isinstance(flavor_raw, list):
            flavor_raw = {
                f.get("name", str(i)): f.get("value", 0)
                for i, f in enumerate(flavor_raw)
                if isinstance(f, dict)
            }

        mapped = {
            "name":            data.get("name") or data.get("title") or "N/A",
            "spirit_type":     data.get("spirit_type") or data.get("type") or "N/A",
            "brand":           str(brand),
            "country":         str(country),
            "badge":           str(data.get("badge") or "N/A"),
            "age":             str(data.get("age") or "N/A"),
            "abv":             str(data.get("abv") or "N/A"),
            "cost_level":      str(data.get("cost_level") or data.get("price_tier") or "N/A"),
            "cask_type":       str(data.get("cask_type") or "N/A"),
            "expert_score":    str(data.get("distiller_score") or data.get("expert_score") or "N/A"),
            "community_score": str(data.get("community_score") or data.get("average_rating") or "N/A"),
            "review_count":    str(data.get("review_count") or data.get("ratings_count") or "N/A"),
            "description":     str(data.get("description") or "N/A"),
            "tasting_notes":   str(data.get("tasting_notes") or data.get("notes") or "N/A"),
            "expert_name":     str(data.get("expert_name") or "N/A"),
            "flavor_summary":  str(data.get("flavor_summary") or "N/A"),
            "flavor_data":     flavor_raw if isinstance(flavor_raw, dict) else {},
            "url":             original_url,
        }

        # 驗證必要欄位
        if mapped["name"] in ("N/A", "", "None"):
            return None

        return mapped
