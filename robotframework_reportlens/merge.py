"""
Merge multiple Robot Framework output.xml files into one ReportModel.

Use cases:
- CI shards (different tests across files) → union under one report
- Retries (same suite path and test name in multiple files) → attempt history; last attempt wins

Single-XML merge is a no-op (returns that model with the same content).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from .builder import _LEVELS, _all_tests, _iter_tests_with_suite_path, build_report_model
from .model import Keyword, ReportModel, Suite, Test


def _attempt_dict(test: Test, index: int, source: str) -> dict[str, Any]:
    return {
        "index": index,
        "status": test.status,
        "duration": test.duration,
        "message": test.message or "",
        "startTime": test.start_time or "",
        "source": source,
        "id": test.id,
    }


def _ensure_suite_path(root: Suite, name_parts: list[str]) -> Suite:
    """Ensure nested suites exist under root for name_parts. Return leaf suite."""
    current = root
    for name in name_parts:
        found = next((c for c in current.suites if c.name == name), None)
        if found is None:
            suite_id = f"{current.id}-s{len(current.suites) + 1}"
            full = f"{current.full_name}.{name}" if current.full_name else name
            found = Suite(
                id=suite_id,
                name=name,
                full_name=full,
                status="PASS",
                start_time="",
                duration=0,
                source="",
                tests=[],
                suites=[],
                statistics={"total": 0, "passed": 0, "failed": 0, "skipped": 0},
            )
            current.suites.append(found)
        current = found
    return current


def _unique_test_id(preferred: str, used: set[str]) -> str:
    """Return ``preferred`` or a ``~N`` suffix that is not already in ``used``."""
    base = preferred or "test"
    if base not in used:
        return base
    n = 2
    candidate = f"{base}~{n}"
    while candidate in used:
        n += 1
        candidate = f"{base}~{n}"
    return candidate


def _rebind_keyword(kw: Keyword, old_id: str, new_id: str) -> Keyword:
    """Point keyword ids at ``new_id`` so two merged tests cannot share kw ids."""
    old_prefix = f"kw-{old_id}-" if old_id else ""
    new_prefix = f"kw-{new_id}-"
    if old_prefix and kw.id.startswith(old_prefix):
        kw_id = new_prefix + kw.id[len(old_prefix) :]
    else:
        kw_id = f"{new_prefix}{kw.id}" if kw.id else f"{new_prefix}0"
    children = [_rebind_keyword(child, old_id, new_id) for child in kw.keywords]
    return replace(kw, id=kw_id, keywords=children)


def _rebind_test_keywords(test: Test, old_id: str, new_id: str) -> Test:
    if not old_id or old_id == new_id:
        return test
    return replace(
        test,
        keywords=[_rebind_keyword(kw, old_id, new_id) for kw in test.keywords],
        setup=_rebind_keyword(test.setup, old_id, new_id) if test.setup else None,
        teardown=_rebind_keyword(test.teardown, old_id, new_id) if test.teardown else None,
    )


def _recompute_suite_stats(suite: Suite) -> None:
    for child in suite.suites:
        _recompute_suite_stats(child)
    passed = sum(1 for t in suite.tests if t.status == "PASS")
    failed = sum(1 for t in suite.tests if t.status == "FAIL")
    skipped = sum(1 for t in suite.tests if t.status == "SKIP")
    for child in suite.suites:
        st = child.statistics or {}
        passed += st.get("passed", 0)
        failed += st.get("failed", 0)
        skipped += st.get("skipped", 0)
    total = passed + failed + skipped
    suite.statistics = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
    }
    if failed:
        suite.status = "FAIL"
    elif skipped and not passed:
        suite.status = "SKIP"
    else:
        suite.status = "PASS"
    suite.duration = sum(t.duration for t in suite.tests) + sum(
        s.duration for s in suite.suites
    )


def _replace_or_append_test(parent: Suite, test: Test) -> None:
    for i, existing in enumerate(parent.tests):
        if existing.name == test.name:
            parent.tests[i] = test
            return
    parent.tests.append(test)


def merge_models(
    models: list[ReportModel],
    *,
    sources: list[str] | None = None,
    merged_name: str = "MERGED",
) -> ReportModel:
    """
    Merge multiple ReportModels into one.

    Tests with the same relative fullName accumulate attempts; the last
    occurrence becomes the visible test body (status/keywords). Distinct
    tests are unioned into a shared suite tree.
    """
    if not models:
        raise ValueError("At least one report model is required to merge")
    sources = list(sources or [""] * len(models))
    if len(sources) < len(models):
        sources.extend([""] * (len(models) - len(sources)))

    if len(models) == 1:
        m = models[0]
        return ReportModel(
            generated=m.generated,
            generator=m.generator,
            start_time=m.start_time,
            end_time=m.end_time,
            duration=m.duration,
            statistics=dict(m.statistics or {}),
            errors=list(m.errors or []),
            root_suite=m.root_suite,
        )

    first = models[0]
    root = Suite(
        id="s0",
        name=merged_name,
        full_name=merged_name,
        status="PASS",
        start_time=first.start_time,
        duration=0,
        source="",
        tests=[],
        suites=[],
        statistics={"total": 0, "passed": 0, "failed": 0, "skipped": 0},
        setup=first.root_suite.setup,
        teardown=None,
    )

    # Identity is (suite name path, test name), not a dotted full_name.
    # Robot reuses ids like s1-t1 in every output.xml, so shards must not share ids.
    attempts_map: dict[tuple[tuple[str, ...], str], list[dict[str, Any]]] = {}
    test_map: dict[tuple[tuple[str, ...], str], Test] = {}
    used_ids: set[str] = set()

    for model, source in zip(models, sources):
        src_label = Path(source).name if source else ""
        for suite_parts, t in _iter_tests_with_suite_path(model.root_suite):
            test_name = t.name or ""
            if not suite_parts and not test_name:
                continue
            rel_key = (suite_parts, test_name)

            attempt_index = len(attempts_map.get(rel_key, [])) + 1
            attempt = _attempt_dict(t, attempt_index, src_label or source)
            attempts_map.setdefault(rel_key, []).append(attempt)

            parent = _ensure_suite_path(root, list(suite_parts))
            replaced_id = next((ex.id for ex in parent.tests if ex.name == test_name), None)
            if replaced_id is not None:
                used_ids.discard(replaced_id)
            new_id = _unique_test_id(t.id or "", used_ids)
            used_ids.add(new_id)

            rel_display = ".".join((*suite_parts, test_name))
            new_full = f"{merged_name}.{rel_display}" if rel_display else merged_name
            cloned = replace(
                t,
                id=new_id,
                full_name=new_full,
                name=test_name or t.name,
                attempts=list(attempts_map[rel_key]),
            )
            cloned = _rebind_test_keywords(cloned, t.id or "", new_id)
            _replace_or_append_test(parent, cloned)
            test_map[rel_key] = cloned

    for rel_key, test in test_map.items():
        # Final attempts list (same object already set, refresh for safety)
        test.attempts = list(attempts_map.get(rel_key, []))

    _recompute_suite_stats(root)

    all_t = _all_tests(root)
    passed = sum(1 for t in all_t if t.status == "PASS")
    failed = sum(1 for t in all_t if t.status == "FAIL")
    skipped = sum(1 for t in all_t if t.status == "SKIP")
    total = passed + failed + skipped
    pass_rate = int((passed / total * 100)) if total else 0

    errors: list[dict] = []
    for m in models:
        errors.extend(m.errors or [])

    duration = sum(m.duration for m in models)
    start_times = [m.start_time for m in models if m.start_time]
    start_time = min(start_times) if start_times else first.start_time

    return ReportModel(
        generated=models[-1].generated or first.generated,
        generator="ReportLens Merge",
        start_time=start_time,
        end_time=models[-1].end_time or "",
        duration=duration,
        statistics={
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "passRate": pass_rate,
        },
        errors=errors,
        root_suite=root,
    )


def merge_xml_files(
    xml_paths: list[str],
    *,
    min_log_level: int | None = None,
    merged_name: str = "MERGED",
) -> ReportModel:
    """Load and merge multiple output.xml files into one ReportModel."""
    if not xml_paths:
        raise ValueError("At least one XML path is required")
    level = min_log_level if min_log_level is not None else _LEVELS["TRACE"]
    models = [build_report_model(p, min_log_level=level) for p in xml_paths]
    return merge_models(models, sources=list(xml_paths), merged_name=merged_name)
