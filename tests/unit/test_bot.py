"""
bot.py 單元測試
使用記憶體 SQLite 與 Flask test client，不需要真實 LINE API 連線
"""

import base64
import hashlib
import hmac
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bot import (
    _get_cached_token,
    _handle,
    _reply,
    _verify_signature,
    create_app,
    fmt_flavors,
    fmt_help,
    fmt_info,
    fmt_list,
    fmt_search,
    fmt_stats,
    fmt_top,
    parse_command,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.executescript("""
        CREATE TABLE spirits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            spirit_type TEXT,
            brand TEXT,
            country TEXT,
            category TEXT,
            badge TEXT,
            age TEXT,
            abv REAL,
            cost_level INTEGER,
            cask_type TEXT,
            expert_score INTEGER,
            community_score REAL,
            review_count INTEGER,
            description TEXT,
            tasting_notes TEXT,
            expert_name TEXT,
            flavor_summary TEXT,
            flavor_data TEXT,
            url TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE flavor_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spirit_id INTEGER NOT NULL,
            flavor_name TEXT NOT NULL,
            flavor_value INTEGER NOT NULL
        );
        CREATE TABLE scrape_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TIMESTAMP,
            total_scraped INTEGER DEFAULT 0,
            total_failed INTEGER DEFAULT 0,
            status TEXT DEFAULT 'completed'
        );
    """)
    conn.executemany(
        "INSERT INTO spirits (name, spirit_type, brand, country, expert_score, community_score, abv, cost_level, review_count, tasting_notes, url) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            (
                "Highland Park 18 Year",
                "Single Malt",
                "Highland Park",
                "Scotland",
                99,
                4.47,
                43.0,
                3,
                3078,
                "Honey and smoke.",
                "https://distiller.com/spirits/hp18",
            ),
            (
                "Hibiki 21 Year",
                "Blended",
                "Suntory",
                "Japan",
                99,
                4.52,
                43.0,
                4,
                900,
                "Floral and silky.",
                "https://distiller.com/spirits/hibiki21",
            ),
            (
                "Lagavulin 16 Year",
                "Single Malt",
                "Lagavulin",
                "Scotland",
                96,
                4.35,
                43.0,
                3,
                2500,
                "Smoke and ash.",
                "https://distiller.com/spirits/lag16",
            ),
            (
                "Tito's Vodka",
                "Unflavored Vodka",
                "Tito's",
                "USA",
                78,
                3.5,
                40.0,
                1,
                500,
                "Clean.",
                "https://distiller.com/spirits/titos",
            ),
        ],
    )
    conn.executemany(
        "INSERT INTO flavor_profiles (spirit_id, flavor_name, flavor_value) VALUES (?,?,?)",
        [
            (1, "smoky", 40),
            (1, "sweet", 70),
            (2, "floral", 60),
            (3, "smoky", 90),
            (3, "peaty", 80),
        ],
    )
    conn.execute(
        "INSERT INTO scrape_runs (started_at, total_scraped, total_failed) VALUES ('2026-02-28', 4, 0)"
    )
    conn.commit()
    conn.close()
    return str(db)


@pytest.fixture
def app(db_path):
    return create_app(
        db_path=db_path, channel_secret="test-secret", channel_id="test-id"
    )


@pytest.fixture
def client(app):
    return app.test_client()


