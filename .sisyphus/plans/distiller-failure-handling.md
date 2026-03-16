# Distiller Scraper — Failure Handling Overhaul

## TL;DR

> **Quick Summary**: Fix 7 identified failure-handling issues (P0-P3) in the Distiller scraper that have caused progressive degradation since Mar 11. The root cause is unhandled `document.body` null errors in `scroll_page()`, compounded by missing retry logic, no run tracking, and poor error reporting.
>
> **Deliverables**:
> - Resilient `scroll_page()` with graceful null-body handling
> - Extended `restart_driver()` triggers for JavaScript errors
> - Pre-flight health check before full scrape runs
> - Exit code propagation fix in `run_scraper.sh`
> - Page-level retry with driver restart
> - Duplicate run short-circuit to save ~13 min/day
> - `scrape_runs` table populated for run history
> - LINE notifications with error details
> - Migration of `run_scraper.sh` to `uv run` (consistency)
> - TDD test coverage for ALL new behaviors
>
> **Estimated Effort**: Medium-Large
> **Parallel Execution**: YES — 4 waves + final verification
> **Critical Path**: Task 1 → Task 2 → Task 3 → Task 8 → Task 12 → F1-F4

---

## Context

### Original Request
User asked to review the Distiller project and propose a better approach for handling scheduled crawler failures. After analysis, user approved implementing all P0-P3 recommendations with TDD.

### Interview Summary
**Key Discussions**:
- All P0-P3 issues confirmed for implementation (7 items)
- TDD approach chosen (RED → GREEN → REFACTOR)
- User deferred priority ranking to our recommendation
- Existing test infrastructure is mature (297 tests, pytest + pytest-mock)

**Research Findings**:
- **Progressive degradation, not cliff failure**: Mar 11 had 1 error + 29 successful scrapes. Mar 16 had 17 errors + 0 data. The scraper is getting worse daily, not "broken since Mar 11."
- **`restart_driver()` never triggers for the actual error**: It only matches `"invalid session id"` / `"session deleted"` strings. The real error (`"Cannot read properties of null"`) bypasses recovery entirely.
- **`storage.record_scrape_run()` and `finish_scrape_run()` already exist**: These methods are implemented in `storage.py` but never called. No new DB methods needed — just wiring.
- **`run_scraper.sh` uses `$VENV_PYTHON` while `run_bot.sh` uses `uv run`**: Inconsistency that should be fixed.
- **`scroll_page()` is called from 2 locations**: `capture_xhr_requests()` (has try/except) and `_fetch_spirit_urls_from_page()` (NO error handling). Fix must be in `scroll_page()` itself.

### Metis Review
**Identified Gaps** (addressed):
- Corrected "broken since Mar 11" → "progressively degrading" (affects urgency framing)
- Health check is defense-in-depth, NOT the primary P0 fix — `scroll_page()` error handling is the real fix
- Added fail-open policy for duplicate detection when DB is unreachable
- Added "successful run" definition for duplicate detection (completed without critical errors, regardless of new spirit count)
- Added bootstrap strategy for empty `scrape_runs` table on first instrumented run
- Added edge case: `restart_driver()` itself failing — need graceful give-up path
- Added edge case: concurrent runs (PID lockfile)
- Added edge case: LINE API down shouldn't mark scraper as failed

---

## Work Objectives

### Core Objective
Make the Distiller scraper resilient to page-load failures, enable self-recovery, reduce wasted runs, and provide meaningful failure reporting — all verified through TDD.

### Concrete Deliverables
- `distiller_scraper/scraper.py` — Modified: `scroll_page()`, `restart_driver()`, `scrape_category_paginated()`, `scrape()` (health check + retry)
- `distiller_scraper/config.py` — New parameters for retry limits, health check, restart caps
- `distiller_scraper/notify.py` — Enhanced failure notification with error details
- `run.py` — `scrape_runs` wiring + duplicate detection
- `scripts/run_scraper.sh` — Exit code fix + `uv run` migration
- `tests/unit/test_scroll_page.py` — New: dedicated scroll_page tests
- `tests/unit/test_restart_driver.py` — New: restart_driver trigger tests
- `tests/unit/test_health_check.py` — New: pre-flight health check tests
- `tests/unit/test_scrape_runs.py` — New: scrape_runs wiring tests
- `tests/unit/test_duplicate_detection.py` — New: duplicate short-circuit tests
- `tests/integration/test_retry_logic.py` — New: page-level retry tests
- Updated `tests/unit/test_notify.py` — Enhanced notification tests

### Definition of Done
- [ ] `uv run pytest --tb=short` passes with 297 + N new tests (zero failures)
- [ ] `scroll_page()` handles null `document.body` gracefully (logs warning, returns)
- [ ] `restart_driver()` triggers on JavaScript null errors (not just session errors)
- [ ] Pre-flight health check gates full scrape run
- [ ] `run_scraper.sh` propagates Python exit code through `tee` pipeline
- [ ] Page-level retry attempts driver restart before giving up
- [ ] `scrape_runs` table populated on every run (start + finish)
- [ ] Duplicate detection short-circuits when recent successful run exists
- [ ] LINE failure notifications include error count and top error message
- [ ] `run_scraper.sh` uses `uv run` (matches `run_bot.sh` convention)

### Must Have
- TDD for all behavioral changes (RED test first, then GREEN implementation)
- All existing 297 tests remain green
- Error handling in `scroll_page()` itself (not just call sites)
- Fail-open policy for duplicate detection (DB failure → proceed with scrape)
- Graceful give-up after N restart failures (don't loop forever)

### Must NOT Have (Guardrails)
- **Do NOT refactor `scroll_page()` scrolling logic** — only add error handling around `execute_script` calls
- **Do NOT replace existing `restart_driver()` triggers** — EXTEND the string match list, keep `"invalid session id"` and `"session deleted"`
- **Do NOT create new storage/DB methods** — use existing `record_scrape_run()` and `finish_scrape_run()` from `storage.py`
- **Do NOT build dashboards or analytics** on `scrape_runs` data
- **Do NOT add exponential backoff, circuit breakers, or retry middleware** — simple fixed-count retry only
- **Do NOT create new notification channels** — enhance existing `notify_failure()` error parameter
- **Do NOT rewrite `run_scraper.sh` flow** — fix exit code + migrate to `uv run`, nothing else
- **Do NOT add monitoring endpoints, health dashboards, or observability infrastructure**
- **Do NOT change `notify_success()` path** — only modify failure notification
- **Do NOT let LINE API failures mark the scraper run as failed** — notification failure is logged, not propagated

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest 9.0.2, pytest-mock 3.12.0)
- **Automated tests**: TDD (RED → GREEN → REFACTOR)
- **Framework**: pytest with `uv run pytest`
- **Each task**: Write failing test FIRST, then implement to make it pass, then refactor

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Scraper methods**: Use Bash (`uv run pytest`) — run targeted test suites
- **Shell script**: Use Bash — execute script with controlled inputs, check exit codes
- **Notifications**: Use Bash (`uv run pytest`) — mock LINE API, verify message format

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — 2 parallel tasks):
├── Task 1: Baseline test verification [quick]
└── Task 2: New config parameters for all features [quick]

Wave 2 (P0 Core + P2 Foundation — 4 parallel tasks):
├── Task 3: TDD scroll_page() error handling (depends: 2) [deep]
├── Task 4: TDD restart_driver() trigger extension (depends: 2) [deep]
├── Task 5: TDD scrape_runs wiring (depends: 2) [unspecified-high]
└── Task 6: Fix exit code in run_scraper.sh (depends: 1) [quick]

Wave 3 (P0 Defense + P1 + P2 + P3 — 4 parallel tasks):
├── Task 7: TDD pre-flight health check (depends: 3) [unspecified-high]
├── Task 8: TDD page-level retry with driver restart (depends: 3, 4) [deep]
├── Task 9: TDD duplicate run short-circuit (depends: 5) [unspecified-high]
└── Task 10: TDD LINE notifications with error details (depends: none) [unspecified-high]

