"""
Build ReportModel from Robot Framework ExecutionResult.
No XML parsing, no HTML. Uses robot.api.ExecutionResult only.
"""

from pathlib import Path

from robot.api import ExecutionResult

from .model import (
    Keyword,
    LogMessage,
    ReportModel,
    Suite,
    Test,
)


def _elapsed_ms(robot_item) -> int:
    """Get elapsed time in milliseconds from a Robot result item."""
    et = getattr(robot_item, "elapsedtime", None)
    if et is not None:
        return int(et)
    elapsed = getattr(robot_item, "elapsed_time", None)
    if elapsed is not None:
        return int(elapsed.total_seconds() * 1000)
    return 0


def _start_time(robot_item) -> str:
    """Get start time string from a Robot result item."""
    st = getattr(robot_item, "starttime", None)
    if st:
        return st
    start = getattr(robot_item, "start_time", None)
    if start is not None:
        return str(start) if not hasattr(start, "isoformat") else start.isoformat()
    return ""


def _build_keyword(robot_kw, test_id: str, kw_index) -> Keyword:
    """Build a Keyword from Robot's keyword result. kw_index can be int or str path like '0-1'."""
    kw_id = f"kw-{test_id}-{kw_index}"
    name = getattr(robot_kw, "name", "") or ""
    kw_type = (getattr(robot_kw, "type", "KEYWORD") or "KEYWORD").upper()
    if kw_type not in ("SETUP", "TEARDOWN", "KEYWORD"):
        kw_type = "KEYWORD"
    status = getattr(robot_kw, "status", "PASS") or "PASS"
    duration_ms = _elapsed_ms(robot_kw)
    start_time = _start_time(robot_kw)
    fail_message = (getattr(robot_kw, "message", None) or "").strip()
    args = list(getattr(robot_kw, "args", []) or [])
    doc = (getattr(robot_kw, "doc", None) or "").strip()

    # Return: check body for Return and collect return values
    returned = False
    return_values = []
    messages_list = []
    seen_return = False
    child_keywords = []
    body = getattr(robot_kw, "body", None)
    if body is not None:
        child_kw_index = 0
        for item in body:
            type_name = type(item).__name__
            if type_name == "Return":
                seen_return = True
                return_values = [str(v).strip() for v in getattr(item, "values", []) or []]
                returned = True
            elif type_name == "Message":
                msg = item
                level = (getattr(msg, "level", "INFO") or "INFO").upper()
                text = (getattr(msg, "message", None) or "").strip()
                ts = getattr(msg, "timestamp", None) or ""
                if ts is not None and hasattr(ts, "isoformat"):
                    ts = ts.isoformat()
                messages_list.append(
                    LogMessage(timestamp=str(ts), level=level, message=text, is_return=seen_return)
                )
            elif type_name == "Keyword":
                child_keywords.append(_build_keyword(item, test_id, f"{kw_index}-{child_kw_index}"))
                child_kw_index += 1

    # If no body iteration (e.g. body empty), use keyword.messages
    if not messages_list and hasattr(robot_kw, "messages") and robot_kw.messages:
        for msg in robot_kw.messages:
            level = (getattr(msg, "level", "INFO") or "INFO").upper()
            text = (getattr(msg, "message", None) or "").strip()
            ts = getattr(msg, "timestamp", None) or ""
            if ts is not None and hasattr(ts, "isoformat"):
                ts = ts.isoformat()
            messages_list.append(LogMessage(timestamp=str(ts), level=level, message=text, is_return=False))

    return Keyword(
        id=kw_id,
        name=name,
        type=kw_type,
        status=status,
        duration=duration_ms,
        start_time=start_time,
        arguments=args,
        documentation=doc,
        messages=messages_list,
        keywords=child_keywords,
        fail_message=fail_message,
        returned=returned,
        return_values=return_values,
    )


def _build_test(robot_test, suite_full_name: str) -> Test:
    """Build a Test from Robot's test case result."""
    test_id = getattr(robot_test, "id", "") or ""
    name = getattr(robot_test, "name", "Test") or "Test"
    full_name = f"{suite_full_name}.{name}" if suite_full_name else name
    status = getattr(robot_test, "status", "PASS") or "PASS"
    raw_tags = getattr(robot_test, "tags", []) or []
    tags = [getattr(t, "name", str(t)) for t in raw_tags]
    duration_ms = _elapsed_ms(robot_test)
    message = (getattr(robot_test, "message", None) or "").strip()
    start_time = _start_time(robot_test)
    doc = (getattr(robot_test, "doc", None) or "").strip()

    keywords = []
    body = getattr(robot_test, "body", None)
    if body is not None:
        kw_index = 0
        for item in body:
            if type(item).__name__ == "Keyword":
                keywords.append(_build_keyword(item, test_id, kw_index))
                kw_index += 1

    robot_setup = getattr(robot_test, "setup", None)
    robot_teardown = getattr(robot_test, "teardown", None)
    test_setup = _build_keyword(robot_setup, test_id, "setup") if robot_setup else None
    test_teardown = _build_keyword(robot_teardown, test_id, "teardown") if robot_teardown else None

    return Test(
        id=test_id,
        name=name,
        full_name=full_name,
        status=status,
        tags=tags,
        duration=duration_ms,
        message=message,
        start_time=start_time,
        documentation=doc,
        keywords=keywords,
        setup=test_setup,
        teardown=test_teardown,
    )


