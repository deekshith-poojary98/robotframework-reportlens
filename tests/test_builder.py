"""Tests for the report model builder."""

from pathlib import Path

from robotframework_reportlens.builder import build_report_model, _is_executable_body_item
from robotframework_reportlens.model import ReportModel, Suite, Test as TestCaseModel
from robotframework_reportlens.model import Keyword


def _nested_xml_path(fixtures_dir):
    """Path to output.xml with nested keywords (keyword containing keyword)."""
    path = fixtures_dir / "nested_keywords_output.xml"
    assert path.exists(), f"Fixture not found: {path}"
    return str(path)


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

    def test_nested_keywords_preserved(self, fixtures_dir):
        """Keywords executed inside another keyword are built recursively and appear in the report."""
        path = _nested_xml_path(fixtures_dir)
        model = build_report_model(path)
        root = model.root_suite
        assert len(root.tests) == 1
        test = root.tests[0]
        assert len(test.keywords) == 1
        outer = test.keywords[0]
        assert outer.name == "Outer Keyword"
        assert len(outer.keywords) == 1, "nested keyword body must be preserved"
        inner = outer.keywords[0]
        assert inner.name == "Log"

    def test_is_executable_body_item(self):
        """_is_executable_body_item identifies Keyword and body-bearing control structures."""
        assert _is_executable_body_item(None) is False
        # Object with body is executable (e.g. For, If, While, Try)
        class WithBody:
            body = []
        assert _is_executable_body_item(WithBody()) is True
        # Object without body is not (e.g. Message, Return)
        class NoBody:
            pass
        assert _is_executable_body_item(NoBody()) is False

    def test_for_loop_built_with_badge_and_children(self, control_structures_xml_path):
        """FOR loop is built as a control keyword with badge FOR and nested children."""
        model = build_report_model(control_structures_xml_path)
        for_test = next(
            (t for t in model.root_suite.tests if "FOR Loop" in t.name and "Range" in t.name),
            None,
        )
        assert for_test is not None, "Expected test 'Accounts: FOR Loop In Range Create Accounts'"
        # FOR node can be first keyword or after a Log; find by badge
        for_kw = next(
            (kw for kw in for_test.keywords if getattr(kw, "badge", None) == "FOR"),
            None,
        )
        assert for_kw is not None, "Expected a keyword with badge FOR"
        assert isinstance(for_kw, Keyword)
        assert len(for_kw.keywords) >= 1, "FOR loop should have at least one iteration (child keywords)"

    def test_while_loop_built_with_badge_and_children(self, control_structures_xml_path):
        """WHILE loop is built as a control keyword with badge WHILE and iteration children (friendly names)."""
        model = build_report_model(control_structures_xml_path)
        while_test = next(
            (t for t in model.root_suite.tests if "WHILE Loop" in t.name),
            None,
        )
        assert while_test is not None, "Expected test 'Accounts: WHILE Loop Retry Until Success'"
        while_kw = next(
            (kw for kw in while_test.keywords if getattr(kw, "badge", None) == "WHILE"),
            None,
        )
        assert while_kw is not None, "Expected a keyword with badge WHILE"
        assert isinstance(while_kw, Keyword)
        assert len(while_kw.keywords) >= 1, "WHILE loop should have at least one iteration (child keywords)"
        # Iterations should show friendly names "Iteration 1", "Iteration 2", ... not "WhileIteration"
        iteration_names = [c.name for c in while_kw.keywords]
        assert any("Iteration" in (n or "") for n in iteration_names), (
            "WHILE iterations should have friendly names like 'Iteration 1', got: %s" % iteration_names
        )

    def test_if_else_built_with_branches(self, control_structures_xml_path):
        """IF/ELSE is built with root control node and branch children (IF, ELSE badges)."""
        model = build_report_model(control_structures_xml_path)
        if_test = next(
            (t for t in model.root_suite.tests if "IF ELSE" in t.name and "Balance" in t.name),
            None,
        )
        assert if_test is not None, "Expected test 'Accounts: IF ELSE Balance Tier'"
        # Root IF has no badge; children are IfBranches with badge IF / ELSE
        if_kw = next(
            (kw for kw in if_test.keywords if "IF" in (kw.name or "") and "ELSE" in (kw.name or "")),
            None,
        )
        assert if_kw is not None, "Expected keyword for IF/ELSE structure"
        assert len(if_kw.keywords) >= 2, "IF/ELSE should have at least IF and ELSE branches"
        branch_badges = [c.badge for c in if_kw.keywords if getattr(c, "badge", None)]
        assert "IF" in branch_badges and "ELSE" in branch_badges

    def test_try_except_built_with_branches(self, control_structures_xml_path):
        """TRY/EXCEPT is built with root control node and branch children (TRY, EXCEPT badges)."""
        model = build_report_model(control_structures_xml_path)
        try_test = next(
            (t for t in model.root_suite.tests if "TRY EXCEPT" in t.name and "Delete" in t.name),
            None,
        )
        assert try_test is not None, "Expected test 'Accounts: TRY EXCEPT Delete Handles Error'"
        try_kw = next(
            (kw for kw in try_test.keywords if "TRY" in (kw.name or "") and "EXCEPT" in (kw.name or "")),
            None,
        )
        assert try_kw is not None, "Expected keyword for TRY/EXCEPT structure"
        assert len(try_kw.keywords) >= 2, "TRY/EXCEPT should have at least TRY and EXCEPT branches"
        branch_badges = [c.badge for c in try_kw.keywords if getattr(c, "badge", None)]
        assert "TRY" in branch_badges or "EXCEPT" in branch_badges
