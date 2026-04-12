"""
風味偏好解析單元測試

涵蓋：
- 關鍵字回歸與新增關鍵字
- 否定偏好
- 風格/地區參照
- 酒款參照提取
- 強度修飾
"""

from distiller_scraper.flavor_parser import parse_flavor_prefs


# ─── 關鍵字回歸 ───────────────────────────────────────────────


class TestKeywordRegression:
    """確保所有原始 26 個關鍵字仍然正常運作。"""

    def test_chinese_smoky(self):
        r = parse_flavor_prefs("煙燻")
        assert r.flavor_vector is not None
        assert r.flavor_vector["smoky"] == 80
        assert r.flavor_vector["peaty"] == 60

    def test_chinese_peaty(self):
        r = parse_flavor_prefs("泥煤")
        assert r.flavor_vector is not None
        assert r.flavor_vector["peaty"] == 85

    def test_english_juniper(self):
        r = parse_flavor_prefs("juniper")
        assert r.flavor_vector is not None
        assert r.flavor_vector["juniper"] == 85

    def test_english_smoky(self):
        r = parse_flavor_prefs("smoky")
        assert r.flavor_vector is not None
        assert r.flavor_vector["smoky"] == 80

    def test_multi_keyword_merge(self):
        """多關鍵字 max 合併。"""
        r = parse_flavor_prefs("煙燻泥煤")
        assert r.flavor_vector is not None
        assert r.flavor_vector["smoky"] == max(80, 70)
        assert r.flavor_vector["peaty"] == max(60, 85)

    def test_no_match_returns_empty(self):
        r = parse_flavor_prefs("asdfgh")
        assert r.flavor_vector is None
        assert r.spirit_refs == []
        assert r.avoid_flavors == set()

    def test_empty_string(self):
        r = parse_flavor_prefs("")
        assert r.flavor_vector is None


# ─── 新增關鍵字 ───────────────────────────────────────────────


class TestNewKeywords:
    """新增關鍵字覆蓋測試。"""

    def test_nutty(self):
        r = parse_flavor_prefs("堅果")
        assert r.flavor_vector is not None
        assert r.flavor_vector["nutty"] == 75

    def test_honey(self):
        r = parse_flavor_prefs("蜂蜜")
        assert r.flavor_vector is not None
        assert r.flavor_vector["sweet"] == 70
        assert r.flavor_vector["floral"] == 40

    def test_chocolate(self):
        r = parse_flavor_prefs("巧克力")
        assert r.flavor_vector is not None
        assert "rich" in r.flavor_vector
        assert "roast" in r.flavor_vector

    def test_english_woody(self):
        r = parse_flavor_prefs("woody")
        assert r.flavor_vector is not None
        assert r.flavor_vector["woody"] == 75

    def test_english_bitter(self):
        r = parse_flavor_prefs("bitter")
        assert r.flavor_vector is not None
        assert r.flavor_vector["bitter"] == 75


# ─── 否定偏好 ───────────────────────────────────────────────


class TestNegation:
    """否定偏好測試。"""

    def test_not_sweet_basic(self):
        """「不甜」→ avoid sweet，不應加入 flavor_vector。"""
        r = parse_flavor_prefs("不甜")
        assert "sweet" in r.avoid_flavors
        assert r.flavor_vector is None or "sweet" not in r.flavor_vector

    def test_not_too_sweet(self):
        """「不要太甜」→ avoid sweet。"""
        r = parse_flavor_prefs("不要太甜")
        assert "sweet" in r.avoid_flavors

    def test_less_sweet(self):
        """「少一點甜」→ avoid sweet。"""
        r = parse_flavor_prefs("少一點甜")
        assert "sweet" in r.avoid_flavors

    def test_dislike_smoky(self):
        """「不喜歡煙燻」→ avoid smoky + peaty。"""
        r = parse_flavor_prefs("不喜歡煙燻")
        assert "smoky" in r.avoid_flavors
        assert "peaty" in r.avoid_flavors

    def test_negation_does_not_add_to_vector(self):
        """否定的關鍵字不應出現在 flavor_vector 中。"""
        r = parse_flavor_prefs("不要太甜 草本")
        assert r.flavor_vector is not None
        assert "sweet" not in r.flavor_vector
        assert r.flavor_vector["herbal"] == 80

    def test_substring_collision_fixed(self):
        """回歸：「不甜」不應觸發正向「甜」。"""
        r = parse_flavor_prefs("不甜")
        assert "sweet" in r.avoid_flavors
        assert (r.flavor_vector or {}).get("sweet", 0) == 0

    def test_negation_not_bitter(self):
        r = parse_flavor_prefs("不要苦")
        assert "bitter" in r.avoid_flavors


