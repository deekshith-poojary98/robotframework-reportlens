"""
Internal report model. Pure data structures for Robot Framework execution results.
No HTML or UI logic. IDs are deterministic and stable (from Robot output.xml).
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LogMessage:
    """A single log message (e.g. from a keyword or return)."""
    timestamp: str
    level: str
    message: str
    is_return: bool = False


@dataclass
class Keyword:
    """An executed keyword (setup, teardown, or test step)."""
    id: str
    name: str
    type: str  # SETUP, TEARDOWN, KEYWORD
    status: str
    duration: int  # milliseconds
    start_time: str
    arguments: list[str]
    documentation: str
    messages: list[LogMessage]
    keywords: list["Keyword"]
    fail_message: str
    returned: bool
    return_values: list[str]
    badge: str | None = None  # Reserved control word shown as badge: FOR, IF, ELSE IF, ELSE, TRY, EXCEPT, FINALLY, WHILE


@dataclass
class Test:
    """A single test case."""
    id: str
    name: str
    full_name: str
    status: str
    tags: list[str]
    duration: int  # milliseconds
    message: str
    start_time: str
    documentation: str
    keywords: list[Keyword]
    setup: "Keyword | None" = None
    teardown: "Keyword | None" = None


@dataclass
class Suite:
    """A test suite (root or nested)."""
    id: str
    name: str
    full_name: str
    status: str
    start_time: str
    duration: int  # milliseconds
    source: str
    tests: list[Test]
    suites: list["Suite"]
    statistics: dict[str, Any]  # total, passed, failed, skipped
    setup: "Keyword | None" = None
    teardown: "Keyword | None" = None


@dataclass
class ReportModel:
    """Root model for a Robot Framework execution result."""
    generated: str
    generator: str
    start_time: str
    end_time: str
    duration: int  # milliseconds
    statistics: dict[str, Any]  # total, passed, failed, skipped, passRate
    errors: list[dict[str, Any]]  # time, level, text
    root_suite: Suite
