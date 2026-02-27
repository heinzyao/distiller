# Changelog

All notable changes to this project will be documented in this file.

## [2.2.0] - 2026-02-27

### Added
- **SQLite storage backend** (`distiller_scraper/storage.py`)
  - `StorageBackend` abstract base class for pluggable storage
  - `SQLiteStorage` with WAL mode, `spirits` + `flavor_profiles` + `scrape_runs` tables
  - `CSVStorage` wrapper for backward-compatible CSV output
  - Upsert support with duplicate URL detection
- **Paginated scraping** for higher data volume
  - `SearchURLBuilder.build_search_url()` now accepts `page` parameter
  - New scraper methods: `_get_search_queries()`, `_fetch_spirit_urls_from_page()`, `scrape_category_paginated()`
  - Smart stop conditions: empty page / low new URL count / high duplicate ratio
  - Pagination constants in `config.py` (`MAX_PAGES_PER_QUERY`, `DUPLICATE_RATIO_THRESHOLD`, etc.)
- **API endpoint discovery** (`distiller_scraper/api_client.py`)
  - `DistillerAPIClient` with dual discovery: Chrome XHR capture + candidate path probing
  - Three-tier fallback: API (fast) → Selenium (reliable) for both search and detail
  - `discover_api()` auto-probes before scraping starts
- **New CLI flags**: `--output csv|sqlite|both`, `--db-path`, `--no-pagination`, `--use-api`
- **98 new tests** (total: 192)
  - `tests/unit/test_storage.py` (30 tests)
  - `tests/unit/test_api_client.py` (42 tests)
  - `tests/integration/test_pagination.py` (22 tests)
  - 4 pagination tests added to `tests/unit/test_url_builder.py`

### Changed
- `DistillerScraperV2` accepts `storage` and `api_client` parameters
- `scrape()` and `scrape_category()` accept `use_pagination` parameter
- Chrome options include Performance Logging for XHR capture
- Version bumped to 2.2.0

### Fixed
- Python 3.12 sqlite3 `cursor.lastrowid` returning wrong value after `ON CONFLICT DO UPDATE`; replaced with explicit SELECT → INSERT/UPDATE flow

## [1.1.1] - 2026-01-28

### Fixed
- Selenium import timeout issue on macOS with version 4.40+
- Pinned selenium to `>=4.20.0,<4.30.0` for reliable imports
- Added `lxml` to requirements for BeautifulSoup performance

### Changed
- Recreated virtual environment with compatible dependencies
- All 98 tests now passing (81 unit + 17 integration)

## [1.1.0] - 2026-01-28

### Added
- Complete automated testing framework with pytest
  - Unit tests for `DataExtractor`, `SearchURLBuilder`, `ScraperConfig`
  - Integration tests with Mock HTML (no network required)
  - End-to-end tests with live scraping (marked as `slow`/`network`)
- Test fixtures: sample HTML files for consistent testing
- `pytest.ini` configuration with custom markers
- GitHub Actions CI/CD workflow (`.github/workflows/test.yml`)
  - Runs unit and integration tests on push/PR
  - Optional E2E tests on main branch

### Changed
- Updated `requirements.txt` to include pytest dependencies

### Files Added
- `tests/` directory with full test suite
- `tests/conftest.py` - pytest fixtures
- `tests/fixtures/` - sample HTML files
- `tests/unit/test_selectors.py` - 30+ unit tests
- `tests/unit/test_url_builder.py` - URL builder tests
- `tests/unit/test_config.py` - config validation tests
- `tests/integration/test_scraper_mock.py` - mock-based integration tests
- `tests/e2e/test_scraper_live.py` - live scraping tests
- `.github/workflows/test.yml` - CI/CD workflow

## [1.0.0] - 2026-01-28

### Added
- Multi-agent collaboration documentation (`AGENTS.md`)
- This changelog file

### Changed
- Reorganized project structure for clarity
- Renamed `run_scraper_v2.py` to `run.py` as single entry point
- Updated `README.md` with new project structure
- Updated `.gitignore` to exclude virtual environment and data files

### Removed
- `dev.py` - Original Edge version scraper (superseded by module)
- `dev.ipynb` - Exploratory notebook (superseded by module)
- `distiller_scraper_improved.py` - Integrated into module
- `distiller_selenium_scraper.py` - Integrated into module
- `run_final_scraper.py` - Replaced by `run.py`
- `run_phase1.py` - Test script (no longer needed)
- `run_selenium_phase1.py` - Test script (no longer needed)
- `TESTING_REPORT.md` - Outdated, content integrated into README
- Test CSV files

## [0.2.0] - 2026-01-27

### Added
- `distiller_scraper/` module with V2 scraper
- Verified CSS selectors for current Distiller.com structure
- Flavor profile extraction (JSON format)
- Support for multiple spirit categories and styles

### Changed
- Switched from Edge to Chrome WebDriver for better compatibility
- Improved rate limiting and error handling

## [0.1.0] - 2026-01-18

### Added
- Initial Selenium scraper implementation
- Basic CSV export functionality
- Testing report
