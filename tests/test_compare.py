"""Tests for compare two runs (Feature 1 — 0.1.9)."""

from pathlib import Path
from unittest.mock import patch


from robotframework_reportlens.compare import compare_xml_files
from robotframework_reportlens.cli import main


def _write_xml(path: Path, tests: list[tuple[str, str, str, str]]) -> Path:
    """
    tests: list of (name, status, elapsed, message)
    """
    body = []
    passed = failed = skipped = 0
    for i, (name, status, elapsed, message) in enumerate(tests, start=1):
        st = status.upper()
        if st == "PASS":
            passed += 1
        elif st == "FAIL":
            failed += 1
        else:
            skipped += 1
        msg_attr = f">{message}" if message else ""
        body.append(
            f"""<test id="s1-t{i}" name="{name}">
<kw name="Log" owner="BuiltIn">
<status status="{st}" start="2026-01-31T12:00:0{i}" elapsed="{elapsed}"/>
</kw>
<status status="{st}" start="2026-01-31T12:00:0{i}" elapsed="{elapsed}">{msg_attr}</status>
</test>"""
        )
    suite_status = "FAIL" if failed else "PASS"
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2026-01-31T12:00:00" rpa="false" schemaversion="5">
<suite id="s1" name="CmpSuite" source="cmp.robot">
{"".join(body)}
<status status="{suite_status}" start="2026-01-31T12:00:01" elapsed="1.0"/>
</suite>
<statistics>
<total>
<stat pass="{passed}" fail="{failed}" skip="{skipped}">All Tests</stat>
</total>
</statistics>
</robot>
"""
    path.write_text(xml, encoding="utf-8")
    return path


def test_compare_newly_failing_and_passing(tmp_path):
    a = _write_xml(
        tmp_path / "a.xml",
        [
            ("Alpha", "PASS", "0.100", ""),
            ("Beta", "FAIL", "0.200", "old fail"),
            ("Gamma", "PASS", "0.050", ""),
        ],
    )
    b = _write_xml(
        tmp_path / "b.xml",
        [
            ("Alpha", "FAIL", "0.300", "new fail"),
            ("Beta", "PASS", "0.150", ""),
            ("Gamma", "PASS", "0.050", ""),
        ],
    )
    payload = compare_xml_files(str(a), str(b))
    assert payload["mode"] == "compare"
    assert payload["summary"]["newlyFailing"] == 1
    assert payload["summary"]["newlyPassing"] == 1
    assert payload["newlyFailing"][0]["name"] == "Alpha"
    assert payload["newlyPassing"][0]["name"] == "Beta"
    alpha = next(x for x in payload["allComparisons"] if x["name"] == "Alpha")
    assert alpha["durationDelta"] == 200  # 300ms - 100ms


def test_compare_health_and_blockers(tmp_path):
    a = _write_xml(
        tmp_path / "a.xml",
        [
            ("Alpha", "PASS", "0.100", ""),
            ("Beta", "FAIL", "0.200", "old fail"),
            ("Gamma", "PASS", "0.050", ""),
        ],
    )
    b = _write_xml(
        tmp_path / "b.xml",
        [
            ("Alpha", "FAIL", "0.300", "new fail"),
            ("Beta", "PASS", "0.150", ""),
            ("Gamma", "PASS", "0.050", ""),
        ],
    )
    payload = compare_xml_files(str(a), str(b))
    s = payload["summary"]
    assert s["verdict"] in ("worse", "mixed", "better", "same")
    assert s["verdict"] == "mixed"
    assert s["blockerCount"] == 1
    assert s["failDelta"] == 0
    assert "durationNoiseMs" in s
    assert payload["blockers"][0]["name"] == "Alpha"
    assert payload["newlyFailing"][0].get("messageChanged") is True


def test_compare_tag_diff(tmp_path):
    a = tmp_path / "a.xml"
    b = tmp_path / "b.xml"
    a.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2026-01-31T12:00:00" schemaversion="5">
<suite id="s1" name="CmpSuite" source="cmp.robot">
<test id="s1-t1" name="Tagged">
<tag>smoke</tag>
<tag>payments</tag>
<status status="PASS" start="2026-01-31T12:00:01" elapsed="0.100"></status>
</test>
<status status="PASS" start="2026-01-31T12:00:01" elapsed="0.100"/>
</suite>
<statistics><total><stat pass="1" fail="0" skip="0">All Tests</stat></total></statistics>
</robot>""",
        encoding="utf-8",
    )
    b.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2026-01-31T12:00:00" schemaversion="5">
