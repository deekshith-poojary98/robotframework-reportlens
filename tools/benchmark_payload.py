"""Simple benchmark to generate external-data and report sizes.

Usage: python tools/benchmark_payload.py <path-to-output-xml> [out-dir]

Generates external-data into out-dir/report.html + reportlens-data/ and prints total size,
number of test files, avg test payload size, and total messages.

This is a conservative, fast script intended for local benchmarking.
"""

import sys
from pathlib import Path
import json

from robotframework_reportlens.generator import RobotFrameworkReportGenerator


def dir_size(path: Path) -> int:
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
    return total


def count_messages(data_dir: Path) -> int:
    # Count messages by summing lengths of keywordMessages lists in *_logs.json
    total_msgs = 0
    for f in data_dir.glob("test_*_logs.json"):
        try:
            obj = json.loads(f.read_text(encoding="utf-8"))
            km = obj.get("keywordMessages", {})
            for lst in km.values():
                total_msgs += len(lst)
        except Exception:
            continue
    return total_msgs


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/benchmark_payload.py <output.xml> [out-dir]")
        return 2
    xml = sys.argv[1]
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("benchmark-output")
    out.mkdir(parents=True, exist_ok=True)
    out_report = out / "report.html"
    gen = RobotFrameworkReportGenerator(xml)
    gen.generate_html(str(out_report), external_data=True)
    data_dir = out / "reportlens-data"
    total = dir_size(data_dir)
    num_tests = len(list(data_dir.glob("test_*.json")))
    avg = int(total / num_tests) if num_tests else 0
    msgs = count_messages(data_dir)
    print("Benchmark result:")
    print("  data_dir:", str(data_dir))
    print("  total_bytes:", total)
    print("  num_test_files:", num_tests)
    print("  avg_test_file_bytes:", avg)
    print("  total_messages:", msgs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
