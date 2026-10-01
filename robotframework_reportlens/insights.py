"""
Duration insights: slowest tests/keywords and a simple duration histogram.

Computed from ReportModel and attached to the template payload for triage
beyond pass/fail (Feature: Duration insights in 0.1.9).
"""

from __future__ import annotations

from typing import Any

from .builder import _all_tests
from .model import Keyword, ReportModel

# Cap lists so large suites stay UI-friendly
DEFAULT_TOP_N = 20
MAX_KEYWORD_WALK = 50_000


def _walk_keywords(
    keywords: list[Keyword],
    *,
    test_full_name: str,
    out: list[tuple[int, str, str, str]],
    limit: int,
) -> None:
    """Collect (duration_ms, name, status, test_full_name) for keywords."""
    for kw in keywords:
        if len(out) >= limit:
            return
        name = kw.name or (kw.badge or "Keyword")
        out.append((int(kw.duration or 0), name, kw.status or "", test_full_name))
        if kw.keywords:
            _walk_keywords(
                kw.keywords,
                test_full_name=test_full_name,
                out=out,
                limit=limit,
            )


def _histogram(durations_ms: list[int]) -> list[dict[str, Any]]:
    """Fixed buckets suitable for triage (ms)."""
    buckets = [
        (0, 100, "0–100ms"),
        (100, 500, "100–500ms"),
        (500, 1000, "0.5–1s"),
        (1000, 5000, "1–5s"),
        (5000, 30000, "5–30s"),
        (30000, None, "30s+"),
    ]
    counts = [0] * len(buckets)
    for d in durations_ms:
        d = max(0, int(d or 0))
        for i, (lo, hi, _) in enumerate(buckets):
            if hi is None:
                if d >= lo:
                    counts[i] += 1
                    break
            elif lo <= d < hi:
                counts[i] += 1
                break
    total = len(durations_ms) or 1
    return [
        {
            "label": label,
            "count": counts[i],
            "pct": round(counts[i] * 100 / total, 1),
        }
        for i, (_, _, label) in enumerate(buckets)
    ]


def compute_duration_insights(
    model: ReportModel, *, top_n: int = DEFAULT_TOP_N
) -> dict[str, Any]:
    """
    Build duration insights dict for the report payload.

    Returns:
      slowestTests, slowestKeywords, histogram, totals
    """
    tests = _all_tests(model.root_suite) if model.root_suite else []
    test_rows = sorted(
        [
            {
                "id": t.id,
                "name": t.name,
                "fullName": t.full_name,
                "status": t.status,
                "duration": int(t.duration or 0),
            }
            for t in tests
        ],
        key=lambda r: r["duration"],
        reverse=True,
    )

    kw_rows: list[tuple[int, str, str, str]] = []
    for t in tests:
        kws: list[Keyword] = []
        if t.setup:
            kws.append(t.setup)
        kws.extend(t.keywords or [])
        if t.teardown:
            kws.append(t.teardown)
        _walk_keywords(
            kws, test_full_name=t.full_name, out=kw_rows, limit=MAX_KEYWORD_WALK
        )

    kw_rows.sort(key=lambda r: r[0], reverse=True)
    slowest_keywords = [
        {
            "name": name,
            "status": status,
            "duration": dur,
            "testFullName": test_fn,
        }
        for dur, name, status, test_fn in kw_rows[:top_n]
    ]

    durations = [int(t.duration or 0) for t in tests]
    return {
        "slowestTests": test_rows[:top_n],
        "slowestKeywords": slowest_keywords,
        "histogram": _histogram(durations),
        "totals": {
            "tests": len(tests),
            "keywordsSampled": len(kw_rows),
            "totalDurationMs": sum(durations),
            "maxTestDurationMs": max(durations) if durations else 0,
        },
    }
