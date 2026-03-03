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
