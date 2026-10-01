"""
Compare two Robot Framework runs (ReportModel A vs B).

Joins tests by suite path and test name (stable across re-runs). Produces a compare payload
for the HTML template: newly failing/passing, still failing, only-in-A/B,
and duration deltas.
"""

from __future__ import annotations

from typing import Any

from .builder import _iter_tests_with_suite_path, build_report_model
from .model import ReportModel, Test

# Separates path segments in compareKey. Dots are not safe: test and suite
# names may themselves contain ".".
_PATH_SEP = "\x1f"

# Default QA noise floor for duration triage (UI can raise).
_DURATION_NOISE_MS = 100


def _normalize_tags(tags: list | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for tag in tags or []:
        if tag and tag not in seen:
            seen.add(tag)
            out.append(tag)
    return out


def _tag_diff(tags_a: list | None, tags_b: list | None) -> tuple[list[str], list[str]]:
    set_a = set(_normalize_tags(tags_a))
    set_b = set(_normalize_tags(tags_b))
    added = sorted(set_b - set_a)
    removed = sorted(set_a - set_b)
    return added, removed


def _merge_tags(*tag_lists: list | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for tags in tag_lists:
        for tag in tags or []:
            if tag and tag not in seen:
                seen.add(tag)
                out.append(tag)
    return out


def _health_verdict(
    *,
    newly_failing: int,
    newly_passing: int,
    fail_delta: int,
    pass_rate_delta: int,
) -> tuple[str, str]:
    """Return (verdict, short label) for QA triage."""
    if newly_failing and newly_passing:
        return "mixed", "Mixed — regressions and fixes"
    if newly_failing > 0:
        return "worse", "Worse — new regressions"
    if newly_passing > 0 or fail_delta < 0 or pass_rate_delta > 0:
        return "better", "Better — improvements"
    if fail_delta > 0 or pass_rate_delta < 0:
        return "worse", "Worse — more failures"
    return "same", "Same — no status regressions"


def _run_summary(model: ReportModel, label: str, source: str = "") -> dict[str, Any]:
    return {
        "label": label,
        "source": source,
        "generated": model.generated,
        "generator": model.generator,
        "startTime": model.start_time,
        "duration": model.duration,
        "statistics": dict(model.statistics or {}),
        "rootSuiteName": model.root_suite.name if model.root_suite else "",
    }


def _index_tests(model: ReportModel) -> dict[tuple[str, ...], Test]:
    """
    Map (suite names under root, test name) -> Test (last wins on duplicates).

    The root suite name is not part of the key, so runs still join when the
    root label differs. Names are not split on ".", so a test called
    ``API.Health`` does not collide with suite ``API`` / test ``Health``.
    """
    out: dict[tuple[str, ...], Test] = {}
    if not model.root_suite:
        return out
    for parts, test in _iter_tests_with_suite_path(model.root_suite):
        name = test.name or ""
        if not parts and not name:
            continue
        out[parts + (name,)] = test
    return out


def _path_label(key: tuple[str, ...]) -> str:
    return ".".join(key)


def _path_token(key: tuple[str, ...]) -> str:
    return _PATH_SEP.join(key)


def _entry_base(
    *,
    key: tuple[str, ...],
    name: str,
    category: str,
    status_a: str | None,
    status_b: str | None,
    duration_a: int | None,
    duration_b: int | None,
    duration_delta: int | None,
    message_a: str,
    message_b: str,
    tags_a: list[str],
    tags_b: list[str],
    tags_added: list[str],
    tags_removed: list[str],
) -> dict[str, Any]:
    suite_parts = key[:-1] if key else ()
    return {
        "fullName": _path_label(key),
        "compareKey": _path_token(key),
        "name": name,
        "suitePath": _path_label(suite_parts) if suite_parts else "",
        "category": category,
        "statusA": status_a,
        "statusB": status_b,
        "durationA": duration_a,
        "durationB": duration_b,
        "durationDelta": duration_delta,
        "messageA": message_a,
        "messageB": message_b,
        "messageChanged": message_a != message_b,
        "tags": _merge_tags(tags_a, tags_b),
        "tagsAdded": tags_added,
        "tagsRemoved": tags_removed,
    }


def _is_meaningful_diff(entry: dict[str, Any], *, duration_noise_ms: int) -> bool:
    if entry.get("category") and entry["category"] != "unchanged":
        return True
    if abs(int(entry.get("durationDelta") or 0)) >= duration_noise_ms:
        return True
    if entry.get("messageChanged"):
        return True
    if entry.get("tagsAdded") or entry.get("tagsRemoved"):
        return True
    return False


def compare_models(
    model_a: ReportModel,
    model_b: ReportModel,
    *,
    label_a: str = "Run A",
    label_b: str = "Run B",
    source_a: str = "",
    source_b: str = "",
) -> dict[str, Any]:
    """
    Compare two report models. Returns a template payload with mode='compare'.
    """
    map_a = _index_tests(model_a)
    map_b = _index_tests(model_b)
    keys_a = set(map_a)
    keys_b = set(map_b)

    newly_failing: list[dict] = []
    newly_passing: list[dict] = []
    still_failing: list[dict] = []
    status_changed: list[dict] = []
    only_in_a: list[dict] = []
    only_in_b: list[dict] = []
    duration_changes: list[dict] = []
    all_comparisons: list[dict] = []
    matched_duration_a = 0
    matched_duration_b = 0
    duration_noise_ms = _DURATION_NOISE_MS

    for key in sorted(keys_a | keys_b):
        ta = map_a.get(key)
        tb = map_b.get(key)

        if ta and not tb:
            tags_a = _normalize_tags(ta.tags)
            entry = _entry_base(
                key=key,
                name=ta.name,
                category="only_in_a",
                status_a=ta.status,
                status_b=None,
                duration_a=ta.duration,
                duration_b=None,
                duration_delta=None,
                message_a=ta.message or "",
                message_b="",
                tags_a=tags_a,
                tags_b=[],
                tags_added=[],
                tags_removed=tags_a,
            )
            only_in_a.append(entry)
            all_comparisons.append(entry)
            continue

        if tb and not ta:
            tags_b = _normalize_tags(tb.tags)
            entry = _entry_base(
                key=key,
                name=tb.name,
                category="only_in_b",
                status_a=None,
                status_b=tb.status,
                duration_a=None,
                duration_b=tb.duration,
                duration_delta=None,
                message_a="",
                message_b=tb.message or "",
                tags_a=[],
                tags_b=tags_b,
                tags_added=tags_b,
                tags_removed=[],
            )
            only_in_b.append(entry)
            all_comparisons.append(entry)
            continue

        assert ta is not None and tb is not None
        status_a = (ta.status or "").upper()
        status_b = (tb.status or "").upper()
        delta = int(tb.duration) - int(ta.duration)
        matched_duration_a += int(ta.duration or 0)
        matched_duration_b += int(tb.duration or 0)
        category = "unchanged"
        if status_a != status_b:
            if status_b == "FAIL" and status_a != "FAIL":
                category = "newly_failing"
            elif status_a == "FAIL" and status_b == "PASS":
                category = "newly_passing"
            else:
                category = "status_changed"
        elif status_a == "FAIL" and status_b == "FAIL":
            category = "still_failing"

        tags_a = _normalize_tags(ta.tags)
        tags_b = _normalize_tags(tb.tags)
        tags_added, tags_removed = _tag_diff(tags_a, tags_b)
        entry = _entry_base(
            key=key,
            name=tb.name or ta.name,
            category=category,
            status_a=status_a,
            status_b=status_b,
            duration_a=ta.duration,
            duration_b=tb.duration,
            duration_delta=delta,
            message_a=ta.message or "",
            message_b=tb.message or "",
            tags_a=tags_a,
            tags_b=tags_b,
            tags_added=tags_added,
            tags_removed=tags_removed,
        )
        if category == "newly_failing":
            newly_failing.append(entry)
        elif category == "newly_passing":
            newly_passing.append(entry)
        elif category == "still_failing":
            still_failing.append(entry)
        elif category == "status_changed":
            status_changed.append(entry)

        if abs(delta) >= duration_noise_ms:
            duration_changes.append(entry)

        if _is_meaningful_diff(entry, duration_noise_ms=duration_noise_ms):
            all_comparisons.append(entry)

    duration_changes.sort(key=lambda e: abs(e["durationDelta"] or 0), reverse=True)

    stats_a = model_a.statistics or {}
    stats_b = model_b.statistics or {}
    total_a = int(stats_a.get("total", 0) or 0)
    total_b = int(stats_b.get("total", 0) or 0)
    pass_a = int(stats_a.get("passed", 0) or 0)
    pass_b = int(stats_b.get("passed", 0) or 0)
    fail_a = int(stats_a.get("failed", 0) or 0)
    fail_b = int(stats_b.get("failed", 0) or 0)
    skip_a = int(stats_a.get("skipped", 0) or 0)
    skip_b = int(stats_b.get("skipped", 0) or 0)
    rate_a = int(stats_a.get("passRate", 0) or 0)
    rate_b = int(stats_b.get("passRate", 0) or 0)
    # Prefer summed matched-test durations over suite wall-clock (often identical).
    dur_a = matched_duration_a if matched_duration_a else int(model_a.duration or 0)
    dur_b = matched_duration_b if matched_duration_b else int(model_b.duration or 0)
    fail_delta = fail_b - fail_a
    rate_delta = rate_b - rate_a
    verdict, verdict_label = _health_verdict(
        newly_failing=len(newly_failing),
        newly_passing=len(newly_passing),
        fail_delta=fail_delta,
        pass_rate_delta=rate_delta,
    )

    return {
        "mode": "compare",
        "generated": model_b.generated or model_a.generated,
        "generator": "ReportLens Compare",
        "runA": _run_summary(model_a, label_a, source_a),
        "runB": _run_summary(model_b, label_b, source_b),
        "summary": {
            "matched": len(keys_a & keys_b),
            "onlyInA": len(only_in_a),
            "onlyInB": len(only_in_b),
            "newlyFailing": len(newly_failing),
            "newlyPassing": len(newly_passing),
            "stillFailing": len(still_failing),
            "statusChanged": len(status_changed),
            "passA": pass_a,
            "failA": fail_a,
            "skipA": skip_a,
            "passB": pass_b,
            "failB": fail_b,
            "skipB": skip_b,
            "totalA": total_a,
            "totalB": total_b,
            "passRateA": rate_a,
            "passRateB": rate_b,
            "passRateDelta": rate_delta,
            "failDelta": fail_delta,
            "durationA": dur_a,
            "durationB": dur_b,
            "durationDelta": dur_b - dur_a,
            "durationBasis": "matched_tests" if matched_duration_a or matched_duration_b else "suite",
            "verdict": verdict,
            "verdictLabel": verdict_label,
            "blockerCount": len(newly_failing),
            "durationNoiseMs": duration_noise_ms,
            "significantDurationChanges": len(duration_changes),
            "diffCount": len(all_comparisons),
        },
        "newlyFailing": newly_failing,
        "newlyPassing": newly_passing,
        "stillFailing": still_failing,
        "statusChanged": status_changed,
        "onlyInA": only_in_a,
        "onlyInB": only_in_b,
        "durationChanges": duration_changes,
        "significantDurationChanges": duration_changes,
        "blockers": newly_failing[:8],
        "allComparisons": all_comparisons,
        # Minimal rootSuite so shared template boot paths don't crash
        "statistics": {
            "total": len(all_comparisons),
            "passed": len(newly_passing),
            "failed": len(newly_failing),
            "skipped": 0,
            "passRate": max(0, min(100, rate_b)),
        },
        "rootSuite": {
            "id": "compare-root",
            "name": f"Compare: {label_a} vs {label_b}",
            "fullName": f"Compare: {label_a} vs {label_b}",
            "status": "FAIL" if newly_failing else "PASS",
            "duration": 0,
            "statistics": {
                "total": len(keys_a | keys_b),
                "passed": len(newly_passing),
                "failed": len(newly_failing),
                "skipped": 0,
            },
            "tests": [],
            "suites": [],
        },
        "startTime": model_b.start_time or model_a.start_time,
        "duration": dur_b,
        "errors": [],
    }


def compare_xml_files(
    xml_a: str,
    xml_b: str,
    *,
    label_a: str = "Run A",
    label_b: str = "Run B",
    min_log_level: int | None = None,
) -> dict[str, Any]:
    """Load two output.xml files and return a compare payload."""
    from .builder import _LEVELS

    level = min_log_level if min_log_level is not None else _LEVELS["TRACE"]
    model_a = build_report_model(xml_a, min_log_level=level)
    model_b = build_report_model(xml_b, min_log_level=level)
    return compare_models(
        model_a,
        model_b,
        label_a=label_a,
        label_b=label_b,
        source_a=xml_a,
        source_b=xml_b,
    )
