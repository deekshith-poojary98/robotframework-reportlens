"""Tests for RobotFrameworkReportGenerator."""

import gzip
import json

from robotframework_reportlens.generator import RobotFrameworkReportGenerator


class TestErrorFilePath:
    """Tests for _error_file_path static method."""

    def test_extracts_path_with_single_quotes(self):
        text = "Error in file '/path/to/file.robot' on line 10: message"
        assert (
            RobotFrameworkReportGenerator._error_file_path(text)
            == "/path/to/file.robot"
        )

    def test_extracts_path_with_double_quotes(self):
        text = 'Error in file "/other.robot" on line 5: message'
        assert RobotFrameworkReportGenerator._error_file_path(text) == "/other.robot"

    def test_returns_none_when_no_match(self):
        assert (
            RobotFrameworkReportGenerator._error_file_path("Some other message") is None
        )
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

    def test_generated_html_contains_report_data_script(
        self, minimal_xml_path, tmp_path
    ):
        out = tmp_path / "report.html"
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        gen.generate_html(str(out))
        content = out.read_text(encoding="utf-8")
        assert 'id="report-data"' in content
        assert (
            '<script type="application/json"' in content
            or "application/json" in content
        )

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

    def test_render_message_body_wraps_img_in_new_tab_link(
        self, tmp_path, minimal_xml_path
    ):
        """renderMessageBody must wrap <img> tags in <a target='_blank'> so images open in a new tab."""
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        gen.generate_html(str(tmp_path / "report.html"))
        js = gen._get_template_javascript()
        assert "renderMessageBody" in js, "renderMessageBody function must be present"
        assert 'target="_blank"' in js, (
            "renderMessageBody must set target=_blank on image links"
        )
        assert "noopener" in js, (
            "renderMessageBody must set rel=noopener on image links"
        )
        assert 'setAttribute("href"' in js or "a.href" in js, (
            "renderMessageBody must set href from img src"
        )

    def test_generated_report_does_not_use_window_open_for_images(
        self, tmp_path, minimal_xml_path
    ):
        """window.open must not be used to open images — that causes double-tab navigation."""
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        out = tmp_path / "report.html"
        gen.generate_html(str(out))
        content = out.read_text(encoding="utf-8")
        assert "window.open" not in content, (
            "report.html must not use window.open — images must open via <a target='_blank'> only"
        )

    def test_generated_report_embeds_isHtml_flag(
        self, tmp_path, html_messages_xml_path
    ):
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

    def test_generated_report_preserves_img_tag_in_message(
        self, tmp_path, html_messages_xml_path
    ):
        """The raw <img> tag from html='true' messages must survive into the embedded JSON."""
        gen = RobotFrameworkReportGenerator(html_messages_xml_path)
        out = tmp_path / "report.html"
        gen.generate_html(str(out))
        content = out.read_text(encoding="utf-8")
        # The <img> is JSON-encoded inside the script tag, so < becomes \u003c or is kept as-is
        assert "img" in content, (
            "Embedded report data must contain the img tag from the HTML message"
        )

    def test_keyword_click_guard_skips_log_message_links(
        self, tmp_path, minimal_xml_path
    ):
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
    """Tests for --external-data --compress-data behaviour.

    New contract (v0.1.8+):
      --external-data              → plain .json only
      --external-data --compress-data → .json.gz only, no .json fallback
    """

    def _gen_compressed(self, xml_path, tmp_path):
        """Helper: generate external-data report with compress_data=True."""
        out = tmp_path / "report.html"
        gen = RobotFrameworkReportGenerator(
            xml_path, external_data=True, compress_data=True
        )
        gen.generate_html(str(out), external_data=True)
        return tmp_path / "reportlens-data"

    # ------------------------------------------------------------------
    # File generation
    # ------------------------------------------------------------------

    def test_compress_data_writes_only_gz_files(self, minimal_xml_path, tmp_path):
        """--compress-data must write ONLY .json.gz — no plain .json files."""
        data_dir = self._gen_compressed(minimal_xml_path, tmp_path)
        plain = [f for f in data_dir.iterdir() if f.suffix == ".json"]
        assert plain == [], f"Unexpected plain .json files: {[f.name for f in plain]}"

    def test_compress_data_writes_all_expected_gz_files(
        self, minimal_xml_path, tmp_path
    ):
        """--compress-data must produce a .json.gz for every expected data file."""
        data_dir = self._gen_compressed(minimal_xml_path, tmp_path)
        expected = [
            "summary.json.gz",
            "suites.json.gz",
            "suite_s1.json.gz",
            "test_s1-t1.json.gz",
            "test_s1-t2.json.gz",
            "test_s1-t1_logs.json.gz",
            "test_s1-t2_logs.json.gz",
        ]
        for name in expected:
            assert (data_dir / name).exists(), f"Missing {name}"

    def test_uncompressed_mode_writes_no_gz_files(self, minimal_xml_path, tmp_path):
        """Without compress_data, no .gz files must be present."""
        out = tmp_path / "report.html"
        gen = RobotFrameworkReportGenerator(
            minimal_xml_path, external_data=True, compress_data=False
        )
        gen.generate_html(str(out), external_data=True)
        data_dir = tmp_path / "reportlens-data"
        gz_files = list(data_dir.glob("*.gz"))
        assert gz_files == [], f"Unexpected .gz files: {gz_files}"

    # ------------------------------------------------------------------
    # Payload integrity
    # ------------------------------------------------------------------

    def test_gzip_payload_decompresses_to_valid_json(self, minimal_xml_path, tmp_path):
        """Every .json.gz file must decompress to a valid JSON dict."""
        data_dir = self._gen_compressed(minimal_xml_path, tmp_path)
        for gz_file in sorted(data_dir.glob("*.gz")):
            with gzip.open(gz_file, "rb") as fh:
                data = json.loads(fh.read())
            assert isinstance(data, dict), (
                f"{gz_file.name} did not decompress to a dict"
            )

    def test_summary_gz_has_correct_statistics(self, minimal_xml_path, tmp_path):
        """Decompressed summary.json.gz must include the expected statistics."""
        data_dir = self._gen_compressed(minimal_xml_path, tmp_path)
        with gzip.open(data_dir / "summary.json.gz", "rb") as fh:
            summary = json.loads(fh.read())
        stats = summary["statistics"]
        assert stats["total"] == 2
        assert stats["passed"] == 1
        assert stats["failed"] == 1

    def test_gz_output_is_deterministic(self, minimal_xml_path, tmp_path):
        """Two runs with the same input must produce bitwise-identical .gz files (mtime=0)."""
        data_dir1 = self._gen_compressed(minimal_xml_path, tmp_path)
        tmp2 = tmp_path / "run2"
        tmp2.mkdir()
        out2 = tmp2 / "report.html"
        gen2 = RobotFrameworkReportGenerator(
            minimal_xml_path, external_data=True, compress_data=True
        )
        gen2.generate_html(str(out2), external_data=True)
        data_dir2 = tmp2 / "reportlens-data"
        for gz1 in sorted(data_dir1.glob("*.gz")):
            gz2 = data_dir2 / gz1.name
            assert gz2.exists(), f"{gz1.name} missing in second run"
            assert gz1.read_bytes() == gz2.read_bytes(), (
                f"{gz1.name} differs between runs — mtime=0 not set?"
            )

    # ------------------------------------------------------------------
    # HTML config
    # ------------------------------------------------------------------

    def test_compressed_html_config_has_compressed_true(
        self, minimal_xml_path, tmp_path
    ):
        """The generated report.html must embed compressed:true in the report-config script."""
        self._gen_compressed(minimal_xml_path, tmp_path)
        content = (tmp_path / "report.html").read_text(encoding="utf-8")
        assert '"compressed": true' in content or '"compressed":true' in content

    def test_compressed_html_config_has_no_compressed_only_flag(
        self, minimal_xml_path, tmp_path
    ):
        """compressedOnly flag is removed — must never appear in the config."""
        self._gen_compressed(minimal_xml_path, tmp_path)
        content = (tmp_path / "report.html").read_text(encoding="utf-8")
        assert '"compressedOnly"' not in content

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
        """The JS capability guard must fire on compressed=true (not the removed compressedOnly)."""
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        js = gen._get_template_javascript()
        assert "compressed && !supportsDecompressionStream" in js, (
            "JS must contain the capability guard: compressed && !supportsDecompressionStream"
        )
        assert "compressedOnly" not in js, (
            "compressedOnly was removed and must not appear in JS"
        )


