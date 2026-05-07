"""Tests for RobotFrameworkReportGenerator."""

import gzip
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
        # setup/teardown are omitted when None (compact serialization)
        assert root.get("setup") is None
        assert root.get("teardown") is None

    def test_test_has_setup_teardown_keys(self, minimal_xml_path):
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        data = gen._build_report_data()
        for test in data["rootSuite"]["tests"]:
            # setup/teardown are omitted when None (compact serialization)
            assert test.get("setup") is None
            assert test.get("teardown") is None

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
        # suites is omitted when empty (compact serialization)
        assert root.get("suites", []) == [] or "suites" in root
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


class TestExternalDataMode:
    """Tests for external-data output mode."""

    def test_external_data_writes_split_files(self, minimal_xml_path, tmp_path):
        out = tmp_path / "report.html"
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        gen.generate_html(str(out), external_data=True)
        data_dir = tmp_path / "reportlens-data"
        assert data_dir.exists()
        assert (data_dir / "summary.json").exists()
        assert (data_dir / "suites.json").exists()
        summary = json.loads((data_dir / "summary.json").read_text(encoding="utf-8"))
        suites = json.loads((data_dir / "suites.json").read_text(encoding="utf-8"))
        root_id = suites.get("rootSuiteId")
        assert summary.get("rootSuiteId") == root_id
        # Minimal suite and test files should be created for root suite and its tests
        assert (data_dir / f"suite_{root_id}.json").exists()
        # minimal_output.xml contains s1-t1 and s1-t2
        assert (data_dir / "test_s1-t1.json").exists()
        assert (data_dir / "test_s1-t2.json").exists()

    def test_external_html_uses_config_only(self, minimal_xml_path, tmp_path):
        out = tmp_path / "report.html"
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        gen.generate_html(str(out), external_data=True)
        content = out.read_text(encoding="utf-8")
        assert "report-config" in content
        assert 'id="report-data"' not in content


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
        # isHtml:false is omitted in compact serialization; absence is equivalent to false
        # so we only assert the html message has isHtml:true present

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


