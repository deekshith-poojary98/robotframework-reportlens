"""Tests for the reportlens CLI."""

from unittest.mock import patch
from robotframework_reportlens.cli import main


def test_cli_missing_file_returns_1_and_prints_error(capsys):
    """When xml_file does not exist, main returns 1 and prints to stderr."""
    with patch("sys.argv", ["reportlens", "/nonexistent/output.xml"]):
        exit_code = main()
    assert exit_code == 1
    out, err = capsys.readouterr()
    assert "Error:" in err
    assert "not found" in err or "File not found" in err
    assert "/nonexistent/output.xml" in err


def test_cli_valid_file_generates_report_and_returns_0(tmp_path, sample_output_xml):
    """With a valid xml file, main generates report and returns 0."""
    out_html = tmp_path / "report.html"
    with patch("sys.argv", ["reportlens", str(sample_output_xml), "-o", str(out_html)]):
        exit_code = main()
    assert exit_code == 0
    assert out_html.exists()
    content = out_html.read_text(encoding="utf-8")
    assert "report-data" in content
    assert "<!DOCTYPE html>" in content


def test_cli_default_output_path(tmp_path, sample_output_xml, monkeypatch):
    """Without -o, report is written to report.html in cwd."""
    monkeypatch.chdir(tmp_path)
    with patch("sys.argv", ["reportlens", str(sample_output_xml)]):
        exit_code = main()
    assert exit_code == 0
    default_report = tmp_path / "report.html"
    assert default_report.exists()


def test_cli_generator_exception_returns_1(capsys, tmp_path):
    """When generator raises, main returns 1 and prints error."""
    invalid_xml = tmp_path / "bad.xml"
    invalid_xml.write_text("not valid xml", encoding="utf-8")
    with patch("sys.argv", ["reportlens", str(invalid_xml), "-o", str(tmp_path / "out.html")]):
        exit_code = main()
    assert exit_code == 1
    out, err = capsys.readouterr()
    assert "Error" in err


def test_cli_success_prints_message(capsys, tmp_path, sample_output_xml):
    """With valid xml, main prints a message about the generated report."""
    out_html = tmp_path / "report.html"
    with patch("sys.argv", ["reportlens", str(sample_output_xml), "-o", str(out_html)]):
        main()
    out, err = capsys.readouterr()
    assert "Report generated" in out
    assert "report.html" in out or str(out_html.name) in out


def test_cli_custom_output_filename(tmp_path, sample_output_xml):
    """-o can specify a custom output path."""
    custom = tmp_path / "custom_report.html"
    with patch("sys.argv", ["reportlens", str(sample_output_xml), "-o", str(custom)]):
        exit_code = main()
    assert exit_code == 0
    assert custom.exists()
    assert custom.read_text(encoding="utf-8").count("report-data") >= 1
