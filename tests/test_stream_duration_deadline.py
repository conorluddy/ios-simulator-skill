"""Regression tests: --duration must fire even when the log stream goes quiet.

`log stream` never exits on its own and can go silent for hours (idle app,
hang-quiet simulator). The old loops in `log_monitor.stream_logs()` and
`hang_watcher.HangWatcher.watch()` only checked the deadline *after* a
blocking `stdout.readline()` returned, so on a quiet stream --duration never
fired and the process hung until EOF — observed as a multi-day hang in the
wild. `log_monitor` additionally called `wait()` unbounded on a process that
never self-exits.

These tests stub Popen with a producer that emits a 200-line burst and then
holds the pipe open silently. The stream loops must return all lines and exit
on the deadline, not on EOF. A select()-on-fd approach fails the line-count
assertion here: with text=True pipes, lines already drained into the
user-space text buffer are invisible to select() and get dropped at the
deadline.
"""

import subprocess
import sys
import time

import hang_watcher
import log_monitor

LINE_COUNT = 200
QUIET_SECONDS = 10  # pipe stays open, silent, well past every deadline below

PRODUCER = (
    "import sys,time\n"
    f"for i in range({LINE_COUNT}):\n"
    "    print(f'burst line {i}')\n"
    "sys.stdout.flush()\n"
    f"time.sleep({QUIET_SECONDS})\n"
)

REAL_POPEN = subprocess.Popen


def _producer_popen(*_args, **kwargs):
    """Stand-in for `xcrun simctl ... log stream`: burst then silence.

    Keeps the caller's pipe/text/bufsize kwargs so pipe semantics match
    production exactly.
    """
    return REAL_POPEN([sys.executable, "-c", PRODUCER], **kwargs)


def test_log_monitor_duration_fires_on_quiet_stream(monkeypatch):
    monkeypatch.setattr(subprocess, "Popen", _producer_popen)
    monitor = log_monitor.LogMonitor()

    start = time.monotonic()
    assert monitor.stream_logs(duration=1.0) is True
    elapsed = time.monotonic() - start

    assert monitor.total_lines == LINE_COUNT  # burst fully drained, no tail loss
    assert 1.0 <= elapsed < 5.0  # deadline fired; not blocked until producer EOF


def test_hang_watcher_duration_fires_on_quiet_stream(monkeypatch):
    monkeypatch.setattr(subprocess, "Popen", _producer_popen)
    watcher = hang_watcher.HangWatcher(udid="FAKE-UDID")
    monkeypatch.setattr(watcher, "_resolve_udid", lambda: "FAKE-UDID")

    seen = []
    real_parse = watcher._parse_line
    monkeypatch.setattr(watcher, "_parse_line", lambda line: seen.append(line) or real_parse(line))

    start = time.monotonic()
    assert watcher.watch(duration_seconds=1, predicate="test-predicate") is True
    elapsed = time.monotonic() - start

    assert len(seen) == LINE_COUNT  # burst fully drained, no tail loss
    assert 1.0 <= elapsed < 5.0  # deadline fired; not blocked until producer EOF