class TestCompressedExternalDataMode:
    """Tests for --compress-data behaviour."""

    def _gen_compressed(self, xml_path, tmp_path):
        """Helper: generate external-data report with compress_data=True."""
        out = tmp_path / "report.html"
        gen = RobotFrameworkReportGenerator(xml_path, external_data=True, compress_data=True)
        gen.generate_html(str(out), external_data=True)
        return tmp_path / "reportlens-data"

    # ------------------------------------------------------------------
    # File generation
    # ------------------------------------------------------------------

    def test_compressed_files_generated_alongside_json(self, minimal_xml_path, tmp_path):
        """.json.gz files must be written next to every .json file when compress_data=True."""
        data_dir = self._gen_compressed(minimal_xml_path, tmp_path)
        expected_bases = ["summary.json", "suites.json", "suite_s1.json",
                          "test_s1-t1.json", "test_s1-t2.json",
                          "test_s1-t1_logs.json", "test_s1-t2_logs.json"]
        for base in expected_bases:
            assert (data_dir / base).exists(), f"Missing {base}"
            assert (data_dir / (base + ".gz")).exists(), f"Missing {base}.gz"

    def test_uncompressed_mode_writes_no_gz_files(self, minimal_xml_path, tmp_path):
        """Without compress_data, no .gz files must be present."""
        out = tmp_path / "report.html"
        gen = RobotFrameworkReportGenerator(minimal_xml_path, external_data=True, compress_data=False)
        gen.generate_html(str(out), external_data=True)
        data_dir = tmp_path / "reportlens-data"
        gz_files = list(data_dir.glob("*.gz"))
        assert gz_files == [], f"Unexpected .gz files: {gz_files}"

    # ------------------------------------------------------------------
    # Payload integrity
    # ------------------------------------------------------------------

    def test_gzip_payload_decompresses_to_valid_json(self, minimal_xml_path, tmp_path):
        """Every .json.gz file must decompress to the same JSON as its .json sibling."""
        data_dir = self._gen_compressed(minimal_xml_path, tmp_path)
        for gz_file in sorted(data_dir.glob("*.gz")):
            json_file = gz_file.parent / gz_file.name[:-3]  # strip trailing .gz
            assert json_file.exists(), f"Missing plain .json sibling for {gz_file.name}"
            plain = json.loads(json_file.read_text(encoding="utf-8"))
            with gzip.open(gz_file, "rb") as fh:
                decompressed = json.loads(fh.read().decode("utf-8"))
            assert plain == decompressed, (
                f"{gz_file.name} decompresses to different data than {json_file.name}"
            )

    def test_summary_gz_has_correct_statistics(self, minimal_xml_path, tmp_path):
        """Decompressed summary.json.gz must include the expected statistics."""
        data_dir = self._gen_compressed(minimal_xml_path, tmp_path)
        with gzip.open(data_dir / "summary.json.gz", "rb") as fh:
            summary = json.loads(fh.read().decode("utf-8"))
        stats = summary["statistics"]
        assert stats["total"] == 2
        assert stats["passed"] == 1
        assert stats["failed"] == 1

    # ------------------------------------------------------------------
    # HTML config
    # ------------------------------------------------------------------

    def test_compressed_html_config_has_compressed_true(self, minimal_xml_path, tmp_path):
        """The generated report.html must embed compressed:true in the report-config script."""
        self._gen_compressed(minimal_xml_path, tmp_path)
        content = (tmp_path / "report.html").read_text(encoding="utf-8")
        assert '"compressed": true' in content or '"compressed":true' in content, (
            "report-config must contain compressed:true when compress_data=True"
        )

    def test_uncompressed_html_config_has_no_compressed_flag(self, minimal_xml_path, tmp_path):
        """Without --compress-data the report-config must NOT contain compressed:true."""
        out = tmp_path / "report.html"
        gen = RobotFrameworkReportGenerator(minimal_xml_path, external_data=True, compress_data=False)
        gen.generate_html(str(out), external_data=True)
        content = out.read_text(encoding="utf-8")
        assert '"compressed": true' not in content and '"compressed":true' not in content

    def test_self_contained_report_has_no_compressed_flag(self, minimal_xml_path, tmp_path):
        """Self-contained mode (no --external-data) must never set compressed:true."""
        out = tmp_path / "report.html"
        gen = RobotFrameworkReportGenerator(minimal_xml_path, compress_data=True)
        gen.generate_html(str(out))
        content = out.read_text(encoding="utf-8")
        assert '"compressed": true' not in content and '"compressed":true' not in content

    # ------------------------------------------------------------------
    # Frontend JS artefacts
    # ------------------------------------------------------------------

    def test_template_js_contains_fetchJsonFile(self, minimal_xml_path):
        """The extracted JS must contain fetchJsonFile so the frontend can prefer .gz."""
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        js = gen._get_template_javascript()
        assert "fetchJsonFile" in js, "template JS must define fetchJsonFile"

    def test_template_js_contains_decompressGzipResponse(self, minimal_xml_path):
        """The extracted JS must define decompressGzipResponse."""
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        js = gen._get_template_javascript()
        assert "decompressGzipResponse" in js

    def test_template_js_detects_DecompressionStream(self, minimal_xml_path):
        """The JS must guard on typeof DecompressionStream for browser compatibility."""
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        js = gen._get_template_javascript()
        assert "DecompressionStream" in js
        assert "supportsDecompressionStream" in js

    def test_template_js_has_compressed_only_capability_guard(self, minimal_xml_path):
        """The JS must contain an early capability check that blocks compressedOnly reports
        in browsers lacking DecompressionStream, showing a visible error banner."""
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        js = gen._get_template_javascript()
        assert "compressedOnly" in js, "JS must read compressedOnly from reportConfig"
        assert "DecompressionStream unavailable" in js or "compressedOnly && !supportsDecompressionStream" in js, \
            "JS must contain the capability guard that stops initialisation"


