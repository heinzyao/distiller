"""
風味偏好解析

涵蓋：
- 關鍵字映射與強度修飾
- 否定偏好偵測
- 風格/地區參照
- 酒款參照提取
"""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass
class ParseResult:
    flavor_vector: dict[str, float] | None
    spirit_refs: list[str]
    avoid_flavors: set[str]


KEYWORD_MAP: dict[str, dict[str, float]] = {
    "煙燻": {"smoky": 80, "peaty": 60},
    "泥煤": {"peaty": 85, "smoky": 70, "earthy": 50},
    "花香": {"floral": 80, "fruity": 50},
    "果香": {"fruity": 80, "floral": 40, "sweet": 50},
    "草本": {"herbal": 80, "juniper": 60},
    "辛香": {"spicy": 80, "herbal": 50},
    "甜": {"sweet": 75, "vanilla": 55},
    "苦": {"bitter": 75, "herbal": 50},
    "濃郁": {"rich": 80, "full_bodied": 70, "sweet": 50},
    "清爽": {"tart": 50, "floral": 55, "sweet": 25, "rich": 20},
    "柑橘": {"fruity": 70, "tart": 60, "floral": 40},
    "香草": {"vanilla": 80, "sweet": 60, "rich": 50},
    "木質": {"woody": 75, "earthy": 50, "rich": 55},
    "咖啡": {"rich": 70, "bitter": 60, "roast": 65},
    "海鹽": {"salty": 70, "briny": 60},
    "輕盈": {"floral": 60, "fruity": 50, "rich": 20, "full_bodied": 25},
    "重口": {"rich": 80, "full_bodied": 80, "spicy": 60},
    "juniper": {"juniper": 85},
    "smoky": {"smoky": 80},
    "peaty": {"peaty": 85},
    "floral": {"floral": 80},
    "herbal": {"herbal": 80},
    "fruity": {"fruity": 80},
    "sweet": {"sweet": 75},
    "spicy": {"spicy": 80},
    "堅果": {"nutty": 75, "rich": 50},
    "穀物": {"grain": 70, "neutral": 40},
    "蜂蜜": {"sweet": 70, "rich": 60, "floral": 40},
    "焦糖": {"sweet": 70, "vanilla": 55, "roast": 45},
    "雪莉": {"rich": 70, "nutty": 60, "fruity": 55},
    "橡木": {"woody": 80, "vanilla": 50, "rich": 55},
    "太妃糖": {"sweet": 75, "rich": 65, "vanilla": 60},
    "熱帶水果": {"fruity": 85, "sweet": 60},
    "薄荷": {"herbal": 70, "spicy": 40},
    "奶油": {"rich": 75, "full_bodied": 65},
    "巧克力": {"rich": 75, "sweet": 55, "bitter": 40, "roast": 50},
    "肉桂": {"spicy": 75, "sweet": 45},
    "woody": {"woody": 75},
    "bitter": {"bitter": 75},
    "tart": {"tart": 70},
    "rich": {"rich": 80},
    "earthy": {"earthy": 70},
    "nutty": {"nutty": 75},
    "roast": {"roast": 70},
    "salty": {"salty": 70},
    "briny": {"briny": 65},
    "oily": {"oily": 70},
    "grain": {"grain": 65},
    "vanilla": {"vanilla": 80},
}


STYLE_MAP: dict[str, dict[str, float]] = {
    "islay": {"smoky": 80, "peaty": 85, "salty": 50, "earthy": 40, "briny": 45},
    "highland": {"herbal": 55, "floral": 50, "rich": 60, "woody": 55},
    "speyside": {"fruity": 70, "sweet": 65, "floral": 55, "vanilla": 50},
    "lowland": {"floral": 65, "sweet": 55, "herbal": 50},
    "campbeltown": {"smoky": 50, "salty": 55, "briny": 50, "rich": 60, "oily": 55},
    "islands": {"smoky": 55, "salty": 60, "briny": 55, "herbal": 45, "peaty": 45},
    "japanese": {"floral": 60, "fruity": 55, "sweet": 50, "rich": 50},
    "bourbon": {"sweet": 70, "vanilla": 75, "woody": 60, "rich": 65},
    "rye": {"spicy": 75, "herbal": 55, "woody": 50, "rich": 55},
    "irish": {"sweet": 55, "floral": 50, "fruity": 50, "grain": 40},
    "mezcal": {"smoky": 85, "earthy": 70, "herbal": 55, "fruity": 40},
    "london dry": {"juniper": 85, "herbal": 65, "floral": 40},
    "old tom": {"sweet": 60, "juniper": 65, "herbal": 55, "floral": 50},
}


_NEGATION_PREFIXES = tuple(
    sorted(["不要太", "不要", "不喜歡", "少一點", "不"], key=len, reverse=True)
)

_INTENSITY_MAP = {
    "很": 1.15,
    "非常": 1.2,
    "超": 1.2,
    "極": 1.2,
    "微": 0.6,
    "稍微": 0.6,
    "有點": 0.65,
    "slightly": 0.6,
    "very": 1.15,
}


