# Release Notes

## [0.1.4] - 2026-02-08

### Improvements

- **Report UI**
  - **Header and suite names** – Project name in the header and suite/test names in the tree use the same display formatting: hyphens and underscores are shown as spaces (e.g. “ROBOTFRAMEWORK REPORTLENS”).
  - **Durations** – Suite rows in the sidebar show total suite duration. Test rows show execution time (same style as setup/teardown). Suite setup and teardown rows continue to show their keyword duration.
  - **Suite icon when skipped** – The suite row’s folder icon uses the skip (yellow) style when the suite has any skipped tests; otherwise it follows the suite’s pass/fail status.
  - **Resizable layout** – Sidebar width and main-panel keyword/logs split are resizable by dragging separators. Sidebar toggle button position is kept in sync when the sidebar is resized.
- **Timestamps**
  - **ISO-8601 normalization** – All timestamps (report generated/start, suite/test/keyword start, log message and error timestamps) are normalized in Python to ISO-8601 with timezone before being serialized. This prevents “Invalid Date” in the UI across systems and browsers; the header time is shown in the user’s local timezone.
- **Report model and CLI**
  - **Report model and debugging** – Report model and builder improvements; optional debug output when `BUILD_DEBUG=1` is set.
  - **Failed keyword logs** – When a keyword fails and Robot provides only a failure message (no log messages), the failure text is now added as a synthetic log entry (level FAIL) so the Logs & Messages pane shows it when that keyword is selected.
  - **CLI** – Refined CLI debugging and import logic.
- **Tests and assets**
  - **Robot tests** – Refactored account tests; added coverage for loops (FOR, IN RANGE), control structures (IF/ELSE, TRY/EXCEPT/FINALLY), and WHILE. Output XML and template styling updated accordingly.

### Links

- [PyPI](https://pypi.org/project/robotframework-reportlens/)
- [Repository](https://github.com/deekshith-poojary98/robotframework-reportlens)

---

## [0.1.3] - 2026-02-01

### Improvements

- **Internal report model and API**
  - **Clean data model** – Parsing is decoupled from rendering. A pure Python report model (`ReportModel`, `Suite`, `Test`, `Keyword`, `LogMessage`) is built from Robot’s `ExecutionResult`; no manual XML traversal. IDs are deterministic and stable for deep linking.
  - **Layers** – Builder (`builder.py`) builds the model from `ExecutionResult`; serializer (`serialize.py`) turns the model into the template payload; generator only assembles HTML and embeds JSON.
- **Deep linking**
  - **URL hash** – Reports support `report.html#test=<test_id>`. On load, the hash is parsed, the target test is resolved, parent suites are expanded, the test is selected and scrolled into view, and its details panel is shown. Invalid IDs are ignored without error.
  - **Shareable links** – Selecting a test in the sidebar or failed list updates the URL hash so the link can be shared or refreshed.
- **Suite and test setup/teardown**
  - **Suite level** – Suite setup and teardown are captured from Robot’s result model and shown in the sidebar (before and after the test list). Clicking a suite setup or teardown row opens the main panel with that keyword’s tree and logs (same as test keywords).
  - **Test level** – Test setup and teardown appear inside the test’s Keyword Execution panel in execution order (setup → body keywords → teardown). Suite setup/teardown are not shown inside a test; only test-level setup/teardown appear there.
  - **Badges** – SETUP, TEARDOWN, RETURNS, and RETURNED badges use a consistent size (10px) in the sidebar and main panel.
  - **Failed suite setup/teardown** – When a suite-level setup or teardown fails, its SETUP or TEARDOWN badge in the sidebar shows a thin red border (0.1px) so failed suite keywords are easy to spot.
- **Report UI**
  - **Sidebar toggle** – The sidebar collapse/expand button is always visible (auto-hide removed).
  - **Suite expand** – Clicking suite setup or teardown rows no longer collapses the suite; only the suite header toggles expand/collapse.

### Development

- **Tests** – Added `test_builder.py` and `test_serialize.py`; more cases in `test_generator.py` and `test_cli.py` (34 tests total). Pytest filter added for model `Test` class collection warning.
- **Build** – License in `pyproject.toml` updated to SPDX string (`"Apache-2.0"`); deprecated license classifier removed to fix setuptools deprecation warnings.

### Links

- [PyPI](https://pypi.org/project/robotframework-reportlens/)
- [Repository](https://github.com/deekshith-poojary98/robotframework-reportlens)

---

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

Requires **Python 3.10+**. No extra runtime dependencies (stdlib only).

### Development

- Pytest test suite for CLI and report generator
- GitHub Actions workflow: lint (Ruff), tests (Python 3.10–3.14), security (Bandit)
- Dev dependencies: `pip install -e ".[dev]"` (pytest, pytest-cov, ruff, build)

### Links

- [PyPI](https://pypi.org/project/robotframework-reportlens/)
- [Repository](https://github.com/deekshith-poojary98/robotframework-reportlens)
- [Sample report (pass)](https://deekshith-poojary98.github.io/robotframework-reportlens/pass/pass_report.html)
- [Sample report (fail)](https://deekshith-poojary98.github.io/robotframework-reportlens/fail/fail_report.html)
