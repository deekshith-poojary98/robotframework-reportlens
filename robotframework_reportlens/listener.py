"""
Live report listener for Robot Framework.

Streams incremental JSON while a suite runs so an HTML shell can poll/refresh.
Use with::

    robot --listener robotframework_reportlens.listener.LiveReportListener:outdir=live-report

Or via CLI helper::

    reportlens live --outdir live-report
    # then: robot --listener ... (printed by the command)

The listener writes:
  <outdir>/live.html          — polling HTML shell
  <outdir>/live-data/status.json
  <outdir>/live-data/summary.json
  <outdir>/live-data/tests.json  — list of completed tests (updated each test)

Robust to mid-run exit: status.json gets finished=false until close();
close() always flushes a final snapshot even if Robot aborts suites.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROBOT_LISTENER_API_VERSION = 3

_LIVE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ReportLens Live</title>
  <style>
    :root { --bg:#0f1419; --fg:#e7ecf1; --muted:#8b98a5; --pass:#3dd68c; --fail:#f07178; --skip:#ffcc66; --card:#1a2332; --border:#2a3544; }
    * { box-sizing: border-box; }
    body { margin:0; font-family: ui-sans-serif, system-ui, sans-serif; background:var(--bg); color:var(--fg); }
    header { padding:16px 20px; border-bottom:1px solid var(--border); display:flex; gap:16px; align-items:center; flex-wrap:wrap; }
    h1 { margin:0; font-size:18px; font-weight:600; }
    .badge { font-size:12px; padding:4px 8px; border-radius:4px; background:var(--card); border:1px solid var(--border); }
    .badge.running { border-color:var(--skip); color:var(--skip); }
    .badge.done { border-color:var(--pass); color:var(--pass); }
    .stats { display:flex; gap:12px; font-size:13px; color:var(--muted); }
    .stats b { color:var(--fg); }
    .pass { color:var(--pass); } .fail { color:var(--fail); } .skip { color:var(--skip); }
    main { padding:16px 20px; max-width:960px; }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th, td { text-align:left; padding:8px 10px; border-bottom:1px solid var(--border); }
    th { color:var(--muted); font-weight:500; }
    .err { color:var(--fail); margin:12px 0; }
    .hint { color:var(--muted); font-size:12px; margin-top:12px; }
  </style>
</head>
<body>
  <header>
    <h1>ReportLens Live</h1>
    <span class="badge" id="status-badge">Connecting…</span>
    <div class="stats" id="stats"></div>
  </header>
  <main>
    <div id="error" class="err" hidden></div>
    <table>
      <thead><tr><th>Status</th><th>Test</th><th>Duration</th><th>Message</th></tr></thead>
      <tbody id="rows"></tbody>
    </table>
    <p class="hint">Polling <code>live-data/status.json</code> every 1s. Serve this folder over HTTP if needed:
      <code>python -m http.server</code></p>
  </main>
  <script>
    const fmt = ms => {
      ms = Number(ms)||0;
      if (ms < 1000) return ms + "ms";
      if (ms < 60000) return (ms/1000).toFixed(1) + "s";
      return Math.floor(ms/60000) + "m " + Math.round((ms%60000)/1000) + "s";
    };
    async function tick() {
      try {
        const st = await fetch("live-data/status.json?t=" + Date.now()).then(r => {
          if (!r.ok) throw new Error("status " + r.status);
          return r.json();
        });
        const tests = await fetch("live-data/tests.json?t=" + Date.now()).then(r => r.json()).catch(() => ({tests:[]}));
        const badge = document.getElementById("status-badge");
        badge.textContent = st.finished ? "Finished" : "Running";
        badge.className = "badge " + (st.finished ? "done" : "running");
        const s = st.statistics || {};
        document.getElementById("stats").innerHTML =
          `<span><b>${s.total||0}</b> done</span>` +
          `<span class="pass"><b>${s.passed||0}</b> pass</span>` +
          `<span class="fail"><b>${s.failed||0}</b> fail</span>` +
          `<span class="skip"><b>${s.skipped||0}</b> skip</span>` +
          (st.currentTest ? `<span>current: <b>${st.currentTest}</b></span>` : "");
        const rows = document.getElementById("rows");
        const list = (tests.tests || []).slice().reverse();
        rows.innerHTML = list.map(t => {
          const cls = (t.status||"").toLowerCase();
          return `<tr>
            <td class="${cls}">${t.status||""}</td>
            <td>${(t.fullName||t.name||"").replace(/</g,"&lt;")}</td>
            <td>${fmt(t.duration)}</td>
            <td>${(t.message||"").replace(/</g,"&lt;").slice(0,120)}</td>
          </tr>`;
        }).join("") || `<tr><td colspan="4" style="color:var(--muted)">Waiting for tests…</td></tr>`;
        document.getElementById("error").hidden = true;
        if (!st.finished) setTimeout(tick, 1000);
        else setTimeout(tick, 5000);
      } catch (e) {
        const el = document.getElementById("error");
        el.hidden = false;
        el.textContent = "Could not load live data: " + e.message +
          " — open via a local server if using file://";
        setTimeout(tick, 2000);
      }
    }
    tick();
  </script>
</body>
</html>
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


class LiveReportListener:
    """
    Robot Framework listener (API v3) that writes a live-updating report.

    Argument: ``outdir=<path>`` (default: ``live-report``).
    """

    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self, outdir: str = "live-report"):
        # Robot passes listener args as a single string after the class path
        if outdir.startswith("outdir="):
            outdir = outdir.split("=", 1)[1]
        self.outdir = Path(outdir)
        self.data_dir = self.outdir / "live-data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.outdir / "live.html").write_text(_LIVE_HTML, encoding="utf-8")
        self._tests: list[dict[str, Any]] = []
        self._stats = {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
        self._current: str | None = None
        self._suite_stack: list[str] = []
        self._started = time.time()
        self._finished = False
        self._flush_status()
        _write_json(self.data_dir / "tests.json", {"tests": []})
        _write_json(
            self.data_dir / "summary.json",
            {"generated": _now_iso(), "generator": "ReportLens Live", "statistics": dict(self._stats)},
        )

    def _flush_status(self) -> None:
        elapsed_ms = int((time.time() - self._started) * 1000)
        _write_json(
            self.data_dir / "status.json",
            {
                "finished": self._finished,
                "currentTest": self._current,
                "suiteStack": list(self._suite_stack),
                "statistics": dict(self._stats),
                "elapsedMs": elapsed_ms,
                "updatedAt": _now_iso(),
            },
        )

    def _flush_tests(self) -> None:
        _write_json(self.data_dir / "tests.json", {"tests": list(self._tests)})
        _write_json(
            self.data_dir / "summary.json",
            {
                "generated": _now_iso(),
                "generator": "ReportLens Live",
                "statistics": dict(self._stats),
                "finished": self._finished,
            },
        )
        self._flush_status()

    def start_suite(self, data, result):  # noqa: ARG002 — Robot listener signature
        name = getattr(data, "name", None) or getattr(result, "name", "") or "Suite"
        self._suite_stack.append(str(name))
        self._flush_status()

    def end_suite(self, data, result):  # noqa: ARG002
        if self._suite_stack:
            self._suite_stack.pop()
        self._flush_status()

    def start_test(self, data, result):  # noqa: ARG002
        name = getattr(data, "name", None) or getattr(result, "name", "") or "Test"
        suite = ".".join(self._suite_stack)
        self._current = f"{suite}.{name}" if suite else str(name)
        self._flush_status()

    def end_test(self, data, result):
        name = getattr(data, "name", None) or getattr(result, "name", "") or "Test"
        suite = ".".join(self._suite_stack)
        full = f"{suite}.{name}" if suite else str(name)
        status = (getattr(result, "status", None) or "PASS").upper()
        message = (getattr(result, "message", None) or "").strip()
        elapsed = getattr(result, "elapsed_time", None)
        if elapsed is not None and hasattr(elapsed, "total_seconds"):
            duration = int(elapsed.total_seconds() * 1000)
        else:
            duration = int(getattr(result, "elapsedtime", 0) or 0)
        entry = {
            "id": getattr(data, "id", "") or getattr(result, "id", "") or full,
            "name": str(name),
            "fullName": full,
            "status": status,
            "duration": duration,
            "message": message,
        }
        self._tests.append(entry)
        self._stats["total"] = len(self._tests)
        self._stats["passed"] = sum(1 for t in self._tests if t["status"] == "PASS")
        self._stats["failed"] = sum(1 for t in self._tests if t["status"] == "FAIL")
        self._stats["skipped"] = sum(1 for t in self._tests if t["status"] == "SKIP")
        self._current = None
        self._flush_tests()

    def close(self):
        self._finished = True
        self._current = None
        self._flush_tests()


# Alias for shorter --listener paths
Listener = LiveReportListener
