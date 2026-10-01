"""CLI for robotframework-reportlens."""

import argparse
import os
import sys
from pathlib import Path


def _add_generate_flags(parser: argparse.ArgumentParser) -> None:
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
            "Requires --external-data."
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print builder debug info to stderr.",
    )
    parser.add_argument(
        "--loglevel",
        choices=["TRACE", "DEBUG", "INFO", "WARN", "ERROR"],
        default=None,
        help="Minimum log level to include (default: DEBUG for external-data, TRACE otherwise).",
    )


def _parser_generate() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="reportlens",
        description="Generate a modern HTML report from Robot Framework XML output (output.xml).",
    )
    p.add_argument("xml_file", help="Path to Robot Framework XML output (e.g. output.xml)")
    _add_generate_flags(p)
    return p


def _parser_compare() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="reportlens compare",
        description="Compare two Robot Framework runs (newly failing/passing, duration deltas).",
    )
    p.add_argument("xml_a", help="Baseline output.xml (run A)")
    p.add_argument("xml_b", help="Candidate output.xml (run B)")
    p.add_argument(
        "-o",
        "--output",
        default="compare.html",
        help="Output HTML file path (default: compare.html)",
    )
    p.add_argument("--label-a", default="Run A", help="Label for run A")
    p.add_argument("--label-b", default="Run B", help="Label for run B")
    p.add_argument("--debug", action="store_true")
    p.add_argument(
        "--loglevel",
        choices=["TRACE", "DEBUG", "INFO", "WARN", "ERROR"],
        default=None,
    )
    return p


def _parser_merge() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="reportlens merge",
        description="Merge multiple XMLs (shards/retries) into one report with attempt history.",
    )
    p.add_argument(
        "xml_files",
        nargs="+",
        help="One or more output.xml files (shards or retries)",
    )
    p.add_argument(
        "--name",
        default="MERGED",
        help="Root suite name for the merged report (default: MERGED)",
    )
    _add_generate_flags(p)
    return p


def _parser_live() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="reportlens live",
        description="Prepare a live-report folder and print the robot --listener command.",
    )
    p.add_argument(
        "--outdir",
        default="live-report",
        help="Directory for live.html and live-data/ (default: live-report)",
    )
    return p


def _print_top_help() -> None:
    print(
        """usage: reportlens [-h] ...
       reportlens compare [-h] ...
       reportlens merge [-h] ...
       reportlens live [-h] ...

Generate a modern HTML report from Robot Framework XML output.

commands:
  (default)   reportlens output.xml -o report.html
  compare     Compare two runs (newly failing/passing, duration deltas)
  merge       Merge shards/retries into one report with attempt history
  live        Prepare live listener output folder

Run 'reportlens <command> -h' for command-specific help.
"""
    )


def _cmd_generate(args) -> int:
    from .builder import _LEVELS
    from .generator import RobotFrameworkReportGenerator

    if not Path(args.xml_file).exists():
        print(f"Error: File not found: {args.xml_file}", file=sys.stderr)
        return 1

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


def _cmd_compare(args) -> int:
    from .builder import _LEVELS
    from .compare import compare_xml_files
    from .generator import RobotFrameworkReportGenerator

    for path, label in ((args.xml_a, "A"), (args.xml_b, "B")):
        if not Path(path).exists():
            print(f"Error: File not found (run {label}): {path}", file=sys.stderr)
            return 1
    level = _LEVELS.get(args.loglevel.upper()) if args.loglevel else _LEVELS["TRACE"]
    try:
        payload = compare_xml_files(
            args.xml_a,
            args.xml_b,
            label_a=args.label_a,
            label_b=args.label_b,
            min_log_level=level,
        )
        gen = RobotFrameworkReportGenerator.from_payload(payload)
        gen.generate_html(args.output, external_data=False)
        return 0
    except Exception as e:
        print(f"Error comparing runs: {e}", file=sys.stderr)
        return 1


def _cmd_merge(args) -> int:
    from .builder import _LEVELS
    from .generator import RobotFrameworkReportGenerator
    from .merge import merge_xml_files

    for path in args.xml_files:
        if not Path(path).exists():
            print(f"Error: File not found: {path}", file=sys.stderr)
            return 1
    level = (
        _LEVELS.get(args.loglevel.upper())
        if args.loglevel
        else (_LEVELS["DEBUG"] if args.external_data else _LEVELS["TRACE"])
    )
    try:
        model = merge_xml_files(
            args.xml_files, min_log_level=level, merged_name=args.name
        )
        gen = RobotFrameworkReportGenerator.from_model(
            model,
            external_data=args.external_data,
            compress_data=args.compress_data,
        )
        gen.generate_html(args.output, external_data=args.external_data)
        return 0
    except Exception as e:
        print(f"Error merging reports: {e}", file=sys.stderr)
        return 1


def _cmd_live(args) -> int:
    from .listener import LiveReportListener

    outdir = args.outdir
    LiveReportListener(outdir=outdir)
    listener_path = "robotframework_reportlens.listener.LiveReportListener"
    print(f"Live report folder ready: {outdir}/")
    print(f"  Open: {outdir}/live.html (via http.server if needed)")
    print()
    print("Run Robot with:")
    print(f"  robot --listener {listener_path}:outdir={outdir} your_suite.robot")
    print()
    print("After the run finishes you can also generate a full post-process report:")
    print("  reportlens output.xml -o report.html")
    return 0


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        _print_top_help()
        if argv and argv[0] in ("-h", "--help"):
            # Also show generate help for discoverability
            _parser_generate().print_help()
        return 0 if argv else 1

    command = argv[0]
    if command == "compare":
        args = _parser_compare().parse_args(argv[1:])
        if args.debug:
            os.environ["BUILD_DEBUG"] = "1"
        return _cmd_compare(args)
    if command == "merge":
        args = _parser_merge().parse_args(argv[1:])
        if args.debug:
            os.environ["BUILD_DEBUG"] = "1"
        return _cmd_merge(args)
    if command == "live":
        args = _parser_live().parse_args(argv[1:])
        return _cmd_live(args)
    if command == "generate":
        args = _parser_generate().parse_args(argv[1:])
        if args.debug:
            os.environ["BUILD_DEBUG"] = "1"
        return _cmd_generate(args)

    # Backward compatible: reportlens output.xml -o report.html
    args = _parser_generate().parse_args(argv)
    if args.debug:
        os.environ["BUILD_DEBUG"] = "1"
    return _cmd_generate(args)


if __name__ == "__main__":
    sys.exit(main())
