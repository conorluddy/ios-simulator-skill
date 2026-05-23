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
    dropped_symbol = "[ImageDecoderForLargeRasterAssets decodeWithOptions:]"
    b_events = [e for e in make_events() if e.symbol != dropped_symbol]
    b = SummaryBuilder(
        session_id="hang-b",
        started_at="2026-05-22T14:35:00",
        duration_ms=30_000,
    ).build(b_events)
    result = diff_sessions(a, b)
    assert any(
        c["symbol_or_prefix"] == dropped_symbol for c in result["resolved_clusters"]
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


# === verdict coverage (#82): the 3 verdicts not exercised elsewhere ===


def _summary_with_clusters(session_id: str, clusters_spec: list[tuple[str, float, str]]):
    """Build a SessionSummary from (fingerprint, max_dur, severity) tuples."""
    from common.hang_pipeline import Cluster, NormalisedEvent, SessionSummary, Severity

    clusters = [
        Cluster(
            fingerprint=fp,
            count=1,
            max_duration_ms=max_dur,
            total_duration_ms=max_dur,
            first_delta_ms=0,
            severity=Severity(sev),
            symbol_or_prefix=fp,
            sample_event=NormalisedEvent(
                delta_ms=0,
                process="p",
                pid=1,
                duration_ms=max_dur,
                severity=Severity(sev),
                symbol=fp,
                message_prefix=fp,
                fingerprint=fp,
            ),
        )
        for fp, max_dur, sev in clusters_spec
    ]
    return SessionSummary(
        session_id=session_id,
        started_at="t",
        duration_ms=1000,
        event_count=len(clusters),
        dropped_below_threshold=0,
        matched_lines=len(clusters),
        total_lines=len(clusters),
        clusters=clusters,
        aggregates={},
    )


def test_diff_verdict_regression_new_minor():
    # A is empty, B has one new MINOR cluster — verdict should NOT be "new critical".
    a = _summary_with_clusters("hang-a", [])
    b = _summary_with_clusters("hang-b", [("fp:newminor", 200.0, "minor")])
    result = diff_sessions(a, b)
    assert result["verdict"] == "regression: 1 new minor"


def test_diff_verdict_improvement_resolved():
    a = _summary_with_clusters("hang-a", [("fp:wasthere", 500.0, "critical")])
    b = _summary_with_clusters("hang-b", [])
    result = diff_sessions(a, b)
    assert result["verdict"] == "improvement: 1 resolved"


def test_diff_verdict_drift_mixed_signs():
    # Shared fingerprints with one worsening + one improving in B.
    a = _summary_with_clusters("hang-a", [("fp:up", 500.0, "critical"), ("fp:down", 800.0, "critical")])
    b = _summary_with_clusters("hang-b", [("fp:up", 800.0, "critical"), ("fp:down", 500.0, "critical")])
    result = diff_sessions(a, b)
    assert result["verdict"] == "drift: 1 worsened, 1 improved"


# === format_diff render coverage (#82) ===


def test_format_diff_renders_new_block():
    a = _summary_with_clusters("hang-a", [])
    b = _summary_with_clusters("hang-b", [("fp:fresh", 1500.0, "critical")])
    out = format_diff(diff_sessions(a, b))
    assert "New (" in out
    assert "fp:fresh" in out
    assert "1500" in out


def test_format_diff_renders_resolved_block():
    a = _summary_with_clusters("hang-a", [("fp:gone", 700.0, "warn")])
    b = _summary_with_clusters("hang-b", [])
    out = format_diff(diff_sessions(a, b))
    assert "Resolved (" in out
    assert "fp:gone" in out


def test_format_diff_renders_drift_block():
    # 60% bump triggers drift entry.
    a = _summary_with_clusters("hang-a", [("fp:slow", 500.0, "critical")])
    b = _summary_with_clusters("hang-b", [("fp:slow", 800.0, "critical")])
    out = format_diff(diff_sessions(a, b))
    assert "Drift (" in out
    assert "fp:slow" in out
    assert "500" in out
    assert "800" in out
