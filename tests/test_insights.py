"""Tests for duration insights (Feature 3 — 0.1.9)."""

from robotframework_reportlens.builder import build_report_model
from robotframework_reportlens.insights import compute_duration_insights, _histogram
from robotframework_reportlens.serialize import model_to_payload
from robotframework_reportlens.generator import RobotFrameworkReportGenerator
from robotframework_reportlens.model import ReportModel, Suite, Test


def test_insights_in_payload(minimal_xml_path):
    model = build_report_model(minimal_xml_path)
    payload = model_to_payload(model)
    assert "durationInsights" in payload
    di = payload["durationInsights"]
    assert "slowestTests" in di
    assert "slowestKeywords" in di
    assert "histogram" in di
    assert di["totals"]["tests"] >= 1
    assert len(di["histogram"]) == 6


def test_slowest_tests_ordered():
    root = Suite(
        id="s1",
        name="S",
        full_name="S",
        status="PASS",
        start_time="",
        tests=[
            Test("t1", "Fast", "S.Fast", "PASS", [], 10, "", ""),
            Test("t2", "Slow", "S.Slow", "PASS", [], 5000, "", ""),
            Test("t3", "Mid", "S.Mid", "FAIL", [], 500, "", "x"),
        ],
        suites=[],
        statistics={"total": 3, "passed": 2, "failed": 1, "skipped": 0},
    )
    model = ReportModel(
        generated="",
        generator="t",
        start_time="",
        end_time="",
        duration=5510,
        statistics={"total": 3, "passed": 2, "failed": 1, "skipped": 0, "passRate": 66},
        errors=[],
        root_suite=root,
    )
    di = compute_duration_insights(model, top_n=2)
    assert [t["name"] for t in di["slowestTests"]] == ["Slow", "Mid"]
    assert di["slowestTests"][0]["fullName"] == "S.Slow"
    assert di["totals"]["maxTestDurationMs"] == 5000


def test_histogram_zero_and_buckets():
    assert _histogram([]) == [
        {"label": "0–100ms", "count": 0, "pct": 0.0},
        {"label": "100–500ms", "count": 0, "pct": 0.0},
        {"label": "0.5–1s", "count": 0, "pct": 0.0},
        {"label": "1–5s", "count": 0, "pct": 0.0},
        {"label": "5–30s", "count": 0, "pct": 0.0},
        {"label": "30s+", "count": 0, "pct": 0.0},
    ]
    h = _histogram([0, 50, 100, 999, 1000, 60000])
    assert h[0]["count"] == 2  # 0, 50
    assert h[1]["count"] == 1  # 100
    assert h[2]["count"] == 1  # 999
    assert h[3]["count"] == 1  # 1000
    assert h[5]["count"] == 1  # 60000


def test_zero_duration_tests_in_insights():
    root = Suite(
        id="s1",
        name="S",
        full_name="S",
        status="PASS",
        start_time="",
        tests=[Test("t1", "Z", "S.Z", "PASS", [], 0, "", "")],
        suites=[],
        statistics={"total": 1, "passed": 1, "failed": 0, "skipped": 0},
    )
    model = ReportModel(
        "", "t", "", "", 0,
        {"total": 1, "passed": 1, "failed": 0, "skipped": 0, "passRate": 100},
        [],
        root,
    )
    di = compute_duration_insights(model)
    assert di["slowestTests"][0]["duration"] == 0
    assert di["histogram"][0]["count"] == 1


def test_insights_in_generated_html(tmp_path, minimal_xml_path):
    out = tmp_path / "r.html"
    RobotFrameworkReportGenerator(minimal_xml_path).generate_html(str(out))
    text = out.read_text(encoding="utf-8")
    assert "durationInsights" in text
    assert "slowestTests" in text
