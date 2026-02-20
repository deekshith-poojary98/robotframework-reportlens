"""Pytest fixtures for robotframework-reportlens tests."""

import pytest
from pathlib import Path


@pytest.fixture
def fixtures_dir():
    """Path to the tests/fixtures directory."""
    return Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def minimal_xml_path(fixtures_dir):
    """Path to minimal valid Robot Framework output.xml."""
    path = fixtures_dir / "minimal_output.xml"
    assert path.exists(), f"Fixture not found: {path}"
    return str(path)


@pytest.fixture
def control_structures_xml_path(fixtures_dir):
    """Path to output.xml with FOR/IF/TRY (project root). Skip if not found (run robot_tests to generate)."""
    path = fixtures_dir.parent.parent / "output.xml"
    if not path.exists():
        pytest.skip("output.xml not found at project root (run: robot robot_tests/accounts.robot)")
    return str(path)


@pytest.fixture
def sample_output_xml(tmp_path):
    """Create a minimal output.xml in a temp directory (for CLI tests)."""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2026-01-31T12:00:00" rpa="false" schemaversion="5">
<suite id="s1" name="Sample" source="sample.robot">
<test id="s1-t1" name="Sample Test">
<kw name="Log" owner="BuiltIn">
<status status="PASS" start="2026-01-31T12:00:01" elapsed="0.001"/>
</kw>
<status status="PASS" start="2026-01-31T12:00:01" elapsed="0.001"/>
</test>
<status status="PASS" start="2026-01-31T12:00:01" elapsed="0.002"/>
</suite>
<statistics>
<total>
<stat pass="1" fail="0" skip="0">All Tests</stat>
</total>
</statistics>
</robot>
"""
    path = tmp_path / "output.xml"
    path.write_text(xml_content, encoding="utf-8")
    return path
