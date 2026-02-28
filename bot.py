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
import sys
from pathlib import Path

import requests
from flask import Flask, abort, request

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

LINE_TOKEN_URL = "https://api.line.me/v2/oauth/accessToken"
LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"
DB_DEFAULT = "distiller.db"
MSG_LIMIT = 4900  # LINE 單則訊息字元上限


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
            return resp.json()["access_token"]
        logger.warning("Token 取得失敗：%s", resp.text)
        return None
    except requests.RequestException as exc:
        logger.error("Token 請求失敗：%s", exc)
        return None


def _verify_signature(body: bytes, signature: str, channel_secret: str) -> bool:
    """驗證 LINE Webhook 簽名（HMAC-SHA256）。"""
    digest = hmac.new(channel_secret.encode(), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode() == signature


def _reply(reply_token: str, text: str, access_token: str) -> None:
    """透過 Reply API 回覆訊息（自動拆分超長訊息，最多 5 則）。"""
    chunks = [text[i:i + MSG_LIMIT] for i in range(0, len(text), MSG_LIMIT)][:5]
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
            logger.warning("Reply 失敗：%s %s", resp.status_code, resp.text)
    except requests.RequestException as exc:
        logger.error("Reply 請求失敗：%s", exc)


# ---------------------------------------------------------------------------
# 資料庫查詢（回傳字串，不 print）
# ---------------------------------------------------------------------------

def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _score_bar(score: int, width: int = 8) -> str:
    if score is None:
        return ""
    filled = round(score / 100 * width)
    return "█" * filled + "░" * (width - filled)


def fmt_top(db_path: str, n: int = 10) -> str:
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT name, spirit_type, country, expert_score FROM spirits "
        "WHERE expert_score IS NOT NULL ORDER BY expert_score DESC LIMIT ?", (n,)
    ).fetchall()
    conn.close()
    if not rows:
        return "資料庫尚無資料。"
    lines = [f"🏆 評分 Top {n}\n"]
    for i, r in enumerate(rows, 1):
        bar = _score_bar(r["expert_score"])
        lines.append(f"{i:>2}. {r['name']}\n    {r['spirit_type']} | {r['country']}\n    {bar} {r['expert_score']}分\n")
    return "\n".join(lines)


def fmt_search(db_path: str, keyword: str, limit: int = 10) -> str:
    conn = _connect(db_path)
    kw = f"%{keyword}%"
    rows = conn.execute(
        "SELECT name, spirit_type, country, expert_score FROM spirits "
        "WHERE name LIKE ? OR brand LIKE ? OR description LIKE ? "
        "ORDER BY expert_score DESC NULLS LAST LIMIT ?",
        (kw, kw, kw, limit),
    ).fetchall()
    conn.close()
    if not rows:
        return f"找不到符合「{keyword}」的烈酒。"
    lines = [f"🔍 搜尋「{keyword}」：{len(rows)} 筆\n"]
    for r in rows:
        score = f"{r['expert_score']}分" if r["expert_score"] else "無評分"
        lines.append(f"・{r['name']}\n  {r['spirit_type']} | {r['country']} | {score}")
    return "\n".join(lines)


