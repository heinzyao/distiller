# Issues - Distiller Failure Handling

## [2026-03-17] Session Start — No issues recorded yet

## PIPESTATUS Bug Fix (2026-03-17)

**File**: `scripts/run_scraper.sh`
**Issue**: Exit code capture pattern was broken
- Original: `if cmd | tee ...; then` - `$?` reflects `tee`'s exit code, not the piped command's
- Impact: Script always reports success when `tee` succeeds (which is almost always), masking Python script failures

**Fix Applied**:
```bash
# Before (WRONG)
if "$VENV_PYTHON" run.py ... | tee -a "$LOG_FILE"; then
    # success case using $? which is tee's exit, not Python's
else
    echo "❌ Scraper failed with exit code $?"  # wrong exit code!
fi

# After (CORRECT)
"$VENV_PYTHON" run.py ... | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}  # capture Python script's exit code
if [ "$EXIT_CODE" -eq 0 ]; then
    # success case
else
    echo "❌ Scraper failed with exit code $EXIT_CODE"  # correct exit code!
fi
```

**Key Pattern**: 
- When piping commands, `$?` always reflects the rightmost command (tee) 
- Must use `${PIPESTATUS[array]}` to access exit codes of all piped commands
- `PIPESTATUS[0]` = first command, `PIPESTATUS[1]` = second, etc.
- `set -eo pipefail` was already present, so this fix ensures the proper exit code propagates

**Verification**: 
- bash -n syntax check passed ✅
- All surrounding logic unchanged (notifications, env checks) ✅
- Ready for Task 11 (uv run migration) ✅

## [2026-03-17] Task 10 - Enhanced LINE notifications

**No issues encountered.**
- TDD flow completed cleanly: 5 failing tests → implement → 27 passing
- Backward compat test confirmed msg_new == msg_old when page_errors=0, error_details=""
- `notify_failure()` new signature: `(self, mode, error="", page_errors=0, error_details="")`
- Message adds "  頁面錯誤數  N" line when page_errors > 0
- Message adds "📋 錯誤詳情" section with _SEP_LIGHT when error_details is non-empty

## [2026-03-17] Task 3 - scroll_page null body handling

**Issue**: `uv run pytest --tb=short -q` exceeded the default 120s timeout twice.
- Full suite passed with 240s timeout (312 passed, 6 deselected).