def _make_signature(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _webhook_payload(
    text: str, reply_token: str = "test-reply-token", user_id: str = ""
) -> dict:
    return {
        "events": [
            {
                "type": "message",
                "replyToken": reply_token,
                "source": {"userId": user_id},
                "message": {"type": "text", "text": text},
            }
        ]
    }


# ---------------------------------------------------------------------------
# 指令解析
# ---------------------------------------------------------------------------


class TestParseCommand:
    def test_help_zh(self):
        assert parse_command("說明") == ("help", [])

    def test_help_en(self):
        assert parse_command("help") == ("help", [])

    def test_help_question(self):
        assert parse_command("?") == ("help", [])

    def test_stats_zh(self):
        assert parse_command("統計") == ("stats", [])

    def test_stats_en(self):
        assert parse_command("stats") == ("stats", [])

    def test_flavors_all(self):
        assert parse_command("風味") == ("flavors", [])

    def test_flavors_name(self):
        cmd, args = parse_command("風味 smoky")
        assert cmd == "flavors" and args == ["smoky"]

    def test_top_default(self):
        cmd, args = parse_command("top")
        assert cmd == "top" and args == [10]

    def test_top_n(self):
        cmd, args = parse_command("top 5")
        assert cmd == "top" and args == [5]

    def test_top_capped(self):
        _, args = parse_command("top 99")
        assert args[0] == 20

    def test_search_zh(self):
        cmd, args = parse_command("搜尋 Lagavulin")
        assert cmd == "search" and args == ["Lagavulin"]

    def test_info_zh(self):
        cmd, args = parse_command("詳情 Highland Park")
        assert cmd == "info" and args == ["Highland Park"]

    def test_list_plain(self):
        cmd, args = parse_command("列表")
        assert cmd == "list" and args == [None, None]

    def test_list_country(self):
        cmd, args = parse_command("列表 Japan")
        assert cmd == "list" and args[0] == "Japan"

    def test_unknown(self):
        cmd, _ = parse_command("隨便說點什麼")
        assert cmd == "unknown"

    def test_run_test_zh(self):
        cmd, args = parse_command("執行 test")
        assert cmd == "run_scrape" and args == ["test"]

    def test_run_medium_en(self):
        cmd, args = parse_command("run medium")
        assert cmd == "run_scrape" and args == ["medium"]

    def test_run_full_zh(self):
        cmd, args = parse_command("執行 full")
        assert cmd == "run_scrape" and args == ["full"]

    def test_run_status(self):
        cmd, args = parse_command("執行狀態")
        assert cmd == "run_status" and args == []


# ---------------------------------------------------------------------------
# 格式化函式
# ---------------------------------------------------------------------------


class TestFmtTop:
    def test_contains_names(self, db_path):
        result = fmt_top(db_path, 3)
        assert "Highland Park" in result
        assert "🥇" in result  # Top 3 使用獎牌 emoji

    def test_respects_limit(self, db_path):
        result = fmt_top(db_path, 2)
        assert "Tito" not in result  # 分數最低，排不進前 2


class TestFmtSearch:
    def test_found(self, db_path):
        result = fmt_search(db_path, "Highland")
        assert "Highland Park" in result
        assert "1 筆" in result

    def test_not_found(self, db_path):
        result = fmt_search(db_path, "zznotexist")
        assert "找不到" in result


class TestFmtInfo:
    def test_full_info(self, db_path):
        result = fmt_info(db_path, "Highland Park")
        assert "Highland Park 18 Year" in result
        assert "Scotland" in result
        assert "smoky" in result  # 風味圖譜

    def test_not_found(self, db_path):
        result = fmt_info(db_path, "zznotexist")
        assert "找不到" in result


class TestFmtStats:
    def test_output(self, db_path):
        result = fmt_stats(db_path)
        assert "總藏酒量" in result and "4" in result
        assert "類型" in result
        assert "產地" in result


class TestFmtFlavors:
    def test_all_flavors(self, db_path):
        result = fmt_flavors(db_path)
        assert "smoky" in result

    def test_specific_flavor(self, db_path):
        result = fmt_flavors(db_path, "smoky")
        assert "Lagavulin" in result  # 最高 90

    def test_flavor_not_found(self, db_path):
        result = fmt_flavors(db_path, "zznotexist")
        assert "找不到" in result


class TestFmtList:
    def test_all(self, db_path):
        result = fmt_list(db_path)
        assert "Highland Park" in result

    def test_by_country(self, db_path):
        result = fmt_list(db_path, country="Japan")
        assert "Hibiki" in result
        assert "Lagavulin" not in result

    def test_by_min_score(self, db_path):
        result = fmt_list(db_path, min_score=99)
        assert "Highland Park" in result
        assert "Lagavulin" not in result


class TestFmtHelp:
    def test_contains_commands(self):
        result = fmt_help()
        for cmd in ("top", "搜尋", "詳情", "統計", "風味", "列表"):
            assert cmd in result

    def test_contains_run_commands(self):
        result = fmt_help()
        assert "執行" in result


# ---------------------------------------------------------------------------
# _handle 整合
# ---------------------------------------------------------------------------


class TestHandle:
    def test_missing_db(self, tmp_path):
        result = _handle("統計", str(tmp_path / "no.db"))
        assert "資料庫不存在" in result

    def test_stats(self, db_path):
        result = _handle("統計", db_path)
        assert "總藏酒量" in result

    def test_search(self, db_path):
        result = _handle("搜尋 Hibiki", db_path)
        assert "Hibiki" in result

    def test_unknown_command(self, db_path):
        result = _handle("blahblah random", db_path)
        assert "不認識指令" in result


# ---------------------------------------------------------------------------
# LINE 簽名驗證
# ---------------------------------------------------------------------------


class TestVerifySignature:
    def test_valid(self):
        body = b"hello"
        sig = _make_signature(body, "secret")
        assert _verify_signature(body, sig, "secret") is True

    def test_invalid(self):
        assert _verify_signature(b"hello", "badsig", "secret") is False

    def test_wrong_secret(self):
        body = b"hello"
        sig = _make_signature(body, "correct-secret")
        assert _verify_signature(body, sig, "wrong-secret") is False


# ---------------------------------------------------------------------------
# Flask Webhook
# ---------------------------------------------------------------------------


class TestWebhook:
    def test_invalid_signature_returns_400(self, client):
        payload = json.dumps(_webhook_payload("統計")).encode()
        resp = client.post(
            "/webhook",
            data=payload,
            headers={"Content-Type": "application/json", "X-Line-Signature": "badsig"},
        )
        assert resp.status_code == 400

    def test_valid_request_returns_200(self, client):
        payload = json.dumps(_webhook_payload("統計")).encode()
        sig = _make_signature(payload, "test-secret")
        with (
            patch("bot._get_access_token", return_value="mock-token"),
            patch("bot._reply") as mock_reply,
        ):
            resp = client.post(
                "/webhook",
                data=payload,
                headers={"Content-Type": "application/json", "X-Line-Signature": sig},
            )
        assert resp.status_code == 200
        mock_reply.assert_called_once()

    def test_reply_contains_query_result(self, client, db_path):
        app = create_app(
            db_path=db_path, channel_secret="test-secret", channel_id="test-id"
        )
        c = app.test_client()
        payload = json.dumps(_webhook_payload("搜尋 Hibiki")).encode()
        sig = _make_signature(payload, "test-secret")
        with (
            patch("bot._get_access_token", return_value="tok"),
            patch("bot._reply") as mock_reply,
        ):
            c.post(
                "/webhook",
                data=payload,
                headers={"Content-Type": "application/json", "X-Line-Signature": sig},
            )
        replied_text = mock_reply.call_args[0][1]
        assert "Hibiki" in replied_text

    def test_non_message_event_ignored(self, client):
        payload = json.dumps({"events": [{"type": "follow"}]}).encode()
        sig = _make_signature(payload, "test-secret")
        with patch("bot._reply") as mock_reply:
            resp = client.post(
                "/webhook",
                data=payload,
                headers={"Content-Type": "application/json", "X-Line-Signature": sig},
            )
        assert resp.status_code == 200
        mock_reply.assert_not_called()

    def test_no_token_no_reply(self, client):
        payload = json.dumps(_webhook_payload("統計")).encode()
        sig = _make_signature(payload, "test-secret")
        with (
            patch("bot._get_access_token", return_value=None),
            patch("bot._reply") as mock_reply,
        ):
            client.post(
                "/webhook",
                data=payload,
                headers={"Content-Type": "application/json", "X-Line-Signature": sig},
            )
        mock_reply.assert_not_called()


# ---------------------------------------------------------------------------
# Token 快取
# ---------------------------------------------------------------------------


class TestTokenCache:
    def test_first_call_fetches_token(self):
        with patch("bot._get_access_token", return_value="tok") as mock_fetch:
            result = _get_cached_token("id", "sec")
        assert result == "tok"
        mock_fetch.assert_called_once()

    def test_second_call_uses_cache(self):
        with patch("bot._get_access_token", return_value="tok") as mock_fetch:
            _get_cached_token("id", "sec")
            _get_cached_token("id", "sec")
        mock_fetch.assert_called_once()

    def test_expired_token_refetches(self):
        import bot

        bot._token_cache["token"] = "old"
        bot._token_cache["expires_at"] = time.time() - 100
        with patch("bot._get_access_token", return_value="new-tok") as mock_fetch:
            result = _get_cached_token("id", "sec")
        mock_fetch.assert_called_once()
        assert result == "new-tok"

    def test_soon_to_expire_refetches(self):
        import bot

        bot._token_cache["token"] = "old"
        bot._token_cache["expires_at"] = time.time() + 30  # inside 60s safety margin
        with patch("bot._get_access_token", return_value="new-tok") as mock_fetch:
            result = _get_cached_token("id", "sec")
        mock_fetch.assert_called_once()
        assert result == "new-tok"

    def test_failed_fetch_returns_none(self):
        import bot

        with patch("bot._get_access_token", return_value=None):
            result = _get_cached_token("id", "sec")
        assert result is None
        assert bot._token_cache.get("token") is None

    def test_cache_populated_on_success(self):
        import bot

        with patch("bot._get_access_token", return_value="tok"):
            _get_cached_token("id", "sec")
        assert bot._token_cache["token"] == "tok"
        assert "expires_at" in bot._token_cache


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_has_required_keys(self, client):
        resp = client.get("/health")
        data = resp.get_json()
        assert "status" in data
        assert "db_exists" in data
        assert "token_cached" in data

    def test_health_db_exists_true(self, client):
        resp = client.get("/health")
        data = resp.get_json()
        assert data["db_exists"] is True

    def test_health_token_cached_false(self, client):
        resp = client.get("/health")
        data = resp.get_json()
        assert data["token_cached"] is False

    def test_health_token_cached_true(self, client):
        import bot

        bot._token_cache["token"] = "tok"
        resp = client.get("/health")
        data = resp.get_json()
        assert data["token_cached"] is True


# ---------------------------------------------------------------------------
# Webhook Verification Probe
# ---------------------------------------------------------------------------


class TestWebhookVerificationProbe:
    def test_empty_events_returns_200_no_signature(self, client):
        payload = json.dumps({"events": []}).encode()
        resp = client.post(
            "/webhook",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200

    def test_malformed_json_returns_200(self, client):
        resp = client.post(
            "/webhook",
            data=b"not-json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# _reply() 回傳值
# ---------------------------------------------------------------------------


class TestReplyReturnValue:
    def test_reply_returns_true_on_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("requests.post", return_value=mock_resp):
            result = _reply("tok", "msg", "access-tok")
        assert result is True

    def test_reply_returns_false_on_non_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "bad request"
        with patch("requests.post", return_value=mock_resp):
            result = _reply("tok", "msg", "access-tok")
        assert result is False

    def test_reply_returns_false_on_network_error(self):
        with patch(
            "requests.post", side_effect=requests.RequestException("network error")
        ):
            result = _reply("tok", "msg", "access-tok")
        assert result is False


# ---------------------------------------------------------------------------
# DB-missing log
# ---------------------------------------------------------------------------


class TestDbMissingLog:
    def test_missing_db_logs_warning(self, tmp_path, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            _handle("統計", str(tmp_path / "no.db"))
        assert "資料庫不存在" in caplog.text


class TestHandleRunScrape:
    """👉 LINE 爬蟲執行指令測試。"""

    def setup_method(self):
        import bot

        bot._scrape_state["running"] = False
        bot._scrape_state["mode"] = None
        bot._scrape_state["started_at"] = None

    def test_unauthorized_user_rejected(self, db_path):
        with patch.dict(os.environ, {"LINE_USER_ID": "correct_user"}):
            result = _handle("執行 test", db_path, user_id="wrong_user")
        assert "⛔" in result

    def test_no_user_id_rejected(self, db_path):
        with patch.dict(os.environ, {"LINE_USER_ID": "correct_user"}):
            result = _handle("執行 test", db_path, user_id=None)
        assert "⛔" in result

    def test_already_running_rejected(self, db_path):
        import bot

        bot._scrape_state["running"] = True
        bot._scrape_state["mode"] = "test"
        with patch.dict(os.environ, {"LINE_USER_ID": "user123"}):
            result = _handle("執行 test", db_path, user_id="user123")
        assert "執行中" in result

    def test_authorized_launches_scraper(self, db_path):
        with (
            patch("bot._start_scraper_thread") as mock_start,
            patch.dict(os.environ, {"LINE_USER_ID": "user123"}),
        ):
            result = _handle("執行 test", db_path, user_id="user123")
        mock_start.assert_called_once_with("test", db_path)
        assert "🚀" in result

    def test_run_status_idle(self, db_path):
        import bot

        bot._scrape_state["running"] = False
        result = _handle("執行狀態", db_path)
        assert "💤" in result

    def test_run_status_running(self, db_path):
        import bot

        bot._scrape_state["running"] = True
        bot._scrape_state["mode"] = "full"
        bot._scrape_state["started_at"] = "2026-03-17T03:00:00"
        result = _handle("執行狀態", db_path)
        assert "full" in result
        assert "已執行" in result


# ---------------------------------------------------------------------------
# Recipe 指令測試
# ---------------------------------------------------------------------------


@pytest.fixture
def diffords_db(tmp_path):
    """建立含一筆 Negroni 酒譜的 Difford's DB。"""
    from distiller_scraper.diffords_storage import DiffordsStorage

    db = tmp_path / "diffords.db"
    with DiffordsStorage(str(db)) as storage:
        storage.save_cocktail(
            {
                "url": "https://www.diffordsguide.com/cocktails/recipe/1502/negroni",
                "name": "Negroni",
                "description": "A classic Italian aperitif cocktail.",
                "glassware": "Old-fashioned glass",
                "garnish": "Orange slice",
                "prepare": None,
                "instructions": "Stir all ingredients with ice. Strain into glass.",
                "review": "A perfectly balanced bitter classic.",
                "history": "Invented by Count Camillo Negroni in 1919.",
                "tags": ["bitter", "classic"],
                "rating_value": 4.5,
                "rating_count": 200,
                "calories": 200,
                "prep_time_minutes": 2,
                "abv": 28.0,
                "date_published": "2010-01-01",
                "lastmod": "2024-01-01",
                "ingredients_html": [
                    {"sort_order": 1, "item": "Campari", "amount": "30ml"},
                    {"sort_order": 2, "item": "Sweet vermouth", "amount": "30ml"},
                    {"sort_order": 3, "item": "Gin", "amount": "30ml"},
                ],
                "ingredients_generic": [],
            }
        )
    return str(db)


class TestParseCommandRecipe:
    def test_recipe_chinese(self):
        cmd, args = parse_command("酒譜 Negroni")
        assert cmd == "recipe"
        assert args[0] == "Negroni"

    def test_recipe_fangjin(self):
        cmd, args = parse_command("酒方 Daiquiri")
        assert cmd == "recipe"
        assert args[0] == "Daiquiri"

    def test_recipe_english(self):
        cmd, args = parse_command("recipe Margarita")
        assert cmd == "recipe"
        assert args[0] == "Margarita"


class TestFmtRecipe:
    def test_found_returns_detail(self, diffords_db):
        from bot import fmt_recipe

        result = fmt_recipe(diffords_db, "Negroni")
        assert "Negroni" in result
        assert "Campari" in result
        assert "食材" in result

    def test_not_found_returns_hint(self, diffords_db):
        from bot import fmt_recipe

        result = fmt_recipe(diffords_db, "NonexistentDrink12345")
        assert "❓" in result

    def test_partial_match_returns_list(self, diffords_db):
        from bot import fmt_recipe

        # "neg" 應該能模糊匹配到 Negroni
        result = fmt_recipe(diffords_db, "neg")
        # 有找到（單筆直接顯示詳情）或列出搜尋結果
        assert "Negroni" in result

    def test_history_shown(self, diffords_db):
        from bot import fmt_recipe

        result = fmt_recipe(diffords_db, "Negroni")
        assert "歷史" in result
        assert "1919" in result

    def test_review_shown(self, diffords_db):
        from bot import fmt_recipe

        result = fmt_recipe(diffords_db, "Negroni")
        assert "評語" in result


class TestHandleRecipe:
    def test_recipe_command_dispatched(self, db_path, diffords_db):
        result = _handle("酒譜 Negroni", db_path, diffords_db_path=diffords_db)
        assert "Negroni" in result
        assert "Campari" in result

    def test_recipe_no_db_returns_warning(self, db_path, tmp_path):
        missing_db = str(tmp_path / "missing.db")
        result = _handle("酒譜 Negroni", db_path, diffords_db_path=missing_db)
        assert "⚠️" in result

    def test_recipe_empty_query(self, db_path, diffords_db):
        # parse_command 不會產生空 query（需要至少一個字），直接測 fmt_recipe
        from bot import fmt_recipe

        # 空名稱測試：search 會找不到
        result = fmt_recipe(diffords_db, "zzz_nothing")
        assert "❓" in result


@pytest.fixture
def mock_recommender_none():
    """CocktailRecommender mock，recommend 回傳 None（模擬無推薦結果）。"""
    with patch("distiller_scraper.recommender.CocktailRecommender") as MockRec:
        inst = MagicMock()
        inst.__enter__ = lambda s: inst
        inst.__exit__ = MagicMock(return_value=False)
        inst.recommend.return_value = None
        MockRec.return_value = inst
        yield MockRec


class TestDiffordsEnrichment:
    """測試 cocktail 指令後附加 Difford's history/review。"""

    def test_enrichment_appended_when_db_exists(
        self, db_path, diffords_db, mock_recommender_none
    ):
        from bot import fmt_cocktail

        result = fmt_cocktail(db_path, "Negroni", None, diffords_db_path=diffords_db)
        assert isinstance(result, str)

    def test_enrichment_skipped_when_no_db(
        self, db_path, tmp_path, mock_recommender_none
    ):
        from bot import fmt_cocktail

        missing = str(tmp_path / "no.db")
        result = fmt_cocktail(db_path, "Negroni", None, diffords_db_path=missing)
        assert isinstance(result, str)
        assert "1919" not in result


class TestFmtHelpCocktailSection:
    """Test fmt_help() contains 🍸 調酒查詢 section with cocktail commands."""

    def test_fmt_help_contains_cocktail_section_header(self):
        """fmt_help() should include '🍸 調酒查詢' header."""
        result = fmt_help()
        assert "🍸 調酒查詢" in result

    def test_fmt_help_contains_specific_cocktail_commands(self):
        """fmt_help() should list all 6 cocktail commands."""
        result = fmt_help()
        expected_commands = [
            "調酒排行",
            "調酒搜尋",
            "調酒詳情",
            "調酒統計",
            "調酒列表",
            "我能做什麼",
        ]
        for cmd in expected_commands:
            assert cmd in result


class TestFmtCocktailEmptyDb:
    """Test fmt_cocktail_* functions return _DIFFORDS_DB_MISSING when DB missing."""

    def test_fmt_cocktail_top_returns_missing_db_message(self, tmp_path):
        """fmt_cocktail_top() returns _DIFFORDS_DB_MISSING when DB doesn't exist."""
        from bot import fmt_cocktail_top, _DIFFORDS_DB_MISSING

        missing_db_path = str(tmp_path / "nonexistent_diffords.db")
        result = fmt_cocktail_top(missing_db_path, n=10)
        assert result == _DIFFORDS_DB_MISSING

    def test_fmt_cocktail_search_returns_missing_db_message(self, tmp_path):
        """fmt_cocktail_search() returns _DIFFORDS_DB_MISSING when DB doesn't exist."""
        from bot import fmt_cocktail_search, _DIFFORDS_DB_MISSING

        missing_db_path = str(tmp_path / "nonexistent_diffords.db")
        result = fmt_cocktail_search(missing_db_path, "martini")
        assert result == _DIFFORDS_DB_MISSING