<suite id="s1" name="CmpSuite" source="cmp.robot">
<test id="s1-t1" name="Tagged">
<tag>critical</tag>
<tag>payments</tag>
<status status="FAIL" start="2026-01-31T12:00:01" elapsed="0.200">boom</status>
</test>
<status status="FAIL" start="2026-01-31T12:00:01" elapsed="0.200"/>
</suite>
<statistics><total><stat pass="0" fail="1" skip="0">All Tests</stat></total></statistics>
</robot>""",
        encoding="utf-8",
    )
    payload = compare_xml_files(str(a), str(b))
    entry = payload["newlyFailing"][0]
    assert entry["tagsAdded"] == ["critical"]
    assert entry["tagsRemoved"] == ["smoke"]
    assert set(entry["tags"]) == {"critical", "payments", "smoke"}
    assert entry.get("suitePath") == ""
    assert "testA" not in entry
    assert payload["summary"]["durationBasis"] == "matched_tests"
    assert payload["summary"]["durationDelta"] == 100


def test_compare_payload_omits_noise_unchanged(tmp_path):
    a = _write_xml(
        tmp_path / "a.xml",
        [
            ("Stable", "PASS", "0.100", ""),
            ("Noisy", "PASS", "0.100", ""),
            ("Failing", "FAIL", "0.200", "x"),
        ],
    )
    b = _write_xml(
        tmp_path / "b.xml",
        [
            ("Stable", "PASS", "0.100", ""),
            ("Noisy", "PASS", "0.120", ""),  # 20ms noise under floor
            ("Failing", "FAIL", "0.200", "x"),
        ],
    )
    payload = compare_xml_files(str(a), str(b))
    names = {e["name"] for e in payload["allComparisons"]}
    assert "Stable" not in names
    assert "Noisy" not in names
    assert "Failing" in names
    assert payload["summary"]["stillFailing"] == 1
    assert payload["durationChanges"] == []


def test_compare_identical_runs(tmp_path, minimal_xml_path):
    payload = compare_xml_files(minimal_xml_path, minimal_xml_path)
    assert payload["summary"]["newlyFailing"] == 0
    assert payload["summary"]["newlyPassing"] == 0
    assert payload["summary"]["matched"] >= 1
    assert all(e["durationDelta"] == 0 for e in payload["durationChanges"]) or not payload[
        "durationChanges"
    ]


def test_compare_only_in_a_and_b(tmp_path):
    a = _write_xml(tmp_path / "a.xml", [("OnlyA", "PASS", "0.010", "")])
    b = _write_xml(tmp_path / "b.xml", [("OnlyB", "FAIL", "0.020", "x")])
    payload = compare_xml_files(str(a), str(b))
    assert payload["summary"]["onlyInA"] == 1
    assert payload["summary"]["onlyInB"] == 1
    assert payload["onlyInA"][0]["name"] == "OnlyA"
    assert payload["onlyInB"][0]["name"] == "OnlyB"


def test_compare_mismatched_suite_trees(tmp_path):
    """Different root folder names still join after stripping builder root rename."""
    dir_a = tmp_path / "run_a"
    dir_b = tmp_path / "run_b"
    dir_a.mkdir()
    dir_b.mkdir()
    a = dir_a / "output.xml"
    b = dir_b / "output.xml"
    a.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2026-01-31T12:00:00" schemaversion="5">
<suite id="s1" name="Nested">
<test id="s1-t1" name="Shared"><status status="PASS" start="2026-01-31T12:00:01" elapsed="0.1"/></test>
<status status="PASS" start="2026-01-31T12:00:01" elapsed="0.1"/>
</suite>
<statistics><total><stat pass="1" fail="0" skip="0">All Tests</stat></total></statistics>
</robot>""",
        encoding="utf-8",
    )
    b.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2026-01-31T12:00:00" schemaversion="5">
