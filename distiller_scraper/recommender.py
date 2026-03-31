"""
雞尾酒烈酒推薦引擎

根據雞尾酒知識庫 + 風味向量相似度，為每個成分從 DB 中推薦最適合的烈酒。
"""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass, field
from typing import Optional

from .cocktail_db import (
    MODE_DYNAMIC,
    MODE_DYNAMIC_OR_STATIC,
    MODE_STATIC_ONLY,
    get_cocktail,
    list_cocktails,
)


# ─── 資料類別 ──────────────────────────────────────────────────

@dataclass
class SpiritCandidate:
    spirit_id: int
    name: str
    brand: str
    spirit_type: str
    country: str
    abv: Optional[float]
    expert_score: Optional[int]
    community_score: Optional[float]
    cost_level: Optional[int]
    flavor_summary: str
    tasting_notes: str
    url: str
    flavors: dict[str, float] = field(default_factory=dict)
    score: float = 0.0
    score_breakdown: dict[str, float] = field(default_factory=dict)


@dataclass
class IngredientRecommendation:
    role: str
    label: str
    recommend_mode: str
    candidates: list[SpiritCandidate] = field(default_factory=list)
    static_fallback: Optional[dict] = None
    used_fallback: bool = False


@dataclass
class CocktailRecommendation:
    cocktail_name: str
    cocktail_description: str
    flavor_style: str
    ingredients: list[IngredientRecommendation] = field(default_factory=list)


# ─── 相似度計算 ────────────────────────────────────────────────

def _cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """計算兩個稀疏向量的餘弦相似度（鍵為維度名稱）。"""
    if not a or not b:
        return 0.0
    keys = set(a) & set(b)
    if not keys:
        return 0.0
    dot = sum(a[k] * b[k] for k in keys)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _abv_penalty(abv: Optional[float], abv_range: Optional[tuple]) -> float:
    """ABV 不在建議範圍時給予懲罰（0.0–1.0，1.0 = 無懲罰）。"""
    if abv_range is None or abv is None:
        return 1.0
    lo, hi = abv_range
    if lo <= abv <= hi:
        return 1.0
    distance = min(abs(abv - lo), abs(abv - hi))
    return max(0.5, 1.0 - distance * 0.02)


# ─── 主要推薦類別 ──────────────────────────────────────────────

