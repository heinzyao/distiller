# LINE Bot Resilience Fix

## TL;DR

> **Quick Summary**: Fix 7 silent failure points in the LINE Bot that cause it to never reply, add resilience features (token caching, health check, startup validation, webhook verification), and update startup infrastructure from venv to uv.
> 
> **Deliverables**:
> - `bot.py` — All 7 failure points fixed, OAuth token caching, health check endpoint, webhook verification, startup env validation, improved logging
> - `scripts/run_bot.sh` — Migrated from `venv/bin/python` to `uv run`
> - `com.distiller.bot.plist` — Updated PATH for uv
> - `tests/unit/test_bot.py` — New tests for token caching, health check, startup validation, webhook verification
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES — 3 waves
> **Critical Path**: Task 1 (token caching) → Task 3 (webhook handler) → Task 5 (tests) → Task 7 (verification)

---

## Context

### Original Request
User's LINE Bot never replies to messages. After diagnostic conversation, user wants full resilience — fix all silent failure points AND add robustness features.

### Interview Summary
**Key Discussions**:
- **Symptom**: Bot never replies — complete silence
- **Infrastructure**: ngrok free tier (URL rotates every restart)
- **Timeout strategy**: Token caching only (no async processing) — keeps it simple
- **Startup script**: Migrate from venv to uv
- **launchd plist**: Update to match uv migration
- **Resilience scope**: Full — fix all 7 failure points + health check + webhook verification + startup validation
- **Test strategy**: Tests after implementation (242 existing unit tests, all pass)

**Research Findings**:
- 7 silent failure points identified in bot.py (see Failure Point Table below)
- `_get_access_token()` fetches a NEW OAuth token for every reply — major latency risk given LINE's 2-second webhook timeout
- LINE sends verification probe `{"events":[]}` with no signature — bot currently rejects with 400
- `_reply()` returns None — no way to know if reply succeeded
- `run_bot.sh` uses `venv/bin/python` but project uses `uv`
- LINE can suspend webhook delivery if bot fails to receive for a long time

### Failure Point Table
| # | Location | Condition | Current Behavior | Fix |
|---|----------|-----------|-----------------|-----|
| 1 | L371: `_verify_signature()` | Wrong channel secret | abort(400), WARNING log | Keep — but add better log context |
| 2 | L375: `request.get_json()` | Malformed JSON | Silent skip, NO log | Add ERROR log |
| 3 | L426-428: `_handle()` | DB query error | Generic error text, ERROR log | Keep — already handled |
| 4 | L388-392: token fetch | Token fetch fails | Skips `_reply()` entirely, ERROR log | Cache token + retry once |
| 5 | L401: DB check | DB file missing | Error text, NO log | Add WARNING log |
| 6 | L99-100: `_reply()` | Reply HTTP error | WARNING log, user sees nothing | Return bool, log response details |
| 7 | L101-102: `_reply()` | Reply network error | ERROR log, user sees nothing | Return bool, log exception details |

---

## Work Objectives

### Core Objective
Make the LINE Bot reliably reply to every message by fixing all 7 silent failure points, caching OAuth tokens to avoid the 2-second webhook timeout, and adding resilience features (health check, webhook verification, startup validation).

### Concrete Deliverables
- `bot.py` — Fixed and hardened (all 7 failure points addressed, token caching, health check, webhook verification, startup env validation)
- `scripts/run_bot.sh` — Uses `uv run` instead of `venv/bin/python`
- `com.distiller.bot.plist` — Updated PATH to include uv
- `tests/unit/test_bot.py` — New test cases for all new functionality

### Definition of Done
- [ ] `uv run python -m pytest tests/unit/ -q` — ALL tests pass (242 existing + new tests)
- [ ] `GET /health` returns 200 with JSON status
- [ ] Webhook verification probe (empty events[]) returns 200
- [ ] Bot replies to "說明" command via Flask test client
- [ ] Token is cached and reused across multiple requests
- [ ] Startup logs show env validation results
- [ ] `run_bot.sh` uses `uv run`

