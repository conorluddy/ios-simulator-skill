"""Diff intelligence: regressions, improvements, drift, version mismatch."""

from __future__ import annotations

from common.hang_pipeline import (
    SummaryBuilder,
    bucket_severity,
    compute_fingerprint,
    diff_sessions,
    format_diff,
)
from tests.fixtures.sample_session import make_events, make_summary


# === diff_sessions ===


def test_diff_no_change_when_identical():
    a = make_summary(session_id="hang-a")
    b = make_summary(session_id="hang-b")
    result = diff_sessions(a, b)
    assert result["verdict"] == "no change"
    assert not result["new_clusters"]
    assert not result["resolved_clusters"]


def test_diff_detects_new_critical_cluster():
    a = make_summary(session_id="hang-a")
    b_events = make_events()
    # Add a new high-severity event with a fresh fingerprint.
    from common.hang_pipeline import NormalisedEvent

    b_events.append(
        NormalisedEvent(
            delta_ms=29_000,
            process="MyApp",
            pid=42,
            duration_ms=1800,
            severity=bucket_severity(1800),
            symbol="[BrandNew explode:]",
            message_prefix="brand-new hang",
            fingerprint=compute_fingerprint("[BrandNew explode:]", "brand-new hang"),
        )
    )
    b = SummaryBuilder(
        session_id="hang-b",
        started_at="2026-05-22T14:35:00",
        duration_ms=30_000,
    ).build(b_events)
    result = diff_sessions(a, b)
    assert any(
        "[BrandNew explode:]" == c["symbol_or_prefix"] for c in result["new_clusters"]
    )
    assert "regression" in result["verdict"]
    assert "critical" in result["verdict"]


def test_diff_detects_resolved_cluster():
    a = make_summary(session_id="hang-a")
    # B has fewer fingerprints than A — at least one resolved.
    b_events = [
        e for e in make_events() if e.symbol != "[ImageDecoder decode:]"
    ]
    b = SummaryBuilder(
        session_id="hang-b",
        started_at="2026-05-22T14:35:00",
        duration_ms=30_000,
    ).build(b_events)
    result = diff_sessions(a, b)
    assert any(
        c["symbol_or_prefix"] == "[ImageDecoder decode:]" for c in result["resolved_clusters"]
    )


def test_diff_flags_drift_when_max_duration_grows():
    a_events = make_events()
    a = SummaryBuilder(
        session_id="hang-a", started_at="t", duration_ms=30_000
    ).build(a_events)
    # B with the same fingerprints but 40% longer durations.
    from common.hang_pipeline import NormalisedEvent

    b_events = [
        NormalisedEvent(
            delta_ms=e.delta_ms,
            process=e.process,
            pid=e.pid,
            duration_ms=e.duration_ms * 1.4,
            severity=bucket_severity(e.duration_ms * 1.4),
            symbol=e.symbol,
            message_prefix=e.message_prefix,
            fingerprint=e.fingerprint,
        )
        for e in a_events
    ]
    b = SummaryBuilder(
        session_id="hang-b", started_at="t", duration_ms=30_000
    ).build(b_events)
    result = diff_sessions(a, b)
    assert len(result["drift"]) > 0
    # 40% bump should flag as worsened, not improved.
    assert all(d["delta_pct"] > 0 for d in result["drift"])


def test_diff_version_mismatch_skips_structural():
    a = make_summary(session_id="hang-a")
    b = make_summary(session_id="hang-b")
    b.fingerprint_version = 99
    result = diff_sessions(a, b)
    assert result["version_mismatch"] is True
    assert "skipped" in result["verdict"]
    # No structural keys when mismatched.
    assert "new_clusters" not in result or not result.get("new_clusters")


# === format_diff ===


def test_format_diff_no_change():
    a = make_summary(session_id="hang-a")
    b = make_summary(session_id="hang-b")
    out = format_diff(diff_sessions(a, b))
    assert "no change" in out
    assert "hang-a" in out
    assert "hang-b" in out


def test_format_diff_version_mismatch_carries_warning():
    a = make_summary(session_id="hang-a")
    b = make_summary(session_id="hang-b")
    b.fingerprint_version = 99
    out = format_diff(diff_sessions(a, b))
    assert "mismatch" in out.lower()