class CocktailRecommender:
    """
    根據雞尾酒知識庫與 Distiller DB，為每個成分推薦最適合的烈酒。

    用法:
        recommender = CocktailRecommender("distiller.db")
        result = recommender.recommend("negroni", user_flavor_prefs={"bitter": 80})
    """

    # 評分權重
    W_COCKTAIL_FLAVOR = 0.45   # 與雞尾酒理想風味的相似度
    W_USER_FLAVOR = 0.30       # 與用戶個人偏好的相似度
    W_EXPERT_SCORE = 0.15      # 專家評分
    W_COMMUNITY_SCORE = 0.10   # 社群評分

    def __init__(self, db_path: str = "distiller.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def recommend(
        self,
        cocktail_query: str,
        user_flavor_prefs: Optional[dict[str, float]] = None,
        max_cost_level: Optional[int] = None,
        top_k: int = 3,
    ) -> Optional[CocktailRecommendation]:
        """
        為指定雞尾酒的每個成分推薦烈酒。

        Args:
            cocktail_query: 雞尾酒名稱（英文 key 或中英文名稱）
            user_flavor_prefs: 用戶風味偏好，例如 {"smoky": 80, "sweet": 20}
            max_cost_level: 最高價格等級 (1–5)，None = 不限
            top_k: 每個成分最多推薦幾筆

        Returns:
            CocktailRecommendation 或 None（找不到雞尾酒）
        """
        cocktail = get_cocktail(cocktail_query)
        if cocktail is None:
            return None

        result = CocktailRecommendation(
            cocktail_name=cocktail["name"],
            cocktail_description=cocktail["description"],
            flavor_style=cocktail["flavor_style"],
        )

        for ing in cocktail["ingredients"]:
            rec = self._recommend_ingredient(ing, user_flavor_prefs, max_cost_level, top_k)
            result.ingredients.append(rec)

        return result

    def _recommend_ingredient(
        self,
        ingredient: dict,
        user_flavor_prefs: Optional[dict[str, float]],
        max_cost_level: Optional[int],
        top_k: int,
    ) -> IngredientRecommendation:
        mode = ingredient["recommend_mode"]
        rec = IngredientRecommendation(
            role=ingredient["role"],
            label=ingredient["label"],
            recommend_mode=mode,
            static_fallback=ingredient.get("static_fallback"),
        )

        if mode == MODE_STATIC_ONLY:
            rec.used_fallback = True
            return rec

        # 從 DB 查詢候選
        candidates = self._fetch_candidates(ingredient, max_cost_level)

        if candidates:
            scored = self._score_candidates(
                candidates, ingredient["ideal_flavors"], user_flavor_prefs,
                ingredient.get("abv_range"),
            )
            rec.candidates = scored[:top_k]
        elif mode == MODE_DYNAMIC_OR_STATIC and ingredient.get("static_fallback"):
            rec.used_fallback = True

        return rec

    def _fetch_candidates(
        self, ingredient: dict, max_cost_level: Optional[int]
    ) -> list[SpiritCandidate]:
        """從 DB 依類別與子類型過濾候選烈酒。"""
        categories = ingredient.get("categories", [])
        suitable = ingredient.get("suitable_subtypes", [])
        unsuitable = ingredient.get("unsuitable_subtypes", [])

        # 若有 suitable_subtypes，直接用 spirit_type 篩選（不限 URL category）
        # 否則依 URL 路徑判斷 category（spirit.category 欄位多為空）
        where_parts: list[str] = []
        params: list = []

        if suitable:
            placeholders = ",".join("?" * len(suitable))
            where_parts.append(f"s.spirit_type IN ({placeholders})")
            params.extend(suitable)
        elif categories:
            url_filters = ["s.url LIKE ?" for _ in categories]
            where_parts.append("(" + " OR ".join(url_filters) + ")")
            params.extend(f"%distiller.com/spirits/{cat}/%" for cat in categories)

        if unsuitable:
            placeholders = ",".join("?" * len(unsuitable))
            where_parts.append(f"s.spirit_type NOT IN ({placeholders})")
            params.extend(unsuitable)

        if max_cost_level is not None:
            where_parts.append("(s.cost_level IS NULL OR s.cost_level <= ?)")
            params.append(max_cost_level)

        where_clause = "WHERE " + " AND ".join(where_parts) if where_parts else ""

        sql = f"""
            SELECT s.id, s.name, s.brand, s.spirit_type, s.country,
                   s.abv, s.expert_score, s.community_score, s.cost_level,
                   s.flavor_summary, s.tasting_notes, s.url
            FROM spirits s
            {where_clause}
            AND s.expert_score IS NOT NULL
            ORDER BY s.expert_score DESC
            LIMIT 100
        """

        rows = self.conn.execute(sql, params).fetchall()
        if not rows:
            return []

        # 批次載入風味資料
        spirit_ids = [r["id"] for r in rows]
        flavor_map = self._load_flavors(spirit_ids)

        candidates = []
        for row in rows:
            c = SpiritCandidate(
                spirit_id=row["id"],
                name=row["name"] or "",
                brand=row["brand"] or "",
                spirit_type=row["spirit_type"] or "",
                country=row["country"] or "",
                abv=row["abv"],
                expert_score=row["expert_score"],
                community_score=row["community_score"],
                cost_level=row["cost_level"],
                flavor_summary=row["flavor_summary"] or "",
                tasting_notes=row["tasting_notes"] or "",
                url=row["url"] or "",
                flavors=flavor_map.get(row["id"], {}),
            )
            candidates.append(c)
        return candidates

    def _load_flavors(self, spirit_ids: list[int]) -> dict[int, dict[str, float]]:
        """批次載入多筆烈酒的風味向量。"""
        if not spirit_ids:
            return {}
        placeholders = ",".join("?" * len(spirit_ids))
        rows = self.conn.execute(
            f"SELECT spirit_id, flavor_name, flavor_value FROM flavor_profiles "
            f"WHERE spirit_id IN ({placeholders})",
            spirit_ids,
        ).fetchall()
        result: dict[int, dict[str, float]] = {}
        for row in rows:
            result.setdefault(row["spirit_id"], {})[row["flavor_name"]] = float(row["flavor_value"])
        return result

    def _score_candidates(
        self,
        candidates: list[SpiritCandidate],
        ideal_flavors: dict[str, float],
        user_flavor_prefs: Optional[dict[str, float]],
        abv_range: Optional[tuple],
    ) -> list[SpiritCandidate]:
        """對每位候選烈酒計算綜合評分並排序。"""
        max_expert = max((c.expert_score or 0) for c in candidates) or 100
        max_community = max((c.community_score or 0) for c in candidates) or 5.0

        for c in candidates:
            cocktail_sim = _cosine_similarity(c.flavors, ideal_flavors)

            user_sim = 0.0
            if user_flavor_prefs:
                user_sim = _cosine_similarity(c.flavors, user_flavor_prefs)

            expert_norm = (c.expert_score or 0) / max_expert
            community_norm = (c.community_score or 0) / max_community

            abv_pen = _abv_penalty(c.abv, abv_range)

            if user_flavor_prefs:
                raw = (
                    self.W_COCKTAIL_FLAVOR * cocktail_sim
                    + self.W_USER_FLAVOR * user_sim
                    + self.W_EXPERT_SCORE * expert_norm
                    + self.W_COMMUNITY_SCORE * community_norm
                )
            else:
                # 無用戶偏好時，重新分配 user_sim 的權重給 cocktail_sim
                w_cocktail = self.W_COCKTAIL_FLAVOR + self.W_USER_FLAVOR
                raw = (
                    w_cocktail * cocktail_sim
                    + self.W_EXPERT_SCORE * expert_norm
                    + self.W_COMMUNITY_SCORE * community_norm
                )

            c.score = raw * abv_pen
            c.score_breakdown = {
                "cocktail_flavor_sim": round(cocktail_sim, 3),
                "user_flavor_sim": round(user_sim, 3),
                "expert_norm": round(expert_norm, 3),
                "community_norm": round(community_norm, 3),
                "abv_penalty": round(abv_pen, 3),
                "final_score": round(c.score, 4),
            }

        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ─── 格式化輸出工具 ────────────────────────────────────────────