### Must Have
- Fix all 7 silent failure points (see table above)
- Cache OAuth access token with TTL (don't fetch per-reply)
- `GET /health` endpoint returning JSON status
- Webhook verification support (empty events[] → 200)
- Startup validation of required environment variables
- `run_bot.sh` migrated to `uv run`
- `com.distiller.bot.plist` updated PATH
- All log messages in Chinese (consistent with existing code)
- Tests for all new functionality

### Must NOT Have (Guardrails)
- NO async processing — keep synchronous Flask handler
- NO LINE SDK migration — keep custom handler approach
- NO new bot commands or features
- NO new Python dependencies (use only stdlib + existing deps)
- NO changes to database schema or query logic
- NO changes to `fmt_*` functions or `parse_command`
- NO changes to existing test cases (only ADD new ones)
- NO over-engineering: token cache can be a simple module-level dict, not Redis/memcached

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest, 242 unit tests)
- **Automated tests**: Tests-after (implementation first, tests second)
- **Framework**: pytest (existing)

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Bot endpoints**: Use Bash (Flask test client via pytest) — send requests, assert responses
- **Startup validation**: Use Bash — run bot.py with missing env vars, check output
- **Infrastructure files**: Use Bash — check file contents, validate syntax

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — independent foundation changes):
├── Task 1: Token caching module [quick]
├── Task 2: Startup infrastructure (run_bot.sh + plist) [quick]
└── (2 tasks — both independent, no dependencies)

Wave 2 (After Wave 1 — core bot.py changes that depend on token caching):
├── Task 3: Webhook handler hardening (all 7 failure points + health check + verification) [deep]
├── (1 task — depends on Task 1 for cached token API)

Wave 3 (After Wave 2 — tests + verification):
├── Task 4: Tests for all new functionality [unspecified-high]
├── Task 5: Full verification + commit [deep]
└── (2 tasks — Task 5 depends on Task 4)

Wave FINAL (After ALL tasks — independent review):
├── Task F1: Plan compliance + code quality audit [oracle]
└── (1 task)

Critical Path: Task 1 → Task 3 → Task 4 → Task 5 → F1
Parallel Speedup: ~30% faster than sequential (Wave 1 parallelism)
Max Concurrent: 2 (Wave 1)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | — | 3 | 1 |
| 2 | — | 5 | 1 |
| 3 | 1 | 4 | 2 |
| 4 | 3 | 5 | 3 |
| 5 | 2, 4 | F1 | 3 |
| F1 | 5 | — | FINAL |

### Agent Dispatch Summary

- **Wave 1**: **2** — T1 → `quick`, T2 → `quick`
- **Wave 2**: **1** — T3 → `deep`
- **Wave 3**: **2** — T4 → `unspecified-high`, T5 → `deep`
- **FINAL**: **1** — F1 → `oracle`

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info + QA Scenarios.


