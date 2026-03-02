# Scraper Resilience Fix — 分頁 Fallback 崩潰修復

## TL;DR

> **Quick Summary**: Fix 3 interrelated bugs in `scraper.py` that cause the scraper to crash with 0 data when all URLs already exist in the database. The root cause is a misdiagnosis chain: existing data → 100% duplicate rate → wrong "pagination broken" conclusion → unprotected scroll fallback → Selenium timeout → unhandled exception → entire scraper dies.
>
> **Deliverables**:
> - Bug 3 fixed: Distinguish "already scraped" from "pagination broken" in duplicate detection logic
> - Bug 1 fixed: Scroll fallback wrapped in try/except so timeouts don't crash the scraper
> - Bug 2 fixed: Per-category error isolation so one category failure doesn't kill subsequent categories
> - All 277 existing tests still pass
> - Scraper runs successfully in medium mode with existing DB data (1027 spirits)
>
> **Estimated Effort**: Quick (3 focused changes in 1 file)
> **Parallel Execution**: NO — sequential (all in same file, logically dependent)
> **Critical Path**: Task 1 (Bug 3) → Task 2 (Bug 1) → Task 3 (Bug 2) → Task 4 (verify)

---

## Context

### Original Request
User ran scraper in medium mode (`uv run python run.py --mode medium --output both`). It crashed after 90 seconds with 0 data collected. Root cause analysis identified 3 bugs forming a failure chain in `distiller_scraper/scraper.py`.

### Crash Log Evidence
From `logs/medium_run_20260301_192601.log`:
- Category "Whiskey" starts → page 1 loads 24 URLs → **100% duplicate rate** (all exist in DB)
- Misdiagnosed as "分頁無效" → triggers scroll fallback
- `_fetch_spirit_urls_from_page()` timeout → **unhandled exception** → scraper crashes
- All subsequent categories (Rum, Tequila, etc.) never execute

### Failure Chain
```
distiller.db has 1027 URLs
  → seen_urls pre-populated (L59-61)
  → Page 1: 24 URLs, ALL already in seen_urls
  → duplicate_ratio = 100%, new_urls = 0
  → L370-371: page >= 2 check FAILS (page=1), falls through
  → L365: page == 2 check triggers on page 2
  → Page 2: also 100% duplicate → L370: not pagination_works → "分頁無效"
  → L374: _fetch_spirit_urls_from_page() called (scroll fallback)
  → Selenium timeout (56.9s) → UNHANDLED EXCEPTION
  → L573: outer catch kills entire scraper → return False
```

### Gap Analysis (Self-Performed)
**Identified gaps addressed in plan:**
- Edge case: empty DB (no duplicates) — must still work normally ✅
- Edge case: partial duplicates (mix of new + existing) — pagination should continue ✅
- Edge case: full duplicates but pagination IS working (page 2 has different-but-seen URLs) ✅
- `get_existing_urls()` URL format matches `seen_urls` format — verified at L59-61 ✅

---

## Work Objectives

### Core Objective
Make the scraper resilient to pre-existing data in the database. When all URLs are already scraped, it should skip gracefully — not crash.

### Concrete Deliverables
- Modified `distiller_scraper/scraper.py` (3 surgical changes, ~20 lines total)

### Definition of Done
- [ ] `uv run python -m pytest` → 277 passed, 0 failed
- [ ] `uv run python run.py --mode medium --output both` → completes without crash, handles existing data gracefully

### Must Have
- Graceful skip when category data already fully scraped
- Error isolation: one category failure cannot kill other categories
- Scroll fallback protected by try/except
- Clear log messages distinguishing "already scraped" from "pagination broken"

### Must NOT Have (Guardrails)
- No changes to pagination logic beyond the duplicate detection fix
- No changes to any file other than `scraper.py`
- No new dependencies
- No refactoring of method signatures or class structure
- No changes to config constants
- No "improvement" to logging beyond the specific new messages needed
- No retry logic (out of scope — separate concern)

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed.

### Test Decision
- **Infrastructure exists**: YES (pytest, 277 tests)
- **Automated tests**: Tests-after (run existing tests; no new unit tests needed for these surgical fixes)
- **Framework**: pytest via `uv run python -m pytest`

### QA Policy
Every task includes agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **CLI verification**: Use Bash — run scraper, check logs, verify exit code
- **Test verification**: Use Bash — run pytest, verify pass count

---

