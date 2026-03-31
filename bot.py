#!/usr/bin/env python3

"""
Distiller LINE Bot

收到 LINE 訊息後查詢 SQLite 資料庫並回覆結果。

啟動方式：
    python bot.py

本機開發需透過 ngrok 建立公開 URL：
    ngrok http 5000
    → 將 Webhook URL 設定於 LINE Developers Console

支援指令（直接在 LINE 傳送）：
    top [N]           評分 Top N（預設 10）
    搜尋 <關鍵字>     搜尋品名、品牌、描述
    詳情 <名稱>       單筆完整資訊（含風味圖譜）
    統計              資料庫統計摘要
    風味              所有風味維度排行
    風味 <名稱>       特定風味最強排行
    列表              列出所有（前 10 筆）
    列表 <產地>       依產地篩選
    列表 <產地> <分數> 依產地與最低分數篩選
    說明              顯示指令說明
"""

import base64
import hashlib
import hmac
import logging
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import cast


import requests
from dotenv import load_dotenv
from flask import Flask, abort, request

_ = load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# GCS 設定：設定 GCS_BUCKET 時啟用雲端模式，否則維持本機行為
GCS_BUCKET = os.getenv("GCS_BUCKET", "")
GCS_DB_BLOB = os.getenv("GCS_DB_BLOB", "distiller.db")

LINE_TOKEN_URL = "https://api.line.me/v2/oauth/accessToken"
LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"
DB_DEFAULT = "distiller.db"
MSG_LIMIT = 4900  # LINE 單則訊息字元上限（官方上限 5000，保留 100 字元緩衝）

# 視覺元素：統一的分隔線與獎牌圖示，讓 LINE 訊息格式一致且易讀
_SEP = "━" * 16  # 主要分隔線（粗）
_SEP_LIGHT = "─" * 16  # 次要分隔線（細）
_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}  # Top 3 排行獎牌

# Access Token 快取：避免每次 Webhook 請求都重新取得 Token
# 結構：{"token": str, "expires_at": float（UNIX timestamp）}
# 設計理由：LINE Channel Access Token 有效期 30 天，但短期 token 有效期約 30 天
# 此處使用 23 小時 TTL（82800 秒），在到期前 60 秒自動更新（_get_cached_token 邏輯）
_token_cache: dict[str, str | float] = {}

# 爬蟲執行狀態：追蹤背景執行的爬蟲進程
_scrape_lock = threading.Lock()
_scrape_state: dict = {
    "running": False,
    "mode": None,
    "started_at": None,
}


# ---------------------------------------------------------------------------
# LINE API 輔助
# ---------------------------------------------------------------------------


