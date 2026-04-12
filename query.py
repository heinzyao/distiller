#!/usr/bin/env python3
"""
Distiller 資料庫查詢工具

用法:
    python query.py list [篩選條件]
    python query.py search <關鍵字>
    python query.py top [N]
    python query.py info <名稱>
    python query.py stats
    python query.py flavors [篩選條件]
    python query.py export <檔案名>
    python query.py cocktail-top [N]
    python query.py cocktail-search <關鍵字>
    python query.py cocktail-info <名稱>
    python query.py cocktail-stats
    python query.py cocktail-list [篩選條件]
    python query.py cocktail-makeable
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DB_DEFAULT = "distiller.db"

# ---------------------------------------------------------------------------
# 格式化輔助
# ---------------------------------------------------------------------------


def _truncate(text: str, width: int) -> str:
    if not text:
        return ""
    return text[: width - 1] + "…" if len(text) > width else text


def _score_bar(score: int, max_score: int = 100, width: int = 10) -> str:
    if score is None:
        return ""
    filled = round(score / max_score * width)
    return "█" * filled + "░" * (width - filled)


def _print_table(headers: list, rows: list, widths: list = None):
    """簡易表格輸出（不需外部依賴）"""
    if not rows:
        print("（無結果）")
        return

    # 自動計算欄寬
    if not widths:
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(str(cell or "")))
        # 限制最大寬度
        widths = [min(w, 50) for w in widths]

    # 表頭
    header_line = "  ".join(str(h).ljust(w) for h, w in zip(headers, widths))
    print(header_line)
    print("  ".join("─" * w for w in widths))

    # 資料行
    for row in rows:
        cells = []
        for cell, w in zip(row, widths):
            text = str(cell) if cell is not None else ""
            cells.append(_truncate(text, w).ljust(w))
        print("  ".join(cells))


def _connect(db_path: str) -> sqlite3.Connection:
    path = Path(db_path)
    if not path.exists():
        print(
            f"錯誤：資料庫 {db_path} 不存在。請先執行爬蟲：python run.py --mode test --output sqlite"
        )
        sys.exit(1)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# 子命令實作
# ---------------------------------------------------------------------------


def cmd_list(args):
    """列出烈酒，支援多種篩選條件"""
    conn = _connect(args.db)
    conditions, params = [], []

    if args.type:
        conditions.append("spirit_type LIKE ?")
        params.append(f"%{args.type}%")
    if args.country:
        conditions.append("country LIKE ?")
        params.append(f"%{args.country}%")
    if args.brand:
        conditions.append("brand LIKE ?")
        params.append(f"%{args.brand}%")
    if args.min_score is not None:
        conditions.append("expert_score >= ?")
        params.append(args.min_score)
    if args.max_score is not None:
        conditions.append("expert_score <= ?")
        params.append(args.max_score)

    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    sort = (
        args.sort
        if args.sort
        in ("name", "expert_score", "community_score", "abv", "review_count")
        else "expert_score"
    )
    order = "ASC" if args.asc else "DESC"
    limit = args.limit or 20

    sql = f"SELECT name, spirit_type, country, expert_score, community_score, abv FROM spirits{where} ORDER BY {sort} {order} NULLS LAST LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    total = conn.execute(
        f"SELECT COUNT(*) FROM spirits{where}", params[:-1]
    ).fetchone()[0]

    print(f"\n共 {total} 筆符合條件（顯示前 {min(limit, total)} 筆）\n")
    _print_table(
        ["品名", "類型", "產地", "專家", "社群", "ABV"],
        [
            (
                r["name"],
                r["spirit_type"],
                r["country"],
                r["expert_score"],
                r["community_score"],
                r["abv"],
            )
            for r in rows
        ],
        [38, 20, 22, 4, 4, 5],
    )
    conn.close()


def cmd_search(args):
    """模糊搜尋品名、品牌、描述"""
    conn = _connect(args.db)
    keyword = f"%{args.keyword}%"
    sql = """
        SELECT name, spirit_type, brand, country, expert_score
        FROM spirits
        WHERE name LIKE ? OR brand LIKE ? OR description LIKE ?
        ORDER BY expert_score DESC NULLS LAST
        LIMIT ?
    """
    rows = conn.execute(sql, (keyword, keyword, keyword, args.limit or 20)).fetchall()
    print(f'\n搜尋 "{args.keyword}"：找到 {len(rows)} 筆\n')
    _print_table(
        ["品名", "類型", "品牌", "產地", "專家"],
        [
            (r["name"], r["spirit_type"], r["brand"], r["country"], r["expert_score"])
            for r in rows
        ],
        [38, 20, 20, 22, 4],
    )
    conn.close()


def cmd_top(args):
    """顯示評分最高的烈酒"""
    conn = _connect(args.db)
    n = args.n or 10
    sql = """
        SELECT name, spirit_type, country, expert_score, community_score, review_count
        FROM spirits WHERE expert_score IS NOT NULL
        ORDER BY expert_score DESC, community_score DESC
        LIMIT ?
    """
    rows = conn.execute(sql, (n,)).fetchall()
    print(f"\n🏆 評分最高 Top {n}\n")
    data = []
    for i, r in enumerate(rows, 1):
        bar = _score_bar(r["expert_score"])
        data.append(
            (
                f"#{i}",
                r["name"],
                r["spirit_type"],
                r["country"],
                r["expert_score"],
                bar,
                r["review_count"],
            )
        )
    _print_table(
        ["#", "品名", "類型", "產地", "分數", "評分條", "評論數"],
        data,
        [3, 38, 20, 22, 4, 10, 5],
    )
    conn.close()


def cmd_info(args):
    """顯示單筆烈酒的完整資訊"""
    conn = _connect(args.db)
    sql = "SELECT * FROM spirits WHERE name LIKE ? LIMIT 1"
    row = conn.execute(sql, (f"%{args.name}%",)).fetchone()
    if not row:
        print(f'找不到符合 "{args.name}" 的烈酒。')
        conn.close()
        return

    row = dict(row)
    print(f"\n{'═' * 60}")
    print(f"  {row['name']}")
    print(f"{'═' * 60}")
    fields = [
        ("類型", "spirit_type"),
        ("品牌", "brand"),
        ("產地", "country"),
        ("年份", "age"),
        ("ABV", "abv"),
        ("價位", "cost_level"),
        ("桶型", "cask_type"),
        ("專家評分", "expert_score"),
        ("社群評分", "community_score"),
        ("評論數", "review_count"),
        ("評鑑人", "expert_name"),
    ]
    for label, key in fields:
        val = row.get(key)
        if val is not None:
            if key == "expert_score":
                bar = _score_bar(val)
                print(f"  {label}：{val} {bar}")
            elif key == "cost_level":
                print(f"  {label}：{'$' * val}")
            else:
                print(f"  {label}：{val}")

    if row.get("description"):
        print(f"\n  📝 描述：\n  {row['description'][:200]}")
    if row.get("tasting_notes"):
        print(f"\n  👃 品飲筆記：\n  {row['tasting_notes'][:200]}")

    # 風味圖譜
    flavors = conn.execute(
        "SELECT flavor_name, flavor_value FROM flavor_profiles WHERE spirit_id = ? ORDER BY flavor_value DESC",
        (row["id"],),
    ).fetchall()
    if flavors:
        print(f"\n  🎨 風味圖譜：")
        for f in flavors:
            bar = "█" * (f["flavor_value"] // 5) + "░" * (20 - f["flavor_value"] // 5)
            print(f"    {f['flavor_name']:15s} {bar} {f['flavor_value']}")

    print(f"\n  🔗 {row.get('url', '')}")
    print()
    conn.close()


def cmd_stats(args):
    """顯示資料庫統計摘要"""
    conn = _connect(args.db)

    total = conn.execute("SELECT COUNT(*) FROM spirits").fetchone()[0]
    with_score = conn.execute(
        "SELECT COUNT(*) FROM spirits WHERE expert_score IS NOT NULL"
    ).fetchone()[0]
    avg_score = conn.execute(
        "SELECT ROUND(AVG(expert_score), 1) FROM spirits WHERE expert_score IS NOT NULL"
    ).fetchone()[0]
    min_score = conn.execute(
        "SELECT MIN(expert_score) FROM spirits WHERE expert_score IS NOT NULL"
    ).fetchone()[0]
    max_score = conn.execute(
        "SELECT MAX(expert_score) FROM spirits WHERE expert_score IS NOT NULL"
    ).fetchone()[0]

    print(f"\n📊 資料庫統計（{args.db}）")
    print(f"{'─' * 40}")
    print(f"  總筆數：{total}")
    print(f"  有評分：{with_score}（{with_score / total * 100:.0f}%）")
    print(f"  平均分：{avg_score}")
    print(f"  分數區間：{min_score} ~ {max_score}")

    # 類型分布
    print(f"\n  📋 類型分布：")
    types = conn.execute(
        "SELECT spirit_type, COUNT(*) c, ROUND(AVG(expert_score),1) avg FROM spirits GROUP BY spirit_type ORDER BY c DESC"
    ).fetchall()
    _print_table(
        ["類型", "筆數", "平均分"],
        [(r[0], r[1], r[2]) for r in types],
        [30, 5, 6],
    )

    # 產地分布 Top 10
    print(f"\n  🌍 產地分布（Top 10）：")
    countries = conn.execute(
        "SELECT country, COUNT(*) c, ROUND(AVG(expert_score),1) avg FROM spirits WHERE country IS NOT NULL GROUP BY country ORDER BY c DESC LIMIT 10"
    ).fetchall()
    _print_table(
        ["產地", "筆數", "平均分"],
        [(r[0], r[1], r[2]) for r in countries],
        [30, 5, 6],
    )

    # 評分分布
    print(f"\n  📈 評分分布：")
    brackets = [
        ("90-100（傑出）", 90, 101),
        ("80-89 （優良）", 80, 90),
        ("70-79 （普通）", 70, 80),
        ("< 70  （較低）", 0, 70),
    ]
    for label, lo, hi in brackets:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM spirits WHERE expert_score >= ? AND expert_score < ?",
            (lo, hi),
        ).fetchone()[0]
        bar = "█" * (cnt // 5)
        print(f"    {label}  {cnt:>4} {bar}")

    # 最近爬取記錄
    runs = conn.execute(
        "SELECT started_at, total_scraped, total_failed, status FROM scrape_runs ORDER BY id DESC LIMIT 3"
    ).fetchall()
    if runs:
        print(f"\n  🕐 最近爬取記錄：")
        _print_table(
            ["時間", "成功", "失敗", "狀態"],
            [(r[0], r[1], r[2], r[3]) for r in runs],
            [22, 5, 5, 10],
        )

    print()
    conn.close()


def cmd_flavors(args):
    """查詢風味圖譜"""
    conn = _connect(args.db)

    if args.name:
        # 查詢特定風味最高的烈酒
        sql = """
            SELECT s.name, s.spirit_type, fp.flavor_value, s.expert_score
            FROM flavor_profiles fp
            JOIN spirits s ON s.id = fp.spirit_id
            WHERE fp.flavor_name = ?
            AND fp.flavor_value >= ?
            ORDER BY fp.flavor_value DESC
            LIMIT ?
        """
        rows = conn.execute(
            sql, (args.name, args.min_value or 0, args.limit or 15)
        ).fetchall()
        print(f"\n🎨 風味「{args.name}」排行（≥ {args.min_value or 0}）\n")
        data = []
        for r in rows:
            bar = "█" * (r["flavor_value"] // 5)
            data.append(
                (r["name"], r["spirit_type"], r["flavor_value"], bar, r["expert_score"])
            )
        _print_table(
            ["品名", "類型", "值", "強度", "專家"],
            data,
            [38, 20, 3, 20, 4],
        )
    else:
        # 顯示所有風味的平均值
        sql = """
            SELECT flavor_name, COUNT(*) cnt,
                   ROUND(AVG(flavor_value), 1) avg,
                   MAX(flavor_value) max
            FROM flavor_profiles
            GROUP BY flavor_name
            ORDER BY avg DESC
        """
        rows = conn.execute(sql).fetchall()
        print(f"\n🎨 風味維度統計\n")
        data = []
        for r in rows:
            bar = "█" * round(r["avg"] / 5)
            data.append((r["flavor_name"], r["cnt"], r["avg"], r["max"], bar))
        _print_table(
            ["風味", "筆數", "平均", "最高", "平均強度"],
            data,
            [15, 5, 5, 4, 20],
        )

    conn.close()


def cmd_export(args):
    """匯出查詢結果為 CSV"""
    conn = _connect(args.db)
    import pandas as pd

    df = pd.read_sql_query("SELECT * FROM spirits ORDER BY expert_score DESC", conn)
    df.to_csv(args.filename, index=False, encoding="utf-8-sig")
    print(f"✓ 已匯出 {len(df)} 筆資料至 {args.filename}")
    conn.close()


# ---------------------------------------------------------------------------
# Difford's 雞尾酒子命令
# ---------------------------------------------------------------------------

COCKTAIL_DB_DEFAULT = "diffords.db"


def _open_diffords(db_path: str):
    """開啟 DiffordsStorage，若 DB 不存在則印出提示並 exit(1)。"""
    from distiller_scraper.diffords_storage import DiffordsStorage

    if not Path(db_path).exists():
        print(
            f"⚠️ Difford's 資料庫不存在：{db_path}\n"
            "請先執行：uv run python run_diffords.py --mode test"
        )
        sys.exit(1)
    return DiffordsStorage(db_path)


def cmd_cocktail_top(args):
    """顯示評分最高的雞尾酒"""
    storage = _open_diffords(args.cocktail_db)
    try:
        n = args.n or 10
        results = storage.get_top_rated(limit=n)
        print(f"\n🍹 Difford's 評分最高 Top {n}\n")
        if not results:
            print("（無結果）")
            return
        for i, c in enumerate(results, 1):
            rating = c.get("rating_value")
            rating_str = f"{rating:.1f}" if rating is not None else "N/A"
            desc = (c.get("description") or "")[:60]
            print(f"{i}. {c['name']} ({rating_str}) — {desc}")
    finally:
        storage.close()


def cmd_cocktail_search(args):
    """搜尋雞尾酒"""
    storage = _open_diffords(args.cocktail_db)
    try:
        results = storage.search_cocktails(args.keyword)
        print(f'\n搜尋 "{args.keyword}"：找到 {len(results)} 筆\n')
        if not results:
            print("（無結果）")
            return
        for i, c in enumerate(results, 1):
            rating = c.get("rating_value")
            rating_str = f"{rating:.1f}" if rating is not None else "N/A"
            desc = (c.get("description") or "")[:60]
            print(f"{i}. {c['name']} ({rating_str}) — {desc}")
    finally:
        storage.close()


def cmd_cocktail_info(args):
    """顯示雞尾酒完整詳情"""
    storage = _open_diffords(args.cocktail_db)
    try:
        result = storage.get_cocktail_by_name(args.name)
        if not result:
            print(f'找不到符合 "{args.name}" 的雞尾酒。')
            return
        print(f"\n{'═' * 60}")
        print(f"  {result['name']}")
        print(f"{'═' * 60}")
        fields = [
            ("評分", "rating_value"),
            ("評分數", "rating_count"),
            ("ABV", "abv"),
            ("杯型", "glassware"),
            ("裝飾", "garnish"),
            ("準備方式", "prepare"),
            ("卡路里", "calories"),
            ("發布日期", "date_published"),
        ]
        for label, key in fields:
            val = result.get(key)
            if val is not None:
                print(f"  {label}：{val}")
        if result.get("description"):
            print(f"\n  📝 描述：\n  {result['description'][:200]}")
        if result.get("instructions"):
            print(f"\n  📋 作法：\n  {result['instructions'][:300]}")
        if result.get("history"):
            print(f"\n  📖 歷史：\n  {result['history'][:200]}")
        if result.get("review"):
            print(f"\n  ⭐ 評語：\n  {result['review'][:200]}")
        ingredients = result.get("ingredients", [])
        if ingredients:
            print(f"\n  🥃 食材：")
            for ing in ingredients:
                amount = ing.get("amount") or ""
                item = ing.get("item") or ""
                print(f"    • {amount} {item}".strip())
        if result.get("url"):
            print(f"\n  🔗 {result['url']}")
        print()
    finally:
        storage.close()


def cmd_cocktail_stats(args):
    """顯示 Difford's 資料庫統計"""
    storage = _open_diffords(args.cocktail_db)
    try:
        stats = storage.get_stats()
        print(f"\n📊 Difford's 資料庫統計（{args.cocktail_db}）")
        print(f"{'─' * 40}")
        for key, val in stats.items():
            print(f"  {key}：{val}")
        print()
    finally:
        storage.close()


