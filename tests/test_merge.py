"""Tests for merge / rebot mode (Feature 2 — 0.1.9)."""

from pathlib import Path
from unittest.mock import patch

from robotframework_reportlens.builder import _all_tests, build_report_model
from robotframework_reportlens.cli import main
from robotframework_reportlens.merge import merge_models, merge_xml_files
from robotframework_reportlens.serialize import model_to_payload


def _xml(path: Path, suite_name: str, tests: list[tuple[str, str, str]]) -> Path:
    """tests: (name, status, elapsed)"""
    parts = []
    p = f = s = 0
    for i, (name, status, elapsed) in enumerate(tests, start=1):
        st = status.upper()
        if st == "PASS":
            p += 1
        elif st == "FAIL":
            f += 1
        else:
            s += 1
        parts.append(
            f'<test id="s1-t{i}" name="{name}">'
            f'<status status="{st}" start="2026-01-31T12:00:0{i}" elapsed="{elapsed}">'
            f'{"err" if st == "FAIL" else ""}</status></test>'
        )
    path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2026-01-31T12:00:00" schemaversion="5">
<suite id="s1" name="{suite_name}">
{"".join(parts)}
<status status="{"FAIL" if f else "PASS"}" start="2026-01-31T12:00:01" elapsed="1"/>
</suite>
<statistics><total><stat pass="{p}" fail="{f}" skip="{s}">All Tests</stat></total></statistics>
</robot>""",
        encoding="utf-8",
    )
    return path


def test_merge_single_xml_is_noop(minimal_xml_path):
    model = merge_xml_files([minimal_xml_path])
    original = build_report_model(minimal_xml_path)
    assert model.statistics["total"] == original.statistics["total"]
    assert len(_all_tests(model.root_suite)) == len(_all_tests(original.root_suite))


def test_merge_shards_unions_tests(tmp_path):
    a = _xml(tmp_path / "shard1.xml", "Shard", [("TestOne", "PASS", "0.01")])
    b = _xml(tmp_path / "shard2.xml", "Shard", [("TestTwo", "FAIL", "0.02")])
    merged = merge_xml_files([str(a), str(b)], merged_name="MERGED")
    names = {t.name for t in _all_tests(merged.root_suite)}
    assert names == {"TestOne", "TestTwo"}
    assert merged.statistics["total"] == 2
    assert merged.statistics["failed"] == 1
    assert merged.statistics["passed"] == 1


def test_merge_retries_preserves_attempt_history(tmp_path):
    a = _xml(tmp_path / "try1.xml", "Suite", [("Flaky", "FAIL", "0.10")])
    b = _xml(tmp_path / "try2.xml", "Suite", [("Flaky", "PASS", "0.20")])
    merged = merge_xml_files([str(a), str(b)])
    tests = _all_tests(merged.root_suite)
    assert len(tests) == 1
    t = tests[0]
    assert t.status == "PASS"  # last wins
    assert len(t.attempts) == 2
    assert t.attempts[0]["status"] == "FAIL"
    assert t.attempts[1]["status"] == "PASS"
    payload = model_to_payload(merged)
    # Find test in payload
    def find(suite):
        for x in suite.get("tests") or []:
            if x.get("name") == "Flaky":
                return x
        for ch in suite.get("suites") or []:
            found = find(ch)
            if found:
                return found
        return None

    pt = find(payload["rootSuite"])
    assert pt is not None
    assert "attempts" in pt
    assert len(pt["attempts"]) == 2


def test_merge_duplicate_names_across_retries(tmp_path):
    files = [
        _xml(tmp_path / f"r{i}.xml", "S", [("Same", "FAIL" if i < 2 else "PASS", "0.01")])
        for i in range(3)
    ]
    merged = merge_xml_files([str(p) for p in files])
    t = _all_tests(merged.root_suite)[0]
    assert len(t.attempts) == 3
    assert t.status == "PASS"


def test_merge_empty_xml(tmp_path):
    empty = tmp_path / "empty.xml"
    empty.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2026-01-31T12:00:00" schemaversion="5">
<suite id="s1" name="Empty"><status status="PASS" start="2026-01-31T12:00:01" elapsed="0"/></suite>
<statistics><total><stat pass="0" fail="0" skip="0">All Tests</stat></total></statistics>
</robot>""",
        encoding="utf-8",
    )
    other = _xml(tmp_path / "one.xml", "Empty", [("T", "PASS", "0.01")])
    merged = merge_xml_files([str(empty), str(other)])
    assert merged.statistics["total"] == 1


def test_merge_cli(tmp_path, minimal_xml_path):
    out = tmp_path / "merged.html"
    with patch(
        "sys.argv",
        ["reportlens", "merge", minimal_xml_path, minimal_xml_path, "-o", str(out)],
    ):
        assert main() == 0
    assert out.exists()
    assert "report-data" in out.read_text(encoding="utf-8")


