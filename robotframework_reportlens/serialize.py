"""
Serialize ReportModel to the template payload (dict).
No HTML. Produces the exact structure the report template expects.
"""

import re
from pathlib import Path
from typing import Any

from .model import Keyword, LogMessage, ReportModel, Suite, Test


# Helper: decide whether to include a value in output
def _include_value(v):
    """Return True if value v should be included in JSON output.

    Exclude empty lists, empty strings, None, and False booleans (conservative).
    """
    if v is None:
        return False
    if isinstance(v, bool):
        # Only include True booleans (False is default/omitted)
        return v is True
    if isinstance(v, (list, tuple)):
        return len(v) > 0
    if isinstance(v, str):
        return bool(v)
    # Numbers, dicts, and other truthy values are included
    return True


def _error_file_path(text: str) -> str | None:
    """Extract file path from error text. Used for assigning errors to suites."""
    m = re.search(r"Error in file ['\"](.+?)['\"] on line", (text or "").strip())
    return m.group(1).strip() if m else None


def _assign_errors_to_suites_and_tests(suite: dict, errors: list[dict]) -> None:
    """Assign root-level errors to suites by source file. Mutates suite dict."""
    errors_with_path = []
    for e in errors:
        err = {
            "time": e.get("time", ""),
            "level": (e.get("level") or "WARN").upper(),
            "text": e.get("text", ""),
        }
        path = _error_file_path(e.get("text", ""))
        if path:
            errors_with_path.append((path, err))

    def walk(s: dict) -> None:
        source = (s.get("source") or "").strip()
        source_norm = str(Path(source).resolve()) if source else None
        suite_errors = []
        if source_norm:
            for path, err in errors_with_path:
                try:
                    path_norm = str(Path(path).resolve())
                except Exception:
                    path_norm = path
                if path_norm == source_norm:
                    suite_errors.append(err)
        s["errors"] = suite_errors
        for t in s.get("tests", []):
            t["suiteErrors"] = suite_errors
        for child in s.get("suites", []):
            walk(child)

    walk(suite)


def _log_message_to_dict(msg: LogMessage, msg_id: str) -> dict:
    out: dict = {"id": msg_id}
    if _include_value(msg.timestamp):
        out["timestamp"] = msg.timestamp
    if _include_value(msg.level):
        out["level"] = msg.level
    if _include_value(msg.message):
        out["message"] = msg.message
    # Booleans: only include if True
    if _include_value(msg.is_return):
        out["isReturn"] = True
    if _include_value(msg.html):
        out["isHtml"] = True
    return out


def _keyword_to_dict(kw: Keyword) -> dict:
    messages = [
        _log_message_to_dict(m, f"{kw.id}-msg-{i}") for i, m in enumerate(kw.messages)
    ]
    children = [_keyword_to_dict(c) for c in kw.keywords]
    out: dict = {"id": kw.id}
    if _include_value(kw.name):
        out["name"] = kw.name
    if _include_value(kw.type):
        out["type"] = kw.type
    if _include_value(kw.status):
        out["status"] = kw.status
    if _include_value(kw.duration):
        out["duration"] = kw.duration
    if _include_value(kw.start_time):
        out["startTime"] = kw.start_time
    # endTime: only include if present and different from start_time
    if _include_value(getattr(kw, "end_time", None)):
        endt = getattr(kw, "end_time")
        if endt and endt != kw.start_time:
            out["endTime"] = endt
    if _include_value(kw.arguments):
        out["arguments"] = kw.arguments
    if _include_value(kw.documentation):
        out["documentation"] = kw.documentation
    if _include_value(messages):
        out["messages"] = messages
    if _include_value(children):
        out["keywords"] = children
    if _include_value(kw.fail_message):
        out["failMessage"] = kw.fail_message
    if _include_value(kw.returned):
        out["returned"] = True
    if _include_value(kw.return_values):
        out["returnValues"] = kw.return_values
    if getattr(kw, "badge", None):
        out["badge"] = kw.badge
    return out


def _keyword_to_dict_without_messages(kw: Keyword) -> dict:
    children = [_keyword_to_dict_without_messages(c) for c in kw.keywords]
    out: dict = {"id": kw.id}
    if _include_value(kw.name):
        out["name"] = kw.name
    if _include_value(kw.type):
        out["type"] = kw.type
    if _include_value(kw.status):
        out["status"] = kw.status
    if _include_value(kw.duration):
        out["duration"] = kw.duration
    if _include_value(kw.start_time):
        out["startTime"] = kw.start_time
    if _include_value(getattr(kw, "end_time", None)):
        endt = getattr(kw, "end_time")
        if endt and endt != kw.start_time:
            out["endTime"] = endt
    if _include_value(kw.arguments):
        out["arguments"] = kw.arguments
    if _include_value(kw.documentation):
        out["documentation"] = kw.documentation
    if _include_value(children):
        out["keywords"] = children
    if _include_value(kw.fail_message):
        out["failMessage"] = kw.fail_message
    if _include_value(kw.returned):
        out["returned"] = True
    if _include_value(kw.return_values):
        out["returnValues"] = kw.return_values
    if getattr(kw, "badge", None):
        out["badge"] = kw.badge
    return out


