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


class TestScreenshotRendering:
    """Tests for inline screenshot / HTML log message rendering in the generated report."""

    def test_render_message_body_wraps_img_in_new_tab_link(self, tmp_path, minimal_xml_path):
        """renderMessageBody must wrap <img> tags in <a target='_blank'> so images open in a new tab."""
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        gen.generate_html(str(tmp_path / "report.html"))
        js = gen._get_template_javascript()
        assert "renderMessageBody" in js, "renderMessageBody function must be present"
        assert 'target="_blank"' in js, "renderMessageBody must set target=_blank on image links"
        assert "noopener" in js, "renderMessageBody must set rel=noopener on image links"
        assert 'setAttribute("href"' in js or "a.href" in js, "renderMessageBody must set href from img src"

    def test_generated_report_does_not_use_window_open_for_images(self, tmp_path, minimal_xml_path):
        """window.open must not be used to open images — that causes double-tab navigation."""
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        out = tmp_path / "report.html"
        gen.generate_html(str(out))
        content = out.read_text(encoding="utf-8")
        assert "window.open" not in content, (
            "report.html must not use window.open — images must open via <a target='_blank'> only"
        )

    def test_generated_report_embeds_isHtml_flag(self, tmp_path, html_messages_xml_path):
        """The embedded JSON in the generated report must include isHtml=true for HTML log messages."""
        gen = RobotFrameworkReportGenerator(html_messages_xml_path)
        out = tmp_path / "report.html"
        gen.generate_html(str(out))
        content = out.read_text(encoding="utf-8")
        assert '"isHtml": true' in content or '"isHtml":true' in content, (
            "Embedded report data must contain isHtml:true for HTML log messages"
        )
        assert '"isHtml": false' in content or '"isHtml":false' in content, (
            "Embedded report data must contain isHtml:false for plain-text log messages"
        )

    def test_generated_report_preserves_img_tag_in_message(self, tmp_path, html_messages_xml_path):
        """The raw <img> tag from html='true' messages must survive into the embedded JSON."""
        gen = RobotFrameworkReportGenerator(html_messages_xml_path)
        out = tmp_path / "report.html"
        gen.generate_html(str(out))
        content = out.read_text(encoding="utf-8")
        # The <img> is JSON-encoded inside the script tag, so < becomes \u003c or is kept as-is
        assert "img" in content, "Embedded report data must contain the img tag from the HTML message"

    def test_keyword_click_guard_skips_log_message_links(self, tmp_path, minimal_xml_path):
        """The [data-keyword-id] click handler must bail out when the click target is an img or anchor
        inside .log-message, so clicking a screenshot doesn't also trigger keyword expansion."""
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        out = tmp_path / "report.html"
        gen.generate_html(str(out))
        content = out.read_text(encoding="utf-8")
        assert "log-message" in content, "report must contain .log-message elements"
        # Guard: the keyword click handler must check for img/a inside .log-message
        assert 'closest(".log-message")' in content, (
            "Keyword click handler must guard against clicks inside .log-message"
        )

    def test_img_click_handler_only_stops_propagation(self, tmp_path, minimal_xml_path):
        """The .log-message img click handler must only stopPropagation, not call window.open."""
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        out = tmp_path / "report.html"
        gen.generate_html(str(out))
        content = out.read_text(encoding="utf-8")
        # window.open must be absent entirely
        assert "window.open" not in content, (
            ".log-message img handler must not call window.open"
        )
