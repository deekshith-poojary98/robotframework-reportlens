"""CLI for robotframework-reportlens."""

import argparse
import os
import sys
from pathlib import Path


def main():
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
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print builder debug info to stderr (e.g. why test keywords may be empty).",
    )
    args = parser.parse_args()

    if args.debug:
        os.environ["BUILD_DEBUG"] = "1"

    # Import after setting BUILD_DEBUG so builder picks it up
    from .generator import RobotFrameworkReportGenerator

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
