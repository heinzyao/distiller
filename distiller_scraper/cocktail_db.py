"""
經典雞尾酒知識庫

每款酒譜定義：
- ingredients：所有需要烈酒/利口酒的成分
  - role：成分角色識別碼
  - label：顯示用中文名稱
  - recommend_mode：
      "dynamic"              → 完整個人化（DB 充足）
      "dynamic_or_static"    → 優先 DB，不足時用靜態 fallback
      "static_only"          → 固定推薦（果汁、糖漿等）
  - categories：對應 distiller.com 的類別
  - suitable_subtypes：適合的 spirit_type（空列表 = 不限）
  - unsuitable_subtypes：明確排除的 spirit_type
  - ideal_flavors：理想風味向量（鍵為 flavor_name，值 0–100）
  - abv_range：建議酒精濃度範圍 (min, max)，None = 不限
  - static_fallback：DB 無資料時的靜態推薦
"""

from __future__ import annotations

# ─── 成分角色常數 ───────────────────────────────────────────────
ROLE_BASE = "base"
ROLE_MODIFIER = "modifier"
ROLE_LIQUEUR = "liqueur"
ROLE_VERMOUTH = "vermouth"
ROLE_BITTER = "bitter"
ROLE_MIXER = "mixer"

# ─── 推薦模式常數 ──────────────────────────────────────────────
MODE_DYNAMIC = "dynamic"
MODE_DYNAMIC_OR_STATIC = "dynamic_or_static"
MODE_STATIC_ONLY = "static_only"


def _ingredient(
    role: str,
    label: str,
    recommend_mode: str,
    ideal_flavors: dict[str, int],
    categories: list[str] | None = None,
    suitable_subtypes: list[str] | None = None,
    classic_subtypes: list[str] | None = None,
    unsuitable_subtypes: list[str] | None = None,
    abv_range: tuple[float, float] | None = None,
    static_fallback: dict | None = None,
) -> dict:
    return {
        "role": role,
        "label": label,
        "recommend_mode": recommend_mode,
        "categories": categories or [],
        "suitable_subtypes": suitable_subtypes or [],
        "classic_subtypes": classic_subtypes or [],
        "unsuitable_subtypes": unsuitable_subtypes or [],
        "ideal_flavors": ideal_flavors,
        "abv_range": abv_range,
        "static_fallback": static_fallback,
    }


