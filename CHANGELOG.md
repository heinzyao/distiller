# Changelog

All notable changes to this project will be documented in this file.

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