Wave 4 (Polish — 2 parallel tasks):
├── Task 11: Migrate run_scraper.sh to uv run (depends: 6) [quick]
└── Task 12: Full regression + integration verification (depends: 3-11) [deep]

Wave FINAL (After ALL tasks — 4 parallel reviews):
├── F1: Plan compliance audit (oracle)
├── F2: Code quality review (unspecified-high)
├── F3: Real QA execution (unspecified-high)
└── F4: Scope fidelity check (deep)

Critical Path: Task 1 → Task 2 → Task 3 → Task 8 → Task 12 → F1-F4
Parallel Speedup: ~65% faster than sequential
Max Concurrent: 4 (Waves 2, 3, FINAL)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | — | 6 | 1 |
| 2 | — | 3, 4, 5 | 1 |
| 3 | 2 | 7, 8 | 2 |
| 4 | 2 | 8 | 2 |
| 5 | 2 | 9 | 2 |
| 6 | 1 | 11 | 2 |
| 7 | 3 | 12 | 3 |
| 8 | 3, 4 | 12 | 3 |
| 9 | 5 | 12 | 3 |
| 10 | — | 12 | 3 |
| 11 | 6 | 12 | 4 |
| 12 | 3-11 | F1-F4 | 4 |

### Agent Dispatch Summary

- **Wave 1**: **2** — T1 → `quick`, T2 → `quick`
- **Wave 2**: **4** — T3 → `deep`, T4 → `deep`, T5 → `unspecified-high`, T6 → `quick`
- **Wave 3**: **4** — T7 → `unspecified-high`, T8 → `deep`, T9 → `unspecified-high`, T10 → `unspecified-high`
- **Wave 4**: **2** — T11 → `quick`, T12 → `deep`
- **FINAL**: **4** — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

> Implementation + Test = ONE Task. TDD: RED → GREEN → REFACTOR in each task.
> EVERY task has: Recommended Agent Profile + Parallelization info + QA Scenarios.


### Wave 1 — Foundation

- [ ] 1. Baseline Test Verification

  **What to do**:
  - Run `uv run pytest --tb=short` and confirm all 297 tests pass
  - Record exact test count and timing as baseline
  - Save output to `.sisyphus/evidence/task-1-baseline.txt`
  - If any tests fail, STOP and report — do not proceed with other tasks

  **Must NOT do**:
  - Do not modify any source or test files
  - Do not "fix" any pre-existing test failures

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single command execution with output capture
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `test`: Project uses uv, not auto-detected — explicit command is clearer

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 2)
  - **Blocks**: Task 6
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `pytest.ini` — Default pytest options (`-v --tb=short -m "not slow and not network"`)

  **External References**:
  - None needed — standard pytest execution

  **WHY Each Reference Matters**:
  - `pytest.ini` tells you the default markers and options so you run the exact same suite the CI runs

  **Acceptance Criteria**:
  - [ ] `uv run pytest --tb=short` exits with code 0
  - [ ] Output shows `297 passed` (or current count)
  - [ ] Evidence file saved: `.sisyphus/evidence/task-1-baseline.txt`

  **QA Scenarios:**

  ```
  Scenario: Baseline test suite passes
    Tool: Bash
    Preconditions: Project dependencies installed (uv sync)
    Steps:
      1. Run: uv run pytest --tb=short 2>&1 | tee .sisyphus/evidence/task-1-baseline.txt
      2. Check exit code: echo $?
      3. Grep output for "passed" count: grep -oP '\d+ passed' .sisyphus/evidence/task-1-baseline.txt
    Expected Result: Exit code 0, output contains "297 passed" (or similar count, 0 failures)
    Failure Indicators: Exit code non-zero, any line containing "FAILED" or "ERROR"
    Evidence: .sisyphus/evidence/task-1-baseline.txt
  ```

  **Commit**: NO

---

