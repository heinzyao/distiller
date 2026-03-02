## [2026-03-02T05:10:38Z] Session: ses_353b61b58ffeygmkcTTzylarQx

### bot.py Key Facts
- 454 lines total
- `_get_access_token()` at L58-76: returns `str | None`, makes POST to LINE_TOKEN_URL
  - Returns `resp.json()["access_token"]` on HTTP 200
  - Returns None on any failure (network or non-200)
- `_verify_signature()` at L79-82
- `_reply()` at L85-102: currently returns `None`
  - Makes POST to LINE_REPLY_URL with Authorization Bearer header
  - Logs warning on non-200, error on network exception
- `create_app()` at L357-396: Flask app factory
  - webhook handler at L367-394
  - L371-373: signature check → abort(400) on failure
  - L375: `data = request.get_json(silent=True) or {}`
  - L388: `token = _get_access_token(_channel_id, _channel_secret)` ← to change to _get_cached_token
- `_handle()` at L399-428: DB path check at L401-402 (no log currently)
- `__main__` at L435-454: starts Flask, no env validation currently

### run_bot.sh Key Facts
- L8: `VENV_PYTHON="$PROJECT_DIR/venv/bin/python"` ← remove
- L21: `exec "$VENV_PYTHON" bot.py` ← change to `exec uv run python bot.py`

### com.distiller.bot.plist Key Facts
- L19: PATH = `/Users/Henry/Project/Distiller/venv/bin:/usr/local/bin:/usr/bin:/bin` ← update
- uv is at `/Users/Henry/.local/bin/uv`
- New PATH should be: `/Users/Henry/.local/bin:/usr/local/bin:/usr/bin:/bin`

### Token Cache Design
- Module-level: `_token_cache: dict = {}`
- Fixed 23-hour TTL (82800 seconds) — LINE tokens last 30 days but we refresh early
- 60-second safety margin before expiry
- Cache dict keys: `token` (str), `expires_at` (float from time.time())
- `_get_cached_token(channel_id, channel_secret) -> str | None`
- Do NOT change `_get_access_token()` — it's the internal fetch function

### Imports Needed
- `import time` must be added to bot.py (not currently imported)

## [2026-03-02] Task 4: New Tests Added
- 17 new test methods added across 5 classes: TestTokenCache (6), TestHealthCheck (5), TestWebhookVerificationProbe (2), TestReplyReturnValue (3), TestDbMissingLog (1)
- The autouse `clear_token_cache` fixture in conftest.py clears `bot._token_cache` before/after each test — but individual token cache tests still need `import bot` to set cache state directly
- Token cache tests require patching `bot._get_access_token` (not `requests.post`) since that's the internal function; `_get_cached_token` wraps it
- For `test_soon_to_expire_refetches`: setting `expires_at = time.time() + 30` puts it within the 60s safety margin → triggers refetch
- `_reply()` patches `requests.post` directly since it calls `requests.post` internally (not a bot module wrapper)
- Webhook verification probe: empty events `{"events": []}` → early return 200 before signature check; malformed JSON → `data is None` path → 200
- `caplog` with `caplog.at_level(logging.WARNING)` needed to capture logger.warning() calls from `_handle()`
- Total test count: 242 → 259 (all passing)

## [2026-03-02T06:05:30Z] Task 3 follow-up

- LSP clean required adding explicit typing casts for sqlite3 rows and string list initializations in bot.py.
- Health/webhook checks run via single-line uv python -c commands to avoid newline escape errors.
