"""
推薦引擎單元測試

涵蓋：
- 評分權重配置
- classic_subtype 加分邏輯
- allow_twist 模式
- 酒譜欄位（recipe/glassware/method）
- cocktail_db 新欄位完整性
- bot 的 twist 關鍵字偵測
"""

import pytest
from distiller_scraper.recommender import (
    CocktailRecommender,
    CocktailRecommendation,
    SpiritCandidate,
    _cosine_similarity,
    _abv_penalty,
    format_recommendation,
)
from distiller_scraper.cocktail_db import (
    get_cocktail,
    list_cocktails,
    COCKTAIL_DB,
    MODE_DYNAMIC,
    MODE_DYNAMIC_OR_STATIC,
    MODE_STATIC_ONLY,
)


# ─── cocktail_db 新欄位完整性 ──────────────────────────────────


class TestCocktailDbNewFields:
    def test_all_cocktails_have_recipe(self):
        """每款雞尾酒都應有 recipe 欄位且至少 1 個項目。"""
        for key, cocktail in COCKTAIL_DB.items():
            assert "recipe" in cocktail, f"{key} 缺少 recipe"
            assert len(cocktail["recipe"]) >= 1, f"{key} recipe 為空"

    def test_recipe_items_have_required_keys(self):
        """每個 recipe 項目必須有 item 與 amount。"""
        for key, cocktail in COCKTAIL_DB.items():
            for i, item in enumerate(cocktail["recipe"]):
                assert "item" in item, f"{key}.recipe[{i}] 缺少 item"
                assert "amount" in item, f"{key}.recipe[{i}] 缺少 amount"

    def test_all_cocktails_have_glassware(self):
        for key, cocktail in COCKTAIL_DB.items():
            assert "glassware" in cocktail, f"{key} 缺少 glassware"
            assert cocktail["glassware"], f"{key} glassware 為空字串"

    def test_all_cocktails_have_method(self):
        for key, cocktail in COCKTAIL_DB.items():
            assert "method" in cocktail, f"{key} 缺少 method"
            assert cocktail["method"], f"{key} method 為空字串"

    def test_dynamic_ingredients_have_classic_subtypes(self):
        """可動態推薦的成分應包含 classic_subtypes（可為空列表）。"""
        for key, cocktail in COCKTAIL_DB.items():
            for ing in cocktail["ingredients"]:
                assert "classic_subtypes" in ing, (
                    f"{key} ingredient '{ing['label']}' 缺少 classic_subtypes"
                )

    def test_classic_subtypes_subset_of_suitable(self):
        """classic_subtypes 應是 suitable_subtypes 的子集（若兩者都非空）。"""
        for key, cocktail in COCKTAIL_DB.items():
            for ing in cocktail["ingredients"]:
                classic = set(ing.get("classic_subtypes", []))
                suitable = set(ing.get("suitable_subtypes", []))
                if classic and suitable:
                    assert classic <= suitable, (
                        f"{key} '{ing['label']}' classic_subtypes {classic} "
                        f"不是 suitable_subtypes {suitable} 的子集"
                    )

    def test_negroni_recipe_content(self):
        cocktail = get_cocktail("negroni")
        items = {r["item"] for r in cocktail["recipe"]}
        assert "琴酒" in items
        assert "Campari" in items
        assert "甜苦艾酒" in items

    def test_negroni_classic_gin_is_london_dry(self):
        cocktail = get_cocktail("negroni")
        gin_ing = next(i for i in cocktail["ingredients"] if i["label"] == "琴酒")
        assert "London Dry Gin" in gin_ing["classic_subtypes"]

    def test_old_fashioned_classic_bourbon(self):
        cocktail = get_cocktail("old_fashioned")
        whiskey_ing = next(i for i in cocktail["ingredients"] if i["role"] == "base")
        assert "Bourbon" in whiskey_ing["classic_subtypes"]

    def test_manhattan_classic_rye(self):
        cocktail = get_cocktail("manhattan")
        base_ing = next(i for i in cocktail["ingredients"] if i["role"] == "base")
        assert "Rye" in base_ing["classic_subtypes"]


# ─── 評分權重 ──────────────────────────────────────────────────


class TestScoringWeights:
    def test_cocktail_flavor_weight_dominant(self):
        """W_COCKTAIL_FLAVOR 應為最大權重（≥ 0.55）。"""
        assert CocktailRecommender.W_COCKTAIL_FLAVOR >= 0.55

    def test_weights_sum_to_one(self):
        total = (
            CocktailRecommender.W_COCKTAIL_FLAVOR
            + CocktailRecommender.W_USER_FLAVOR
            + CocktailRecommender.W_EXPERT_SCORE
            + CocktailRecommender.W_COMMUNITY_SCORE
        )
        assert abs(total - 1.0) < 1e-9

    def test_expert_score_weight_less_than_flavor(self):
        assert (
            CocktailRecommender.W_EXPERT_SCORE < CocktailRecommender.W_COCKTAIL_FLAVOR
        )

    def test_classic_subtype_bonus_positive(self):
        assert CocktailRecommender.CLASSIC_SUBTYPE_BONUS > 0