- [ ] 2. Add Config Parameters for All Failure Handling Features

  **What to do**:
  - RED: Write tests in `tests/unit/test_config.py` (or add to existing) verifying new config constants exist with expected default values:
    - `MAX_SCROLL_RETRIES = 3` — max retries when scroll_page hits null body
    - `MAX_RESTART_ATTEMPTS = 2` — max driver restarts per scrape run before giving up
    - `HEALTH_CHECK_TIMEOUT = 10` — seconds to wait for health check page load
    - `PAGE_RETRY_COUNT = 2` — retries per page before skipping
    - `RESTART_TRIGGER_ERRORS` — list of error substrings that trigger driver restart (keep existing + add JS null errors)
    - `DUPLICATE_RUN_WINDOW_HOURS = 20` — hours to look back for recent successful run
  - GREEN: Add these constants to `distiller_scraper/config.py`
  - REFACTOR: Group new constants under a clear comment section (`# Failure Handling & Recovery`)

  **Must NOT do**:
  - Do not add config for things not in this plan (no monitoring, no dashboards)
  - Do not change existing config values

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple constant additions to config file + basic test assertions
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 1)
  - **Blocks**: Tasks 3, 4, 5
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `distiller_scraper/config.py:1-134` — Existing config structure and naming conventions (ALL_CAPS with descriptive comments)
  - `tests/unit/test_config.py` — If exists, follow existing test pattern; if not, create following `test_storage.py` pattern

  **API/Type References**:
  - `distiller_scraper/scraper.py:208-230` — `restart_driver()` method to understand which error strings currently trigger restart (`"invalid session id"`, `"session deleted"`)

  **WHY Each Reference Matters**:
  - `config.py` shows the naming convention (ALL_CAPS, grouped by concern, with Chinese+English comments)
  - `scraper.py:208-230` shows the existing restart trigger strings so we know what to include in `RESTART_TRIGGER_ERRORS`

  **Acceptance Criteria**:
  - [ ] RED: `uv run pytest tests/unit/test_config.py -v` shows new tests FAILING (constants don't exist yet)
  - [ ] GREEN: After adding constants, `uv run pytest tests/unit/test_config.py -v` passes
  - [ ] All 297+ tests still pass: `uv run pytest --tb=short`

  **QA Scenarios:**

  ```
  Scenario: New config constants exist with correct defaults
    Tool: Bash
    Preconditions: Task 2 implementation complete
    Steps:
      1. Run: uv run pytest tests/unit/test_config.py -v
      2. Run: uv run python -c "from distiller_scraper.config import MAX_SCROLL_RETRIES, MAX_RESTART_ATTEMPTS, HEALTH_CHECK_TIMEOUT, PAGE_RETRY_COUNT, RESTART_TRIGGER_ERRORS, DUPLICATE_RUN_WINDOW_HOURS; print(f'scroll={MAX_SCROLL_RETRIES}, restart={MAX_RESTART_ATTEMPTS}, health={HEALTH_CHECK_TIMEOUT}, retry={PAGE_RETRY_COUNT}, triggers={len(RESTART_TRIGGER_ERRORS)}, dup_window={DUPLICATE_RUN_WINDOW_HOURS}')"
    Expected Result: All tests pass; import prints "scroll=3, restart=2, health=10, retry=2, triggers=4, dup_window=20" (or similar)
    Failure Indicators: ImportError, test failures
    Evidence: .sisyphus/evidence/task-2-config-params.txt

  Scenario: Existing config unchanged
    Tool: Bash
    Preconditions: Task 2 implementation complete
    Steps:
      1. Run: uv run pytest --tb=short
      2. Verify total test count >= 297
    Expected Result: Exit code 0, no regressions
    Failure Indicators: Any previously passing test now fails
    Evidence: .sisyphus/evidence/task-2-regression.txt
  ```

  **Commit**: YES
  - Message: `feat(config): add failure handling and recovery parameters`
  - Files: `distiller_scraper/config.py`, `tests/unit/test_config.py`
  - Pre-commit: `uv run pytest --tb=short`

---

### Wave 2 — P0 Core Fixes + P2 Foundation

- [ ] 3. TDD: scroll_page() Graceful Error Handling

  **What to do**:
  - RED: Create `tests/unit/test_scroll_page.py` with these test cases:
    - `test_scroll_page_handles_null_body` — Mock `execute_script` to raise `JavascriptException("Cannot read properties of null (reading 'scrollHeight')")`. Assert: method returns gracefully (no exception), logs a warning.
    - `test_scroll_page_retries_on_null_body` — Mock `execute_script` to fail twice then succeed. Assert: scroll completes after retries, `page_errors` NOT incremented (transient error recovered).
    - `test_scroll_page_gives_up_after_max_retries` — Mock `execute_script` to always fail. Assert: method returns after `MAX_SCROLL_RETRIES` attempts, logs error, increments `page_errors`.
    - `test_scroll_page_normal_operation_unchanged` — Mock `execute_script` to return valid scroll heights. Assert: existing scrolling behavior works identically.
  - GREEN: Modify `scroll_page()` in `scraper.py`:
    - Wrap `driver.execute_script("return document.body.scrollHeight")` in try/except for `JavascriptException`
    - On catch: log warning, wait briefly, retry up to `MAX_SCROLL_RETRIES`
    - After max retries: log error, increment `self.page_errors`, return (don't raise)
    - Do NOT change the scroll loop logic itself — only guard the `execute_script` calls
  - REFACTOR: Extract retry logic into clear steps within the method

  **Must NOT do**:
  - Do NOT refactor the scrolling algorithm (scroll-wait-compare-repeat loop)
  - Do NOT change method signature or return type of `scroll_page()`
  - Do NOT add error handling at call sites — fix within `scroll_page()` itself

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Root cause fix requiring careful understanding of Selenium error types and scroll behavior
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 5, 6)
  - **Blocks**: Tasks 7, 8
  - **Blocked By**: Task 2 (needs `MAX_SCROLL_RETRIES` constant)

  **References**:

  **Pattern References**:
  - `distiller_scraper/scraper.py:174-206` — Current `scroll_page()` implementation. Lines 177 and 187 are the `execute_script` calls that fail when `document.body` is null.
  - `distiller_scraper/scraper.py:484-530` — `scrape_spirit_detail()` shows existing try/except pattern for Selenium errors (model for error handling style).
  - `tests/integration/test_pagination.py:1-60` — Mock driver fixture pattern and `patch.object` usage for Selenium mocking.

  **API/Type References**:
  - `selenium.common.exceptions.JavascriptException` — The specific exception type raised when `execute_script` fails on null `document.body`.
  - `distiller_scraper/config.py:MAX_SCROLL_RETRIES` — New constant from Task 2.

  **Test References**:
  - `tests/integration/test_pagination.py:40-60` — `mock_driver` fixture pattern: create MagicMock with spec, inject into scraper instance.

  **WHY Each Reference Matters**:
  - `scraper.py:174-206` — You need to see the exact lines where `execute_script` is called to know WHERE to add try/except.
  - `scraper.py:484-530` — Shows the project's existing error handling style (log + continue, not raise).
  - `test_pagination.py:40-60` — Shows how to create a mock driver that can simulate Selenium exceptions.

  **Acceptance Criteria**:
  - [ ] RED: `uv run pytest tests/unit/test_scroll_page.py -v` shows 4 tests FAILING
  - [ ] GREEN: After implementation, all 4 tests PASS
  - [ ] `uv run pytest --tb=short` — all 297+ tests pass (no regressions)

  **QA Scenarios:**

  ```
  Scenario: scroll_page handles null document.body gracefully
    Tool: Bash
    Preconditions: Task 3 implementation complete
    Steps:
      1. Run: uv run pytest tests/unit/test_scroll_page.py -v 2>&1 | tee .sisyphus/evidence/task-3-scroll-page.txt
      2. Verify 4 tests pass, specifically test_scroll_page_handles_null_body
      3. Run: uv run pytest --tb=short
    Expected Result: All 4 scroll_page tests pass; full suite still passes (297+ tests)
    Failure Indicators: Any test failure, ImportError, or assertion error
    Evidence: .sisyphus/evidence/task-3-scroll-page.txt

  Scenario: scroll_page retries before giving up
    Tool: Bash
    Preconditions: Task 3 implementation complete
    Steps:
      1. Run: uv run pytest tests/unit/test_scroll_page.py::TestScrollPage::test_scroll_page_retries_on_null_body -v 2>&1 | tee .sisyphus/evidence/task-3-scroll-retry.txt
      2. Verify the test asserts that execute_script was called MAX_SCROLL_RETRIES+1 times before returning
    Expected Result: Test passes, retry behavior verified
    Failure Indicators: execute_script called only once (no retry), or exception propagated
    Evidence: .sisyphus/evidence/task-3-scroll-retry.txt
  ```

  **Commit**: YES (group with Task 4)
  - Message: `fix(scraper): handle scroll_page null body and extend restart_driver triggers`
  - Files: `distiller_scraper/scraper.py`, `tests/unit/test_scroll_page.py`, `tests/unit/test_restart_driver.py`
  - Pre-commit: `uv run pytest --tb=short`

---

- [ ] 4. TDD: Extend restart_driver() Trigger Conditions

  **What to do**:
  - RED: Create `tests/unit/test_restart_driver.py` with these test cases:
    - `test_restart_triggers_on_js_null_error` — Simulate error containing `"Cannot read properties of null"`. Assert: `restart_driver()` is called.
    - `test_restart_still_triggers_on_invalid_session` — Simulate `"invalid session id"` error. Assert: existing behavior preserved, `restart_driver()` is called.
    - `test_restart_still_triggers_on_session_deleted` — Simulate `"session deleted"` error. Assert: existing behavior preserved.
    - `test_restart_gives_up_after_max_attempts` — Simulate repeated failures. Assert: after `MAX_RESTART_ATTEMPTS`, scraper logs error and stops retrying (doesn't loop forever).
    - `test_restart_resets_count_on_success` — After a successful restart and scrape, the restart counter resets.
    - `test_restart_failure_is_graceful` — If `restart_driver()` itself raises (Chrome crash), catch and log, don't propagate.
  - GREEN: Modify `scraper.py`:
    - Add `self.restart_count: int = 0` to `__init__`
    - In the error handling paths of `scrape_spirit_detail()` and `scrape_category_paginated()`, use `RESTART_TRIGGER_ERRORS` list from config instead of hardcoded strings
    - Before calling `restart_driver()`, check `self.restart_count < MAX_RESTART_ATTEMPTS`
    - If max reached: log error, set a `self.driver_failed` flag, skip remaining work gracefully
    - Wrap `restart_driver()` call in try/except — if restart itself fails, log and set `driver_failed`
  - REFACTOR: Extract the "should we restart?" decision into a helper method `_should_restart(error_msg: str) -> bool`

  **Must NOT do**:
  - Do NOT remove existing `"invalid session id"` / `"session deleted"` string checks — EXTEND the list
  - Do NOT change `restart_driver()` internals (driver quit + re-init logic) — only change WHEN it's called
  - Do NOT add exponential backoff to restart attempts — simple counter is sufficient

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Error recovery logic with multiple edge cases and state management
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 3, 5, 6)
  - **Blocks**: Task 8
  - **Blocked By**: Task 2 (needs `MAX_RESTART_ATTEMPTS`, `RESTART_TRIGGER_ERRORS`)

  **References**:

  **Pattern References**:
  - `distiller_scraper/scraper.py:208-230` — Current `restart_driver()` method. Shows driver quit + re-init flow.
  - `distiller_scraper/scraper.py:484-530` — `scrape_spirit_detail()` error handling where `restart_driver()` is currently triggered. Look for the string matching on `"invalid session id"`.
  - `distiller_scraper/scraper.py:375-440` — `scrape_category_paginated()` error handling that should ALSO trigger restart on JS errors.

  **API/Type References**:
  - `distiller_scraper/config.py:MAX_RESTART_ATTEMPTS` — New constant from Task 2.
  - `distiller_scraper/config.py:RESTART_TRIGGER_ERRORS` — New list from Task 2 containing error substrings.

  **Test References**:
  - `tests/integration/test_pagination.py:40-60` — Mock driver fixture and scraper setup pattern.

  **WHY Each Reference Matters**:
  - `scraper.py:208-230` — Shows the restart_driver internals so you know NOT to modify them, only the trigger conditions.
  - `scraper.py:484-530` — Shows where the hardcoded string matching currently lives — this is what you replace with `RESTART_TRIGGER_ERRORS`.
  - `scraper.py:375-440` — Second location where restart triggers need to be added.

  **Acceptance Criteria**:
  - [ ] RED: `uv run pytest tests/unit/test_restart_driver.py -v` shows 6 tests FAILING
  - [ ] GREEN: After implementation, all 6 tests PASS
  - [ ] `uv run pytest --tb=short` — all 297+ tests pass (no regressions)

  **QA Scenarios:**

  ```
  Scenario: restart_driver triggers on JavaScript null errors
    Tool: Bash
    Preconditions: Task 4 implementation complete
    Steps:
      1. Run: uv run pytest tests/unit/test_restart_driver.py -v 2>&1 | tee .sisyphus/evidence/task-4-restart-driver.txt
      2. Verify 6 tests pass
      3. Run: uv run pytest --tb=short
    Expected Result: All 6 restart_driver tests pass; full suite passes
    Failure Indicators: test_restart_triggers_on_js_null_error fails, existing trigger tests broken
    Evidence: .sisyphus/evidence/task-4-restart-driver.txt

  Scenario: restart gives up gracefully after max attempts
    Tool: Bash
    Preconditions: Task 4 implementation complete
    Steps:
      1. Run: uv run pytest tests/unit/test_restart_driver.py::TestRestartDriver::test_restart_gives_up_after_max_attempts -v 2>&1 | tee .sisyphus/evidence/task-4-restart-max.txt
      2. Verify the test confirms restart_driver is called exactly MAX_RESTART_ATTEMPTS times, then stops
    Expected Result: Test passes, no infinite restart loop
    Failure Indicators: restart_driver called more than MAX_RESTART_ATTEMPTS times, or exception propagated
    Evidence: .sisyphus/evidence/task-4-restart-max.txt
  ```

  **Commit**: YES (grouped with Task 3)
  - Message: `fix(scraper): handle scroll_page null body and extend restart_driver triggers`
  - Files: `distiller_scraper/scraper.py`, `tests/unit/test_scroll_page.py`, `tests/unit/test_restart_driver.py`
  - Pre-commit: `uv run pytest --tb=short`

---

- [ ] 5. TDD: Wire scrape_runs Table Recording

  **What to do**:
  - RED: Create `tests/unit/test_scrape_runs.py` with these test cases:
    - `test_scrape_run_recorded_on_start` — Mock storage. Assert: `record_scrape_run()` called at scrape start with correct parameters (mode, categories).
    - `test_scrape_run_finished_on_success` — Mock storage. Assert: `finish_scrape_run()` called with `status='completed'`, correct `spirits_count`, `duration > 0`.
    - `test_scrape_run_finished_on_failure` — Mock storage. Assert: `finish_scrape_run()` called with `status='failed'`, `error_message` contains relevant error info, `page_errors` count included.
    - `test_scrape_run_finished_on_partial_success` — Some spirits scraped but errors occurred. Assert: `status='completed_with_errors'`, both `spirits_count > 0` and `page_errors > 0` recorded.
    - `test_scrape_run_recorded_even_if_notification_fails` — LINE notification fails after scrape. Assert: `finish_scrape_run()` still called (notification failure doesn't skip recording).
  - GREEN: Modify `run.py` (in `run_full()`, `run_medium()`, `run_test()`):
    - At start: call `storage.record_scrape_run(mode=mode, categories=categories)`
    - At end (success): call `storage.finish_scrape_run(run_id, status='completed', spirits_count=len(spirits_data), page_errors=stats.get('page_errors', 0))`
    - At end (failure): call `storage.finish_scrape_run(run_id, status='failed', error_message=str(e), page_errors=stats.get('page_errors', 0))`
    - At end (partial): call with `status='completed_with_errors'`
  - REFACTOR: Create a context manager or try/finally pattern to ensure `finish_scrape_run` always executes

  **Must NOT do**:
  - Do NOT create new storage methods — use existing `record_scrape_run()` (L351) and `finish_scrape_run()` (L368) from `storage.py`
  - Do NOT add analytics queries or reporting on `scrape_runs` data
  - Do NOT modify the `scrape_runs` table schema

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Wiring existing methods across multiple functions with proper error state tracking
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 3, 4, 6)
  - **Blocks**: Task 9
  - **Blocked By**: Task 2 (needs config constants)

  **References**:

  **Pattern References**:
  - `distiller_scraper/storage.py:351-380` — `record_scrape_run()` and `finish_scrape_run()` methods. Read their signatures and parameters to know exactly what to pass.
  - `run.py:78-80` (`run_test`), `run.py:110-112` (`run_medium`), `run.py:150-152` (`run_full`) — The three run functions where wiring needs to happen. Each has a similar try/finally structure.

  **API/Type References**:
  - `distiller_scraper/storage.py:SQLiteStorage.record_scrape_run()` — Returns `run_id: int` needed for `finish_scrape_run()`.
  - `distiller_scraper/storage.py:SQLiteStorage.finish_scrape_run(run_id, status, spirits_count, error_message)` — Records completion.

  **WHY Each Reference Matters**:
  - `storage.py:351-380` — You MUST use these exact methods, not create new ones. The signatures tell you exactly what parameters to provide.
  - `run.py:78-152` — Shows where to insert the start/finish calls in each run mode. The existing try/except structure determines where finish goes.

  **Acceptance Criteria**:
  - [ ] RED: `uv run pytest tests/unit/test_scrape_runs.py -v` shows 5 tests FAILING
  - [ ] GREEN: After wiring, all 5 tests PASS
  - [ ] `uv run pytest --tb=short` — all 297+ tests pass

  **QA Scenarios:**

  ```
  Scenario: scrape_runs records start and finish
    Tool: Bash
    Preconditions: Task 5 implementation complete
    Steps:
      1. Run: uv run pytest tests/unit/test_scrape_runs.py -v 2>&1 | tee .sisyphus/evidence/task-5-scrape-runs.txt
      2. Verify 5 tests pass
      3. Run: uv run pytest --tb=short
    Expected Result: All 5 scrape_runs tests pass; full suite passes
    Failure Indicators: record_scrape_run or finish_scrape_run not called, wrong status values
    Evidence: .sisyphus/evidence/task-5-scrape-runs.txt

  Scenario: finish_scrape_run called even on error
    Tool: Bash
    Preconditions: Task 5 implementation complete
    Steps:
      1. Run: uv run pytest tests/unit/test_scrape_runs.py::TestScrapeRuns::test_scrape_run_finished_on_failure -v 2>&1 | tee .sisyphus/evidence/task-5-error-recording.txt
    Expected Result: Test passes, finish_scrape_run called with status='failed'
    Failure Indicators: finish_scrape_run not called when scraper raises exception
    Evidence: .sisyphus/evidence/task-5-error-recording.txt
  ```

  **Commit**: YES (group with Task 6)
  - Message: `feat(scraper): wire scrape_runs tracking and fix exit code propagation`
  - Files: `run.py`, `tests/unit/test_scrape_runs.py`
  - Pre-commit: `uv run pytest --tb=short`

---

- [ ] 6. Fix Exit Code Propagation in run_scraper.sh

  **What to do**:
  - Diagnose the exit code issue: `"$VENV_PYTHON" run.py ... 2>&1 | tee -a "$LOG_FILE"` pipes through `tee`, so `$?` captures `tee`'s exit code (always 0), not Python's.
  - Fix using `PIPESTATUS[0]` or process substitution:
    ```bash
    "$VENV_PYTHON" run.py ... 2>&1 | tee -a "$LOG_FILE"
    EXIT_CODE=${PIPESTATUS[0]}
    ```
  - Verify `set -o pipefail` is present (it is, but confirm it works with the `if` construct).
  - If `if` construct suppresses pipefail, restructure to run the command first, capture exit code, then branch.
  - Add a comment explaining why `PIPESTATUS[0]` is needed.

  **Must NOT do**:
  - Do NOT remove the `tee` pipeline — logging to file is important
  - Do NOT restructure the entire shell script — minimal change to fix exit code
  - Do NOT add new shell features (PID lockfile, etc.) — that's not in this task

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single shell script fix, well-understood pattern
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 3, 4, 5)
  - **Blocks**: Task 11
  - **Blocked By**: Task 1 (baseline verification)

  **References**:

  **Pattern References**:
  - `scripts/run_scraper.sh` — Full shell script. Look for the `if` block that runs `run.py` and captures exit code. The `| tee` pipeline is the problem.
  - `scripts/run_bot.sh` — Compare with bot script (already migrated to `uv run`) for reference.

  **External References**:
  - Bash `PIPESTATUS` documentation — Array capturing exit codes of each command in a pipeline.

  **WHY Each Reference Matters**:
  - `run_scraper.sh` — You need to see the exact pipeline structure to know where to insert `PIPESTATUS[0]`.
  - `run_bot.sh` — Shows the `uv run` pattern that Task 11 will migrate to — ensure exit code fix is compatible.

  **Acceptance Criteria**:
  - [ ] Shell script captures Python exit code through `tee` pipeline
  - [ ] `PIPESTATUS[0]` or equivalent used (not bare `$?`)
  - [ ] `set -o pipefail` still present
  - [ ] Logging via `tee` still works

  **QA Scenarios:**

  ```
  Scenario: Exit code propagates through tee pipeline
    Tool: Bash
    Preconditions: Task 6 implementation complete
    Steps:
      1. Create test: bash -c 'source scripts/run_scraper.sh; echo "would test exit code"' (or simpler: test the PIPESTATUS pattern directly)
      2. Run: bash -c 'set -o pipefail; (exit 1) 2>&1 | tee /dev/null; echo "PIPESTATUS=\${PIPESTATUS[0]}"'
      3. Verify PIPESTATUS[0] shows 1 (not 0)
      4. Read scripts/run_scraper.sh and verify PIPESTATUS[0] is used after the run.py pipeline
    Expected Result: PIPESTATUS captures non-zero exit code from Python
    Failure Indicators: $? or PIPESTATUS[0] shows 0 when Python exited 1
    Evidence: .sisyphus/evidence/task-6-exit-code.txt

  Scenario: tee logging still works
    Tool: Bash
    Preconditions: Task 6 implementation complete
    Steps:
      1. Grep scripts/run_scraper.sh for 'tee' to confirm logging pipeline preserved
      2. Verify the log file path is still referenced
    Expected Result: tee pipeline intact, log file path unchanged
    Failure Indicators: tee removed, log file path missing
    Evidence: .sisyphus/evidence/task-6-tee-check.txt
  ```

  **Commit**: YES (group with Task 5)
  - Message: `feat(scraper): wire scrape_runs tracking and fix exit code propagation`
  - Files: `scripts/run_scraper.sh`, `run.py`, `tests/unit/test_scrape_runs.py`
  - Pre-commit: `uv run pytest --tb=short`