def _get_access_token(channel_id: str, channel_secret: str) -> str | None:
    """用 Channel ID + Secret 取得短期 Access Token。"""
    try:
        resp = requests.post(
            LINE_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": channel_id,
                "client_secret": channel_secret,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                token = data.get("access_token")
                if isinstance(token, str):
                    return token
            return None
        logger.warning("Token 取得失敗：%s", resp.text)
        return None
    except requests.RequestException as exc:
        logger.error("Token 請求失敗：%s", exc)
        return None


def _get_cached_token(channel_id: str, channel_secret: str) -> str | None:
    """取得有效的 Access Token（優先使用快取，逾期前 60 秒自動更新）。"""
    now = time.time()
    token = _token_cache.get("token")
    expires_at = _token_cache.get("expires_at", 0.0)
    if isinstance(token, str) and isinstance(expires_at, (int, float)):
        if now < expires_at - 60:
            return token
    token = _get_access_token(channel_id, channel_secret)
    if token:
        _token_cache["token"] = token
        _token_cache["expires_at"] = now + 82800  # 23 小時 TTL
    return token


def _verify_signature(body: bytes, signature: str, channel_secret: str) -> bool:
    """驗證 LINE Webhook 簽名（HMAC-SHA256）。"""
    digest = hmac.new(channel_secret.encode(), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode() == signature


def _reply(reply_token: str, text: str, access_token: str) -> bool:
    """透過 Reply API 回覆訊息（自動拆分超長訊息，最多 5 則）。"""
    chunks = [text[i : i + MSG_LIMIT] for i in range(0, len(text), MSG_LIMIT)][:5]
    messages = [{"type": "text", "text": chunk} for chunk in chunks]
    try:
        resp = requests.post(
            LINE_REPLY_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={"replyToken": reply_token, "messages": messages},
            timeout=10,
        )
        if resp.status_code != 200:
            logger.warning("Reply 失敗：%s %s", resp.status_code, resp.text[:200])
            return False
        return True
    except requests.RequestException as exc:
        logger.error("Reply 請求失敗：%s", exc)
        return False


def _start_scraper_thread(mode: str, db_path: str) -> None:
    """在背景執行緒中啟動爬蟲，完成後由 run.py --notify-line 自動推播通知。"""
    run_py = str(Path(__file__).parent / "run.py")
    cmd = [
        sys.executable,
        run_py,
        "--mode",
        mode,
        "--output",
        "sqlite",
        "--db-path",
        db_path,
        "--notify-line",
    ]

    def _run() -> None:
        with _scrape_lock:
            _scrape_state["running"] = True
            _scrape_state["mode"] = mode
            _scrape_state["started_at"] = datetime.now().isoformat(timespec="seconds")
        try:
            subprocess.run(cmd, capture_output=False)
        finally:
            with _scrape_lock:
                _scrape_state["running"] = False
                _scrape_state["mode"] = None

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def _start_scraper_cloud_run(mode: str) -> None:
    """觸發 Cloud Run Job 執行爬蟲（Cloud Run 環境專用）。"""
    project = os.getenv("GOOGLE_CLOUD_PROJECT", os.getenv("GCLOUD_PROJECT", ""))
    region = os.getenv("CLOUD_RUN_REGION", "asia-east1")
    job_name = os.getenv("SCRAPER_JOB_NAME", "distiller-scraper")

    from google.cloud import run_v2  # type: ignore[import]

    client = run_v2.JobsClient()
    name = f"projects/{project}/locations/{region}/jobs/{job_name}"
    overrides = run_v2.RunJobRequest.Overrides(
        container_overrides=[
            run_v2.RunJobRequest.Overrides.ContainerOverride(
                args=["--mode", mode, "--output", "sqlite", "--use-api", "--notify-line"]
            )
        ]
    )
    client.run_job(request=run_v2.RunJobRequest(name=name, overrides=overrides))
    logger.info("Cloud Run Job 已觸發：%s (mode=%s)", name, mode)


def _start_scraper(mode: str, db_path: str) -> None:
    """啟動爬蟲：Cloud Run 環境使用 Jobs API，本機使用 subprocess 執行緒。"""
    if GCS_BUCKET and os.getenv("GOOGLE_CLOUD_PROJECT"):
        _start_scraper_cloud_run(mode)
        with _scrape_lock:
            _scrape_state["running"] = True
            _scrape_state["mode"] = mode
            _scrape_state["started_at"] = datetime.now().isoformat(timespec="seconds")
    else:
        _start_scraper_thread(mode, db_path)


def _ensure_db_from_gcs(db_path: str) -> bool:
    """如果資料庫不存在且設定了 GCS_BUCKET，嘗試從 GCS 下載。"""
    if Path(db_path).exists():
        return True
    if not GCS_BUCKET:
        return False
    from distiller_scraper import gcs_storage

    logger.info("資料庫不存在，嘗試從 GCS 下載：%s", db_path)
    return gcs_storage.download_db(GCS_BUCKET, GCS_DB_BLOB, db_path)


# ---------------------------------------------------------------------------
# 資料庫查詢（回傳字串，不 print）
# ---------------------------------------------------------------------------


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _score_bar(score: int | None, width: int = 8) -> str:
    if score is None:
        return ""
    filled = round(score / 100 * width)
    return "█" * filled + "░" * (width - filled)


def _fmt_score(score_value: int | float | None) -> str:
    bar = _score_bar(
        int(score_value) if isinstance(score_value, (int, float)) else None
    )
    return f"{bar} {score_value}分" if score_value else "無評分"


def fmt_top(db_path: str, n: int = 10) -> str:
    conn = _connect(db_path)
    rows = cast(
        list[sqlite3.Row],
        conn.execute(
            "SELECT name, spirit_type, country, expert_score FROM spirits "
            "WHERE expert_score IS NOT NULL ORDER BY expert_score DESC LIMIT ?",
            (n,),
        ).fetchall(),
    )
    rows = [dict(r) for r in rows]
    conn.close()
    if not rows:
        return "資料庫尚無資料。"
    lines: list[str] = [f"🏆 評分 Top {n}", _SEP]
    for i, r in enumerate(rows, 1):
        score = r.get("expert_score")
        bar = _score_bar(int(score) if isinstance(score, (int, float)) else None)
        rank = _MEDALS.get(i, f"{i:>2}.")
        lines.append(f"{rank} {r['name']}")
        lines.append(f"   {r['spirit_type']} | {r['country']}")
        lines.append(f"   {bar} {r['expert_score']}分")
        lines.append("")
    return "\n".join(lines)


def fmt_search(db_path: str, keyword: str, limit: int = 10) -> str:
    conn = _connect(db_path)
    kw = f"%{keyword}%"
    rows = cast(
        list[sqlite3.Row],
        conn.execute(
            "SELECT name, spirit_type, country, expert_score FROM spirits "
            "WHERE name LIKE ? OR brand LIKE ? OR description LIKE ? "
            "ORDER BY expert_score DESC NULLS LAST LIMIT ?",
            (kw, kw, kw, limit),
        ).fetchall(),
    )
    rows = [dict(r) for r in rows]
    conn.close()
    if not rows:
        return f"找不到符合「{keyword}」的烈酒。"
    lines: list[str] = [f"🔍 搜尋「{keyword}」：{len(rows)} 筆", _SEP_LIGHT]
    for r in rows:
        score = _fmt_score(r.get("expert_score"))
        lines.append(f"・{r['name']}")
        lines.append(f"  {r['spirit_type']} | {r['country']}")
        lines.append(f"  {score}")
        lines.append("")
    return "\n".join(lines)


def fmt_info(db_path: str, name: str) -> str:
    conn = _connect(db_path)
    row = conn.execute(
        "SELECT * FROM spirits WHERE name LIKE ? LIMIT 1", (f"%{name}%",)
    ).fetchone()
    if not row:
        conn.close()
        return f"找不到符合「{name}」的烈酒。"
    row = dict(row)
    cost_level = row.get("cost_level")
    if isinstance(cost_level, int):
        price_text = "$" * cost_level
    else:
        price_text = "—"
    score_value = row.get("expert_score")
    score_text = score_value if isinstance(score_value, (int, float)) else "—"
    score_bar = _score_bar(
        int(score_value) if isinstance(score_value, (int, float)) else None
    )
    lines: list[str] = [
        f"🥃 {row['name']}",
        _SEP,
        "",
        f"類型　{row.get('spirit_type') or '—'}",
        f"品牌　{row.get('brand') or '—'}",
        f"產地　{row.get('country') or '—'}",
        f"年份　{row.get('age') or '—'}",
        f"ABV 　{row.get('abv') or '—'}%",
        f"價位　{price_text}",
        "",
        f"專家評分　{score_text} {score_bar}",
        f"社群評分　{row.get('community_score') or '—'}",
        f"評論數　　{row.get('review_count') or '—'}",
    ]
    tasting_notes = row.get("tasting_notes")
    if isinstance(tasting_notes, str) and tasting_notes:
        lines.append("")
        lines.append(f"👃 {tasting_notes[:150]}")

    flavors = cast(
        list[sqlite3.Row],
        conn.execute(
            "SELECT flavor_name, flavor_value FROM flavor_profiles "
            "WHERE spirit_id = ? ORDER BY flavor_value DESC LIMIT 8",
            (row["id"],),
        ).fetchall(),
    )
    flavors = [dict(f) for f in flavors]
    conn.close()
    if flavors:
        lines.append("")
        lines.append("🎨 風味圖譜")
        lines.append(_SEP_LIGHT)
        for f in flavors:
            value = f.get("flavor_value", 0)
            bar = _score_bar(int(value), width=6)
            pct = f"{int(value)}%"
            lines.append(f"  {f['flavor_name']}  {bar} {pct}")
    return "\n".join(lines)


def fmt_stats(db_path: str) -> str:
    conn = _connect(db_path)
    total = conn.execute("SELECT COUNT(*) FROM spirits").fetchone()[0]
    avg = conn.execute(
        "SELECT ROUND(AVG(expert_score),1) FROM spirits WHERE expert_score IS NOT NULL"
    ).fetchone()[0]
    hi = conn.execute("SELECT MAX(expert_score) FROM spirits").fetchone()[0]
    lo = conn.execute(
        "SELECT MIN(expert_score) FROM spirits WHERE expert_score IS NOT NULL"
    ).fetchone()[0]
    types = cast(
        list[sqlite3.Row],
        conn.execute(
            "SELECT spirit_type, COUNT(*) c FROM spirits GROUP BY spirit_type ORDER BY c DESC LIMIT 6"
        ).fetchall(),
    )
    countries = cast(
        list[sqlite3.Row],
        conn.execute(
            "SELECT country, COUNT(*) c FROM spirits WHERE country IS NOT NULL GROUP BY country ORDER BY c DESC LIMIT 5"
        ).fetchall(),
    )
    types = [tuple(r) for r in types]
    countries = [tuple(r) for r in countries]
    conn.close()

    lines: list[str] = [
        "📊 資料庫統計",
        _SEP,
        "",
        f"  總筆數　　{total}",
        f"  平均分　　{avg}",
        f"  分數區間　{lo} ~ {hi}",
        "",
        "📋 主要類型",
        _SEP_LIGHT,
    ]
    for r in types:
        lines.append(f"  {r[0]}　{r[1]}筆")
    lines.append("")
    lines.append("🌍 主要產地")
    lines.append(_SEP_LIGHT)
    for r in countries:
        lines.append(f"  {r[0]}　{r[1]}筆")
    return "\n".join(lines)


def fmt_flavors(db_path: str, flavor_name: str | None = None, limit: int = 10) -> str:
    conn = _connect(db_path)
    if flavor_name:
        rows = cast(
            list[sqlite3.Row],
            conn.execute(
                "SELECT s.name, fp.flavor_value, s.expert_score "
                "FROM flavor_profiles fp JOIN spirits s ON s.id = fp.spirit_id "
                "WHERE fp.flavor_name = ? ORDER BY fp.flavor_value DESC LIMIT ?",
                (flavor_name, limit),
            ).fetchall(),
        )
        rows = [dict(r) for r in rows]
        conn.close()
        if not rows:
            return f"找不到風味「{flavor_name}」的資料。"
        lines: list[str] = [f"🎨 風味「{flavor_name}」排行", _SEP]
        for i, r in enumerate(rows, 1):
            value = r.get("flavor_value", 0)
            bar = _score_bar(int(value), width=6)
            pct = f"{int(value)}%"
            lines.append(f"{i:>2}. {r['name']}")
            lines.append(f"    {bar} {pct} | 專家 {r['expert_score']}分")
            lines.append("")
        return "\n".join(lines)
    else:
        rows = cast(
            list[sqlite3.Row],
            conn.execute(
                "SELECT flavor_name, ROUND(AVG(flavor_value),0) avg "
                "FROM flavor_profiles GROUP BY flavor_name ORDER BY avg DESC"
            ).fetchall(),
        )
        rows = [dict(r) for r in rows]
        conn.close()
        lines: list[str] = ["🎨 風味維度平均值", _SEP]
        for r in rows:
            avg_value = r.get("avg", 0)
            bar = _score_bar(int(avg_value), width=6)
            pct = f"{int(avg_value)}%"
            lines.append(f"  {r['flavor_name']}  {bar} {pct}")
        return "\n".join(lines)


def fmt_list(
    db_path: str,
    country: str | None = None,
    min_score: int | None = None,
    limit: int = 10,
) -> str:
    conn = _connect(db_path)
    conds: list[str] = []
    params: list[object] = []
    if country:
        conds.append("country LIKE ?")
        params.append(f"%{country}%")
    if min_score is not None:
        conds.append("expert_score >= ?")
        params.append(min_score)
    where = " WHERE " + " AND ".join(conds) if conds else ""
    total = conn.execute(f"SELECT COUNT(*) FROM spirits{where}", params).fetchone()[0]
    params.append(limit)
    rows = cast(
        list[sqlite3.Row],
        conn.execute(
            f"SELECT name, spirit_type, country, expert_score FROM spirits{where} "
            f"ORDER BY expert_score DESC NULLS LAST LIMIT ?",
            params,
        ).fetchall(),
    )
    rows = [dict(r) for r in rows]
    conn.close()
    if not rows:
        return "找不到符合條件的烈酒。"
    title_parts = []
    if country:
        title_parts.append(country)
    if min_score:
        title_parts.append(f"{min_score}分以上")
    title = "・".join(title_parts) if title_parts else "全部"
    lines: list[str] = [f"📋 烈酒列表（{title}，共 {total} 筆）", _SEP_LIGHT]
    for r in rows:
        score = _fmt_score(r.get("expert_score"))
        lines.append(f"・{r['name']}")
        lines.append(f"  {r['spirit_type']} | {r['country']}")
        lines.append(f"  {score}")
        lines.append("")
    if total > limit:
        lines.append(f"（顯示前 {limit} 筆，共 {total} 筆）")
    return "\n".join(lines)


def fmt_run_status() -> str:
    """回傳爬蟲目前執行狀態。"""
    with _scrape_lock:
        running = _scrape_state.get("running", False)
        mode = _scrape_state.get("mode")
        started_at = _scrape_state.get("started_at")
    if running:
        elapsed_str = "—"
        if started_at:
            try:
                elapsed = datetime.now() - datetime.fromisoformat(started_at)
                m, s = divmod(int(elapsed.total_seconds()), 60)
                elapsed_str = f"{m} 分 {s} 秒"
            except (ValueError, TypeError):
                pass
        return f"🔄 爬蟲執行中\n模式：{mode}\n開始時間：{started_at}\n已執行：{elapsed_str}"
    return "💤 目前無爬蟲執行中"


def fmt_cocktail(db_path: str, cocktail_query: str, pref_text: str | None) -> str:
    """雞尾酒多成分推薦，整合 CocktailRecommender。"""
    from distiller_scraper.cocktail_db import get_cocktail, list_cocktails
    from distiller_scraper.recommender import CocktailRecommender, format_recommendation

    cocktail = get_cocktail(cocktail_query)
    # 若查無結果且有偏好文字，嘗試將「酒名 + 偏好文字」合起來當酒名
    # 處理如 "cocktail Old Fashioned" 被拆成 name="Old", pref="Fashioned" 的情況
    if cocktail is None and pref_text:
        full_name = f"{cocktail_query} {pref_text}"
        cocktail = get_cocktail(full_name)
        if cocktail is not None:
            cocktail_query = full_name
            pref_text = None

    if cocktail is None:
        supported = "、".join(list_cocktails())
        return (
            f"❓ 找不到「{cocktail_query}」的配方。\n\n"
            f"目前支援：\n{supported}\n\n"
            "傳送「雞尾酒 清單」查看完整列表。"
        )

    # 解析偏好文字為風味向量（簡單關鍵字對應）
    user_flavor_prefs = _parse_flavor_prefs(pref_text) if pref_text else None

    with CocktailRecommender(db_path) as rec:
        result = rec.recommend(
            cocktail_query,
            user_flavor_prefs=user_flavor_prefs,
            top_k=3,
        )

    if result is None:
        return "⚠️ 推薦時發生錯誤，請稍後再試。"

    text = format_recommendation(result)

    if pref_text:
        text += f"\n\n💬 根據您的偏好「{pref_text}」調整排序"

    return text


def _parse_flavor_prefs(pref_text: str) -> dict[str, float] | None:
    """將自然語言偏好文字轉換為風味向量（關鍵字比對）。"""
    _KEYWORD_MAP: dict[str, dict[str, float]] = {
        "煙燻": {"smoky": 80, "peaty": 60},
        "泥煤": {"peaty": 85, "smoky": 70, "earthy": 50},
        "花香": {"floral": 80, "fruity": 50},
        "果香": {"fruity": 80, "floral": 40, "sweet": 50},
        "草本": {"herbal": 80, "juniper": 60},
        "辛香": {"spicy": 80, "herbal": 50},
        "甜": {"sweet": 75, "vanilla": 55},
        "不甜": {"sweet": 10, "tart": 40},
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
    }

    merged: dict[str, float] = {}
    pref_lower = pref_text.lower()
    for keyword, flavors in _KEYWORD_MAP.items():
        if keyword in pref_lower:
            for k, v in flavors.items():
                merged[k] = max(merged.get(k, 0.0), v)

    return merged if merged else None


def fmt_cocktail_list() -> str:
    """列出所有支援的雞尾酒。"""
    from distiller_scraper.cocktail_db import COCKTAIL_DB

    lines = ["🍹 支援的經典雞尾酒", _SEP, ""]
    for cocktail in COCKTAIL_DB.values():
        aliases = "、".join(cocktail.get("aliases", []))
        alias_str = f"（{aliases}）" if aliases else ""
        lines.append(f"• {cocktail['name']}{alias_str}")
        lines.append(f"  {cocktail['flavor_style']} — {cocktail['description'][:30]}…")
    lines.append("")
    lines.append("用法：雞尾酒 <酒名> [偏好描述]")
    lines.append("例：雞尾酒 Negroni 我喜歡苦味草本")
    return "\n".join(lines)


def fmt_help() -> str:
    return "\n".join(
        [
            "🥃 Distiller 查詢指令",
            _SEP,
            "",
            "🔎 搜尋與瀏覽",
            "top [N]",
            "  評分最高前 N 筆（預設 10）",
            "搜尋 <關鍵字>",
            "  搜尋品名、品牌、描述",
            "詳情 <名稱>",
            "  完整資訊與風味圖譜",
            "列表 [產地] [分數]",
            "  例：列表 Japan｜列表 Scotland 95",
            "",
            "📊 統計與風味",
            "統計  資料庫統計摘要",
            "風味 [名稱]  維度排行",
            "  例：風味 smoky",
            "",
            "",
            "🍹 雞尾酒推薦",
            "雞尾酒 <酒名> [偏好]",
            "  依雞尾酒推薦基酒與利口酒",
            "  例：雞尾酒 Negroni",
            "  例：雞尾酒 Martini 喜歡花香清爽",
            "  例：雞尾酒 清單  列出支援酒款",
            "",
            "🤖 爬蟲指令（僅授權使用者）",
            "執行 test / medium / full",
            "  啟動爬蟲（完成後推播通知）",
            "執行狀態",
            "  查看目前執行狀態",
            "❓ 說明  顯示本說明",
        ]
    )


# ---------------------------------------------------------------------------
# 指令解析
# ---------------------------------------------------------------------------


def parse_command(text: str) -> tuple[str, list[str | int | None]]:
    """將 LINE 訊息解析為 (command, args)。"""
    text = text.strip()
    lower = text.lower()

    if lower in ("說明", "help", "指令", "?", "？"):
        return "help", []

    if lower in ("統計", "stats", "總覽"):
        return "stats", []

    if lower in ("風味", "flavors", "flavor"):
        return "flavors", []

    m = re.match(r"^(風味|flavor[s]?)\s+(.+)$", text, re.IGNORECASE)
    if m:
        return "flavors", [m.group(2).strip()]

    m = re.match(r"^(top|排行)\s*(\d+)?$", lower)
    if m:
        n = int(m.group(2)) if m.group(2) else 10
        return "top", [min(n, 20)]

    m = re.match(r"^(搜尋|search|找)\s+(.+)$", text, re.IGNORECASE)
    if m:
        return "search", [m.group(2).strip()]

    m = re.match(r"^(詳情|info|查)\s+(.+)$", text, re.IGNORECASE)
    if m:
        return "info", [m.group(2).strip()]

    # 列表 [產地] [分數]
    m = re.match(r"^(列表|list)(\s+(.+?))?(\s+(\d{2,3}))?$", text, re.IGNORECASE)
    if m:
        country = m.group(3).strip() if m.group(3) else None
        score = int(m.group(5)) if m.group(5) else None
        # 如果第三組只是數字，視為分數
        if country and country.isdigit():
            score = int(country)
            country = None
        return "list", [country, score]

    # 雞尾酒推薦（支援：雞尾酒 <酒名>、雞尾酒 <酒名> <偏好>、調酒 <酒名>）
    m = re.match(r"^(雞尾酒|調酒|cocktail)\s+(清單|list)$", text, re.IGNORECASE)
    if m:
        return "cocktail_list", []

    m = re.match(r"^(雞尾酒|調酒|cocktail)\s+(.+)$", text, re.IGNORECASE)
    if m:
        rest = m.group(2).strip()
        # 嘗試拆分「酒名 偏好描述」：偏好以空白隔開，兩字以上才算偏好
        parts = rest.split(None, 1)
        cocktail_name = parts[0]
        pref_text = parts[1] if len(parts) > 1 else None
        return "cocktail", [cocktail_name, pref_text]

    # 執行爬蟲
    m = re.match(r"^(執行|run)\s+(test|medium|full)$", text, re.IGNORECASE)
    if m:
        return "run_scrape", [m.group(2).lower()]

    if lower in ("執行狀態", "run status", "爬蟲狀態"):
        return "run_status", []

    return "unknown", [text]


# ---------------------------------------------------------------------------
# Flask App
# ---------------------------------------------------------------------------


def create_app(
    db_path: str = DB_DEFAULT,
    channel_secret: str | None = None,
    channel_id: str | None = None,
) -> Flask:
    app = Flask(__name__)
    _channel_secret = channel_secret or os.getenv("LINE_CHANNEL_SECRET", "")
    _channel_id = channel_id or os.getenv("LINE_CHANNEL_ID", "")

    @app.route("/health", methods=["GET"])
    def health():
        return {
            "status": "ok",
            "db_exists": Path(db_path).exists(),
            "token_cached": _token_cache.get("token") is not None,
        }, 200

    @app.route("/webhook", methods=["POST"])
    def webhook():
        body = request.get_data()
        data = request.get_json(silent=True)

        if not data or not data.get("events"):
            if body and data is None:
                logger.warning("收到無法解析的 JSON")
            return "OK", 200

        signature = request.headers.get("X-Line-Signature", "")
        if not _verify_signature(body, signature, _channel_secret):
            logger.warning("簽名驗證失敗（來源 IP：%s）", request.remote_addr)
            abort(400)

        for event in data.get("events", []):
            if event.get("type") != "message":
                continue
            if event.get("message", {}).get("type") != "text":
                continue

            reply_token = event.get("replyToken", "")
            user_text = event["message"]["text"]
            logger.info("收到訊息：%s", user_text)

            user_id = event.get("source", {}).get("userId", "")

            response = _handle(user_text, db_path, user_id=user_id)

            token = _get_cached_token(_channel_id, _channel_secret)
            if token:
                if not _reply(reply_token, response, token):
                    logger.error("回覆訊息失敗")
            else:
                logger.error("無法取得 Access Token，無法回覆")

        return "OK", 200

    return app


def _handle(text: str, db_path: str, user_id: str | None = None) -> str:
    """解析指令並回傳回覆文字。"""
    if not Path(db_path).exists():
        if not _ensure_db_from_gcs(db_path):
            logger.warning("資料庫不存在：%s", db_path)
            return "⚠️ 資料庫不存在，請先執行：python run.py --mode test --output sqlite"

    command, args = parse_command(text)

    try:
        if command == "help":
            return fmt_help()
        elif command == "top":
            raw_n = args[0] if args else 10
            if isinstance(raw_n, int):
                n = raw_n
            elif isinstance(raw_n, str) and raw_n.isdigit():
                n = int(raw_n)
            else:
                n = 10
            return fmt_top(db_path, n)
        elif command == "search":
            keyword = str(args[0])
            return fmt_search(db_path, keyword)
        elif command == "info":
            name = str(args[0])
            return fmt_info(db_path, name)
        elif command == "stats":
            return fmt_stats(db_path)
        elif command == "flavors":
            flavor_name = str(args[0]) if args else None
            return fmt_flavors(db_path, flavor_name)
        elif command == "list":
            raw_country = args[0] if len(args) > 0 else None
            country = str(raw_country) if raw_country is not None else None
            raw_score = args[1] if len(args) > 1 else None
            if isinstance(raw_score, int):
                min_score = raw_score
            elif isinstance(raw_score, str) and raw_score.isdigit():
                min_score = int(raw_score)
            else:
                min_score = None
            return fmt_list(db_path, country, min_score)
        elif command == "cocktail":
            cocktail_name = str(args[0]) if args[0] else ""
            pref_text = str(args[1]) if len(args) > 1 and args[1] else None
            return fmt_cocktail(db_path, cocktail_name, pref_text)
        elif command == "cocktail_list":
            return fmt_cocktail_list()
        elif command == "run_status":
            return fmt_run_status()
        elif command == "run_scrape":
            authorized_user_id = os.getenv("LINE_USER_ID", "")
            if not authorized_user_id or user_id != authorized_user_id:
                return "⛔ 僅授權使用者可執行爬蟲指令。"
            with _scrape_lock:
                if _scrape_state.get("running"):
                    return f"⚠️ 爬蟲正在執行中（{_scrape_state.get('mode')} 模式），請稍後再試。"
            mode = str(args[0])
            try:
                _start_scraper(mode, db_path)
            except Exception as exc:
                logger.error("啟動爬蟲失敗：%s", exc)
                return f"⚠️ 爬蟲啟動失敗：{exc}"
            return f"🚀 爬蟲已啟動（{mode} 模式），完成後將推播通知您。"
        else:
            return f"不認識指令「{text}」。\n傳送「說明」查看所有指令。"
    except Exception as exc:
        logger.error("處理指令失敗：%s", exc)
        return "⚠️ 查詢時發生錯誤，請稍後再試。"


# ---------------------------------------------------------------------------
# 主程式
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"""
Distiller LINE Bot 已啟動
────────────────────────
Port : {port}
DB   : {DB_DEFAULT}

本機開發步驟：
1. 安裝 ngrok：brew install ngrok
2. 啟動 tunnel：ngrok http {port}
3. 複製 https://xxxx.ngrok.io/webhook
4. 在 LINE Developers Console 貼上 Webhook URL
5. 開啟 Use webhook 開關

注意：macOS AirPlay Receiver 會佔用 port 5000
      可在系統設定 → 通用 → AirDrop 與接力 中關閉，或使用預設 port 8000
""")
    _secret = os.getenv("LINE_CHANNEL_SECRET", "")
    _id = os.getenv("LINE_CHANNEL_ID", "")
    if not _secret or not _id:
        logger.error("缺少必要環境變數：LINE_CHANNEL_SECRET / LINE_CHANNEL_ID")
        sys.exit(1)
    logger.info("環境變數檢查通過")
    app = create_app()
    app.run(host="0.0.0.0", port=port, debug=False)