def cmd_cocktail_list(args):
    """雞尾酒列表（支援篩選）"""
    storage = _open_diffords(args.cocktail_db)
    try:
        limit = args.limit or 20
        if args.ingredient:
            results = storage.filter_by_ingredient(args.ingredient, limit=limit)
            print(f"\n🍹 含「{args.ingredient}」的雞尾酒（共 {len(results)} 筆）\n")
        elif args.tag:
            results = storage.filter_by_tag(args.tag, limit=limit)
            print(f"\n🍹 標籤「{args.tag}」的雞尾酒（共 {len(results)} 筆）\n")
        elif args.rating is not None:
            results = storage.filter_by_rating(min_rating=args.rating, limit=limit)
            print(f"\n🍹 評分 ≥ {args.rating} 的雞尾酒（共 {len(results)} 筆）\n")
        else:
            results = storage.get_top_rated(limit=limit)
            print(f"\n🍹 雞尾酒列表（共 {len(results)} 筆）\n")
        if not results:
            print("（無結果）")
            return
        for i, c in enumerate(results, 1):
            rating = c.get("rating_value")
            rating_str = f"{rating:.1f}" if rating is not None else "N/A"
            desc = (c.get("description") or "")[:60]
            print(f"{i}. {c['name']} ({rating_str}) — {desc}")
    finally:
        storage.close()