<suite id="s1" name="Nested">
<test id="s1-t1" name="Shared"><status status="FAIL" start="2026-01-31T12:00:01" elapsed="0.2">boom</status></test>
<status status="FAIL" start="2026-01-31T12:00:01" elapsed="0.2"/>
</suite>
<statistics><total><stat pass="0" fail="1" skip="0">All Tests</stat></total></statistics>
</robot>""",
        encoding="utf-8",
    )
    payload = compare_xml_files(str(a), str(b))
    assert payload["summary"]["matched"] == 1
    assert payload["summary"]["newlyFailing"] == 1
    assert payload["newlyFailing"][0]["name"] == "Shared"


def test_compare_missing_file_cli(capsys, tmp_path, minimal_xml_path):
    with patch(
        "sys.argv",
        ["reportlens", "compare", str(minimal_xml_path), str(tmp_path / "nope.xml")],
    ):
        assert main() == 1
    err = capsys.readouterr().err
    assert "not found" in err.lower()


def test_compare_cli_generates_html(tmp_path, minimal_xml_path):
    out = tmp_path / "diff.html"
    with patch(
        "sys.argv",
        [
            "reportlens",
            "compare",
            minimal_xml_path,
            minimal_xml_path,
            "-o",
            str(out),
            "--label-a",
            "Before",
            "--label-b",
            "After",
        ],
    ):
        assert main() == 0
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "report-data" in text
    assert '"mode": "compare"' in text or '"mode":"compare"' in text


def test_compare_dotted_name_is_not_the_nested_suite_test(tmp_path):
    """Test 'API.Health' must not be joined with suite API / test Health."""
    a = tmp_path / "a.xml"
    b = tmp_path / "b.xml"
    a.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2026-01-31T12:00:00" schemaversion="5">
<suite id="s1" name="Root">
<test id="s1-t1" name="API.Health"><status status="PASS" start="2026-01-31T12:00:01" elapsed="0.1"/></test>
<status status="PASS" start="2026-01-31T12:00:01" elapsed="0.1"/>
</suite>
<statistics><total><stat pass="1" fail="0" skip="0">All Tests</stat></total></statistics>
</robot>""",
        encoding="utf-8",
    )
    b.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2026-01-31T12:00:00" schemaversion="5">
<suite id="s1" name="Root">
<suite id="s1-s1" name="API">
<test id="s1-s1-t1" name="Health"><status status="FAIL" start="2026-01-31T12:00:01" elapsed="0.2">boom</status></test>
<status status="FAIL" start="2026-01-31T12:00:01" elapsed="0.2"/>
</suite>
<status status="FAIL" start="2026-01-31T12:00:01" elapsed="0.2"/>
</suite>
<statistics><total><stat pass="0" fail="1" skip="0">All Tests</stat></total></statistics>
</robot>""",
        encoding="utf-8",
    )
    payload = compare_xml_files(str(a), str(b))
    assert payload["summary"]["matched"] == 0
    assert payload["summary"]["newlyFailing"] == 0
    assert payload["summary"]["onlyInA"] == 1
    assert payload["summary"]["onlyInB"] == 1
    assert payload["onlyInA"][0]["name"] == "API.Health"
    assert payload["onlyInB"][0]["name"] == "Health"
    assert payload["onlyInA"][0]["compareKey"] != payload["onlyInB"][0]["compareKey"]


def test_compare_empty_suite(tmp_path):
    empty = tmp_path / "empty.xml"
    empty.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2026-01-31T12:00:00" schemaversion="5">
<suite id="s1" name="Empty">
<status status="PASS" start="2026-01-31T12:00:01" elapsed="0"/>
</suite>
<statistics><total><stat pass="0" fail="0" skip="0">All Tests</stat></total></statistics>
</robot>""",
        encoding="utf-8",
    )
    payload = compare_xml_files(str(empty), str(empty))
    assert payload["summary"]["matched"] == 0
    assert payload["allComparisons"] == []
