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


# === zero-duration drift handling (#79) ===


def _zero_dur_summary(session_id: str, clusters: dict[str, float]) -> "SessionSummary":
    """Build a SessionSummary with a controlled fingerprint → max_duration_ms map."""
    from common.hang_pipeline import Cluster, NormalisedEvent, SessionSummary, Severity

    cluster_list = [
        Cluster(
            fingerprint=fp,
            count=1,
            max_duration_ms=max_dur,
            total_duration_ms=max_dur,
            first_delta_ms=0,
            severity=Severity.CRITICAL if max_dur >= 500 else Severity.MINOR,
            symbol_or_prefix=fp,
            sample_event=NormalisedEvent(
                delta_ms=0,
                process="p",
                pid=1,
                duration_ms=max_dur,
                severity=Severity.CRITICAL if max_dur >= 500 else Severity.MINOR,
                symbol=fp,
                message_prefix=fp,
                fingerprint=fp,
            ),
        )
        for fp, max_dur in clusters.items()
    ]
    return SessionSummary(
        session_id=session_id,
        started_at="t",
        duration_ms=1000,
        event_count=len(cluster_list),
        dropped_below_threshold=0,
        matched_lines=len(cluster_list),
        total_lines=len(cluster_list),
        clusters=cluster_list,
        aggregates={},
    )


def test_diff_zero_to_zero_counts_as_stable():
    a = _zero_dur_summary("hang-a", {"fp:silent": 0.0})
    b = _zero_dur_summary("hang-b", {"fp:silent": 0.0})
    result = diff_sessions(a, b)
    assert result["stable_count"] == 1
    assert not result["drift"]


def test_diff_zero_to_nonzero_is_drift_with_inf_delta():
    a = _zero_dur_summary("hang-a", {"fp:newsignal": 0.0})
    b = _zero_dur_summary("hang-b", {"fp:newsignal": 800.0})
    result = diff_sessions(a, b)
    assert len(result["drift"]) == 1
    assert result["drift"][0]["delta_pct"] == float("inf")
    assert result["drift"][0]["max_duration_ms_a"] == 0.0
    assert result["drift"][0]["max_duration_ms_b"] == 800.0


def test_diff_nonzero_to_zero_is_drift_with_minus_one_hundred():
    a = _zero_dur_summary("hang-a", {"fp:fixed": 800.0})
    b = _zero_dur_summary("hang-b", {"fp:fixed": 0.0})
    result = diff_sessions(a, b)
    assert len(result["drift"]) == 1
    assert result["drift"][0]["delta_pct"] == -100.0


def test_diff_nonzero_unchanged_still_uses_threshold():
    # Regression guard — the new zero-handling branches must not break the standard path.
    a = _zero_dur_summary("hang-a", {"fp:steady": 500.0})
    b = _zero_dur_summary("hang-b", {"fp:steady": 505.0})  # 1% drift, well under 20% threshold
    result = diff_sessions(a, b)
    assert result["stable_count"] == 1
    assert not result["drift"]


def test_format_diff_renders_inf_delta_as_new():
    a = _zero_dur_summary("hang-a", {"fp:newsignal": 0.0})
    b = _zero_dur_summary("hang-b", {"fp:newsignal": 800.0})
    out = format_diff(diff_sessions(a, b))
    assert "new" in out
    assert "inf" not in out.lower()
