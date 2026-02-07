"""
Build ReportModel from Robot Framework ExecutionResult.
No XML parsing, no HTML. Uses robot.api.ExecutionResult only.
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path

from robot.api import ExecutionResult

# Set BUILD_DEBUG=1 in env to print builder debug info (e.g. why test keywords may be empty).
BUILD_DEBUG = os.environ.get("BUILD_DEBUG", "").strip() in ("1", "true", "yes")


def _debug(*args, **kwargs):
    if BUILD_DEBUG:
        print("[builder]", *args, **kwargs, file=sys.stderr)

from .model import (
    Keyword,
    LogMessage,
    ReportModel,
    Suite,
    Test,
)

# Robot legacy timestamp format: "YYYYMMDD HH:MM:SS.fff" (e.g. "20260201 14:04:20.902")
_LEGACY_TS = re.compile(r"^(\d{4})(\d{2})(\d{2})\s+(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?$")
# ISO 8601 timezone suffix (Z or ±HH:MM) so we don't double-append
_ISO_TZ = re.compile(r"(Z|[+-]\d{2}:\d{2})$")


def _local_tz():
    """Timezone of the machine where the report is built (same as Robot run). Naive timestamps are treated as this."""
    return datetime.now().astimezone().tzinfo


def _ensure_iso_tz(s: str) -> str:
    """Ensure ISO string has timezone (Z or ±HH:MM). Appends Z if missing so JS Date.parse is reliable."""
    if not s or not s.strip():
        return s
    s = s.strip()
    if _ISO_TZ.search(s):
        return s
    return s.rstrip("Z") + "Z"


def _naive_to_iso(dt: datetime) -> str:
    """Convert datetime to ISO string with timezone. Naive datetimes are treated as local time (Robot run timezone)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_local_tz())
    return dt.isoformat()


def _to_iso_time(ts) -> str:
    """
    Normalize a timestamp to ISO 8601 with timezone for the report/JS.
    Handles datetime, ISO strings, legacy Robot "YYYYMMDD HH:MM:SS.fff", or None.
    Naive values (no timezone) are treated as local time (where Robot ran); output has offset e.g. +05:30.
    Always returns a string ending with Z or ±HH:MM, or empty string if missing/invalid.
    """
    if ts is None or (isinstance(ts, str) and not ts.strip()):
        return ""
    if hasattr(ts, "isoformat"):
        return _naive_to_iso(ts)
    s = str(ts).strip()
    if not s:
        return ""
    if "T" in s:
        try:
            parsed = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return _naive_to_iso(parsed)
        except ValueError:
            pass
    m = _LEGACY_TS.match(s)
    if m:
        y, mo, d, h, mi, sec = (int(m.group(i)) for i in range(1, 7))
        frac = m.group(7)
        if frac:
            frac = frac.ljust(6, "0")[:6]
            micro = int(frac)
        else:
            micro = 0
        try:
            dt = datetime(y, mo, d, h, mi, sec, micro)
            return _naive_to_iso(dt)
        except ValueError:
            return ""
    try:
        parsed = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return _naive_to_iso(parsed)
    except ValueError:
        return ""


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
    """Get start time as ISO 8601 with timezone from a Robot result item."""
    st = getattr(robot_item, "starttime", None)
    if st:
        return _to_iso_time(st)
    start = getattr(robot_item, "start_time", None)
    if start is not None:
        return _to_iso_time(start)
    return ""


def _get_body(robot_item):
    """Get iterable body from a Robot body item (test, keyword, For, If, etc.). Handles result model variants."""
    body = getattr(robot_item, "body", None)
    if body is not None:
        return body
    # Some result model variants use 'iterations' for For/While
    out = getattr(robot_item, "iterations", None)
    if BUILD_DEBUG and out is not None:
        _debug("_get_body: got iterations for", type(robot_item).__name__)
    return out


def _control_display_name(robot_item) -> str:
    """Human-readable name for a control structure (For, ForIteration, If, Try, etc.). Avoids repr()."""
    name = getattr(robot_item, "_log_name", None)
    if name is not None and isinstance(name, str) and name.strip():
        return name.strip()
    # Do not read .assign on If/IfBranch/Try/WhileIteration/ForIteration: deprecated in Robot Framework 8.0
    type_name = type(robot_item).__name__
    if type_name not in ("If", "IfBranch", "Try", "WhileIteration", "ForIteration"):
        assign = getattr(robot_item, "assign", None)
        if assign is not None:
            try:
                items = list(assign.items()) if hasattr(assign, "items") else []
                if items:
                    return ", ".join(f"{k} = {v}" for k, v in items)
            except Exception:
                pass
    s = str(robot_item).strip()
    if s.startswith("robot.") and "(" in s:
        return ""  # Avoid dumping repr; caller will use a fallback
    return s


