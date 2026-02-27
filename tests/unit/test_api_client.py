"""
DistillerAPIClient 單元測試
所有 HTTP 請求均使用 Mock，不需要真實網路連線
"""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from distiller_scraper.api_client import DistillerAPIClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    return DistillerAPIClient()


def make_response(data, status_code=200, content_type="application/json"):
    """建立 Mock requests.Response"""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.headers = {"Content-Type": content_type}
    resp.json.return_value = data
    return resp


def make_fail_response(status_code=404):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.headers = {"Content-Type": "text/html"}
    resp.json.side_effect = ValueError("not JSON")
    return resp


# ---------------------------------------------------------------------------
# 初始化
# ---------------------------------------------------------------------------

class TestInit:
    def test_default_state(self, client):
        assert client.is_available() is False
        assert client.search_endpoint is None
        assert client.detail_endpoint_template is None
        assert client._discovered is False

    def test_session_headers(self, client):
        headers = client.session.headers
        assert "User-Agent" in headers
        assert "XMLHttpRequest" in headers.get("X-Requested-With", "")


# ---------------------------------------------------------------------------
# _is_json
# ---------------------------------------------------------------------------

class TestIsJson:
    def test_json_content_type(self, client):
        resp = MagicMock()
        resp.headers = {"Content-Type": "application/json"}
        resp.json.return_value = {}
        assert client._is_json(resp) is True

    def test_parseable_body(self, client):
        resp = MagicMock()
        resp.headers = {"Content-Type": "text/html"}
        resp.json.return_value = {"key": "value"}
        assert client._is_json(resp) is True

    def test_non_json(self, client):
        resp = MagicMock()
        resp.headers = {"Content-Type": "text/html"}
        resp.json.side_effect = ValueError
        assert client._is_json(resp) is False


# ---------------------------------------------------------------------------
# _url_to_slug
# ---------------------------------------------------------------------------

class TestUrlToSlug:
    def test_standard_url(self, client):
        assert client._url_to_slug("https://distiller.com/spirits/highland-park-18") == "highland-park-18"

    def test_url_with_query(self, client):
        assert client._url_to_slug("https://distiller.com/spirits/macallan-12?ref=x") == "macallan-12"

    def test_no_slug(self, client):
        assert client._url_to_slug("https://distiller.com/search") is None

    def test_empty_url(self, client):
        assert client._url_to_slug("") is None


# ---------------------------------------------------------------------------
# _extract_json_candidates
# ---------------------------------------------------------------------------

class TestExtractJsonCandidates:
    def test_filters_static_assets(self, client):
        urls = [
            "https://distiller.com/assets/app.js",
            "https://distiller.com/search.json?category=whiskey",
            "https://distiller.com/styles.css",
        ]
        result = client._extract_json_candidates(urls)
        assert "https://distiller.com/search.json?category=whiskey" in result
        # 以 path 結尾判斷（避免 .json 被誤當成 .js）
        paths = [u.split("?")[0] for u in result]
        assert not any(p.endswith(".js") or p.endswith(".css") for p in paths)

    def test_filters_other_domains(self, client):
        urls = [
            "https://other.com/api/spirits",
            "https://distiller.com/api/spirits",
        ]
        result = client._extract_json_candidates(urls)
        assert len(result) == 1
        assert "distiller.com" in result[0]

    def test_api_paths_sorted_first(self, client):
        urls = [
            "https://distiller.com/search?category=whiskey",
            "https://distiller.com/api/spirits?category=whiskey",
            "https://distiller.com/search.json?category=whiskey",
        ]
        result = client._extract_json_candidates(urls)
        # /api/ 和 .json 應排在前面
        assert result[0] in (
            "https://distiller.com/api/spirits?category=whiskey",
            "https://distiller.com/search.json?category=whiskey",
        )

    def test_deduplication(self, client):
        urls = [
            "https://distiller.com/api/spirits?page=1",
            "https://distiller.com/api/spirits?page=2",  # 同路徑不同 query → 合併
        ]
        result = client._extract_json_candidates(urls)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# _map_search_response
# ---------------------------------------------------------------------------