---

### Wave 3 — P0 Defense + P1 + P2 + P3

- [ ] 7. TDD: Pre-flight Health Check

  **What to do**:
  - RED: Create `tests/unit/test_health_check.py` with these test cases:
    - `test_health_check_passes_on_valid_page` — Mock driver to load a page and return valid `document.body`. Assert: health check returns True, scrape proceeds.
    - `test_health_check_fails_on_null_body` — Mock driver where page loads but `document.body` is null. Assert: health check returns False, appropriate log message.
    - `test_health_check_fails_on_timeout` — Mock driver to raise `TimeoutException`. Assert: health check returns False, timeout logged.
    - `test_health_check_blocks_scrape_on_failure` — Health check returns False. Assert: `scrape()` exits early with meaningful error, doesn't attempt any categories.
    - `test_health_check_uses_config_timeout` — Assert: health check uses `HEALTH_CHECK_TIMEOUT` from config.
  - GREEN: Add `_health_check() -> bool` method to `DistillerScraperV2`:
    - Load `https://distiller.com` (or the configured base URL)
    - Wait up to `HEALTH_CHECK_TIMEOUT` seconds
    - Execute `document.body.scrollHeight` to verify body is accessible
    - Return True if successful, False on any exception
    - Call at the start of `scrape()` method, before the category loop
    - If health check fails: log error, return early from `scrape()` with failure indicators
  - REFACTOR: Keep the health check simple — ONE page load + ONE JS execution

  **Must NOT do**:
  - Do NOT add retry logic to the health check itself — it's a gate, not a recovery mechanism
  - Do NOT build a monitoring system — just a pre-flight boolean check
  - Do NOT add new endpoints or health URLs — use the existing base URL

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: New method with Selenium interactions and integration into scrape() flow
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 8, 9, 10)
  - **Blocks**: Task 12
  - **Blocked By**: Task 3 (scroll_page must be resilient first — health check is defense-in-depth)

  **References**:

  **Pattern References**:
  - `distiller_scraper/scraper.py:600-660` — `scrape()` method. This is where health check call goes (before the `for category in categories` loop).
  - `distiller_scraper/scraper.py:174-206` — `scroll_page()` for the `execute_script("return document.body.scrollHeight")` pattern to reuse in health check.
  - `distiller_scraper/scraper.py:130-170` — `start_driver()` for understanding driver initialization and page loading.

  **API/Type References**:
  - `distiller_scraper/config.py:HEALTH_CHECK_TIMEOUT` — New constant from Task 2.
  - `distiller_scraper/config.py:BASE_URL` — Base URL to load for health check.

  **WHY Each Reference Matters**:
  - `scraper.py:600-660` — You need to know the exact entry point of `scrape()` to insert the health check gate.
  - `scraper.py:174-206` — Reuse the same `execute_script` call that causes production failures — if this works, scrolling will too.

  **Acceptance Criteria**:
  - [ ] RED: `uv run pytest tests/unit/test_health_check.py -v` shows 5 tests FAILING
  - [ ] GREEN: After implementation, all 5 tests PASS
  - [ ] `uv run pytest --tb=short` — all tests pass

  **QA Scenarios:**

  ```
  Scenario: Health check gates the scrape run
    Tool: Bash
    Preconditions: Task 7 implementation complete
    Steps:
      1. Run: uv run pytest tests/unit/test_health_check.py -v 2>&1 | tee .sisyphus/evidence/task-7-health-check.txt
      2. Verify 5 tests pass, specifically test_health_check_blocks_scrape_on_failure
      3. Run: uv run pytest --tb=short
    Expected Result: All 5 health check tests pass; full suite passes
    Failure Indicators: Health check doesn't block scrape, or blocks on successful check
    Evidence: .sisyphus/evidence/task-7-health-check.txt

  Scenario: Health check timeout is configurable
    Tool: Bash
    Preconditions: Task 7 implementation complete
    Steps:
      1. Run: uv run pytest tests/unit/test_health_check.py::TestHealthCheck::test_health_check_uses_config_timeout -v 2>&1 | tee .sisyphus/evidence/task-7-timeout.txt
    Expected Result: Test passes, confirms HEALTH_CHECK_TIMEOUT from config is used
    Failure Indicators: Hardcoded timeout value instead of config constant
    Evidence: .sisyphus/evidence/task-7-timeout.txt
  ```

  **Commit**: YES (group with Task 8)
  - Message: `feat(scraper): add health check and page-level retry`
  - Files: `distiller_scraper/scraper.py`, `tests/unit/test_health_check.py`, `tests/integration/test_retry_logic.py`
  - Pre-commit: `uv run pytest --tb=short`