def cmd_cocktail_makeable(args):
    """根據您的收藏可調製的雞尾酒"""
    from distiller_scraper.diffords_storage import (
        DiffordsStorage,
        get_user_spirit_types,
        load_ingredient_mapping,
    )

    if not Path(args.cocktail_db).exists():
        print(
            f"⚠️ Difford's 資料庫不存在：{args.cocktail_db}\n"
            "請先執行：uv run python run_diffords.py --mode test"
        )
        sys.exit(1)

    user_types = get_user_spirit_types(args.spirits_db)
    mapping = load_ingredient_mapping()

    storage = DiffordsStorage(args.cocktail_db)
    try:
        results = storage.get_makeable_cocktails(user_types, mapping)
        print(f"\n🍹 您可調製的雞尾酒（共 {len(results)} 筆）\n")
        if not results:
            print("（無符合結果，請確認烈酒資料庫與食材映射）")
            return
        for i, c in enumerate(results, 1):
            matched = c.get("matched_ingredients", [])
            matched_str = ", ".join(matched) if matched else "—"
            rating = c.get("rating_value")
            rating_str = f"{rating:.1f}" if rating is not None else "N/A"
            print(f"{i}. {c['name']} ({rating_str}) — 匹配食材：{matched_str}")
    finally:
        storage.close()


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Distiller 資料庫查詢工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例：
  python query.py list                          列出所有（前 20 筆）
  python query.py list --type "Single Malt"     篩選類型
  python query.py list --country Japan          篩選產地
  python query.py list --min-score 90           90 分以上
  python query.py search Hibiki                 搜尋關鍵字
  python query.py top 10                        評分 Top 10
  python query.py info "Highland Park"          查看完整資訊
  python query.py stats                         資料庫統計
  python query.py flavors                       風味維度總覽
  python query.py flavors --name smoky          最煙燻的烈酒
  python query.py export output.csv             匯出 CSV
        """,
    )
    parser.add_argument(
        "--db", default=DB_DEFAULT, help=f"資料庫路徑（預設：{DB_DEFAULT}）"
    )

    sub = parser.add_subparsers(dest="command", help="查詢子命令")

    # list
    p_list = sub.add_parser("list", help="列出烈酒（支援篩選）")
    p_list.add_argument("--type", help="類型篩選（模糊匹配）")
    p_list.add_argument("--country", help="產地篩選（模糊匹配）")
    p_list.add_argument("--brand", help="品牌篩選（模糊匹配）")
    p_list.add_argument("--min-score", type=int, help="最低專家評分")
    p_list.add_argument("--max-score", type=int, help="最高專家評分")
    p_list.add_argument(
        "--sort", default="expert_score", help="排序欄位（預設：expert_score）"
    )
    p_list.add_argument("--asc", action="store_true", help="升序排列")
    p_list.add_argument("--limit", type=int, default=20, help="顯示筆數（預設：20）")

    # search
    p_search = sub.add_parser("search", help="模糊搜尋品名、品牌、描述")
    p_search.add_argument("keyword", help="搜尋關鍵字")
    p_search.add_argument("--limit", type=int, default=20, help="顯示筆數")

    # top
    p_top = sub.add_parser("top", help="評分最高的烈酒")
    p_top.add_argument(
        "n", nargs="?", type=int, default=10, help="顯示筆數（預設：10）"
    )

    # info
    p_info = sub.add_parser("info", help="查看單筆烈酒完整資訊")
    p_info.add_argument("name", help="烈酒名稱（模糊匹配）")

    # stats
    sub.add_parser("stats", help="資料庫統計摘要")

    # flavors
    p_flavors = sub.add_parser("flavors", help="風味圖譜查詢")
    p_flavors.add_argument("--name", help="風味名稱（如 smoky, sweet, peaty）")
    p_flavors.add_argument("--min-value", type=int, default=0, help="最低風味值")
    p_flavors.add_argument("--limit", type=int, default=15, help="顯示筆數")

    # export
    p_export = sub.add_parser("export", help="匯出為 CSV")
    p_export.add_argument("filename", help="輸出檔名")

    # cocktail-top
    p_ctop = sub.add_parser("cocktail-top", help="評分最高的雞尾酒")
    p_ctop.add_argument("n", nargs="?", type=int, default=10, help="數量 (預設 10)")
    p_ctop.add_argument(
        "--cocktail-db",
        default=COCKTAIL_DB_DEFAULT,
        help=f"Difford's DB 路徑（預設：{COCKTAIL_DB_DEFAULT}）",
    )

    # cocktail-search
    p_csearch = sub.add_parser("cocktail-search", help="搜尋雞尾酒")
    p_csearch.add_argument("keyword", help="關鍵字")
    p_csearch.add_argument(
        "--cocktail-db",
        default=COCKTAIL_DB_DEFAULT,
        help=f"Difford's DB 路徑（預設：{COCKTAIL_DB_DEFAULT}）",
    )

    # cocktail-info
    p_cinfo = sub.add_parser("cocktail-info", help="雞尾酒完整詳情")
    p_cinfo.add_argument("name", help="雞尾酒名稱")
    p_cinfo.add_argument(
        "--cocktail-db",
        default=COCKTAIL_DB_DEFAULT,
        help=f"Difford's DB 路徑（預設：{COCKTAIL_DB_DEFAULT}）",
    )

    # cocktail-stats
    p_cstats = sub.add_parser("cocktail-stats", help="Difford's 資料庫統計")
    p_cstats.add_argument(
        "--cocktail-db",
        default=COCKTAIL_DB_DEFAULT,
        help=f"Difford's DB 路徑（預設：{COCKTAIL_DB_DEFAULT}）",
    )

    # cocktail-list
    p_clist = sub.add_parser("cocktail-list", help="雞尾酒列表（支援篩選）")
    p_clist.add_argument("--ingredient", help="按材料篩選")
    p_clist.add_argument("--tag", help="按標籤篩選")
    p_clist.add_argument("--rating", type=float, help="最低評分")
    p_clist.add_argument("--limit", type=int, default=20, help="數量上限")
    p_clist.add_argument(
        "--cocktail-db",
        default=COCKTAIL_DB_DEFAULT,
        help=f"Difford's DB 路徑（預設：{COCKTAIL_DB_DEFAULT}）",
    )

    # cocktail-makeable
    p_cmake = sub.add_parser("cocktail-makeable", help="根據您的收藏可調製的雞尾酒")
    p_cmake.add_argument("--spirits-db", default="distiller.db", help="烈酒 DB 路徑")
    p_cmake.add_argument(
        "--cocktail-db",
        default=COCKTAIL_DB_DEFAULT,
        help=f"Difford's DB 路徑（預設：{COCKTAIL_DB_DEFAULT}）",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        "list": cmd_list,
        "search": cmd_search,
        "top": cmd_top,
        "info": cmd_info,
        "stats": cmd_stats,
        "flavors": cmd_flavors,
        "export": cmd_export,
        "cocktail-top": cmd_cocktail_top,
        "cocktail-search": cmd_cocktail_search,
        "cocktail-info": cmd_cocktail_info,
        "cocktail-stats": cmd_cocktail_stats,
        "cocktail-list": cmd_cocktail_list,
        "cocktail-makeable": cmd_cocktail_makeable,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