# ─── classic 加分邏輯 ──────────────────────────────────────────


def _make_candidate(
    spirit_type: str, expert_score: int = 90, flavors: dict | None = None
) -> SpiritCandidate:
    return SpiritCandidate(
        spirit_id=1,
        name="Test Spirit",
        brand="Brand",
        spirit_type=spirit_type,
        country="Scotland",
        abv=43.0,
        expert_score=expert_score,
        community_score=4.5,
        cost_level=3,
        flavor_summary="",
        tasting_notes="",
        url="https://example.com",
        flavors=flavors or {"herbal": 70, "juniper": 75},
    )


class TestClassicBonus:
    def _score(
        self, spirit_type: str, classic_subtypes: list[str], allow_twist: bool = False
    ) -> float:
        rec = CocktailRecommender.__new__(CocktailRecommender)
        rec.W_COCKTAIL_FLAVOR = CocktailRecommender.W_COCKTAIL_FLAVOR
        rec.W_USER_FLAVOR = CocktailRecommender.W_USER_FLAVOR
        rec.W_EXPERT_SCORE = CocktailRecommender.W_EXPERT_SCORE
        rec.W_COMMUNITY_SCORE = CocktailRecommender.W_COMMUNITY_SCORE
        rec.CLASSIC_SUBTYPE_BONUS = CocktailRecommender.CLASSIC_SUBTYPE_BONUS

        candidate = _make_candidate(spirit_type)
        candidates = rec._score_candidates(
            [candidate],
            ideal_flavors={"herbal": 70, "juniper": 75},
            user_flavor_prefs=None,
            abv_range=(40, 50),
            classic_subtypes=classic_subtypes,
            allow_twist=allow_twist,
        )
        return candidates[0].score

    def test_classic_type_scores_higher(self):
        classic_score = self._score(
            "London Dry Gin", ["London Dry Gin"], allow_twist=False
        )
        non_classic_score = self._score(
            "Old Tom Gin", ["London Dry Gin"], allow_twist=False
        )
        assert classic_score > non_classic_score

    def test_classic_bonus_equals_constant(self):
        classic_score = self._score(
            "London Dry Gin", ["London Dry Gin"], allow_twist=False
        )
        non_classic_score = self._score(
            "Old Tom Gin", ["London Dry Gin"], allow_twist=False
        )
        assert (
            abs(
                (classic_score - non_classic_score)
                - CocktailRecommender.CLASSIC_SUBTYPE_BONUS
            )
            < 1e-6
        )

    def test_twist_mode_disables_bonus(self):
        score_no_twist = self._score(
            "London Dry Gin", ["London Dry Gin"], allow_twist=False
        )
        score_twist = self._score(
            "London Dry Gin", ["London Dry Gin"], allow_twist=True
        )
        assert score_no_twist > score_twist
        assert (
            abs(
                (score_no_twist - score_twist)
                - CocktailRecommender.CLASSIC_SUBTYPE_BONUS
            )
            < 1e-6
        )

    def test_empty_classic_subtypes_no_bonus(self):
        score_with = self._score(
            "London Dry Gin", ["London Dry Gin"], allow_twist=False
        )
        score_without = self._score("London Dry Gin", [], allow_twist=False)
        assert score_with > score_without

    def test_classic_bonus_in_score_breakdown(self):
        rec = CocktailRecommender.__new__(CocktailRecommender)
        rec.W_COCKTAIL_FLAVOR = CocktailRecommender.W_COCKTAIL_FLAVOR
        rec.W_USER_FLAVOR = CocktailRecommender.W_USER_FLAVOR
        rec.W_EXPERT_SCORE = CocktailRecommender.W_EXPERT_SCORE
        rec.W_COMMUNITY_SCORE = CocktailRecommender.W_COMMUNITY_SCORE
        rec.CLASSIC_SUBTYPE_BONUS = CocktailRecommender.CLASSIC_SUBTYPE_BONUS

        candidate = _make_candidate("London Dry Gin")
        results = rec._score_candidates(
            [candidate],
            ideal_flavors={"herbal": 70},
            user_flavor_prefs=None,
            abv_range=None,
            classic_subtypes=["London Dry Gin"],
            allow_twist=False,
        )
        assert "classic_bonus" in results[0].score_breakdown
        assert results[0].score_breakdown["classic_bonus"] == pytest.approx(
            CocktailRecommender.CLASSIC_SUBTYPE_BONUS
        )


# ─── format_recommendation 酒譜顯示 ───────────────────────────