---

- [ ] 8. TDD: Page-Level Retry with Driver Restart

  **What to do**:
  - RED: Create `tests/integration/test_retry_logic.py` with these test cases:
    - `test_page_retry_on_scroll_failure` — Mock page that fails on first attempt (scroll error), succeeds on retry. Assert: page is retried, data extracted on second attempt.
    - `test_page_retry_triggers_driver_restart` — Mock persistent page failure. Assert: after retry fails, `restart_driver()` is called (if under `MAX_RESTART_ATTEMPTS`), then page retried once more.
    - `test_page_retry_skips_after_max_retries` — Mock page that always fails. Assert: after `PAGE_RETRY_COUNT` retries, page is skipped (not retried forever), `page_errors` incremented.
    - `test_page_retry_doesnt_retry_on_clean_empty` — Page loads fine but has no spirits (legitimate empty page). Assert: no retry triggered — retry is only for errors.
    - `test_page_retry_with_driver_failed_flag` — `self.driver_failed` is True (from Task 4). Assert: no retry attempted, page skipped immediately.
  - GREEN: Modify `scrape_category_paginated()` in `scraper.py`:
    - Wrap the inner page-fetch logic in a retry loop (up to `PAGE_RETRY_COUNT`)
    - On page failure: log warning, attempt retry
    - On second failure: if `_should_restart(error)` and `restart_count < MAX_RESTART_ATTEMPTS`, call `restart_driver()`, retry once more
    - On final failure: increment `page_errors`, break pagination for this category
    - Check `self.driver_failed` before each retry — if driver is dead, skip immediately
  - REFACTOR: Keep retry logic contained within `scrape_category_paginated()` — no external retry framework

  **Must NOT do**:
  - Do NOT add exponential backoff or circuit breaker patterns
  - Do NOT create a general retry decorator or middleware
  - Do NOT retry on legitimate empty pages — only on errors/exceptions

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex interaction between retry logic, driver restart state, and pagination flow
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 7, 9, 10)
  - **Blocks**: Task 12
  - **Blocked By**: Tasks 3, 4 (needs scroll_page fix and restart_driver extension)

  **References**:

  **Pattern References**:
  - `distiller_scraper/scraper.py:375-440` — Current `scrape_category_paginated()`. This is where retry logic wraps around the existing page-fetch code.
  - `distiller_scraper/scraper.py:287-330` — `_fetch_spirit_urls_from_page()` — the method that actually loads and parses a page. Retry wraps around calls to this.
  - `distiller_scraper/scraper.py:208-230` — `restart_driver()` and the new `_should_restart()` helper from Task 4.

  **API/Type References**:
  - `distiller_scraper/config.py:PAGE_RETRY_COUNT` — New constant from Task 2.
  - `distiller_scraper/config.py:MAX_RESTART_ATTEMPTS` — Used to check restart budget.

  **WHY Each Reference Matters**:
  - `scraper.py:375-440` — The exact method where retry logic must be inserted. You need to understand the existing pagination loop to wrap retry around the right parts.
  - `scraper.py:287-330` — The method being retried. Understanding its error behavior tells you what exceptions to catch.
  - `scraper.py:208-230` — Integration point — retry calls restart_driver when simple retry isn't enough.

  **Acceptance Criteria**:
  - [ ] RED: `uv run pytest tests/integration/test_retry_logic.py -v` shows 5 tests FAILING
  - [ ] GREEN: After implementation, all 5 tests PASS
  - [ ] `uv run pytest --tb=short` — all tests pass

  **QA Scenarios:**

  ```
  Scenario: Page retry recovers from transient failure
    Tool: Bash
    Preconditions: Task 8 implementation complete
    Steps:
      1. Run: uv run pytest tests/integration/test_retry_logic.py -v 2>&1 | tee .sisyphus/evidence/task-8-retry-logic.txt
      2. Verify 5 tests pass, specifically test_page_retry_on_scroll_failure
      3. Run: uv run pytest --tb=short
    Expected Result: All 5 retry logic tests pass; full suite passes
    Failure Indicators: Page not retried on failure, or retried on legitimate empty page
    Evidence: .sisyphus/evidence/task-8-retry-logic.txt

  Scenario: Retry respects driver_failed flag
    Tool: Bash
    Preconditions: Task 8 implementation complete
    Steps:
      1. Run: uv run pytest tests/integration/test_retry_logic.py::TestRetryLogic::test_page_retry_with_driver_failed_flag -v 2>&1 | tee .sisyphus/evidence/task-8-driver-failed.txt
    Expected Result: Test passes, no retry attempted when driver_failed=True
    Failure Indicators: Retry attempted despite driver being dead
    Evidence: .sisyphus/evidence/task-8-driver-failed.txt
  ```

  **Commit**: YES (grouped with Task 7)
  - Message: `feat(scraper): add health check and page-level retry`
  - Files: `distiller_scraper/scraper.py`, `tests/unit/test_health_check.py`, `tests/integration/test_retry_logic.py`
  - Pre-commit: `uv run pytest --tb=short`