def _is_executable_body_item(robot_item) -> bool:
    """True if item is a step that can have nested execution (Keyword or control structure)."""
    if robot_item is None:
        return False
    if type(robot_item).__name__ == "Keyword":
        return True
    return _get_body(robot_item) is not None


def _build_keyword(robot_kw, test_id: str, kw_index) -> Keyword:
    """Build a Keyword from Robot's keyword or control structure. Recurses into body for all nested steps."""
    type_name = type(robot_kw).__name__
    body = _get_body(robot_kw)
    if body is None:
        body = getattr(robot_kw, "body", None)

    # Control structure (FOR / IF / WHILE / TRY or branch/iteration): one Keyword node, children from body
    if type_name != "Keyword" and body is not None:
        body_list = list(body) if body is not None else []
        _debug(f"_build_keyword control type={type_name!r} test_id={test_id!r} body_list len={len(body_list)}")
        kw_id = f"kw-{test_id}-{kw_index}"
        name = _control_display_name(robot_kw)
        if not name:
            name = str(robot_kw).strip()
        # Never show Python repr in the report (e.g. robot.result.If())
        if name and ("robot." in name or (name.startswith("robot.") and "(" in name)):
            name = ""
        if not name:
            # Friendly labels for root control structures that have no _log_name
            _root_labels = {"For": "FOR", "While": "WHILE", "If": "IF / ELSE", "Try": "TRY / EXCEPT"}
            name = _root_labels.get(type_name, type_name)
        # ForIteration / WhileIteration: show "Iteration 1", "Iteration 2", ... instead of class name
        if type_name in ("ForIteration", "WhileIteration"):
            parts = kw_index.split("-")
            if len(parts) >= 2 and parts[-1].isdigit():
                name = f"Iteration {int(parts[-1]) + 1}"
            else:
                name = "Iteration"
        # Prepend control type so the header shows "FOR ...", "WHILE ...", "IF ...", "TRY ..."
        if type_name == "For" and not name.upper().startswith("FOR"):
            name = "FOR " + name
        elif type_name == "While" and not name.upper().startswith("WHILE"):
            name = "WHILE " + name
        elif type_name == "If" and name and not name.upper().startswith(("IF", "ELSE")):
            name = "IF " + name
        elif type_name == "Try" and name and not name.upper().startswith(("TRY", "EXCEPT", "ELSE", "FINALLY")):
            name = "TRY " + name
        elif type_name == "IfBranch":
            branch_type = (getattr(robot_kw, "type", None) or "").upper()
            if branch_type in ("IF", "ELSE IF", "ELSE"):
                if branch_type == "IF" and name and not name.upper().startswith("IF"):
                    name = "IF " + name
                elif branch_type == "ELSE IF" and name and not name.upper().startswith("ELSE"):
                    name = "ELSE IF " + name
                elif branch_type == "ELSE" and (not name or name.upper().strip() != "ELSE"):
                    name = "ELSE"
        elif type_name == "TryBranch":
            branch_type = (getattr(robot_kw, "type", None) or "").upper()
            if branch_type and name and not name.upper().startswith(("TRY", "EXCEPT", "ELSE", "FINALLY")):
                name = branch_type + " " + name
        # Reserve a badge for control words and use the rest as display name
        badge = None
        name_rest = name
        u = (name or "").upper()
        if type_name == "For" and u.startswith("FOR"):
            badge = "FOR"
            name_rest = name[4:].lstrip()
        elif type_name == "While" and u.startswith("WHILE"):
            badge = "WHILE"
            name_rest = name[6:].lstrip()
        # No badge for root If / Try parents (e.g. "IF / ELSE", "TRY / EXCEPT")
        elif type_name == "IfBranch":
            branch_type = (getattr(robot_kw, "type", None) or "").upper()
            if branch_type == "IF" and u.startswith("IF "):
                badge = "IF"
                name_rest = name[3:].lstrip()
            elif branch_type == "ELSE IF" and u.startswith("ELSE IF "):
                badge = "ELSE IF"
                name_rest = name[8:].lstrip()
            elif branch_type == "ELSE":
                badge = "ELSE"
                name_rest = ""
        elif type_name == "TryBranch":
            branch_type = (getattr(robot_kw, "type", None) or "").upper()
            if branch_type:
                badge = branch_type
                prefix = branch_type + " "
                if u.startswith(prefix):
                    name_rest = name[len(prefix) :].lstrip()
                elif u == branch_type:
                    name_rest = ""
        raw_type = getattr(robot_kw, "type", None)
        kw_type = (raw_type.upper() if isinstance(raw_type, str) else "KEYWORD") or "KEYWORD"
        if kw_type not in ("SETUP", "TEARDOWN", "KEYWORD"):
            kw_type = "KEYWORD"
        status = getattr(robot_kw, "status", "PASS") or "PASS"
        duration_ms = _elapsed_ms(robot_kw)
        start_time = _start_time(robot_kw)
        fail_message = (getattr(robot_kw, "message", None) or "").strip()
        child_keywords = []
        for i, item in enumerate(body_list):
            if _is_executable_body_item(item):
                child_keywords.append(_build_keyword(item, test_id, f"{kw_index}-{i}"))
        _debug(f"  control badge={badge!r} name={name_rest!r} child_keywords len={len(child_keywords)}")
        return Keyword(
            id=kw_id,
            name=name_rest,
            type=kw_type,
            status=status,
            duration=duration_ms,
            start_time=start_time,
            arguments=[],
            documentation="",
            messages=[],
            keywords=child_keywords,
            fail_message=fail_message,
            returned=False,
            return_values=[],
            badge=badge,
        )

    # Keyword: full extraction and recurse into body for keywords and control structures
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

    returned = False
    return_values = []
    messages_list = []
    seen_return = False
    child_keywords = []
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
                ts = _to_iso_time(getattr(msg, "timestamp", None) or "")
                messages_list.append(
                    LogMessage(timestamp=ts, level=level, message=text, is_return=seen_return)
                )
            elif _is_executable_body_item(item):
                child_keywords.append(_build_keyword(item, test_id, f"{kw_index}-{child_kw_index}"))
                child_kw_index += 1

    # If no body iteration (e.g. body empty), use keyword.messages
    if not messages_list and hasattr(robot_kw, "messages") and robot_kw.messages:
        for msg in robot_kw.messages:
            level = (getattr(msg, "level", "INFO") or "INFO").upper()
            text = (getattr(msg, "message", None) or "").strip()
            ts = _to_iso_time(getattr(msg, "timestamp", None) or "")
            messages_list.append(LogMessage(timestamp=ts, level=level, message=text, is_return=False))

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
        badge=None,
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
    body = _get_body(robot_test) or getattr(robot_test, "body", None)
    _debug(f"_build_test id={test_id!r} name={name!r} body={type(body).__name__ if body is not None else None!r}")
    if body is not None:
        body_items = list(body)
        _debug(f"  body_items len={len(body_items)}")
        # Some result/model variants expose steps only via flatten() (e.g. IF/TRY roots replaced by branches)
        if not body_items and hasattr(body, "flatten"):
            body_items = list(body.flatten())
            _debug(f"  after flatten body_items len={len(body_items)}")
        kw_index = 0
        for i, item in enumerate(body_items):
            item_type = type(item).__name__
            is_exec = _is_executable_body_item(item)
            _debug(f"  body[{i}] type={item_type} executable={is_exec}")
            if is_exec:
                keywords.append(_build_keyword(item, test_id, kw_index))
                kw_index += 1
        _debug(f"  -> keywords len={len(keywords)}")

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
            ts = _to_iso_time(getattr(msg, "timestamp", None) or "")
            text = getattr(msg, "message", None) or getattr(msg, "text", "") or ""
            errors.append({"time": ts, "level": level, "text": str(text).strip()})

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
    # Generated / generator from result (generation_time is set from <robot generated="..."> when loading XML)
    gen = getattr(result, "generator", "Robot Framework") or "Robot Framework"
    gen_time = getattr(result, "generation_time", None) or getattr(result, "generated", None)
    gen_str = _to_iso_time(gen_time) if gen_time else ""
    # Report start: root suite start_time, then generation_time, then suite status start, then earliest test
    start_time = _report_start_time(result, root)
    if not start_time and root_suite.start_time:
        start_time = _to_iso_time(root_suite.start_time)
    if not start_time:
        start_time = gen_str
    end_time = start_time
    duration_ms = root_suite.duration

    if BUILD_DEBUG:
        for t in _all_tests(root_suite):
            nk = len(t.keywords)
            if nk == 0:
                _debug(f"SUMMARY: test id={t.id!r} name={t.name!r} has 0 keywords")

    return ReportModel(
        generated=gen_str,
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


def _all_robot_tests(robot_suite):
    """Yield all Robot test case objects from a Robot suite tree."""
    for t in getattr(robot_suite, "tests", []) or []:
        yield t
    for s in getattr(robot_suite, "suites", []) or []:
        yield from _all_robot_tests(s)


def _report_start_time(result, robot_root) -> str:
    """
    Best available report start time as ISO string.
    Order: root suite start_time, result generation_time, root suite status start, earliest test start.
    """
    candidates = []
    if robot_root:
        st = _start_time(robot_root)
        if st:
            candidates.append(st)
    gen = getattr(result, "generation_time", None) or getattr(result, "generated", None)
    if gen is not None and gen != "":
        candidates.append(gen.isoformat() if hasattr(gen, "isoformat") else str(gen))
    if not candidates and robot_root:
        status = getattr(robot_root, "status", None)
        if status is not None:
            st = _start_time(status)
            if st:
                candidates.append(st)
    if not candidates and robot_root:
        for robot_test in _all_robot_tests(robot_root):
            st = _start_time(robot_test)
            if st:
                candidates.append(st)
    if not candidates:
        return ""
    return _to_iso_time(candidates[0])
