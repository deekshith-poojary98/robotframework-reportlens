"""
Serialize ReportModel to the template payload (dict).
No HTML. Produces the exact structure the report template expects.
"""

import re
from pathlib import Path
from typing import Any

from .model import Keyword, LogMessage, ReportModel, Suite, Test


def _error_file_path(text: str) -> str | None:
    """Extract file path from error text. Used for assigning errors to suites."""
    m = re.search(r"Error in file ['\"](.+?)['\"] on line", (text or "").strip())
    return m.group(1).strip() if m else None


def _assign_errors_to_suites_and_tests(suite: dict, errors: list[dict]) -> None:
    """Assign root-level errors to suites by source file. Mutates suite dict."""
    errors_with_path = []
    for e in errors:
        err = {"time": e.get("time", ""), "level": (e.get("level") or "WARN").upper(), "text": e.get("text", "")}
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
    return {
        "id": msg_id,
        "timestamp": msg.timestamp,
        "level": msg.level,
        "message": msg.message,
        "isReturn": msg.is_return,
    }


def _keyword_to_dict(kw: Keyword) -> dict:
    messages = [
        _log_message_to_dict(m, f"{kw.id}-msg-{i}") for i, m in enumerate(kw.messages)
    ]
    children = [_keyword_to_dict(c) for c in kw.keywords]
    out = {
        "id": kw.id,
        "name": kw.name,
        "type": kw.type,
        "status": kw.status,
        "duration": kw.duration,
        "startTime": kw.start_time or "",
        "endTime": kw.start_time or "",
        "arguments": kw.arguments,
        "documentation": kw.documentation,
        "messages": messages,
        "keywords": children,
        "failMessage": kw.fail_message,
        "returned": kw.returned,
        "returnValues": kw.return_values,
    }
    if getattr(kw, "badge", None):
        out["badge"] = kw.badge
    return out


def _test_to_dict(t: Test) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "fullName": t.full_name,
        "status": t.status,
        "tags": t.tags,
        "duration": t.duration,
        "message": t.message,
        "startTime": t.start_time or "",
        "endTime": t.start_time or "",
        "keywords": [_keyword_to_dict(k) for k in t.keywords],
        "documentation": t.documentation,
        "setup": _keyword_to_dict(t.setup) if t.setup else None,
        "teardown": _keyword_to_dict(t.teardown) if t.teardown else None,
    }


def _suite_to_dict(s: Suite) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "fullName": s.full_name,
        "status": s.status,
        "startTime": s.start_time or "",
        "endTime": s.start_time or "",
        "duration": s.duration,
        "statistics": s.statistics,
        "tests": [_test_to_dict(t) for t in s.tests],
        "suites": [_suite_to_dict(c) for c in s.suites],
        "source": s.source or "",
        "setup": _keyword_to_dict(s.setup) if s.setup else None,
        "teardown": _keyword_to_dict(s.teardown) if s.teardown else None,
    }


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
        "startTime": model.start_time,
        "endTime": model.end_time,
        "duration": model.duration,
        "statistics": model.statistics,
        "errors": model.errors,
        "rootSuite": root_suite,
    }