def test_merge_missing_file(capsys, tmp_path, minimal_xml_path):
    with patch(
        "sys.argv",
        ["reportlens", "merge", minimal_xml_path, str(tmp_path / "missing.xml")],
    ):
        assert main() == 1
    assert "not found" in capsys.readouterr().err.lower()


def test_merge_models_requires_at_least_one():
    import pytest

    with pytest.raises(ValueError):
        merge_models([])


def test_merge_shards_keep_unique_ids_and_external_bodies(tmp_path):
    """Each shard's output.xml reuses s1-t1. Merged detail files must not overwrite."""
    import json

    from robotframework_reportlens.generator import RobotFrameworkReportGenerator

    def write(path: Path, name: str, status: str, message: str) -> None:
        path.write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2026-01-31T12:00:00" schemaversion="5">
<suite id="s1" name="Shard">
<test id="s1-t1" name="{name}">
<kw name="Step {name}"><status status="{status}" start="2026-01-31T12:00:01" elapsed="0.01">{message}</status></kw>
<status status="{status}" start="2026-01-31T12:00:01" elapsed="0.01">{message}</status>
</test>
<status status="{status}" start="2026-01-31T12:00:01" elapsed="0.01"/>
</suite>
<statistics><total><stat pass="{'1' if status == 'PASS' else '0'}" fail="{'1' if status == 'FAIL' else '0'}" skip="0">All Tests</stat></total></statistics>
</robot>""",
            encoding="utf-8",
        )

    a = tmp_path / "shard1.xml"
    b = tmp_path / "shard2.xml"
    write(a, "Alpha", "PASS", "ok-alpha")
    write(b, "Beta", "FAIL", "beta-broke")
    merged = merge_xml_files([str(a), str(b)])
    tests = _all_tests(merged.root_suite)
    assert {t.name for t in tests} == {"Alpha", "Beta"}
    assert len({t.id for t in tests}) == 2
    alpha = next(t for t in tests if t.name == "Alpha")
    beta = next(t for t in tests if t.name == "Beta")
    assert alpha.keywords[0].fail_message == "ok-alpha"
    assert beta.keywords[0].fail_message == "beta-broke"
    assert alpha.keywords[0].id != beta.keywords[0].id

    out = tmp_path / "merged.html"
    gen = RobotFrameworkReportGenerator.from_model(merged, external_data=True)
    gen.generate_html(str(out), external_data=True)
    bodies = {}
    data_dir = tmp_path / "reportlens-data"
    for path in data_dir.glob("test_*.json"):
        if path.name.endswith("_logs.json"):
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        test = payload["test"]
        bodies[test["name"]] = test.get("message")
    assert bodies == {"Alpha": "ok-alpha", "Beta": "beta-broke"}


def test_merge_dotted_test_name_does_not_collapse_nested_suite(tmp_path):
    """A test named 'API.Health' is not the same test as suite API / test Health."""
    dotted = tmp_path / "dotted.xml"
    nested = tmp_path / "nested.xml"
    dotted.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2026-01-31T12:00:00" schemaversion="5">
<suite id="s1" name="Root">
<test id="s1-t1" name="API.Health">
<status status="PASS" start="2026-01-31T12:00:01" elapsed="0.01">dotted-ok</status>
</test>
<status status="PASS" start="2026-01-31T12:00:01" elapsed="0.01"/>
</suite>
<statistics><total><stat pass="1" fail="0" skip="0">All Tests</stat></total></statistics>
</robot>""",
        encoding="utf-8",
    )
    nested.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2026-01-31T12:00:00" schemaversion="5">
<suite id="s1" name="Root">
<suite id="s1-s1" name="API">
<test id="s1-s1-t1" name="Health">
<status status="FAIL" start="2026-01-31T12:00:01" elapsed="0.01">nested-fail</status>
</test>
<status status="FAIL" start="2026-01-31T12:00:01" elapsed="0.01"/>
</suite>
<status status="FAIL" start="2026-01-31T12:00:01" elapsed="0.01"/>
</suite>
<statistics><total><stat pass="0" fail="1" skip="0">All Tests</stat></total></statistics>
</robot>""",
        encoding="utf-8",
    )
    merged = merge_xml_files([str(dotted), str(nested)])
    tests = _all_tests(merged.root_suite)
    assert {t.name for t in tests} == {"API.Health", "Health"}
    assert merged.statistics["total"] == 2
    assert merged.statistics["passed"] == 1
    assert merged.statistics["failed"] == 1
    assert all(len(t.attempts) == 1 for t in tests)
    dotted_test = next(t for t in tests if t.name == "API.Health")
    assert dotted_test.status == "PASS"
    assert dotted_test.message == "dotted-ok"