class TestFormatRecommendation:
    def _make_result(self, allow_twist: bool = False) -> CocktailRecommendation:
        return CocktailRecommendation(
            cocktail_name="Negroni",
            cocktail_description="等比例琴酒 + Campari + 甜苦艾酒",
            flavor_style="苦甜草本",
            recipe=[
                {"item": "琴酒", "amount": "30ml"},
                {"item": "Campari", "amount": "30ml", "note": "苦橙"},
            ],
            glassware="老式杯",
            method="攪拌法",
            allow_twist=allow_twist,
        )

    def test_recipe_shown_in_output(self):
        result = self._make_result()
        text = format_recommendation(result)
        assert "📋 酒譜" in text
        assert "琴酒" in text
        assert "30ml" in text

    def test_glassware_and_method_shown(self):
        result = self._make_result()
        text = format_recommendation(result)
        assert "老式杯" in text
        assert "攪拌法" in text

    def test_recipe_note_shown(self):
        result = self._make_result()
        text = format_recommendation(result)
        assert "苦橙" in text

    def test_twist_label_shown(self):
        result = self._make_result(allow_twist=True)
        text = format_recommendation(result)
        assert "Twist" in text

    def test_no_twist_label_when_classic(self):
        result = self._make_result(allow_twist=False)
        text = format_recommendation(result)
        assert "Twist" not in text

    def test_no_recipe_section_when_empty(self):
        result = CocktailRecommendation(
            cocktail_name="Test",
            cocktail_description="desc",
            flavor_style="style",
            recipe=[],
        )
        text = format_recommendation(result)
        assert "📋 酒譜" not in text


# ─── bot twist 關鍵字偵測 ──────────────────────────────────────


class TestBotTwistDetection:
    def test_twist_keyword_detected(self):
        import bot

        # 模擬關鍵字偵測邏輯
        from bot import _TWIST_KEYWORDS

        for keyword in ["twist", "variation", "變化", "創意", "非傳統", "特色"]:
            assert any(k in keyword.lower() for k in _TWIST_KEYWORDS), (
                f"關鍵字 '{keyword}' 未被偵測"
            )

    def test_normal_pref_not_twist(self):
        from bot import _TWIST_KEYWORDS

        pref = "喜歡花香清爽"
        result = any(k in pref.lower() for k in _TWIST_KEYWORDS)
        assert result is False

    def test_twist_in_pref_text(self):
        from bot import _TWIST_KEYWORDS

        pref = "想要 twist 版本"
        result = any(k in pref.lower() for k in _TWIST_KEYWORDS)
        assert result is True

    def test_variation_in_pref_text(self):
        from bot import _TWIST_KEYWORDS

        pref = "做 variation"
        result = any(k in pref.lower() for k in _TWIST_KEYWORDS)
        assert result is True


# ─── avoid_flavors 懲罰測試 ───────────────────────────────────────


@pytest.fixture
def recommender():
    """使用真實資料庫的推薦引擎實例。"""
    rec = CocktailRecommender("distiller.db")
    yield rec
    rec.close()


class TestAvoidFlavors:
    """avoid_flavors 懲罰測試。"""

    def test_avoid_penalty_applied(self, recommender):
        """avoid sweet → 甜的烈酒 score 降低。"""
        result_normal = recommender.recommend("Old Fashioned", top_k=10)
        result_avoid = recommender.recommend(
            "Old Fashioned", avoid_flavors={"sweet"}, top_k=10
        )

        assert result_normal is not None
        assert result_avoid is not None

        normal_scores = {}
        for ing in result_normal.ingredients:
            for c in ing.candidates:
                if c.flavors.get("sweet", 0) > 50:
                    normal_scores[c.spirit_id] = c.score

        avoid_scores = {}
        for ing in result_avoid.ingredients:
            for c in ing.candidates:
                if c.spirit_id in normal_scores:
                    avoid_scores[c.spirit_id] = c.score

        if avoid_scores:
            for sid in avoid_scores:
                assert avoid_scores[sid] < normal_scores[sid], (
                    f"Spirit {sid} should have lower score with avoid_flavors"
                )

    def test_avoid_none_no_effect(self, recommender):
        """avoid_flavors=None → 不影響評分（向後相容）。"""
        result_none = recommender.recommend(
            "Old Fashioned", avoid_flavors=None, top_k=3
        )
        result_default = recommender.recommend("Old Fashioned", top_k=3)

        assert result_none is not None
        assert result_default is not None

        for ing_none, ing_default in zip(
            result_none.ingredients, result_default.ingredients
        ):
            for c_none, c_default in zip(ing_none.candidates, ing_default.candidates):
                assert c_none.score == c_default.score

    def test_avoid_below_threshold_no_penalty(self, recommender):
        """spirit below threshold (<=50) → 不被懲罰。"""
        result = recommender.recommend(
            "Old Fashioned", avoid_flavors={"sweet"}, top_k=10
        )
        assert result is not None

        for ing in result.ingredients:
            for c in ing.candidates:
                if c.flavors.get("sweet", 0) <= 50:
                    assert c.score_breakdown.get("avoid_penalty", 1.0) == 1.0