---

- [ ] 9. TDD: Duplicate Run Short-Circuit

  **What to do**:
  - RED: Create `tests/unit/test_duplicate_detection.py` with these test cases:
    - `test_skips_when_recent_successful_run` — Mock `scrape_runs` table with a successful run 2 hours ago. Assert: scraper exits early with log "Recent successful run found, skipping".
    - `test_proceeds_when_no_recent_run` — Mock empty `scrape_runs` table. Assert: scraper proceeds normally (bootstrap case).
    - `test_proceeds_when_recent_run_failed` — Mock `scrape_runs` with a failed run 2 hours ago. Assert: scraper proceeds (failed runs don't count as successful).
    - `test_proceeds_when_run_is_old` — Mock `scrape_runs` with a successful run 24 hours ago (outside `DUPLICATE_RUN_WINDOW_HOURS`). Assert: scraper proceeds.
    - `test_proceeds_when_db_check_fails` — Mock `scrape_runs` query to raise `sqlite3.Error`. Assert: scraper proceeds (fail-open policy), logs warning.
    - `test_partial_success_counts_as_successful` — Mock `scrape_runs` with `status='completed_with_errors'`. Assert: treated as successful, skips re-run.
  - GREEN: Add duplicate detection logic to `run.py` (or a helper in `scraper.py`):
    - Before starting scrape, query `scrape_runs` for most recent run with `status IN ('completed', 'completed_with_errors')` within `DUPLICATE_RUN_WINDOW_HOURS`
    - If found: log "Recent successful run found at {timestamp}, skipping", exit 0 (success, not failure)
    - If DB query fails: log warning, proceed with scrape (fail-open)
    - If no recent successful run: proceed normally
  - REFACTOR: Extract into a `_should_skip_run(storage) -> bool` function

  **Must NOT do**:
  - Do NOT fail-closed (DB error should NOT prevent scraping)
  - Do NOT check for "any run" — only successful runs count
  - Do NOT add complex scheduling logic — simple time-window check
  - Do NOT prevent the first-ever run (empty table = proceed)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: DB query + time comparison + fail-open policy with edge cases
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 7, 8, 10)
  - **Blocks**: Task 12
  - **Blocked By**: Task 5 (needs `scrape_runs` table populated)

  **References**:

  **Pattern References**:
  - `distiller_scraper/storage.py:351-380` — `record_scrape_run()` and `finish_scrape_run()`. Understand the table schema to know what columns to query.
  - `run.py:150-220` — `run_full()` function. The duplicate check goes at the TOP, before scraper initialization.

  **API/Type References**:
  - `distiller_scraper/config.py:DUPLICATE_RUN_WINDOW_HOURS` — New constant from Task 2.
  - SQLite `scrape_runs` table schema — columns: `id, started_at, finished_at, status, spirits_count, error_message`.

  **WHY Each Reference Matters**:
  - `storage.py:351-380` — Shows the exact column names and types in `scrape_runs` so your query matches.
  - `run.py:150-220` — Shows where to insert the early-exit check (before `DistillerScraperV2()` instantiation).

  **Acceptance Criteria**:
  - [ ] RED: `uv run pytest tests/unit/test_duplicate_detection.py -v` shows 6 tests FAILING
  - [ ] GREEN: After implementation, all 6 tests PASS
  - [ ] `uv run pytest --tb=short` — all tests pass

  **QA Scenarios:**

  ```
  Scenario: Duplicate detection short-circuits on recent success
    Tool: Bash
    Preconditions: Task 9 implementation complete
    Steps:
      1. Run: uv run pytest tests/unit/test_duplicate_detection.py -v 2>&1 | tee .sisyphus/evidence/task-9-duplicate-detection.txt
      2. Verify 6 tests pass
      3. Run: uv run pytest --tb=short
    Expected Result: All 6 duplicate detection tests pass; full suite passes
    Failure Indicators: Scraper runs despite recent successful run, or DB error blocks scraping
    Evidence: .sisyphus/evidence/task-9-duplicate-detection.txt

  Scenario: Fail-open on DB error
    Tool: Bash
    Preconditions: Task 9 implementation complete
    Steps:
      1. Run: uv run pytest tests/unit/test_duplicate_detection.py::TestDuplicateDetection::test_proceeds_when_db_check_fails -v 2>&1 | tee .sisyphus/evidence/task-9-failopen.txt
    Expected Result: Test passes, scraper proceeds when DB query raises exception
    Failure Indicators: Exception propagated, scraper aborts on DB error
    Evidence: .sisyphus/evidence/task-9-failopen.txt
  ```

  **Commit**: YES (group with Task 10)
  - Message: `feat(scraper): duplicate detection short-circuit and enhanced notifications`
  - Files: `run.py`, `distiller_scraper/notify.py`, `tests/unit/test_duplicate_detection.py`, `tests/unit/test_notify.py`
  - Pre-commit: `uv run pytest --tb=short`

