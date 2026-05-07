"""
Robot Framework Report Generator.
Uses ExecutionResult -> ReportModel -> template payload. No manual XML.
"""

import gzip
import json
from pathlib import Path

from .builder import build_report_model, _LEVELS
from .serialize import (
    _error_file_path,
    model_to_payload,
    _keyword_to_dict,
    _test_to_dict,
    _collect_keyword_messages,
    _test_to_dict_without_messages,
)


class RobotFrameworkReportGenerator:
    """Generate HTML report from Robot Framework output.xml via internal ReportModel."""

    def __init__(self, xml_file, external_data: bool = False, min_log_level: int | None = None, compress_data: bool = False, compress_data_only: bool = False):
        self.xml_file = xml_file
        # Default loglevel: TRACE (include everything) for self-contained; DEBUG (exclude TRACE) for external-data
        if min_log_level is None:
            min_log_level = _LEVELS["DEBUG"] if external_data else _LEVELS["TRACE"]
        self._model = build_report_model(xml_file, min_log_level=min_log_level)
        self._external_data = external_data
        self._compress_data = compress_data or compress_data_only
        # When True, skip writing plain .json files (only .json.gz is written).
        # The frontend falls back to .json if .gz is unavailable, so skipping .json
        # saves disk space at the cost of no fallback for old browsers.
        self._gz_only = compress_data_only

    _error_file_path = staticmethod(_error_file_path)

    @staticmethod
    def _write_json_files(path_obj: Path, data: dict, compress: bool = False, gz_only: bool = False) -> None:
        """Write *data* as UTF-8 JSON to *path_obj* (must end in ``.json``).

        When *compress* is ``True``, also write a sibling ``<name>.json.gz``
        at gzip compresslevel 9.

        When *gz_only* is ``True``, the plain ``.json`` file is **not** written —
        only the ``.json.gz`` sibling is created.  Use this when old-browser fallback
        is not required and you want the smallest possible output directory.
        *gz_only* implies *compress*; passing ``gz_only=True, compress=False`` is
        treated as ``gz_only=True, compress=True``.
        """
        json_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
        if not gz_only:
            path_obj.write_bytes(json_bytes)
        if compress or gz_only:
            gz_path = path_obj.parent / (path_obj.name + ".gz")
            with gzip.open(gz_path, "wb", compresslevel=9) as fh:
                fh.write(json_bytes)

    def _build_report_data(self):
        """Build template-format report data from the internal model."""
        return model_to_payload(self._model)

    def generate_html(self, output_file='report.html', external_data: bool = False):
        """Generate the complete HTML report. Overwrites the file if it already exists."""
        if external_data:
            self._build_external(output_file)
            return
        html_content = self._build_html(external_data=False)
        path = Path(output_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html_content, encoding='utf-8')
        print(f"Report generated: {output_file}")

    def _get_template_html_path(self):
        """Path to template.html inside this package (works when installed)."""
        return Path(__file__).resolve().parent / 'template' / 'template.html'

    def _get_template_css(self):
        """Extract CSS from template/template.html."""
        path = self._get_template_html_path()
        if not path.exists():
            return '/* template.html not found */'
        text = path.read_text(encoding='utf-8')
        start = text.find('<style>') + len('<style>')
        end = text.find('</style>')
        if start < len('<style>') or end == -1:
            return ''
        return text[start:end].strip()

    def _get_template_javascript(self):
        """Extract JS from template/template.html and adapt to use embedded reportData."""
        path = self._get_template_html_path()
        if not path.exists():
            return 'console.error("template.html not found");'
        text = path.read_text(encoding='utf-8')
        start = text.find('<script>') + len('<script>')
        end = text.find('</script>', start)
        if start < len('<script>') or end == -1:
            return ''
        js = text[start:end]
        js = js.replace('mockData', 'reportData')
        mock_start = js.find('// ========== Mock Data ==========')
        icons_start = js.find('// ========== Icons ==========')
        if mock_start != -1 and icons_start != -1 and icons_start > mock_start:
            js = js[:mock_start] + js[icons_start:]
        js = js.replace(
            'expandFailedSuites(reportData.rootSuite);',
            'if (reportData.rootSuite) expandFailedSuites(reportData.rootSuite);'
        )
        js = js.replace(
            'const failedTests = getFailedTests(reportData.rootSuite);\n    if (failedTests.length > 0)',
            'const failedTests = reportData.rootSuite ? getFailedTests(reportData.rootSuite) : [];\n    if (failedTests.length > 0)'
        )
        return js.strip()

    def _build_html(self, external_data: bool = False, data_root: str = "reportlens-data"):
        """Build the complete HTML document (template-style, data-driven)."""
        report_data = None if external_data else self._build_report_data()
        json_str = json.dumps(report_data, ensure_ascii=False) if report_data is not None else ""
        json_str = json_str.replace('</script>', '<\\/script>').replace('</SCRIPT>', '<\\/SCRIPT>') if json_str else ""
        css = self._get_template_css()
        js = self._get_template_javascript()
        config = {
            "externalData": external_data,
            "dataRoot": data_root,
            "schemaVersion": 1,
        }
        if external_data and self._compress_data:
            config["compressed"] = True
        if external_data and self._gz_only:
            config["compressedOnly"] = True
        config_str = json.dumps(config, ensure_ascii=False)
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=0.25, maximum-scale=5, user-scalable=yes">
  <title>Robot Framework Test Report</title>
  <link rel="icon" type="image/svg+xml" href="https://docs.robotframework.org/img/robot-framework-dark.svg">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
{css}
  </style>
