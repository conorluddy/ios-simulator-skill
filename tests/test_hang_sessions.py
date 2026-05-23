"""Lifecycle + storage tests for common.hang_sessions."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from common.hang_pipeline import (
    NormalisedEvent,
    Severity,
    SummaryBuilder,
    compute_fingerprint,
    event_to_jsonl,
)
from common.hang_sessions import SessionStore, _generate_session_id, _resolve_cutoff_ms


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    return SessionStore(tmp_path / "sessions")


# === session ID ===


def test_generate_session_id_format():
    sid = _generate_session_id()
    parts = sid.split("-")
    assert len(parts) == 4
    assert parts[0] == "hang"
    assert len(parts[1]) == 8
    assert len(parts[2]) == 6
    assert len(parts[3]) == 4


def test_generate_session_id_uniqueness():
    # 4-hex suffix gives 65,536 values per same-second window; this proves the
    # suffix is actually random, without inviting birthday-paradox flakiness.
    ids = {_generate_session_id() for _ in range(20)}
    assert len(ids) == 20


# === create ===


def test_create_lays_down_dir_with_initial_meta(store: SessionStore):
    meta = store.create({"min_hang_ms": 200, "bundle_id": "com.example.app"})
    session_dir = store.session_dir(meta.session_id)
    assert session_dir.is_dir()
    assert (session_dir / "meta.json").exists()
    assert (session_dir / "events.jsonl").exists()
    assert meta.status == "pending"
    assert meta.pid is None


def test_load_meta_roundtrips(store: SessionStore):
    meta = store.create({"min_hang_ms": 250})
    loaded = store.load_meta(meta.session_id)
    assert loaded.session_id == meta.session_id
    assert loaded.args["min_hang_ms"] == 250


# === claim + wait ===


def test_claim_worker_sets_running(store: SessionStore):
    meta = store.create({})
    claimed = store.claim_worker(meta.session_id, pid=os.getpid())
    assert claimed.status == "running"
    assert claimed.pid == os.getpid()


def test_wait_for_worker_returns_when_running(store: SessionStore):
    meta = store.create({})
    store.claim_worker(meta.session_id, pid=os.getpid())
    out = store.wait_for_worker(meta.session_id, timeout_seconds=0.5)
    assert out.status == "running"


def test_wait_for_worker_times_out(store: SessionStore):
    meta = store.create({})
    with pytest.raises(TimeoutError):
        store.wait_for_worker(meta.session_id, timeout_seconds=0.2)


# === events.jsonl ===


def _norm(symbol: str, ms: float, delta: int) -> NormalisedEvent:
    return NormalisedEvent(
        delta_ms=delta,
        process="MyApp",
        pid=1,
        duration_ms=ms,
        severity=Severity.CRITICAL if ms >= 500 else Severity.WARN,
        symbol=symbol,
        message_prefix="prefix",
        fingerprint=compute_fingerprint(symbol, "prefix"),
    )


def test_read_events_filters_sentinel(store: SessionStore):
    meta = store.create({})
    path = store.events_path(meta.session_id)
    with open(path, "w") as handle:
        handle.write(event_to_jsonl(_norm("[A]", 300, 100)) + "\n")
        handle.write('{"event":"stream_ended","at_ms":1234}\n')
        handle.write(event_to_jsonl(_norm("[B]", 600, 200)) + "\n")
    events = store.read_events(meta.session_id)
    assert len(events) == 2
    assert {e.symbol for e in events} == {"[A]", "[B]"}


def test_read_events_skips_corrupt_lines(store: SessionStore):
    meta = store.create({})
    path = store.events_path(meta.session_id)
    with open(path, "w") as handle:
        handle.write(event_to_jsonl(_norm("[A]", 300, 100)) + "\n")
        handle.write("garbage that is not json\n")
        handle.write(event_to_jsonl(_norm("[B]", 600, 200)) + "\n")
    events = store.read_events(meta.session_id)
    assert len(events) == 2


# === stop + summary ===


def test_stop_writes_summary_and_marks_stopped(store: SessionStore):
    meta = store.create({})
    store.claim_worker(meta.session_id, pid=os.getpid())
    builder = SummaryBuilder(
        session_id=meta.session_id,
        started_at=meta.started_at,
        duration_ms=10_000,
    )
    summary = builder.build([_norm("[A]", 600, 1000)])
    store.stop(meta.session_id, summary)
    loaded_meta = store.load_meta(meta.session_id)
    assert loaded_meta.status == "stopped"
    assert loaded_meta.stopped_at is not None
    loaded_summary = store.load_summary(meta.session_id)
    assert loaded_summary is not None
    assert loaded_summary.event_count == 1


def test_build_summary_reads_events_and_clusters(store: SessionStore):
    meta = store.create({})
    path = store.events_path(meta.session_id)
    with open(path, "w") as handle:
        for i in range(5):
            handle.write(event_to_jsonl(_norm("[A]", 600, i * 100)) + "\n")
        for i in range(3):
            handle.write(event_to_jsonl(_norm("[B]", 300, 5_000 + i * 100)) + "\n")
    summary = store.build_summary(
        meta.session_id, matched_lines=8, total_lines=500, dropped_below_threshold=2
    )
    assert summary.event_count == 8
    assert len(summary.clusters) == 2
    assert summary.dropped_below_threshold == 2


# === list / clear / prune ===


def test_list_sessions_newest_first(store: SessionStore):
    a = store.create({})
    time.sleep(0.01)
    b = store.create({})
    listed = store.list_sessions()
    assert [m.session_id for m in listed] == [b.session_id, a.session_id]


def test_clear_removes_all_when_no_filter(store: SessionStore):
    for _ in range(3):
        store.create({})
        time.sleep(0.001)
    assert store.clear() == 3
    assert store.list_sessions() == []


def test_clear_older_than_filters_recent(store: SessionStore):
    meta = store.create({})
    deleted = store.clear(older_than="1h")
    # Just-created session is younger than 1h; should NOT be deleted.
    assert deleted == 0
    assert store.list_sessions()[0].session_id == meta.session_id


def test_clear_older_than_zero_deletes_all(store: SessionStore):
    store.create({})
    store.create({})
    # An ``older than 0s`` cutoff is "everything not created in the future" → all gone.
    deleted = store.clear(older_than="0s")
    assert deleted == 2


def test_prune_expired_uses_default_ttl(store: SessionStore):
    meta = store.create({})
    # TTL of 24h (default); fresh session should remain.
    assert store.prune_expired() == 0
    assert store.list_sessions()[0].session_id == meta.session_id


# === signal_worker ===


def test_signal_worker_returns_false_when_no_pid(store: SessionStore):
    meta = store.create({})
    # status=pending, pid=None
    assert store.signal_worker(meta.session_id) is False


def test_signal_worker_returns_false_for_dead_pid(store: SessionStore):
    meta = store.create({})
    # PID 1 typically refuses SIGTERM from non-root; emulates a dead process.
    # Use a more reliable approach: a very high PID likely doesn't exist.
    store.claim_worker(meta.session_id, pid=999_999)
    # ProcessLookupError → returns False
    assert store.signal_worker(meta.session_id) is False


# === duration parser ===


def test_resolve_cutoff_ms_accepts_all_units():
    for token in ("30s", "5m", "1h", "2d"):
        assert isinstance(_resolve_cutoff_ms(token), int)


def test_resolve_cutoff_ms_rejects_invalid():
    with pytest.raises(ValueError):
        _resolve_cutoff_ms("bogus")


# === atomic writes ===


def test_meta_write_is_atomic(store: SessionStore):
    meta = store.create({})
    # No .tmp residue after write.
    tmp = (store.session_dir(meta.session_id) / "meta.json.tmp")
    assert not tmp.exists()


def test_meta_json_is_valid(store: SessionStore):
    meta = store.create({"foo": "bar"})
    with open(store.session_dir(meta.session_id) / "meta.json") as handle:
        payload = json.load(handle)
    assert payload["args"]["foo"] == "bar"


# === auto_samples (JSONL) ===


def test_stash_auto_sample_appends_jsonl(store: SessionStore):
    meta = store.create({})
    store.stash_auto_sample(meta.session_id, "fp:aaa", {"stack": ["a", "b"], "reason": "ok"})
    store.stash_auto_sample(meta.session_id, "fp:bbb", {"stack": ["c"], "reason": "ok"})

    samples = store.read_auto_samples(meta.session_id)
    assert set(samples.keys()) == {"fp:aaa", "fp:bbb"}
    assert samples["fp:aaa"]["stack"] == ["a", "b"]
    assert samples["fp:bbb"]["stack"] == ["c"]


def test_stash_auto_sample_last_write_wins_per_fingerprint(store: SessionStore):
    meta = store.create({})
    store.stash_auto_sample(meta.session_id, "fp:dup", {"reason": "first"})
    store.stash_auto_sample(meta.session_id, "fp:dup", {"reason": "second"})

    samples = store.read_auto_samples(meta.session_id)
    assert samples["fp:dup"]["reason"] == "second"


def test_read_auto_samples_returns_empty_when_missing(store: SessionStore):
    meta = store.create({})
    assert store.read_auto_samples(meta.session_id) == {}


def test_concurrent_stash_drops_nothing(store: SessionStore):
    """Two threads stashing in tight succession must both land — append-only avoids the
    read-modify-write race the old auto_samples.json had."""
    import threading

    meta = store.create({})
    fingerprints = [f"fp:{i:04d}" for i in range(50)]
    threads = [
        threading.Thread(
            target=store.stash_auto_sample,
            args=(meta.session_id, fp, {"reason": fp}),
        )
        for fp in fingerprints
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    samples = store.read_auto_samples(meta.session_id)
    assert set(samples.keys()) == set(fingerprints)


def test_read_auto_samples_skips_corrupt_lines(store: SessionStore):
    meta = store.create({})
    # Manually corrupt the file with one bad line between two good ones.
    path = store.session_dir(meta.session_id) / "auto_samples.jsonl"
    with open(path, "w") as handle:
        handle.write(json.dumps({"fingerprint": "fp:1", "sample": {"reason": "good"}}) + "\n")
        handle.write("not-json\n")
        handle.write(json.dumps({"fingerprint": "fp:2", "sample": {"reason": "good"}}) + "\n")

    samples = store.read_auto_samples(meta.session_id)
    assert set(samples.keys()) == {"fp:1", "fp:2"}