def _collect_keyword_messages(kw: Keyword, out: dict[str, list[dict]]) -> None:
    if kw.messages:
        out[kw.id] = [
            _log_message_to_dict(m, f"{kw.id}-msg-{i}")
            for i, m in enumerate(kw.messages)
        ]
    for child in kw.keywords:
        _collect_keyword_messages(child, out)


def _test_to_dict(t: Test) -> dict:
    out: dict = {"id": t.id}
    if _include_value(t.name):
        out["name"] = t.name
    if _include_value(t.full_name):
        out["fullName"] = t.full_name
    if _include_value(t.status):
        out["status"] = t.status
    if _include_value(t.tags):
        out["tags"] = t.tags
    if _include_value(t.duration):
        out["duration"] = t.duration
    if _include_value(t.message):
        out["message"] = t.message
    if _include_value(t.start_time):
        out["startTime"] = t.start_time
    if _include_value(getattr(t, "end_time", None)):
        endt = getattr(t, "end_time")
        if endt and endt != t.start_time:
            out["endTime"] = endt
    kws = [_keyword_to_dict(k) for k in t.keywords]
    if _include_value(kws):
        out["keywords"] = kws
    if _include_value(t.documentation):
        out["documentation"] = t.documentation
    if t.setup:
        out_setup = _keyword_to_dict(t.setup)
        if _include_value(out_setup):
            out["setup"] = out_setup
    if t.teardown:
        out_teardown = _keyword_to_dict(t.teardown)
        if _include_value(out_teardown):
            out["teardown"] = out_teardown
    return out


def _test_to_dict_without_messages(t: Test) -> dict:
    out: dict = {"id": t.id}
    if _include_value(t.name):
        out["name"] = t.name
    if _include_value(t.full_name):
        out["fullName"] = t.full_name
    if _include_value(t.status):
        out["status"] = t.status
    if _include_value(t.tags):
        out["tags"] = t.tags
    if _include_value(t.duration):
        out["duration"] = t.duration
    if _include_value(t.message):
        out["message"] = t.message
    if _include_value(t.start_time):
        out["startTime"] = t.start_time
    if _include_value(getattr(t, "end_time", None)):
        endt = getattr(t, "end_time")
        if endt and endt != t.start_time:
            out["endTime"] = endt
    kws = [_keyword_to_dict_without_messages(k) for k in t.keywords]
    if _include_value(kws):
        out["keywords"] = kws
    if _include_value(t.documentation):
        out["documentation"] = t.documentation
    if t.setup:
        out_setup = _keyword_to_dict_without_messages(t.setup)
        if _include_value(out_setup):
            out["setup"] = out_setup
    if t.teardown:
        out_teardown = _keyword_to_dict_without_messages(t.teardown)
        if _include_value(out_teardown):
            out["teardown"] = out_teardown
    return out


def _suite_to_dict(s: Suite) -> dict:
    out: dict = {"id": s.id}
    if _include_value(s.name):
        out["name"] = s.name
    if _include_value(s.full_name):
        out["fullName"] = s.full_name
    if _include_value(s.status):
        out["status"] = s.status
    if _include_value(s.start_time):
        out["startTime"] = s.start_time
    if _include_value(getattr(s, "end_time", None)):
        endt = getattr(s, "end_time")
        if endt and endt != s.start_time:
            out["endTime"] = endt
    if _include_value(s.duration):
        out["duration"] = s.duration
    if _include_value(s.statistics):
        out["statistics"] = s.statistics
    tests = [_test_to_dict(t) for t in s.tests]
    if _include_value(tests):
        out["tests"] = tests
    suites = [_suite_to_dict(c) for c in s.suites]
    if _include_value(suites):
        out["suites"] = suites
    if _include_value(s.source):
        out["source"] = s.source
    if s.setup:
        out_setup = _keyword_to_dict(s.setup)
        if _include_value(out_setup):
            out["setup"] = out_setup
    if s.teardown:
        out_teardown = _keyword_to_dict(s.teardown)
        if _include_value(out_teardown):
            out["teardown"] = out_teardown
    return out


def model_to_payload(model: ReportModel) -> dict[str, Any]:
    """
    Convert ReportModel to the template payload (dict).
    Assigns errors to suites. Returns the exact structure expected by the report template.
    """
    root_suite = _suite_to_dict(model.root_suite)
    _assign_errors_to_suites_and_tests(root_suite, model.errors)
    return {
        "generated": model.generated,
        "generator": model.generator,
        # Only include top-level values when present
        **({"startTime": model.start_time} if _include_value(model.start_time) else {}),
        **({"endTime": model.end_time} if _include_value(model.end_time) else {}),
        **({"duration": model.duration} if _include_value(model.duration) else {}),
        **(
            {"statistics": model.statistics} if _include_value(model.statistics) else {}
        ),
        **({"errors": model.errors} if _include_value(model.errors) else {}),
        "rootSuite": root_suite,
    }
