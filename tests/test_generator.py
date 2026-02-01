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
        data = gen._build_report_data()
        stats = data["statistics"]
        assert stats["passed"] == 1
        assert stats["failed"] == 1
        assert stats["skipped"] == 0
        assert stats["total"] == 2

    def test_parses_errors(self, minimal_xml_path):
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        data = gen._build_report_data()
        errors = data["errors"]
        assert len(errors) >= 1
        first = errors[0]
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

    def test_root_suite_has_setup_teardown_keys(self, minimal_xml_path):
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        data = gen._build_report_data()
        root = data["rootSuite"]
        assert "setup" in root
        assert "teardown" in root
        assert root["setup"] is None
        assert root["teardown"] is None

    def test_test_has_setup_teardown_keys(self, minimal_xml_path):
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        data = gen._build_report_data()
        for test in data["rootSuite"]["tests"]:
            assert "setup" in test
            assert "teardown" in test
            assert test["setup"] is None
            assert test["teardown"] is None

    def test_root_suite_structure(self, minimal_xml_path):
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        data = gen._build_report_data()
        root = data["rootSuite"]
        assert "id" in root
        assert "name" in root
        assert "fullName" in root
        assert "status" in root
        assert "statistics" in root
        assert "tests" in root
        assert "suites" in root
        assert root["id"] == "s1"
        assert root["statistics"]["total"] == 2
        assert root["statistics"]["passed"] == 1
        assert root["statistics"]["failed"] == 1

    def test_test_has_keywords_and_documentation(self, minimal_xml_path):
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        data = gen._build_report_data()
        tests = data["rootSuite"]["tests"]
        passing = next(t for t in tests if t["name"] == "Passing Test")
        assert "keywords" in passing
        assert len(passing["keywords"]) >= 1
        assert passing["keywords"][0]["name"] == "Log"
        assert "documentation" in passing
        assert "A passing test" in passing["documentation"]


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

    def test_generated_html_contains_report_data_script(self, minimal_xml_path, tmp_path):
        out = tmp_path / "report.html"
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        gen.generate_html(str(out))
        content = out.read_text(encoding="utf-8")
        assert 'id="report-data"' in content
        assert "<script type=\"application/json\"" in content or "application/json" in content

    def test_generated_html_contains_css_and_js(self, minimal_xml_path, tmp_path):
        out = tmp_path / "report.html"
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        gen.generate_html(str(out))
        content = out.read_text(encoding="utf-8")
        assert "<style>" in content
        assert "</style>" in content
        assert "<script>" in content or "reportData" in content
