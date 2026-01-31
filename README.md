# Robotframework ReportLens

[![PyPI version](https://badge.fury.io/py/robotframework-reportlens.svg)](https://badge.fury.io/py/robotframework-reportlens)
[![Python](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org/downloads/)
[![CI Tests](https://github.com/deekshith-poojary98/robotframework-reportlens/actions/workflows/code-checks.yml/badge.svg)](https://github.com/deekshith-poojary98/robotframework-reportlens/actions/workflows/code-checks.yml)

**ReportLens** turns Robot Framework XML output (`output.xml`) into a single, self-contained HTML report with a modern, interactive UI.

## Sample Report

View generated reports here

- [Pass Report](https://deekshith-poojary98.github.io/robotframework-reportlens/pass/pass_report.html "Link to sample report")
- [Fail Report](https://deekshith-poojary98.github.io/robotframework-reportlens/fail/fail_report.html "Link to sample report")

## Installation

```bash
pip install robotframework-reportlens
```

Requires **Python 3.7+**. No extra dependencies (stdlib only).

## Usage

After running Robot Framework tests (e.g. `robot test/`), generate a report from `output.xml`:

```bash
reportlens output.xml -o report.html
```

**Arguments:**

- `xml_file` – Path to Robot Framework XML output (e.g. `output.xml`)
- `-o`, `--output` – Output HTML path (default: `report.html`)

**Examples:**

```bash
# Default output (report.html in current directory)
reportlens output.xml

# Custom output path
reportlens output.xml -o docs/report.html
```

Open the generated `.html` file in a browser.

You can also run the module directly:

```bash
python -m robotframework_reportlens output.xml -o report.html
```

## Features

- **Suite/test tree** – Navigate suites and tests with pass/fail/skip counts
- **Search & filters** – Filter by status and tags; search test names
- **Keyword tree** – Expand SETUP, keywords, and TEARDOWN; select a keyword to see its logs
- **Logs panel** – Log level filter (All, ERROR, WARN, INFO, etc.); copy button on each log message (shown on hover)
- **Failed-tests summary** – Quick access to failed tests from the sidebar
- **Dark/light theme** – Toggle in the report header
- **Fixed layout** – Same layout on all screens; zoom and scroll as needed

## How it works

ReportLens reads `output.xml`, parses suites, tests, keywords, and messages, then builds one HTML file from a bundled template. The report is data-driven: all content is embedded as JSON and rendered by JavaScript in the browser. No server required.

## Development / source layout

```
├── robotframework_reportlens/
│   ├── __init__.py
│   ├── cli.py           # reportlens entry point
│   ├── generator.py     # XML → report data → HTML
│   └── template/
│       └── template.html
├── tests/
│   ├── conftest.py      # pytest fixtures
│   ├── test_cli.py      # CLI tests
│   ├── test_generator.py # report generator tests
│   └── fixtures/        # minimal Robot output.xml for tests
├── pyproject.toml
└── README.md
```

### Running tests

Install with dev dependencies and run pytest:

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## License

Apache License 2.0 - See [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