def _overlaps(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    for r_start, r_end in ranges:
        if start < r_end and end > r_start:
            return True
    return False


def _merge_vector(
    target: dict[str, float], addition: dict[str, float], multiplier: float = 1.0
) -> None:
    for dim, value in addition.items():
        scaled = min(100.0, value * multiplier)
        existing = target.get(dim, 0.0)
        target[dim] = max(existing, scaled)


def _extract_style_vectors(pref_text: str) -> list[dict[str, float]]:
    style_vectors: list[dict[str, float]] = []
    style_map_lower = {key.lower(): value for key, value in STYLE_MAP.items()}
    seen: set[str] = set()

    for match in re.finditer(r"像\s*(.+?)\s*風格", pref_text, flags=re.IGNORECASE):
        style = match.group(1).strip().lower()
        if style in style_map_lower and style not in seen:
            style_vectors.append(style_map_lower[style])
            seen.add(style)

    for match in re.finditer(r"(\w[\w\s]*?)\s*style", pref_text, flags=re.IGNORECASE):
        style = match.group(1).strip().lower()
        if style in style_map_lower and style not in seen:
            style_vectors.append(style_map_lower[style])
            seen.add(style)

    for match in re.finditer(r"(\w+)\s*風", pref_text, flags=re.IGNORECASE):
        style = match.group(1).strip().lower()
        if style in style_map_lower and style not in seen:
            style_vectors.append(style_map_lower[style])
            seen.add(style)

    return style_vectors


def _extract_spirit_refs(pref_text: str) -> list[str]:
    spirit_refs: list[str] = []

    for match in re.finditer(
        r"類似\s*(.+?)(?=\s+[\u4e00-\u9fff]|$|，|,|。|！)",
        pref_text,
        flags=re.IGNORECASE,
    ):
        name = match.group(1).strip(" ，,。！!、")
        if name:
            spirit_refs.append(name)

    for match in re.finditer(
        r"like\s+(.+?)(\s+style)?(?:\s*$|,)", pref_text, flags=re.IGNORECASE
    ):
        if match.group(2):
            continue
        name = match.group(1).strip(" ，,。！!、")
        if name:
            spirit_refs.append(name)

    for match in re.finditer(
        r"像\s*(.+?)(?:\s+那樣|\s+那種|\s+的感覺)", pref_text, flags=re.IGNORECASE
    ):
        name = match.group(1).strip(" ，,。！!、")
        if name:
            spirit_refs.append(name)

    return spirit_refs


def parse_flavor_prefs(pref_text: str) -> ParseResult:
    if not pref_text:
        return ParseResult(flavor_vector=None, spirit_refs=[], avoid_flavors=set())

    pref_lower = pref_text.lower()
    avoid_flavors: set[str] = set()
    consumed_negations: list[tuple[int, int]] = []

    for prefix in _NEGATION_PREFIXES:
        for keyword, vector in KEYWORD_MAP.items():
            combined = (prefix + keyword).lower()
            start = pref_lower.find(combined)
            while start != -1:
                end = start + len(combined)
                consumed_negations.append((start, end))
                avoid_flavors.update(vector.keys())
                start = pref_lower.find(combined, start + 1)

    flavor_vector: dict[str, float] = {}
    for style_vector in _extract_style_vectors(pref_text):
        _merge_vector(flavor_vector, style_vector)

    handled_ranges: list[tuple[int, int]] = []
    intensity_items = sorted(
        _INTENSITY_MAP.items(), key=lambda item: len(item[0]), reverse=True
    )
    keyword_items = list(KEYWORD_MAP.items())

    for keyword, vector in keyword_items:
        keyword_lower = keyword.lower()
        for modifier, multiplier in intensity_items:
            pattern = re.escape(modifier.lower()) + r"\s*" + re.escape(keyword_lower)
            for match in re.finditer(pattern, pref_lower):
                keyword_start = match.end() - len(keyword_lower)
                keyword_end = match.end()
                if _overlaps(keyword_start, keyword_end, consumed_negations):
                    continue
                if _overlaps(keyword_start, keyword_end, handled_ranges):
                    continue
                _merge_vector(flavor_vector, vector, multiplier)
                handled_ranges.append((keyword_start, keyword_end))

    for keyword, vector in keyword_items:
        keyword_lower = keyword.lower()
        start = pref_lower.find(keyword_lower)
        while start != -1:
            end = start + len(keyword_lower)
            if not _overlaps(start, end, consumed_negations) and not _overlaps(
                start, end, handled_ranges
            ):
                _merge_vector(flavor_vector, vector)
                handled_ranges.append((start, end))
            start = pref_lower.find(keyword_lower, start + 1)

    spirit_refs = _extract_spirit_refs(pref_text)

    result_vector = flavor_vector or None

    return ParseResult(
        flavor_vector=result_vector,
        spirit_refs=spirit_refs,
        avoid_flavors=avoid_flavors,
    )
