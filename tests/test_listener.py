"""Tests for live listener mode (Feature 4 — 0.1.9)."""

import json
from unittest.mock import MagicMock, patch

from robotframework_reportlens.cli import main
from robotframework_reportlens.listener import LiveReportListener


def test_live_cli_prepares_folder(tmp_path):
    outdir = tmp_path / "live-report"
    with patch("sys.argv", ["reportlens", "live", "--outdir", str(outdir)]):
        assert main() == 0
    assert (outdir / "live.html").exists()
    status = json.loads((outdir / "live-data" / "status.json").read_text(encoding="utf-8"))
    assert status["finished"] is False
    assert (outdir / "live-data" / "tests.json").exists()


def test_listener_records_tests_and_close(tmp_path):
    outdir = tmp_path / "live"
    listener = LiveReportListener(outdir=str(outdir))
    data = MagicMock()
    data.name = "MyTest"
    data.id = "s1-t1"
    result = MagicMock()
    result.name = "MyTest"
    result.status = "FAIL"
    result.message = "boom"
    result.elapsedtime = 123
    result.elapsed_time = None

    listener.start_suite(MagicMock(name="Suite"), MagicMock())
    listener.start_test(data, result)
    status = json.loads((outdir / "live-data" / "status.json").read_text(encoding="utf-8"))
    assert status["currentTest"] and "MyTest" in status["currentTest"]

    listener.end_test(data, result)
    tests = json.loads((outdir / "live-data" / "tests.json").read_text(encoding="utf-8"))
    assert len(tests["tests"]) == 1
    assert tests["tests"][0]["status"] == "FAIL"
    assert tests["tests"][0]["duration"] == 123

    listener.close()
    status = json.loads((outdir / "live-data" / "status.json").read_text(encoding="utf-8"))
    assert status["finished"] is True
    assert status["currentTest"] is None


def test_listener_outdir_kwarg_prefix(tmp_path):
    outdir = tmp_path / "x"
    LiveReportListener(outdir=f"outdir={outdir}")
    assert (outdir / "live.html").exists()


def test_listener_mid_run_flush_survives(tmp_path):
    """Even without close(), completed tests are on disk (robust mid-run exit)."""
    outdir = tmp_path / "mid"
    listener = LiveReportListener(outdir=str(outdir))
    data = MagicMock(name="T", id="t1")
    data.name = "T"
    data.id = "t1"
    result = MagicMock(status="PASS", message="", elapsedtime=1, elapsed_time=None)
    result.status = "PASS"
    result.message = ""
    result.elapsedtime = 1
    result.elapsed_time = None
    listener.end_test(data, result)
    # Simulate crash: no close()
    tests = json.loads((outdir / "live-data" / "tests.json").read_text(encoding="utf-8"))
    assert len(tests["tests"]) == 1
    status = json.loads((outdir / "live-data" / "status.json").read_text(encoding="utf-8"))
    assert status["finished"] is False