---

- [ ] 10. TDD: Enhanced LINE Failure Notifications

  **What to do**:
  - RED: Add tests to existing `tests/unit/test_notify.py`:
    - `test_failure_notification_includes_error_details` — Call `notify_failure()` with error details. Assert: LINE message body contains error count and top error message.
    - `test_failure_notification_includes_page_errors` — Pass `page_errors=17` to failure notification. Assert: message includes "17 page errors" or similar.
    - `test_failure_notification_truncates_long_errors` — Pass a 1000-char error string. Assert: message is truncated to fit LINE message limits (not over 2000 chars total).
    - `test_notification_failure_does_not_propagate` — Mock LINE API to fail (DNS error). Assert: `notify_failure()` returns False, does NOT raise exception.
    - `test_success_notification_unchanged` — Assert: `notify_success()` signature and behavior unchanged from current implementation.
  - GREEN: Modify `distiller_scraper/notify.py`:
    - Enhance `notify_failure()` to accept optional `page_errors: int = 0` and `error_details: str = ""` parameters
    - Format error details into the LINE message template (append to existing format)
    - Truncate `error_details` if message would exceed LINE limits
    - Ensure `notify_failure()` never raises — always returns bool
  - Update callers in `run.py` to pass error details:
    - In failure path: `notifier.notify_failure(error=str(e), page_errors=stats.get('page_errors', 0), error_details=top_error_message)`
  - REFACTOR: Keep message formatting simple — no HTML, no rich formatting

  **Must NOT do**:
  - Do NOT change `notify_success()` — only modify failure notifications
  - Do NOT create new notification channels (email, Slack, etc.)
  - Do NOT add error classification or categorization system
  - Do NOT let notification failure affect the scraper's exit code

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Modifying notification formatting + updating callers + message length handling
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 7, 8, 9)
  - **Blocks**: Task 12
  - **Blocked By**: None (can start immediately, but grouped in Wave 3 for commit strategy)

  **References**:

  **Pattern References**:
  - `distiller_scraper/notify.py:1-140` — Full notification module. Focus on `notify_failure()` method signature and message formatting.
  - `tests/unit/test_notify.py` — Existing notification tests (22 tests). Add new tests following the same pattern.
  - `run.py:203-223` — Where `notify_failure()` is called. This is where you pass the new parameters.

  **API/Type References**:
  - LINE Messaging API — Text message max length is 5000 characters. Keep messages well under this.
  - `distiller_scraper/notify.py:notify_failure(error: str = "")` — Current signature to extend.

  **WHY Each Reference Matters**:
  - `notify.py` — You need to see the current message template to know where to insert error details without breaking the format.
  - `test_notify.py` — Follow the exact same mock and assertion patterns for new tests.
  - `run.py:203-223` — The caller that needs updating to pass the new parameters.

  **Acceptance Criteria**:
  - [ ] RED: New tests in `test_notify.py` FAIL
  - [ ] GREEN: After implementation, all tests PASS (22 existing + 5 new = 27)
  - [ ] `uv run pytest --tb=short` — all tests pass

  **QA Scenarios:**

  ```
  Scenario: Failure notification includes error details
    Tool: Bash
    Preconditions: Task 10 implementation complete
    Steps:
      1. Run: uv run pytest tests/unit/test_notify.py -v 2>&1 | tee .sisyphus/evidence/task-10-notifications.txt
      2. Verify 27+ tests pass (22 existing + 5 new)
      3. Run: uv run pytest --tb=short
    Expected Result: All notification tests pass; full suite passes
    Failure Indicators: New tests fail, existing tests broken, notify_success changed
    Evidence: .sisyphus/evidence/task-10-notifications.txt

  Scenario: Notification failure doesn't propagate
    Tool: Bash
    Preconditions: Task 10 implementation complete
    Steps:
      1. Run: uv run pytest tests/unit/test_notify.py::TestLineNotifier::test_notification_failure_does_not_propagate -v 2>&1 | tee .sisyphus/evidence/task-10-no-propagate.txt
    Expected Result: Test passes, notify_failure returns False on LINE API error
    Failure Indicators: Exception raised when LINE API fails
    Evidence: .sisyphus/evidence/task-10-no-propagate.txt
  ```

  **Commit**: YES (grouped with Task 9)
  - Message: `feat(scraper): duplicate detection short-circuit and enhanced notifications`
  - Files: `run.py`, `distiller_scraper/notify.py`, `tests/unit/test_duplicate_detection.py`, `tests/unit/test_notify.py`
  - Pre-commit: `uv run pytest --tb=short`

---

### Wave 4 — Polish

- [ ] 11. Migrate run_scraper.sh to uv run

  **What to do**:
  - Replace `$VENV_PYTHON` / `"$PROJECT_DIR/venv/bin/python"` with `uv run python` throughout `scripts/run_scraper.sh`
  - Ensure environment activation is handled by `uv run` (no explicit `source venv/bin/activate`)
  - Verify `PATH` includes `uv` location in `com.distiller.scraper.plist` (check `/Users/Henry/.local/bin` is in PATH, same as `com.distiller.bot.plist`)
  - Update the plist if needed to match `run_bot.sh` / `com.distiller.bot.plist` pattern
  - Ensure the exit code fix from Task 6 still works with `uv run`

  **Must NOT do**:
  - Do NOT change the scraper's execution logic — only the invocation method
  - Do NOT modify `run.py` — this is shell script only
  - Do NOT add new features to the shell script

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple search-and-replace in shell script + plist PATH update
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Task 12)
  - **Blocks**: Task 12
  - **Blocked By**: Task 6 (exit code fix must be in place)

  **References**:

  **Pattern References**:
  - `scripts/run_bot.sh` — Already migrated to `uv run`. Use this as the exact pattern to follow.
  - `scripts/run_scraper.sh` — Current script using `$VENV_PYTHON`. Replace `$VENV_PYTHON` with `uv run python`.
  - `com.distiller.bot.plist` — Already has updated PATH with `/Users/Henry/.local/bin`. Copy this PATH pattern.
  - `com.distiller.scraper.plist` — May need PATH update to include uv location.

  **WHY Each Reference Matters**:
  - `run_bot.sh` — The "after" state — copy this pattern exactly for consistency.
  - `run_scraper.sh` — The "before" state — know what to replace.
  - Both plists — Ensure PATH consistency so `uv` is found at runtime by launchd.

  **Acceptance Criteria**:
  - [ ] `scripts/run_scraper.sh` uses `uv run` instead of `$VENV_PYTHON`
  - [ ] No references to `venv/bin/python` or `$VENV_PYTHON` remain in the script
  - [ ] `com.distiller.scraper.plist` PATH includes `/Users/Henry/.local/bin`
  - [ ] PIPESTATUS fix from Task 6 still works with `uv run`

  **QA Scenarios:**

  ```
  Scenario: run_scraper.sh uses uv run
    Tool: Bash
    Preconditions: Task 11 implementation complete
    Steps:
      1. Grep: grep -c 'VENV_PYTHON\|venv/bin/python' scripts/run_scraper.sh
      2. Grep: grep -c 'uv run' scripts/run_scraper.sh
      3. Grep: grep 'local/bin' com.distiller.scraper.plist
    Expected Result: Step 1 returns 0 (no old references), Step 2 returns >= 1, Step 3 shows /Users/Henry/.local/bin in PATH
    Failure Indicators: Old venv references remain, uv run not found, PATH missing
    Evidence: .sisyphus/evidence/task-11-uv-migration.txt

  Scenario: Exit code fix still works with uv run
    Tool: Bash
    Preconditions: Task 11 implementation complete
    Steps:
      1. Grep: grep 'PIPESTATUS' scripts/run_scraper.sh
      2. Verify PIPESTATUS usage is compatible with uv run pipeline
    Expected Result: PIPESTATUS still used after uv run pipeline
    Failure Indicators: PIPESTATUS removed or incompatible
    Evidence: .sisyphus/evidence/task-11-exitcode.txt
  ```

  **Commit**: YES (group with Task 12)
  - Message: `chore(scripts): migrate run_scraper.sh to uv run and full regression verification`
  - Files: `scripts/run_scraper.sh`, `com.distiller.scraper.plist`
  - Pre-commit: `uv run pytest --tb=short`