</head>
<body>
  <div class="app" id="app"></div>
  <script type="application/json" id="report-config">{config_str}</script>
  {'' if external_data else f'<script type="application/json" id="report-data">{json_str}</script>'}
  <script>
{js}
  </script>
</body>
</html>'''

    def _build_external(self, output_file: str):
        """Generate report.html plus external JSON payload split across files."""
        report_data = self._build_report_data()
        payload = model_to_payload(self._model)

        path = Path(output_file)
        data_dir = path.parent / "reportlens-data"
        data_dir.mkdir(parents=True, exist_ok=True)

        suite_errors_map = {}
        test_suite_errors = {}

        def walk_errors(suite_dict):
            suite_errors_map[suite_dict.get("id")] = suite_dict.get("errors", [])
            for t in suite_dict.get("tests", []):
                test_suite_errors[t.get("id")] = t.get("suiteErrors", [])
            for child in suite_dict.get("suites", []):
                walk_errors(child)

        if payload.get("rootSuite"):
            walk_errors(payload["rootSuite"])

        def iter_suites(suite):
            yield suite
            for child in suite.suites:
                yield from iter_suites(child)

        root = self._model.root_suite
        summary = {
            "schemaVersion": 1,
            "generated": report_data.get("generated", ""),
            "generator": report_data.get("generator", ""),
            "startTime": report_data.get("startTime", ""),
            "endTime": report_data.get("endTime", ""),
            "duration": report_data.get("duration", 0),
            "statistics": report_data.get("statistics", {}),
            "errors": report_data.get("errors", []),
            "rootSuiteId": root.id,
            "rootSuiteName": root.name,
        }

        suites_list = []
        for suite in iter_suites(root):
            suites_list.append(
                {
                    "id": suite.id,
                    "name": suite.name,
                    "fullName": suite.full_name,
                    "status": suite.status,
                    "startTime": suite.start_time,
                    "duration": suite.duration,
                    "statistics": suite.statistics,
                    "childSuiteIds": [s.id for s in suite.suites],
                    "testIds": [t.id for t in suite.tests],
                }
            )

        suites_json = {
            "schemaVersion": 1,
            "rootSuiteId": root.id,
            "suites": suites_list,
        }

        def write_json(path_obj: Path, data: dict):
            self._write_json_files(path_obj, data, compress=self._compress_data, gz_only=self._gz_only)

        write_json(data_dir / "summary.json", summary)
        write_json(data_dir / "suites.json", suites_json)

        for suite in iter_suites(root):
            tests_stub = []
            for test in suite.tests:
                tests_stub.append(
                    {
                        "id": test.id,
                        "name": test.name,
                        "fullName": test.full_name,
                        "status": test.status,
                        "duration": test.duration,
                        "startTime": test.start_time,
                        "message": test.message,
                        "tags": test.tags,
                    }
                )

            suite_payload = {
                "schemaVersion": 1,
                "suite": {
                    "id": suite.id,
                    "name": suite.name,
                    "fullName": suite.full_name,
                    "status": suite.status,
                    "startTime": suite.start_time,
                    "duration": suite.duration,
                    "statistics": suite.statistics,
                    "setup": _keyword_to_dict(suite.setup) if suite.setup else None,
                    "teardown": _keyword_to_dict(suite.teardown) if suite.teardown else None,
                    "childSuiteIds": [s.id for s in suite.suites],
                    "testIds": [t.id for t in suite.tests],
                    "errors": suite_errors_map.get(suite.id, []),
                },
                "tests": tests_stub,
            }
            write_json(data_dir / f"suite_{suite.id}.json", suite_payload)

            for test in suite.tests:
                test_payload = _test_to_dict_without_messages(test)
                test_payload["suiteErrors"] = test_suite_errors.get(test.id, [])
                test_file = {
                    "schemaVersion": 1,
                    "test": test_payload,
                }
                write_json(data_dir / f"test_{test.id}.json", test_file)

                log_map: dict[str, list[dict]] = {}
                for kw in test.keywords:
                    _collect_keyword_messages(kw, log_map)
                logs_file = {
                    "schemaVersion": 1,
                    "testId": test.id,
                    "keywordMessages": log_map,
                }
                write_json(data_dir / f"test_{test.id}_logs.json", logs_file)

        html_content = self._build_html(external_data=True, data_root="reportlens-data")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html_content, encoding="utf-8")
        print(f"Report generated: {output_file}")
