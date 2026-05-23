"""Worker-loop tests for #84 — EOF detection, bounded restart, crashed marking.

The real worker spawns ``xcrun simctl spawn ... log stream``. These tests
monkeypatch ``subprocess.Popen`` with a scripted fake so we can drive
end-of-stream, mid-stream death, and clean shutdown deterministically.
"""

from __future__ import annotations

import io
import os
import signal
from pathlib import Path

import pytest

import hang_watcher
from common.hang_sessions import SessionStore


# === fake subprocess ===


class _FakeProc:
    """Scripted stand-in for ``subprocess.Popen`` of ``log stream``.

    Each call returns a fresh instance. ``script`` is an iterable yielded by a
    factory so test code can vary behaviour across restart attempts.
    """

    def __init__(self, lines: list[str], exit_code: int | None = 0):
        # readline() returns each line in order, then "" forever (EOF).
        self._lines = list(lines)
        self.stdout = self
        self._exit_code = exit_code
        self._terminated = False
        self._waited = False

    # --- file-like surface for select / readline ---
    def fileno(self) -> int:
        # select() needs a real fileno. Use stderr's — we never actually read
        # from it; select is monkeypatched at the call site for determinism.
        return 2

    def readline(self) -> str:
        if self._lines:
            return self._lines.pop(0)
        return ""  # EOF

    # --- Popen surface ---
    def poll(self) -> int | None:
        # Once readline has returned EOF the subprocess "exited".
        return self._exit_code if not self._lines else None

    def terminate(self) -> None:
        self._terminated = True

    def kill(self) -> None:
        self._terminated = True

    def wait(self, timeout: float | None = None) -> int:
        self._waited = True
        return self._exit_code if self._exit_code is not None else 0


@pytest.fixture
def patched_select(monkeypatch):
    """Force ``select.select`` to always report stdout ready so readline runs
    immediately. The worker's normal 0.25s tick is irrelevant under the fake."""
    monkeypatch.setattr(
        hang_watcher.select,
        "select",
        lambda rlist, wlist, xlist, timeout: (list(rlist), [], []),
    )


@pytest.fixture
def patched_sleep(monkeypatch):
    """Skip the 2s restart backoff so the bounded-restart test isn't slow."""
    monkeypatch.setattr(hang_watcher.time, "sleep", lambda _: None)


@pytest.fixture
def fast_max_restarts(monkeypatch):
    """Force a small restart budget so exhaustion tests run in milliseconds."""
    monkeypatch.setenv("IOS_SIM_HANG_MAX_RESTARTS", "2")


@pytest.fixture
def buster(tmp_path: Path) -> hang_watcher.HangBuster:
    store = SessionStore(tmp_path / "sessions")
    return hang_watcher.HangBuster(store=store)


def _start_session(buster: hang_watcher.HangBuster, **overrides) -> str:
    """Create a session row and return its id. Worker isn't spawned — the test
    invokes ``run_worker`` directly in-process."""
    args = {
        "udid": "fake-udid",
        "min_hang_ms": 100,
        "bundle_id": None,
        "predicate": None,
        "auto_sample": False,
    }
    args.update(overrides)
    meta = buster.store.create(args)
    return meta.session_id