---

- [ ] 12. Full Regression + Integration Verification

  **What to do**:
  - Run the COMPLETE test suite: `uv run pytest -v --tb=short`
  - Verify total test count: should be 297 (original) + ~31 new tests (4+6+5+5+6+5 from Tasks 3,4,5,7,8,9,10)
  - Run with coverage to identify any missed paths: `uv run pytest --cov=distiller_scraper --cov-report=term-missing`
  - Verify cross-task integration by reviewing that:
    - scroll_page error → page_errors increment → restart_driver trigger → retry logic → scrape_runs records failure → notification includes error details
    - This chain works end-to-end in the test suite (each link is tested individually, verify no gaps)
  - Run a dry import test: `uv run python -c "from distiller_scraper.scraper import DistillerScraperV2; print('Import OK')"` to ensure no circular imports
  - Save full test output and coverage report as evidence

  **Must NOT do**:
  - Do NOT run the actual scraper against distiller.com — tests only
  - Do NOT modify any source code — this is verification only
  - Do NOT skip failing tests — all must pass

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Comprehensive verification requiring analysis of test output and coverage gaps
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (after all implementation tasks)
  - **Blocks**: F1-F4 (Final Verification Wave)
  - **Blocked By**: Tasks 3-11 (all implementation tasks must be complete)

  **References**:

  **Pattern References**:
  - `.sisyphus/evidence/task-1-baseline.txt` — Compare baseline test count with final count to verify all new tests are present.
  - All test files from Tasks 3-10 — Verify they exist and are collected by pytest.

  **WHY Each Reference Matters**:
  - Baseline evidence — Proves we started green and stayed green throughout.
  - Test file existence — Confirms every task actually delivered its test artifacts.

  **Acceptance Criteria**:
  - [ ] `uv run pytest --tb=short` — ALL tests pass (0 failures)
  - [ ] Test count >= 328 (297 original + 31 new)
  - [ ] `uv run python -c "from distiller_scraper.scraper import DistillerScraperV2"` — no import errors
  - [ ] Coverage report generated and saved

  **QA Scenarios:**

  ```
  Scenario: Full test suite passes with all new tests
    Tool: Bash
    Preconditions: Tasks 3-11 all complete
    Steps:
      1. Run: uv run pytest -v --tb=short 2>&1 | tee .sisyphus/evidence/task-12-full-regression.txt
      2. Verify exit code 0
      3. Count tests: grep -oP '\d+ passed' .sisyphus/evidence/task-12-full-regression.txt
      4. Verify count >= 328
    Expected Result: All tests pass, count >= 328, 0 failures, 0 errors
    Failure Indicators: Any FAILED or ERROR in output, count < 328
    Evidence: .sisyphus/evidence/task-12-full-regression.txt

  Scenario: No import errors in modified modules
    Tool: Bash
    Preconditions: Tasks 3-11 all complete
    Steps:
      1. Run: uv run python -c "from distiller_scraper.scraper import DistillerScraperV2; from distiller_scraper.notify import LineNotifier; from distiller_scraper.config import MAX_SCROLL_RETRIES, MAX_RESTART_ATTEMPTS; print('All imports OK')"
    Expected Result: Prints 'All imports OK' with no errors
    Failure Indicators: ImportError, circular import, missing attribute
    Evidence: .sisyphus/evidence/task-12-imports.txt

  Scenario: Coverage report generated
    Tool: Bash
    Preconditions: Tasks 3-11 all complete
    Steps:
      1. Run: uv run pytest --cov=distiller_scraper --cov-report=term-missing 2>&1 | tee .sisyphus/evidence/task-12-coverage.txt
    Expected Result: Coverage report printed, all modified files show coverage
    Failure Indicators: Coverage tool not installed, modified files at 0% coverage
    Evidence: .sisyphus/evidence/task-12-coverage.txt
  ```

  **Commit**: YES (grouped with Task 11)
  - Message: `chore(scripts): migrate run_scraper.sh to uv run and full regression verification`
  - Files: (no new files — verification only)
  - Pre-commit: `uv run pytest --tb=short`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in `.sisyphus/evidence/`. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `uv run pytest --tb=short` + check for: `# type: ignore` additions, bare `except:`, `pass` in except blocks, unused imports, commented-out code. Check AI slop: excessive comments, over-abstraction, generic variable names (data/result/item/temp). Verify all new test files follow existing patterns (class-based, fixtures, MagicMock with spec=).
  Output: `Tests [N pass/N fail] | Quality Issues [N] | Slop Score [low/med/high] | VERDICT`

- [ ] F3. **Real QA Execution** — `unspecified-high`
  Execute EVERY QA scenario from EVERY task. Follow exact steps. Capture evidence. Test cross-task integration: does scroll_page error → restart_driver trigger → retry → scrape_runs record the failure? Test the notification chain. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (`git log`/`diff`). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination: Task N touching Task M's files. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| After | Message | Key Files | Pre-commit |
|-------|---------|-----------|------------|
| Task 2 | `feat(config): add failure handling parameters` | `config.py` | `uv run pytest` |
| Tasks 3-4 | `fix(scraper): handle scroll_page null body and extend restart_driver triggers` | `scraper.py`, `test_scroll_page.py`, `test_restart_driver.py` | `uv run pytest` |
| Tasks 5-6 | `feat(scraper): wire scrape_runs tracking and fix exit code propagation` | `run.py`, `run_scraper.sh`, `test_scrape_runs.py` | `uv run pytest` |
| Tasks 7-8 | `feat(scraper): add health check and page-level retry` | `scraper.py`, `test_health_check.py`, `test_retry_logic.py` | `uv run pytest` |
| Tasks 9-10 | `feat(scraper): duplicate detection short-circuit and enhanced notifications` | `run.py`, `notify.py`, `test_duplicate_detection.py`, `test_notify.py` | `uv run pytest` |
| Tasks 11-12 | `chore(scripts): migrate to uv run and full regression verification` | `run_scraper.sh` | `uv run pytest` |

---

## Success Criteria

### Verification Commands
```bash
uv run pytest --tb=short           # Expected: ALL pass (297 + N new tests)
uv run pytest tests/unit/ -v       # Expected: All new unit tests pass
uv run pytest tests/integration/ -v # Expected: All integration tests pass
bash scripts/run_scraper.sh --dry-run 2>/dev/null; echo $?  # Expected: 0 (if supported)
```

### Final Checklist
- [ ] All "Must Have" present and verified
- [ ] All "Must NOT Have" absent (searched codebase)
- [ ] All 297 original tests still pass
- [ ] All new TDD tests pass
- [ ] Evidence files exist in `.sisyphus/evidence/`
- [ ] No AI slop (excessive comments, over-abstraction, generic names)