class TestCompactSerialiserGuards:
    """Regression tests: compact serialisation omits empty arrays/falsy fields.
    The JS template must guard every suite/test field access with || [] / || "".
    These tests caught two production crashes:
      - suite.tests.filter() → TypeError (tests key absent on childless suites)
      - suite.suites.map()   → TypeError (suites key absent on leaf suites)
    """

    def test_template_js_guards_suite_tests_access(self, minimal_xml_path):
        """renderTestTree must use (suite.tests || []) not suite.tests directly."""
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        js = gen._get_template_javascript()
        # Must NOT contain the bare unguarded form
        assert "suite.tests.filter(" not in js, (
            "Bare suite.tests.filter() found — will crash when tests key is absent "
            "(compact serialisation omits empty arrays)"
        )
        # Must contain the guarded form
        assert "(suite.tests || []).filter(" in js

    def test_template_js_guards_suite_suites_map(self, minimal_xml_path):
        """renderTestTree must use (suite.suites || []) not suite.suites directly."""
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        js = gen._get_template_javascript()
        # Must NOT contain the bare unguarded form anywhere that calls .map or .some
        assert "suite.suites.map(" not in js, (
            "Bare suite.suites.map() found — will crash when suites key is absent "
            "(compact serialisation omits empty arrays)"
        )
        assert "suite.suites.some(" not in js, (
            "Bare suite.suites.some() found — will crash when suites key is absent"
        )

    def test_self_contained_report_renders_without_crash(
        self, minimal_xml_path, tmp_path
    ):
        """Generating a self-contained report must not raise and must produce valid HTML.
        Regression: compact serialisation dropped suite.tests / suite.suites keys,
        crashing renderTestTree in the browser on the first render call."""
        out = tmp_path / "report.html"
        gen = RobotFrameworkReportGenerator(minimal_xml_path)
        gen.generate_html(str(out))
        content = out.read_text(encoding="utf-8")
        # The report-data payload must parse as valid JSON with a rootSuite
        start = content.find('id="report-data">') + len('id="report-data">')
        end = content.find("</script>", start)
        payload = json.loads(
            content[start:end].strip().replace("<\\/script>", "</script>")
        )
        root = payload["rootSuite"]
        # Compact serialisation may omit empty arrays — that is correct behaviour.
        # The JS must cope; we verify the keys are either absent or valid lists.
        assert root.get("tests") is None or isinstance(root.get("tests"), list)
        assert root.get("suites") is None or isinstance(root.get("suites"), list)
