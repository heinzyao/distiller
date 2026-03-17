import pytest
import bot


@pytest.fixture(autouse=True)
def clear_token_cache():
    """各測試前清除 token 快取，避免測試間狀態污染。"""
    bot._token_cache.clear()
    bot._scrape_state["running"] = False
    bot._scrape_state["mode"] = None
    bot._scrape_state["started_at"] = None
    yield
    bot._token_cache.clear()
    bot._scrape_state["running"] = False
    bot._scrape_state["mode"] = None
    bot._scrape_state["started_at"] = None
