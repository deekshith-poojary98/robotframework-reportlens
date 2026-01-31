"""CLI for robotframework-reportlens."""

import sys
from pathlib import Path

from .generator import RobotFrameworkReportGenerator


def main():
    import argparse
    parser = argparse.ArgumentParser(
        prog="reportlens",
        description="Generate a modern HTML report from Robot Framework XML output (output.xml).",
    )
    parser.add_argument(
        "xml_file",
        help="Path to Robot Framework XML output (e.g. output.xml)",
    )
    parser.add_argument(
        "-o", "--output",
        default="report.html",
        help="Output HTML file path (default: report.html)",
    )
    args = parser.parse_args()

    if not Path(args.xml_file).exists():
        print(f"Error: File not found: {args.xml_file}", file=sys.stderr)
        return 1

    try:
        generator = RobotFrameworkReportGenerator(args.xml_file)
        generator.generate_html(args.output)
        return 0
    except Exception as e:
        print(f"Error generating report: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