class TestMapSearchResponse:
    def test_list_with_url(self, client):
        data = [
            {"url": "/spirits/highland-park-18", "name": "Highland Park 18"},
            {"url": "/spirits/macallan-12", "name": "Macallan 12"},
        ]
        urls = client._map_search_response(data)
        assert len(urls) == 2
        assert "https://distiller.com/spirits/highland-park-18" in urls

    def test_dict_with_spirits_key(self, client):
        data = {"spirits": [{"url": "/spirits/glenfiddich-15"}]}
        urls = client._map_search_response(data)
        assert len(urls) == 1

    def test_dict_with_results_key(self, client):
        data = {"results": [{"slug": "ardbeg-10"}]}
        urls = client._map_search_response(data)
        assert "https://distiller.com/spirits/ardbeg-10" in urls

    def test_dict_with_data_key(self, client):
        data = {"data": [{"slug": "laphroaig-10"}]}
        urls = client._map_search_response(data)
        assert len(urls) == 1

    def test_absolute_url_unchanged(self, client):
        data = [{"url": "https://distiller.com/spirits/test-spirit"}]
        urls = client._map_search_response(data)
        assert urls[0] == "https://distiller.com/spirits/test-spirit"

    def test_empty_list(self, client):
        assert client._map_search_response([]) == []

    def test_empty_dict(self, client):
        assert client._map_search_response({}) == []

    def test_unknown_structure(self, client):
        assert client._map_search_response("not a dict or list") == []

    def test_items_without_url_or_slug_skipped(self, client):
        data = [{"name": "Spirit without url"}, {"url": "/spirits/valid"}]
        urls = client._map_search_response(data)
        assert len(urls) == 1


# ---------------------------------------------------------------------------
# _map_detail_response
# ---------------------------------------------------------------------------

class TestMapDetailResponse:
    def _full_data(self):
        return {
            "name": "Highland Park 18 Year",
            "spirit_type": "Single Malt",
            "brand": "Highland Park",
            "country": "Scotland",
            "age": "18 Year",
            "abv": 43.0,
            "expert_score": 99,
            "community_score": 4.47,
            "review_count": 512,
            "description": "Rich and complex.",
            "tasting_notes": "Honey and smoke.",
            "flavor_profile": {"smoky": 40, "sweet": 35},
        }

    def test_full_data(self, client):
        url = "https://distiller.com/spirits/highland-park-18"
        result = client._map_detail_response(self._full_data(), url)
        assert result is not None
        assert result["name"] == "Highland Park 18 Year"
        assert result["url"] == url
        assert result["flavor_data"] == {"smoky": 40, "sweet": 35}

    def test_unwraps_spirit_key(self, client):
        data = {"spirit": self._full_data()}
        result = client._map_detail_response(data, "https://distiller.com/spirits/test")
        assert result["name"] == "Highland Park 18 Year"

    def test_unwraps_data_key(self, client):
        data = {"data": self._full_data()}
        result = client._map_detail_response(data, "https://distiller.com/spirits/test")
        assert result["name"] == "Highland Park 18 Year"

    def test_non_dict_returns_none(self, client):
        assert client._map_detail_response(["not", "a", "dict"], "url") is None
        assert client._map_detail_response("string", "url") is None

    def test_missing_name_returns_none(self, client):
        assert client._map_detail_response({}, "url") is None

    def test_flavor_list_converted_to_dict(self, client):
        data = {
            "name": "Spirit",
            "flavors": [
                {"name": "smoky", "value": 40},
                {"name": "sweet", "value": 30},
            ],
        }
        result = client._map_detail_response(data, "url")
        assert result["flavor_data"] == {"smoky": 40, "sweet": 30}

    def test_alternative_field_names(self, client):
        data = {
            "name": "Spirit X",
            "distillery": "Famous Distillery",
            "country_name": "Japan",
            "distiller_score": 95,
            "average_rating": 4.5,
        }
        result = client._map_detail_response(data, "url")
        assert result["brand"] == "Famous Distillery"
        assert result["country"] == "Japan"
        assert result["expert_score"] == "95"
        assert result["community_score"] == "4.5"


# ---------------------------------------------------------------------------
# discover (mock HTTP)
# ---------------------------------------------------------------------------