COST_SYMBOLS = {1: "$", 2: "$$", 3: "$$$", 4: "$$$$", 5: "$$$$$"}


def format_recommendation(result: CocktailRecommendation) -> str:
    """將推薦結果格式化為 LINE Bot 文字訊息。"""
    lines: list[str] = []
    lines.append(f"🍹 {result.cocktail_name} 用料推薦")
    lines.append(f"風格：{result.flavor_style}")
    lines.append(f"{result.cocktail_description}")
    lines.append("─" * 30)

    for ing in result.ingredients:
        lines.append(f"\n【{ing.label}】")

        if ing.recommend_mode == MODE_STATIC_ONLY:
            fb = ing.static_fallback or {}
            usage = f"  用量：{fb['usage']}" if fb.get("usage") else ""
            note = f"  說明：{fb['note']}" if fb.get("note") else ""
            lines.append(f"  📌 {fb.get('name', '—')}{usage}{note}")
            continue

        if ing.candidates:
            for i, c in enumerate(ing.candidates, 1):
                cost = COST_SYMBOLS.get(c.cost_level or 0, "?")
                score_str = f"評分 {c.expert_score}" if c.expert_score else ""
                abv_str = f"{c.abv}%" if c.abv else ""
                meta = " | ".join(filter(None, [score_str, abv_str, cost, c.country]))
                lines.append(f"  {'⭐' if i == 1 else f'{i}.'} {c.name}")
                if meta:
                    lines.append(f"     {meta}")
                if c.flavor_summary:
                    lines.append(f"     {c.flavor_summary}")

            if ing.used_fallback or (ing.recommend_mode == MODE_DYNAMIC_OR_STATIC and ing.static_fallback):
                fb = ing.static_fallback or {}
                if fb.get("alternatives"):
                    alts = "、".join(fb["alternatives"])
                    lines.append(f"  💡 其他選項：{alts}")

        elif ing.used_fallback and ing.static_fallback:
            fb = ing.static_fallback
            lines.append(f"  📌 {fb.get('name', '—')}（靜態推薦）")
            if fb.get("note"):
                lines.append(f"     {fb['note']}")
            if fb.get("alternatives"):
                alts = "、".join(fb["alternatives"])
                lines.append(f"  💡 替代選項：{alts}")

    return "\n".join(lines)


def format_recommendation_short(result: CocktailRecommendation) -> str:
    """精簡版格式，適合快速回覆。"""
    lines: list[str] = [f"🍹 {result.cocktail_name}"]
    for ing in result.ingredients:
        if ing.recommend_mode == MODE_STATIC_ONLY:
            fb = ing.static_fallback or {}
            lines.append(f"• {ing.label}：{fb.get('name', '—')}")
            continue
        if ing.candidates:
            top = ing.candidates[0]
            cost = COST_SYMBOLS.get(top.cost_level or 0, "")
            lines.append(f"• {ing.label}：{top.name} ({top.expert_score}分 {cost})")
        elif ing.used_fallback and ing.static_fallback:
            lines.append(f"• {ing.label}：{ing.static_fallback.get('name', '—')}")
    return "\n".join(lines)
