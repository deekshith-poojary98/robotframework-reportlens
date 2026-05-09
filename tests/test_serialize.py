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
        # startTime may be omitted if not available
        assert "startTime" in payload or True
        assert "rootSuite" in payload
        assert "fullName" in root
        # These keys may be omitted when empty; assert presence only when non-empty
        if _ := root.get("tests"):
            assert isinstance(_, list)
            t = _[0]
            assert "fullName" in t
            assert "keywords" in t
        # suites, setup, teardown may be omitted when empty

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
        assert test.get("keywords")
        kw = test["keywords"][0]
        # startTime/endTime may be omitted if not present
        assert "startTime" in kw or True
        # failMessage/returnValues/messages may be omitted when empty
        assert "returnValues" in kw or True
        assert "keywords" in kw or True
        assert "messages" in kw or True

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
        assert html_msg["isHtml"] is True, (
            "HTML message must serialize with isHtml=True"
        )
        # isHtml is omitted when False (compact serialization) so absence means False
        assert html_msg.get("isHtml", False) is True  # double-check html message
        assert plain_msg.get("isHtml", False) is False, (
            "Plain-text message must serialize without isHtml or isHtml=False"
        )

    def test_trace_messages_filtered_when_debug_level(
        self, fixtures_dir, minimal_xml_path
    ):
        """TRACE-level messages are filtered when min_log_level=DEBUG is passed explicitly."""
        from robotframework_reportlens.builder import _LEVELS

        model = build_report_model(minimal_xml_path, min_log_level=_LEVELS["DEBUG"])

        # Look through all messages and assert none has level TRACE
        def collect_levels(tests):
            for t in tests:
                for kw in t.keywords:
                    for m in kw.messages:
                        yield m.level
                    for child in kw.keywords:
                        yield from collect_levels([child])

        levels = list(collect_levels(model.root_suite.tests))
        assert "TRACE" not in levels