# ─── 雞尾酒知識庫 ─────────────────────────────────────────────
COCKTAIL_DB: dict[str, dict] = {

    # ── Negroni ──────────────────────────────────────────────────
    "negroni": {
        "name": "Negroni",
        "aliases": ["內格羅尼"],
        "description": "等比例琴酒 + Campari + 甜苦艾酒，苦甜平衡的義式經典",
        "flavor_style": "苦甜草本",
        "recipe": [
            {"item": "琴酒",     "amount": "30ml"},
            {"item": "Campari",  "amount": "30ml", "note": "苦橙利口酒，奠定苦味骨架"},
            {"item": "甜苦艾酒", "amount": "30ml", "note": "香草調，柔化苦澀"},
            {"item": "橙皮",     "amount": "1 片",  "note": "裝飾"},
        ],
        "glassware": "老式杯（加冰）",
        "method": "攪拌法",
        "ingredients": [
            _ingredient(
                role=ROLE_BASE, label="琴酒",
                recommend_mode=MODE_DYNAMIC,
                categories=["gin"],
                suitable_subtypes=["London Dry Gin", "Old Tom Gin", "Distilled Gin"],
                classic_subtypes=["London Dry Gin"],
                unsuitable_subtypes=["Flavored Gin"],
                ideal_flavors={"herbal": 70, "juniper": 75, "bitter": 25, "floral": 35},
                abv_range=(40, 50),
            ),
            _ingredient(
                role=ROLE_MODIFIER, label="苦味利口酒",
                recommend_mode=MODE_DYNAMIC_OR_STATIC,
                categories=["liqueurs-bitters"],
                suitable_subtypes=["Amaro"],
                classic_subtypes=["Amaro"],
                ideal_flavors={"bitter": 85, "sweet": 35, "fruity": 50, "herbal": 55},
                abv_range=(20, 30),
                static_fallback={
                    "name": "Campari",
                    "alternatives": ["Aperol（較甜）", "Contratto Bitter"],
                    "note": "苦橙調性，奠定 Negroni 的苦味骨架",
                },
            ),
            _ingredient(
                role=ROLE_VERMOUTH, label="甜型苦艾酒",
                recommend_mode=MODE_DYNAMIC_OR_STATIC,
                categories=["liqueurs-bitters"],
                suitable_subtypes=["Vermouth"],
                classic_subtypes=["Vermouth"],
                ideal_flavors={"sweet": 60, "herbal": 55, "rich": 45, "bitter": 20},
                abv_range=(15, 20),
                static_fallback={
                    "name": "Carpano Antica Formula",
                    "alternatives": ["Martini Rosso", "Dolin Rouge"],
                    "note": "香草調甜苦艾酒，柔化 Campari 的苦澀",
                },
            ),
        ],
    },

    # ── Old Fashioned ────────────────────────────────────────────
    "old_fashioned": {
        "name": "Old Fashioned",
        "aliases": ["老式雞尾酒", "老古板"],
        "description": "威士忌 + 方糖 + 苦精，最古典的烈酒調飲",
        "flavor_style": "濃郁辛香",
        "recipe": [
            {"item": "波本/裸麥威士忌", "amount": "60ml"},
            {"item": "方糖",           "amount": "1 顆", "note": "或 1tsp 糖漿"},
            {"item": "Angostura 苦精", "amount": "2 dash"},
            {"item": "橙皮",           "amount": "1 片",  "note": "擠壓後入杯裝飾"},
        ],
        "glassware": "老式杯（加一顆大冰塊）",
        "method": "攪拌法",
        "ingredients": [
            _ingredient(
                role=ROLE_BASE, label="威士忌",
                recommend_mode=MODE_DYNAMIC,
                categories=["whiskey"],
                suitable_subtypes=["Bourbon", "Rye", "Tennessee Whiskey"],
                classic_subtypes=["Bourbon"],
                unsuitable_subtypes=["Blended", "Canadian"],
                ideal_flavors={"rich": 75, "sweet": 55, "spicy": 50, "vanilla": 60, "woody": 45},
                abv_range=(40, 60),
            ),
            _ingredient(
                role=ROLE_BITTER, label="芳香苦精",
                recommend_mode=MODE_STATIC_ONLY,
                ideal_flavors={},
                static_fallback={
                    "name": "Angostura Aromatic Bitters",
                    "alternatives": ["Peychaud's Bitters（偏八角香）"],
                    "usage": "2 dash",
                    "note": "微量使用，點綴芳香層次，無需從 DB 篩選",
                },
            ),
        ],
    },

    # ── Manhattan ────────────────────────────────────────────────
    "manhattan": {
        "name": "Manhattan",
        "aliases": ["曼哈頓"],
        "description": "裸麥威士忌 + 甜苦艾酒 + 苦精，紐約風格的優雅經典",
        "flavor_style": "辛香甜潤",
        "recipe": [
            {"item": "裸麥威士忌",    "amount": "60ml", "note": "Rye 為傳統首選"},
            {"item": "甜苦艾酒",     "amount": "30ml"},
            {"item": "Angostura 苦精", "amount": "2 dash"},
            {"item": "黑櫻桃",       "amount": "1 顆",  "note": "裝飾"},
        ],
        "glassware": "馬丁尼杯（無冰）",
        "method": "攪拌法",
        "ingredients": [
            _ingredient(
                role=ROLE_BASE, label="裸麥/波本威士忌",
                recommend_mode=MODE_DYNAMIC,
                categories=["whiskey"],
                suitable_subtypes=["Rye", "Bourbon"],
                classic_subtypes=["Rye"],
                ideal_flavors={"spicy": 65, "rich": 60, "sweet": 45, "woody": 40},
                abv_range=(40, 55),
            ),
            _ingredient(
                role=ROLE_VERMOUTH, label="甜型苦艾酒",
                recommend_mode=MODE_DYNAMIC_OR_STATIC,
                categories=["liqueurs-bitters"],
                suitable_subtypes=["Vermouth"],
                classic_subtypes=["Vermouth"],
                ideal_flavors={"sweet": 65, "herbal": 50, "rich": 50},
                abv_range=(15, 20),
                static_fallback={
                    "name": "Carpano Antica Formula",
                    "alternatives": ["Martini Rosso", "Cocchi Storico Vermouth di Torino"],
                    "note": "選用香草調性較重的甜苦艾，與裸麥辛香形成對比",
                },
            ),
            _ingredient(
                role=ROLE_BITTER, label="芳香苦精",
                recommend_mode=MODE_STATIC_ONLY,
                ideal_flavors={},
                static_fallback={
                    "name": "Angostura Aromatic Bitters",
                    "usage": "2 dash",
                },
            ),
        ],
    },

    # ── Martini ──────────────────────────────────────────────────
    "martini": {
        "name": "Martini",
        "aliases": ["馬丁尼", "乾馬丁尼"],
        "description": "琴酒 + 不甜苦艾酒，以比例決定乾燥程度",
        "flavor_style": "清爽草本",
        "recipe": [
            {"item": "琴酒",     "amount": "60ml"},
            {"item": "不甜苦艾酒", "amount": "10ml", "note": "比例 6:1（Dry Martini）"},
            {"item": "橄欖或檸檬皮", "amount": "1 個", "note": "裝飾，決定風格走向"},
        ],
        "glassware": "馬丁尼杯（無冰）",
        "method": "攪拌法（或 shaken，視偏好）",
        "ingredients": [
            _ingredient(
                role=ROLE_BASE, label="琴酒",
                recommend_mode=MODE_DYNAMIC,
                categories=["gin"],
                suitable_subtypes=["London Dry Gin", "Distilled Gin"],
                classic_subtypes=["London Dry Gin"],
                unsuitable_subtypes=["Flavored Gin", "Barrel-Aged Gin"],
                ideal_flavors={"juniper": 80, "herbal": 65, "floral": 40, "tart": 25},
                abv_range=(40, 50),
            ),
            _ingredient(
                role=ROLE_VERMOUTH, label="不甜苦艾酒",
                recommend_mode=MODE_DYNAMIC_OR_STATIC,
                categories=["liqueurs-bitters"],
                suitable_subtypes=["Vermouth"],
                classic_subtypes=["Vermouth"],
                ideal_flavors={"herbal": 65, "tart": 45, "floral": 35, "sweet": 20},
                abv_range=(15, 20),
                static_fallback={
                    "name": "Noilly Prat Original Dry",
                    "alternatives": ["Dolin Dry", "Martini Extra Dry"],
                    "note": "乾型苦艾酒輕點即可，比例 5:1 至 15:1（琴酒:苦艾）",
                },
            ),
        ],
    },

    # ── Daiquiri ─────────────────────────────────────────────────
    "daiquiri": {
        "name": "Daiquiri",
        "aliases": ["黛吉利"],
        "description": "白蘭姆 + 萊姆汁 + 糖，展現蘭姆酒純粹風味的古巴經典",
        "flavor_style": "清爽果酸",
        "recipe": [
            {"item": "白蘭姆",    "amount": "60ml", "note": "Silver Rum 最能展現純淨風味"},
            {"item": "現榨萊姆汁", "amount": "22ml", "note": "必須新鮮現榨"},
            {"item": "糖漿",      "amount": "15ml"},
        ],
        "glassware": "雞尾酒杯（無冰）",
        "method": "搖盪法",
        "ingredients": [
            _ingredient(
                role=ROLE_BASE, label="白蘭姆",
                recommend_mode=MODE_DYNAMIC,
                categories=["rum"],
                suitable_subtypes=["Silver Rum"],
                classic_subtypes=["Silver Rum"],
                unsuitable_subtypes=["Spiced Rum", "Dark Rum", "Flavored Rum"],
                ideal_flavors={"sweet": 50, "fruity": 55, "tart": 35, "floral": 30},
                abv_range=(37, 46),
            ),
            _ingredient(
                role=ROLE_MIXER, label="現榨萊姆汁",
                recommend_mode=MODE_STATIC_ONLY,
                ideal_flavors={},
                static_fallback={
                    "name": "現榨萊姆汁",
                    "usage": "3/4 oz",
                    "note": "必須新鮮現榨，不可用瓶裝",
                },
            ),
        ],
    },

    # ── Margarita ────────────────────────────────────────────────
    "margarita": {
        "name": "Margarita",
        "aliases": ["瑪格麗特"],
        "description": "龍舌蘭 + 橙味利口酒 + 萊姆汁，墨西哥國民調酒",
        "flavor_style": "活潑果酸",
        "recipe": [
            {"item": "龍舌蘭（Blanco）", "amount": "50ml", "note": "Blanco 最為經典"},
            {"item": "橙味利口酒",       "amount": "25ml", "note": "Cointreau 為標準"},
            {"item": "現榨萊姆汁",       "amount": "25ml"},
            {"item": "鹽口",            "amount": "適量",  "note": "杯口裝飾（可省略）"},
        ],
        "glassware": "瑪格麗特杯或老式杯",
        "method": "搖盪法",
        "ingredients": [
            _ingredient(
                role=ROLE_BASE, label="龍舌蘭",
                recommend_mode=MODE_DYNAMIC,
                categories=["tequila-mezcal"],
                suitable_subtypes=["Tequila Blanco", "Tequila Reposado",
                                   "Blanco Tequila", "Reposado Tequila"],
                classic_subtypes=["Tequila Blanco", "Blanco Tequila"],
                unsuitable_subtypes=["Mezcal", "Mezcal Añejo"],
                ideal_flavors={"fruity": 55, "herbal": 45, "spicy": 35, "tart": 30},
                abv_range=(38, 46),
            ),
            _ingredient(
                role=ROLE_LIQUEUR, label="橙味利口酒",
                recommend_mode=MODE_DYNAMIC_OR_STATIC,
                categories=["liqueurs-bitters"],
                suitable_subtypes=["Triple Sec/Curaçao"],
                classic_subtypes=["Triple Sec/Curaçao"],
                ideal_flavors={"sweet": 60, "fruity": 70, "tart": 35, "floral": 30},
                abv_range=(30, 45),
                static_fallback={
                    "name": "Cointreau",
                    "alternatives": ["Pierre Ferrand Dry Curaçao（DB 有收錄，評分 96）",
                                     "Grand Marnier（較甜）"],
                    "note": "橙皮精油香氣，提升整體複雜度",
                },
            ),
            _ingredient(
                role=ROLE_MIXER, label="現榨萊姆汁",
                recommend_mode=MODE_STATIC_ONLY,
                ideal_flavors={},
                static_fallback={
                    "name": "現榨萊姆汁",
                    "usage": "1 oz",
                },
            ),
        ],
    },

    # ── Whiskey Sour ─────────────────────────────────────────────
    "whiskey_sour": {
        "name": "Whiskey Sour",
        "aliases": ["威士忌酸酒"],
        "description": "波本威士忌 + 檸檬汁 + 糖，加蛋白可做 Boston Sour",
        "flavor_style": "酸甜濃郁",
        "recipe": [
            {"item": "波本威士忌",  "amount": "60ml"},
            {"item": "新鮮檸檬汁",  "amount": "22ml"},
            {"item": "糖漿",       "amount": "15ml"},
            {"item": "蛋白",       "amount": "1 個（選用）", "note": "加入即為 Boston Sour"},
        ],
        "glassware": "岩石杯或酸酒杯",
        "method": "搖盪法（加蛋白需乾搖）",
        "ingredients": [
            _ingredient(
                role=ROLE_BASE, label="波本威士忌",
                recommend_mode=MODE_DYNAMIC,
                categories=["whiskey"],
                suitable_subtypes=["Bourbon", "Rye", "American Single Malt"],
                classic_subtypes=["Bourbon"],
                ideal_flavors={"sweet": 60, "rich": 65, "vanilla": 55, "fruity": 40},
                abv_range=(40, 55),
            ),
            _ingredient(
                role=ROLE_MIXER, label="新鮮檸檬汁",
                recommend_mode=MODE_STATIC_ONLY,
                ideal_flavors={},
                static_fallback={"name": "新鮮檸檬汁", "usage": "3/4 oz"},
            ),
        ],
    },

    # ── Mojito ───────────────────────────────────────────────────
    "mojito": {
        "name": "Mojito",
        "aliases": ["莫希托"],
        "description": "白蘭姆 + 薄荷 + 萊姆 + 糖 + 氣泡水，古巴夏日清爽飲",
        "flavor_style": "清爽薄荷",
        "recipe": [
            {"item": "白蘭姆",  "amount": "50ml", "note": "Silver Rum 保持清爽"},
            {"item": "新鮮薄荷", "amount": "10 片", "note": "輕壓不研磨，避免苦澀"},
            {"item": "萊姆",    "amount": "半顆",  "note": "切塊搾入"},
            {"item": "糖漿",    "amount": "15ml"},
            {"item": "氣泡水",  "amount": "適量",  "note": "最後補入"},
        ],
        "glassware": "高球杯（加碎冰）",
        "method": "搗壓法 + 直調",
        "ingredients": [
            _ingredient(
                role=ROLE_BASE, label="白蘭姆",
                recommend_mode=MODE_DYNAMIC,
                categories=["rum"],
                suitable_subtypes=["Silver Rum"],
                classic_subtypes=["Silver Rum"],
                unsuitable_subtypes=["Dark Rum", "Spiced Rum"],
                ideal_flavors={"sweet": 45, "fruity": 50, "floral": 35, "tart": 30},
                abv_range=(37, 43),
            ),
        ],
    },

    # ── Gimlet ───────────────────────────────────────────────────
    "gimlet": {
        "name": "Gimlet",
        "aliases": ["琴蕾"],
        "description": "琴酒 + 萊姆汁（或萊姆糖漿），簡約清新的英式古典",
        "flavor_style": "清新酸甜",
        "recipe": [
            {"item": "琴酒",      "amount": "60ml"},
            {"item": "Rose's 萊姆糖漿", "amount": "15ml", "note": "傳統版；現代版改用新鮮萊姆汁+糖"},
        ],
        "glassware": "雞尾酒杯（無冰）",
        "method": "搖盪法",
        "ingredients": [
            _ingredient(
                role=ROLE_BASE, label="琴酒",
                recommend_mode=MODE_DYNAMIC,
                categories=["gin"],
                suitable_subtypes=["London Dry Gin", "Modern Gin", "Distilled Gin"],
                classic_subtypes=["London Dry Gin"],
                unsuitable_subtypes=["Barrel-Aged Gin"],
                ideal_flavors={"juniper": 70, "herbal": 60, "floral": 50, "tart": 35},
                abv_range=(40, 48),
            ),
        ],
    },

    # ── Cosmopolitan ─────────────────────────────────────────────
    "cosmopolitan": {
        "name": "Cosmopolitan",
        "aliases": ["柯夢波丹", "宇宙"],
        "description": "伏特加 + 橙味利口酒 + 蔓越莓汁 + 萊姆，都市感粉紅色雞尾酒",
        "flavor_style": "果香甜酸",
        "recipe": [
            {"item": "伏特加",    "amount": "40ml"},
            {"item": "橙味利口酒", "amount": "15ml", "note": "Cointreau 為標準"},
            {"item": "蔓越莓汁",  "amount": "30ml"},
            {"item": "現榨萊姆汁", "amount": "15ml"},
            {"item": "橙皮",     "amount": "1 片",  "note": "裝飾"},
        ],
        "glassware": "馬丁尼杯（無冰）",
        "method": "搖盪法",
        "ingredients": [
            _ingredient(
                role=ROLE_BASE, label="伏特加",
                recommend_mode=MODE_DYNAMIC,
                categories=["vodka"],
                suitable_subtypes=["Unflavored Vodka"],
                classic_subtypes=["Unflavored Vodka"],
                unsuitable_subtypes=["Barrel-Aged Vodka"],
                ideal_flavors={"neutral": 70, "sweet": 30, "fruity": 25},
                abv_range=(37, 45),
            ),
            _ingredient(
                role=ROLE_LIQUEUR, label="橙味利口酒",
                recommend_mode=MODE_DYNAMIC_OR_STATIC,
                categories=["liqueurs-bitters"],
                suitable_subtypes=["Triple Sec/Curaçao"],
                classic_subtypes=["Triple Sec/Curaçao"],
                ideal_flavors={"sweet": 65, "fruity": 70, "floral": 30},
                static_fallback={
                    "name": "Cointreau",
                    "alternatives": ["Pierre Ferrand Dry Curaçao"],
                },
            ),
        ],
    },

    # ── Moscow Mule ──────────────────────────────────────────────
    "moscow_mule": {
        "name": "Moscow Mule",
        "aliases": ["莫斯科騾子"],
        "description": "伏特加 + 薑汁啤酒 + 萊姆，銅杯盛裝的辛辣清爽飲",
        "flavor_style": "辛辣清爽",
        "recipe": [
            {"item": "伏特加",  "amount": "50ml", "note": "中性清爽款為佳"},
            {"item": "薑汁啤酒", "amount": "100ml"},
            {"item": "萊姆汁",  "amount": "15ml"},
            {"item": "萊姆角",  "amount": "1 塊",  "note": "裝飾"},
        ],
        "glassware": "銅杯（加冰）",
        "method": "直調法",
        "ingredients": [
            _ingredient(
                role=ROLE_BASE, label="伏特加",
                recommend_mode=MODE_DYNAMIC,
                categories=["vodka"],
                suitable_subtypes=["Unflavored Vodka"],
                classic_subtypes=["Unflavored Vodka"],
                ideal_flavors={"neutral": 75, "sweet": 20},
                abv_range=(37, 45),
            ),
        ],
    },

    # ── Aperol Spritz ────────────────────────────────────────────
    "aperol_spritz": {
        "name": "Aperol Spritz",
        "aliases": ["阿佩羅氣泡"],
        "description": "Aperol + 普賽克氣泡酒 + 氣泡水，義大利開胃酒代表",
        "flavor_style": "苦橙輕盈",
        "recipe": [
            {"item": "Aperol",    "amount": "90ml"},
            {"item": "普賽克氣泡酒", "amount": "60ml"},
            {"item": "氣泡水",    "amount": "30ml"},
            {"item": "橙片",      "amount": "1 片",  "note": "裝飾"},
        ],
        "glassware": "大型紅酒杯（加冰）",
        "method": "直調法（3-2-1 比例）",
        "ingredients": [
            _ingredient(
                role=ROLE_MODIFIER, label="苦味開胃酒",
                recommend_mode=MODE_DYNAMIC_OR_STATIC,
                categories=["liqueurs-bitters"],
                suitable_subtypes=["Amaro"],
                classic_subtypes=["Amaro"],
                ideal_flavors={"bitter": 65, "sweet": 45, "fruity": 60, "floral": 35},
                abv_range=(11, 20),
                static_fallback={
                    "name": "Aperol",
                    "alternatives": ["Campari（較苦）", "Select（威尼斯傳統）"],
                    "note": "低酒精苦橙利口酒，定義此調酒的核心風格",
                },
            ),
        ],
    },

    # ── Paloma ───────────────────────────────────────────────────
    "paloma": {
        "name": "Paloma",
        "aliases": ["帕洛瑪"],
        "description": "龍舌蘭 + 葡萄柚汁/氣泡飲，墨西哥最受歡迎的龍舌蘭調酒",
        "flavor_style": "苦甜果香",
        "recipe": [
            {"item": "龍舌蘭（Blanco）", "amount": "50ml"},
            {"item": "葡萄柚氣泡飲（Squirt）", "amount": "150ml", "note": "或新鮮葡萄柚汁+氣泡水"},
            {"item": "萊姆汁",  "amount": "15ml"},
            {"item": "鹽口",    "amount": "適量",  "note": "杯口裝飾（可省略）"},
        ],
        "glassware": "高球杯（加冰）",
        "method": "直調法",
        "ingredients": [
            _ingredient(
                role=ROLE_BASE, label="龍舌蘭",
                recommend_mode=MODE_DYNAMIC,
                categories=["tequila-mezcal"],
                suitable_subtypes=["Tequila Blanco", "Tequila Reposado",
                                   "Blanco Tequila", "Reposado Tequila"],
                classic_subtypes=["Tequila Blanco", "Blanco Tequila"],
                ideal_flavors={"fruity": 50, "herbal": 40, "spicy": 30, "tart": 40},
                abv_range=(38, 46),
            ),
        ],
    },

    # ── Sidecar ──────────────────────────────────────────────────
    "sidecar": {
        "name": "Sidecar",
        "aliases": ["側車"],
        "description": "干邑白蘭地 + 橙味利口酒 + 檸檬汁，法式優雅調酒",
        "flavor_style": "果香優雅",
        "recipe": [
            {"item": "干邑白蘭地",  "amount": "50ml", "note": "VSOP 以上等級為佳"},
            {"item": "橙味利口酒", "amount": "20ml", "note": "Cointreau 為標準"},
            {"item": "新鮮檸檬汁", "amount": "20ml"},
            {"item": "糖口",      "amount": "適量",  "note": "杯口裝飾（可省略）"},
        ],
        "glassware": "雞尾酒杯（無冰）",
        "method": "搖盪法",
        "ingredients": [
            _ingredient(
                role=ROLE_BASE, label="干邑白蘭地",
                recommend_mode=MODE_DYNAMIC,
                categories=["brandy"],
                suitable_subtypes=["Cognac"],
                classic_subtypes=["Cognac"],
                ideal_flavors={"fruity": 65, "rich": 60, "sweet": 50, "floral": 40},
                abv_range=(40, 50),
            ),
            _ingredient(
                role=ROLE_LIQUEUR, label="橙味利口酒",
                recommend_mode=MODE_DYNAMIC_OR_STATIC,
                categories=["liqueurs-bitters"],
                suitable_subtypes=["Triple Sec/Curaçao"],
                classic_subtypes=["Triple Sec/Curaçao"],
                ideal_flavors={"sweet": 60, "fruity": 70, "tart": 30},
                static_fallback={
                    "name": "Cointreau",
                    "alternatives": ["Grand Marnier（增添白蘭地風味）"],
                },
            ),
        ],
    },

    # ── Last Word ────────────────────────────────────────────────
    "last_word": {
        "name": "Last Word",
        "aliases": ["最後一語"],
        "description": "等比例琴酒 + 夏翠絲 + 黑櫻桃利口酒 + 萊姆汁，禁酒令時代復古傑作",
        "flavor_style": "草本花香複雜",
        "recipe": [
            {"item": "琴酒",         "amount": "22ml"},
            {"item": "Green Chartreuse", "amount": "22ml", "note": "130 種草本，不可替換"},
            {"item": "Luxardo Maraschino", "amount": "22ml"},
            {"item": "現榨萊姆汁",  "amount": "22ml"},
        ],
        "glassware": "雞尾酒杯（無冰）",
        "method": "搖盪法（等比例 4 種）",
        "ingredients": [
            _ingredient(
                role=ROLE_BASE, label="琴酒",
                recommend_mode=MODE_DYNAMIC,
                categories=["gin"],
                suitable_subtypes=["London Dry Gin", "Distilled Gin"],
                classic_subtypes=["London Dry Gin"],
                ideal_flavors={"juniper": 75, "herbal": 65, "floral": 40},
                abv_range=(40, 48),
            ),
            _ingredient(
                role=ROLE_LIQUEUR, label="綠夏翠絲",
                recommend_mode=MODE_DYNAMIC_OR_STATIC,
                categories=["liqueurs-bitters"],
                suitable_subtypes=["Herbal/Spice Liqueurs"],
                classic_subtypes=["Herbal/Spice Liqueurs"],
                ideal_flavors={"herbal": 90, "sweet": 55, "spicy": 45, "floral": 50},
                abv_range=(55, 60),
                static_fallback={
                    "name": "Green Chartreuse",
                    "note": "130種草本，不可替換，是此酒的靈魂",
                },
            ),
            _ingredient(
                role=ROLE_LIQUEUR, label="黑櫻桃利口酒",
                recommend_mode=MODE_DYNAMIC_OR_STATIC,
                categories=["liqueurs-bitters"],
                suitable_subtypes=["Other Liqueurs"],
                classic_subtypes=["Other Liqueurs"],
                ideal_flavors={"sweet": 70, "fruity": 75, "floral": 40},
                static_fallback={
                    "name": "Luxardo Maraschino",
                    "note": "義大利原廠黑櫻桃利口酒，帶杏仁核苦味",
                },
            ),
        ],
    },

    # ── Paper Plane ──────────────────────────────────────────────
    "paper_plane": {
        "name": "Paper Plane",
        "aliases": ["紙飛機"],
        "description": "等比例波本 + Aperol + Amaro Nonino + 檸檬汁，現代經典",
        "flavor_style": "苦甜辛香平衡",
        "recipe": [
            {"item": "波本威士忌",         "amount": "22ml"},
            {"item": "Aperol",           "amount": "22ml"},
            {"item": "Amaro Nonino",     "amount": "22ml", "note": "草本葡萄渣基底"},
            {"item": "新鮮檸檬汁",         "amount": "22ml"},
        ],
        "glassware": "雞尾酒杯（無冰）",
        "method": "搖盪法（等比例 4 種）",
        "ingredients": [
            _ingredient(
                role=ROLE_BASE, label="波本威士忌",
                recommend_mode=MODE_DYNAMIC,
                categories=["whiskey"],
                suitable_subtypes=["Bourbon"],
                classic_subtypes=["Bourbon"],
                ideal_flavors={"sweet": 55, "spicy": 50, "vanilla": 55, "rich": 60},
                abv_range=(40, 55),
            ),
            _ingredient(
                role=ROLE_MODIFIER, label="苦橙開胃酒",
                recommend_mode=MODE_DYNAMIC_OR_STATIC,
                categories=["liqueurs-bitters"],
                suitable_subtypes=["Amaro"],
                classic_subtypes=["Amaro"],
                ideal_flavors={"bitter": 65, "sweet": 45, "fruity": 60},
                static_fallback={"name": "Aperol"},
            ),
            _ingredient(
                role=ROLE_LIQUEUR, label="草本阿瑪羅",
                recommend_mode=MODE_DYNAMIC_OR_STATIC,
                categories=["liqueurs-bitters"],
                suitable_subtypes=["Amaro"],
                classic_subtypes=["Amaro"],
                ideal_flavors={"herbal": 70, "bitter": 55, "sweet": 40, "spicy": 45},
                static_fallback={
                    "name": "Amaro Nonino Quintessentia",
                    "note": "葡萄渣蒸餾基底，風味較輕盈",
                },
            ),
        ],
    },

    # ── Penicillin ───────────────────────────────────────────────
    "penicillin": {
        "name": "Penicillin",
        "aliases": ["盤尼西林"],
        "description": "調和蘇格蘭威士忌 + 泥煤單一麥芽浮在上層 + 薑汁蜂蜜檸檬",
        "flavor_style": "煙燻蜂蜜薑香",
        "recipe": [
            {"item": "調和蘇格蘭威士忌", "amount": "50ml", "note": "作為基底"},
            {"item": "薑汁蜂蜜糖漿",    "amount": "22ml"},
            {"item": "新鮮檸檬汁",      "amount": "22ml"},
            {"item": "泥煤單一麥芽",    "amount": "15ml", "note": "浮在上層，Islay 單麥為佳"},
        ],
        "glassware": "老式杯（加冰）",
        "method": "搖盪法（基底），浮層用量酒器輕覆",
        "ingredients": [
            _ingredient(
                role=ROLE_BASE, label="調和蘇格蘭威士忌（基底）",
                recommend_mode=MODE_DYNAMIC,
                categories=["whiskey"],
                suitable_subtypes=["Blended"],
                classic_subtypes=["Blended"],
                ideal_flavors={"sweet": 55, "fruity": 45, "rich": 50},
                abv_range=(40, 46),
            ),
            _ingredient(
                role=ROLE_BASE, label="泥煤單一麥芽（浮層）",
                recommend_mode=MODE_DYNAMIC,
                categories=["whiskey"],
                suitable_subtypes=["Single Malt"],
                classic_subtypes=["Single Malt"],
                ideal_flavors={"smoky": 80, "peaty": 85, "salty": 40, "earthy": 50},
                abv_range=(43, 60),
            ),
        ],
    },

    # ── Dark & Stormy ────────────────────────────────────────────
    "dark_and_stormy": {
        "name": "Dark & Stormy",
        "aliases": ["暗黑風暴"],
        "description": "深色蘭姆 + 薑汁啤酒，百慕達傳統飲",
        "flavor_style": "焦糖辛辣",
        "recipe": [
            {"item": "深色蘭姆（Gosling's Black Seal）", "amount": "50ml", "note": "百慕達官方指定"},
            {"item": "薑汁啤酒",                        "amount": "100ml"},
            {"item": "萊姆角",                          "amount": "1 塊", "note": "裝飾"},
        ],
        "glassware": "高球杯（加冰）",
        "method": "直調法（先倒薑汁，蘭姆浮上層）",
        "ingredients": [
            _ingredient(
                role=ROLE_BASE, label="深色/陳年蘭姆",
                recommend_mode=MODE_DYNAMIC,
                categories=["rum"],
                suitable_subtypes=["Dark Rum", "Aged Rum", "Gold Rum"],
                classic_subtypes=["Dark Rum"],
                unsuitable_subtypes=["Silver Rum", "Spiced Rum"],
                ideal_flavors={"rich": 70, "sweet": 60, "vanilla": 55, "fruity": 40},
                abv_range=(37, 50),
            ),
        ],
    },

    # ── French 75 ────────────────────────────────────────────────
    "french_75": {
        "name": "French 75",
        "aliases": ["法式七十五"],
        "description": "琴酒 + 檸檬汁 + 糖 + 香檳，節慶感十足的氣泡調酒",
        "flavor_style": "清新氣泡花香",
        "recipe": [
            {"item": "琴酒",   "amount": "30ml"},
            {"item": "新鮮檸檬汁", "amount": "15ml"},
            {"item": "糖漿",   "amount": "10ml"},
            {"item": "香檳",   "amount": "60ml", "note": "最後補入，Brut 款為佳"},
        ],
        "glassware": "香檳杯或笛型杯",
        "method": "搖盪法（前三種），香檳最後直調補入",
        "ingredients": [
            _ingredient(
                role=ROLE_BASE, label="琴酒",
                recommend_mode=MODE_DYNAMIC,
                categories=["gin"],
                suitable_subtypes=["London Dry Gin", "Modern Gin"],
                classic_subtypes=["London Dry Gin"],
                ideal_flavors={"juniper": 65, "herbal": 55, "floral": 55, "tart": 30},
                abv_range=(40, 47),
            ),
        ],
    },

    # ── Singapore Sling ──────────────────────────────────────────
    "singapore_sling": {
        "name": "Singapore Sling",
        "aliases": ["新加坡司令"],
        "description": "琴酒 + 櫻桃白蘭地 + 君度 + 菠蘿汁等，來自萊佛士酒店的異國長飲",
        "flavor_style": "熱帶果香複雜",
        "recipe": [
            {"item": "琴酒",         "amount": "30ml"},
            {"item": "Heering 櫻桃利口酒", "amount": "15ml"},
            {"item": "君度/Triple Sec", "amount": "7.5ml"},
            {"item": "Bénédictine", "amount": "7.5ml"},
            {"item": "新鮮鳳梨汁",   "amount": "120ml"},
            {"item": "萊姆汁",       "amount": "15ml"},
            {"item": "紅石榴糖漿",   "amount": "10ml"},
            {"item": "Angostura 苦精", "amount": "1 dash"},
        ],
        "glassware": "颶風杯或高球杯（加冰）",
        "method": "搖盪法",
        "ingredients": [
            _ingredient(
                role=ROLE_BASE, label="琴酒",
                recommend_mode=MODE_DYNAMIC,
                categories=["gin"],
                suitable_subtypes=["London Dry Gin"],
                classic_subtypes=["London Dry Gin"],
                ideal_flavors={"juniper": 65, "herbal": 60, "fruity": 35},
                abv_range=(40, 47),
            ),
            _ingredient(
                role=ROLE_LIQUEUR, label="櫻桃利口酒",
                recommend_mode=MODE_DYNAMIC_OR_STATIC,
                categories=["liqueurs-bitters"],
                suitable_subtypes=["Other Liqueurs"],
                classic_subtypes=["Other Liqueurs"],
                ideal_flavors={"sweet": 70, "fruity": 75},
                static_fallback={
                    "name": "Heering Cherry Liqueur",
                    "note": "丹麥傳統櫻桃利口酒，為此酒的標準配方",
                },
            ),
        ],
    },

    # ── Sazerac ──────────────────────────────────────────────────
    "sazerac": {
        "name": "Sazerac",
        "aliases": ["薩澤拉克"],
        "description": "裸麥威士忌 + 苦精 + 艾碧斯漱口，紐奧良最古老的雞尾酒",
        "flavor_style": "辛香草本苦甜",
        "recipe": [
            {"item": "裸麥威士忌",       "amount": "60ml"},
            {"item": "方糖",             "amount": "1 顆"},
            {"item": "Peychaud's 苦精",  "amount": "3 dash"},
            {"item": "Absinthe（艾碧斯）", "amount": "少許", "note": "漱口杯壁後倒掉"},
            {"item": "檸檬皮",           "amount": "1 片",  "note": "擠壓後棄置或裝飾"},
        ],
        "glassware": "老式杯（無冰，預冷）",
        "method": "攪拌法",
        "ingredients": [
            _ingredient(
                role=ROLE_BASE, label="裸麥威士忌",
                recommend_mode=MODE_DYNAMIC,
                categories=["whiskey"],
                suitable_subtypes=["Rye"],
                classic_subtypes=["Rye"],
                ideal_flavors={"spicy": 70, "rich": 60, "bitter": 30, "woody": 40},
                abv_range=(40, 55),
            ),
            _ingredient(
                role=ROLE_BITTER, label="苦精",
                recommend_mode=MODE_STATIC_ONLY,
                ideal_flavors={},
                static_fallback={
                    "name": "Peychaud's Bitters",
                    "usage": "3 dash",
                    "note": "紐奧良特有，八角茴香風味，不可用 Angostura 替代",
                },
            ),
        ],
    },

    # ── Pisco Sour ───────────────────────────────────────────────
    "pisco_sour": {
        "name": "Pisco Sour",
        "aliases": ["皮斯可酸酒"],
        "description": "秘魯/智利皮斯可 + 萊姆汁 + 糖 + 蛋白 + 苦精",
        "flavor_style": "花果酸甜輕盈",
        "recipe": [
            {"item": "Pisco",     "amount": "60ml", "note": "秘魯 Quebranta 最為經典"},
            {"item": "新鮮萊姆汁", "amount": "30ml"},
            {"item": "糖漿",      "amount": "20ml"},
            {"item": "蛋白",      "amount": "1 個"},
            {"item": "Angostura 苦精", "amount": "3 滴", "note": "滴在泡沫上裝飾"},
        ],
        "glassware": "酸酒杯（無冰）",
        "method": "乾搖後加冰再搖",
        "ingredients": [
            _ingredient(
                role=ROLE_BASE, label="Pisco",
                recommend_mode=MODE_DYNAMIC,
                categories=["brandy"],
                suitable_subtypes=["Pisco"],
                classic_subtypes=["Pisco"],
                ideal_flavors={"fruity": 65, "floral": 60, "sweet": 45, "tart": 35},
                abv_range=(38, 48),
            ),
        ],
    },

    # ── Espresso Martini ─────────────────────────────────────────
    "espresso_martini": {
        "name": "Espresso Martini",
        "aliases": ["濃縮咖啡馬丁尼"],
        "description": "伏特加 + 咖啡利口酒 + 濃縮咖啡，提神又優雅的派對飲品",
        "flavor_style": "咖啡苦甜",
        "recipe": [
            {"item": "伏特加",   "amount": "40ml"},
            {"item": "咖啡利口酒", "amount": "20ml", "note": "Mr Black 或 Kahlúa"},
            {"item": "濃縮咖啡", "amount": "30ml", "note": "新鮮萃取，趁熱搖盪"},
            {"item": "咖啡豆",  "amount": "3 顆",  "note": "浮於泡沫上裝飾"},
        ],
        "glassware": "馬丁尼杯（無冰）",
        "method": "搖盪法（用力搖出泡沫）",
        "ingredients": [
            _ingredient(
                role=ROLE_BASE, label="伏特加",
                recommend_mode=MODE_DYNAMIC,
                categories=["vodka"],
                suitable_subtypes=["Unflavored Vodka"],
                classic_subtypes=["Unflavored Vodka"],
                ideal_flavors={"neutral": 75, "sweet": 20},
                abv_range=(37, 45),
            ),
            _ingredient(
                role=ROLE_LIQUEUR, label="咖啡利口酒",
                recommend_mode=MODE_DYNAMIC_OR_STATIC,
                categories=["liqueurs-bitters"],
                suitable_subtypes=["Coffee Liqueurs"],
                classic_subtypes=["Coffee Liqueurs"],
                ideal_flavors={"rich": 70, "sweet": 55, "bitter": 45},
                abv_range=(20, 35),
                static_fallback={
                    "name": "Mr Black Cold Brew Coffee Liqueur",
                    "alternatives": ["Kahlúa（較甜）", "Tia Maria"],
                    "note": "Mr Black 已收錄於 DB（評分 96），優先推薦",
                },
            ),
        ],
    },
}

# ─── 查詢工具函式 ──────────────────────────────────────────────


def get_cocktail(name: str) -> dict | None:
    """依名稱查詢雞尾酒（支援 key、name、aliases 模糊匹配）。"""
    key = name.lower().replace(" ", "_").replace("-", "_")
    if key in COCKTAIL_DB:
        return COCKTAIL_DB[key]

    name_lower = name.lower()
    for cocktail in COCKTAIL_DB.values():
        if cocktail["name"].lower() == name_lower:
            return cocktail
        if any(alias.lower() == name_lower for alias in cocktail.get("aliases", [])):
            return cocktail
    return None


def list_cocktails() -> list[str]:
    """回傳所有支援的雞尾酒名稱。"""
    return [v["name"] for v in COCKTAIL_DB.values()]


def get_dynamic_ingredients(cocktail: dict) -> list[dict]:
    """篩選出可從 DB 動態推薦的成分。"""
    return [
        ing for ing in cocktail["ingredients"]
        if ing["recommend_mode"] in (MODE_DYNAMIC, MODE_DYNAMIC_OR_STATIC)
        and ing["categories"]
    ]