# ─── 風格/地區 ───────────────────────────────────────────────


class TestRegionStyle:
    """地區/風格參照測試。"""

    def test_islay_style(self):
        r = parse_flavor_prefs("像 Islay 風格")
        assert r.flavor_vector is not None
        assert r.flavor_vector["smoky"] >= 70
        assert r.flavor_vector["peaty"] >= 80

    def test_bourbon_style(self):
        r = parse_flavor_prefs("bourbon style")
        assert r.flavor_vector is not None
        assert r.flavor_vector["sweet"] >= 65
        assert r.flavor_vector["vanilla"] >= 70

    def test_speyside_style(self):
        r = parse_flavor_prefs("像 Speyside 風格")
        assert r.flavor_vector is not None
        assert r.flavor_vector["fruity"] >= 65
        assert r.flavor_vector["sweet"] >= 60

    def test_islay_case_insensitive(self):
        r = parse_flavor_prefs("像 islay 風格")
        assert r.flavor_vector is not None
        assert r.flavor_vector["smoky"] >= 70

    def test_unknown_style_ignored(self):
        """不認識的風格不加入向量。"""
        r = parse_flavor_prefs("像 Narnia 風格")
        assert r.flavor_vector is None or "smoky" not in r.flavor_vector


# ─── 酒款參照 ────────────────────────────────────────────────


class TestSpiritReference:
    """酒款參照提取測試。"""

    def test_chinese_similar_to(self):
        r = parse_flavor_prefs("類似 Highland Park")
        assert "Highland Park" in r.spirit_refs

    def test_english_like(self):
        r = parse_flavor_prefs("like Lagavulin")
        assert "Lagavulin" in r.spirit_refs

    def test_spirit_ref_not_confused_with_style(self):
        """「bourbon style」應為地區風格，非酒款參照。"""
        r = parse_flavor_prefs("bourbon style")
        assert r.spirit_refs == []

    def test_multiple_refs(self):
        """同時有酒款參照和風味關鍵字。"""
        r = parse_flavor_prefs("類似 Highland Park 但偏煙燻")
        assert "Highland Park" in r.spirit_refs
        assert r.flavor_vector is not None
        assert r.flavor_vector["smoky"] >= 70


# ─── 強度修飾 ────────────────────────────────────────────────


class TestIntensityModifiers:
    """強度修飾詞測試。"""

    def test_very_smoky(self):
        r = parse_flavor_prefs("很煙燻")
        assert r.flavor_vector is not None
        assert r.flavor_vector["smoky"] > 80

    def test_slightly_sweet(self):
        r = parse_flavor_prefs("微甜")
        assert r.flavor_vector is not None
        assert r.flavor_vector["sweet"] < 75
        assert r.flavor_vector["sweet"] > 0

    def test_very_in_english(self):
        r = parse_flavor_prefs("very smoky")
        assert r.flavor_vector is not None
        assert r.flavor_vector["smoky"] > 80


# ─── 複合輸入 ───────────────────────────────────────────────


class TestMixedInput:
    """複合輸入測試。"""

    def test_combined_prefs(self):
        """煙燻 + 否定甜 + 風格參照。"""
        r = parse_flavor_prefs("煙燻但不要太甜 像 Islay 風格")
        assert r.flavor_vector is not None
        assert r.flavor_vector["smoky"] >= 70
        assert "sweet" in r.avoid_flavors
        assert r.flavor_vector.get("peaty", 0) >= 60

    def test_spirit_ref_plus_keyword(self):
        r = parse_flavor_prefs("類似 Highland Park 草本花香")
        assert "Highland Park" in r.spirit_refs
        assert r.flavor_vector is not None
        assert r.flavor_vector["herbal"] == 80
        assert r.flavor_vector["floral"] == 80


# ─── ParseResult 結構 ────────────────────────────────────────


class TestParseResultDataclass:
    """ParseResult 回傳值結構測試。"""

    def test_returns_parse_result(self):
        r = parse_flavor_prefs("煙燻")
        assert hasattr(r, "flavor_vector")
        assert hasattr(r, "spirit_refs")
        assert hasattr(r, "avoid_flavors")

    def test_spirit_refs_is_list(self):
        r = parse_flavor_prefs("煙燻")
        assert isinstance(r.spirit_refs, list)

    def test_avoid_flavors_is_set(self):
        r = parse_flavor_prefs("不甜")
        assert isinstance(r.avoid_flavors, set)
