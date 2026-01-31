"""
Robot Framework XML Report Generator
Parses output.xml and generates a modern, interactive HTML report.
"""

import json
import re
from pathlib import Path

import xml.etree.ElementTree as ET


class RobotFrameworkReportGenerator:
    def __init__(self, xml_file):
        self.xml_file = xml_file
        self.tree = ET.parse(xml_file)
        self.root = self.tree.getroot()
        self.suites = []
        self.statistics = {'total': {}, 'by_suite': {}}
        self.messages = []
        self.errors = []
        self.parse_data()

    def parse_data(self):
        """Parse XML and extract all relevant data"""
        self._parse_statistics()
        self._parse_errors()
        self._parse_suites(self.root)

    def _parse_errors(self):
        """Parse root <errors> section (warnings and errors shown at top in log.html)."""
        errors_elem = self.root.find('errors')
        if errors_elem is None:
            return
        for msg_elem in errors_elem.findall('msg'):
            self.errors.append({
                'time': msg_elem.get('time', ''),
                'level': msg_elem.get('level', 'WARN'),
                'text': (msg_elem.text or '').strip(),
            })

    def _parse_statistics(self):
        """Extract statistics from XML"""
        stats_elem = self.root.find('statistics/total/stat')
        if stats_elem is not None:
            self.statistics['total'] = {
                'pass': int(stats_elem.get('pass', 0)),
                'fail': int(stats_elem.get('fail', 0)),
                'skip': int(stats_elem.get('skip', 0)),
            }

    def _parse_suites(self, parent_elem, depth=0):
        """Recursively parse suite elements"""
        for suite_elem in parent_elem.findall('suite'):
            suite_data = {
                'id': suite_elem.get('id'),
                'name': suite_elem.get('name'),
                'source': suite_elem.get('source'),
                'tests': [],
                'suites': [],
                'status': 'PASS',
                'pass': 0,
                'fail': 0,
                'skip': 0,
                'elapsed': 0.0,
            }

            nested = self._parse_suites(suite_elem, depth + 1)
            suite_data['suites'] = nested

            for test_elem in suite_elem.findall('test'):
                test_data = self._parse_test(test_elem)
                suite_data['tests'].append(test_data)
                suite_data[test_data['status'].lower()] += 1
                if test_data['status'] == 'FAIL':
                    suite_data['status'] = 'FAIL'

            status_elem = suite_elem.find('status')
            if status_elem is not None:
                suite_data['status'] = status_elem.get('status', 'PASS')
                suite_data['elapsed'] = float(status_elem.get('elapsed', 0))

            self.suites.append(suite_data)

        return self.suites if depth == 0 else []

    def _parse_test(self, test_elem):
        """Parse a test element"""
        test_data = {
            'id': test_elem.get('id'),
            'name': test_elem.get('name'),
            'keywords': [],
            'status': 'PASS',
            'elapsed': 0.0,
            'start': '',
            'doc': '',
            'tags': [],
            'message': '',
        }

        doc_elem = test_elem.find('doc')
        if doc_elem is not None and doc_elem.text:
            test_data['doc'] = doc_elem.text.strip()

        for tag_elem in test_elem.findall('tag'):
            if tag_elem.text:
                test_data['tags'].append(tag_elem.text.strip())

        for kw_elem in test_elem.findall('kw'):
            kw_data = self._parse_keyword(kw_elem)
            test_data['keywords'].append(kw_data)

        status_elem = test_elem.find('status')
        if status_elem is not None:
            test_data['status'] = status_elem.get('status', 'PASS')
            test_data['elapsed'] = float(status_elem.get('elapsed', 0))
            test_data['start'] = status_elem.get('start', '')
            if status_elem.text:
                test_data['message'] = status_elem.text.strip()

        return test_data

    def _parse_keyword(self, kw_elem):
        """Parse a keyword element and its nested keywords recursively"""
        kw_data = {
            'name': kw_elem.get('name'),
            'owner': kw_elem.get('owner'),
            'status': 'PASS',
            'elapsed': 0.0,
            'start': '',
            'arguments': [],
            'messages': [],
            'doc': '',
            'keywords': [],
        }

        for child_kw in kw_elem.findall('kw'):
            kw_data['keywords'].append(self._parse_keyword(child_kw))

        for arg_elem in kw_elem.findall('arg'):
            kw_data['arguments'].append(arg_elem.text or '')

        for msg_elem in kw_elem.findall('msg'):
            msg_data = {
                'time': msg_elem.get('time', ''),
                'level': msg_elem.get('level', 'INFO'),
                'text': msg_elem.text or '',
            }
            kw_data['messages'].append(msg_data)

        doc_elem = kw_elem.find('doc')
        if doc_elem is not None:
            kw_data['doc'] = (doc_elem.text or '').strip()

        status_elem = kw_elem.find('status')
        if status_elem is not None:
            kw_data['status'] = status_elem.get('status', 'PASS')
            kw_data['elapsed'] = float(status_elem.get('elapsed', 0))
            kw_data['start'] = status_elem.get('start', '')

        return kw_data

    def _build_report_data(self):
        """Build template-format report data from XML (tree structure)."""
        stats = self.statistics.get('total', {})
        passed = stats.get('pass', 0)
        failed = stats.get('fail', 0)
        skipped = stats.get('skip', 0)
        total = passed + failed + skipped
        pass_rate = int((passed / total * 100)) if total > 0 else 0

        root_suite_elem = self.root.find('suite')
        project_name = (Path(self.xml_file).resolve().parent.name or 'Test Run').upper()
        if root_suite_elem is None:
            root_suite = {
                'id': 's0',
                'name': project_name,
                'fullName': project_name,
                'status': 'PASS',
                'startTime': self.root.get('generated', ''),
                'endTime': self.root.get('generated', ''),
                'duration': 0,
                'statistics': {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0},
                'tests': [],
                'suites': [],
            }
        else:
            root_suite = self._convert_suite_elem(root_suite_elem, '')
            root_suite['name'] = project_name
            root_suite['fullName'] = project_name
            self._assign_errors_to_suites_and_tests(root_suite)

        generated = self.root.get('generated', '')
        generator = self.root.get('generator', 'Robot Framework')
        start_time = root_suite.get('startTime', generated)
        end_time = root_suite.get('endTime', generated)
        duration_ms = int(root_suite.get('duration', 0))

        errors = [
            {'time': e.get('time', ''), 'level': (e.get('level') or 'WARN').upper(), 'text': e.get('text', '')}
            for e in self.errors
        ]

        return {
            'generated': generated,
            'generator': generator,
            'startTime': start_time,
            'endTime': end_time,
            'duration': duration_ms,
            'statistics': {
                'total': total,
                'passed': passed,
                'failed': failed,
                'skipped': skipped,
                'passRate': pass_rate,
            },
            'errors': errors,
            'rootSuite': root_suite,
        }

    @staticmethod
    def _error_file_path(text):
        """Extract file path from error text like \"Error in file 'path' on line N: ...\"."""
        m = re.search(r"Error in file ['\"](.+?)['\"] on line", (text or '').strip())
        return m.group(1).strip() if m else None

    def _assign_errors_to_suites_and_tests(self, suite):
        """Assign root-level errors to suites by source file only."""
        errors_with_path = []
        for e in self.errors:
            err = {'time': e.get('time', ''), 'level': (e.get('level') or 'WARN').upper(), 'text': e.get('text', '')}
            path = self._error_file_path(e.get('text', ''))
            if path:
                errors_with_path.append((path, err))

        def walk(s):
            source = (s.get('source') or '').strip()
            source_norm = str(Path(source).resolve()) if source else None
            suite_errors = []
            if source_norm:
                for path, err in errors_with_path:
                    try:
                        path_norm = str(Path(path).resolve())
                    except Exception:
                        path_norm = path
                    if path_norm == source_norm:
                        suite_errors.append(err)
            s['errors'] = suite_errors
            for t in s.get('tests', []):
                t['suiteErrors'] = suite_errors
            for child in s.get('suites', []):
                walk(child)

        walk(suite)

    def _convert_suite_elem(self, suite_elem, parent_full_name):
        """Convert a Robot suite element to template-format suite (recursive)."""
        suite_id = suite_elem.get('id', '')
        name = suite_elem.get('name', 'Suite')
        full_name = f"{parent_full_name}.{name}" if parent_full_name else name
        status_elem = suite_elem.find('status')
        status = status_elem.get('status', 'PASS') if status_elem is not None else 'PASS'
        elapsed = float(status_elem.get('elapsed', 0)) if status_elem is not None else 0.0
        start_time = status_elem.get('start', '') if status_elem is not None else ''
        duration_ms = int(elapsed * 1000)

        tests = []
        for test_elem in suite_elem.findall('test'):
            tests.append(self._convert_test_elem(test_elem, full_name))

        suites = []
        for child_suite in suite_elem.findall('suite'):
            suites.append(self._convert_suite_elem(child_suite, full_name))

        passed = sum(1 for t in tests if t['status'] == 'PASS')
        failed = sum(1 for t in tests if t['status'] == 'FAIL')
        skipped = sum(1 for t in tests if t['status'] == 'SKIP')
        total_direct = len(tests)

        return {
            'id': suite_id,
            'name': name,
            'fullName': full_name,
            'status': status,
            'startTime': start_time or '',
            'endTime': start_time or '',
            'duration': duration_ms,
            'statistics': {'total': total_direct, 'passed': passed, 'failed': failed, 'skipped': skipped},
            'tests': tests,
            'suites': suites,
            'source': suite_elem.get('source', ''),
        }

    def _convert_test_elem(self, test_elem, suite_full_name):
        """Convert a Robot test element to template-format test."""
        test_id = test_elem.get('id', '')
        name = test_elem.get('name', 'Test')
        full_name = f"{suite_full_name}.{name}" if suite_full_name else name
        status_elem = test_elem.find('status')
        status = status_elem.get('status', 'PASS') if status_elem is not None else 'PASS'
        elapsed = float(status_elem.get('elapsed', 0)) if status_elem is not None else 0.0
        start_time = status_elem.get('start', '') if status_elem is not None else ''
        message = (status_elem.text or '').strip() if status_elem is not None and status_elem.text else ''
        duration_ms = int(elapsed * 1000)

        doc_elem = test_elem.find('doc')
        documentation = (doc_elem.text or '').strip() if doc_elem is not None and doc_elem.text else ''
        tags = []
        for tag_elem in test_elem.findall('tag'):
            if tag_elem.text:
                tags.append(tag_elem.text.strip())

        keywords = []
        for i, kw_elem in enumerate(test_elem.findall('kw')):
            keywords.append(self._convert_keyword_elem(kw_elem, test_id, i))

        return {
            'id': test_id,
            'name': name,
            'fullName': full_name,
            'status': status,
            'tags': tags,
            'duration': duration_ms,
            'message': message,
            'startTime': start_time or '',
            'endTime': start_time or '',
            'keywords': keywords,
            'documentation': documentation,
        }

    def _convert_keyword_elem(self, kw_elem, test_id, kw_index):
        """Convert a Robot keyword element to template-format keyword (recursive)."""
        kw_id = f"kw-{test_id}-{kw_index}"
        name = kw_elem.get('name', '')
        kw_type = (kw_elem.get('type') or 'KEYWORD').upper()
        if kw_type not in ('SETUP', 'TEARDOWN', 'KEYWORD'):
            kw_type = 'KEYWORD'
        status_elem = kw_elem.find('status')
        status = status_elem.get('status', 'PASS') if status_elem is not None else 'PASS'
        elapsed = float(status_elem.get('elapsed', 0)) if status_elem is not None else 0.0
        start_time = status_elem.get('start', '') if status_elem is not None else ''
        fail_message = (status_elem.text or '').strip() if status_elem is not None and status_elem.text else ''
        duration_ms = int(elapsed * 1000)

        arguments = []
        for arg_elem in kw_elem.findall('arg'):
            arguments.append(arg_elem.text or '')

        doc_elem = kw_elem.find('doc')
        documentation = (doc_elem.text or '').strip() if doc_elem is not None else ''

        return_elem = kw_elem.find('return')
        returned = return_elem is not None
        return_values = []
        if return_elem is not None:
            for val_elem in return_elem.findall('value'):
                return_values.append((val_elem.text or '').strip())

        messages = []
        seen_return = False
        for j, child in enumerate(kw_elem):
            if child.tag == 'return':
                seen_return = True
            elif child.tag == 'msg':
                msg_time = child.get('time', '')
                level = (child.get('level') or 'INFO').upper()
                text = (child.text or '').strip()
                is_return_log = seen_return
                messages.append({
                    'id': f"{kw_id}-msg-{len(messages)}",
                    'timestamp': msg_time,
                    'level': level,
                    'message': text,
                    'isReturn': is_return_log,
                })

        children = []
        for i, child_kw in enumerate(kw_elem.findall('kw')):
            children.append(self._convert_keyword_elem(child_kw, test_id, f"{kw_index}-{i}"))

        return {
            'id': kw_id,
            'name': name,
            'type': kw_type,
            'status': status,
            'duration': duration_ms,
            'startTime': start_time or '',
            'endTime': start_time or '',
            'arguments': arguments,
            'documentation': documentation,
            'messages': messages,
            'keywords': children,
            'failMessage': fail_message,
            'returned': returned,
            'returnValues': return_values,
        }

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