## Execution Strategy

### Sequential Execution (Single File)

All changes are in `scraper.py` and logically dependent. Tasks execute sequentially.

```
Task 1: Fix Bug 3 — Duplicate detection logic (L355-378)
  ↓
Task 2: Fix Bug 1 — Wrap scroll fallback in try/except (L372-378)
  ↓
Task 3: Fix Bug 2 — Per-category error isolation (L541-575)
  ↓
Task 4: Full verification — tests + live run
```

### Agent Dispatch Summary

- **Task 1**: `quick` — Small logic change (~8 lines)
- **Task 2**: `quick` — Add try/except wrapper (~5 lines)
- **Task 3**: `quick` — Move try/except inside loop (~5 lines)
- **Task 4**: `deep` — End-to-end verification with evidence capture

---

## TODOs

- [ ] 1. Fix Bug 3: Distinguish "already scraped" from "pagination broken"

  **What to do**:
  - In `scrape_category_paginated()` at L370-378, before concluding "分頁無效", check whether the high duplicate rate is because URLs already exist in the database (i.e., they're in `self.seen_urls` which was pre-loaded from storage at L59-61)
  - If ALL URLs on page 1 are already in `seen_urls` AND `self.storage` exists, this means the category is already scraped — log "此類別資料已存在於資料庫，跳過" and `break` without triggering scroll fallback
  - Only fall through to scroll fallback if duplicates are from the *current session* (URLs seen during this run, not pre-loaded from DB)
  - Implementation approach: Before the pagination loop (around L336), snapshot the DB URLs: `db_urls = self.storage.get_existing_urls() if self.storage else set()`. Then at L371, if `not pagination_works` and all `urls_on_page` are in `db_urls`, log skip message and break. Otherwise proceed with existing scroll fallback logic.
  - Simplest alternative: At L371, add a check — if `self.storage` and `all(u in self.storage.get_existing_urls() for u in urls_on_page)`, log and break. But calling `get_existing_urls()` per page is wasteful. Prefer snapshotting once before the loop.

  **Must NOT do**:
  - Do not change how `seen_urls` is populated
  - Do not change `get_existing_urls()` or `storage.py`
  - Do not add new class attributes

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small, focused logic change in one location (~8 lines added)
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (Task 1 of 4)
  - **Blocks**: Task 2, Task 3, Task 4
  - **Blocked By**: None

  **References**:

  **Pattern References** (existing code to follow):
  - `distiller_scraper/scraper.py:59-61` — `seen_urls` initialization from storage; shows that DB URLs are loaded at construction time
  - `distiller_scraper/scraper.py:355-357` — `new_urls` calculation and `duplicate_ratio`; this is where duplicates are detected
  - `distiller_scraper/scraper.py:364-378` — Current pagination validity logic; the exact code to modify
  - `distiller_scraper/scraper.py:336` — `pagination_works = False` initialization; context for the pagination state machine

  **API/Type References**:
  - `distiller_scraper/storage.py:115` — `get_existing_urls() -> Set[str]` abstract method; returns URL strings in same format as `seen_urls`

  **External References**:
  - `logs/medium_run_20260301_192601.log` — Crash log showing the exact failure sequence (100% duplicate → misdiagnosis → crash)

  **WHY Each Reference Matters**:
  - L59-61: Shows that `seen_urls` contains BOTH DB URLs and session URLs — you need to distinguish between them
  - L355-357: Shows how `new_urls` is calculated — your fix needs to add a parallel check against DB-only URLs
  - L364-378: The exact code block to modify — understand the current flow before changing it
  - Storage L115: Confirms `get_existing_urls()` returns `Set[str]` — safe to use for set operations

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Category with all data already in DB is skipped gracefully
    Tool: Bash
    Preconditions: distiller.db contains 1027 existing spirits
    Steps:
      1. Run: uv run python -c "
         from distiller_scraper.scraper import DistillerScraperV2
         from distiller_scraper.storage import SQLiteStorage
         storage = SQLiteStorage('distiller.db')
         scraper = DistillerScraperV2(storage=storage)
         print(f'seen_urls count: {len(scraper.seen_urls)}')
         print('PASS: seen_urls loaded from DB')
         storage.close()"
      2. Verify output contains "seen_urls count: 1027" (or close to it)
      3. Verify output contains "PASS"
    Expected Result: seen_urls is pre-populated from DB, confirming the precondition
    Failure Indicators: seen_urls count is 0, or import error
    Evidence: .sisyphus/evidence/task-1-seen-urls-preload.txt

  Scenario: Existing pytest suite still passes after Bug 3 fix
    Tool: Bash
    Preconditions: Bug 3 fix applied to scraper.py
    Steps:
      1. Run: uv run python -m pytest tests/ -v --tb=short 2>&1
      2. Count passed/failed tests
    Expected Result: 277 passed, 0 failed (or more passed if new tests added)
    Failure Indicators: Any test failure or error
    Evidence: .sisyphus/evidence/task-1-pytest.txt
  ```

  **Commit**: YES
  - Message: `fix(scraper): distinguish already-scraped from pagination-broken in duplicate detection`
  - Files: `distiller_scraper/scraper.py`
  - Pre-commit: `uv run python -m pytest tests/ -q`

---

- [ ] 2. Fix Bug 1: Wrap scroll fallback in try/except

  **What to do**:
  - At L372-375 (after Task 1's changes, line numbers may shift), the scroll fallback calls `self._fetch_spirit_urls_from_page(base_url)` and `self._scrape_urls()` without any error handling
  - Wrap both calls in a try/except block that catches `Exception`, logs the error with `logger.warning()`, and continues (break from pagination loop)
  - The error message should clearly indicate the scroll fallback failed: "滾動模式 fallback 失敗: {e}"
  - Note: After Task 1's fix, this scroll fallback should rarely trigger (since "already scraped" is now detected). But this is a safety net for genuine pagination failures.

  **Must NOT do**:
  - Do not add retry logic
  - Do not change the scroll fallback behavior when it succeeds
  - Do not catch specific exception types (keep broad `Exception` to match existing pattern at L346)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Adding a try/except wrapper around 2 existing lines
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (Task 2 of 4)
  - **Blocks**: Task 3, Task 4
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `distiller_scraper/scraper.py:344-348` — Existing try/except pattern for `_fetch_spirit_urls()` on the same method; follow this exact style for consistency
  - `distiller_scraper/scraper.py:372-378` — The exact lines to wrap (line numbers are pre-Task-1; re-read after Task 1 to get updated positions)

  **WHY Each Reference Matters**:
  - L344-348: Shows the project's established error handling pattern (catch Exception, log with logger.error, break). Your fix should mirror this style exactly.
  - L372-378: The exact code to modify — understand the control flow (the `break` at L378 happens after both the if and else branches)

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Scroll fallback error is caught and logged (not crashing)
    Tool: Bash
    Preconditions: Bug 1 fix applied
    Steps:
      1. Run: uv run python -c "
         import inspect
         from distiller_scraper.scraper import DistillerScraperV2
         source = inspect.getsource(DistillerScraperV2.scrape_category_paginated)
         lines = source.split('\n')
         fallback_idx = next(i for i, l in enumerate(lines) if '_fetch_spirit_urls_from_page' in l)
         preceding = '\n'.join(lines[max(0,fallback_idx-5):fallback_idx])
         if 'try:' in preceding:
             print('PASS: scroll fallback is inside try block')
         else:
             print('FAIL: scroll fallback is NOT inside try block')"
      2. Verify output contains "PASS"
    Expected Result: The _fetch_spirit_urls_from_page call is wrapped in try/except
    Failure Indicators: Output contains "FAIL"
    Evidence: .sisyphus/evidence/task-2-try-except-check.txt

  Scenario: Existing pytest suite still passes after Bug 1 fix
    Tool: Bash
    Preconditions: Bugs 3 and 1 both fixed
    Steps:
      1. Run: uv run python -m pytest tests/ -v --tb=short 2>&1
      2. Count passed/failed tests
    Expected Result: 277 passed, 0 failed
    Failure Indicators: Any test failure
    Evidence: .sisyphus/evidence/task-2-pytest.txt
  ```

  **Commit**: YES (group with Task 1)
  - Message: `fix(scraper): wrap scroll fallback in try/except to prevent crash on timeout`
  - Files: `distiller_scraper/scraper.py`
  - Pre-commit: `uv run python -m pytest tests/ -q`

---

- [ ] 3. Fix Bug 2: Per-category error isolation in scrape()

  **What to do**:
  - In `scrape()` method at L541-575, the try/except currently wraps the entire `for cat_idx, category in enumerate(categories, 1)` loop
  - Move the try/except INSIDE the for loop so each category iteration is independently protected
  - On per-category failure: log error with `logger.error(f"類別 {category} 爬取失敗: {e}")`, then `continue` to next category
  - Keep the outer structure: `end_time`, duration logging, and `return True` should still execute after the loop completes (even if some categories failed)
  - The `finally: self.close_driver()` must remain at the outer level
  - After moving try/except inside the loop, add a simple outer try/finally to ensure `close_driver()` is still called

  **Must NOT do**:
  - Do not change the scrape() method signature
  - Do not add new parameters
  - Do not change what gets logged on success
  - Do not restructure the method beyond moving the try/except

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Moving existing try/except from outer to inner scope; ~5 lines changed
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (Task 3 of 4)
  - **Blocks**: Task 4
  - **Blocked By**: Task 1, Task 2

  **References**:

  **Pattern References**:
  - `distiller_scraper/scraper.py:541-578` — Current `scrape()` method structure with outer try/except; the exact code to restructure
  - `distiller_scraper/scraper.py:344-348` — Existing per-page try/except pattern in `scrape_category_paginated()`; shows the project's error isolation style

  **WHY Each Reference Matters**:
  - L541-578: The exact code block to modify. Critical to understand: L561-569 (end_time, duration logging) and L571 (return True) must remain OUTSIDE the per-category try/except but INSIDE the overall method flow
  - L344-348: Shows the pattern to follow — catch, log, continue/break

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: try/except is inside the for loop, not wrapping it
    Tool: Bash
    Preconditions: Bug 2 fix applied
    Steps:
      1. Run: uv run python -c "
         import inspect
         from distiller_scraper.scraper import DistillerScraperV2
         source = inspect.getsource(DistillerScraperV2.scrape)
         lines = source.split('\n')
         for_line = next((i, l) for i, l in enumerate(lines) if 'for cat_idx, category in' in l)
         try_lines = [(i, l) for i, l in enumerate(lines) if l.strip().startswith('try:')]
         for_idx = for_line[0]
         for_indent = len(for_line[1]) - len(for_line[1].lstrip())
         inner_tries = [t for t in try_lines if t[0] > for_idx and (len(t[1]) - len(t[1].lstrip())) > for_indent]
         if inner_tries:
             print('PASS: try/except is inside the for loop')
         else:
             print('FAIL: try/except is not inside the for loop')"
      2. Verify output contains "PASS"
    Expected Result: try block is nested inside the for loop (greater indentation)
    Failure Indicators: Output contains "FAIL"
    Evidence: .sisyphus/evidence/task-3-error-isolation-check.txt

  Scenario: Existing pytest suite still passes after Bug 2 fix
    Tool: Bash
    Preconditions: All 3 bugs fixed
    Steps:
      1. Run: uv run python -m pytest tests/ -v --tb=short 2>&1
      2. Count passed/failed tests
    Expected Result: 277 passed, 0 failed
    Failure Indicators: Any test failure
    Evidence: .sisyphus/evidence/task-3-pytest.txt
  ```

  **Commit**: YES (group with Tasks 1 & 2 into single commit)
  - Message: `fix(scraper): isolate per-category errors so one failure doesn't kill all categories`
  - Files: `distiller_scraper/scraper.py`
  - Pre-commit: `uv run python -m pytest tests/ -q`

---

- [ ] 4. Full Verification: Tests + Live Scraper Run

  **What to do**:
  - Run the full pytest suite to confirm all 277 tests pass
  - Run the scraper in medium mode with existing DB to verify end-to-end resilience
  - Capture logs and verify:
    - No crash / unhandled exception
    - "已存在於資料庫" or similar skip message appears for already-scraped categories
    - Scraper completes with `return True` (exit code 0)
    - Any new data (if any) is scraped successfully
  - If scraper takes >5 minutes, that's acceptable — it's doing real scraping. Timeout at 15 minutes.

  **Must NOT do**:
  - Do not modify any code in this task
  - Do not skip the live run

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: End-to-end verification requires patience, log analysis, and careful evidence capture
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (Task 4 of 4, final)
  - **Blocks**: None (final task)
  - **Blocked By**: Task 1, Task 2, Task 3

  **References**:

  **Pattern References**:
  - `logs/medium_run_20260301_192601.log` — The original crash log; compare against new run to verify fix
  - `run.py` — Entry point; use `uv run python run.py --mode medium --output both` for verification

  **WHY Each Reference Matters**:
  - Crash log: Compare old failure (crash at 90s, 0 data) vs new behavior (graceful skip or successful scrape)
  - run.py: The exact command to reproduce the original failure, now expected to succeed

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Full pytest suite passes
    Tool: Bash
    Preconditions: All 3 bugs fixed in scraper.py
    Steps:
      1. Run: uv run python -m pytest tests/ -v --tb=short 2>&1
      2. Verify "277 passed" (or more) in output
      3. Verify "0 failed" in output
    Expected Result: 277 passed, 0 failed, 6 deselected
    Failure Indicators: Any "FAILED" or "ERROR" in output
    Evidence: .sisyphus/evidence/task-4-pytest-final.txt

  Scenario: Scraper completes medium run without crash (existing DB)
    Tool: Bash
    Preconditions: distiller.db has 1027 existing spirits, all 3 bugs fixed
    Steps:
      1. Run: uv run python run.py --mode medium --output both 2>&1 (timeout: 900s / 15 min)
      2. Check exit code is 0
      3. Check log output does NOT contain unhandled exception tracebacks
      4. Check log output contains graceful skip message for already-scraped data OR successfully scrapes new data
      5. Check log output contains "爬取完成" (scrape complete message from L565)
    Expected Result: Scraper completes with exit 0, logs show graceful handling of existing data
    Failure Indicators: Non-zero exit code, unhandled exception traceback, "爬蟲執行時發生錯誤" at top level
    Evidence: .sisyphus/evidence/task-4-medium-run.txt

  Scenario: Scraper handles already-scraped category gracefully (no scroll fallback crash)
    Tool: Bash
    Preconditions: Same as above
    Steps:
      1. In the log output from the medium run, search for "滾動模式" messages
      2. If scroll fallback was triggered, verify it either succeeded or was caught by try/except (no crash)
      3. Verify subsequent categories were attempted (look for "類別 2/" or "類別 3/" in logs)
    Expected Result: Either scroll fallback doesn't trigger (Bug 3 fix prevents it) OR if triggered, errors are caught (Bug 1 fix). Multiple categories are attempted (Bug 2 fix).
    Failure Indicators: Scroll fallback triggers AND crashes, only "類別 1/" appears in logs
    Evidence: .sisyphus/evidence/task-4-category-isolation.txt
  ```

  **Commit**: YES (final single commit for all 3 fixes if not already committed)
  - Message: `fix(scraper): prevent crash on pagination fallback with existing DB data`
  - Files: `distiller_scraper/scraper.py`
  - Pre-commit: `uv run python -m pytest tests/ -q`

---

## Final Verification Wave

> After ALL implementation tasks, 1 review agent verifies completeness.
> This is a lightweight plan — full 4-agent review is overkill for 3 surgical fixes.

- [ ] F1. **Plan Compliance + Code Quality Audit** — `deep`
  Read the plan end-to-end. For each "Must Have": verify implementation exists in scraper.py. For each "Must NOT Have": search codebase for forbidden changes. Run `uv run python -m pytest` and verify 277+ pass. Review the 3 changed code blocks for: correctness, edge cases, style consistency with surrounding code. Check evidence files exist in `.sisyphus/evidence/`.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tests [PASS/FAIL] | Code Quality [PASS/FAIL] | VERDICT: APPROVE/REJECT`

---

## Commit Strategy

All 3 fixes should be committed as a **single atomic commit** since they form one logical fix:

- **Message**: `fix(scraper): prevent crash on pagination fallback with existing DB data`
- **Description**: Fix 3 interrelated bugs: (1) distinguish already-scraped data from pagination failure, (2) wrap scroll fallback in try/except, (3) isolate per-category errors so one failure doesn't kill all categories
- **Files**: `distiller_scraper/scraper.py`
- **Pre-commit**: `uv run python -m pytest tests/ -q`

---

## Success Criteria

### Verification Commands
```bash
uv run python -m pytest tests/ -v    # Expected: 277 passed, 0 failed
uv run python run.py --mode medium --output both    # Expected: completes without crash, exit 0
```

### Final Checklist
- [ ] All "Must Have" present (graceful skip, error isolation, fallback protection, clear logs)
- [ ] All "Must NOT Have" absent (no changes outside scraper.py, no new deps, no refactoring)
- [ ] All 277 tests pass
- [ ] Scraper runs end-to-end with existing DB without crashing
