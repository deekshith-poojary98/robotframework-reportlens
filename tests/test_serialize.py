"""Tests for the report model serializer."""

from robotframework_reportlens.builder import build_report_model
from robotframework_reportlens.serialize import model_to_payload


class TestModelToPayload:
    """Tests for model_to_payload."""

    def test_returns_dict_with_root_suite(self, minimal_xml_path):
        model = build_report_model(minimal_xml_path)
        payload = model_to_payload(model)
        assert isinstance(payload, dict)
        assert "rootSuite" in payload
        assert "statistics" in payload
        assert "errors" in payload

    def test_payload_uses_camel_case_keys(self, minimal_xml_path):
        model = build_report_model(minimal_xml_path)
        payload = model_to_payload(model)
        root = payload["rootSuite"]
        assert "rootSuite" in payload
        assert "startTime" in payload
        assert "rootSuite" in payload
        assert "fullName" in root
        assert "startTime" in root
        assert "tests" in root
        assert "suites" in root
        assert "setup" in root
        assert "teardown" in root
        if root["tests"]:
            t = root["tests"][0]
            assert "fullName" in t
            assert "startTime" in t
            assert "keywords" in t
            assert "setup" in t
            assert "teardown" in t

    def test_suite_has_errors_after_assign(self, minimal_xml_path):
        model = build_report_model(minimal_xml_path)
        payload = model_to_payload(model)
        root = payload["rootSuite"]
        assert "errors" in root
        for test in root["tests"]:
            assert "suiteErrors" in test

    def test_keyword_has_camel_case_keys(self, minimal_xml_path):
        model = build_report_model(minimal_xml_path)
        payload = model_to_payload(model)
        root = payload["rootSuite"]
        test = root["tests"][0]
        assert test["keywords"]
        kw = test["keywords"][0]
        assert "startTime" in kw
        assert "failMessage" in kw
        assert "returnValues" in kw
        assert "keywords" in kw
        assert "messages" in kw

    def test_html_message_isHtml_in_payload(self, html_messages_xml_path):
        """Serialized message dict includes isHtml flag matching the html attribute."""
        model = build_report_model(html_messages_xml_path)
        payload = model_to_payload(model)
        test = payload["rootSuite"]["tests"][0]
        screenshot_kw = test["keywords"][0]
        plain_kw = test["keywords"][1]
        html_msg = screenshot_kw["messages"][0]
        plain_msg = plain_kw["messages"][0]
        assert "isHtml" in html_msg, "Serialized message must have isHtml key"
        assert html_msg["isHtml"] is True, "HTML message must serialize with isHtml=True"
        assert plain_msg["isHtml"] is False, "Plain-text message must serialize with isHtml=False"


class TestUniqueFailures:
    """Tests for unique failure grouping via model payload."""

    def test_failed_tests_have_message(self, unique_failures_xml_path):
        """Each failed test in the payload carries a non-empty message."""
        model = build_report_model(unique_failures_xml_path)
        payload = model_to_payload(model)
        failed = [t for t in payload["rootSuite"]["tests"] if t["status"] == "FAIL"]
        assert len(failed) == 4
        for t in failed:
            assert t["message"], f"Expected non-empty message for test {t['name']}"

    def test_unique_failure_messages_grouped(self, unique_failures_xml_path):
        """Group failed tests by message: 3 tests share one message, 1 has a different message.

        The grouping logic here mirrors the JS getUniqueFailures() in template.html.
        If the JS grouping changes, update this test accordingly.
        """
        model = build_report_model(unique_failures_xml_path)
        payload = model_to_payload(model)
        failed = [t for t in payload["rootSuite"]["tests"] if t["status"] == "FAIL"]
        # Mirror JS getUniqueFailures: group by stripped message, fallback "No error message"
        groups = {}
        for t in failed:
            msg = (t["message"] or "").strip() or "No error message"
            groups.setdefault(msg, []).append(t)
        assert len(groups) == 2, f"Expected 2 unique failure messages, got {len(groups)}: {list(groups.keys())}"
        conn_refused = groups.get("Connection refused", [])
        invalid_card = groups.get("Invalid card number", [])
        assert len(conn_refused) == 3, f"Expected 3 occurrences of 'Connection refused', got {len(conn_refused)}"
        assert len(invalid_card) == 1, f"Expected 1 occurrence of 'Invalid card number', got {len(invalid_card)}"

    def test_passing_tests_excluded_from_failures(self, unique_failures_xml_path):
        """Passing tests do not appear in the failure groups."""
        model = build_report_model(unique_failures_xml_path)
        payload = model_to_payload(model)
        all_tests = payload["rootSuite"]["tests"]
        passing = [t for t in all_tests if t["status"] == "PASS"]
        assert len(passing) == 1
        failed = [t for t in all_tests if t["status"] == "FAIL"]
        passing_names = {t["name"] for t in passing}
        failed_names = {t["name"] for t in failed}
        assert not passing_names.intersection(failed_names)
