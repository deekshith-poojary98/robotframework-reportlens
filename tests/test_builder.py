"""Tests for the report model builder."""

from robotframework_reportlens.builder import build_report_model
from robotframework_reportlens.model import ReportModel, Suite, Test as TestCaseModel


class TestBuildReportModel:
    """Tests for build_report_model."""

    def test_returns_report_model(self, minimal_xml_path):
        model = build_report_model(minimal_xml_path)
        assert isinstance(model, ReportModel)
        assert model.root_suite is not None
        assert isinstance(model.root_suite, Suite)

    def test_root_suite_has_id_and_name(self, minimal_xml_path):
        model = build_report_model(minimal_xml_path)
        root = model.root_suite
        assert root.id == "s1"
        assert root.name
        assert root.full_name

    def test_root_suite_has_tests(self, minimal_xml_path):
        model = build_report_model(minimal_xml_path)
        root = model.root_suite
        assert len(root.tests) == 2
        for t in root.tests:
            assert isinstance(t, TestCaseModel)
            assert t.id
            assert t.name
            assert t.status in ("PASS", "FAIL", "SKIP")

    def test_root_suite_has_statistics(self, minimal_xml_path):
        model = build_report_model(minimal_xml_path)
        root = model.root_suite
        assert "total" in root.statistics
        assert "passed" in root.statistics
        assert "failed" in root.statistics
        assert "skipped" in root.statistics
        assert root.statistics["total"] == 2
        assert root.statistics["passed"] == 1
        assert root.statistics["failed"] == 1

    def test_model_has_statistics_and_errors(self, minimal_xml_path):
        model = build_report_model(minimal_xml_path)
        assert model.statistics["total"] == 2
        assert len(model.errors) >= 1
        assert "time" in model.errors[0]
        assert "level" in model.errors[0]
        assert "text" in model.errors[0]

    def test_test_has_keywords(self, minimal_xml_path):
        model = build_report_model(minimal_xml_path)
        tests = model.root_suite.tests
        passing = next(t for t in tests if t.name == "Passing Test")
        assert len(passing.keywords) >= 1
        assert passing.keywords[0].name == "Log"
        assert passing.keywords[0].id.startswith("kw-")

    def test_root_suite_has_setup_teardown_attrs(self, minimal_xml_path):
        model = build_report_model(minimal_xml_path)
        root = model.root_suite
        assert hasattr(root, "setup")
        assert hasattr(root, "teardown")
        assert root.setup is None
        assert root.teardown is None

    def test_test_has_setup_teardown_attrs(self, minimal_xml_path):
        model = build_report_model(minimal_xml_path)
        for test in model.root_suite.tests:
            assert hasattr(test, "setup")
            assert hasattr(test, "teardown")
            assert test.setup is None
            assert test.teardown is None

    def test_report_start_time_and_generated_set_from_xml(self, minimal_xml_path):
        """Report start_time and generated come from XML (root suite or generation_time)."""
        model = build_report_model(minimal_xml_path)
        assert model.generated, "generated should be set from <robot generated='...'>"
        assert model.start_time, "start_time should be set (suite/status or generation_time fallback)"
        # Should be ISO-like so JS Date(iso) parses
        assert "T" in model.start_time or model.start_time.startswith("202"), model.start_time
        assert "T" in model.generated or model.generated.startswith("202"), model.generated
