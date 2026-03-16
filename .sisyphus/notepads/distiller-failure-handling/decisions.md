# Decisions - Distiller Failure Handling

## [2026-03-17] Session Start

### Explicit Constraints (from plan Must NOT Have)
- Do NOT refactor the scrolling algorithm — extend only
- Do NOT replace existing restart_driver() triggers — EXTEND, keep 'invalid session id' and 'session deleted'
- Do NOT create new storage/DB methods — use existing record_scrape_run() and finish_scrape_run()
- Do NOT build dashboards or analytics on scrape_runs data
- Do NOT add exponential backoff, circuit breakers, or retry middleware
- Do NOT create new notification channels
- Do NOT rewrite run_scraper.sh flow — fix exit code + migrate to uv run, nothing else
- Do NOT add monitoring endpoints, health dashboards, or observability infrastructure
- Do NOT change notify_success() path
- Do NOT let LINE API failures mark the scraper run as failed

### TDD Approach
- RED → GREEN → REFACTOR for every behavioral change
- Test runner: `uv run pytest`
