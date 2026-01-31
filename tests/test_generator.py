"""Tests for RobotFrameworkReportGenerator."""

import json

from robotframework_reportlens.generator import RobotFrameworkReportGenerator


class TestErrorFilePath:
    """Tests for _error_file_path static method."""

    def test_extracts_path_with_single_quotes(self):
        text = "Error in file '/path/to/file.robot' on line 10: message"
        assert RobotFrameworkReportGenerator._error_file_path(text) == "/path/to/file.robot"

    def test_extracts_path_with_double_quotes(self):
        text = 'Error in file "/other.robot" on line 5: message'
        assert RobotFrameworkReportGenerator._error_file_path(text) == "/other.robot"

    def test_returns_none_when_no_match(self):
        assert RobotFrameworkReportGenerator._error_file_path("Some other message") is None
        assert RobotFrameworkReportGenerator._error_file_path("") is None
        assert RobotFrameworkReportGenerator._error_file_path(None) is None


class TestReportGeneratorParsing:
    """Tests for XML parsing and report data building."""

    def test_parses_statistics(self, minimal_xml_path):
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        assert gen.statistics["total"]["pass"] == 1
        assert gen.statistics["total"]["fail"] == 1
        assert gen.statistics["total"]["skip"] == 0

    def test_parses_errors(self, minimal_xml_path):
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        assert len(gen.errors) >= 1
        first = gen.errors[0]
        assert "time" in first
        assert "level" in first
        assert "text" in first
        assert "suite.robot" in first["text"] or "warning" in first["text"].lower()

    def test_build_report_data_has_required_keys(self, minimal_xml_path):
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        data = gen._build_report_data()
        assert "generated" in data
        assert "generator" in data
        assert "statistics" in data
        assert "rootSuite" in data
        assert "errors" in data
        stats = data["statistics"]
        assert stats["total"] == 2
        assert stats["passed"] == 1
        assert stats["failed"] == 1
        assert stats["skipped"] == 0

    def test_root_suite_has_tests(self, minimal_xml_path):
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        data = gen._build_report_data()
        root = data["rootSuite"]
        assert "tests" in root
        assert len(root["tests"]) == 2
        names = [t["name"] for t in root["tests"]]
        assert "Passing Test" in names
        assert "Failing Test" in names


class TestGenerateHtml:
    """Tests for HTML generation."""

    def test_generate_html_creates_file(self, minimal_xml_path, tmp_path):
        out = tmp_path / "report.html"
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        gen.generate_html(str(out))
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert 'id="report-data"' in content

    def test_report_data_is_valid_json(self, minimal_xml_path, tmp_path):
        out = tmp_path / "report.html"
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        gen.generate_html(str(out))
        content = out.read_text(encoding="utf-8")
        start = content.find('id="report-data">') + len('id="report-data">')
        end = content.find("</script>", start)
        json_str = content[start:end].strip()
        json_str = json_str.replace("<\\/script>", "</script>")
        data = json.loads(json_str)
        assert "rootSuite" in data
        assert "statistics" in data

    def test_generate_html_creates_parent_dirs(self, minimal_xml_path, tmp_path):
        out = tmp_path / "sub" / "dir" / "report.html"
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        gen.generate_html(str(out))
        assert out.exists()