- [ ] 1. **Token Caching Module**

  **What to do**:
  - Replace per-reply `_get_access_token()` calls with a cached token mechanism
  - Add a module-level `_token_cache` dict with keys `token` and `expires_at`
  - Create `_get_cached_token(channel_id, channel_secret)` that:
    - Returns cached token if `time.time() < expires_at - 60` (60s safety margin)
    - Otherwise fetches a new token via existing `_get_access_token()`
    - Caches the result with TTL (LINE short-lived tokens last ~30 days, use 23 hours as cache TTL to be safe)
    - Returns `None` on failure (preserving existing error handling contract)
  - Update `import` to include `time`
  - Keep existing `_get_access_token()` unchanged — it becomes the internal fetch function
  - The cache is process-level (dict) — resets on restart, which is fine

  **Must NOT do**:
  - Do NOT add Redis, memcached, or any external cache dependency
  - Do NOT change the signature or behavior of `_get_access_token()`
  - Do NOT add async/threading for token refresh

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small, focused change — add one function + one dict, well-defined contract
  - **Skills**: []
    - No special skills needed — pure Python, no browser/git/UI

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 2)
  - **Blocks**: Task 3 (webhook handler needs to call `_get_cached_token`)
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References** (existing code to follow):
  - `bot.py:58-76` — `_get_access_token()` — the existing token fetch function. Keep this unchanged; the new `_get_cached_token()` wraps it.
  - `bot.py:48` — `LINE_TOKEN_URL` constant — used by `_get_access_token()`

  **API/Type References** (contracts to implement against):
  - `bot.py:388` — `token = _get_access_token(_channel_id, _channel_secret)` — this call site will change to `_get_cached_token()` in Task 3
  - LINE OAuth API returns `{"access_token": "...", "expires_in": 2592000, "token_type": "Bearer"}` — use `expires_in` for TTL

  **External References**:
  - LINE OAuth docs: access tokens from client credentials grant have `expires_in` field (typically 2592000 = 30 days)

  **WHY Each Reference Matters**:
  - `bot.py:58-76`: The new function wraps this — must understand its return type (`str | None`) and error handling
  - `bot.py:388`: This is the call site that Task 3 will update — cache function must be a drop-in replacement

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Token is fetched and cached on first call
    Tool: Bash (pytest)
    Preconditions: No cached token exists
    Steps:
      1. Call `_get_cached_token('test-id', 'test-secret')` with mocked `_get_access_token` returning 'mock-token'
      2. Assert return value is 'mock-token'
      3. Call `_get_cached_token` again
      4. Assert `_get_access_token` was called only ONCE (second call used cache)
    Expected Result: Token fetched once, reused on second call
    Failure Indicators: `_get_access_token` called twice, or second call returns None
    Evidence: .sisyphus/evidence/task-1-token-cache.txt

  Scenario: Token fetch failure returns None without caching
    Tool: Bash (pytest)
    Preconditions: No cached token
    Steps:
      1. Call `_get_cached_token` with mocked `_get_access_token` returning None
      2. Assert return value is None
      3. Assert `_token_cache` is empty (failure not cached)
    Expected Result: None returned, no stale token cached
    Failure Indicators: Cache contains None, or exception raised
    Evidence: .sisyphus/evidence/task-1-token-cache-failure.txt
  ```

  **Commit**: YES (groups with all tasks)
  - Message: `fix(bot): add resilience — token caching, failure point fixes, health check, startup validation`
  - Files: `bot.py`
  - Pre-commit: `uv run python -m pytest tests/unit/ -q`

---

- [ ] 2. **Startup Infrastructure Migration**

  **What to do**:
  - **`scripts/run_bot.sh`**:
    - Change line 8: `VENV_PYTHON="$PROJECT_DIR/venv/bin/python"` → remove this variable
    - Change line 21: `exec "$VENV_PYTHON" bot.py` → `exec uv run python bot.py`
    - Remove the `VENV_PYTHON` variable entirely
    - Keep everything else (PROJECT_DIR, LOG_DIR, .env sourcing, cd)
  - **`com.distiller.bot.plist`**:
    - Change line 19 PATH: add uv's typical path (`/Users/Henry/.local/bin` or `~/.cargo/bin`) to the PATH string
    - Verify uv location first: `which uv` to get exact path
    - Keep all other plist settings unchanged (Label, WorkingDirectory, KeepAlive, log paths)

  **Must NOT do**:
  - Do NOT change the plist Label, WorkingDirectory, log paths, or KeepAlive settings
  - Do NOT change .env sourcing logic in run_bot.sh
  - Do NOT add new functionality to the startup script
  - Do NOT install the plist via launchctl (user will do this manually)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Two small file edits — script and plist, no complex logic
  - **Skills**: []
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 1)
  - **Blocks**: Task 5 (verification needs updated scripts)
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References** (existing code to follow):
  - `scripts/run_bot.sh:1-21` — Full current startup script. Key lines: L8 (VENV_PYTHON), L21 (exec command)
  - `com.distiller.bot.plist:1-36` — Full current plist. Key line: L19 (PATH)
  - `scripts/run_scraper.sh` — The scraper startup script, for reference on how the project's other script is structured

  **External References**:
  - `which uv` output — to determine exact uv binary location for plist PATH

  **WHY Each Reference Matters**:
  - `run_bot.sh:8,21`: These are the exact two lines that need changing — venv path → uv run
  - `plist:19`: PATH must include uv's location for launchd to find it
  - `run_scraper.sh`: Compare patterns to keep consistency between the two startup scripts

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: run_bot.sh uses uv instead of venv
    Tool: Bash (grep)
    Preconditions: scripts/run_bot.sh has been edited
    Steps:
      1. Run `grep -c 'venv' scripts/run_bot.sh`
      2. Assert output is 0 (no venv references remain)
      3. Run `grep 'uv run' scripts/run_bot.sh`
      4. Assert output contains 'uv run python bot.py'
      5. Run `bash -n scripts/run_bot.sh` to validate syntax
    Expected Result: No venv references, uv run present, valid bash syntax
    Failure Indicators: venv still referenced, or bash syntax error
    Evidence: .sisyphus/evidence/task-2-run-bot-sh.txt

  Scenario: plist PATH includes uv location
    Tool: Bash (grep)
    Preconditions: com.distiller.bot.plist has been edited
    Steps:
      1. Run `which uv` to get uv binary location
      2. Extract the directory from the uv path
      3. Run `grep '<string>.*uv-directory.*</string>' com.distiller.bot.plist` (substitute actual directory)
      4. Assert the PATH line includes the uv directory
      5. Run `plutil -lint com.distiller.bot.plist` to validate plist syntax
    Expected Result: PATH includes uv location, valid plist
    Failure Indicators: uv directory missing from PATH, or plutil reports errors
    Evidence: .sisyphus/evidence/task-2-plist.txt
  ```

  **Commit**: YES (groups with all tasks)
  - Files: `scripts/run_bot.sh`, `com.distiller.bot.plist`