class TestDiscover:
    def test_finds_search_endpoint_from_candidate(self, client):
        search_resp = make_response({"spirits": [{"url": "/spirits/test"}]})
        with patch.object(client.session, "get", return_value=search_resp):
            result = client.discover()
        assert result["available"] is True
        assert result["search_endpoint"] is not None
        assert client.is_available() is True

    def test_no_endpoint_found(self, client):
        fail_resp = make_fail_response(404)
        with patch.object(client.session, "get", return_value=fail_resp):
            result = client.discover()
        assert result["available"] is False
        assert client.is_available() is False

    def test_xhr_candidates_probed_first(self, client):
        xhr_urls = ["https://distiller.com/api/v1/spirits"]
        probed = []

        def mock_get(url, **kwargs):
            probed.append(url)
            return make_response({})

        with patch.object(client.session, "get", side_effect=mock_get):
            client.discover(xhr_urls=xhr_urls)

        # API 路徑應在候選清單中被嘗試
        assert any("distiller.com" in u for u in probed)

    def test_discover_sets_discovered_flag(self, client):
        with patch.object(client.session, "get", return_value=make_fail_response()):
            client.discover()
        assert client._discovered is True


# ---------------------------------------------------------------------------
# fetch_search_results (mock HTTP)
# ---------------------------------------------------------------------------

class TestFetchSearchResults:
    def test_returns_urls_when_api_available(self, client):
        client.search_endpoint = "https://distiller.com/search.json"
        resp = make_response([{"url": "/spirits/macallan-12"}])
        with patch.object(client, "_probe", return_value=resp):
            urls = client.fetch_search_results("whiskey")
        assert len(urls) == 1

    def test_returns_empty_when_no_endpoint(self, client):
        urls = client.fetch_search_results("whiskey")
        assert urls == []

    def test_probe_failure_returns_empty(self, client):
        client.search_endpoint = "https://distiller.com/search.json"
        with patch.object(client, "_probe", return_value=None):
            urls = client.fetch_search_results("whiskey")
        assert urls == []

    def test_page_param_passed(self, client):
        client.search_endpoint = "https://distiller.com/search.json"
        captured_params = {}

        def mock_probe(url, params=None, **kw):
            captured_params.update(params or {})
            return make_response([])

        with patch.object(client, "_probe", side_effect=mock_probe):
            client.fetch_search_results("gin", page=3, spirit_style_id="105")

        assert captured_params.get("page") == 3
        assert captured_params.get("spirit_style_id") == "105"

    def test_page_1_no_page_param(self, client):
        client.search_endpoint = "https://distiller.com/search.json"
        captured_params = {}

        def mock_probe(url, params=None, **kw):
            captured_params.update(params or {})
            return make_response([])

        with patch.object(client, "_probe", side_effect=mock_probe):
            client.fetch_search_results("gin", page=1)

        assert "page" not in captured_params


# ---------------------------------------------------------------------------
# fetch_spirit_detail (mock HTTP)
# ---------------------------------------------------------------------------

class TestFetchSpiritDetail:
    def test_returns_dict_when_api_available(self, client):
        client.detail_endpoint_template = "https://distiller.com/spirits/{slug}.json"
        resp = make_response({"name": "Macallan 12", "spirit_type": "Single Malt"})
        with patch.object(client, "_probe", return_value=resp):
            result = client.fetch_spirit_detail("https://distiller.com/spirits/macallan-12")
        assert result is not None
        assert result["name"] == "Macallan 12"

    def test_returns_none_when_no_endpoint(self, client):
        result = client.fetch_spirit_detail("https://distiller.com/spirits/test")
        assert result is None

    def test_returns_none_on_probe_failure(self, client):
        client.detail_endpoint_template = "https://distiller.com/spirits/{slug}.json"
        with patch.object(client, "_probe", return_value=None):
            result = client.fetch_spirit_detail("https://distiller.com/spirits/test")
        assert result is None

    def test_invalid_url_returns_none(self, client):
        client.detail_endpoint_template = "https://distiller.com/spirits/{slug}.json"
        result = client.fetch_spirit_detail("https://distiller.com/search")
        assert result is None