def _build_suite(robot_suite, parent_full_name: str) -> Suite:
    """Build a Suite from Robot's test suite result."""
    suite_id = getattr(robot_suite, "id", "") or ""
    name = getattr(robot_suite, "name", "Suite") or "Suite"
    full_name = f"{parent_full_name}.{name}" if parent_full_name else name
    status = getattr(robot_suite, "status", "PASS") or "PASS"
    start_time = _start_time(robot_suite)
    duration_ms = _elapsed_ms(robot_suite)
    source = str(getattr(robot_suite, "source", "") or "")

    tests = []
    for robot_test in getattr(robot_suite, "tests", []) or []:
        tests.append(_build_test(robot_test, full_name))

    suites = []
    for child in getattr(robot_suite, "suites", []) or []:
        suites.append(_build_suite(child, full_name))

    passed = sum(1 for t in tests if t.status == "PASS")
    failed = sum(1 for t in tests if t.status == "FAIL")
    skipped = sum(1 for t in tests if t.status == "SKIP")
    statistics = {"total": len(tests), "passed": passed, "failed": failed, "skipped": skipped}

    robot_setup = getattr(robot_suite, "setup", None)
    robot_teardown = getattr(robot_suite, "teardown", None)
    suite_setup = _build_keyword(robot_setup, f"suite-{suite_id}", "setup") if robot_setup else None
    suite_teardown = _build_keyword(robot_teardown, f"suite-{suite_id}", "teardown") if robot_teardown else None

    return Suite(
        id=suite_id,
        name=name,
        full_name=full_name,
        status=status,
        start_time=start_time,
        duration=duration_ms,
        source=source,
        tests=tests,
        suites=suites,
        statistics=statistics,
        setup=suite_setup,
        teardown=suite_teardown,
    )


def build_report_model(xml_path: str) -> ReportModel:
    """
    Load output.xml via Robot's ExecutionResult and build our ReportModel.
    No manual XML, no HTML. IDs are deterministic (from Robot).
    """
    result = ExecutionResult(xml_path)
    root = result.suite
    if root is None:
        project_name = (Path(xml_path).resolve().parent.name or "Test Run").upper()
        root_suite = Suite(
            id="s0",
            name=project_name,
            full_name=project_name,
            status="PASS",
            start_time="",
            duration=0,
            source="",
            tests=[],
            suites=[],
            statistics={"total": 0, "passed": 0, "failed": 0, "skipped": 0},
            setup=None,
            teardown=None,
        )
    else:
        root_suite = _build_suite(root, "")
        project_name = (Path(xml_path).resolve().parent.name or "Test Run").upper()
        root_suite.name = project_name
        root_suite.full_name = project_name

    # Errors (ExecutionErrors has .messages)
    errors = []
    errs = getattr(result, "errors", None)
    if errs is not None:
        messages = getattr(errs, "messages", errs) if hasattr(errs, "messages") else errs
        for msg in (messages or []):
            level = (getattr(msg, "level", "WARN") or "WARN").upper()
            ts = getattr(msg, "timestamp", None) or ""
            if ts is not None and hasattr(ts, "isoformat"):
                ts = ts.isoformat()
            text = getattr(msg, "message", None) or getattr(msg, "text", "") or ""
            errors.append({"time": str(ts), "level": level, "text": str(text).strip()})

    # Statistics
    stats = result.statistics
    total_stats = getattr(stats, "total", None)
    if total_stats is not None:
        passed = getattr(total_stats, "passed", 0) or 0
        failed = getattr(total_stats, "fail", None) or getattr(total_stats, "failed", 0) or 0
        skipped = getattr(total_stats, "skip", None) or getattr(total_stats, "skipped", 0) or 0
    else:
        passed = sum(1 for t in _all_tests(root_suite) if t.status == "PASS")
        failed = sum(1 for t in _all_tests(root_suite) if t.status == "FAIL")
        skipped = sum(1 for t in _all_tests(root_suite) if t.status == "SKIP")
    total = passed + failed + skipped
    pass_rate = int((passed / total * 100)) if total > 0 else 0

    # Generated / generator from result
    gen = getattr(result, "generator", "Robot Framework") or "Robot Framework"
    gen_time = getattr(result, "generation_time", None) or ""
    if gen_time is not None and hasattr(gen_time, "isoformat"):
        gen_time = gen_time.isoformat()
    start_time = root_suite.start_time or str(gen_time)
    end_time = start_time
    duration_ms = root_suite.duration

    return ReportModel(
        generated=str(gen_time),
        generator=str(gen),
        start_time=start_time,
        end_time=end_time,
        duration=duration_ms,
        statistics={
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "passRate": pass_rate,
        },
        errors=errors,
        root_suite=root_suite,
    )


def _all_tests(suite: Suite) -> list:
    """Flatten all tests from suite tree."""
    out = list(suite.tests)
    for s in suite.suites:
        out.extend(_all_tests(s))
    return out
