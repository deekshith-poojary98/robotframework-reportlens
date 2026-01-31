# Release Notes

## [0.1.2] - 2026-01-31

### Improvements

- **Report UI**
  - **Log order** – Logs are now sorted by execution order (timestamp, then keyword depth) so e.g. Set Variable’s log appears before the parent keyword’s return log.
  - **RETURNS badge (keyword tree)** – Keywords that return a value (from `<return>` in output.xml) show a **RETURNS** badge in the keyword tree (same size as SETUP/TEARDOWN). Tooltip shows returned variable name(s).
  - **RETURNED badge (logs panel)** – Log lines that are the keyword’s return-value log (the `<msg>` after `<return>` in the XML) show a **RETURNED** badge in the logs list so you can see which line is the return.

### Links

- [PyPI](https://pypi.org/project/robotframework-reportlens/)
- [Repository](https://github.com/deekshith-poojary98/robotframework-reportlens)

---

## [0.1.1] - 2026-01-31

### Improvements

- **Report UI**
  - **Header spacing** – Project name and generator line now use a consistent gap on all platforms (fixes tight spacing on macOS vs Windows).

### Development

- Pytest test suite for CLI and report generator (14 tests).
- GitHub Actions workflow updated to use `pyproject.toml` and `robotframework_reportlens` paths (lint, test, security).
- Dev dependencies: pytest, pytest-cov, ruff, build (see `pip install -e ".[dev]"`).

### Links

- [PyPI](https://pypi.org/project/robotframework-reportlens/)
- [Repository](https://github.com/deekshith-poojary98/robotframework-reportlens)

---

## [0.1.0] - 2026-01-31

### Initial release

**robotframework-reportlens** turns Robot Framework XML output (`output.xml`) into a single, self-contained HTML report with a modern, interactive UI.

### Features

- **Suite/test tree** – Navigate suites and tests with pass/fail/skip counts
- **Search & filters** – Filter by status and tags; search test names
- **Keyword tree** – Expand SETUP, keywords, and TEARDOWN; select a keyword to see its logs
- **Logs panel** – Log level filter (All, ERROR, WARN, INFO, etc.); copy button on each log message (shown on hover)
- **Failed-tests summary** – Quick access to failed tests from the sidebar
- **Dark/light theme** – Toggle in the report header
- **Fixed layout** – Same layout on all screens; zoom and scroll as needed

### Usage

```bash
pip install robotframework-reportlens
reportlens output.xml -o report.html
```

Requires **Python 3.8+**. No extra runtime dependencies (stdlib only).

### Development

- Pytest test suite for CLI and report generator
- GitHub Actions workflow: lint (Ruff), tests (Python 3.8–3.14), security (Bandit)
- Dev dependencies: `pip install -e ".[dev]"` (pytest, pytest-cov, ruff, build)

### Links

- [PyPI](https://pypi.org/project/robotframework-reportlens/)
- [Repository](https://github.com/deekshith-poojary98/robotframework-reportlens)
- [Sample report (pass)](https://deekshith-poojary98.github.io/robotframework-reportlens/pass/pass_report.html)
- [Sample report (fail)](https://deekshith-poojary98.github.io/robotframework-reportlens/fail/fail_report.html)
