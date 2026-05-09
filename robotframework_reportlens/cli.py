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
        "-o",
        "--output",
        default="report.html",
        help="Output HTML file path (default: report.html)",
    )
    parser.add_argument(
        "--external-data",
        action="store_true",
        help="Write report.html plus split JSON files under reportlens-data/ for lazy loading.",
    )
    parser.add_argument(
        "--compress-data",
        action="store_true",
        help=(
            "Write gzip-compressed .json.gz files instead of plain .json in reportlens-data/. "
            "Requires --external-data. Produces the smallest possible output (~97%% smaller at 10k tests). "
            "Requires Chrome 80+, Edge 80+, Firefox 113+, or Safari 16.4+ (DecompressionStream API). "
            "Reports will not load in older browsers — a clear error banner is shown instead."
        ),
    )
    # TODO: needs to improvise this feature for better debugging which users can use to debug the report
    # as well as raise issues if needed with debug logs attached
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print builder debug info to stderr (e.g. why test keywords may be empty).",
    )
    parser.add_argument(
        "--loglevel",
        choices=["TRACE", "DEBUG", "INFO", "WARN", "ERROR"],
        default=None,
        help="Minimum log level to include in external-data payloads (default: DEBUG, excludes TRACE).",
    )
    args = parser.parse_args()

    if args.debug:
        os.environ["BUILD_DEBUG"] = "1"

    # Import after setting BUILD_DEBUG so builder picks it up
    from .builder import _LEVELS
    from .generator import RobotFrameworkReportGenerator

    if not Path(args.xml_file).exists():
        print(f"Error: File not found: {args.xml_file}", file=sys.stderr)
        return 1

    # Resolve explicit min_log_level (None means generator will pick mode-appropriate default)
    min_log_level = _LEVELS.get(args.loglevel.upper()) if args.loglevel else None

    try:
        generator = RobotFrameworkReportGenerator(
            args.xml_file,
            external_data=args.external_data,
            min_log_level=min_log_level,
            compress_data=args.compress_data,
        )
        generator.generate_html(args.output, external_data=args.external_data)
        return 0
    except Exception as e:
        print(f"Error generating report: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