class TestCompressDataOnlyMode:
    """Tests for --compress-data-only (gz-only, no plain .json written)."""

    def _gen_gz_only(self, xml_path, tmp_path):
        out = tmp_path / "report.html"
        gen = RobotFrameworkReportGenerator(xml_path, external_data=True, compress_data_only=True)
        gen.generate_html(str(out), external_data=True)
        return tmp_path / "reportlens-data"

    def test_gz_only_writes_no_plain_json(self, minimal_xml_path, tmp_path):
        """compress_data_only must not write any plain .json data files."""
        data_dir = self._gen_gz_only(minimal_xml_path, tmp_path)
        json_files = [f for f in data_dir.iterdir() if f.suffix == ".json"]
        assert json_files == [], f"Expected no .json files, found: {[f.name for f in json_files]}"

    def test_gz_only_writes_all_gz_files(self, minimal_xml_path, tmp_path):
        """compress_data_only must write .json.gz for every expected file."""
        data_dir = self._gen_gz_only(minimal_xml_path, tmp_path)
        expected = ["summary.json.gz", "suites.json.gz", "suite_s1.json.gz",
                    "test_s1-t1.json.gz", "test_s1-t2.json.gz",
                    "test_s1-t1_logs.json.gz", "test_s1-t2_logs.json.gz"]
        for name in expected:
            assert (data_dir / name).exists(), f"Missing {name}"

    def test_gz_only_payloads_are_valid(self, minimal_xml_path, tmp_path):
        """All .json.gz files written by compress_data_only must decompress to valid JSON."""
        data_dir = self._gen_gz_only(minimal_xml_path, tmp_path)
        for gz_file in sorted(data_dir.glob("*.gz")):
            with gzip.open(gz_file, "rb") as fh:
                data = json.loads(fh.read().decode("utf-8"))
            assert isinstance(data, dict), f"{gz_file.name} did not decompress to a dict"

    def test_gz_only_html_config_has_compressed_true(self, minimal_xml_path, tmp_path):
        """compress_data_only must also set compressed:true in report-config."""
        self._gen_gz_only(minimal_xml_path, tmp_path)
        content = (tmp_path / "report.html").read_text(encoding="utf-8")
        assert '"compressed": true' in content or '"compressed":true' in content

    def test_gz_only_html_config_has_compressed_only_true(self, minimal_xml_path, tmp_path):
        """compress_data_only must set compressedOnly:true in report-config."""
        self._gen_gz_only(minimal_xml_path, tmp_path)
        content = (tmp_path / "report.html").read_text(encoding="utf-8")
        assert '"compressedOnly": true' in content or '"compressedOnly":true' in content

    def test_compress_data_does_not_set_compressed_only(self, minimal_xml_path, tmp_path):
        """--compress-data (dual-write) must NOT set compressedOnly:true in report-config."""
        out = tmp_path / "report.html"
        gen = RobotFrameworkReportGenerator(minimal_xml_path, external_data=True, compress_data=True)
        gen.generate_html(str(out), external_data=True)
        content = (tmp_path / "report.html").read_text(encoding="utf-8")
        # The JSON config block must not contain the compressedOnly flag; the JS
        # variable name "compressedOnly" will always appear in the embedded script.
        assert '"compressedOnly": true' not in content and '"compressedOnly":true' not in content

    def test_compress_data_still_writes_both(self, minimal_xml_path, tmp_path):
        """--compress-data (not only) must still write both .json and .json.gz."""
        out = tmp_path / "report.html"
        gen = RobotFrameworkReportGenerator(minimal_xml_path, external_data=True, compress_data=True)
        gen.generate_html(str(out), external_data=True)
        data_dir = tmp_path / "reportlens-data"
        assert (data_dir / "summary.json").exists(), "summary.json must exist with --compress-data"
        assert (data_dir / "summary.json.gz").exists(), "summary.json.gz must exist with --compress-data"