def fmt_info(db_path: str, name: str) -> str:
    conn = _connect(db_path)
    row = conn.execute("SELECT * FROM spirits WHERE name LIKE ? LIMIT 1", (f"%{name}%",)).fetchone()
    if not row:
        conn.close()
        return f"找不到符合「{name}」的烈酒。"
    row = dict(row)
    lines = [
        f"🥃 {row['name']}",
        f"{'─' * 30}",
        f"類型：{row.get('spirit_type') or '—'}",
        f"品牌：{row.get('brand') or '—'}",
        f"產地：{row.get('country') or '—'}",
        f"年份：{row.get('age') or '—'}",
        f"ABV：{row.get('abv') or '—'}%",
        f"價位：{'$' * row['cost_level'] if row.get('cost_level') else '—'}",
        f"專家評分：{row.get('expert_score') or '—'} {_score_bar(row.get('expert_score'))}",
        f"社群評分：{row.get('community_score') or '—'}",
        f"評論數：{row.get('review_count') or '—'}",
    ]
    if row.get("tasting_notes"):
        lines.append(f"\n👃 {row['tasting_notes'][:150]}")

    flavors = conn.execute(
        "SELECT flavor_name, flavor_value FROM flavor_profiles "
        "WHERE spirit_id = ? ORDER BY flavor_value DESC LIMIT 8",
        (row["id"],),
    ).fetchall()
    conn.close()
    if flavors:
        lines.append("\n🎨 風味：")
        for f in flavors:
            bar = "█" * (f["flavor_value"] // 10)
            lines.append(f"  {f['flavor_name']:12s} {bar} {f['flavor_value']}")
    return "\n".join(lines)


def fmt_stats(db_path: str) -> str:
    conn = _connect(db_path)
    total = conn.execute("SELECT COUNT(*) FROM spirits").fetchone()[0]
    avg = conn.execute("SELECT ROUND(AVG(expert_score),1) FROM spirits WHERE expert_score IS NOT NULL").fetchone()[0]
    hi = conn.execute("SELECT MAX(expert_score) FROM spirits").fetchone()[0]
    lo = conn.execute("SELECT MIN(expert_score) FROM spirits WHERE expert_score IS NOT NULL").fetchone()[0]
    types = conn.execute(
        "SELECT spirit_type, COUNT(*) c FROM spirits GROUP BY spirit_type ORDER BY c DESC LIMIT 6"
    ).fetchall()
    countries = conn.execute(
        "SELECT country, COUNT(*) c FROM spirits WHERE country IS NOT NULL GROUP BY country ORDER BY c DESC LIMIT 5"
    ).fetchall()
    conn.close()

    lines = [
        f"📊 資料庫統計",
        f"{'─' * 25}",
        f"總筆數：{total}",
        f"平均分：{avg}",
        f"分數區間：{lo} ~ {hi}",
        f"\n📋 主要類型：",
    ]
    for r in types:
        lines.append(f"  {r[0]}：{r[1]}筆")
    lines.append(f"\n🌍 主要產地：")
    for r in countries:
        lines.append(f"  {r[0]}：{r[1]}筆")
    return "\n".join(lines)


def fmt_flavors(db_path: str, flavor_name: str | None = None, limit: int = 10) -> str:
    conn = _connect(db_path)
    if flavor_name:
        rows = conn.execute(
            "SELECT s.name, fp.flavor_value, s.expert_score "
            "FROM flavor_profiles fp JOIN spirits s ON s.id = fp.spirit_id "
            "WHERE fp.flavor_name = ? ORDER BY fp.flavor_value DESC LIMIT ?",
            (flavor_name, limit),
        ).fetchall()
        conn.close()
        if not rows:
            return f"找不到風味「{flavor_name}」的資料。"
        lines = [f"🎨 風味「{flavor_name}」排行\n"]
        for i, r in enumerate(rows, 1):
            bar = "█" * (r["flavor_value"] // 10)
            lines.append(f"{i:>2}. {r['name']}\n    {bar} {r['flavor_value']} | 專家 {r['expert_score']}分")
        return "\n".join(lines)
    else:
        rows = conn.execute(
            "SELECT flavor_name, ROUND(AVG(flavor_value),0) avg "
            "FROM flavor_profiles GROUP BY flavor_name ORDER BY avg DESC"
        ).fetchall()
        conn.close()
        lines = ["🎨 風味維度平均值\n"]
        for r in rows:
            bar = "█" * (int(r["avg"]) // 10)
            lines.append(f"  {r['flavor_name']:14s} {bar} {int(r['avg'])}")
        return "\n".join(lines)


def fmt_list(db_path: str, country: str | None = None, min_score: int | None = None, limit: int = 10) -> str:
    conn = _connect(db_path)
    conds, params = [], []
    if country:
        conds.append("country LIKE ?")
        params.append(f"%{country}%")
    if min_score is not None:
        conds.append("expert_score >= ?")
        params.append(min_score)
    where = " WHERE " + " AND ".join(conds) if conds else ""
    total = conn.execute(f"SELECT COUNT(*) FROM spirits{where}", params).fetchone()[0]
    params.append(limit)
    rows = conn.execute(
        f"SELECT name, spirit_type, country, expert_score FROM spirits{where} "
        f"ORDER BY expert_score DESC NULLS LAST LIMIT ?", params
    ).fetchall()
    conn.close()
    if not rows:
        return "找不到符合條件的烈酒。"
    title_parts = []
    if country:
        title_parts.append(country)
    if min_score:
        title_parts.append(f"{min_score}分以上")
    title = "・".join(title_parts) if title_parts else "全部"
    lines = [f"📋 烈酒列表（{title}，共 {total} 筆）\n"]
    for r in rows:
        score = f"{r['expert_score']}分" if r["expert_score"] else "無評分"
        lines.append(f"・{r['name']}\n  {r['spirit_type']} | {r['country']} | {score}")
    if total > limit:
        lines.append(f"\n（顯示前 {limit} 筆，共 {total} 筆）")
    return "\n".join(lines)


def fmt_help() -> str:
    return (
        "🥃 Distiller 查詢指令\n"
        "────────────────\n"
        "top [N]\n  評分最高前 N 筆（預設 10）\n\n"
        "搜尋 <關鍵字>\n  搜尋品名、品牌、描述\n\n"
        "詳情 <名稱>\n  完整資訊與風味圖譜\n\n"
        "統計\n  資料庫統計摘要\n\n"
        "風味\n  所有風味維度平均\n\n"
        "風味 <名稱>\n  例：風味 smoky\n\n"
        "列表\n  列出前 10 筆\n\n"
        "列表 <產地>\n  例：列表 Japan\n\n"
        "列表 <產地> <最低分>\n  例：列表 Scotland 95"
    )


# ---------------------------------------------------------------------------
# 指令解析
# ---------------------------------------------------------------------------

def parse_command(text: str) -> tuple[str, list]:
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

    @app.route("/webhook", methods=["POST"])
    def webhook():
        body = request.get_data()
        signature = request.headers.get("X-Line-Signature", "")

        if not _verify_signature(body, signature, _channel_secret):
            logger.warning("簽名驗證失敗")
            abort(400)

        data = request.get_json(silent=True) or {}
        for event in data.get("events", []):
            if event.get("type") != "message":
                continue
            if event.get("message", {}).get("type") != "text":
                continue

            reply_token = event.get("replyToken", "")
            user_text = event["message"]["text"]
            logger.info("收到訊息：%s", user_text)

            response = _handle(user_text, db_path)

            token = _get_access_token(_channel_id, _channel_secret)
            if token:
                _reply(reply_token, response, token)
            else:
                logger.error("無法取得 Access Token，無法回覆")

        return "OK", 200

    return app


def _handle(text: str, db_path: str) -> str:
    """解析指令並回傳回覆文字。"""
    if not Path(db_path).exists():
        return "⚠️ 資料庫不存在，請先執行：python run.py --mode test --output sqlite"

    command, args = parse_command(text)

    try:
        if command == "help":
            return fmt_help()
        elif command == "top":
            return fmt_top(db_path, args[0] if args else 10)
        elif command == "search":
            return fmt_search(db_path, args[0])
        elif command == "info":
            return fmt_info(db_path, args[0])
        elif command == "stats":
            return fmt_stats(db_path)
        elif command == "flavors":
            return fmt_flavors(db_path, args[0] if args else None)
        elif command == "list":
            return fmt_list(db_path, args[0] if len(args) > 0 else None, args[1] if len(args) > 1 else None)
        else:
            return (
                f"不認識指令「{text}」。\n"
                "傳送「說明」查看所有指令。"
            )
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
    app = create_app()
    app.run(host="0.0.0.0", port=port, debug=False)