---

- [ ] 3. **Webhook Handler Hardening (All 7 Failure Points + Health Check + Verification)**

  **What to do**:
  - **Add startup env validation** (in `create_app()` or `__main__` block):
    - Check `LINE_CHANNEL_SECRET` and `LINE_CHANNEL_ID` are non-empty
    - If missing: log `logger.error("缺少必要環境變數：LINE_CHANNEL_SECRET / LINE_CHANNEL_ID")` and `sys.exit(1)`
    - Add log at startup: `logger.info("環境變數檢查通過")`
  - **Add `GET /health` endpoint** in `create_app()`:
    - Returns `{"status": "ok", "db_exists": true/false, "token_cached": true/false}` with HTTP 200
    - Check `Path(db_path).exists()` for db_exists
    - Check `_token_cache.get("token") is not None` for token_cached
  - **Add webhook verification support** (fix Failure Point #2-adjacent):
    - In webhook handler, BEFORE signature verification, check if `events` is empty: `data = request.get_json(silent=True) or {}`; if `not data.get("events")`: return `"OK", 200` immediately
    - This handles LINE's verification probe which sends `{"events":[]}` without a signature
  - **Fix Failure Point #1** (signature verify) — improve log context:
    - Change L372: `logger.warning("簽名驗證失敗")` → `logger.warning("簽名驗證失敗（來源 IP：%s）", request.remote_addr)`
  - **Fix Failure Point #2** (malformed JSON) — add log:
    - After `data = request.get_json(silent=True) or {}`, if data is empty dict AND body is non-empty, log: `logger.warning("收到無法解析的 JSON")`
  - **Fix Failure Point #4** (token fetch) — use cached token:
    - Change L388: `token = _get_access_token(...)` → `token = _get_cached_token(...)` (from Task 1)
  - **Fix Failure Point #5** (DB missing) — add log:
    - In `_handle()`, when DB doesn't exist (L401-402), add: `logger.warning("資料庫不存在：%s", db_path)`
  - **Fix Failure Point #6 & #7** (`_reply()` improvements):
    - Change `_reply()` to return `bool` — `True` if reply succeeded, `False` otherwise
    - After `_reply()` call in webhook handler, log result: if False → `logger.error("回覆訊息失敗")`
    - In `_reply()`, add response body to the warning log for HTTP errors: include `resp.text[:200]`
  - **Failure Point #3** (DB query error) — already handled, no changes needed

  **Must NOT do**:
  - Do NOT modify `fmt_*` functions or `parse_command`
  - Do NOT add async processing or threading
  - Do NOT change existing error text strings ("查詢時發生錯誤" etc.)
  - Do NOT add new routes beyond `/health`
  - Do NOT change `_get_access_token()` function (it's wrapped by cache now)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Multiple surgical edits across bot.py — needs careful coordination and understanding of the webhook handler flow
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (sequential after Task 1)
  - **Parallel Group**: Wave 2 (solo)
  - **Blocks**: Task 4 (tests), Task 5 (verification)
  - **Blocked By**: Task 1 (needs `_get_cached_token` function)

  **References**:

  **Pattern References** (existing code to follow):
  - `bot.py:357-396` — `create_app()` + webhook handler — the MAIN function being modified. All changes go here or in functions it calls.
  - `bot.py:85-102` — `_reply()` function — changing return type to `bool`
  - `bot.py:399-428` — `_handle()` function — adding DB-missing log
  - `bot.py:435-454` — `__main__` block — startup validation goes here (before `create_app()`)
  - `bot.py:45-46` — logging setup — follow this pattern for new log calls

  **API/Type References**:
  - `bot.py:58-76` — `_get_access_token()` return type: `str | None` — `_get_cached_token()` has same contract
  - LINE verification probe payload: `{"destination": "xxx", "events": []}` — empty events array, no X-Line-Signature header

  **Test References**:
  - `tests/unit/test_bot.py:295-349` — `TestWebhook` class — existing webhook tests. New tests will extend this class.
  - `tests/unit/test_bot.py:111-113` — `_make_signature()` helper — reuse for new webhook tests

  **WHY Each Reference Matters**:
  - `bot.py:357-396`: This is the function being modified — must understand the full flow to know where to insert each fix
  - `bot.py:85-102`: `_reply()` currently returns None — changing to bool affects the webhook handler
  - `bot.py:435-454`: Startup validation must run BEFORE `create_app()` to fail fast
  - `test_bot.py:295-349`: Existing test patterns to follow for consistency

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Health check endpoint returns JSON status
    Tool: Bash (pytest or curl via Flask test client)
    Preconditions: App created with test config
    Steps:
      1. Create Flask test client
      2. Send GET /health
      3. Assert HTTP 200
      4. Assert response JSON has 'status' key with value 'ok'
      5. Assert response JSON has 'db_exists' boolean key
    Expected Result: HTTP 200, {"status": "ok", "db_exists": true/false, "token_cached": true/false}
    Failure Indicators: Non-200 status, missing keys, or non-JSON response
    Evidence: .sisyphus/evidence/task-3-health-check.txt

  Scenario: Empty events (LINE verification probe) returns 200 without signature check
    Tool: Bash (pytest)
    Preconditions: App created with test config
    Steps:
      1. Send POST /webhook with body '{"events": []}' and NO X-Line-Signature header
      2. Assert HTTP 200 (not 400)
    Expected Result: 200 OK — verification probe accepted
    Failure Indicators: 400 error (signature check ran on empty events)
    Evidence: .sisyphus/evidence/task-3-webhook-verify.txt

  Scenario: Missing env vars cause startup failure
    Tool: Bash
    Preconditions: Unset LINE_CHANNEL_SECRET and LINE_CHANNEL_ID
    Steps:
      1. Run `LINE_CHANNEL_SECRET= LINE_CHANNEL_ID= uv run python -c "from bot import create_app; create_app()"` (or similar)
      2. Assert process exits with non-zero code OR logs error about missing env vars
    Expected Result: Clear error about missing environment variables
    Failure Indicators: Bot starts silently without env vars
    Evidence: .sisyphus/evidence/task-3-startup-validation.txt

  Scenario: Webhook with invalid signature logs IP address
    Tool: Bash (pytest)
    Preconditions: App created with test config
    Steps:
      1. Send POST /webhook with bad signature
      2. Check logs contain '簽名驗證失敗' AND IP information
    Expected Result: Log includes source IP for debugging
    Failure Indicators: Log missing IP, or no log at all
    Evidence: .sisyphus/evidence/task-3-signature-log.txt
  ```

  **Commit**: YES (groups with all tasks)
  - Files: `bot.py`

---

- [ ] 4. **Tests for All New Functionality**

  **What to do**:
  - Add new test classes/methods to `tests/unit/test_bot.py`:
    - **TestTokenCache**: Test `_get_cached_token()` — first call fetches, second uses cache, expired token refetches, failed fetch returns None
    - **TestHealthCheck**: Test `GET /health` — returns 200 with JSON, contains expected keys
    - **TestWebhookVerification**: Test empty events `{"events":[]}` returns 200 without signature
    - **TestStartupValidation**: Test that `create_app()` raises/exits when env vars missing
    - **TestReplyReturnValue**: Test `_reply()` returns `True` on success, `False` on failure
    - **TestDbMissingLog**: Test `_handle()` with missing DB logs warning
  - Import `_get_cached_token` and `_token_cache` from bot module
  - Use `unittest.mock.patch` for mocking `_get_access_token`, `requests.post`, etc.
  - Follow existing test patterns in the file (fixtures, `_make_signature`, `_webhook_payload`)
  - Target: ~15-20 new test methods

  **Must NOT do**:
  - Do NOT modify existing test methods
  - Do NOT change existing fixtures (add new ones if needed)
  - Do NOT use real LINE API calls in tests
  - Do NOT import private functions that don't exist yet (check Task 1 and 3 output first)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Multiple test classes with mocking — needs attention to detail but isn't architecturally complex
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 5 (must pass before final verification)
  - **Blocked By**: Task 3 (needs all code changes completed to test against)

  **References**:

  **Pattern References** (existing tests to follow):
  - `tests/unit/test_bot.py:39-98` — Fixtures (`db_path`, `app`, `client`) — reuse these for new tests
  - `tests/unit/test_bot.py:111-123` — `_make_signature()` and `_webhook_payload()` helpers — reuse for webhook tests
  - `tests/unit/test_bot.py:295-349` — `TestWebhook` class — follow this pattern for new webhook-related tests
  - `tests/unit/test_bot.py:254-269` — `TestHandle` class — follow this pattern for _handle tests

  **API/Type References**:
  - `bot.py` after Task 1: `_get_cached_token(channel_id, channel_secret) -> str | None` and `_token_cache` dict
  - `bot.py` after Task 3: `_reply() -> bool`, `GET /health` endpoint, startup validation

  **WHY Each Reference Matters**:
  - Existing test patterns ensure consistency and use the same fixture infrastructure
  - Knowing the exact function signatures prevents import errors

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All unit tests pass including new ones
    Tool: Bash
    Preconditions: Tasks 1-3 complete, new tests written
    Steps:
      1. Run `uv run python -m pytest tests/unit/ -q`
      2. Assert exit code 0
      3. Assert total test count > 242 (new tests added)
      4. Assert 0 failures
    Expected Result: 255+ tests pass, 0 failures
    Failure Indicators: Any test failure, or test count still 242
    Evidence: .sisyphus/evidence/task-4-pytest.txt

  Scenario: New tests cover token caching behavior
    Tool: Bash (grep)
    Preconditions: test_bot.py has been updated
    Steps:
      1. Run `grep -c 'cached_token\|token_cache\|_get_cached' tests/unit/test_bot.py`
      2. Assert count >= 3 (at least 3 test methods reference caching)
    Expected Result: Multiple test methods for token caching
    Failure Indicators: No caching-related tests found
    Evidence: .sisyphus/evidence/task-4-test-coverage.txt
  ```

  **Commit**: YES (groups with all tasks)
  - Files: `tests/unit/test_bot.py`

---

- [ ] 5. **Full Verification + Commit**

  **What to do**:
  - Run full unit test suite: `uv run python -m pytest tests/unit/ -q --tb=short`
  - Verify all 7 failure points are addressed by reading `bot.py` diff
  - Verify health check works: create a quick test script or use pytest
  - Verify webhook verification works: send empty events payload
  - Verify startup validation: attempt to start with missing env vars
  - Verify `run_bot.sh` has no venv references
  - Verify `com.distiller.bot.plist` has correct PATH
  - Create single atomic commit:
    - Message: `fix(bot): add resilience — token caching, failure point fixes, health check, startup validation`
    - Files: `bot.py`, `scripts/run_bot.sh`, `com.distiller.bot.plist`, `tests/unit/test_bot.py`
    - Pre-commit: `uv run python -m pytest tests/unit/ -q`

  **Must NOT do**:
  - Do NOT push to remote (user will do this)
  - Do NOT modify any code — this is verification only + commit
  - Do NOT run integration tests (they hang — known issue)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Comprehensive verification across multiple files, must check each failure point
  - **Skills**: [`git-master`]
    - `git-master`: Need proper atomic commit with conventional message

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (after Task 4)
  - **Blocks**: F1
  - **Blocked By**: Tasks 2, 4

  **References**:

  **Pattern References**:
  - Previous commit: `e3d737d` — `fix(scraper): prevent crash on pagination fallback with existing DB data` — follow this commit style
  - `AGENTS.md` — Update with this session's work after commit

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All tests pass and commit created
    Tool: Bash
    Steps:
      1. Run `uv run python -m pytest tests/unit/ -q --tb=short`
      2. Assert 0 failures, 255+ tests
      3. Run `git diff --stat` to verify only expected files changed
      4. Run `git log -1 --oneline` to verify commit message
    Expected Result: Tests pass, commit exists with correct message and files
    Failure Indicators: Test failures, wrong files in commit, or commit not created
    Evidence: .sisyphus/evidence/task-5-final-verify.txt
  ```

  **Commit**: YES — this IS the commit task
  - Message: `fix(bot): add resilience — token caching, failure point fixes, health check, startup validation`
  - Files: `bot.py`, `scripts/run_bot.sh`, `com.distiller.bot.plist`, `tests/unit/test_bot.py`

---

## Final Verification Wave

- [ ] F1. **Plan Compliance + Code Quality Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Run `uv run python -m pytest tests/unit/ -q`. Check evidence files exist in `.sisyphus/evidence/`. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tests [N pass/N fail] | VERDICT: APPROVE/REJECT`

---

## Commit Strategy

- **Single atomic commit**: `fix(bot): add resilience — token caching, failure point fixes, health check, startup validation`
  - Files: `bot.py`, `scripts/run_bot.sh`, `com.distiller.bot.plist`, `tests/unit/test_bot.py`
  - Pre-commit: `uv run python -m pytest tests/unit/ -q`

---

## Success Criteria

### Verification Commands
```bash
uv run python -m pytest tests/unit/ -q  # Expected: all pass (242+ tests)
```

### Final Checklist
- [ ] All 7 failure points addressed
- [ ] Token caching implemented and tested
- [ ] GET /health endpoint works
- [ ] Webhook verification (empty events[]) returns 200
- [ ] Startup env validation logs results
- [ ] run_bot.sh uses uv
- [ ] plist updated
- [ ] All tests pass
- [ ] No new dependencies added
- [ ] All log messages in Chinese