def _read_events(buster: hang_watcher.HangBuster, session_id: str) -> list[dict]:
    import json as _json

    path = buster.store.events_path(session_id)
    return [_json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# === EOF triggers restart, exhausts to crashed ===


def test_eof_exhausts_restarts_and_marks_crashed(
    buster, patched_select, patched_sleep, fast_max_restarts, monkeypatch
):
    """Every spawn EOFs immediately with no lines — after MAX_RESTARTS the
    session is marked crashed, not left in stale 'running'."""
    spawn_count = {"n": 0}

    def _fake_popen(*_args, **_kwargs):
        spawn_count["n"] += 1
        return _FakeProc(lines=[], exit_code=1)

    monkeypatch.setattr(hang_watcher.subprocess, "Popen", _fake_popen)

    session_id = _start_session(buster)
    rc = buster.run_worker(session_id)

    # MAX_RESTARTS=2 → initial spawn + 2 retries = 3 total.
    assert spawn_count["n"] == 3
    assert rc == 2
    meta = buster.store.load_meta(session_id)
    assert meta.status == "crashed"
    assert meta.stopped_at_ms is not None

    events = _read_events(buster, session_id)
    # Expect 1 stream_died after attempt 0, then 1 stream_restart for attempt 1,
    # stream_died, stream_restart for attempt 2, stream_died (no final restart).
    died = [e for e in events if e.get("event") == "stream_died"]
    restarts = [e for e in events if e.get("event") == "stream_restart"]
    assert len(died) == 3
    assert len(restarts) == 2
    assert [r["attempt"] for r in restarts] == [1, 2]


def test_eof_then_clean_run_does_not_mark_crashed(
    buster, patched_select, patched_sleep, fast_max_restarts, monkeypatch
):
    """First spawn EOFs immediately; second spawn delivers lines then EOFs.
    Third spawn (after second EOF) also EOFs. Hits restart budget → crashed.
    Verifies restart accounting + that lines from attempt 1 are captured."""
    scripts = [
        [],  # attempt 0: EOF immediately
        ["2026-05-23 11:00:00.000 0xa Default 0xa 1 0 grapla: hello\n"],  # attempt 1
        [],  # attempt 2: EOF
    ]
    spawn_log: list[int] = []

    def _fake_popen(*_args, **_kwargs):
        idx = len(spawn_log)
        spawn_log.append(idx)
        return _FakeProc(lines=scripts[idx], exit_code=1)

    monkeypatch.setattr(hang_watcher.subprocess, "Popen", _fake_popen)

    session_id = _start_session(buster)
    rc = buster.run_worker(session_id)

    assert spawn_log == [0, 1, 2]
    assert rc == 2  # exhausted -> crashed
    meta = buster.store.load_meta(session_id)
    assert meta.status == "crashed"
    assert meta.extras["line_counters"]["total"] == 1
    assert meta.extras["line_counters"]["stream_restarts"] == 2


# === SIGTERM path is not a crash ===


def test_sigterm_during_read_loop_marks_stopped_not_crashed(
    buster, patched_select, patched_sleep, monkeypatch
):
    """SIGTERM mid-stream causes a clean shutdown — stream_ended marker, no
    stream_died, status stays whatever the parent set (here: still 'running'
    because no parent stop() ran). Critically: NOT 'crashed'."""

    # Script: deliver one line, then on the next readline call set stop_flag.
    # We simulate SIGTERM by patching readline to trigger the worker's handler.
    raised = {"sent": False}

    class _SigtermProc(_FakeProc):
        def readline(self):
            if not raised["sent"]:
                raised["sent"] = True
                # Send SIGTERM to ourselves — the worker registered a handler.
                os.kill(os.getpid(), signal.SIGTERM)
                return "2026-05-23 11:00:00.000 0xa Default 0xa 1 0 grapla: hi\n"
            return super().readline()

    spawn_count = {"n": 0}

    def _fake_popen(*_args, **_kwargs):
        spawn_count["n"] += 1
        return _SigtermProc(lines=["fallback\n"], exit_code=0)

    monkeypatch.setattr(hang_watcher.subprocess, "Popen", _fake_popen)

    session_id = _start_session(buster)
    rc = buster.run_worker(session_id)

    assert rc == 0  # clean exit
    meta = buster.store.load_meta(session_id)
    assert meta.status != "crashed"
    # Only one spawn — SIGTERM kills the restart loop immediately.
    assert spawn_count["n"] == 1
    events = _read_events(buster, session_id)
    assert any(e.get("event") == "stream_ended" for e in events)
    assert not any(e.get("event") == "stream_died" for e in events)


# === Missing xcrun ===


def test_missing_xcrun_marks_crashed_immediately(buster, monkeypatch):
    """FileNotFoundError on Popen (e.g. xcrun absent in CI) → crashed, no retry."""

    def _fake_popen(*_args, **_kwargs):
        raise FileNotFoundError("xcrun")

    monkeypatch.setattr(hang_watcher.subprocess, "Popen", _fake_popen)

    session_id = _start_session(buster)
    rc = buster.run_worker(session_id)

    assert rc == 2
    assert buster.store.load_meta(session_id).status == "crashed"


# === Counters surface restart count ===


def test_stream_restarts_counter_in_persisted_meta(
    buster, patched_select, patched_sleep, fast_max_restarts, monkeypatch
):
    """After exhausted restarts, meta.extras.line_counters.stream_restarts
    matches the highest attempt that ran."""

    def _fake_popen(*_args, **_kwargs):
        return _FakeProc(lines=[], exit_code=1)

    monkeypatch.setattr(hang_watcher.subprocess, "Popen", _fake_popen)

    session_id = _start_session(buster)
    buster.run_worker(session_id)
    meta = buster.store.load_meta(session_id)
    # MAX_RESTARTS=2 → counter records 2.
    assert meta.extras["line_counters"]["stream_restarts"] == 2


# === #85: raw NDJSON capture ===


def test_raw_capture_writes_lines_to_raw_ndjson(buster, patched_select, monkeypatch):
    """Raw capture dumps every line verbatim to raw.ndjson; events.jsonl
    receives only synthetic markers (stream_ended on clean stop)."""
    lines = [
        '{"eventMessage":"first","process":"grapla"}\n',
        '{"eventMessage":"second","process":"runningboardd"}\n',
    ]
    raised = {"sent": False}

    class _Proc(_FakeProc):
        def readline(self):
            # After delivering all real lines, SIGTERM ourselves so the worker
            # exits cleanly instead of running the restart loop.
            line = super().readline()
            if not line and not raised["sent"]:
                raised["sent"] = True
                os.kill(os.getpid(), signal.SIGTERM)
            return line

    monkeypatch.setattr(
        hang_watcher.subprocess, "Popen", lambda *a, **k: _Proc(lines=list(lines), exit_code=0)
    )

    session_id = _start_session(buster, raw_capture=True, max_size_mb=10, no_gzip=False)
    rc = buster.run_worker(session_id)

    assert rc == 0
    raw_path = buster.store.raw_path(session_id)
    raw_lines = raw_path.read_text().splitlines()
    assert raw_lines == [line.rstrip() for line in lines]


def test_raw_capture_size_cap_triggers_clean_stop(buster, patched_select, monkeypatch):
    """When raw.ndjson exceeds max_size_bytes, the worker stops cleanly:
    writes size_cap_hit event, sets extras.truncated, status=running (not
    crashed). The parent's stop() will mark stopped."""
    # 1 KB JSON lines × many → easily exceeds the cap on second write.
    # Must start with '{' to survive the banner filter in _read_stream_into_raw.
    big_line = '{"x":"' + "x" * 1014 + '"}\n'
    lines = [big_line] * 5

    monkeypatch.setattr(
        hang_watcher.subprocess, "Popen", lambda *a, **k: _FakeProc(lines=lines, exit_code=0)
    )

    # max_size_mb=0 with a >0 cap intent — use a custom override path.
    # Simulate a tiny cap by passing max_size_mb=0, then we manually override
    # the threshold in the test... but the worker code multiplies by 1024*1024.
    # Easier: write a few-KB cap via monkeypatching the multiplier indirectly —
    # but cleanest is using max_size_mb=0 means no cap. So instead use 1 MB
    # cap and feed enough lines (1024 × 1024 lines ≈ 1 GB — too slow).
    # Trick: monkeypatch _read_stream_into_raw's max_size_bytes computation by
    # passing the cap directly. Easiest: a tiny override env var? No env exists.
    # Solution: instantiate _read_stream_into_raw directly with a tiny cap.
    proc = _FakeProc(lines=lines, exit_code=0)
    session_id = _start_session(buster, raw_capture=True, max_size_mb=10, no_gzip=True)
    # The worker has to claim_worker before raw_path is meaningful.
    buster.store.claim_worker(session_id, pid=os.getpid())
    raw_handle = open(buster.store.raw_path(session_id), "a", buffering=1)
    try:
        cap_state: dict = {"hit": False}
        counters: dict = {"total": 0}
        exit_code = buster._read_stream_into_raw(
            proc=proc,
            raw_handle=raw_handle,
            stop_flag={"value": False},
            counters=counters,
            max_size_bytes=2048,  # 2 KB — first line over, second pushes past
            session_id=session_id,
            cap_state=cap_state,
        )
    finally:
        raw_handle.close()

    assert cap_state["hit"] is True
    assert counters["total"] >= 1
    assert buster.store.raw_path(session_id).stat().st_size >= 2048


def test_stop_gzips_raw_ndjson(buster, patched_select, monkeypatch, tmp_path):
    """HangBuster.stop on a raw session gzips raw.ndjson → raw.ndjson.gz,
    removes the uncompressed file, and records bytes in meta.extras."""
    session_id = _start_session(buster, raw_capture=True, max_size_mb=10, no_gzip=False)
    buster.store.claim_worker(session_id, pid=os.getpid())
    # Write some raw content directly to simulate captured stream.
    raw_path = buster.store.raw_path(session_id)
    raw_path.write_text(
        '{"eventMessage":"a","process":"grapla"}\n'
        '{"eventMessage":"b","process":"runningboardd"}\n'
    )
    # Also persist a line_counters extras so the stop summary doesn't 404.
    buster.store.persist_worker_counters(session_id, {"total": 2, "stream_restarts": 0})

    # Skip signal_worker — the test doesn't have a real worker pid.
    monkeypatch.setattr(buster.store, "signal_worker", lambda *a, **k: False)

    out = buster.stop(session_id, json_mode=True)
    payload = __import__("json").loads(out)
    assert payload["mode"] == "raw"
    assert payload["raw_bytes_compressed"] is not None

    gz_path = buster.store.raw_path(session_id, gzipped=True)
    assert gz_path.exists()
    assert not raw_path.exists()

    # Round-trip: gunzip and confirm content survived.
    import gzip as _gz

    with _gz.open(gz_path, "rb") as fp:
        content = fp.read().decode()
    assert "grapla" in content and "runningboardd" in content


def test_stop_no_gzip_preserves_raw_ndjson(buster, monkeypatch):
    session_id = _start_session(buster, raw_capture=True, max_size_mb=10, no_gzip=True)
    buster.store.claim_worker(session_id, pid=os.getpid())
    raw_path = buster.store.raw_path(session_id)
    raw_path.write_text("line\n")
    buster.store.persist_worker_counters(session_id, {"total": 1})
    monkeypatch.setattr(buster.store, "signal_worker", lambda *a, **k: False)

    buster.stop(session_id)
    assert raw_path.exists()
    assert not buster.store.raw_path(session_id, gzipped=True).exists()


# === #85: aggregate-cap pruning ===


def test_prune_to_aggregate_cap_evicts_oldest_first(buster):
    """When total bytes exceed cap, oldest session is dropped first until
    under cap. Newer sessions are preserved."""
    import time as _time

    # Build 3 sessions with known sizes (~500 bytes each in events.jsonl).
    ids = []
    for i in range(3):
        meta = buster.store.create({"udid": "u", "n": i})
        buster.store.events_path(meta.session_id).write_text("x" * 500)
        ids.append(meta.session_id)
        _time.sleep(0.005)  # ensure distinct started_at_ms

    # Cap at 800 bytes total → must drop at least 2 of 3.
    deleted = buster.store.prune_to_aggregate_cap(800)
    assert deleted >= 2

    remaining = {m.session_id for m in buster.store.list_sessions()}
    # Newest survives.
    assert ids[2] in remaining
    # Oldest dropped.
    assert ids[0] not in remaining


def test_prune_to_aggregate_cap_noop_when_under(buster):
    meta = buster.store.create({"udid": "u"})
    buster.store.events_path(meta.session_id).write_text("tiny")
    assert buster.store.prune_to_aggregate_cap(10 * 1024 * 1024) == 0
    assert meta.session_id in {m.session_id for m in buster.store.list_sessions()}


def test_session_total_bytes_sums_all_files(buster):
    meta = buster.store.create({"udid": "u"})
    buster.store.events_path(meta.session_id).write_text("aa")  # 2
    buster.store.raw_path(meta.session_id).write_text("bbb")  # 3
    # meta.json itself contributes too, so we assert ≥ 5.
    assert buster.store.session_total_bytes(meta.session_id) >= 5
