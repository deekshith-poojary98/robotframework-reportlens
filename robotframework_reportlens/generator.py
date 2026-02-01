"""
Robot Framework Report Generator.
Uses ExecutionResult -> ReportModel -> template payload. No manual XML.
"""

import json
from pathlib import Path

from .builder import build_report_model
from .serialize import _error_file_path, model_to_payload


class RobotFrameworkReportGenerator:
    """Generate HTML report from Robot Framework output.xml via internal ReportModel."""

    def __init__(self, xml_file):
        self.xml_file = xml_file
        self._model = build_report_model(xml_file)

    _error_file_path = staticmethod(_error_file_path)

    def _build_report_data(self):
        """Build template-format report data from the internal model."""
        return model_to_payload(self._model)

    def generate_html(self, output_file='report.html'):
        """Generate the complete HTML report. Overwrites the file if it already exists."""
        html_content = self._build_html()
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
            inject = 'const reportData = JSON.parse(document.getElementById("report-data").textContent);\n    '
            js = js[:mock_start] + inject + js[icons_start:]
        else:
            js = 'const reportData = JSON.parse(document.getElementById("report-data").textContent);\n    ' + js
        js = js.replace(
            'expandFailedSuites(reportData.rootSuite);',
            'if (reportData.rootSuite) expandFailedSuites(reportData.rootSuite);'
        )
        js = js.replace(
            'const failedTests = getFailedTests(reportData.rootSuite);\n    if (failedTests.length > 0)',
            'const failedTests = reportData.rootSuite ? getFailedTests(reportData.rootSuite) : [];\n    if (failedTests.length > 0)'
        )
        return js.strip()

    def _build_html(self):
        """Build the complete HTML document (template-style, data-driven)."""
        report_data = self._build_report_data()
        json_str = json.dumps(report_data, ensure_ascii=False)
        json_str = json_str.replace('</script>', '<\\/script>').replace('</SCRIPT>', '<\\/SCRIPT>')
        css = self._get_template_css()
        js = self._get_template_javascript()
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
  <script type="application/json" id="report-data">{json_str}</script>
  <script>
{js}
  </script>
</body>
</html>'''
